"""Front door. The island, the dashboard and the terminal all call these.

  python -m alibi.cli start "draw for 1 hour"
  python -m alibi.cli status
  python -m alibi.cli end [--artefact URL_OR_PATH]
  python -m alibi.cli report
  python -m alibi.cli say "how am I doing"      # free text, routed like the island prompt

While a session is live, `say` also understands: "add 10", "change to 40", "break 5", "back", "snooze 5",
"it's on task". After a pace reminder, "yes" starts the suggested session.
"""
import argparse, re, threading, time
from . import config, db, intent

_lock = threading.RLock()          # FastAPI runs sync endpoints in a thread pool (R2/R3)
HINT = 'Say "end", "break 5" or "add 10".'


def start(con, text: str) -> str:
    with _lock:
        s = db.active_session(con)
        if s:
            return f"Already watching {config.display_name(s['habit'])}. End it first."
        try:
            it = intent.parse(text)
        except intent.DurationError as e:
            return str(e)
        except ValueError:
            return _not_a_habit(con, text)
        return start_habit(con, it["habit"], it["minutes"], said=intent._minutes(text) is not None)


def start_habit(con, habit: str, minutes: int, said: bool = True) -> str:
    with _lock:
        h = config.habits()["habits"].get(habit)
        if not h or not h.get("modality"):
            return _not_a_habit(con, habit)
        sid = db.create_session(con, habit, h["modality"], minutes)
        if sid is None:
            s = db.active_session(con)
            return f"Already watching {config.display_name(s['habit']) if s else 'something'}. End it first."
    name = config.display_name(habit)
    how = "" if said else " (your usual)"
    return f"Session {sid}: {name} for {minutes} min{how}. Watching — say \"change to 40\" to fix."


def _not_a_habit(con, text: str) -> str:
    """F9: Strava habits get a claim the daemon checks; unknown verbs get told how to add a habit."""
    key = intent.match_habit(text, include_sources=True)
    h = config.habits()["habits"].get(key or "", {})
    if key and h.get("source") == "strava":
        km = h.get("min_km", 5)
        now = time.time()
        db.add_event(con, "user", "claim", {"habit": key, "min_km": km, "until": now + 2 * 3600})
        return (f"{config.display_name(key)} is Strava's job. I'll check for a ≥{km:g} km run in the next 2 h.")
    return 'Not a habit yet. Say "add habit reading, physical, 20 min".'


def status(con) -> str:
    s = db.active_session(con)
    if not s:
        return "No active session."
    left = max(0, s["ends_at"] - time.time())
    b = db.in_break(con, s["id"])
    extra = f" (on a break for {int((b[1] - time.time()) // 60) + 1} more min)" if b else ""
    return f"{config.display_name(s['habit'])} — {int(left // 60)} min {int(left % 60):02d} s left{extra}"


def end(con, artefact: str | None = None, ended_at: float | None = None, missed: bool = False) -> str:
    """End the live session. Exactly one caller wins (R3); the rest get the recorded verdict, with no second alert."""
    from . import verifier
    from .notify import notify
    with _lock:
        s = db.active_session(con)
        if not s:
            last = con.execute("SELECT * FROM sessions WHERE status='done' ORDER BY ended_at DESC LIMIT 1").fetchone()
            if last and last["ended_at"] and time.time() - last["ended_at"] < 30:
                return verifier.voice(con, last)          # a racing duplicate end: same answer, no second alert
            return "No active session."
        out = verifier.close(con, s, artefact=artefact, ended_at=ended_at)
    if out is None:
        return verifier.voice(con, db.get_session(con, s["id"]))
    done = out["session"]
    note = _artefact_note(s, artefact)
    early = done["ended_at"] < s["ends_at"] - 1 and not missed
    if missed:
        _, _, dark = verifier.coverage_parts(con, done)
        name, dm = config.display_name(done['habit']), done["declared_min"]
        slept = min(dm, round(dark / 60))
        seen = max(0, min(round((done["on_task_ratio"] or 0) * dm), dm - slept))
        if dark >= 60:
            text = (f"While you were away: {name} — the laptop slept {slept} of {dm} min; "
                    f"{seen} min seen. Logged as {done['verdict']}.")
        else:
            n = len(verifier.camera_labels(con, done))
            text = (f"While you were away: {name} ended at "
                    f"{time.strftime('%H:%M', time.localtime(done['ended_at']))} — {done['verdict']}, "
                    f"{(done['on_task_ratio'] or 0):.0%} on task"
                    + (f" over {verifier._plural(n, 'sample')}." if n else "."))
        text += _streak_tail(con, done)
    else:
        text = out["voice"] + note + _streak_tail(con, done)
    notify(text, image_path=done["evidence_path"], kind="verdict", session_id=done["id"], habit=done["habit"],
           verdict=done["verdict"], ratio=done["on_task_ratio"], ended_early=early, missed=missed, line=out["line"],
           actions=[{"label": "Watch reel", "url": f"/api/reel?session={done['id']}"},
                    {"label": "Fix samples", "url": f"/#session-{done['id']}"},
                    {"label": f"Again {done['declared_min']}m",
                     "say": f"{done['habit']} for {done['declared_min']} min"}])
    from .daemon import _reel_later
    _reel_later(done["id"])
    return out["voice"] + note


