"""The long-running process. Owns timers, sampling, nudges, nightly report, and serves the local API.

Run:  python -m alibi.daemon            (then open http://127.0.0.1:8765 or launch the island)
"""
import datetime as dt, time
from . import camera, config, db, nudges, verifier
from .notify import notify

TICK_S = 5
_report_sent_on = None


def tick(con) -> None:
    """One pass of everything time-based. Tests call this directly with a fake clock."""
    global _report_sent_on
    s = db.active_session(con)
    if s and s["modality"] in ("physical", "hybrid"):
        camera.maybe_sample(con, s, force=time.time() >= s["ends_at"])   # always one last look at the bell
    if s and time.time() < s["ends_at"]:
        nudges.check(con, s)
    if s and time.time() >= s["ends_at"]:
        line = verifier.finalise(con, s)
        done = con.execute("SELECT evidence_path FROM sessions WHERE id=?", (s["id"],)).fetchone()
        notify(f"Time's up. {line}", image_path=done["evidence_path"], kind="verdict")
    today = dt.date.fromtimestamp(time.time())
    if dt.datetime.fromtimestamp(time.time()).hour == config.REPORT_HOUR and _report_sent_on != today:
        from . import report
        _report_sent_on = today
        notify(report.build_json()["summary"], kind="report")


def main():
    from . import api
    con = db.connect()
    api.serve_in_thread()
    notify(f"Alibi daemon up — witness: {config.VISION_BACKEND}, "
           f"dashboard: http://{config.API_HOST}:{config.API_PORT}")
    while True:
        try:
            tick(con)
        except Exception as e:                      # a long-running agent must not die on one bad tick
            print(f"[alibi] tick error: {e!r}", flush=True)
        time.sleep(TICK_S)


if __name__ == "__main__":
    main()
