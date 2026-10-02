"""What's left today, the agent's latest note, and the receipt for a habits save.

    plan_today(con, now, session) -> /api/state.plan_today: today's blocks from calendar_sync.plan() (the one source
                                     the Spark's context and /api/calendar/plan also use), sorted into left / done /
                                     missed / checking, with a one-line summary. On a day with blocks, work kept off
                                     the plan (a Done session outside every block, a verified run claim) is in done
                                     too, marked unplanned. None if it can't be built.
    phrase_for(con, now, plan, live) -> /api/state.phrase (pinch.phrase with its inputs gathered here; a session that
                                     ended or a habits save after the agent's brief makes the brief old news)
    record_save(before, after, via, intent, start) -> the `saved` receipt for PUT /api/habits and POST /api/habits/add,
                                     raising one `habits_saved` alert for the island (unless nothing changed or the
                                     add also starts a session)

Nothing here calls a model or the network; /api/state calls it every second per client.
"""
import datetime as dt, json, math, os, time
from . import calendar_sync, config, db, pinch
from .notify import last_alert, notify

GLYPH = {"camera": "camera", "screen": "laptop", "both": "camera", "strava": "run", "health": "heart"}
DONE_STATES = ("done", "partial", "slacked")

_errs = {"plan": 0.0, "phrase": 0.0, "save": 0.0}


def _log_once(what: str, e: Exception) -> None:
    """At most one line a minute per kind: /api/state runs every second."""
    if time.time() - _errs.get(what, 0.0) > 60:
        _errs[what] = time.time()
        print(f"[alibi] today.{what} failed: {e!r}", flush=True)


def _hm(ts: float) -> str:
    return time.strftime("%H:%M", time.localtime(ts))


def _item(b: dict, status: str, h: dict) -> dict:
    session = b.get("session_id")
    return {"key": b["key"], "habit": b["habit"], "label": b["label"], "at": b["at"], "end_at": _hm(b["end"]),
            "start": float(b["start"]), "end": float(b["end"]), "minutes": int(b["min"]), "check": b["check"],
            "glyph": "moon" if h.get("metric") == "sleep_h" else GLYPH.get(b["check"], "camera"),
            "status": status, "verdict": b["state"] if status == "done" else None,
            "ratio": b.get("ratio") if status == "done" and session else None,
            "session_id": session, "startable": b["check"] not in ("strava", "health"),
            "once": bool(b.get("once")), "moved": bool(b.get("moved")), "unplanned": False}


def plan_today(con, now: float | None = None, session: dict | None = None, cfg: dict | None = None) -> dict | None:
    """Today's plan, rebuilt on every call from habits.yaml and calendar.json, so a save shows on the next poll.
    `session` is the live session JSON (for the minutes it has left). Never raises: None means unknown."""
    try:
        return _plan_today(con, float(now or time.time()), session, cfg)
    except Exception as e:
        _log_once("plan", e)
        return None


def _plan_today(con, now: float, session: dict | None, cfg: dict | None) -> dict:
    cfg = cfg or config.habits()
    habits = cfg.get("habits") or {}
    day = dt.date.fromtimestamp(now)
    left, done, missed, checking = [], [], [], []
    planned = []
    for b in calendar_sync.plan(con, day, 1, now):
        h = habits.get(b["habit"]) or {}
        made = config.habit_created_ts(h)
        if made and b["end"] < made and not b.get("session_id"):
            continue                       # a habit added at 21:42 never shows a "missed" 11:00 block
        st = b["state"]
        if st == "live":
            left.append(_item(b, "live", h))
        elif st == "now":
            left.append(_item(b, "now", h))
        elif st == "planned":
            planned.append(b)
        elif st in DONE_STATES:
            done.append(_item(b, "done", h))
        elif st in ("missed", "skipped"):
            missed.append(_item(b, st, h))
        elif st in ("waiting", "nodata"):
            checking.append(_item(b, "checking" if st == "waiting" else "nodata", h))
    planned.sort(key=lambda b: b["start"])
    for i, b in enumerate(planned):
        left.append(_item(b, "next" if i == 0 else "later", habits.get(b["habit"]) or {}))
    if left or done or missed or checking:       # a day with a plan: work done off it still counts as kept
        done += _off_plan(con, day, habits, cfg, left + done + missed + checking)
    for xs in (left, done, missed, checking):
        xs.sort(key=lambda x: x["start"])
    nows = [x for x in left if x["status"] == "now"]
    nxt = nows[0] if nows else next((x for x in left if x["status"] == "next"), None)
    left_min = 0
    for x in left:
        if x["status"] == "live":
            left_min += _live_left_min(con, x, session, now)
        else:
            left_min += x["minutes"]
    total = len(left) + len(done) + len(missed) + len(checking)
    out = {"date": day.isoformat(), "now": now,
           "scheduled": any(isinstance(h, dict) and h.get("schedule") for h in habits.values()),
           "total": total, "kept": sum(x["verdict"] in ("done", "partial") for x in done), "left_min": left_min,
           "summary": "", "next": nxt, "left": left, "done": done, "missed": missed, "checking": checking,
           "away": None}
    out["summary"] = pinch.summary_line(out)
    return out


