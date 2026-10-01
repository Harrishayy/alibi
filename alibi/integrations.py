"""Daemon plugin for outside evidence: Strava sync, Apple Health samples from the phone, the opt-in phone listener.

hooks.py calls start(con) once and tick(con, now) every daemon tick.

Apple Health arrives as events(source='health', kind='samples', session_id=None, ts=noon of payload.date,
payload={date, steps, sleep_h, mindful_min, workout_min, workouts, ...docs/SIGNALS.md}) — one per day, latest wins.
Health habits in habits.yaml: {source: health, metric: <any key of METRICS>, daily_target, display}; metrics marked
lower=True (resting heart rate, headphone level) are met at or below the target.

Round 3 (docs/SIGNALS.md): the phone listener takes single rows or {"batch": [...]} of phone/health rows (stored by
signals.store, which attaches each row to the session its ts falls in), and serves GET /api/phone/session so the
iPhone can couple to a live session. The Mac turns an "Alibi" Focus on/off with each session via Shortcuts.
"""
import datetime as dt, hmac, json, math, os, re, secrets as _rand, socket, subprocess, threading, time
from . import config, db, pinch, secrets as store

STRAVA_EVERY_S = int(os.getenv("STRAVA_SYNC_EVERY_S", "1800"))
PHONE_HOST = os.getenv("PHONE_HOST", "0.0.0.0")        # the phone listener is the only thing Alibi exposes to the LAN
PHONE_PORT = int(os.getenv("PHONE_PORT", "8766"))
STATE_FILE = "integrations_state.json"

METRICS = {
    "steps":       {"label": "Steps",      "unit": "steps", "fmt": lambda v: f"{int(round(v)):,}"},
    "sleep_h":     {"label": "Sleep",      "unit": "h",     "fmt": lambda v: f"{int(v)} h" + (f" {int(round((v % 1) * 60)):02d}" if round((v % 1) * 60) else "")},
    "mindful_min": {"label": "Meditation", "unit": "min",   "fmt": lambda v: f"{int(round(v))} min"},
    "workout_min": {"label": "Workouts",   "unit": "min",   "fmt": lambda v: f"{int(round(v))} min"},
    "exercise_min": {"label": "Exercise",  "unit": "min",   "fmt": lambda v: f"{int(round(v))} min"},
    "distance_km": {"label": "Distance",   "unit": "km",    "fmt": lambda v: f"{v:.1f} km"},
    "flights":     {"label": "Flights climbed", "unit": "flights", "fmt": lambda v: f"{int(round(v))} flights"},
    "active_kcal": {"label": "Active energy", "unit": "kcal", "fmt": lambda v: f"{int(round(v)):,} kcal"},
    "stand_h":     {"label": "Stand hours", "unit": "h",    "fmt": lambda v: f"{int(round(v))} h"},
    "daylight_min": {"label": "Time in daylight", "unit": "min", "fmt": lambda v: f"{int(round(v))} min"},
    "hrv_ms":      {"label": "HRV",        "unit": "ms",    "fmt": lambda v: f"{int(round(v))} ms"},
    "resting_hr":  {"label": "Resting heart rate", "unit": "bpm", "fmt": lambda v: f"{int(round(v))} bpm", "lower": True},
    "resp_rate":   {"label": "Breathing rate", "unit": "/min", "fmt": lambda v: f"{v:.1f}/min", "lower": True},
    "headphone_db": {"label": "Headphone level", "unit": "dB", "fmt": lambda v: f"{int(round(v))} dB", "lower": True},
}
NUMERIC = tuple(k for k in METRICS if k not in ("sleep_h", "mindful_min", "workout_min", "steps"))
SLEEP_STAGES = ("core_h", "deep_h", "rem_h", "awake_h")
PHONE_KINDS = ("motion", "pickup", "screentime", "shield", "focus", "location", "app")
MOTION_STATES = ("stationary", "walking", "running", "automotive", "cycling", "unknown")
BATCH_MAX = 500
SESSION_SYNC_S = int(os.getenv("PHONE_SESSION_SYNC_S", "180"))      # phone sync cadence while a session runs
IDLE_SYNC_S = int(os.getenv("PHONE_IDLE_SYNC_S", "1800"))
FOCUS_ON, FOCUS_OFF = "Alibi Focus On", "Alibi Focus Off"

_strava_thread: threading.Thread | None = None
_strava_last_try = 0.0


# --- small persisted state (not secret) ---------------------------------------------------------------------------

def state() -> dict:
    try:
        return json.loads((config.DATA_DIR / STATE_FILE).read_text())
    except (FileNotFoundError, ValueError):
        return {}


_state_lock = threading.Lock()


def set_state(**kv) -> dict:
    with _state_lock:                                   # the Focus thread and the listener write here too
        d = state()
        d.update(kv)
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = config.DATA_DIR / f".{STATE_FILE}.{os.getpid()}.{threading.get_ident()}.tmp"
        tmp.write_text(json.dumps(d))
        os.replace(tmp, config.DATA_DIR / STATE_FILE)
        return d


