"""First-run wizard + plain-language habit endpoints (included by api.py through hooks.routers()).

GET  /api/onboarding                 {onboarded, needs_onboarding, step, picked, steps, connect, templates, habits}
GET  /api/onboarding/templates       {templates: [{id, title, emoji, check, check_text, minutes?, blurb, how, schedule,
                                       ask_name?}]}
POST /api/onboarding/habits          {picks: [{template, name?, minutes?, schedule?, calendar?, check?, target?}],
                                      replace?: true}  -> {added: [keys], habits: [view]}
POST /api/onboarding/progress        {step, picked?}  -> saved progress (wizard resumes there)
POST /api/onboarding/practice        {habit?}         -> {started, habit, reply, session_id}  (2-minute session)
POST /api/onboarding/done            -> {onboarded: true}
POST /api/onboarding/reset           -> {onboarded: false}  ('Run setup again')
GET  /api/habits/view                {habits: [{key, label, check, check_text, how, minutes, target_text, schedule,
                                       schedule_text, calendar, emoji, created_at, startable, details}]}
GET  /api/habits/checks              {checks: [{value, text, how}]}  — 'How should Alibi check it?'
GET  /api/habits/suggest?text=...    {known, draft: {name, key, minutes, check, check_text, how, schedule, calendar,
                                       start_after_add}, card_label, reply}; no text -> the last unknown reply (60 s)
POST /api/habits/add                 {name, minutes?, check?, schedule?, calendar?, template?, target?, key?, start?,
                                      weekly_target_min?, phone_shield?}
                                      -> {key, label, habit, reply, habits, saved}  (saved: see api.put_habits; no
                                      island alert when start is true: the session start says it)
POST /api/session/cancel             {undo?: bool, remove_habit?: key} -> {cancelled, reply, habits?}  (first 90 s, before
                                       only: no verdict, no honesty hit, no calendar outcome; undo also removes a
                                       habit that was added a moment ago and has no history)
GET  /api/health/summary             {rows: health.health_summary(), status: health.health_status()}
"""
import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from . import config, db, onboarding, templates

router = APIRouter()


@router.get("/api/onboarding")
def get_state():
    return onboarding.state()


@router.get("/api/onboarding/templates")
def get_templates():
    return {"templates": templates.public()}


class Picks(BaseModel):
    picks: list[dict]
    replace: bool = True


@router.post("/api/onboarding/habits")
def post_picks(body: Picks):
    try:
        return onboarding.apply_picks(body.picks, replace=body.replace)
    except ValueError as e:
        raise HTTPException(400, str(e))


class Progress(BaseModel):
    step: str
    picked: list[str] | None = None


@router.post("/api/onboarding/progress")
def post_progress(body: Progress):
    return onboarding.save_progress(body.step, body.picked)


class Practice(BaseModel):
    habit: str | None = None


@router.post("/api/onboarding/practice")
def post_practice(body: Practice | None = None):
    return onboarding.practice(habit=body.habit if body else None)


@router.post("/api/onboarding/done")
def post_done():
    return onboarding.mark_done()


@router.post("/api/onboarding/reset")
def post_reset():
    return onboarding.reset()


@router.get("/api/habits/view")
def habits_view():
    return {"habits": onboarding.view_habits()}


@router.get("/api/habits/checks")
def habit_checks():
    return {"checks": [{"value": k, "text": config.CHECK_TEXT[k], "how": config.photo_text(templates.CHECK_HOW[k])}
                       for k in ("camera", "screen", "both", "strava", "health")]}


@router.get("/api/habits/suggest")
def habit_suggest(text: str = ""):
    if not text:
        from . import cli
        last = getattr(cli, "LAST_UNKNOWN", None)
        if last and time.time() - last["ts"] < 60:
            return {**onboarding.suggest(last["text"]), "text": last["text"]}
        return {"known": None, "draft": None, "card_label": None, "reply": None}
    return {**onboarding.suggest(text), "text": text}


class AddHabit(BaseModel):
    name: str | None = None
    minutes: int | None = None
    check: str | None = None
    schedule: list[dict] | None = None
    calendar: bool | None = None
    template: str | None = None
    target: float | None = None
    key: str | None = None
    start: bool = False
    weekly_target_min: int | None = None
    phone_shield: bool | None = None


@router.post("/api/habits/add")
def habit_add(body: AddHabit, request: Request):
    from . import today
    try:
        before = config.habits()
    except Exception:
        before = {}
    try:
        out = onboarding.add(body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    con = db.connect()
    if body.start and out["habit"].get("modality"):
        from . import cli
        out["reply"] = cli.start_habit(con, out["key"], int(body.minutes or out["habit"]["default_min"]))
    out["habits"] = onboarding.view_habits()
    out["saved"] = today.record_save(before, config.habits(), today.via_of(request.headers.get("x-alibi-client")),
                                     start=body.start, con=con)
    return out


@router.get("/api/health/summary")
def health_summary():
    from . import health
    con = db.connect()
    return {"rows": health.health_summary(con), "status": health.health_status(con)}


class Cancel(BaseModel):
    undo: bool = False
    remove_habit: str | None = None


@router.post("/api/session/cancel")
def session_cancel(body: Cancel | None = None):
    from . import cli
    body = body or Cancel()
    con = db.connect()
    s = db.active_session(con)
    reply = cli.cancel(con, force=body.undo)
    cancelled = bool(s) and db.get_session(con, s["id"]) is None
    out = {"cancelled": cancelled, "reply": reply}
    if cancelled and body.remove_habit:
        out.update(onboarding.remove_new(con, body.remove_habit))
    return out
