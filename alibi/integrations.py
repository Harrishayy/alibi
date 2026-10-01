"""Daemon plugin for outside evidence: Strava sync, Apple Health samples from the phone, the opt-in phone listener.

hooks.py calls start(con) once and tick(con, now) every daemon tick.

Apple Health arrives as events(source='health', kind='samples', session_id=None, ts=noon of payload.date,
payload={date, steps, sleep_h, mindful_min, workout_min, workouts}) — one per day, the latest row wins.
Health habits in habits.yaml: {source: health, metric: steps|sleep_h|mindful_min|workout_min, daily_target, display}.
"""
import datetime as dt, hmac, json, os, re, secrets as _rand, socket, subprocess, threading, time
from . import config, db, secrets as store

STRAVA_EVERY_S = int(os.getenv("STRAVA_SYNC_EVERY_S", "1800"))
PHONE_HOST = os.getenv("PHONE_HOST", "0.0.0.0")        # the phone listener is the only thing Alibi exposes to the LAN
PHONE_PORT = int(os.getenv("PHONE_PORT", "8766"))
STATE_FILE = "integrations_state.json"

METRICS = {
    "steps":       {"label": "Steps",      "unit": "steps", "fmt": lambda v: f"{int(round(v)):,}"},
    "sleep_h":     {"label": "Sleep",      "unit": "h",     "fmt": lambda v: f"{int(v)} h" + (f" {int(round((v % 1) * 60)):02d}" if round((v % 1) * 60) else "")},
    "mindful_min": {"label": "Meditation", "unit": "min",   "fmt": lambda v: f"{int(round(v))} min"},
    "workout_min": {"label": "Workouts",   "unit": "min",   "fmt": lambda v: f"{int(round(v))} min"},
}

_strava_thread: threading.Thread | None = None
_strava_last_try = 0.0


# --- small persisted state (not secret) ---------------------------------------------------------------------------

def state() -> dict:
    try:
        return json.loads((config.DATA_DIR / STATE_FILE).read_text())
    except (FileNotFoundError, ValueError):
        return {}


def set_state(**kv) -> dict:
    d = state()
    d.update(kv)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = config.DATA_DIR / f".{STATE_FILE}.tmp"
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
        return float(v)
    if isinstance(v, (list, tuple)):
        xs = [x for x in (_num(i) for i in v) if x is not None]
        return sum(xs) if xs else None
    if isinstance(v, dict):
        return _num(v.get("value") or v.get("quantity"))
    s = str(v).strip()
    if "\n" in s:                                      # Shortcuts joins list items with newlines
        return _num(s.splitlines())
    s = s.replace(",", "") if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?\D*", s) else s.replace(",", ".")
    m = _NUM.search(s)
    return float(m.group(0)) if m else None


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


def normalise_health(raw: dict) -> dict:
    """Shortcut body -> the contract payload. Sleep may arrive as hours, minutes or seconds (a night can't be confused);
    meditation/workout must say their unit: mindful_min/workout_min in minutes, or mindful_s/workout_s in seconds."""
    if not isinstance(raw, dict):
        raise ValueError("expected a JSON object")
    p = {"date": _day(raw.get("date"))}
    steps = _num(raw.get("steps"))
    if steps is not None:
        p["steps"] = int(round(steps))
    sleep = _num(raw.get("sleep_h") if raw.get("sleep_h") not in (None, "") else raw.get("sleep"))
    if sleep is None and _num(raw.get("sleep_min")) is not None:
        sleep = _num(raw.get("sleep_min")) / 60
    if sleep is None and _num(raw.get("sleep_s")) is not None:
        sleep = _num(raw.get("sleep_s")) / 3600
    if sleep is not None:
        sleep = sleep / 3600 if sleep > 24 * 60 else sleep / 60 if sleep > 24 else sleep
        p["sleep_h"] = round(sleep, 2)
    for k in ("mindful_min", "workout_min"):           # no guessing here: 60 could be 1 min (as seconds) or an
        v = _num(raw.get(k))                            # hour, so minutes come as *_min and seconds as *_s
        if v is None and _num(raw.get(k[:-4] + "_s")) is not None:
            v = _num(raw.get(k[:-4] + "_s")) / 60
        if v is not None:
            p[k] = round(v, 1)
    w = raw.get("workouts")
    if isinstance(w, str):
        w = [x.strip() for x in w.splitlines() if x.strip()]
    if isinstance(w, list):
        p["workouts"] = w[:50]
        if "workout_min" not in p:
            mins = [_num(x.get("min") or x.get("duration_min")) for x in w if isinstance(x, dict)]
            if any(m is not None for m in mins):
                p["workout_min"] = round(sum(m or 0 for m in mins), 1)
    else:
        p["workouts"] = []
    if not any(k in p for k in ("steps", "sleep_h", "mindful_min", "workout_min")) and not p["workouts"]:
        raise ValueError("no Health numbers found — send at least one of steps, sleep_h, mindful_min, workout_min")
    return p