# --- plugin hooks -------------------------------------------------------------------------------------------------

def start(con) -> None:
    if state().get("phone_sync_enabled"):
        try:
            phone_start()
        except Exception as e:
            print(f"[alibi] phone sync listener didn't start: {e!r}", flush=True)


def tick(con, now: float) -> None:
    _check_claims(con)
    _maybe_strava(now)
    _focus_sweep(con)


def on_session_start(con, session) -> None:
    set_mac_focus(True)


def on_verdict(con, session) -> None:
    set_mac_focus(False)


# --- Mac "Alibi" Focus via Shortcuts (Focus shares to the iPhone; its Focus filter then shields apps) ----------------

_focus = {"checked": 0.0, "names": set(), "threads": []}      # threads: only the latest run (finished ones dropped)
FOCUS_MAX_FAILS = int(os.getenv("ALIBI_FOCUS_MAX_FAILS", "5"))      # the sweep gives up after this many in a row
FOCUS_BACKOFF_S = float(os.getenv("ALIBI_FOCUS_BACKOFF_S", "30"))   # 30 s, 1 min, 2 min, 4 min ... (cap 1 h)


def _focus_enabled() -> bool:
    return os.getenv("ALIBI_FOCUS_SHORTCUTS", "1") != "0"


def _shortcuts(*args: str, timeout: float = 20) -> subprocess.CompletedProcess:
    """`shortcuts <args>`; tests replace this."""
    return subprocess.run(["shortcuts", *args], capture_output=True, text=True, timeout=timeout)


def focus_shortcuts(refresh: bool = False) -> dict:
    """{on, off}: whether 'Alibi Focus On' / 'Alibi Focus Off' exist (cached 10 min; `shortcuts list`)."""
    if not _focus_enabled():
        return {"on": False, "off": False, "enabled": False}
    if refresh or time.time() - _focus["checked"] > 600:
        try:
            out = _shortcuts("list", timeout=10).stdout or ""
            _focus["names"] = {ln.strip() for ln in out.splitlines() if ln.strip()}
        except Exception:
            _focus["names"] = set()
        _focus["checked"] = time.time()
    return {"on": FOCUS_ON in _focus["names"], "off": FOCUS_OFF in _focus["names"], "enabled": True}


def _focus_fail(on: bool) -> dict:
    """{n, ts}: consecutive failures of the On / Off shortcut and when the last one ran."""
    f = (state().get("mac_focus_fail") or {}).get("on" if on else "off") or {}
    return {"n": int(f.get("n") or 0), "ts": float(f.get("ts") or 0)}


def focus_problem() -> dict | None:
    """{name, n, gave_up, ts} when a Focus shortcut keeps failing (signals.status shows it), else None."""
    for on in (False, True):
        f = _focus_fail(on)
        if f["n"]:
            return {"name": FOCUS_ON if on else FOCUS_OFF, "n": f["n"], "gave_up": f["n"] >= FOCUS_MAX_FAILS,
                    "ts": f["ts"]}
    return None


def _focus_busy() -> bool:
    return any(t.is_alive() for t in _focus["threads"])


def set_mac_focus(on: bool, wait: bool = False, sweep: bool = False) -> bool:
    """Run the matching Shortcut in the background if it exists. Never raises; returns whether it was started.

    One run at a time. A failing shortcut is retried by the tick sweep (sweep=True) with exponential backoff, and the
    sweep gives up after FOCUS_MAX_FAILS in a row (signals.status says so). Session start/end still try once each."""
    try:
        if _focus_busy():
            return False
        have = focus_shortcuts()
        if not have.get("on" if on else "off"):
            return False
        if not on and not state().get("mac_focus_on"):
            return False                                  # only turn off what Alibi turned on
        f = _focus_fail(on)
        if sweep and f["n"] and (f["n"] >= FOCUS_MAX_FAILS or
                                 time.time() < f["ts"] + min(3600.0, FOCUS_BACKOFF_S * 2 ** (f["n"] - 1))):
            return False
        name, key = (FOCUS_ON, "on") if on else (FOCUS_OFF, "off")
        prev = bool(state().get("mac_focus_on"))

        def run():
            try:
                r = _shortcuts("run", name)
                ok = r.returncode == 0
            except Exception:
                ok = False
            fails = dict(state().get("mac_focus_fail") or {})
            if ok:
                fails.pop(key, None)
            else:
                fails[key] = {"n": _focus_fail(on)["n"] + 1, "ts": time.time()}
                print(f"[alibi] shortcut '{name}' failed ({fails[key]['n']} in a row)", flush=True)
            set_state(mac_focus_on=on if ok else prev, mac_focus_fail=fails,
                      mac_focus_last={"on": on, "ok": ok, "ts": time.time()})
        set_state(mac_focus_on=on)
        t = threading.Thread(target=run, daemon=True, name="alibi-focus")
        _focus["threads"] = [t]
        t.start()
        if wait:
            t.join(30)
        return True
    except Exception as e:
        print(f"[alibi] focus shortcut failed: {e!r}", flush=True)
        return False


