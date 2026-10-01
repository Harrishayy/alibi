"""P2 — nudge mid-session when the last N camera samples are not on task. Max one nudge per cooldown."""
import time
from . import config, db
from .notify import notify

_last_nudge = {}     # session_id -> ts

LINES = {
    "phone": "You said {habit}. I've seen your phone for {mins}.",
    "absent": "You said {habit}. The desk has been empty for {mins}.",
    "idle": "You said {habit}. You're there, but nothing's happening — {mins} now.",
    "off_task": "You said {habit}. That isn't {habit} — {mins} and counting.",
}


def check(con, session) -> str | None:
    cfg = config.habits()
    n = int(cfg.get("nudge_after_off_task_samples", 3))
    cooldown = float(cfg.get("nudge_cooldown_min", 10)) * 60
    now = time.time()
    if now - _last_nudge.get(session["id"], 0) < cooldown:
        return None
    labels = [e["payload"]["label"] for e in db.session_events(con, session["id"], "camera")][-n:]
    if len(labels) < n or "on_task" in labels:
        return None
    worst = max(set(labels), key=labels.count)
    secs = n * config.SAMPLE_EVERY_S
    mins = round(secs / 60)
    span = f"{secs} seconds" if secs < 90 else f"{mins} minute{'s' * (mins != 1)}"
    text = LINES[worst].format(habit=session["habit"], mins=span)
    _last_nudge[session["id"]] = now
    notify(text, kind="nudge")
    return text