def _off_plan(con, day: dt.date, habits: dict, cfg: dict, items: list) -> list[dict]:
    """Promises kept today that answered no block: a finished session with a done/partial verdict ("draw for 8" at
    21:42 when drawing's block was 19:00) and a verified run claim (when no Strava block was kept). Without them the
    phrase says "Today slipped." two minutes after a verdict that said Done. Marked `unplanned`, so they never end the
    plan (no plan_done)."""
    answered = {x["session_id"] for x in items if x.get("session_id")}
    kept = {x["habit"] for x in items if x["status"] == "done" and x.get("verdict") in ("done", "partial")}
    d0 = dt.datetime.combine(day, dt.time()).timestamp()
    d1 = dt.datetime.combine(day + dt.timedelta(days=1), dt.time()).timestamp()      # a DST day isn't 86400 s
    out = []
    for s in con.execute("SELECT * FROM sessions WHERE status='done' AND verdict IN ('done','partial') "
                         "AND started_at >= ? AND started_at < ? ORDER BY started_at", (d0, d1)).fetchall():
        if s["id"] in answered:
            continue
        h = habits.get(s["habit"]) or {}
        chk = pinch.kind_of(h) if h else {"digital": "screen", "hybrid": "both"}.get(s["modality"], "camera")
        end = float(s["ended_at"] or s["ends_at"])
        out.append({"key": f"{s['habit']}@session-{s['id']}", "habit": s["habit"],
                    "label": config.display_name(s["habit"], cfg), "at": _hm(s["started_at"]), "end_at": _hm(end),
                    "start": float(s["started_at"]), "end": end, "minutes": int(s["declared_min"]), "check": chk,
                    "glyph": GLYPH.get(chk, "camera"), "status": "done", "verdict": s["verdict"],
                    "ratio": s["on_task_ratio"], "session_id": s["id"], "startable": True, "once": False,
                    "moved": False, "unplanned": True})
    # Run claims: today's settles first (one indexed range, no payload parsing; empty on most days), claims only then.
    settled = con.execute("SELECT ts, payload FROM events WHERE ts >= ? AND ts < ? AND source='alibi' "
                          "AND kind='claim_settled' ORDER BY ts, id", (d0, d1)).fetchall()
    claims = {r["id"]: r for r in con.execute(
        "SELECT id, ts, payload FROM events WHERE ts >= ? AND ts < ? AND source='user' AND kind='claim'",
        (d0 - 2 * 3600, d1))} if settled else {}
    for e in settled:
        p = _payload(e["payload"])
        c = claims.get(p.get("claim_id"))
        hk = str(_payload(c["payload"]).get("habit") or "") if c else ""
        if not hk or not p.get("verified") or hk in kept:
            continue
        kept.add(hk)
        out.append({"key": f"{hk}@claim-{c['id']}", "habit": hk, "label": config.display_name(hk, cfg),
                    "at": _hm(c["ts"]), "end_at": _hm(e["ts"]), "start": float(c["ts"]), "end": float(e["ts"]),
                    "minutes": 0, "check": "strava", "glyph": "run", "status": "done", "verdict": "done",
                    "ratio": None, "session_id": None, "startable": False, "once": False, "moved": False,
                    "unplanned": True})
    return out