def _focus_sweep(con) -> None:
    """A cancelled session never reaches on_verdict: turn the Focus off once nothing is live (with backoff)."""
    if state().get("mac_focus_on") and not db.active_session(con) and _focus_enabled():
        set_mac_focus(False, sweep=True)


def _check_claims(con) -> None:
    """'Going for a run' claims settle every tick, not only after a Strava sync (INT-9)."""
    try:
        from . import daemon
        daemon.check_claims(con)
    except Exception as e:
        print(f"[alibi] claim check failed: {e!r}", flush=True)


def _maybe_strava(now: float, force: bool = False) -> threading.Thread | None:
    global _strava_thread, _strava_last_try
    from . import strava
    if not strava.connected() or (_strava_thread and _strava_thread.is_alive()):
        return None
    st = strava.state()
    if st.get("needs_reconnect") and not force:
        return None
    if not force and (now < float(st.get("backoff_until") or 0) or now - _strava_last_try < STRAVA_EVERY_S):
        return None
    _strava_last_try = now
    _strava_thread = threading.Thread(target=strava_sync_now, daemon=True, name="alibi-strava")
    _strava_thread.start()
    return _strava_thread


def strava_sync_now() -> dict:
    """Sync and announce new runs. Never raises; returns {ok, added, error}."""
    from . import strava
    from .notify import notify
    try:
        added = strava.sync()
    except strava.NeedsReconnect as e:
        if not state().get("strava_reconnect_told"):
            notify("Strava stopped accepting Alibi's access, so runs aren't being checked. Open Setup → Reconnect Strava.",
                   kind="info", actions=[{"label": "Reconnect", "url": "/strava/setup"}])
            set_state(strava_reconnect_told=True)
        return {"ok": False, "added": [], "error": str(e), "needs_reconnect": True}
    except strava.RateLimited as e:
        return {"ok": False, "added": [], "error": str(e)}
    except Exception as e:
        print(f"[alibi] strava sync failed: {e!r}", flush=True)
        strava._state(last_error="Couldn't reach Strava. Alibi will try again later.")
        return {"ok": False, "added": [], "error": "Couldn't reach Strava."}
    set_state(strava_reconnect_told=False)
    for r in added:
        what = "updated" if r.get("edited") else "logged"
        notify(f"Strava: {r['name']}, {r['distance_km']:g} km — {what}.", kind="info")
    try:
        _check_claims(db.connect())
    except Exception:
        pass
    return {"ok": True, "added": added, "error": None}


# --- Apple Health: normalise what an iOS Shortcut sends --------------------------------------------------------

_NUM = re.compile(r"-?\d+(?:[.,]\d+)?")


def _num(v) -> float | None:
    """'7,5' / '7.5 hr' / 8123 / ['3000', '5123'] (summed) / '' -> float or None."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            x = float(v)
        except OverflowError:                          # a 400-digit int
            return None
        return x if math.isfinite(x) else None
    if isinstance(v, (list, tuple)):
        xs = [x for x in (_num(i) for i in v) if x is not None]
        return (sum(xs) if math.isfinite(sum(xs)) else None) if xs else None
    if isinstance(v, dict):
        return _num(v.get("value") or v.get("quantity"))
    s = str(v).strip()
    if "\n" in s:                                      # Shortcuts joins list items with newlines
        return _num(s.splitlines())
    s = s.replace(",", "") if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?\D*", s) else s.replace(",", ".")
    m = _NUM.search(s)
    x = float(m.group(0)) if m else None
    return x if x is not None and math.isfinite(x) else None


def _day(v) -> str:
    if isinstance(v, (int, float)) and v > 1e9:
        return dt.date.fromtimestamp(v).isoformat()
    s = str(v or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    for fmt in ("%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(s.split(" at ")[0].strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return dt.date.today().isoformat()


_KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


def _clean(v, depth: int = 0):
    """JSON-safe copy of an unknown key's value, small: scalars, short strings, shallow lists/dicts."""
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        return v[:200]
    if depth >= 2:
        return None
    if isinstance(v, list):
        return [_clean(x, depth + 1) for x in v[:50]]
    if isinstance(v, dict):
        return {str(k)[:40]: _clean(x, depth + 1) for k, x in list(v.items())[:30]}
    return None


def _hhmm(v) -> str | None:
    m = re.search(r"(\d{1,2})[:.](\d{2})", str(v or ""))
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m and int(m.group(1)) < 24 else None


