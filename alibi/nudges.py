"""P2 — nudge mid-session when the last N samples are not on task (F1: camera AND screen), escalate on the second (F7).

Cooldown is durable (R8): nudges are recorded as events(source='alibi', kind='nudge'), so a daemon restart can't repeat
one, and only samples taken after the last nudge count towards the next.
"""
import subprocess, time
from . import config, db
from .notify import notify

LINES = {
    "phone": "Still {habit}? Your phone's been out for {mins}.",
    "absent": "Still {habit}? The desk has been empty for {mins}.",
    "idle": "Still {habit}? You're there, but nothing's moving — {mins} now.",
    "off_task": "Still {habit}? That doesn't look like {habit} — {mins} now.",
    "window": "Still {habit}? Your screen has been {title} for {mins}.",
    "window_then": "Still {habit}? Your screen has been {title} for {mins}, plus {rest}.",
    "window_mixed": "Still {habit}? Your screen has been everything but {habit} for {mins} ({names}).",
}
SECOND = "Second time. It's going in the report."


def cooldown_s() -> float:
    cfg = config.habits()
    if "nudge_cooldown_min" in cfg and config.SAMPLE_EVERY_S >= 30:
        return float(cfg["nudge_cooldown_min"]) * 60
    if config.SAMPLE_EVERY_S < 30:                               # demo cadence: nudge ~150 s, strike ~210 s (B4)
        return max(3.0 * config.SAMPLE_EVERY_S, 60.0)
    return 600.0


def recent_samples(con, session, since: float = 0.0) -> list[dict]:
    """Camera labels + (digital/hybrid) classified window titles, merged by time: [{ts, label, source, title?}]."""
    from . import evidence, verifier
    out = [{"ts": e["ts"], "label": e["payload"]["label"], "source": "camera", "note": e["payload"].get("note", "")}
           for e in verifier.camera_labels(con, session)] if session["modality"] in ("physical", "hybrid") else []
    if session["modality"] in ("digital", "hybrid"):
        win = verifier._window_events(con, session)[-12:]
        labels = verifier.classify_titles(con, session["habit"], {evidence._title_key(e["payload"]) for e in win})
        for e in win:
            k = evidence._title_key(e["payload"])
            out.append({"ts": e["ts"], "label": "on_task" if labels.get(k) == "on_task" else "off_task",
                        "source": "screen", "title": k, "app": e["payload"].get("app", "")})
    return sorted((x for x in out if x["ts"] > since), key=lambda x: x["ts"])


def nudges_for(con, session_id: int) -> list[dict]:
    return [e for e in db.session_events(con, session_id, "alibi") if e["kind"] == "nudge"]


def check(con, session) -> str | None:
    cfg = config.habits()
    n = int(cfg.get("nudge_after_off_task_samples", 3))
    now = time.time()
    if db.in_break(con, session["id"], now) or _snoozed(con, session["id"], now):
        return None
    past = nudges_for(con, session["id"])
    last = past[-1]["ts"] if past else 0.0
    if now - last < cooldown_s():
        return None
    labels = recent_samples(con, session, since=last)[-n:]
    habit = config.spoken_name(session["habit"])
    screen = []
    if len(labels) < n or any(l["label"] == "on_task" for l in labels):
        sig = _signal_reason(con, session, last, now)      # the phone/Mac can drift while the desk looks fine
        if not sig:
            return None
        worst, text = sig[0], sig[1].format(habit=habit)
        source = "signals"
    else:
        source = "samples"
        secs = int(labels[-1]["ts"] - labels[0]["ts"]) + (config.SAMPLE_EVERY_S if labels[-1]["source"] == "camera"
                                                           else config.LAPTOP_EVERY_S)
        mins = round(secs / 60)
        span = f"{secs} seconds" if secs < 90 else f"{mins} minute{'s' * (mins != 1)}"
        screen = [l for l in labels if l["source"] == "screen"]
        if screen and (len(screen) * 2 >= len(labels) or session["modality"] == "digital"):
            text, worst = _window_line(habit, screen, span), "off_task"
        else:
            cams = [l["label"] for l in labels if l["source"] == "camera"]
            worst = max(set(cams), key=cams.count)
            text = LINES[worst].format(habit=habit, mins=span)
    strike = len(past) >= 1
    if strike:
        nth = {1: SECOND}.get(len(past), f"{['Third', 'Fourth', 'Fifth'][min(len(past), 4) - 2]} time. "
                                           "It's all going in the report.")
        text = f"{text} {nth}"
        db.add_event(con, "alibi", "strike", {"n": len(past)}, session_id=session["id"], ts=now)
        if config.BLOCK_ON_DRIFT and screen:
            _hide(_most_common_app(screen))
    db.add_event(con, "alibi", "nudge", {"text": text, "label": worst, "strike": strike, "from": source},
                 session_id=session["id"], ts=now)
    notify(text, kind="nudge", session_id=session["id"], habit=session["habit"], label=worst, strike=strike,
           actions=[{"label": "I'm back", "say": "back"}, {"label": "It's on task", "say": "it's on task"},
                    {"label": "Snooze 5m", "say": "snooze 5"}])
    return text


def _signal_reason(con, session, since: float, now: float) -> tuple[str, str] | None:
    """('phone', 'Your phone says Instagram for 10 min. Still {habit}?') from docs/SIGNALS.md rows, or None."""
    try:
        from . import signals
        return signals.nudge_reason(con, session, since, now)
    except Exception as e:
        print(f"[alibi] signal nudge skipped: {e!r}", flush=True)
        return None


def _span(secs: float) -> str:
    secs = int(secs)
    mins = round(secs / 60)
    return f"{secs} seconds" if secs < 90 else f"{mins} minute{'s' * (mins != 1)}"


def _window_line(habit: str, screen: list[dict], span: str) -> str:
    """Name what the screen actually was (B2): one site -> its name + the whole span; a mostly-one-site run -> that
    site's own duration, 'then X'; a mix -> 'everything but C++ (YouTube, Slack, RustDesk)'."""
    from collections import Counter
    from . import verifier
    names = [verifier.short_title(l.get("title", "")) for l in screen]
    cnt = Counter(names)
    top, n = cnt.most_common(1)[0]
    if n == len(names):
        return LINES["window"].format(habit=habit, title=top, mins=span)
    if n * 2 > len(names):
        rest = verifier.join_names([k for k, _ in cnt.most_common()[1:3]])
        return LINES["window_then"].format(habit=habit, title=top, mins=_span(n * config.LAPTOP_EVERY_S), rest=rest)
    return LINES["window_mixed"].format(habit=habit, mins=span,
                                        names=", ".join(k for k, _ in cnt.most_common(4)))


def _most_common_app(screen: list[dict]) -> str:
    from collections import Counter
    return Counter(l.get("app", "") for l in screen).most_common(1)[0][0]


def _snoozed(con, session_id: int, now: float) -> bool:
    return any(e["payload"].get("until", 0) > now for e in db.user_events(con, session_id, "snooze"))


def _hide(app: str) -> None:
    """Opal-style consequence: hide the off-task app. Opt-in (BLOCK_ON_DRIFT=1). Never hides Alibi or a terminal."""
    from .verifier import CODE_APPS
    if not app or app.lower() in ("alibi", "finder") or app.lower() in CODE_APPS:
        return
    safe = app.replace('"', "")
    subprocess.Popen(["osascript", "-e", f'tell application "System Events" to set visible of process "{safe}" to false'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