def _payload(s) -> dict:
    try:
        p = json.loads(s)
    except (TypeError, ValueError):
        return {}
    return p if isinstance(p, dict) else {}


def _live_left_min(con, item: dict, session: dict | None, now: float) -> int:
    if session and session.get("id") == item["session_id"] and session.get("left_s") is not None:
        return math.ceil(max(0.0, float(session["left_s"])) / 60)
    s = db.get_session(con, item["session_id"]) if item["session_id"] else None
    return math.ceil(max(0.0, s["ends_at"] - now) / 60) if s else item["minutes"]


# --- the phrase's inputs ------------------------------------------------------------------------------------------

_brief_cache: dict = {"key": None, "row": None}
_saved_cache: dict = {"key": None, "ts": None}


def latest_brief(now: float | None = None) -> dict | None:
    """The newest brief that was shown as the agent's (timely: within 20 min of its slot, so the island dropped it).
    A late brief is stored only (e.g. a heartbeat risk note at :49 for the :00 slot) and never becomes the phrase
    unannounced. Re-read only when agent_briefs.jsonl's (mtime, size) changes. Returns a copy whose `text` is shown as
    words (cards.display: "off_track" -> "off track"); the cache keeps the raw row."""
    from . import routes_agent
    p = routes_agent._path()
    try:
        st = p.stat()
    except OSError:
        _brief_cache.update(key=None, row=None)
        return None
    key = (str(p), st.st_mtime_ns, st.st_size)
    if _brief_cache["key"] != key:
        rows = [r for r in routes_agent.briefs(20) if isinstance(r, dict)]
        row = next((r for r in reversed(rows) if (r.get("response") or {}).get("shown_as") == "agent"), None)
        _brief_cache.update(key=key, row=row)
    row = _brief_cache["row"]
    if row is None:
        return None
    from . import cards
    return dict(row, text=cards.display(row.get("text")))


def last_session_end(con) -> float | None:
    r = con.execute("SELECT max(ended_at) FROM sessions WHERE status='done'").fetchone()
    return r[0] if r and r[0] is not None else None


def last_habits_save() -> float | None:
    """When the habits last changed through the editor, the island or the API: the newest habits_saved alert's ts
    (it follows the test Clock; habits.yaml's mtime wouldn't). Re-read only when alerts.jsonl's (mtime, size) changes."""
    p = config.ALERTS_PATH
    try:
        st = p.stat()
    except OSError:
        return None
    key = (str(p), st.st_mtime_ns, st.st_size)
    if _saved_cache["key"] != key:
        a = last_alert("habits_saved")
        ts = a.get("ts") if a else None
        _saved_cache.update(key=key, ts=float(ts) if isinstance(ts, (int, float)) else None)
    return _saved_cache["ts"]


def last_fact(con) -> float | None:
    """The newest thing an agent brief can't know about: a session that ended, or a habits save. Either makes the
    brief old news, so the phrase goes back to the rules (which read the new plan)."""
    xs = [x for x in (last_session_end(con), last_habits_save()) if isinstance(x, (int, float))]
    return max(xs) if xs else None


def tomorrow_first(now: float, cfg: dict | None = None) -> dict | None:
    """Tomorrow's first planned block, startable or not (for "Tomorrow: drawing at 19:00.")."""
    day = dt.date.fromtimestamp(now) + dt.timedelta(days=1)
    bs = calendar_sync.blocks(day, 1, cfg or config.habits(), calendar_sync.load())
    return bs[0] if bs else None


def phrase_for(con, now: float, plan: dict | None, live: bool = False, cfg: dict | None = None) -> dict:
    """/api/state.phrase. Never None and never raises."""
    try:
        return pinch.phrase(plan, now, latest_brief(now), tomorrow_first(now, cfg), last_fact(con), live=live)
    except Exception as e:
        _log_once("phrase", e)
        return pinch.phrase(None, now)


