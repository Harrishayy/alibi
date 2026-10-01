"""R1-R10: the alibi can't be faked, races don't double-count, bad input never 500s, the data dir isn't public."""
import os, threading, time as _time
os.environ["SAMPLE_EVERY_S"] = "15"
from harness import Clock, check
import make_fixtures
os.environ["CAMERA_SOURCE"] = str(make_fixtures.video("desk_4min.mp4", [("on_task", 120), ("phone", 60), ("absent", 60)]))
from fastapi.testclient import TestClient
from alibi import api, cli, config, daemon, db, intent, nudges, notify, report, verifier

con = db.connect()
c = TestClient(api.app)

# R2: parallel starts -> exactly one active session
replies = []
def go():
    replies.append(cli.start(db.connect(), "draw for 3 minutes"))
ts = [threading.Thread(target=go) for _ in range(6)]
[t.start() for t in ts]; [t.join() for t in ts]
n_active = con.execute("SELECT count(*) FROM sessions WHERE status='active'").fetchone()[0]
check(n_active == 1, f"6 parallel starts -> 1 active session (replies: {sum('Session' in r for r in replies)} started)")

# R3: racing ends -> one verdict alert, one close (past the "only just started -> Cancel" window)
_cw, cli.CANCEL_WINDOW_S = getattr(cli, "CANCEL_WINDOW_S", 0), 0
sid = db.active_session(con)["id"]
before = sum(a["kind"] == "verdict" for a in notify.recent_alerts(500))
outs = []
ts = [threading.Thread(target=lambda: outs.append(cli.end(db.connect()))) for _ in range(4)]
[t.start() for t in ts]; [t.join() for t in ts]
daemon.join_reels()
after = sum(a["kind"] == "verdict" for a in notify.recent_alerts(500))
check(after - before == 1, f"4 racing ends -> exactly 1 verdict alert (got {after - before})")
check(db.get_session(con, sid)["status"] == "done", "session closed once")

clock = Clock()
# R1: ending a long claim after one sample is not a done verdict and doesn't credit the declared minutes
r = cli.say(con, "draw for 200 minutes")
check("Started" in r, r)
daemon.tick(con); clock.advance(10); daemon.tick(con)
v = cli.say(con, "done")
s = con.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
check(s["verdict"] == "slacked" and s["on_task_ratio"] < 0.01, f"10 s of a 200-min claim -> slacked ({v})")
row = next(x for x in report.build_json()["rows"] if x["habit"] == "drawing")
check(row["verified_min"] < 5, f"report verified ≈ elapsed, not declared (verified {row['verified_min']} of {row['declared_min']})")
check("Ended after 0 min of 200" in v, "verdict says it ended early: " + v)
cli.CANCEL_WINDOW_S = _cw          # (R1 above is about judging; a 10 s 'end' is a Cancel in normal use — test_journey)
st = c.get(f"/api/sessions").json()[0]
check(st["coverage"] < 0.01 and "only 0 of 200 min happened" in st["why"], "session JSON explains coverage: " + st["why"])

# R7 / R6: durations
for text, want in [("draw for 25", 25), ("draw for an hour and a half", 90), ("sketch", 25)]:
    check(intent.parse(text)["minutes"] == want, f"{text!r} -> {want} min")
for text in ("draw for 0 minutes", "draw for 600 minutes", "draw for 99999999999999999999 minutes"):
    r = c.post("/api/say", json={"text": text})
    check(r.status_code == 200 and db.active_session(con) is None, f"{text!r} -> friendly no: {r.json()['reply']}")
r = cli.say(con, "finish the sketch for 20 min")
check("Started" in r and "20 min" in r, f"'finish the sketch for 20 min' starts drawing: {r}")
cli.end(con)
r = cli.say(con, "write the report for 30 min")
check("habit" in r.lower() and "verified" not in r.lower(), f"'write the report for 30 min' isn't the weekly report: {r}")

# R6: bad input -> 4xx JSON, never 500
check(c.get("/api/reel?date=yesterday").status_code == 400, "reel bad date -> 400")
check(c.post("/api/sessions/9999/correct", json={"ts": 1, "label": "on_task"}).status_code == 404, "correct unknown session -> 404")
check(c.post(f"/api/sessions/{sid}/correct", json={"ts": 1, "label": "on_task"}).status_code == 400, "correct bogus ts -> 400")
habits = c.get("/api/habits").json()["habits"]
check(c.put("/api/habits", json={"habits": {"x": "oops"}}).status_code == 400, "habit as string -> 400")
check(c.put("/api/habits", json={"habits": {"x": {"modality": "physical", "weekly_target_min": "lots"}}}).status_code == 400,
      "garbage number -> 400")
check(c.put("/api/habits", json={"habits": habits}).status_code == 200, "habits restored")

# R4: laptop asleep through the bell
cli.start(con, "draw for 4 minutes")
s4 = db.active_session(con)
for _ in range(4):
    daemon.tick(con); clock.advance(15)
n_before = len(db.session_events(con, s4["id"], "camera"))
clock.advance(2 * 3600)
daemon.tick(con)
s4b = db.get_session(con, s4["id"])
check(s4b["status"] == "done" and abs(s4b["ended_at"] - s4b["ends_at"]) < 1, "slept through bell -> ended_at = ends_at")
check(len(db.session_events(con, s4["id"], "camera")) == n_before, "no post-wake camera sample")
away = [a for a in notify.recent_alerts() if a.get("kind") != "report"]   # run near 20:00, the jump crosses 22:00
check(away[-1].get("missed") and "While you were away" in away[-1]["text"], away[-1]["text"])

# R5: a correction drops the stale reel; it's rebuilt with ?v= cache-buster
daemon.join_reels()
reel = config.DATA_DIR / "reels" / f"session-{s4['id']}.mp4"
check(reel.exists(), "reel built after the bell")
lab = c.get("/api/sessions").json()[0]["labels"][0]
out = c.post(f"/api/sessions/{s4['id']}/correct", json={"ts": lab["ts"], "label": "phone"})
check(out.status_code == 200 and "New score" in out.json()["reply"], out.json()["reply"])
daemon.join_reels()
check(reel.exists() and "?v=" in c.get("/api/sessions").json()[0]["reel_url"], "reel rebuilt, URL cache-busted")

# R8: nudge cooldown survives a restart (durable), and only fresh samples count
os.environ["CAMERA_SOURCE"] = str(make_fixtures.video("desk_phone.mp4", [("phone", 400)]))
config.CAMERA_SOURCE = os.environ["CAMERA_SOURCE"]
from alibi import camera
camera.release()
cli.start(con, "draw for 6 minutes")
s8 = db.active_session(con)
nudged = 0
for _ in range(14):
    daemon.tick(con); clock.advance(5)
first = len(nudges.nudges_for(con, s8["id"]))
import importlib
importlib.reload(nudges)          # "restart": no in-memory state survives
check(first == 1 and nudges.check(con, db.active_session(con)) is None, "restart doesn't repeat the nudge")
cli.end(con)

# R9: island health from heartbeat
c.get("/api/state", headers={"X-Alibi-Client": "island"})
isl = next(x for x in c.get("/api/health").json()["checks"] if x["key"] == "island")
check(isl["ok"] and "last seen" in isl["details"], "island health from heartbeat: " + isl["details"])

# R10: data dir not public; Host check
check(c.get("/files/alibi.db").status_code == 404 and c.get("/files/alerts.jsonl").status_code == 404,
      "alibi.db and alerts.jsonl not served")
check(c.get("/api/state", headers={"host": "evil.example"}).status_code == 400, "foreign Host header rejected")
print("Robustness DoD passed.")
