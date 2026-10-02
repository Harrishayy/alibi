"""Work done off the plan still counts on Today. An unplanned "draw for 5" after the
day's blocks were missed, and a verified run claim, are kept items: the phrase never says "Today slipped." after a Done
verdict, every surface's "kept of total" agrees, and an off-plan session never ends the plan (no plan_done)."""
import datetime as dt, os, time
os.environ.update(ALIBI_BRIEF_ALERTS="all", REPORT_HOUR="22", CHECK_HOURS="12,16,20", MORNING_AT="07:30")
from harness import Clock, check
from fastapi.testclient import TestClient
from alibi import api, cli, config, db, health, notify

con = db.connect()
c = TestClient(api.app)
clock = Clock()
day = dt.date.fromtimestamp(time.time())
at = lambda h, m=0, s=0: dt.datetime.combine(day, dt.time(h, m, s)).timestamp()
DAY = config.DAYS[day.weekday()]
clock.t = at(12)
hs = config.habits()["habits"]
hs["math"]["schedule"] = [{"days": [DAY], "at": "09:00", "min": 30}]
hs["drawing"]["schedule"] = [{"days": [DAY], "at": "10:00", "min": 25}]
health.save_habits(hs)
st = c.get("/api/state").json()
check(st["plan_today"]["kept"] == 0 and st["plan_today"]["total"] == 2 and st["phrase"]["situation"] == "none_kept",
      f"before: both blocks missed, none kept ({st['phrase']['text']!r})")

# an unplanned drawing session at 12:05, long after drawing's 10:00 block
clock.t = at(12, 5)
cli.start(con, "draw for 5 minutes")
sid = db.active_session(con)["id"]
for i in range(5):
    db.add_event(con, "camera", "label", {"label": "on_task", "note": "pen on paper"}, session_id=sid,
                 ts=at(12, 5, 30) + i * 60)
clock.t = at(12, 11)
cli.end(con)
v = [a for a in notify.recent_alerts(50) if a.get("kind") == "verdict"][-1]
check(v["verdict"] == "done" and v["session_id"] == sid, "the off-plan session ends done")
st = c.get("/api/state").json()
pt, ph, pn = st["plan_today"], st["phrase"], st["pinch"]
off = [x for x in pt["done"] if x.get("unplanned")]
check(len(off) == 1 and off[0]["session_id"] == sid and off[0]["habit"] == "drawing" and off[0]["at"] == "12:05"
      and off[0]["status"] == "done" and off[0]["verdict"] == "done", "the session is a kept item, marked unplanned")
check(pt["kept"] == 1 and pt["total"] == 3 and pt["summary"] == "Nothing left today. 1 of 3 kept.",
      f"kept of total agrees with the verdict: {pt['summary']}")
check(ph["situation"] == "some_kept" and "slipped" not in ph["text"], f"phrase: {ph['text']!r}")
check(pn["moment"] == "verdict" and "last block" not in (pn["line"] or ""),
      f"an off-plan session never ends the plan: {pn['line']!r}")
clock.t = at(12, 20)
check(c.get("/api/state").json()["plan_today"]["kept"] == 1, "still kept once the verdict line has gone")

# a verified run claim (no running block today) counts too; an unverified one doesn't
clock.t = at(12, 30)
db.add_event(con, "user", "claim", {"habit": "running", "min_km": 5.0, "until": at(14, 30)}, ts=at(12, 30))
claim_id = con.execute("SELECT max(id) FROM events WHERE source='user' AND kind='claim'").fetchone()[0]
pt = c.get("/api/state").json()["plan_today"]
check(pt["kept"] == 1, "an open claim isn't kept yet")
db.add_event(con, "alibi", "claim_settled", {"claim_id": claim_id, "verified": True}, ts=at(13, 10))
clock.t = at(13, 11)
pt = c.get("/api/state").json()["plan_today"]
run = [x for x in pt["done"] if x["habit"] == "running"]
check(len(run) == 1 and run[0]["unplanned"] and run[0]["check"] == "strava" and pt["kept"] == 2 and pt["total"] == 4,
      f"a verified run claim is kept: {pt['summary']}")
print("Off-plan DoD passed.")
