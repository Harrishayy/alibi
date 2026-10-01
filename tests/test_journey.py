"""Journey fixes: Cancel/Undo for a just-started session, pace counted from when a habit was added, and
'Run the welcome tour again' that reopens the wizard without wiping habits."""
import os, json, time, datetime as dt
from harness import Clock, check, ROOT
os.environ["CAMERA_SOURCE"] = str(ROOT / "tests" / "fixtures" / "desk_4min.mp4")
os.environ["ALIBI_CALENDAR_BIN"] = ""
from fastapi.testclient import TestClient
from alibi import api, cli, config, db, health, onboarding, report

con = db.connect()
c = TestClient(api.app)
clock = Clock()

# --- Cancel: a mis-tap leaves no trace ------------------------------------------------------------------------
before = report.build_json()
r = c.post("/api/habits/add", json={"name": "Piano", "minutes": 20, "check": "camera", "start": True}).json()
check(r["reply"].startswith("Started Piano"), f"add + start: {r['reply']}")
clock.advance(10)
out = cli.say(con, "end")
check(out.startswith("Cancelled Piano") and "doesn't count" in out, f"'end' 10 s in cancels: {out}")
check(con.execute("SELECT count(*) FROM sessions WHERE habit='piano'").fetchone()[0] == 0, "no session row left")
after = report.build_json()
check(after["alibi_score"] == before["alibi_score"], f"honesty untouched: {before['alibi_score']} -> {after['alibi_score']}")
check("piano" in config.habits()["habits"], "the habit itself stays after a plain cancel")

# Undo from the toast: cancels and removes the habit added a moment ago
r = c.post("/api/habits/add", json={"name": "Harp", "minutes": 20, "check": "camera", "start": True}).json()
clock.advance(3)
u = c.post("/api/session/cancel", json={"undo": True, "remove_habit": r["key"]}).json()
check(u["cancelled"] and u["removed"] == r["key"] and r["key"] not in config.habits()["habits"],
      f"Undo cancels + removes the new habit: {u['reply']} {u.get('reply_extra')}")

# After the window, cancel refuses and end judges as before
cli.start(con, "draw for 25")
clock.advance(120)
out = cli.say(con, "cancel")
check("too long to cancel" in out and db.active_session(con), f"cancel after 2 min refused: {out}")
out = cli.end(con)
check(not out.startswith("Cancelled"), f"end after 2 min still judges: {out[:60]}")
check(cli.say(con, "cancel") == "Nothing to cancel.", "cancel with nothing live")

# --- Pace from created_at -------------------------------------------------------------------------------------
now = time.time()
hs = config.habits()["habits"]
today = config.DAYS[dt.date.fromtimestamp(now).weekday()]
hs["fresh"] = {"modality": "digital", "default_min": 30, "weekly_target_min": 150, "aliases": ["fresh"],
               "on_task_looks_like": "editor", "schedule": [{"days": list(config.DAYS), "at": "00:01", "min": 30}],
               "created_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(now - 600))}
health.save_habits(hs)
rj = report.build_json(now)
row = next(x for x in rj["rows"] if x["habit"] == "fresh")
check(row["is_new"] and row["behind_by_min"] == 0 and row["status"] == "aligned",
      f"habit added 10 min ago is never behind: {row['behind_by_min']} {row['status']}")
check(row["target_min"] <= 150 and row["weekly_target_min"] == 150, f"target prorated: {row['target_min']} of 150")
pc = report._pace(dict(hs["fresh"], created_at=time.strftime("%Y-%m-%d %H:%M", time.localtime(now - 2 * 86400))),
                  report.week_start(now), now)
check(not pc["new"] and pc["pace"] <= pc["target"], f"older habit: pace {pc['pace']:.0f} within target {pc['target']}")
check(row["today_planned_min"] == 30, f"today's plan known: {row['today_planned_min']}")

# --- Welcome tour again keeps habits ----------------------------------------------------------------------------
keys = set(config.habits()["habits"])
c.post("/api/onboarding/reset")
st = c.get("/api/onboarding").json()
check(st["needs_onboarding"] and st["replay"], "tour again: wizard opens on an install with history")
res = c.post("/api/onboarding/habits", json={"picks": [{"template": "drawing", "schedule": [
    {"days": ["mon"], "at": "09:00", "min": 20}]}, {"template": "sleep"}], "replace": False}).json()
now_keys = set(config.habits()["habits"])
check(keys <= now_keys and config.habits()["habits"]["drawing"]["schedule"][0]["at"] == "09:00",
      f"replay keeps every habit and updates drawing's plan; added {sorted(now_keys - keys)}")
c.post("/api/onboarding/done")
check(not c.get("/api/onboarding").json()["needs_onboarding"], "done ends the replay")
print("Journey DoD passed.")
