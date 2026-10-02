"""Calendar + plan endpoints (mounted by api.py through hooks.routers()).

GET  /api/calendar/status                 Setup row: {available, permission, connected, message, action{label,post}, ...}
POST /api/calendar/connect                ask macOS for access (shows the system prompt once), make "Alibi", sync
POST /api/calendar/disconnect {remove_future?}   stop syncing (optionally delete future planned events)
POST /api/calendar/sync                   sync the next 14 days now
POST /api/calendar/settings {log_unplanned?}     also log sessions that weren't planned
POST /api/calendar/open-settings          open System Settings › Privacy & Security › Calendars
GET  /api/calendar/plan?days=1&date=YYYY-MM-DD    planned blocks with state (Today strip / island next-up)
POST /api/calendar/plan/start {key}       start the block's session now (same as saying "<habit> for <min> minutes")
POST /api/calendar/plan/snooze {key, min=10}     ask again in N minutes
POST /api/calendar/plan/skip {key}        skip it today (the calendar event says "skipped")
POST /api/calendar/plan/unskip {key}
POST /api/calendar/plan/move {key, at:"HH:MM"}   move this one occurrence
GET  /api/calendar/away                   days off from today on: {days: [{date, label}]}
PUT  /api/calendar/away {days: [...]}     replace them -> {days, cleared_blocks}; 400 {detail} with one sentence
GET  /api/calendar/days?days=3            the Plan page: today and the next days, each block with what can still change
POST /api/calendar/plan/edit {op, ...}    one change (move|skip|unskip|add|remove|dayoff|dayon) -> {ok, reply, days...}

The Plan page is web/plan.html; the phone gets the same view and edits on :8766 (routes_phone, header key).
"""
import datetime as dt, subprocess, sys, time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from . import calendar_sync as cal, db
from .notify import notify

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/status")
def status():
    return cal.status()


@router.post("/connect")
def connect():
    res = cal.connect()
    return {**res, "status": cal.status()}


class Disconnect(BaseModel):
    remove_future: bool = False


@router.post("/disconnect")
def disconnect(body: Disconnect | None = None):
    res = cal.disconnect(remove_future=bool(body and body.remove_future))
    return {**res, "status": cal.status()}


@router.post("/sync")
def sync():
    res = cal.sync(force=True)
    return {**res, "status": cal.status()}


class Settings(BaseModel):
    log_unplanned: bool | None = None


@router.post("/settings")
def settings(body: Settings):
    if body.log_unplanned is not None:
        cal.update(lambda st: st.update(log_unplanned=body.log_unplanned))
    return cal.status()


@router.post("/open-settings")
def open_settings():
    if sys.platform != "darwin":
        raise HTTPException(400, "Only on a Mac.")
    subprocess.Popen(["open", cal.SETTINGS_URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True}


TEXT = {"planned": "Planned", "now": "Now", "live": "In progress", "done": "Done", "partial": "Partly done",
        "slacked": "Didn't count", "missed": "Didn't happen", "skipped": "Skipped", "waiting": "Checking", "nodata": "No data"}


@router.get("/plan")
def plan(days: int = 1, date: str | None = None):
    days = max(1, min(int(days), 14))
    try:
        day0 = dt.date.fromisoformat(date) if date else None
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")
    now = time.time()
    blocks = cal.plan(db.connect(), day0, days, now)
    for b in blocks:
        b["state_text"] = TEXT.get(b["state"], b["state"])
        b["starts_in_s"] = round(b["start"] - now)
    nxt = next((b for b in blocks if b["state"] in ("now", "planned")), None)
    live = next((b for b in blocks if b["state"] == "live"), None)
    return {"now": now, "blocks": blocks, "next": nxt, "live": live,
            "calendar": {"connected": cal.load().get("enabled", False), "name": cal.CAL_TITLE}}


class Key(BaseModel):
    key: str


class Snooze(BaseModel):
    key: str
    min: int = 10


class Move(BaseModel):
    key: str
    at: str


def _block(key: str) -> dict:
    b = cal._find(key)
    if not b:
        raise HTTPException(404, "That planned session isn't on the schedule any more.")
    return b


@router.post("/plan/start")
def start(body: Key):
    from . import cli
    b = _block(body.key)
    reply = cli.say(db.connect(), f"{b['habit']} for {b['min']} minutes")
    return {"reply": reply, "block": b}


@router.post("/plan/snooze")
def snooze(body: Snooze):
    _block(body.key)
    b = cal.snooze(body.key, body.min)
    return {"ok": True, "block": b, "reply": f"OK — I'll ask again at {time.strftime('%H:%M', time.localtime(b['snoozed_until']))}."}


@router.post("/plan/skip")
def skip(body: Key):
    _block(body.key)
    b = cal.skip(body.key)
    return {"ok": True, "block": b, "reply": f"Skipped {b['label']} for today."}


@router.post("/plan/unskip")
def unskip(body: Key):
    _block(body.key)
    cal.unskip(body.key)
    return {"ok": True}


@router.post("/plan/move")
def move(body: Move):
    _block(body.key)
    try:
        b = cal.move(body.key, body.at)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "block": b, "reply": f"Moved {b['label']} to {b['at']}."}


