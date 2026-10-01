"""Signals from the iPhone and the Mac (docs/SIGNALS.md is the contract): store, attach to sessions, explain, fuse.

Every signal is an `events` row (no schema change). The store decides `session_id` from the row's own `ts`, so a
batch that arrives after the session ended still lands on the right session.

  timeline(con, session)        -> [{ts, source, kind, verdict_hint, text}] — the evidence the dashboard shows
  day_summary(con, day)         -> today's screen time, pickups, motion, notifications, heart, Mac presence, git
  live(con)                     -> last value per source/kind + freshness
  status(con)                   -> which sources are flowing, what's missing, and a plain-language fix
  hourly(con, keys, hours=24)   -> rows per hour per "source.kind" (a reporting read, like live())
  egress()                      -> what leaves the Mac and where it goes, from config + a cached Spark probe
  cap(con, session, ratio, cov) -> signals may LOWER a score (with a stated reason); never raise it
  nudge_reason(con, session, since, now) -> a mid-session nudge from the phone/Mac, or None
"""
import datetime as dt, json, math, os, re, time
from . import config, db

SOURCES = ("phone", "mac")                  # plus health/heart (health/samples is daily, not a timeline row)
PHONE_KINDS = ("motion", "pickup", "screentime", "shield", "focus", "location", "app")
MAC_KINDS = ("presence", "media", "meeting", "focus", "notifications", "switches", "git")
MOVING = {"walking": "walking", "running": "running", "automotive": "driving", "cycling": "cycling"}
VIDEO = ("youtube", "netflix", "twitch", "prime video", "disney+", "tiktok", "instagram", "hbo", "hulu", "apple tv")
IDLE_S = 300                                 # contract: mac idle_s > 300 on a digital habit -> idle
MIN_CAP_S = 120                              # signals lower a score only when they add up to 2 min or more
PHONE_NUDGE_MIN = float(os.getenv("PHONE_NUDGE_MIN", "5"))
MOVING_NUDGE_S = 180


# --- store ----------------------------------------------------------------------------------------------------------

def session_at(con, ts: float) -> int | None:
    """The session whose [started_at, end] holds ts (end = ended_at, or ends_at while it's live)."""
    r = con.execute("SELECT id FROM sessions WHERE started_at<=? AND COALESCE(ended_at, ends_at)>=? "
                    "ORDER BY id DESC LIMIT 1", (ts, ts)).fetchone()
    return r[0] if r else None


def store(con, source: str, kind: str, payload: dict, ts: float | None = None) -> int | None:
    """Write one signal row; returns the session it was attached to (or None)."""
    ts = float(ts) if ts else time.time()
    sid = session_at(con, ts)
    db.add_event(con, source, kind, payload, session_id=sid, ts=ts)
    return sid


def _rows(con, t0: float, t1: float, sources=("phone", "mac", "health"), session_id: int | None = None) -> list[dict]:
    q = (f"SELECT * FROM events WHERE source IN ({','.join('?' * len(sources))}) AND kind!='samples' AND "
         "((ts BETWEEN ? AND ?)" + (" OR session_id=?" if session_id else "") + ") ORDER BY ts, id")
    args = [*sources, t0, t1] + ([session_id] if session_id else [])
    out = []
    for r in con.execute(q, args):
        try:
            out.append(dict(r, payload=_load(r["payload"])))
        except ValueError:
            continue
    return out


def _f(v, default=0.0) -> float:
    """float(v), or default for junk, NaN and ±Infinity (a bad row must never 500 the routes)."""
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError):
        return default
    return x if math.isfinite(x) else default


def _load(s: str):
    """json.loads that turns Infinity / NaN (which json.dumps writes) into None, so payloads stay JSON-safe."""
    return json.loads(s, parse_constant=lambda _c: None)


# --- derived: screen-time deltas, intervals ---------------------------------------------------------------------------

def _midnight(ts: float) -> float:
    d = dt.date.fromtimestamp(ts)
    return dt.datetime(d.year, d.month, d.day).timestamp()


def screentime_deltas(con, t0: float, t1: float) -> list[dict]:
    """Screen Time events carry cumulative minutes for the day; turn them into 'minutes used since the last event'.
    [{id, ts, app, category, minutes, delta}] for events in [t0, t1]."""
    out, last = [], {}
    for (eid, ts, payload) in con.execute("SELECT id, ts, payload FROM events WHERE source='phone' AND "
                                          "kind='screentime' AND ts BETWEEN ? AND ? ORDER BY ts, id",
                                          (_midnight(t0), t1)):
        try:
            p = _load(payload)
        except ValueError:
            continue
        app = str(p.get("app") or "Picked apps")[:60]
        mins = _f(p.get("minutes"))
        step = _f(p.get("threshold_min"), 5.0) or 5.0
        key = (dt.date.fromtimestamp(ts).isoformat(), app)
        prev = last.get(key)
        # Cumulative within a day (the key includes the date), so a smaller number is a duplicate or out-of-order
        # replay, never new use. The first row of a day may be a backfill burst: count at most one step.
        delta = min(mins, step) if prev is None else max(0.0, mins - prev)
        mins = mins if prev is None else max(mins, prev)
        last[key] = mins
        if ts >= t0 and delta > 0:
            out.append({"id": eid, "ts": ts, "app": app, "category": p.get("category"), "minutes": mins,
                        "delta": round(delta, 1)})
    return out