def save_health(con, raw: dict) -> dict:
    p = normalise_health(raw)
    noon = dt.datetime.fromisoformat(p["date"]).replace(hour=12).timestamp()
    db.add_event(con, "health", "samples", p, session_id=None, ts=noon)
    set_state(health_last_received=time.time())
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
        days = []
        for i in range(7):
            d = monday + dt.timedelta(days=i)
            if d > today:
                break
            v = (all_days.get(d.isoformat()) or {}).get(metric)
            met = None if v is None else (v >= target if target else True)
            days.append({"date": d.isoformat(), "value": v, "met": met,
                         "text": meta["fmt"](v) if v is not None else None})
        checked = [x for x in days if x["met"] is not None]
        met_n = sum(1 for x in checked if x["met"])
        streak, d = 0, today
        if (all_days.get(d.isoformat()) or {}).get(metric) is None or \
                all_days[d.isoformat()][metric] < target:
            d -= dt.timedelta(days=1)                   # today not done yet doesn't break the streak
        while (v := (all_days.get(d.isoformat()) or {}).get(metric)) is not None and v >= target:
            streak += 1
            d -= dt.timedelta(days=1)
        latest = max(all_days) if all_days else None
        name = h.get("display") or h.get("label") or config.display_name(key, cfg)
        t = (meta["fmt"](target) + (" steps" if metric == "steps" else "")) if target else "—"
        if not all_days:
            status, text = "no_data", f"Waiting for your iPhone to send {meta['label'].lower()}."
        else:
            status = "aligned" if not checked or met_n >= -(-len(checked) * 7 // 10) else "behind"
            text = (f"{met_n} of {len(checked)} day{'s' * (len(checked) != 1)} at {t} or more this week."
                    if checked else "No data for this week yet.")
        today_v = days[-1]["value"] if days else None
        out.append({"habit": key, "label": name, "source": "health", "metric": metric, "unit": meta["unit"],
                    "metric_label": meta["label"], "daily_target": target, "target_text": t,
                    "days": days, "days_met": met_n, "days_checked": len(checked),
                    "today_value": today_v, "today_met": days[-1]["met"] if days else None,
                    "today_text": meta["fmt"](today_v) if today_v is not None else None,
                    "streak_days": streak, "status": status, "behind_by_days": len(checked) - met_n,
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
    """Ways the phone can reach this Mac: home Wi-Fi IP, Bonjour name, Tailscale IP (works away from home)."""
    out = []
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
        con = db.connect()
        if isinstance(body, dict) and body.get("source") == "phone":
            s = db.active_session(con)
            db.add_event(con, "phone", str(body.get("kind") or "event"), body.get("payload") or {},
                         session_id=s["id"] if s else None, ts=body.get("ts"))
            return {"ok": True}
        raw = body.get("payload") if isinstance(body, dict) and body.get("source") == "health" else body
        try:
            p = save_health(con, raw)
        except ValueError as e:
            raise HTTPException(400, str(e))
        bits = [f"{METRICS[k]['label']} {METRICS[k]['fmt'](p[k])}" for k in METRICS if k in p]
        return {"ok": True, "saved": p, "message": f"Alibi got {p['date']}: " + ", ".join(bits)}

    @app.get("/phone", response_class=HTMLResponse)
    def phone_page():
        from . import routes_integrations as ri
        return ri.phone_page_html(on_phone=True)

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
