"""F1-F10: digital nudges, breaks/extend, pace reminder, activity feed, streak + score, corrections that stick,
escalation, verdict voice, Strava claims + add habit, day recap."""
import datetime as dt, os
os.environ["SAMPLE_EVERY_S"] = "15"
os.environ["LAPTOP_EVERY_S"] = "15"
os.environ["PACE_HOURS"] = "11"
from harness import Clock, check
import make_fixtures
os.environ["CAMERA_SOURCE"] = str(make_fixtures.video("desk_feat.mp4", [("on_task", 60), ("phone", 340)]))
from fastapi.testclient import TestClient
from alibi import api, cli, config, daemon, db, laptop_logger, notify, report, verifier

con = db.connect()
clock = Clock()
clock.t = dt.datetime.fromtimestamp(clock.t).replace(hour=9, minute=0).timestamp()
c = TestClient(api.app)
yt = {"app": "Google Chrome", "title": "YouTube", "url": "https://youtube.com"}
code = {"app": "Visual Studio Code", "title": "main.cpp — learncpp", "url": ""}

# F1 + F7 + F8: digital session drifts -> window nudge, live on-task score, second nudge = strike, voice says C++
laptop_logger.frontmost = lambda: code
print(" ", cli.say(con, "learn c++ for 10 minutes"))
for _ in range(6):
    daemon.tick(con); clock.advance(5)
laptop_logger.frontmost = lambda: yt
nudges = []
for _ in range(60):                                    # 5 min of YouTube
    daemon.tick(con); clock.advance(5)
    for a in notify.recent_alerts(5):
        if a["kind"] == "nudge" and a["id"] not in [n["id"] for n in nudges]:
            nudges.append(a)
st = c.get("/api/state").json()["session"]
check(nudges and "Your screen has been YouTube" in nudges[0]["text"], "digital nudge: " + (nudges[0]["text"] if nudges else "none"))
check(st["on_task_so_far"] is not None and st["on_task_so_far"] < 0.5, f"live on-task score for digital: {st['on_task_so_far']:.0%}")
check(len(nudges) >= 2 and "Second time" in nudges[1]["text"], "second nudge escalates: " + (nudges[1]["text"] if len(nudges) > 1 else "none"))
check(st["strikes"] >= 1 and st["drifting"] and st["drifting"]["label_text"] == "YouTube", f"state shows strikes + drifting {st['drifting']}")
check(st["last_seen"]["source"] == "screen" and "YouTube" in st["last_seen"]["text"], "last_seen: " + st["last_seen"]["text"])
check(nudges[0]["actions"][0]["say"] == "back", "nudge alert carries actions for the island")
v = cli.end(con)
check(v.startswith("C++: slacked. The screen was YouTube"), "verdict voice: " + v)
sid_cpp = db.get_session(con, con.execute("SELECT max(id) FROM sessions").fetchone()[0])["id"]

# F6b: re-label a window title -> persists for the next session
r = c.post(f"/api/sessions/{sid_cpp}/correct", json={"title": "Google Chrome — YouTube", "label": "on_task"}).json()
check("from now on" in r["reply"] and r["session"]["verdict"] != "slacked", "title correction re-scores: " + r["reply"])
check(verifier.classify_titles(con, "cpp", {"Google Chrome — YouTube"})["Google Chrome — YouTube"] == "on_task",
      "title_cache learned it")
con.execute("UPDATE title_cache SET label='off_task' WHERE habit='cpp' AND title='Google Chrome — YouTube'"); con.commit()

# F2: break / extend / change / fallback, breaks excluded from evidence
laptop_logger.frontmost = lambda: code
print(" ", cli.say(con, "draw for 4 minutes"))
s = db.active_session(con)
ends0 = s["ends_at"]
check("Still watching" in cli.say(con, "add 2"), "add 2 extends")
check(db.get_session(con, s["id"])["ends_at"] == ends0 + 120, "ends_at moved by 2 min")
check("Say \"end\"" in cli.say(con, "what should I do next"), "unparsed text while live -> status + hint")
r1 = cli.say(con, "break 5")
for _ in range(6):
    daemon.tick(con); clock.advance(5)
