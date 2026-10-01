"""Pinch's rulebook: what the mascot is doing right now, computed once on the server so the dashboard, the island
and the iPhone react the same way and never double-fire.

    pinch_state(state) -> {"mood", "event", "seq", "age_s", "line"}

- mood: the held, looping pose: idle | focused | listening | thinking | sleepy | reading
- event: the latest one-shot clip: hello | sideeye | nudge | celebrate | partial | supportive | surprise | connected,
  or None
- seq: milliseconds of the moment that triggered `event` (it only grows). A client plays `event` once, when `seq`
  is bigger than the last one it played AND `age_s` is small (a page that loads late doesn't replay old news).
- line: Pinch's line for this moment, at most 12 words, or None.

`state` is the dict /api/state builds ({now, session, alert, recent_verdict, ...}); /api/phone/session passes the same
keys. Stdlib only, no I/O. Frequency caps (one one-shot per 90 s, three side-eyes per session) live in the engines.
"""
from __future__ import annotations

import datetime as dt
import time

MOODS = ("idle", "focused", "listening", "thinking", "sleepy", "reading")
CLIPS = ("hello", "sideeye", "nudge", "celebrate", "partial", "supportive", "surprise", "connected")

FRESH_S = 15 * 60          # an alert older than this no longer drives an event
JUST_STARTED_S = 30        # a session younger than this gets a thumbs-up
REPORT_READING_S = 10 * 60  # how long Pinch "reads" after the nightly report lands


def _clock(ts: float | None) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%H:%M") if ts else ""


def _mins(seconds: float | None) -> int:
    return max(1, round((seconds or 0) / 60))


def _habit(d: dict | None) -> str:
    if not d:
        return "it"
    return (d.get("habit_label") or d.get("label") or d.get("habit") or "it").lower()


def _seen(v: dict, finished: dict | None = None) -> str | None:
    """'23 of 25 min seen' from a verdict alert (minutes come from the finished session when it matches), else '92% on task'."""
    ratio = v.get("ratio", v.get("on_task_ratio"))
    declared = v.get("declared_min")
    if not declared and finished and finished.get("id") == v.get("session_id"):
        declared = finished.get("declared_min")
    if declared and ratio is not None:
        return f"{round(declared * ratio)} of {declared} min seen"
    if ratio is not None:
        return f"{round(ratio * 100)}% on task"
    return None


def _event(alert: dict | None, session: dict | None, now: float,
           finished: dict | None = None) -> tuple[str | None, float | None, str | None]:
    """(clip, trigger_ts, line) for the newest thing worth reacting to."""
    best: tuple[str | None, float | None, str | None] = (None, None, None)
    if alert and now - (alert.get("ts") or 0) <= FRESH_S:
        kind, ts = alert.get("kind"), alert.get("ts")
        if kind == "nudge":
            clip = "sideeye" if alert.get("label") == "phone" else "nudge"
            best = (clip, ts, alert.get("text"))
        elif kind == "verdict":
            v = alert.get("verdict")
            seen = _seen(alert, finished)
            if v == "done":
                best = ("celebrate", ts, f"Done. {seen}." if seen else "Done. Logged.")
            elif v == "partial":
                best = ("partial", ts, f"Partly. {seen}." if seen else "Partly done. Logged.")
            elif v == "slacked":
                best = ("supportive", ts, f"Not this time. {seen}." if seen else "Not this time. Tomorrow?")
        elif kind == "planned":
            best = ("hello", ts, f"It's time for {_habit(alert)}.")
        elif kind == "info" and str(alert.get("text", "")).startswith("Strava:"):
            best = ("connected", ts, "Run synced from Strava.")
        elif kind == "synced":
            text = str(alert.get("text") or "")
            best = ("connected", ts, text if text and len(text.split()) <= 12 and "!" not in text
                    else "Your iPhone checked in.")
    started = (session or {}).get("started_at")
    if started and now - started <= JUST_STARTED_S and (best[1] is None or started > best[1]):
        best = ("connected", started, f"On it. Watching {_habit(session)}.")
    return best


def _mood(state: dict, now: float) -> tuple[str, str | None]:
    s = state.get("session")
    if s:
        if s.get("on_break"):
            back = s["on_break"].get("until")
            return "sleepy", f"Break. Back at {_clock(back)}." if back else "On a break."
        d = s.get("drifting")
        if d:
            return "thinking", f"Hm. {d.get('label_text') or d.get('label', 'something else')} for {_mins(d.get('since_s'))} min."
        if not s.get("samples"):
            return "listening", f"Watching {_habit(s)}. First check in a minute."
        ends = s.get("ends_at")
        return "focused", f"Watching {_habit(s)} until {_clock(ends)}." if ends else f"Watching {_habit(s)}."
    a = state.get("alert") or {}
    if a.get("kind") == "report" and now - (a.get("ts") or 0) <= REPORT_READING_S:
        return "reading", "Reading tonight's report."
    hour = dt.datetime.fromtimestamp(now).hour
    if hour >= 23 or hour < 6:
        return "sleepy", None
    return "idle", None