def _union(iv: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = []
    for a, b in sorted(x for x in iv if x[1] > x[0]):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _clip(iv, a0: float, b0: float, holes=()) -> list[tuple[float, float]]:
    out = []
    for a, b in _union([(max(a, a0), min(b, b0)) for a, b in iv]):
        segs = [(a, b)]
        for x, y in holes:
            segs = [s for (p, q) in segs for s in ((p, min(q, x)), (max(p, y), q)) if s[1] > s[0]]
        out += segs
    return out


def _len(iv) -> float:
    return sum(b - a for a, b in iv)


def _window(session) -> tuple[float, float]:
    s = dict(session)
    end = s.get("ended_at") or min(time.time(), s["ends_at"])
    return s["started_at"], min(end, s["ends_at"])


def _mm(secs: float) -> str:
    m = max(1, round(secs / 60))
    return f"{m} min"


# --- timeline ---------------------------------------------------------------------------------------------------------

def _hint(e: dict, s: dict, st: dict) -> tuple[str, str] | None:
    """(verdict_hint, text) for one row in a session, or None to leave it off the timeline."""
    src, kind, p = e["source"], e["kind"], e["payload"]
    digital = s.get("modality") in ("digital", "hybrid")
    if src == "phone":
        if kind == "screentime":
            d = st.get(e["id"])
            if not d:
                return None
            return "off_task", f"Phone: {d['app']} +{d['delta']:g} min ({d['minutes']:g} min today)"
        if kind == "pickup":
            return "off_task", "Picked up the phone"
        if kind == "motion":
            state = str(p.get("state") or "unknown")
            mins = _mm(_f(p.get("end"), e["ts"]) - _f(p.get("start"), e["ts"]))
            if state in MOVING and p.get("confidence") != "low":
                return "absent", f"Phone says {MOVING[state]} for {mins}"
            return "neutral", f"Phone {state} ({mins})"
        if kind == "location":
            return ("neutral", "Phone is at home") if p.get("at_home") else ("absent", "Phone left home")
        if kind == "shield":
            return "neutral", (f"Phone apps blocked ({int(_f(p.get('apps')))} apps)" if p.get("on")
                               else "Phone apps unblocked")
        if kind == "focus":
            return "neutral", f"Phone Focus {p.get('name') or 'Alibi'} {'on' if p.get('on') else 'off'}"
        return None                                                    # 'app' lifecycle rows are debug only
    if src == "health" and kind == "heart":
        bpm = [_f(x[1]) for x in p.get("samples") or [] if isinstance(x, (list, tuple)) and len(x) > 1]
        if not bpm:
            return None
        avg = round(sum(bpm) / len(bpm))
        rng = f", {round(min(bpm))}–{round(max(bpm))}" if len(bpm) > 1 else ""
        return "neutral", f"Heart {avg} bpm{rng} ({len(bpm)} reading{'s' * (len(bpm) != 1)})"
    if src == "mac":
        if kind == "presence":
            if p.get("locked") or p.get("display_asleep"):
                return "absent", "Mac locked" if p.get("locked") else "Mac display asleep"
            idle = _f(p.get("idle_s"))
            if idle > IDLE_S and digital:
                return "idle", f"Mac idle for {_mm(idle)}"
            return None                                                # an active Mac is the window log's job
        if kind == "media":
            if not p.get("playing"):
                return None
            what = " — ".join(x for x in (str(p.get("app") or ""), str(p.get("title") or "")) if x)
            video = any(v in what.lower() for v in VIDEO)
            return ("off_task" if video else "neutral"), f"Playing: {what or 'media'}"
        if kind == "meeting":
            if not (p.get("camera") or p.get("mic")):
                return None
            dev = " and ".join(x for x, on in (("camera", p.get("camera")), ("mic", p.get("mic"))) if on)
            return "neutral", f"In a meeting{' (' + str(p['app']) + ')' if p.get('app') else ''}: {dev} on"
        if kind == "focus":
            return "neutral", f"Mac Focus {'on' if p.get('on') else 'off'}" + (f" ({p['mode']})" if p.get("mode") else "")
        if kind == "notifications":
            n = int(_f(p.get("count")))
            if n <= 0:
                return None
            return "neutral", f"{n} notification{'s' * (n != 1)} from {p.get('app') or 'an app'}" + \
                (" (iPhone)" if p.get("phone") else "")
        if kind == "switches":
            pm = _f(p.get("per_min"))
            return ("neutral", f"Switching apps {pm:g}×/min") if pm >= 4 else None
        if kind == "git":
            c = int(_f(p.get("commits")))
            if not c:
                return None
            return "on_task", (f"{c} commit{'s' * (c != 1)} in {p.get('repo') or 'a repo'}"
                               f" (+{int(_f(p.get('insertions')))} −{int(_f(p.get('deletions')))})")
    return None


def timeline(con, session) -> list[dict]:
    """Ordered phone/Mac/heart evidence for a session: [{ts, source, kind, verdict_hint, text}]."""
    s = dict(session)
    t0, t1 = _window(s)
    st = {d["id"]: d for d in screentime_deltas(con, t0, t1)}
    out = []
    for e in _rows(con, t0 - 6 * 3600, t1, session_id=s["id"]):
        if e["kind"] == "motion":                   # a segment counts if it overlaps the session, wherever its row is
            a, b = _f(e["payload"].get("start"), e["ts"]), _f(e["payload"].get("end"), e["ts"])
            if b < t0 or a > t1:
                continue
        elif not (t0 <= e["ts"] <= t1) and e["session_id"] != s["id"]:
            continue
        h = _hint(e, s, st)
        if h:
            out.append({"ts": e["ts"], "source": e["source"], "kind": e["kind"], "verdict_hint": h[0], "text": h[1]})
    return out


# --- fusion: signals may lower a score, never raise it -------------------------------------------------------------

def off_intervals(con, session) -> dict[str, list[tuple[float, float]]]:
    """Stretches the phone/Mac say you weren't on task, clipped to the session minus breaks."""
    s = dict(session)
    t0, t1 = _window(s)
    holes = db.breaks(con, s["id"], t1)
    phone, moving, idle = [], [], []
    for d in screentime_deltas(con, t0, t1 + 300):
        if d["ts"] <= t1 + 300:                    # the event lands a moment after the minutes it reports
            phone.append((d["ts"] - d["delta"] * 60, d["ts"]))
    rows = _rows(con, t0 - 6 * 3600, t1 + 300, sources=("phone", "mac"), session_id=s["id"])
    for e in rows:
        p = e["payload"]
        if e["source"] == "phone" and e["kind"] == "motion" and p.get("state") in MOVING \
                and p.get("confidence") != "low":
            a, b = _f(p.get("start"), e["ts"]), _f(p.get("end"), e["ts"])
            if b - a >= 60:
                moving.append((a, b))
    if s.get("modality") == "digital":            # a still laptop is fine while you draw on paper; not while you code
        for e in rows:
            p = e["payload"]
            if e["source"] == "mac" and e["kind"] == "presence":
                if p.get("locked") or p.get("display_asleep"):
                    idle.append((e["ts"] - 30, e["ts"]))
                elif _f(p.get("idle_s")) > IDLE_S:
                    idle.append((e["ts"] - _f(p.get("idle_s")) + IDLE_S, e["ts"]))
    return {k: _clip(v, t0, t1, holes) for k, v in (("phone", phone), ("moving", moving), ("idle", idle))}


def cap(con, session, ratio: float, cov: float) -> tuple[float, str | None, dict]:
    """(new_ratio, reason or None, detail). new_ratio <= ratio, always. Signals cap the share of the watched time
    that can count as on task: if the phone says Instagram for 12 of 30 min, at most 18 of 30 min count."""
    s = dict(session)
    t0, t1 = _window(s)
    holes = db.breaks(con, s["id"], t1)
    elapsed = max(60.0, (t1 - t0) - _len(_clip(holes, t0, t1)))
    iv = off_intervals(con, s)
    off = _union(iv["phone"] + iv["moving"] + iv["idle"])
    off_s = _len(off)
    detail = {"off_s": round(off_s), "phone_s": round(_len(iv["phone"])), "moving_s": round(_len(iv["moving"])),
              "idle_s": round(_len(iv["idle"])), "elapsed_s": round(elapsed)}
    if off_s < MIN_CAP_S:
        return ratio, None, detail
    limit = max(0.0, 1.0 - off_s / elapsed) * cov
    if limit >= ratio - 0.005:
        return ratio, None, detail
    bits = []
    if iv["phone"]:
        apps = {}
        for d in screentime_deltas(con, t0, t1 + 300):
            apps[d["app"]] = apps.get(d["app"], 0) + d["delta"]
        top = sorted(apps.items(), key=lambda kv: -kv[1])[:2]
        names = " and ".join(a for a, _ in top) or "picked apps"
        bits.append(f"your phone says {names} for {_mm(_len(iv['phone']))}")
    if iv["moving"]:
        bits.append(("it also says" if bits else "your phone says") +
                    f" you were on the move for {_mm(_len(iv['moving']))}")
    if iv["idle"]:
        bits.append(f"the Mac sat idle or locked for {_mm(_len(iv['idle']))}")
    reason = "; ".join(bits)
    return round(limit, 4), reason[0].upper() + reason[1:], detail


def last_cap(con, session_id: int) -> dict | None:
    """The most recent fusion decision recorded by the verifier for this session (None if signals never lowered it)."""
    r = con.execute("SELECT payload FROM events WHERE session_id=? AND source='alibi' AND kind='signals_cap' "
                    "ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
    if not r:
        return None
    p = _load(r[0])
    return p if p.get("capped") else None


# --- nudges ------------------------------------------------------------------------------------------------------------

def nudge_reason(con, session, since: float, now: float | None = None) -> tuple[str, str] | None:
    """(label, sentence with {habit}) when the phone or Mac says you've drifted since the last nudge."""
    s = dict(session)
    now = now or time.time()
    t0 = max(since, s["started_at"])
    apps = {}
    for d in screentime_deltas(con, t0, now):
        if d["ts"] > t0:
            apps[d["app"]] = apps.get(d["app"], 0) + d["delta"]
    if apps and sum(apps.values()) >= PHONE_NUDGE_MIN:
        app, mins = max(apps.items(), key=lambda kv: kv[1])
        total = sum(apps.values())
        what = app if len(apps) == 1 else f"{app} and {len(apps) - 1} more"
        return "phone", f"Your phone says {what} for {round(total):g} min. Still {{habit}}?"
    moving = 0.0
    kind = None
    for e in _rows(con, t0 - 3600, now, sources=("phone",)):
        p = e["payload"]
        if e["kind"] == "motion" and p.get("state") in MOVING and p.get("confidence") != "low" and e["ts"] > since:
            a, b = max(_f(p.get("start"), e["ts"]), t0), min(_f(p.get("end"), e["ts"]), now)
            if b > a:
                moving += b - a
                kind = MOVING[p["state"]]
    if moving >= MOVING_NUDGE_S:
        return "absent", f"Your phone says you're {kind} — {_mm(moving)} now. Still {{habit}}?"
    if s.get("modality") == "digital":
        r = con.execute("SELECT ts, payload FROM events WHERE source='mac' AND kind='presence' AND ts>? "
                        "ORDER BY ts DESC LIMIT 1", (max(t0, now - 120),)).fetchone()
        if r:
            p = _load(r[1])
            if p.get("locked"):
                return "absent", "Still {habit}? Your Mac is locked."
            if _f(p.get("idle_s")) > IDLE_S:
                return "idle", f"Still {{habit}}? Your Mac has been idle for {_mm(_f(p.get('idle_s')))}."
    return None


# --- day summary, live, status ---------------------------------------------------------------------------------------

def day_summary(con, day: str | None = None) -> dict:
    day = day or dt.date.today().isoformat()
    t0 = dt.datetime.fromisoformat(day).timestamp()
    t1 = t0 + 86400
    rows = _rows(con, t0, t1)
    apps = {}
    for d in screentime_deltas(con, t0, t1):
        apps[d["app"]] = max(apps.get(d["app"], 0), d["minutes"])          # cumulative: the day's last value
    motion = {}
    seg = {}
    for e in rows:
        if e["kind"] == "motion":
            p = e["payload"]
            st = str(p.get("state") or "unknown")
            seg.setdefault(st, []).append((max(_f(p.get("start"), e["ts"]), t0), min(_f(p.get("end"), e["ts"]), t1)))
    for st, iv in seg.items():
        motion[st] = round(_len(_union(iv)) / 60)
    notif = {}
    notif_phone = 0
    for e in rows:
        if e["source"] == "mac" and e["kind"] == "notifications":
            a = str(e["payload"].get("app") or "?")
            n = int(_f(e["payload"].get("count")))
            notif[a] = notif.get(a, 0) + n
            if e["payload"].get("phone"):
                notif_phone += n
    bpm = [_f(x[1]) for e in rows if e["source"] == "health" and e["kind"] == "heart"
           for x in e["payload"].get("samples") or [] if isinstance(x, (list, tuple)) and len(x) > 1]
    idle_min = round(sum(min(_f(e["payload"].get("idle_s")), 300) for e in rows
                         if e["kind"] == "presence" and _f(e["payload"].get("idle_s")) > IDLE_S) / 60)
    git = [e["payload"] for e in rows if e["kind"] == "git"]
    sw = [_f(e["payload"].get("per_min")) for e in rows if e["kind"] == "switches"]
    meet = sum(1 for e in rows if e["kind"] == "meeting" and (e["payload"].get("camera") or e["payload"].get("mic")))
    health = {}
    try:
        from . import integrations
        health = integrations.health_days(con, since=day).get(day) or {}
    except Exception:
        pass
    return {"day": day,
            "screentime": {"total_min": round(sum(apps.values())),
                           "apps": [{"app": a, "minutes": round(m)} for a, m in sorted(apps.items(), key=lambda kv: -kv[1])]},
            "pickups": sum(1 for e in rows if e["kind"] == "pickup"),
            "motion_min": motion,
            "left_home": sum(1 for e in rows if e["kind"] == "location" and e["payload"].get("at_home") is False),
            "shield_on": sum(1 for e in rows if e["kind"] == "shield" and e["payload"].get("on")),
            "notifications": {"total": sum(notif.values()), "from_phone": notif_phone,
                              "apps": [{"app": a, "count": n} for a, n in sorted(notif.items(), key=lambda kv: -kv[1])[:8]]},
            "heart": ({"avg": round(sum(bpm) / len(bpm)), "min": round(min(bpm)), "max": round(max(bpm)), "n": len(bpm)}
                      if bpm else None),
            "mac": {"idle_min": idle_min, "meeting_samples": meet,
                    "switches_per_min": round(sum(sw) / len(sw), 1) if sw else None,
                    "commits": int(sum(_f(g.get("commits")) for g in git)),
                    "lines": int(sum(_f(g.get("insertions")) + _f(g.get("deletions")) for g in git))},
            "health": health}


# how long a source may stay quiet before it counts as stale (seconds)
FRESH_S = {"phone": 6 * 3600, "health.heart": 6 * 3600, "health.samples": 36 * 3600, "mac": 15 * 60,
           "mac.git": 7 * 86400, "mac.notifications": 6 * 3600, "mac.meeting": 86400, "mac.media": 86400,
           "mac.focus": 7 * 86400, "phone.location": 7 * 86400, "phone.shield": 7 * 86400, "phone.focus": 7 * 86400}


def _fresh_s(source: str, kind: str) -> float:
    return FRESH_S.get(f"{source}.{kind}", FRESH_S.get(source, 6 * 3600))


def live(con, now: float | None = None) -> dict:
    """Last value per source/kind, with its age and whether it's fresh."""
    now = now or time.time()
    out = {}
    for r in con.execute("SELECT source, kind, MAX(id) FROM events WHERE source IN ('phone','mac','health') "
                         "GROUP BY source, kind"):
        e = con.execute("SELECT * FROM events WHERE id=?", (r[2],)).fetchone()
        try:
            p = _load(e["payload"])
        except ValueError:
            continue
        age = max(0.0, now - e["ts"])
        if r[0] == "health" and r[1] == "samples":
            got = _f((_state().get("health_last_received")), e["ts"])
            age = max(0.0, now - got)
        h = _hint(dict(e, payload=p), {"modality": "digital"}, {}) if r[1] != "screentime" else \
            ("off_task", f"Phone: {p.get('app') or 'Picked apps'} {_f(p.get('minutes')):g} min today")
        out[f"{r[0]}.{r[1]}"] = {"source": r[0], "kind": r[1], "ts": e["ts"], "age_s": round(age),
                                 "fresh": age <= _fresh_s(r[0], r[1]), "payload": p,
                                 "text": h[1] if h else _plain(r[0], r[1], p), "session_id": e["session_id"]}
    s = db.active_session(con)
    return {"now": now, "session": dict(s) if s else None, "signals": out}


def _plain(source: str, kind: str, p: dict) -> str | None:
    """A short line for rows the timeline leaves out (nothing notable happening)."""
    if kind == "presence":
        return f"Mac in use (idle {int(_f(p.get('idle_s')))} s)"
    if kind == "samples":
        bits = [f"{int(p['steps']):,} steps" if isinstance(p.get("steps"), (int, float)) else None,
                f"{p['sleep_h']:g} h sleep" if isinstance(p.get("sleep_h"), (int, float)) else None]
        return f"Health for {p.get('date')}: " + (", ".join(b for b in bits if b) or "received")
    if kind == "media":
        return "Nothing playing"
    if kind == "meeting":
        return "No call"
    if kind == "notifications":
        return "No new notifications"
    if kind == "app":
        return "Alibi iPhone app " + ("opened" if p.get("opened") else "in the background")
    return None


def _state() -> dict:
    try:
        from . import integrations
        return integrations.state()
    except Exception:
        return {}


STATUS = [  # (key, label, fix when missing)
    ("phone.app", "Alibi on your iPhone",
     "Install the Alibi iPhone app and open it once; it needs phone sync turned on in Setup → iPhone."),
    ("health.samples", "Apple Health daily totals",
     "In the Alibi iPhone app, tap Allow Health and switch on every category (steps, sleep, heart, mindful, workouts)."),
    ("health.heart", "Live heart rate",
     "Allow Heart Rate in the Alibi iPhone app's Health permissions. Live readings need an Apple Watch."),
    ("phone.screentime", "iPhone Screen Time",
     "In the Alibi iPhone app, tap Screen Time → Allow, then pick the apps that pull you away."),
    ("phone.shield", "Phone app blocking during sessions",
     "In the Alibi iPhone app, turn on Block during sessions (uses the same Screen Time permission)."),
    ("phone.motion", "Phone motion (walking, driving)",
     "Allow Motion & Fitness for Alibi on the iPhone (Settings → Privacy & Security → Motion & Fitness)."),
    ("phone.pickup", "Phone pickups",
     "Comes with Motion & Fitness. Allow it for Alibi on the iPhone."),
    ("phone.location", "Home geofence",
     "In the Alibi iPhone app, tap Set home here and allow Location 'Always'. Only 'home / not home' is sent."),
    ("phone.focus", "Alibi Focus on the iPhone",
     "Create a Focus named 'Alibi' on the iPhone, add Alibi's Focus filter, and turn on Share Across Devices."),
    ("mac.presence", "Mac idle / lock", "Start Alibi's Mac sensor (bin/alibi-sense); it runs with the daemon."),
    ("mac.notifications", "Notifications (Mac + mirrored iPhone)",
     "Give Full Disk Access to the app running Alibi (System Settings → Privacy & Security → Full Disk Access)."),
    ("mac.meeting", "Meetings (camera / mic in use)", "Start Alibi's Mac sensor (bin/alibi-sense)."),
    ("mac.media", "What's playing", "Start Alibi's Mac sensor (bin/alibi-sense)."),
    ("mac.focus", "Mac Focus", "Start Alibi's Mac sensor (bin/alibi-sense)."),
    ("mac.switches", "App-switch rate", "Comes from the window log; it fills in once a session runs."),
    ("mac.git", "Git commits", "Add a repos: list to a coding habit in habits.yaml (e.g. repos: [~/Documents/c++]) so commits count as work."),
]


def _no_watch() -> bool:
    """User said they have no Apple Watch (integrations state apple_watch=false, or ALIBI_APPLE_WATCH=0)."""
    import os
    if os.getenv("ALIBI_APPLE_WATCH") == "0":
        return True
    try:
        from . import integrations
        return integrations.state().get("apple_watch") is False
    except Exception:
        return False


def status(con, now: float | None = None) -> dict:
    """Which sources are flowing, when they were last seen, what's missing, and how to fix it — in plain words."""
    now = now or time.time()
    lv = live(con, now)["signals"]
    mac_st, fda_fix = {}, None
    try:
        from . import mac_signals
        fn = getattr(mac_signals, "status", None)
        mac_st = (fn() if fn else {}) or {}
        fda_fix = getattr(mac_signals, "FDA_FIX", None)
    except Exception:
        mac_st = {}
    try:
        from . import integrations
        ph = integrations.phone_status()
        focus = integrations.focus_shortcuts()
        fprob = integrations.focus_problem()
    except Exception:
        ph, focus, fprob = {"enabled": False, "running": False}, {"on": False, "off": False}, None
    out = []
    for key, label, fix in STATUS:
        src, kind = key.split(".")
        x = lv.get(key)
        ms = str(mac_st.get(kind) or "") if src == "mac" and isinstance(mac_st, dict) else ""
        sense = str(mac_st.get("sense") or "") if isinstance(mac_st, dict) else ""
        if key == "health.heart" and x is None and _no_watch():
            out.append({"key": key, "source": src, "kind": kind, "label": label, "state": "not_applicable",
                        "flowing": False, "last_seen": None, "age_s": None,
                        "text": "No Apple Watch, so live heart rate isn't used.", "fix": None})
            continue
        if x is None and key == "phone.app":                   # any phone row proves the app is talking to us
            x = max((v for k, v in lv.items() if k.startswith(("phone.", "health."))), key=lambda v: v["ts"], default=None)
        if "full disk access" in ms.lower() and not (x and x["fresh"]):
            state, text = "needs_permission", "Needs Full Disk Access. " + (fda_fix or fix)
            fix = fda_fix or fix
        elif src == "mac" and sense.startswith("missing") and kind in ("presence", "media", "meeting") and x is None:
            state, text = "missing", f"The Mac sensor isn't built ({sense})."
        elif x is None and kind in ("meeting", "media", "switches") and lv.get("mac.presence", {}).get("fresh"):
            state, text = "waiting", {"meeting": "Nothing yet — shows up when another app uses the camera or mic.",
                                      "media": "Nothing yet — shows up when music or video plays.",
                                      "switches": "Nothing yet — fills in once a session runs."}[kind]
            fix = None
        elif key == "mac.git" and not (x and x["fresh"]) and _git_repos(con, now):
            # Repos are set up and simply quiet: that's waiting, not a broken source.
            hrs = round(x["age_s"] / 3600) if x else 24
            state, text, fix = "waiting", f"No commits in the last {hrs} h.", None
        elif x is None:
            state, text = "missing", fix
        elif x["fresh"]:
            state, text = "ok", f"Last seen {_ago(x['age_s'])}."
        else:
            state, text = "stale", f"Nothing since {_ago(x['age_s'])}. " + fix
        out.append({"key": key, "source": src, "kind": kind, "label": label, "state": state,
                    "flowing": state == "ok", "last_seen": x["ts"] if x else None,
                    "age_s": x["age_s"] if x else None, "text": text, "fix": None if state == "ok" else fix})
    if not ph.get("running"):
        out.insert(0, {"key": "phone.listener", "source": "phone", "kind": "listener", "label": "Phone sync on this Mac",
                       "state": "missing", "flowing": False, "last_seen": None, "age_s": None,
                       "text": "Phone sync is off, so the iPhone has nowhere to send.",
                       "fix": "Turn on phone sync in Alibi → Setup → iPhone."})
    have = focus.get("on") and focus.get("off")
    row = {"key": "mac.focus_shortcuts", "source": "mac", "kind": "focus_shortcuts",
           "label": "Turn on the Alibi Focus when a session starts", "state": "ok" if have else "missing",
           "flowing": bool(have), "last_seen": None, "age_s": None,
           "text": "Alibi turns your Alibi Focus on and off with each session." if have else
           "Make two Shortcuts on this Mac: 'Alibi Focus On' (Set Focus → Alibi → On) and 'Alibi Focus Off'.",
           "fix": None if have else "Shortcuts app → New Shortcut → Set Focus. Name them exactly "
                                    "'Alibi Focus On' and 'Alibi Focus Off'."}
    if have and fprob:
        row.update(state="stale", problem="failed", flowing=False, last_seen=fprob["ts"], age_s=round(max(0.0, now - fprob["ts"])),
                   text=f"{fprob['name']} shortcut failed ({fprob['n']} times in a row)" +
                        (", so Alibi stopped retrying." if fprob["gave_up"] else "; Alibi will retry."),
                   fix=f"Open Shortcuts and run '{fprob['name']}' by hand to see the error; check it sets the "
                       "Focus named Alibi.")
    out.append(row)
    flowing = [x["key"] for x in out if x["flowing"]]
    missing = [x for x in out if not x["flowing"] and x["state"] not in ("waiting", "not_applicable")]
    return {"now": now, "sources": out, "flowing": flowing, "missing": [x["key"] for x in missing],
            "text": (f"{len(flowing)} of {len([x for x in out if x['state'] != 'not_applicable'])} signals flowing." +
                     (f" Next: {missing[0]['label']} — {missing[0]['fix']}" if missing else ""))}


def _git_repos(con, now: float) -> int:
    try:
        from . import mac_signals
        return len(mac_signals.repos(con, now))
    except Exception:
        return 0


# --- hourly counts (a reporting read, like live()) --------------------------------------------------------------------

def hourly(con, keys, hours: int = 24, now: float | None = None) -> dict[str, list[int]]:
    """Rows per hour for each "source.kind" key over the last `hours` whole hours (oldest first, the current hour
    last). A reporting read for the Signals page, same precedent as live(); the verifier never sees it."""
    now = now or time.time()
    hours = max(1, min(int(hours), 168))
    end = math.floor(now / 3600) * 3600 + 3600
    t0 = end - hours * 3600
    out = {}
    for key in keys:
        src, _, kind = str(key).partition(".")
        n = [0] * hours
        for (ts,) in con.execute("SELECT ts FROM events WHERE source=? AND kind=? AND ts>=? AND ts<?",
                                 (src, kind, t0, end)):
            i = int((_f(ts, t0) - t0) // 3600)
            if 0 <= i < hours:
                n[i] += 1
        out[key] = n
    return out


# --- egress: what leaves the Mac, derived from config at call time (AGENTS.md rule 5) --------------------------------

PROBE_TTL_S = 60
_probe_cache: dict[str, tuple[float, bool]] = {}


def _http_probe(base: str) -> bool:
    """Is the server there? Any HTTP answer counts (a 401 still means it's up); we never send a token to ask."""
    import urllib.request, urllib.error
    try:
        urllib.request.urlopen(base.rstrip("/") + "/models", timeout=2).close()
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


PROBE = _http_probe                     # tests swap this out; the real one never takes more than ~2 s


def probe(base: str, now: float | None = None) -> bool:
    now = now or time.time()
    hit = _probe_cache.get(base)
    if hit and now - hit[0] < PROBE_TTL_S:
        return hit[1]
    up = bool(PROBE(base))
    _probe_cache[base] = (now, up)
    return up


def _host(url: str) -> str:
    from urllib.parse import urlparse
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _where(url: str) -> str:
    """mac (loopback) | tailnet:spark (any other self-hosted server) | nvidia_build."""
    h = _host(url)
    if h in ("127.0.0.1", "localhost", "::1") or h.startswith("127."):
        return "mac"
    return "tailnet:spark" if config._local_llm(url) else "nvidia_build"


def egress(now: float | None = None) -> dict:
    """What leaves this Mac and where it goes, from the config right now plus a cached reachability probe.
    Rows are {what, where, active, why}; only host names are shown, never URLs, keys or values."""
    now = now or time.time()
    rows = []

    def remote(url: str) -> bool:
        return probe(url, now) if _where(url) != "nvidia_build" else True

    vb = config.VISION_BACKEND
    if vb != "nvidia":
        rows.append({"what": "Camera frames", "where": "mac", "active": True, "host": None,
                     "why": "Frames never leave the Mac. " +
                            ("Apple Vision checks them on this Mac." if vb == "apple" else "Test mode: nothing is checked.")})
    else:
        w = _where(config.VLM_BASE_URL)
        up = remote(config.VLM_BASE_URL) and bool(config.VLM_MODEL)
        why = {"mac": "Frames never leave the Mac. A model server on this Mac checks them.",
               "tailnet:spark": "Frames go to your Spark over Tailscale to be checked.",
               "nvidia_build": "Frames go to NVIDIA Build to be checked."}[w]
        if not up and w != "mac":
            why += " It isn't answering, so Apple Vision on this Mac checks them instead."
        rows.append({"what": "Camera frames", "where": w, "active": up, "host": _host(config.VLM_BASE_URL) or None,
                     "why": why})

    if config.TEXT_READY:
        w = _where(config.LLM_BASE_URL)
        up = remote(config.LLM_BASE_URL)
        why = {"mac": "Habit names and minutes go to a model server on this Mac.",
               "tailnet:spark": "Habit names and minutes go to your Spark over Tailscale.",
               "nvidia_build": "Habit names and minutes go to NVIDIA Build."}[w]
        if not up:
            why += " It isn't answering, so the rules on this Mac write the summary instead."
        rows.append({"what": "Habit names and minutes", "where": w, "active": up,
                     "host": _host(config.LLM_BASE_URL) or None, "why": why})
    else:
        rows.append({"what": "Habit names and minutes", "where": "mac", "active": True, "host": None,
                     "why": "No model is set up, so the rules on this Mac write every summary."})

    ask = os.getenv("NEMOCLAW_URL", "")
    if ask:
        up = remote(ask)
        rows.append({"what": "Ask questions", "where": _where(ask), "active": up, "host": _host(ask) or None,
                     "why": "Your questions go to NemoClaw on your Spark over Tailscale." if up else
                            "NemoClaw isn't answering, so Ask is off."})
        rows.append({"what": "Search questions", "where": "search_provider", "active": up, "host": None,
                     "why": "Search questions go to the search provider."})

    rows.append({"what": "Window titles, app names, coordinates, notification text", "where": "mac", "active": True,
                 "host": None, "why": "Never sent. They are read on this Mac and stay here."})

    summ = next(r for r in rows if r["what"] == "Habit names and minutes")
    where = summ["where"] if summ["active"] else "mac"
    text = {"mac": "Summaries stay on this Mac.", "tailnet:spark": "Summaries go to your Spark over Tailscale.",
            "nvidia_build": "Summaries go to NVIDIA Build."}[where]
    leaves = any(r["active"] and r["where"] in ("nvidia_build", "search_provider") for r in rows)
    return {"now": now, "rows": rows,
            "summary": {"where": where, "active": summ["active"] and where != "mac", "text": text,
                        "leaves_tailnet": leaves}}


def _ago(s: float) -> str:
    s = int(s)
    if s < 90:
        return "just now"
    if s < 5400:
        return f"{round(s / 60)} min ago"
    if s < 2 * 86400:
        return f"{round(s / 3600)} h ago"
    return f"{round(s / 86400)} days ago"


def session_summary(con, session) -> dict:
    s = dict(session)
    tl = timeline(con, s)
    iv = off_intervals(con, s)
    hints = {}
    for x in tl:
        hints[x["verdict_hint"]] = hints.get(x["verdict_hint"], 0) + 1
    return {"session": s, "timeline": tl, "hints": hints,
            "off_s": {k: round(_len(v)) for k, v in iv.items()}, "cap": last_cap(con, s["id"])}