check(not [e for e in db.session_events(con, s["id"], "camera") if e["ts"] > clock.t - 30], "no samples during the break")
check(c.get("/api/state").json()["session"]["on_break"] is not None, "state shows on_break")
check("Back" in cli.say(con, "back"), "back resumes")
r2 = cli.say(con, "break 2")
check("Second break. Noted on the record." in r2, f"second break is on the record: {r2}")
cli.say(con, "back")
check(cli.say(con, "change to 3").endswith("now 3 min."), "change to 3")
cli.end(con)

# F4: activity feed
f = c.get("/api/feed?limit=30&session=%d" % s["id"]).json()["items"]
srcs = {x["source"] for x in f}
check({"you", "alibi"} <= srcs and all({"ts", "source", "label", "text", "thumb"} <= set(x) for x in f),
      f"feed has humanised sources {sorted(srcs)}")
check(f == sorted(f, key=lambda x: -x["ts"]), "feed newest first")

# F6a: the same correction twice -> the witness applies it next time
cli.say(con, "draw for 3 minutes")
s6 = db.active_session(con)
for _ in range(38):
    daemon.tick(con); clock.advance(5)
done = c.get("/api/sessions").json()[0]
ph = [l for l in done["labels"] if l["label"] == "phone"][:2]
for l in ph:
    c.post(f"/api/sessions/{s6['id']}/correct", json={"ts": l["ts"], "label": "on_task"})
cli.say(con, "draw for 3 minutes")
s7 = db.active_session(con)
clock.advance(0)
from alibi import camera
camera._last.clear()
clock.t = s7["started_at"] + 120                      # the fixture shows the phone now
camera.maybe_sample(con, s7)
e = db.session_events(con, s7["id"], "camera")[-1]["payload"]
check(e["label"] == "on_task" and e.get("learned_from") == "phone", f"witness learned the correction: {e['note']}")
from alibi import witness
check("corrected" in witness.prompt_for("drawing", {}), "VLM prompt carries the corrections as few-shot")
cli.end(con)

# F5: streak + alibi score
r = report.build_json()
row = next(x for x in r["rows"] if x["habit"] == "drawing")
check(row["streak_days"] >= 1 and row["streak_today"], f"drawing streak {row['streak_days']} day(s)")
check(0 < r["alibi_score"] <= 1 and r["headline"].startswith("This week:"), f"alibi_score {r['alibi_score']:.0%}; {r['headline']}")
check(sum(x["severity"] == "worst" for x in r["rows"]) <= 1 and {"rank", "label", "gap_to_pace_min"} <= set(row), "rows ranked")
check(any(x["strikes"] for x in r["rows"]), "strikes reach the report")

# F3: pace reminder at 11:00, 'yes' starts it
clock.t = dt.datetime.fromtimestamp(clock.t).replace(hour=11, minute=2).timestamp()
daemon.tick(con); daemon.tick(con)
pace = [a for a in notify.recent_alerts(50) if a["kind"] == "pace"]
check(len(pace) == 1 and "behind pace" in pace[0]["text"], "one pace reminder per slot: " + (pace[0]["text"] if pace else ""))
r = cli.say(con, "yes")
check("Session" in r and pace[0]["habit"] in db.active_session(con)["habit"], f"'yes' starts it: {r}")
cli.end(con)
check("Today:" in report.build_json()["summary"] or "Today" in report._dry(report.build_json()), "summary says Today before 18:00")

# F9: run claims + add habit
r = cli.say(con, "go for a run")
check("Strava" in r and "5 km" in r, r)
db.add_event(con, "strava", "activity", {"id": 1, "name": "Run", "distance_km": 5.4, "start_date": clock.t}, ts=clock.t + 60)
check(daemon.check_claims(con) == ["Run verified: 5.4 km."], "claim verified by Strava")
r = cli.say(con, "read for 20 min")
check(r.startswith("Not a habit yet"), r)
r = cli.say(con, "add habit reading, physical, 20 min")
check("Added Reading" in r and "reading" in config.habits()["habits"], r)
check("Reading for 20" in cli.say(con, "reading for 20"), "new habit starts")
cli.end(con)

# F10: day recap builds the reel
daemon.join_reels()
text = daemon.recap(con, dt.date.fromtimestamp(clock.t).isoformat())
a = notify.recent_alerts()[-1]
check(a["kind"] == "recap" and "reel is ready" in text and a["reel"], "recap: " + text)
check(c.get("/api/state").json()["alert"]["reel_url"].startswith("/files/reels/day-"), "state exposes recap reel_url")
print("Features DoD passed.")