def _streak_tail(con, s) -> str:
    """F5: 'Streak holds at 4 days. Your word is worth 64% this week.'"""
    try:
        from . import report
        r = report.build_json()
        row = next((x for x in r["rows"] if x["habit"] == s["habit"]), None)
        bits = []
        if row and row["streak_days"] >= 1 and s["verdict"] in ("done", "partial"):
            bits.append(f"Streak holds at {row['streak_days']} day{'s' * (row['streak_days'] != 1)}.")
        elif row and s["verdict"] == "slacked":
            bits.append("No streak today.")
        if r.get("alibi_score") is not None:
            bits.append(f"Your word is worth {r['alibi_score']:.0%} this week.")
        return (" " + " ".join(bits)) if bits else ""
    except Exception:
        return ""


def _artefact_note(s, artefact: str | None) -> str:
    """If the artefact is a git repo, show what actually changed during the session."""
    import os, subprocess
    if not artefact or not os.path.isdir(os.path.join(os.path.expanduser(artefact), ".git")):
        return f" Artefact: {artefact}." if artefact else ""
    since = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s["started_at"]))
    log = subprocess.run(["git", "-C", os.path.expanduser(artefact), "log", f"--since={since}", "--shortstat",
                          "--format="], capture_output=True, text=True).stdout.split("\n")
    stats = [l.strip() for l in log if l.strip()]
    return f" Repo: {len(stats)} commit(s) this session" + (f", last: {stats[0]}." if stats else ".")


def report(con=None) -> str:
    from . import report as r
    return r.build()


# --- live-session controls (F2) ----------------------------------------------------------------------------------

def extend(con, s, minutes: int) -> str:
    with _lock:
        new_total = s["declared_min"] + minutes
        if new_total > config.MAX_SESSION_MIN:
            return f"That makes {new_total} min — over the {config.MAX_SESSION_MIN} min limit. End this one and start another."
        con.execute("UPDATE sessions SET ends_at=ends_at+?, declared_min=declared_min+? WHERE id=? AND status='active'",
                    (minutes * 60, minutes, s["id"]))
        con.commit()
        db.add_event(con, "user", "extend", {"min": minutes}, session_id=s["id"])
    return f"{config.display_name(s['habit'])}: +{minutes} min, {new_total} min in all. Still watching."


def change_to(con, s, minutes: int) -> str:
    with _lock:
        if minutes < 1 or minutes > config.MAX_SESSION_MIN:
            return f"Pick 1–{config.MAX_SESSION_MIN} minutes."
        delta = minutes - s["declared_min"]
        if s["started_at"] + minutes * 60 <= time.time():
            return f"{minutes} min has already passed. Say \"end\" instead."
        con.execute("UPDATE sessions SET ends_at=ends_at+?, declared_min=? WHERE id=? AND status='active'",
                    (delta * 60, minutes, s["id"]))
        con.commit()
        db.add_event(con, "user", "change", {"from": s["declared_min"], "to": minutes}, session_id=s["id"])
    return f"{config.display_name(s['habit'])}: now {minutes} min."


def take_break(con, s, minutes: int | None) -> str:
    """Pause the clock (ends_at moves out by the break) and the witness. The second break goes on the record."""
    minutes = max(1, min(30, minutes or 5))
    now = time.time()
    with _lock:
        if db.in_break(con, s["id"], now):
            return "Already on a break. Say \"back\" when you are."
        n = len(db.user_events(con, s["id"], "break"))
        db.add_event(con, "user", "break", {"until": now + minutes * 60, "min": minutes}, session_id=s["id"], ts=now)
        con.execute("UPDATE sessions SET ends_at=ends_at+? WHERE id=? AND status='active'", (minutes * 60, s["id"]))
        con.commit()
    if n >= 1:
        return f"Second break. Noted on the record. Back in {minutes} min." if n == 1 else \
            f"Break number {n + 1}. Noted on the record."
    return f"Break: {minutes} min. The witness looks away; the clock waits. Say \"back\" to resume."


def resume(con, s) -> str:
    now = time.time()
    with _lock:
        b = db.in_break(con, s["id"], now)
        if not b:
            db.add_event(con, "user", "back", {}, session_id=s["id"], ts=now)
            return f"Noted. Back on {config.display_name(s['habit'])}."
        db.add_event(con, "user", "resume", {}, session_id=s["id"], ts=now)
        con.execute("UPDATE sessions SET ends_at=ends_at-? WHERE id=? AND status='active'", (b[1] - now, s["id"]))
        con.commit()
    return f"Back. {status(con)}."


