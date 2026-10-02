"""Desk witness DoD: 4-min drawing session: draw 2 min, phone 1 min, leave 1 min -> ~50% partial + contact sheet."""
import os, pathlib
os.environ["SAMPLE_EVERY_S"] = "15"
from harness import Clock, check
import make_fixtures
os.environ["CAMERA_SOURCE"] = str(make_fixtures.video("desk_4min.mp4", [("on_task", 120), ("phone", 60), ("absent", 60)]))
from alibi import cli, daemon, db, notify

con = db.connect()
clock = Clock()
print(" ", cli.start(con, "draw for 4 minutes"))
sid = db.active_session(con)["id"]
for _ in range(49):
    daemon.tick(con); clock.advance(5)
s = con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
ev = db.session_events(con, sid, "camera")
print("  labels:", " ".join(e["payload"]["label"][:2] for e in ev))
print("  reused by motion gate:", sum(e["payload"]["reused"] for e in ev), "of", len(ev))
check(s["status"] == "done", "session closed by the timer")
check(s["verdict"] == "partial", f"verdict partial (got {s['verdict']})")
check(0.4 <= s["on_task_ratio"] <= 0.6, f"ratio ≈ 50% (got {s['on_task_ratio']:.0%})")
check({e["payload"]["label"] for e in ev} == {"on_task", "phone", "absent"}, "saw on_task, phone, absent")
check(any(e["payload"]["reused"] for e in ev), "motion gate skipped some model calls")
check(s["evidence_path"] and pathlib.Path(s["evidence_path"]).exists(), f"contact sheet at {s['evidence_path']}")
a = notify.recent_alerts()[-1]
check(a["kind"] == "verdict" and a["verdict"] == "partial" and "partial" in a["text"] and a["session_id"] == sid,
      "verdict notified in the witness's voice, with structured fields: " + a["text"])
print("Desk witness DoD passed.")