# --- days off -------------------------------------------------------------------------------------------------------

@router.get("/away")
def get_away():
    today = dt.date.fromtimestamp(time.time()).isoformat()
    return {"days": [d for d in cal.load_away() if d["date"] >= today]}


@router.put("/away")
def put_away(body: dict):
    now = time.time()
    today = dt.date.fromtimestamp(now)
    try:
        days = cal.clean_away(body.get("days"), today)
    except ValueError as e:
        raise HTTPException(400, str(e))
    old = {d["date"]: d["label"] for d in cal.load_away() if d["date"] >= today.isoformat()}
    added = [d for d in days if d["date"] not in old]
    span = max([cal.HORIZON_DAYS] + [(dt.date.fromisoformat(d["date"]) - today).days + 1 for d in added])
    con = db.connect()
    before = {b["key"] for b in cal.plan(con, today, span, now) if b["state"] == "skipped"}
    stored = cal.set_away(days, today)
    cleared = [b for b in cal.plan(con, today, span, now) if b["state"] == "skipped" and b["key"] not in before]
    if cal.away_on():                              # ALIBI_AWAY=0: stored, and nothing else changes
        if added:
            try:
                notify(_away_line(added, cleared, today), kind="info", actions=[{"label": "OK", "dismiss": True}])
            except Exception as e:
                print(f"[alibi] day-off line skipped: {e!r}", flush=True)
        if set(old) != {d["date"] for d in days} and cal.load().get("enabled"):
            cal._bg(cal.sync, True)                # the "Alibi" calendar follows now, not at the next 6-hour sync
    horizon = (today + dt.timedelta(days=cal.HORIZON_DAYS)).isoformat()
    return {"days": [d for d in stored if d["date"] >= today.isoformat()],
            "cleared_blocks": sum(b["date"] < horizon for b in cleared)}


def _day_name(day: dt.date, today: dt.date) -> str:
    n = (day - today).days
    return "Today" if n == 0 else "Tomorrow" if n == 1 else day.strftime("%A") if n < 7 else f"{day.day} {day:%B}"


def _away_line(added: list[dict], cleared: list[dict], today: dt.date) -> str:
    """'Monday's a day off. I've cleared its 4 blocks.' / '3 days off added. I've cleared 9 blocks.'"""
    dates = {d["date"] for d in added}
    n = sum(b["date"] in dates for b in cleared)
    if len(added) == 1:
        name = _day_name(dt.date.fromisoformat(added[0]["date"]), today)
        head = f"{name} is a day off." if name[0].isdigit() else f"{name}'s a day off."
        tail = ("Nothing was planned." if not n else "I've cleared its block." if n == 1
                else f"I've cleared its {n} blocks.")
    else:
        head = f"{len(added)} days off added."
        tail = "Nothing was planned." if not n else f"I've cleared {n} block{'s' * (n != 1)}."
    return f"{head} {tail}"


# --- the next few days: one view, one edit, for the Plan page (dashboard) and the phone (routes_phone mirrors both) ---

PLAN_DAYS = 3
ADD_DAYS = 14                                    # one-off blocks go on today .. the next two weeks
WHY_NOT = {"move": "That one has already started or happened.", "skip": "That one has already started or happened.",
           "unskip": "That one isn't skipped.", "remove": "That one has already happened."}


