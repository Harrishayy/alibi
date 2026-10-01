"""The long-running process. Owns timers, sampling, nudges, nightly report.

Run in tmux:  python -m alibi.daemon
"""
import time
from . import db
from .notify import notify

TICK_S = 5


def main():
    con = db.connect()
    started = time.time()
    notify("Alibi daemon up.")
    while True:
        s = db.active_session(con)
        if s and time.time() >= s["ends_at"]:
            # P0: just end. P1: replace with verifier.finalise(con, s) and notify with verdict + evidence.
            db.finish_session(con, s["id"])
            notify(f"Time's up on {s['habit']} — let's see what you did.")
        # TODO (P1): if s and modality in (physical, hybrid): camera.maybe_sample(con, s)
        # TODO (P2): nudges.check(con, s)
        # TODO (P4): if it's REPORT_HOUR and report not sent today: notify(report.build())
        time.sleep(TICK_S)


if __name__ == "__main__":
    main()
