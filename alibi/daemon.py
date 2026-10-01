"""The long-running process. Owns timers, sampling, nudges, nightly report.

Run:  python -m alibi.daemon
"""
import time
from . import camera, db, verifier
from .notify import notify

TICK_S = 5


def tick(con) -> None:
    """One pass of everything time-based. Tests call this directly with a fake clock."""
    s = db.active_session(con)
    if s and s["modality"] in ("physical", "hybrid"):
        camera.maybe_sample(con, s, force=time.time() >= s["ends_at"])   # always one last look at the bell
    if s and time.time() >= s["ends_at"]:
        line = verifier.finalise(con, s)
        done = con.execute("SELECT evidence_path FROM sessions WHERE id=?", (s["id"],)).fetchone()
        notify(f"Time's up. {line}", image_path=done["evidence_path"], kind="verdict")


def main():
    con = db.connect()
    notify("Alibi daemon up.")
    while True:
        try:
            tick(con)
        except Exception as e:                      # a long-running agent must not die on one bad tick
            print(f"[alibi] tick error: {e!r}", flush=True)
        time.sleep(TICK_S)


if __name__ == "__main__":
    main()
