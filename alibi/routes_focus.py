"""Focus over HTTP (mounted by api.py through hooks.routers(); loopback dashboard only, like the rest of :8765).

GET /api/focus/day?date=YYYY-MM-DD|today|yesterday   one day's review: pickups by hour and against the week, in
                                                     planned blocks, per habit and session, Mac distractions, rules
GET /api/focus/week                                  the last 7 days, pickups an hour per habit, who struggled

Numbers come from alibi/focus.py, counted by code. These name sites and apps (the Mac's top distractions): the agent
gets alibi.focus.agent_summary() through /api/agent/context instead, which never does.
"""
from fastapi import APIRouter, HTTPException
from . import db, focus

router = APIRouter()


@router.get("/api/focus/day")
def get_day(date: str | None = None):
    try:
        d0 = focus.as_date(date)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return focus.day(db.connect(), d0)


@router.get("/api/focus/week")
def get_week():
    return focus.week(db.connect())