def _can(b: dict, now: float) -> list[str]:
    """What the Plan page may still do to a block. Days off are changed by the day, never block by block."""
    if b.get("away_label"):
        return []
    extra = ["remove"] if b.get("once") else []
    if b["state"] in ("planned", "now") and b["end"] > now:
        return ["move", "skip"] + extra
    if b["state"] == "skipped" and b["end"] > now:
        return ["unskip"] + extra
    return []


def days_view(days: int = PLAN_DAYS, now: float | None = None) -> dict:
    """Today and the next days: each day's blocks with state and allowed edits, its day off, the habits you can add."""
    from . import config, digest
    days = max(1, min(int(days), 7))
    now = now or time.time()
    today = dt.date.fromtimestamp(now)
    cfg = config.habits()
    try:                                         # a one-off block from an accepted night review says so
        accepted = {r.get("accepted_key") for r in digest.rows(200) if r.get("accepted_at")}
    except Exception:
        accepted = set()
    off = {d["date"]: d["label"] for d in cal.days_off(today, days)}
    by_day: dict = {}
    for b in cal.plan(db.connect(), today, days, now):
        by_day.setdefault(b["date"], []).append(b)
    out = []
    for i in range(days):
        d = today + dt.timedelta(days=i)
        rows = [{"key": b["key"], "habit": b["habit"], "label": b["label"], "at": b["at"], "min": b["min"],
                 "planned_at": b["planned_at"], "moved": b["moved"], "once": bool(b.get("once")), "check": b["check"],
                 "state": b["state"], "state_text": TEXT.get(b["state"], b["state"]), "detail": b.get("detail"),
                 "from": "review" if b["key"] in accepted else "you" if b.get("once") else "schedule",
                 "can": _can(b, now)} for b in by_day.get(d.isoformat(), [])]
        out.append({"date": d.isoformat(), "name": _day_name(d, today), "short": f"{d:%a} {d.day} {d:%b}",
                    "off": off.get(d.isoformat()),
                    "planned_min": sum(r["min"] for r in rows if r["state"] != "skipped"), "blocks": rows})
    habits = [{"key": k, "label": config.display_name(k, cfg), "min": int(h.get("default_min") or 25),
               "check": cal.kind_of(h)} for k, h in (cfg.get("habits") or {}).items() if isinstance(h, dict)]
    return {"now": now, "days": out, "habits": habits,
            "calendar": {"connected": bool(cal.load().get("enabled")), "name": cal.CAL_TITLE}}


def _when(date: str, today: dt.date) -> str:
    name = _day_name(dt.date.fromisoformat(date), today)
    return name.lower() if name in ("Today", "Tomorrow") else f"on {name}"