def normalise_health(raw: dict) -> dict:
    """Shortcut / companion body -> the contract payload. Sleep may arrive as hours, minutes or seconds (a night can't
    be confused) or as {core_h, deep_h, rem_h, awake_h, bed, wake}; meditation/workout must say their unit:
    mindful_min/workout_min in minutes, or mindful_s/workout_s in seconds. Unknown keys are kept (small, JSON-safe)."""
    if not isinstance(raw, dict):
        raise ValueError("expected a JSON object")
    p = {"date": _day(raw.get("date"))}
    steps = _num(raw.get("steps"))
    if steps is not None:
        p["steps"] = int(round(steps))
    stages = raw.get("sleep") if isinstance(raw.get("sleep"), dict) else None
    sleep = _num(raw.get("sleep_h") if raw.get("sleep_h") not in (None, "") else (None if stages else raw.get("sleep")))
    if sleep is None and _num(raw.get("sleep_min")) is not None:
        sleep = _num(raw.get("sleep_min")) / 60
    if sleep is None and _num(raw.get("sleep_s")) is not None:
        sleep = _num(raw.get("sleep_s")) / 3600
    if stages:
        st = {k: round(v, 2) for k in SLEEP_STAGES if (v := _num(stages.get(k))) is not None and 0 <= v <= 24}
        for k in ("bed", "wake"):
            if _hhmm(stages.get(k)):
                st[k] = _hhmm(stages.get(k))
        if st:
            p["sleep"] = st
        if sleep is None and any(k in st for k in ("core_h", "deep_h", "rem_h")):
            sleep = sum(st.get(k, 0) for k in ("core_h", "deep_h", "rem_h"))
    if sleep is not None:
        sleep = sleep / 3600 if sleep > 24 * 60 else sleep / 60 if sleep > 24 else sleep
        p["sleep_h"] = round(sleep, 2)
    for k in ("mindful_min", "workout_min"):           # no guessing here: 60 could be 1 min (as seconds) or an
        v = _num(raw.get(k))                            # hour, so minutes come as *_min and seconds as *_s
        if v is None and _num(raw.get(k[:-4] + "_s")) is not None:
            v = _num(raw.get(k[:-4] + "_s")) / 60
        if v is not None:
            p[k] = round(v, 1)
    for k in NUMERIC:
        v = _num(raw.get(k))
        if v is not None and v >= 0:
            p[k] = round(v, 2)
    w = raw.get("workouts")
    if isinstance(w, str):
        w = [x.strip() for x in w.splitlines() if x.strip()]
    if isinstance(w, list):
        p["workouts"] = [_clean(x, 1) for x in w[:50]]
        if "workout_min" not in p:
            mins = [_num(x.get("min") or x.get("duration_min")) for x in w if isinstance(x, dict)]
            if any(m is not None for m in mins):
                p["workout_min"] = round(sum(m or 0 for m in mins), 1)
    else:
        p["workouts"] = []
    if isinstance(raw.get("moods"), list):
        p["moods"] = [_clean(x, 1) for x in raw["moods"][:50] if isinstance(x, dict)]
    if not any(k in p for k in ("steps", "sleep_h", "mindful_min", "workout_min", "sleep", "moods", *NUMERIC)) \
            and not p["workouts"]:
        raise ValueError("no Health numbers found — send at least one of steps, sleep_h, mindful_min, workout_min")
    for k, v in raw.items():                           # contract: unknown keys kept
        if isinstance(k, str) and k not in p and k not in METRICS and _KEY.match(k) and k not in ("sleep", "sleep_min", "sleep_s",
                                                                             "mindful_s", "workout_s", "source", "kind"):
            c = _clean(v)
            if c is not None and len(p) < 80:
                p[k] = c
    return p


def save_health(con, raw: dict) -> dict:
    p = normalise_health(raw)
    noon = dt.datetime.fromisoformat(p["date"]).replace(hour=12).timestamp()
    db.add_event(con, "health", "samples", p, session_id=None, ts=noon)
    now = time.time()
    st = state()
    set_state(health_last_received=now)
    if now - float(st.get("health_synced_told") or 0) > 3600:        # one "synced" moment an hour, not one per day row
        set_state(health_synced_told=now)
        from .notify import notify
        bits = [f"{METRICS[k]['label'].lower()} {METRICS[k]['fmt'](p[k])}" for k in ("steps", "sleep_h") if k in p]
        notify("Your iPhone checked in" + (f": {', '.join(bits)}." if bits else "."), kind="synced", source="health",
               date=p["date"])
    return p


def health_days(con, since: str | None = None) -> dict[str, dict]:
    """{date: payload}, latest row per day wins."""
    out = {}
    for (payload,) in con.execute("SELECT payload FROM events WHERE source='health' AND kind='samples' ORDER BY id"):
        try:
            p = json.loads(payload)
        except ValueError:
            continue
        d = p.get("date")
        if d and (since is None or d >= since):
            out[d] = p
    return out


def _metric(day: dict | None, metric: str) -> float | None:
    """A day's value for a metric as a number (sleep_h may be derived from stages); junk -> None, never a crash."""
    if not day:
        return None
    v = day.get(metric)
    if v is None and metric == "sleep_h" and isinstance(day.get("sleep"), dict):
        st = day["sleep"]
        v = sum(_num(st.get(k)) or 0 for k in ("core_h", "deep_h", "rem_h")) or None
    if isinstance(v, bool):
        return None
    return float(v) if isinstance(v, (int, float)) else _num(v)


def health_habits(cfg: dict | None = None) -> dict:
    cfg = cfg or config.habits()
    return {k: h for k, h in (cfg.get("habits") or {}).items() if isinstance(h, dict) and h.get("source") == "health"}


