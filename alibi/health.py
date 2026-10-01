"""P9 — setup checklist and habit editing, so nobody has to touch YAML or guess why the camera is dark."""
import json, os, re, shutil, subprocess, time
import yaml
from . import config, db, witness


CLIENT_SEEN: dict[str, float] = {}     # R9: clients send X-Alibi-Client (island | dashboard) when they poll


def _check(key, label, ok, detail, fix=""):
    return {"key": key, "label": label, "ok": bool(ok), "detail": detail, "fix": "" if ok else fix}


def camera_auth() -> str:
    """authorized | denied | restricted | not_determined | unknown — asks AVFoundation, never turns the camera on."""
    try:
        return subprocess.run([str(witness.WITNESS_BIN), "--camera-auth"], capture_output=True, text=True,
                              timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _strava_connected() -> bool:
    try:
        from . import strava
        if hasattr(strava, "refresh_token"):
            return bool(strava.refresh_token())
    except Exception:
        pass
    return bool(os.getenv("STRAVA_REFRESH_TOKEN") or config.secrets().get("strava_refresh_token"))


def checks() -> dict:
    """Setup rows. Every row: key, label, ok, detail, fix (plain words for anyone) + sentence, action, details
    (the technical bit, shown behind a 'Details' toggle)."""
    con = db.connect()
    out = []
    if config.CAMERA_SOURCE:
        ok = os.path.exists(config.CAMERA_SOURCE)
        out.append(_check("camera", "Camera", ok,
                          "Using a recorded test video instead of your camera" if ok else "The test video is missing",
                          "Remove the test video setting to use your real camera"))
        out[-1]["details"] = f"CAMERA_SOURCE={config.CAMERA_SOURCE}"
    else:
        a = camera_auth()
        out.append(_check("camera", "Camera", a in ("authorized", "not_determined"),
                          {"authorized": "Allowed. It only turns on while you're doing a camera habit.",
                           "not_determined": "Your Mac will ask for permission the first time you start a camera habit.",
                           "denied": "Turned off for Alibi in your Mac's settings.",
                           "restricted": "Blocked on this Mac (school or work settings?)."}.get(a, "Couldn't check the camera."),
                          "Open System Settings → Privacy & Security → Camera and turn on Alibi"))
        out[-1]["details"] = f"AVFoundation authorization: {a}"
    last = con.execute("SELECT payload, ts FROM events WHERE source='laptop' ORDER BY ts DESC LIMIT 1").fetchone()
    p = json.loads(last["payload"]) if last else {}
    fresh = last and time.time() - last["ts"] < 5 * 60
    out.append(_check("windows", "Screen", fresh and p.get("app"),
                      f"Working — right now: {p.get('app', '?')}" if fresh else
                      "Alibi hasn't been able to see which app you're using.",
                      "Open System Settings → Privacy & Security → Accessibility and turn on Alibi"
                      if fresh else "Start Alibi, then allow it under Privacy & Security → Accessibility"))
    out[-1]["details"] = (f"last window: {p.get('app', '?')} — {p.get('title', '')[:60]}" if last
                          else "no window events recorded yet")
    out.append(_check("witness", "Photo checking", config.VISION_BACKEND in ("nvidia", "apple"),
                      {"nvidia": "Photos are checked by NVIDIA's AI model online.",
                       "apple": "Photos are checked on this Mac and never leave it.",
                       "mock": "Test mode — photos aren't really checked."}[config.VISION_BACKEND],
                      "Turn off test mode to check photos on this Mac"))
    out[-1]["details"] = {"nvidia": f"VISION_BACKEND=nvidia · {config.VLM_MODEL}", "apple": "VISION_BACKEND=apple (Apple Vision)",
                          "mock": "VISION_BACKEND=mock — unset it to use Apple Vision"}[config.VISION_BACKEND]
    out.append(_check("text", "Smart replies", config.TEXT_READY,
                      "On — replies and the nightly note are written by AI." if config.TEXT_READY else
                      "Off — Alibi uses simple built-in replies. Everything still works.",
                      "Optional: add an NVIDIA key (see Details)"))
    out[-1]["details"] = (config.LLM_MODEL if config.TEXT_READY else
                          "add NVIDIA_API_KEY + LLM_MODEL to .env for smarter parsing and summaries")
    strava = _strava_connected()
    out.append(_check("strava", "Strava", strava, "Connected — your runs are checked every hour." if strava else
                      "Not connected.", "Click Connect Strava and follow the steps"))
    out[-1]["action"] = None if strava else {"label": "Connect Strava", "target": "strava"}
    out[-1]["details"] = "token from STRAVA_REFRESH_TOKEN or data/secrets.json" if strava else "no Strava token yet"
    seen = CLIENT_SEEN.get("island")
    if seen and time.time() - seen < 10:
        island = True
    else:
        island = any(subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0
                     for name in ("alibi-island", "Alibi"))
    out.append(_check("island", "Notch", island,
                      "Running — move your mouse to the notch, or press ⌥⌘A." if island else "Not running.",
                      "Click Start to open it"))
    out[-1]["action"] = None if island else {"label": "Start", "target": "island"}
    out[-1]["details"] = (f"last seen {int(time.time() - seen)} s ago" if seen else "never seen") + \
        " · ./alibi.sh up  (or double-click Alibi.app)"
    out += signal_checks(con)
    for c in out:
        c.setdefault("action", None)
        c["sentence"] = f"{c['label']}: {c['detail']}" + ("" if c["ok"] else f" {c['fix']}.")
    return {"checks": out, "ok": all(c["ok"] for c in out if c["key"] in ("camera", "windows", "witness", "island"))}


_SHORTCUTS: dict = {"at": 0.0, "names": None}


def shortcut_names(ttl: float = 120) -> set[str] | None:
    """Names from `shortcuts list` (cached), or None when the Shortcuts CLI isn't available."""
    if _SHORTCUTS["names"] is not None and time.time() - _SHORTCUTS["at"] < ttl:
        return _SHORTCUTS["names"]
    try:
        r = subprocess.run(["shortcuts", "list"], capture_output=True, text=True, timeout=5)
        names = {ln.strip() for ln in r.stdout.splitlines() if ln.strip()} if r.returncode == 0 else None
    except Exception:
        names = None
    _SHORTCUTS.update(at=time.time(), names=names)
    return names


def _ago(s: float) -> str:
    s = max(0, int(s))
    return "just now" if s < 90 else f"{s // 60} min ago" if s < 5400 else f"{s // 3600} h ago" if s < 172800 \
        else f"{s // 86400} days ago"


def signal_checks(con) -> list[dict]:
    """Round-3 rows: Full Disk Access (notifications + Focus), the Alibi Focus shortcuts, the iPhone stream."""
    from . import mac_signals
    rows = []
    st = mac_signals.status()
    fda = st["full_disk_access"]
    ok = fda == "ok"
    rows.append(_check("full_disk", "Notifications & Focus", ok,
                       "On — Alibi counts notifications (never reads them) and sees your Focus." if ok else
                       "Alibi can't count your notifications or see your Focus yet — it needs Full Disk Access."
                       if fda == mac_signals.FDA_TEXT else f"Not available on this Mac ({fda}).",
                       mac_signals.FDA_FIX if fda == mac_signals.FDA_TEXT else ""))
    rows[-1]["details"] = (f"notification database: {fda} · Focus: {st['focus']} · helper: {st['sense']} · "
                           "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles")
    names = shortcut_names()
    want = ("Alibi Focus On", "Alibi Focus Off")
    have = [n for n in want if names and n in names]
    ok = len(have) == 2
    rows.append(_check("focus_shortcuts", "Alibi Focus", ok,
                       "Ready — your Mac turns on the Alibi Focus during a session, and your iPhone follows." if ok else
                       "Couldn't check your Shortcuts." if names is None else
                       "Missing — sessions can't silence your iPhone yet.",
                       "In the Shortcuts app make two shortcuts named “Alibi Focus On” and “Alibi Focus Off” "
                       "(Set Focus → Alibi → On / Off), and turn on Share Across Devices in Focus settings"))
    rows[-1]["details"] = f"found: {', '.join(have) or 'none'} (looked for: {', '.join(want)})"
    r = con.execute("SELECT ts, source, kind FROM events WHERE source='phone' OR (source='health' AND kind='heart') "
                    "ORDER BY ts DESC LIMIT 1").fetchone()
    h = con.execute("SELECT ts FROM events WHERE source='health' ORDER BY ts DESC LIMIT 1").fetchone()
    last = r["ts"] if r else 0          # health/samples rows are stamped at noon of their day, so they don't count
    age = time.time() - last if last else None
    live = age is not None and age < 30 * 60
    rows.append(_check("phone_stream", "iPhone", live,
                       f"Streaming — last data {_ago(age)}." if live else
                       f"Quiet — last data {_ago(age)}." if age is not None else
                       "Your iPhone hasn't sent anything yet.",
                       "Open the Alibi app on your iPhone and allow Health, Motion and Screen Time"))
    rows[-1]["details"] = (f"latest phone row: {r['source']}/{r['kind']}" if r else "no phone rows") + \
        (f" · latest health row {_ago(time.time() - h['ts'])}" if h else "")
    return rows


def _num(h: dict, field: str, default, cast, key: str):
    v = h.get(field, default)
    if v is None or v == "":
        v = default
    try:
        return cast(float(v)) if cast is int else cast(v)
    except (TypeError, ValueError):
        raise ValueError(f"{key}: {field} must be a number (got {v!r})")


SLUG = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
TIME = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
DAY_WORDS = {"weekdays": ["mon", "tue", "wed", "thu", "fri"], "weekends": ["sat", "sun"],
             "daily": list(config.DAYS), "everyday": list(config.DAYS), "every day": list(config.DAYS)}
EXTRA_KEYS = ("created_at", "emoji", "template")      # passed through untouched when valid scalars


def _days(v, key: str) -> list[str]:
    if isinstance(v, str):
        v = DAY_WORDS.get(v.strip().lower()) or [x for x in re.split(r"[,\s]+", v) if x]
    if not isinstance(v, list):
        raise ValueError(f"{key}: pick at least one day")
    out = set()
    for d in v:
        d3 = str(d).strip().lower()[:3]
        if d3 not in config.DAYS:
            raise ValueError(f"{key}: {d!r} isn't a day (use mon…sun)")
        out.add(d3)
    if not out:
        raise ValueError(f"{key}: pick at least one day")
    return [d for d in config.DAYS if d in out]


def clean_schedule(v, key: str, default_min: int = 25) -> list[dict]:
    """[{days: [mon..sun], at: "HH:MM", min: 1..MAX_SESSION_MIN}] — the round-3 contract. Raises plain ValueErrors."""
    if v in (None, "", []):
        return []
    if isinstance(v, dict):
        v = [v]
    if not isinstance(v, list) or len(v) > 14:
        raise ValueError(f"{key}: schedule must be a list of {{days, at, min}}")
    out = []
    for b in v:
        if not isinstance(b, dict):
            raise ValueError(f"{key}: each planned time needs days, a time and minutes")
        at = str(b.get("at", "")).strip()
        m = TIME.match(at)
        if not m:
            raise ValueError(f"{key}: {at or 'a blank time'!r} isn't a time — use 24-hour HH:MM, like 18:30")
        mins = _num(b, "min", default_min, int, key)
        if not 1 <= mins <= config.MAX_SESSION_MIN:
            raise ValueError(f"{key}: planned length must be 1–{config.MAX_SESSION_MIN} minutes")
        out.append({"days": _days(b.get("days"), key), "at": f"{int(m.group(1)):02d}:{m.group(2)}", "min": mins})
    return out


def _bool(v, default: bool) -> bool:
    if v is None or v == "":
        return default
    if isinstance(v, str):
        return v.strip().lower() not in ("false", "no", "off", "0")
    return bool(v)


def _common(key: str, h: dict, out: dict, prev: dict | None) -> dict:
    """Fields every kind of habit may carry: label/display, schedule + calendar, created_at, emoji, template."""
    for f in ("label", "display"):
        if h.get(f):
            out[f] = str(h[f]).strip()[:24]
    sched = clean_schedule(h.get("schedule"), key, int(out.get("default_min") or 30))
    if sched:
        out["schedule"] = sched
        out["calendar"] = _bool(h.get("calendar"), True)
    elif h.get("calendar") is not None:
        out["calendar"] = _bool(h["calendar"], True)
    for f in EXTRA_KEYS:
        if isinstance(h.get(f), (str, int, float)) and str(h[f]).strip():
            out[f] = h[f] if not isinstance(h[f], str) else h[f][:40]
    repos = h.get("repos") or h.get("repo") or []
    repos = [repos] if isinstance(repos, str) else repos
    if isinstance(repos, list) and any(str(r).strip() for r in repos):
        out["repos"] = [str(r).strip()[:300] for r in repos if str(r).strip()][:10]   # git evidence (mac_signals)
    if h.get("phone_shield") is not None:
        out["phone_shield"] = _bool(h["phone_shield"], True)
    if "created_at" not in out:
        out["created_at"] = (prev or {}).get("created_at") or (
            None if prev is not None else time.strftime("%Y-%m-%d %H:%M"))
        if out["created_at"] is None:
            out.pop("created_at")
    return out


def save_habits(habits: dict) -> dict:
    """Validate and write habits back to habits.yaml, keeping verdict/nudge settings. Returns the new config.

    Kinds: camera/screen/both (modality physical/digital/hybrid, or `check: camera|screen|both`), Strava
    ({source: strava, weekly_sessions, min_km}) and Apple Health ({source: health, metric, daily_target}).
    Every kind may carry schedule [{days, at, min}] + calendar (default true when there's a schedule).
    New habits get created_at; aliases and on_task_looks_like are generated when left blank."""
    from . import templates
    if not isinstance(habits, dict):
        raise ValueError("habits must be an object of {name: {...}}")
    try:
        before = config.habits().get("habits") or {}
    except Exception:
        before = {}
    clean = {}
    for key, h in habits.items():
        if not isinstance(key, str) or not SLUG.match(key):
            raise ValueError(f"habit name {key!r}: lowercase letters, digits, underscores")
        if not isinstance(h, dict):
            raise ValueError(f"{key}: expected an object like {{modality: physical, default_min: 25}}")
        prev = before.get(key)
        if h.get("source") == "strava":
            c = {"source": "strava", "weekly_sessions": max(1, min(14, _num(h, "weekly_sessions", 3, int, key))),
                 "min_km": max(0.0, _num(h, "min_km", 5, float, key))}
            clean[key] = _common(key, h, c, prev)
            continue
        if h.get("source") == "health":
            metric = h.get("metric")
            if metric not in config.HEALTH_METRICS:
                raise ValueError(f"{key}: Apple Health habits track one of {', '.join(config.HEALTH_METRICS)}")
            dflt = config.HEALTH_METRICS[metric][2]
            cast = float if metric == "sleep_h" else int
            tgt = _num(h, "daily_target", dflt, cast, key)
            if not tgt or tgt <= 0:
                raise ValueError(f"{key}: the daily target must be more than 0")
            if metric == "sleep_h" and tgt > 16:
                raise ValueError(f"{key}: {tgt:g} hours of sleep is more than a day's worth — try 7")
            clean[key] = _common(key, h, {"source": "health", "metric": metric, "daily_target": tgt}, prev)
            continue
        if h.get("source"):
            raise ValueError(f"{key}: source must be strava or health")
        modality = h.get("modality") or config.CHECK_TO_MODALITY.get(str(h.get("check", "")))
        if modality not in ("physical", "digital", "hybrid"):
            raise ValueError(f"{key}: choose how Alibi checks it — camera, screen or both "
                             "(modality must be physical, digital or hybrid)")
        aliases = h.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [a.strip() for a in aliases.split(",")]
        elif not isinstance(aliases, list):
            aliases = [str(aliases)]
        aliases = [str(a).strip() for a in aliases if str(a).strip()]
        name = str(h.get("label") or h.get("display") or key.replace("_", " "))
        if not aliases:
            aliases = templates.auto_aliases(name, key)
        default = min(config.MAX_SESSION_MIN, max(1, _num(h, "default_min", 25, int, key)))
        c = {"modality": modality, "aliases": aliases,
             "weekly_target_min": max(0, _num(h, "weekly_target_min", 0, int, key)),
             "default_min": default,
             "on_task_looks_like": str(h.get("on_task_looks_like") or "").strip()
             or templates.auto_looks_like(name, config.MODALITY_TO_CHECK[modality])}
        clean[key] = _common(key, h, c, prev)
    if not clean:
        raise ValueError("need at least one habit")
    cfg = config.habits()
    cfg["habits"] = clean
    path = config.HABITS_PATH
    shutil.copy(path, path.with_suffix(".yaml.bak"))
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text("# Edited from the Alibi dashboard. Keys are what the agent maps your sentence to.\n"
                   + yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    os.replace(tmp, path)
    return cfg


# --- Apple Health habits: numbers per day, for the report, Setup and the island ---------------------------------

def health_days(con) -> dict[str, dict]:
    """{date: payload} from events(source='health', kind='samples'), the latest event per date winning."""
    out: dict[str, dict] = {}
    for r in con.execute("SELECT payload FROM events WHERE source='health' AND kind='samples' ORDER BY ts, id"):
        try:
            p = json.loads(r["payload"])
        except Exception:
            continue
        if isinstance(p, dict) and isinstance(p.get("date"), str):
            out[p["date"][:10]] = p
    return out


def fmt_metric(metric: str, v) -> str:
    if v is None:
        return "no data"
    return config.HEALTH_METRICS[metric][3].format(v=float(v)).replace(".0 ", " ")


def _short(metric: str, v) -> str:
    """8000 -> '8,000'; 7.0 h -> '7 h'; 10 mindful min -> '10 min'."""
    v = float(v)
    return {"steps": f"{v:,.0f}", "sleep_h": f"{v:.1f} h".replace(".0 ", " ")}.get(metric, f"{v:.0f} min")


def health_summary(con=None, now: float | None = None) -> list[dict]:
    """One row per Health habit: {habit, label, metric, target, today, yesterday, last_date, last_value, days_met,
    days_with_data, week_days, streak, avg, line}. Kept out of the minutes table and the alibi score.

    line: 'Sleep: 6.1 h average, target 7 h — 2 of 6 nights.'"""
    import datetime as dt
    con = con or db.connect()
    now = now or time.time()
    today = dt.date.fromtimestamp(now)
    monday = today - dt.timedelta(days=today.weekday())
    days = health_days(con)
    rows = []
    for key, h in (config.habits().get("habits") or {}).items():
        if h.get("source") != "health" or h.get("metric") not in config.HEALTH_METRICS:
            continue
        m, tgt = h["metric"], float(h.get("daily_target") or config.HEALTH_METRICS[h["metric"]][2])
        val = lambda d: (days.get(d.isoformat()) or {}).get(m)
        week = [monday + dt.timedelta(days=i) for i in range((today - monday).days + 1)]
        have = [(d, float(val(d))) for d in week if isinstance(val(d), (int, float))]
        met = sum(v >= tgt for _, v in have)
        streak, d = 0, today if isinstance(val(today), (int, float)) else today - dt.timedelta(days=1)
        while isinstance(val(d), (int, float)) and float(val(d)) >= tgt:
            streak += 1
            d -= dt.timedelta(days=1)
        known = sorted(k for k in days if isinstance(days[k].get(m), (int, float)))
        last = known[-1] if known else None
        avg = round(sum(v for _, v in have) / len(have), 1) if have else None
        label = config.display_name(key)
        unit_word = "nights" if m == "sleep_h" else "days"
        if not have:
            line = f"{label}: no numbers from Apple Health yet this week."
        elif len(have) == 1:
            d1, v1 = have[0]
            when = "today" if d1 == today else "yesterday" if d1 == today - dt.timedelta(days=1) else d1.strftime("%a")
            if m == "sleep_h":
                when = "last night" if d1 == today else f"the night before {d1.strftime('%a')}"
            line = (f"{label}: {fmt_metric(m, v1)} {when}, target {_short(m, tgt)} — "
                    f"{'met ✓' if v1 >= tgt else 'not met'}.")
        else:
            line = f"{label}: {_short(m, avg)} average (target {_short(m, tgt)}) — met {met} of {len(have)} {unit_word}."
        rows.append({"habit": key, "label": label, "metric": m, "target": tgt, "unit": config.HEALTH_METRICS[m][1],
                     "today": val(today), "yesterday": val(today - dt.timedelta(days=1)),
                     "last_date": last, "last_value": days[last][m] if last else None,
                     "days_met": met, "days_with_data": len(have), "week_days": len(week), "streak": streak,
                     "avg": avg, "line": line})
    return rows


def health_status(con=None) -> dict:
    """Plain words for Setup: 'Last synced last night — 8,412 steps, 7.2 h of sleep.'"""
    import datetime as dt
    con = con or db.connect()
    r = con.execute("SELECT ts, payload FROM events WHERE source='health' AND kind='samples' ORDER BY ts DESC, id DESC LIMIT 1"
                    ).fetchone()
    if not r:
        return {"connected": False, "last_sync": None, "text": "No numbers from your iPhone yet."}
    p = json.loads(r["payload"])
    days = (dt.date.today() - dt.date.fromtimestamp(r["ts"])).days
    when = {0: "today", 1: "last night"}.get(days, f"{days} days ago")
    if days == 0 and dt.datetime.fromtimestamp(r["ts"]).hour < 6:
        when = "last night"
    bits = [fmt_metric(m, p[m]) for m in config.HEALTH_METRICS if isinstance(p.get(m), (int, float))]
    return {"connected": True, "last_sync": r["ts"], "date": p.get("date"),
            "text": f"Last synced {when}" + (f" — {', '.join(bits[:3])}." if bits else ".")}
