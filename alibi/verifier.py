"""P1/P3 — turn a session's events into on_task_ratio + verdict + evidence."""
from . import config, db, evidence


def verdict_for(ratio: float) -> str:
    t = config.habits().get("verdict", {})
    return "done" if ratio >= t.get("done", 0.7) else "partial" if ratio >= t.get("partial", 0.4) else "slacked"


def finalise(con, session, artefact: str | None = None) -> str:
    """Score the session, render evidence, close it. Returns a one-line human summary for notify()."""
    labels = db.session_events(con, session["id"], source="camera")
    if not labels:
        db.finish_session(con, session["id"], on_task_ratio=0.0, verdict="slacked", artefact=artefact)
        return f"{session['habit']}: no evidence collected — logged as slacked."
    ratio = sum(e["payload"]["label"] == "on_task" for e in labels) / len(labels)
    verdict = verdict_for(ratio)
    path = evidence.contact_sheet(session, labels, ratio, verdict)
    db.finish_session(con, session["id"], on_task_ratio=ratio, verdict=verdict, evidence_path=path, artefact=artefact)
    return _line(session, verdict, ratio, labels)


def _line(session, verdict, ratio, labels) -> str:
    seen = {l: sum(e["payload"]["label"] == l for e in labels) for l in db.LABELS}
    off = ", ".join(f"{l.replace('_', ' ')} ×{n}" for l, n in seen.items() if n and l != "on_task")
    return (f"{session['habit'].capitalize()}: {verdict.upper()} — {ratio:.0%} on task "
            f"over {len(labels)} samples" + (f" ({off})." if off else "."))
