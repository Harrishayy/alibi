"""P10 DoD: reel from the P1 fixture session -> H.264 mp4 with duration.  P11 DoD: correct samples -> verdict moves."""
import os, subprocess
os.environ["SAMPLE_EVERY_S"] = "15"
from harness import Clock, check
import make_fixtures
os.environ["CAMERA_SOURCE"] = str(make_fixtures.video("desk_4min.mp4", [("on_task", 120), ("phone", 60), ("absent", 60)]))
from fastapi.testclient import TestClient
from alibi import api, cli, daemon, db

con = db.connect()
clock = Clock()
cli.start(con, "draw for 4 minutes")
sid = db.active_session(con)["id"]
for _ in range(49):
    daemon.tick(con); clock.advance(5)
c = TestClient(api.app)
url = c.get(f"/api/reel?session={sid}").json()["url"]
path = os.environ["ALIBI_DATA_DIR"] + url.split("?")[0].removeprefix("/files")
probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name:format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True).stdout.split()
print("    reel:", url, probe)
check(probe and probe[0] == "h264", "H.264 (plays in every browser)")
check(float(probe[-1]) > 3, "duration > 3 s")
check(c.get(url).status_code == 200, "served over HTTP")
check(c.get("/api/sessions").json()[0]["reel_url"] == url, "session JSON links the reel")

before = c.get("/api/sessions").json()[0]
phone = [l for l in before["labels"] if l["label"] in ("phone", "absent")]
for l in phone[:6]:
    r = c.post(f"/api/sessions/{sid}/correct", json={"ts": l["ts"], "label": "on_task"}).json()["reply"]
after = c.get("/api/sessions").json()[0]
print(f"    {before['verdict']} {before['on_task_ratio']:.0%}  ->  {after['verdict']} {after['on_task_ratio']:.0%}   ({r})")
check(before["verdict"] == "partial" and after["verdict"] == "done", "verdict moved partial -> done")
check(sum(bool(l["corrected_from"]) for l in after["labels"]) == 6, "corrections visible on the labels")
check(after["ended_at"] == before["ended_at"], "re-score kept the original end time")
check(c.post(f"/api/sessions/{sid}/correct", json={"ts": 1, "label": "nap"}).status_code == 400, "bad label rejected")
print("P10 + P11 DoD passed.")