def pinch_state(state: dict | None) -> dict:
    state = state or {}
    now = float(state.get("now") or time.time())
    mood, mood_line = _mood(state, now)
    clip, ts, clip_line = _event(state.get("alert"), state.get("session"), now, state.get("recent_verdict"))
    return {
        "mood": mood,
        "event": clip,
        "seq": int(ts * 1000) if ts else 0,
        "age_s": round(now - ts, 1) if ts else None,
        "line": clip_line if clip and now - ts <= 120 else mood_line,
    }


def from_db(con) -> dict:
    """pinch_state() for callers outside /api/state (the phone listener), built from the same helpers."""
    from . import api, db
    from .notify import recent_alerts
    s = db.active_session(con)
    alerts = recent_alerts(1)
    return pinch_state({"now": time.time(), "session": api._session_json(con, s, live=True) if s else None,
                        "alert": alerts[-1] if alerts else None,
                        "recent_verdict": None if s else api._recent_verdict(con)})


def _selftest() -> None:
    now = 1_790_870_000.0
    idle = pinch_state({"now": now})
    assert idle["mood"] in MOODS and idle["event"] is None and idle["seq"] == 0, idle
    live = {"now": now, "session": {"habit": "drawing", "label": "Drawing", "started_at": now - 600,
                                    "ends_at": now + 900, "samples": 8}}
    assert pinch_state(live)["mood"] == "focused"
    fresh = {**live, "session": {**live["session"], "started_at": now - 5, "samples": 0}}
    r = pinch_state(fresh)
    assert r["mood"] == "listening" and r["event"] == "connected" and r["seq"] == int((now - 5) * 1000), r
    drift = {**live, "session": {**live["session"], "drifting": {"label": "phone", "label_text": "Phone", "since_s": 190}}}
    assert pinch_state(drift)["mood"] == "thinking"
    nudge = {**drift, "alert": {"kind": "nudge", "label": "phone", "ts": now - 3,
                                "text": "You said drawing. I've seen your phone for 3 minutes."}}
    r = pinch_state(nudge)
    assert r["event"] == "sideeye" and r["line"].startswith("You said drawing"), r
    brk = {**live, "session": {**live["session"], "on_break": {"until": now + 240, "left_s": 240}}}
    assert pinch_state(brk)["mood"] == "sleepy"
    for v, clip in (("done", "celebrate"), ("partial", "partial"), ("slacked", "supportive")):
        r = pinch_state({"now": now, "alert": {"kind": "verdict", "verdict": v, "ts": now - 2, "declared_min": 25,
                                              "ratio": 0.92}})
        assert r["event"] == clip and r["mood"] in MOODS, r
    r = pinch_state({"now": now, "alert": {"kind": "verdict", "verdict": "done", "ts": now - 2, "declared_min": 25,
                                          "ratio": 0.92}})
    assert r["line"] == "Done. 23 of 25 min seen.", r
    r = pinch_state({"now": now, "alert": {"kind": "verdict", "verdict": "done", "ts": now - 2, "session_id": 7,
                                          "ratio": 0.92}, "recent_verdict": {"id": 7, "declared_min": 25}})
    assert r["line"] == "Done. 23 of 25 min seen.", r
    r = pinch_state({"now": now, "alert": {"kind": "verdict", "verdict": "partial", "ts": now - 2, "ratio": 0.5}})
    assert r["line"] == "Partly. 50% on task.", r
    r = pinch_state({"now": now, "alert": {"kind": "verdict", "verdict": "slacked", "ts": now - 2, "declared_min": 25,
                                          "ratio": 0.3}})
    assert r["line"] == "Not this time. 8 of 25 min seen.", r
    stale = pinch_state({"now": now, "alert": {"kind": "verdict", "verdict": "done", "ts": now - FRESH_S - 1}})
    assert stale["event"] is None, stale
    strava = pinch_state({"now": now, "alert": {"kind": "info", "text": "Strava: Morning run, 5.1 km — logged.",
                                               "ts": now - 1}})
    assert strava["event"] == "connected", strava
    synced = pinch_state({"now": now, "alert": {"kind": "synced", "source": "health", "ts": now - 2,
                                               "text": "Your iPhone checked in: steps 2,022."}})
    assert synced["event"] == "connected" and synced["line"].startswith("Your iPhone"), synced
    a, b = pinch_state(nudge), pinch_state({**nudge, "now": now + 1})
    assert a["seq"] == b["seq"], "the same alert must keep the same seq across polls"
    for r in (idle, pinch_state(live), pinch_state(nudge)):
        assert r["line"] is None or (len(r["line"].split()) <= 12 and "!" not in r["line"]), r
    print("pinch rulebook ok")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    else:
        import json
        print(json.dumps(pinch_state({"now": time.time()}), indent=2))
