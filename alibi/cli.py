"""Front door. The island, the dashboard and the terminal all call these.

  python -m alibi.cli start "draw for 1 hour"
  python -m alibi.cli status
  python -m alibi.cli end [--artefact URL_OR_PATH]
  python -m alibi.cli report
  python -m alibi.cli say "how am I doing"      # free text, routed like the island prompt
"""
import argparse, re, time
from . import db, intent


def start(con, text: str) -> str:
    s = db.active_session(con)
    if s:
        return f"Already watching {s['habit']}. End it first."
    try:
        it = intent.parse(text)
    except ValueError:
        return "I don't know that habit. Try one from habits.yaml."
    sid = db.create_session(con, it["habit"], it["modality"], it["minutes"])
    return f"Session {sid}: {it['habit']} ({it['modality']}) for {it['minutes']} min. Watching."


def status(con) -> str:
    s = db.active_session(con)
    if not s:
        return "No active session."
    left = max(0, s["ends_at"] - time.time())
    return f"{s['habit']} — {int(left // 60)} min {int(left % 60):02d} s left"


def end(con, artefact: str | None = None) -> str:
    s = db.active_session(con)
    if not s:
        return "No active session."
    from . import verifier
    from .notify import notify
    line = verifier.finalise(con, s, artefact=artefact)
    done = con.execute("SELECT evidence_path FROM sessions WHERE id=?", (s["id"],)).fetchone()
    notify(f"Ended early. {line}", image_path=done["evidence_path"], kind="verdict")
    return line


def report(con=None) -> str:
    from . import report as r
    return r.build()


def say(con, text: str) -> str:
    """Route free text the way a chat agent would."""
    t = text.strip().lower()
    if re.fullmatch(r"(status|how am i doing\??|how's it going\??|time left\??)", t):
        return status(con)
    if re.match(r"^(end|stop|done|finish|i'?m done)\b", t):
        art = re.search(r"(https?://\S+|/\S+)", text)
        return end(con, art.group(1) if art else None)
    if re.search(r"\b(report|this week|aligned)\b", t):
        return report(con)
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


if __name__ == "__main__":
    main()