# --- agent presence and clients -------------------------------------------------------------------------------------

def agent_host() -> str:
    return os.getenv("ALIBI_AGENT_HOST", "DGX Spark").strip() or "DGX Spark"


def model_name(model: str | None) -> str:
    """'nvidia/nemotron-3-super-120b-a12b' -> 'Nemotron 3 Super'. Metadata only, never a claim about where it ran."""
    m = (model or "").lower()
    if "nemotron-3-super" in m:
        return "Nemotron 3 Super"
    if "nemotron-3-nano" in m:
        return "Nemotron 3 Nano"
    return "Nemotron" if "nemotron" in m else ""


def source_line(model: str | None) -> str:
    """'DGX Spark · Nemotron 3 Super', or just the host for an unknown model."""
    name = model_name(model)
    return f"{agent_host()} · {name}" if name else agent_host()


def agent_info(now: float) -> dict:
    from . import integrations
    ts = integrations.state().get("agent_last_seen")
    ts = float(ts) if isinstance(ts, (int, float)) else None
    ago = round(max(0.0, now - ts)) if ts is not None else None
    return {"last_seen": ts, "ago_s": ago, "online": ago is not None and ago <= 90, "host": agent_host()}


def clients(now: float) -> dict:
    from . import health
    seen = health.CLIENT_SEEN
    ago = lambda k: round(max(0.0, now - seen[k]), 1) if seen.get(k) else None
    return {"island_ago_s": ago("island"), "dashboard_ago_s": ago("dashboard")}


# --- habits saves -------------------------------------------------------------------------------------------------

IGNORED = {"created_at", "template", "emoji"}
KNOWN = {"label", "display", "modality", "source", "check", "schedule", "default_min", "weekly_target_min",
         "weekly_sessions", "min_km", "daily_target", "metric", "calendar", "phone_shield", "aliases",
         "on_task_looks_like", "repos"}


def _truthy(v, default: bool) -> bool:
    """health._bool: blank -> default, 'false'/'no'/'off'/'0' -> False."""
    if v is None or v == "":
        return default
    if isinstance(v, str):
        return v.strip().lower() not in ("false", "no", "off", "0")
    return bool(v)