def snooze(con, s, minutes: int | None) -> str:
    minutes = max(1, min(30, minutes or 5))
    db.add_event(con, "user", "snooze", {"until": time.time() + minutes * 60}, session_id=s["id"])
    return f"No nudges for {minutes} min. The witness still watches."


def on_task_last(con, s) -> str:
    """'It's on task' from a nudge: overrule the latest sample (camera) or the latest window title (screen)."""
    from . import nudges, verifier
    smp = nudges.recent_samples(con, s)
    if not smp:
        return "Nothing to overrule yet."
    last = smp[-1]
    if last["source"] == "screen":
        return verifier.correct(con, s["id"], None, "on_task", title=last["title"])
    return verifier.correct(con, s["id"], last["ts"], "on_task")


def add_habit(con, text: str) -> str:
    """'add habit reading, physical, 20 min' -> habits.yaml (via health.save_habits validation)."""
    from . import health
    m = re.match(r"^add habit\s+([a-z][a-z0-9_ ]{0,23})\s*,\s*(physical|digital|hybrid)(?:\s*,\s*(\d+)\s*(?:m|min|mins|minutes)?)?",
                 text.strip().lower())
    if not m:
        return 'Say it like "add habit reading, physical, 20 min".'
    key = m.group(1).strip().replace(" ", "_")
    habits = config.habits()["habits"]
    if key in habits:
        return f"{config.display_name(key)} is already a habit."
    default = int(m.group(3) or 25)
    habits[key] = {"modality": m.group(2), "aliases": [key.replace("_", " ")], "weekly_target_min": default * 4,
                   "default_min": default, "on_task_looks_like": key.replace("_", " ")}
    try:
        health.save_habits(habits)
    except ValueError as e:
        return f"Couldn't add it: {e}"
    return f"Added {config.display_name(key)} ({m.group(2)}, {default} min). Say \"{key.replace('_', ' ')} for {default}\"."


def _pace_offer() -> dict | None:
    from .notify import last_alert
    a = last_alert("pace")
    if a and time.time() - a["ts"] < 600 and a.get("habit"):
        return a
    return None


def say(con, text: str) -> str:
    """Route free text the way a chat agent would."""
    t = re.sub(r"\s+", " ", text.strip().lower())
    if not t:
        return "Say what you're about to do, e.g. \"draw for 25\"."
    if re.fullmatch(r"(status|how am i doing\??|how's it going\??|time left\??)", t):
        return status(con)
    s = db.active_session(con)
    if t.startswith("add habit"):
        return add_habit(con, text)
    if s:
        if m := re.match(r"^(?:add|extend(?: by)?|\+)\s*(\d+)", t):
            return extend(con, s, int(m.group(1)))
        if m := re.match(r"^(?:change|make it|set it|set)(?: it)? to (\d+)", t):
            return change_to(con, s, int(m.group(1)))
        if m := re.match(r"^(?:take a )?(?:break|pause)(?: for)?\s*(\d+)?", t):
            return take_break(con, s, int(m.group(1)) if m.group(1) else None)
        if re.fullmatch(r"(back|i'?m back|resume|unpause|back on it)[.!]?", t):
            return resume(con, s)
        if m := re.match(r"^snooze\s*(\d+)?", t):
            return snooze(con, s, int(m.group(1)) if m.group(1) else None)
        if re.fullmatch(r"(it'?s|its|that'?s|that was) (on task|work|fine)[.!]?", t):
            return on_task_last(con, s)
    try:
        has_duration = intent._minutes(t) is not None
    except Exception:
        has_duration = False
    habit = intent.match_habit(t)
    if re.match(r"^(end|stop|done|finish|i'?m done)\b", t) and not (habit and has_duration):
        art = re.search(r"(https?://\S+|/\S+)", text)
        return end(con, art.group(1) if art else None)
    if re.search(r"\b(report|this week|aligned)\b", t) and not (habit or has_duration):
        return report(con)
    if not s and re.fullmatch(r"(yes|yeah|yep|ok|okay|sure|go|do it|start)[.!]?", t):
        offer = _pace_offer()
        if offer:
            return start_habit(con, offer["habit"], int(offer.get("minutes") or 25))
        return "Yes to what? Say what you're about to do, e.g. \"draw for 25\"."
    if s and not habit:
        return f"{status(con)}. {HINT}"
    return start(con, text)


def main():
    p = argparse.ArgumentParser(prog="alibi")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("start").add_argument("text")
    sub.add_parser("status")
    sub.add_parser("end").add_argument("--artefact")
    sub.add_parser("report")
    sub.add_parser("say").add_argument("text")
    a = p.parse_args()
    con = db.connect()
    print({"start": lambda: start(con, a.text), "status": lambda: status(con),
           "end": lambda: end(con, a.artefact), "report": lambda: report(con),
           "say": lambda: say(con, a.text)}[a.cmd]())
    from .daemon import join_reels
    join_reels()          # R5: a CLI `end` must not exit before its reel is written


if __name__ == "__main__":
    main()
