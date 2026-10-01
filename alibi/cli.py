"""Front door. OpenClaw / Telegram call these four commands.

  python -m alibi.cli start "draw for 1 hour"
  python -m alibi.cli status
  python -m alibi.cli end [--artefact URL_OR_PATH]
  python -m alibi.cli report
"""
import argparse, time
from . import db, intent


def main():
    p = argparse.ArgumentParser(prog="alibi")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.add_argument("text")
    sub.add_parser("status")
    e = sub.add_parser("end"); e.add_argument("--artefact")
    sub.add_parser("report")
    a = p.parse_args()
    con = db.connect()

    if a.cmd == "start":
        if db.active_session(con):
            print("A session is already running. End it first."); return
        it = intent.parse(a.text)
        sid = db.create_session(con, it["habit"], it["modality"], it["minutes"])
        print(f"Session {sid}: {it['habit']} ({it['modality']}) for {it['minutes']} min. Watching.")
    elif a.cmd == "status":
        s = db.active_session(con)
        print("No active session." if not s else
              f"{s['habit']} — {max(0, int((s['ends_at'] - time.time()) / 60))} min left")
    elif a.cmd == "end":
        # TODO (P1): call verifier.finalise(con, s, artefact=a.artefact) instead of a bare finish.
        s = db.active_session(con)
        if not s: print("No active session."); return
        db.finish_session(con, s["id"], artefact=a.artefact)
        print(f"Ended session {s['id']}.")
    elif a.cmd == "report":
        from . import report  # P4
        print(report.build())


if __name__ == "__main__":
    main()