def _number(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default if v is None or v == "" else v


def _at(v) -> str:
    try:
        h, m = str(v).strip().split(":")[:2]
        return f"{int(h):02d}:{int(m):02d}"
    except (ValueError, AttributeError):
        return str(v)


def _sched(h: dict) -> list[tuple]:
    rows = h.get("schedule") or []
    rows = rows if isinstance(rows, list) else [rows]
    return [(tuple(pinch.day_list(r.get("days"))), _at(r.get("at")), _number(r.get("min"), h.get("default_min")))
            for r in rows if isinstance(r, dict)]


def _what(key: str, b: dict, a: dict) -> list[str]:
    """What changed on one habit, in the order the line rules read it (pinch.WHAT_ORDER)."""
    w = set()
    # by display name: the editor writes label "Drawing" for a habit that had none, which is no rename
    if config.display_name(key, {"habits": {key: b}}) != config.display_name(key, {"habits": {key: a}}):
        w.add("name")
    if pinch.kind_of(b) != pinch.kind_of(a):
        w.add("check")
    sb, sa = _sched(b), _sched(a)
    if sb != sa:
        if not sa:
            w.add("unscheduled")
        elif len(sa) == 1:
            if len(sb) == 1 and sb[0][0] == sa[0][0]:
                if sb[0][1] != sa[0][1]:
                    w.add("time")
            else:
                w.add("days")
            if len(sb) == 1 and sb[0][2] != sa[0][2]:
                w.add("length")
        else:
            w.add("schedule")
    if _number(b.get("default_min"), 25) != _number(a.get("default_min"), 25) and a.get("default_min") is not None:
        w.add("length")
    goal = ({"weekly_target_min": 0} if pinch.kind_of(a) in pinch.STARTABLE else
            {"weekly_sessions": 3, "min_km": 5, "daily_target": None, "metric": None})     # health.save_habits defaults
    if any(_number(b.get(f), d) != _number(a.get(f), d) for f, d in goal.items()):
        w.add("goal")
    if _truthy(b.get("calendar"), True) != _truthy(a.get("calendar"), True):
        w.add("calendar")
    if _truthy(b.get("phone_shield"), True) != _truthy(a.get("phone_shield"), True):
        w.add("phone_shield")
    # aliases and looks-like are generated when blank, so a blank before isn't a change
    other = [f for f in ("aliases", "on_task_looks_like") if b.get(f)] + ["repos"] + \
        sorted((set(b) | set(a)) - KNOWN - IGNORED)
    if any((b.get(f) or None) != (a.get(f) or None) for f in other):
        w.add("other")
    return [x for x in pinch.WHAT_ORDER if x in w]


def changes(before: dict | None, after: dict | None) -> list[dict]:
    """[{habit, label, what: [...]}] between two habits maps ({key: entry}). created_at, template, emoji and key
    order are ignored."""
    before, after = before or {}, after or {}
    out = []
    for k in list(after) + [k for k in before if k not in after]:
        b, a = before.get(k), after.get(k)
        if not isinstance(a, dict) and not isinstance(b, dict):
            continue
        what = ["added"] if b is None else ["removed"] if a is None else _what(k, b, a)
        if what:
            out.append({"habit": k, "label": config.display_name(k, {"habits": after if a is not None else before}),
                        "what": what})
    return out


def via_of(client: str | None) -> str:
    """X-Alibi-Client -> the alert's `via`: dashboard -> web, island -> island, anything else -> api."""
    return {"dashboard": "web", "island": "island"}.get((client or "").strip().lower(), "api")


def record_save(before_cfg: dict | None, after_cfg: dict | None, via: str = "api", intent: str | None = None,
                start: bool = False, con=None) -> dict:
    """The `saved` receipt. Raises the habits_saved alert unless nothing changed or `start` (the island's "add and
    start": the session start is the acknowledgement). A failure here never fails the save: the file is written."""
    saved = {"changes": [], "line": None, "alert_id": None, "plan_today": None}
    intent = (intent or "").strip().lower() or None
    intent = intent if intent == "undo" else None
    con = con or db.connect()
    try:
        before = (before_cfg or {}).get("habits") or {}
        after = (after_cfg or {}).get("habits") or {}
        ch = changes(before, after)
        if intent == "undo":
            for c in ch:
                c["what"] = ["restored" if w == "added" else w for w in c["what"]]
        saved["changes"] = ch
        saved["line"] = pinch.habits_line(ch, before, after, intent) if ch else None
        if ch and not start:
            _alert(con, ch, saved["line"], before, after, via)
            a = last_alert("habits_saved")
            saved["alert_id"] = a.get("id") if a else None
    except Exception as e:
        _log_once("save", e)
    saved["plan_today"] = plan_today(con, time.time(), cfg=after_cfg if after_cfg and after_cfg.get("habits") else None)
    return saved


def _alert(con, ch: list, line: str | None, before: dict, after: dict, via: str) -> None:
    """One line in alerts.jsonl the island drops down, with Start when there's one habit to start."""
    one = ch[0] if len(ch) == 1 else None
    key = one["habit"] if one else None
    h = (after.get(key) or before.get(key) or {}) if key else {}
    m = h.get("default_min")
    m = int(m) if isinstance(m, (int, float)) and not isinstance(m, bool) else None
    change = one["what"][0] if one and one["what"] else "several"
    actions = [{"label": "OK", "dismiss": True}]
    if one and m and pinch.kind_of(h) in pinch.STARTABLE and change != "removed" and key in after \
            and db.active_session(con) is None:
        actions.insert(0, {"label": f"Start {m} min", "say": f"{key} for {m} minutes"})
    extra = {"habit": key, "habit_label": one["label"] if one else "Habits"}
    if m is not None and one:
        extra["minutes"] = m
    notify(line or "Noted.", kind="habits_saved", via=via, change=change, changes=ch, actions=actions, **extra)