def health_rows(con, now: float | None = None, cfg: dict | None = None) -> list[dict]:
    """One row per Health habit for this week (Mon → today). A day without data is 'no data', never a miss."""
    now = now or time.time()
    today = dt.date.fromtimestamp(now)
    monday = today - dt.timedelta(days=today.weekday())
    all_days = health_days(con)
    out = []
    for key, h in health_habits(cfg).items():
        metric = h.get("metric", "steps")
        meta = METRICS.get(metric, {"label": metric, "unit": "", "fmt": lambda v: f"{v:g}"})
        target = float(h.get("daily_target") or 0)
        lower = bool(meta.get("lower")) if h.get("direction") not in ("above", "below") else h["direction"] == "below"
        ok = (lambda v: v <= target) if lower else (lambda v: v >= target)
        days = []
        for i in range(7):
            d = monday + dt.timedelta(days=i)
            if d > today:
                break
            v = _metric(all_days.get(d.isoformat()), metric)
            met = None if v is None else (ok(v) if target else True)
            days.append({"date": d.isoformat(), "value": v, "met": met,
                         "text": meta["fmt"](v) if v is not None else None})
        checked = [x for x in days if x["met"] is not None]
        met_n = sum(1 for x in checked if x["met"])
        streak, d = 0, today
        if (v := _metric(all_days.get(d.isoformat()), metric)) is None or not ok(v):
            d -= dt.timedelta(days=1)                   # today not done yet doesn't break the streak
        while (v := _metric(all_days.get(d.isoformat()), metric)) is not None and ok(v):
            streak += 1
            d -= dt.timedelta(days=1)
        latest = max(all_days) if all_days else None
        name = h.get("display") or h.get("label") or config.display_name(key, cfg)
        t = (meta["fmt"](target) + (" steps" if metric == "steps" else "")) if target else "—"
        cmp = "or less" if lower else "or more"
        if not all_days:
            status, text = "no_data", f"Waiting for your iPhone to send {meta['label'].lower()}."
        else:
            status = "aligned" if not checked or met_n >= -(-len(checked) * 7 // 10) else "behind"
            text = (f"{met_n} of {len(checked)} day{'s' * (len(checked) != 1)} at {t} {cmp} this week."
                    if checked else "No data for this week yet.")
        today_v = days[-1]["value"] if days else None
        out.append({"habit": key, "label": name, "source": "health", "metric": metric, "unit": meta["unit"],
                    "metric_label": meta["label"], "daily_target": target, "target_text": t,
                    "days": days, "days_met": met_n, "days_checked": len(checked),
                    "today_value": today_v, "today_met": days[-1]["met"] if days else None,
                    "today_text": meta["fmt"](today_v) if today_v is not None else None,
                    "streak_days": streak, "status": status, "lower_is_better": lower, "behind_by_days": len(checked) - met_n,
                    "latest_date": latest, "text": text})
    return out


def health_status(con) -> dict:
    days = health_days(con)
    last = state().get("health_last_received")
    latest = max(days) if days else None
    if not days:
        text = "Not set up yet. Set up a nightly Shortcut on your iPhone to send steps, sleep and workouts."
    else:
        when = {dt.date.today().isoformat(): "today",
                (dt.date.today() - dt.timedelta(days=1)).isoformat(): "yesterday"}.get(latest, latest)
        text = f"Your iPhone last sent Health data for {when}."
    return {"connected": bool(days), "days_received": len(days), "latest_date": latest, "last_received": last,
            "text": text, "action": "Set up iPhone" if not days else "iPhone setup",
            "habits": list(health_habits().keys()), "phone_sync": phone_status()}


# --- opt-in phone listener (LAN / Tailscale): POST /ingest and GET /phone only ------------------------------------

_phone = {"server": None, "thread": None}


def phone_secret(create: bool = True) -> str:
    s = store.load().get("phone_secret") or ""
    if not s and create:
        s = _rand.token_urlsafe(18)
        store.update(phone_secret=s)
    return s


def rotate_phone_secret() -> str:
    store.update(phone_secret=_rand.token_urlsafe(18))
    return phone_secret()


def _secret_ok(given: str) -> bool:
    want = phone_secret(create=False) or os.getenv("INGEST_SECRET", "")
    return bool(want) and hmac.compare_digest(str(given or "").encode(), want.encode())


def addresses() -> list[dict]:
    """Ways the phone can reach this Mac: Tailscale HTTPS (if `tailscale serve` proxies the phone port — the only
    option Safari's HTTPS-only mode accepts), home Wi-Fi IP, Bonjour name, Tailscale IP (works away from home)."""
    out = []
    try:
        web = json.loads(subprocess.run(["tailscale", "serve", "status", "--json"], capture_output=True, text=True,
                                        timeout=3).stdout or "{}").get("Web", {})
        for hostport, cfg in web.items():
            if any(str(h.get("Proxy", "")).endswith(f":{PHONE_PORT}") for h in cfg.get("Handlers", {}).values()):
                host, _, port = hostport.rpartition(":")
                out.append({"kind": "tailscale_https", "host": host, "label": "Tailscale, secure (works anywhere)",
                            "base": f"https://{host}" + ("" if port == "443" else f":{port}")})
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))                # no packet is sent; picks the LAN interface
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("127."):
            out.append({"kind": "wifi", "host": ip, "label": "Home Wi-Fi"})
    except OSError:
        pass
    try:
        name = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True, timeout=2).stdout.strip()
        if name:
            out.append({"kind": "bonjour", "host": f"{name}.local", "label": "Home Wi-Fi (by name)"})
    except Exception:
        pass
    for exe in ("tailscale", "/Applications/Tailscale.app/Contents/MacOS/Tailscale"):
        try:
            ts = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True, timeout=2).stdout.split()
            if ts:
                out.append({"kind": "tailscale", "host": ts[0], "label": "Tailscale (works away from home)"})
                break
        except Exception:
            continue
    return out


