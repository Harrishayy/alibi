"""Phone + Mac signal endpoints (mounted by api.py through hooks.routers()). Contract: docs/SIGNALS.md.

GET /api/signals?session=ID      the session's phone/Mac/heart timeline, off-task stretches, and any score cap
GET /api/signals?day=YYYY-MM-DD  the day's summary + its whole timeline (meeting/media "off" rows carry end=True)
GET /api/signals/live            last value per source/kind + freshness
GET /api/signals/status          which sources are flowing, when last seen, what's missing + a plain-language fix
"""
import datetime as dt
from fastapi import APIRouter, HTTPException
from . import db, signals

router = APIRouter()


def _con():
    return db.connect()


@router.get("/api/signals")
def get_signals(session: int | None = None, day: str | None = None):
    con = _con()
    if session is not None:
        s = db.get_session(con, session)
        if s is None:
            raise HTTPException(404, f"No session {session}.")
        return signals.session_summary(con, s)
    try:
        d = dt.date.fromisoformat(day).isoformat() if day else dt.date.today().isoformat()
    except ValueError:
        raise HTTPException(400, "day must look like 2026-10-01.")
    t0 = dt.datetime.fromisoformat(d).timestamp()
    rows = []
    st = {x["id"]: x for x in signals.screentime_deltas(con, t0, t0 + 86400)}
    sess = {}
    for e in signals._rows(con, t0, t0 + 86400):
        if e["session_id"] and e["session_id"] not in sess:
            r = db.get_session(con, e["session_id"])
            sess[e["session_id"]] = dict(r) if r else {}
        h = signals._hint(e, sess.get(e["session_id"]) or {}, st)
        end = None
        if not h:
            end = _span_end(e)                     # sensors write on *change*: the "off" row closes the span
            if not end:
                continue
            h = ("neutral", end)
        row = {"ts": e["ts"], "source": e["source"], "kind": e["kind"], "session_id": e["session_id"],
               "verdict_hint": h[0] if e["session_id"] else "neutral", "text": h[1]}
        if end:
            row["end"] = True
        rows.append(row)
    # The whole day, never the newest N: a real day is a few thousand rows and the page draws them in ms. Only a
    # pathological day is trimmed, and then the page is told where the lanes start (it says so instead of "no data").
    out = {"day": d, "summary": signals.day_summary(con, d), "timeline": rows, "from_ts": None}
    if len(rows) > DAY_ROWS_MAX:
        out["timeline"] = rows[-DAY_ROWS_MAX:]
        out["from_ts"] = out["timeline"][0]["ts"]
    return out


DAY_ROWS_MAX = 20000


def _span_end(e: dict) -> str | None:
    """Text for a change-based "off" row (meeting over, media stopped) so the page can close the on-span it opened."""
    p = e["payload"] if isinstance(e.get("payload"), dict) else {}
    if e["source"] == "mac" and e["kind"] == "meeting" and not (p.get("camera") or p.get("mic")):
        return "Call ended: camera and mic off"
    if e["source"] == "mac" and e["kind"] == "media" and not p.get("playing"):
        return f"Stopped playing{': ' + str(p['app']) if p.get('app') else ''}"
    return None


@router.get("/api/signals/live")
def get_live():
    return signals.live(_con())


@router.get("/api/signals/status")
def get_status():
    return signals.status(_con())


@router.get("/signals", include_in_schema=False)
def signals_page():
    """The Signals page (alibi/web/signals.html): is Alibi seeing you, today's lanes, per-session evidence, Health."""
    from fastapi.responses import FileResponse
    from . import config
    return FileResponse(config.ROOT / "alibi" / "web" / "signals.html")