def edit(body: dict, now: float | None = None, source: str = "web") -> dict:
    """One change to the next days -> {ok, reply, ...days_view}. Refusals are HTTPException(400/404/409), one sentence.
    Every change goes through calendar_sync (moved/skipped/once/away), so Apple Calendar and the agent's /context follow."""
    from . import config
    now = now or time.time()
    today = dt.date.fromtimestamp(now)
    op = body.get("op")
    if op in ("move", "skip", "unskip", "remove"):
        key = str(body.get("key") or "")
        try:
            day = dt.date.fromisoformat(key.split("@", 1)[1][:10])
        except (IndexError, ValueError):
            raise HTTPException(404, "That block isn't on the plan any more.")
        b = next((x for x in cal.plan(db.connect(), day, 1, now) if x["key"] == key), None) if day >= today else None
        if not b:
            raise HTTPException(404, "That block isn't on the plan any more.")
        if op not in _can(b, now):
            if op == "remove" and not b.get("once"):
                raise HTTPException(409, "That one is on your weekly schedule. Skip it, or change it in Habits.")
            raise HTTPException(409, "That day is off. Turn it back on first." if b.get("away_label") else WHY_NOT[op])
        when = _when(b["date"], today)
        if op == "move":
            hm = cal._hm(body.get("at"))
            if not hm:
                raise HTTPException(400, "Use a time like 19:30.")
            if dt.datetime.combine(day, dt.time(*hm)).timestamp() < now - 60:
                raise HTTPException(400, "That time has passed. Pick a later one.")
            nb = cal.move(key, f"{hm[0]:02d}:{hm[1]:02d}")
            reply = f"Moved {b['label']} to {nb['at']} {when}."
        elif op == "skip":
            cal.skip(key)
            reply = f"Skipped {b['label']} {when}."
        elif op == "unskip":
            cal.unskip(key)
            reply = f"{b['label']} is back on {when} at {b['at']}."
        else:
            cal.remove_once(key)
            reply = f"Removed {b['label']} {when}."
    elif op == "add":
        cfg = config.habits()
        habit = str(body.get("habit") or "")
        h = (cfg.get("habits") or {}).get(habit)
        if not isinstance(h, dict):
            raise HTTPException(404, "Pick one of your habits.")
        try:
            day = dt.date.fromisoformat(str(body.get("date") or "")[:10])
        except ValueError:
            raise HTTPException(400, "Pick a day.")
        if not today <= day < today + dt.timedelta(days=ADD_DAYS):
            raise HTTPException(400, "Pick a day in the next two weeks.")
        hm = cal._hm(body.get("at"))
        if not hm:
            raise HTTPException(400, "Use a time like 18:30.")
        if dt.datetime.combine(day, dt.time(*hm)).timestamp() < now - 60:
            raise HTTPException(400, "That time has passed. Pick a later one.")
        try:
            mins = int(body.get("min") or h.get("default_min") or 25)
        except (TypeError, ValueError):
            raise HTTPException(400, "Minutes must be a number.")
        if not 5 <= mins <= 240:
            raise HTTPException(400, "Pick 5 to 240 minutes.")
        if cal.days_off(day, 1):
            raise HTTPException(409, "That day is off. Turn it back on first.")
        at = f"{hm[0]:02d}:{hm[1]:02d}"
        same = next((x for x in cal.plan(db.connect(), day, 1, now)
                     if x["key"] == f"{habit}@{day.isoformat()}T{at}" and x["state"] != "skipped"), None)
        if same:
            raise HTTPException(409, f"{same['label']} is already planned then.")
        nb = cal.add_once(habit, day.isoformat(), at, mins)
        reply = f"Added {nb['label']} {_when(nb['date'], today)} at {nb['at']}, {nb['min']} min."
    elif op in ("dayoff", "dayon"):
        try:
            day = dt.date.fromisoformat(str(body.get("date") or "")[:10])
        except ValueError:
            raise HTTPException(400, "Pick a day.")
        keep = [d for d in cal.load_away() if d["date"] >= today.isoformat() and d["date"] != day.isoformat()]
        label = str(body.get("label") or "Day off").strip()[:24] or "Day off"
        r = put_away({"days": keep + [{"date": day.isoformat(), "label": label}] if op == "dayoff" else keep})
        name = _day_name(day, today)
        if op == "dayoff":
            n = r["cleared_blocks"]
            reply = f"{name} is a day off. " + ("Nothing was planned." if not n else
                                                "I've cleared its block." if n == 1 else f"I've cleared its {n} blocks.")
        else:
            reply = f"{name} is back on the plan."
    else:
        raise HTTPException(400, "op must be move, skip, unskip, add, remove, dayoff or dayon.")
    if source == "phone" and op not in ("dayoff", "dayon") and not db.active_session(db.connect()):
        try:                                     # the notch confirms a change made on the phone (days off say it already)
            notify(f"From your iPhone: {reply}", kind="info", actions=[{"label": "OK", "dismiss": True}])
        except Exception as e:
            print(f"[alibi] plan line skipped: {e!r}", flush=True)
    return {"ok": True, "reply": reply, **days_view(int(body.get("days") or PLAN_DAYS), now)}


@router.get("/days")
def get_days(days: int = PLAN_DAYS):
    return days_view(days)


@router.post("/plan/edit")
def post_edit(body: dict):
    return edit(body)


def plan_page_html() -> str:
    """web/plan.html with tokens.css inlined, for the phone listener (it serves no /web files)."""
    import pathlib, re
    web = pathlib.Path(__file__).resolve().parent / "web"
    page = (web / "plan.html").read_text()
    css = (web / "css" / "tokens.css").read_text()
    return re.sub(r'<link rel="stylesheet" href="[^"]*tokens\.css[^"]*">', lambda m: f"<style>{css}</style>", page, count=1)