# --- phone rows (docs/SIGNALS.md): validate, normalise, store via signals.store -------------------------------------

TS_PAST_S = 7 * 86400                                    # phone timestamps are clamped to [now-7d, now+5min]


def _ts(v) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        t = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(t):                             # 'inf', 1e400, 'nan' — never let them reach the DB
        return None
    if t > 1e12:                                         # milliseconds
        t /= 1000
    return t if t > 1e9 else None


def _clamp_ts(t: float, now: float) -> float:
    return min(max(t, now - TS_PAST_S), now + 300)


def _bool(v) -> bool:
    return v is True or str(v).strip().lower() in ("1", "true", "yes", "on")


def normalise_phone(kind: str, raw: dict, ts: float | None) -> tuple[dict, float]:
    """(payload, ts) for one phone row. Location carries only at_home — coordinates never get stored."""
    p = raw if isinstance(raw, dict) else {}
    now = time.time()
    if kind == "motion":
        a = _clamp_ts(_ts(p.get("start")) or ts or now, now)
        b = _clamp_ts(_ts(p.get("end")) or ts or now, now)
        state = str(p.get("state") or "unknown").lower()
        conf = str(p.get("confidence") or "medium").lower()
        out = {"start": min(a, b), "end": max(a, b), "state": state if state in MOTION_STATES else "unknown",
               "confidence": conf if conf in ("low", "medium", "high") else "medium"}
        ts = ts or out["end"]
    elif kind == "pickup":
        t = _clamp_ts(_ts(p.get("ts")) or ts or now, now)
        out, ts = {"ts": t}, ts or t
    elif kind == "screentime":
        out = {"app": str(p.get("app") or "Picked apps")[:80],
               "minutes": min(1440.0, max(0.0, _num(p.get("minutes")) or 0.0)),
               "threshold_min": min(1440.0, max(0.5, _num(p.get("threshold_min")) or 5.0))}
        if p.get("category"):
            out["category"] = str(p["category"])[:60]
    elif kind == "shield":
        out = {"on": _bool(p.get("on")), "apps": int(min(10000.0, max(0.0, _num(p.get("apps")) or 0.0)))}
    elif kind == "focus":
        out = {"on": _bool(p.get("on")), "name": str(p.get("name") or "Alibi")[:40]}
    elif kind == "location":
        if "at_home" not in p:
            raise ValueError("location rows carry at_home only")
        out = {"at_home": _bool(p.get("at_home"))}
    elif kind == "app":
        out = {"opened": _bool(p.get("opened")), "reason": str(p.get("reason") or "")[:80]}
    else:
        if not _KEY.match(kind):
            raise ValueError(f"unknown kind {kind!r}")
        out = _clean(p) or {}
        if len(json.dumps(out)) > 4000:
            raise ValueError("payload too big")
    return out, min(ts or now, now + 300)


def normalise_heart(raw: dict) -> list[list[float]]:
    out = []
    for x in (raw or {}).get("samples") or []:
        if isinstance(x, dict):
            x = [x.get("ts"), x.get("bpm")]
        if isinstance(x, (list, tuple)) and len(x) >= 2:
            t, bpm = _ts(x[0]), _num(x[1])
            if t and bpm is not None and 25 <= bpm <= 250:
                out.append([round(t, 1), round(bpm, 1)])
    return sorted(out)[-2000:]


