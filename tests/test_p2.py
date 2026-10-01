"""P2 DoD: declare from the chat surface (API); pick up the phone at the desk; within ~3 samples a nudge fires."""
import os
os.environ["SAMPLE_EVERY_S"] = "60"
from harness import Clock, check
import make_fixtures
os.environ["CAMERA_SOURCE"] = str(make_fixtures.video("desk_nudge.mp4", [("on_task", 120), ("phone", 300)]))
from fastapi.testclient import TestClient
from alibi import api, daemon, db, notify

con = db.connect()
clock = Clock()
c = TestClient(api.app)
r = c.post("/api/say", json={"text": "draw for 10 minutes"}).json()["reply"]
print("  island ->", r)
check("drawing" in r.lower(), "declared via the island/chat API")
st = c.get("/api/state").json()
check(st["session"]["habit"] == "drawing" and st["session"]["left_s"] > 590, "state shows live session")
check(c.get("/").status_code == 200, "dashboard served at /")
nudged_at = None
for i in range(0, 61):
    daemon.tick(con); clock.advance(5)
    if nudged_at is None and any(a["kind"] == "nudge" for a in notify.recent_alerts()):
        nudged_at = i * 5
check(nudged_at is not None, f"nudge fired at t={nudged_at}s (phone from t=120s)")
check(nudged_at <= 120 + 3 * 60, "within ~3 min of picking up the phone")
print("  nudge:", [a["text"] for a in notify.recent_alerts() if a["kind"] == "nudge"][0])
check(sum(a["kind"] == "nudge" for a in notify.recent_alerts()) == 1, "only one nudge inside the cooldown")
check(c.get("/api/state").json()["alert"]["kind"] in ("nudge", "info"), "alert exposed to the island")
r = c.post("/api/say", json={"text": "how am I doing"}).json()["reply"]
check("left" in r, f"status via chat: {r}")
r = c.post("/api/end", json={}).json()["reply"]
check("Drawing:" in r and c.get("/api/state").json()["alert"]["kind"] == "verdict", f"end via island -> verdict alert")
sessions = c.get("/api/sessions").json()
check(sessions and sessions[0]["evidence_url"] and c.get(sessions[0]["evidence_url"]).status_code == 200,
      "contact sheet served over HTTP")
print("P2 DoD passed.")
