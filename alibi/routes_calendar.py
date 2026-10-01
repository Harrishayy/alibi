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
"""
import datetime as dt, subprocess, sys, time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from . import calendar_sync as cal, db

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