def store_row(con, row: dict) -> dict:
    """One {source, kind, ts?, payload} row -> stored. Returns {kind, session_id, ...}; raises ValueError if bad."""
    from . import signals
    if not isinstance(row, dict):
        raise ValueError("each row must be a JSON object")
    src, kind = str(row.get("source") or ""), str(row.get("kind") or "")
    ts = _ts(row.get("ts"))
    if src == "health" and kind == "heart":
        samples = normalise_heart(row.get("payload"))
        if not samples:
            raise ValueError("heart rows need samples: [[ts, bpm], ...]")
        groups: dict = {}
        for t, bpm in samples:                           # split by session so each part lands where it was measured
            groups.setdefault(signals.session_at(con, t), []).append([t, bpm])
        sids = [signals.store(con, "health", "heart", {"samples": g}, ts=g[0][0]) for g in groups.values()]
        set_state(heart_last_received=time.time())
        return {"kind": "heart", "samples": len(samples), "session_id": next((x for x in sids if x), None)}
    if src == "health" or (not src and not kind):
        raw = row.get("payload") if src == "health" else row
        p = save_health(con, raw)
        return {"kind": "samples", "saved": p}
    if src != "phone":
        raise ValueError("source must be phone or health")
    payload, ts = normalise_phone(kind or "event", row.get("payload") or {}, ts)
    sid = signals.store(con, "phone", kind or "event", payload, ts=ts)
    set_state(phone_last_received=time.time())
    out = {"kind": kind, "session_id": sid}
    # finished sessions this row can still speak for: a motion segment overlapping one, or a Screen Time step that
    # landed in the 5 min after it ended (signals.cap reads those too)
    a, b = (payload["start"], payload["end"]) if kind == "motion" else (ts - 300, ts)
    out["late_sids"] = _done_sessions_overlapping(con, a, b)
    return out


def _done_sessions_overlapping(con, a: float, b: float) -> list[int]:
    return [r[0] for r in con.execute("SELECT id FROM sessions WHERE status='done' AND started_at<=? AND "
                                      "ended_at>=? ORDER BY id DESC LIMIT 5", (b, a))]


def refuse_late(con, sids) -> list[dict]:
    """Phone rows that land on an already-scored session re-run fusion there (it may only lower the score)."""
    from . import verifier
    out = []
    for sid in sorted({x for x in sids if x}):
        r = verifier.refuse_late(con, sid)
        if r:
            out.append({"session_id": sid, **r})
            print(f"[alibi] late phone evidence lowered session {sid}: {r['from']:.0%} -> {r['to']:.0%} "
                  f"({r['verdict']}) — {r['reason']}", flush=True)
            try:
                from .notify import notify
                s = db.get_session(con, sid)
                notify(f"{config.display_name(s['habit'])}: your phone's report came in late and lowered it to "
                       f"{r['to']:.0%} ({r['verdict']}). {r['reason']}.", kind="info")
            except Exception:
                pass
    return out


def _late_sids(out: dict) -> list:
    return list(out.pop("late_sids", None) or [])


def ingest_body(con, body) -> dict:
    """POST /ingest body: one row, a batch {batch: [rows]} (<= 500), or a bare Health Shortcut dict."""
    if isinstance(body, dict) and isinstance(body.get("batch"), list):
        rows = body["batch"]
        if len(rows) > BATCH_MAX:
            raise OverflowError(f"Send at most {BATCH_MAX} rows per batch.")
        saved, errors, kinds, sids = 0, [], {}, []
        for i, r in enumerate(rows):
            try:
                out = store_row(con, r)
                saved += 1
                kinds[out["kind"]] = kinds.get(out["kind"], 0) + 1
                sids += _late_sids(out)
            except ValueError as e:
                errors.append({"i": i, "error": str(e)[:160]})
        res = {"ok": not errors or saved > 0, "saved": saved, "rejected": errors[:20], "kinds": kinds,
               "session": session_info(con)}
        late = refuse_late(con, sids)
        if late:
            res["rescored"] = late
        return res
    if isinstance(body, dict) and body.get("source") in ("phone",) or \
            (isinstance(body, dict) and body.get("source") == "health" and body.get("kind") == "heart"):
        out = store_row(con, body)
        late = refuse_late(con, _late_sids(out))
        return {"ok": True, **out, **({"rescored": late} if late else {})}
    raw = body.get("payload") if isinstance(body, dict) and body.get("source") == "health" else body
    p = save_health(con, raw)
    bits = [f"{METRICS[k]['label']} {METRICS[k]['fmt'](p[k])}" for k in METRICS
            if isinstance(p.get(k), (int, float)) and not isinstance(p.get(k), bool)]
    return {"ok": True, "saved": p, "message": f"Alibi got {p['date']}: " + ", ".join(bits)}


def session_info(con) -> dict:
    """What the iPhone needs to couple to a live session (shield apps, sync faster) and to mirror it (Today screen,
    Live Activity): the same derivations as /api/state so every surface agrees. Extra fields are all nullable."""
    out = _session_core(con)
    try:
        out.update(_mirror(con))
    except Exception as e:                       # the mirror is a nicety; coupling must never fail because of it
        print(f"[alibi] phone mirror failed: {e!r}", flush=True)
    out["pinch"] = pinch.from_db(con)
    out["capabilities"] = {"say": True, "end": True, "ask": False}   # what the phone may write (routes_phone.py)
    return out


