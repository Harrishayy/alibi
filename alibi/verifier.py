"""P1/P3 — turn a session's events into on_task_ratio + verdict + evidence.

physical -> camera labels; digital -> laptop window titles (classified once, cached); hybrid -> per-minute OR of both.
"""
import re
from collections import Counter
from . import config, db, evidence, llm

DISTRACTIONS = ("youtube", "netflix", "twitter", "x.com", "reddit", "instagram", "tiktok", "twitch", "messages",
                "whatsapp", "discord", "facebook", "prime video", "disney+", "spotify")
STOP = {"with", "or", "and", "the", "on", "in", "of", "a", "to", "files", "content", "next", "screen", "docs",
        "working", "hands", "holding", "output", "pages"}
TITLE_SYSTEM = ('You decide whether each window title is on task for a habit. Reply with JSON only: '
                '{"labels": {"<title>": "on_task|off_task", ...}}')


def verdict_for(ratio: float) -> str:
    t = config.habits().get("verdict", {})
    return "done" if ratio >= t.get("done", 0.7) else "partial" if ratio >= t.get("partial", 0.4) else "slacked"


def finalise(con, session, artefact: str | None = None) -> str:
    """Score the session, render evidence, close it. Returns a one-line human summary for notify()."""
    cam = db.session_events(con, session["id"], source="camera")
    win = _window_events(con, session)
    mod = session["modality"]
    if mod == "physical" or (mod == "hybrid" and not win):
        marks = [e["payload"]["label"] == "on_task" for e in cam]
    elif mod == "digital" or not cam:
        labels = classify_titles(con, session["habit"], {evidence._title_key(e["payload"]) for e in win})
        marks = [labels.get(evidence._title_key(e["payload"])) == "on_task" for e in win]
    else:
        marks = _hybrid_marks(con, session, cam, win)
    if not marks:
        db.finish_session(con, session["id"], on_task_ratio=0.0, verdict="slacked", artefact=artefact)
        return f"{session['habit'].capitalize()}: no evidence collected — logged as slacked."
    ratio = sum(marks) / len(marks)
    verdict = verdict_for(ratio)
    path = evidence.contact_sheet(session, cam, ratio, verdict) if cam else None
    db.finish_session(con, session["id"], on_task_ratio=ratio, verdict=verdict, evidence_path=path, artefact=artefact)
    line = f"{session['habit'].capitalize()}: {verdict.upper()} — {ratio:.0%} on task"
    if cam:
        seen = Counter(e["payload"]["label"] for e in cam)
        off = ", ".join(f"{l.replace('_', ' ')} ×{n}" for l, n in seen.items() if l != "on_task")
        line += f" over {len(cam)} samples" + (f" ({off})" if off else "")
    if win and mod != "physical":
        top = window_breakdown(con, session)[:2]
        line += "; screen: " + ", ".join(f"{w['title'][:40]} {w['share']:.0%}" for w in top)
    return line + "."


def _window_events(con, session):
    end = session["ended_at"] or session["ends_at"]
    return [e for e in db.events_between(con, session["started_at"], end, "laptop") if e["payload"].get("app")]


def window_breakdown(con, session) -> list[dict]:
    win = _window_events(con, session)
    labels = classify_titles(con, session["habit"], {evidence._title_key(e["payload"]) for e in win})
    return evidence.title_summary(win, labels)


def _hybrid_marks(con, session, cam, win) -> list[bool]:
    labels = classify_titles(con, session["habit"], {evidence._title_key(e["payload"]) for e in win})
    minutes = {}
    for e in cam:
        minutes.setdefault(int((e["ts"] - session["started_at"]) // 60), []).append(e["payload"]["label"] == "on_task")
    for e in win:
        minutes.setdefault(int((e["ts"] - session["started_at"]) // 60), []).append(
            labels.get(evidence._title_key(e["payload"])) == "on_task")
    return [any(v) for _, v in sorted(minutes.items())]


def classify_titles(con, habit: str, titles: set[str]) -> dict[str, str]:
    """title_cache first; uncached titles go to ONE batch LLM call (or keyword rules offline); write back."""
    titles = {t for t in titles if t}
    cached = {r["title"]: r["label"] for r in con.execute(
        f"SELECT title, label FROM title_cache WHERE habit=? AND title IN ({','.join('?' * len(titles))})",
        (habit, *titles))} if titles else {}
    todo = sorted(titles - cached.keys())
    if todo:
        fresh = {}
        if config.TEXT_READY:
            try:
                h = config.habits()["habits"].get(habit, {})
                out = llm.chat_json(TITLE_SYSTEM, f"Habit: {habit}. On task looks like: {h.get('on_task_looks_like')}\n"
                                                  "Titles:\n" + "\n".join(todo), max_tokens=1500)
                fresh = {t: l for t, l in out.get("labels", {}).items() if t in todo and l in ("on_task", "off_task")}
            except Exception:
                fresh = {}
        for t in todo:
            fresh.setdefault(t, _rule_label(habit, t))
        con.executemany("INSERT OR REPLACE INTO title_cache(habit, title, label) VALUES (?,?,?)",
                        [(habit, t, l) for t, l in fresh.items()])
        con.commit()
        cached.update(fresh)
    return cached


def _rule_label(habit: str, title: str) -> str:
    t = title.lower()
    if any(d in t for d in DISTRACTIONS):
        return "off_task"
    h = config.habits()["habits"].get(habit, {})
    words = {habit, *map(str, h.get("aliases", []))}
    words |= {w for w in re.findall(r"[\w.+#-]+", str(h.get("on_task_looks_like", "")).lower())
              if len(w) > 2 and w not in STOP}
    return "on_task" if any(re.search(rf"(?<![\w]){re.escape(w.lower())}", t) for w in words) else "off_task"