def _mirror(con) -> dict:
    from . import api
    cfg = config.habits()
    s = db.active_session(con)
    sess = None
    if s:
        sj = api._session_json(con, s, live=True)
        last = (sj.get("labels") or [None])[-1]
        sess = {"id": s["id"], "habit": s["habit"], "habit_label": config.display_name(s["habit"], cfg),
                "modality": s["modality"], "started_at": s["started_at"], "ends_at": s["ends_at"],
                "declared_min": s["declared_min"], "on_break": sj.get("on_break"),
                "on_task_ratio": sj.get("on_task_so_far"), "last_label": last and last.get("label"),
                "drifting": sj.get("drifting") and {"label": sj["drifting"].get("label"),
                                                     "since_s": sj["drifting"].get("since_s")},
                "nudges": sj.get("nudges")}
    t = api._today(con, cfg["habits"])
    rv = None if s else api._recent_verdict(con)
    streak, week = None, None
    try:
        from . import report
        rj = report.build_json()
        rows = rj["rows"]
        streak = max((x.get("streak_days") or 0 for x in rows), default=0)
        week = {"week_start": rj.get("week_start"),
                "claimed_min": sum(x.get("declared_min") or 0 for x in rows),
                "seen_min": sum(x.get("verified_min") or 0 for x in rows),
                "habits": [{"habit": x["habit"], "label": x.get("label"), "claimed_min": x.get("declared_min") or 0,
                            "seen_min": x.get("verified_min") or 0, "target_min": x.get("target_min"),
                            "status": x.get("status")} for x in rows]}
    except Exception:
        pass
    nxt = None
    try:
        from . import calendar_sync
        up = calendar_sync.upcoming(time.time(), cfg)
        if up:
            nxt = {"habit": up[0].get("habit"), "starts_at": up[0].get("start") or up[0].get("starts_at")}
    except Exception:
        pass
    return {"session": sess,
            "today": {"habits_done": t.get("habits_done"), "habits_total": t.get("habits_total"),
                      "verified_min": t.get("verified_min")},
            "recent_verdict": rv and {"habit": rv["habit"], "verdict": rv["verdict"], "ratio": rv["on_task_ratio"],
                                      "ended_at": rv["ended_at"]},
            "streak_days": streak, "week": week, "plan_next": nxt}


def _session_core(con) -> dict:
    s = db.active_session(con)
    if not s:
        return {"active": False, "habit": None, "label": None, "ends_at": None, "shield": False,
                "sync_every_s": IDLE_SYNC_S}
    h = (config.habits().get("habits") or {}).get(s["habit"]) or {}
    shield = bool(h.get("phone_shield", state().get("phone_shield", True)))
    on_break = db.in_break(con, s["id"]) is not None
    return {"active": True, "habit": s["habit"], "label": config.display_name(s["habit"]), "session_id": s["id"],
            "started_at": s["started_at"], "ends_at": s["ends_at"], "shield": shield and not on_break,
            "on_break": on_break, "sync_every_s": SESSION_SYNC_S}


def phone_app():
    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.responses import HTMLResponse
    app = FastAPI(title="Alibi phone sync", docs_url=None, redoc_url=None, openapi_url=None)

    @app.post("/ingest")
    async def ingest(request: Request, x_alibi_secret: str = Header(default="")):
        if not _secret_ok(x_alibi_secret or request.query_params.get("key", "")):
            raise HTTPException(401, "Wrong or missing key. Copy the key from Alibi → iPhone setup into the Shortcut.")
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(400, "Send JSON: Request Body → JSON in the Shortcut.")
        try:
            return ingest_body(db.connect(), body)
        except OverflowError as e:
            raise HTTPException(413, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/api/phone/session")
    def phone_session(request: Request, x_alibi_secret: str = Header(default="")):
        if not _secret_ok(x_alibi_secret or request.query_params.get("key", "")):
            raise HTTPException(401, "Wrong or missing key.")
        set_state(phone_last_polled=time.time())
        return session_info(db.connect())

    @app.get("/phone", response_class=HTMLResponse)
    def phone_page():
        from . import routes_integrations as ri
        return ri.phone_page_html(on_phone=True)

    from . import routes_phone                   # F7 writes: say and end, tailnet/loopback + header only
    app.include_router(routes_phone.router)
    return app


def phone_start() -> dict:
    import uvicorn
    if _phone["server"] and _phone["thread"] and _phone["thread"].is_alive():
        return phone_status()
    phone_secret()
    server = uvicorn.Server(uvicorn.Config(phone_app(), host=PHONE_HOST, port=PHONE_PORT, log_level="warning"))
    server.install_signal_handlers = lambda: None
    t = threading.Thread(target=server.run, daemon=True, name="alibi-phone")
    t.start()
    for _ in range(50):
        if server.started or not t.is_alive():
            break
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError(f"Port {PHONE_PORT} is busy — set PHONE_PORT to another number.")
    _phone.update(server=server, thread=t)
    return phone_status()


def phone_stop() -> None:
    s, t = _phone["server"], _phone["thread"]
    if s:
        s.should_exit = True
    if t:
        t.join(5)
    _phone.update(server=None, thread=None)


def phone_running() -> bool:
    return bool(_phone["server"] and _phone["thread"] and _phone["thread"].is_alive() and _phone["server"].started)


def phone_status() -> dict:
    return {"enabled": bool(state().get("phone_sync_enabled")), "running": phone_running(),
            "port": PHONE_PORT, "host": PHONE_HOST}
