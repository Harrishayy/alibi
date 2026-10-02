"""Plan overview DoD: GET /api/plan/overview — one row per habit, planned blocks inside the week with outcomes, sessions, pace
v2 status, and milestones from goals.json (past due and not done = off_track). Fake clock, seeded week."""
import datetime as dt, json
from harness import Clock, check
import yaml
from fastapi.testclient import TestClient
from alibi import api, config, db

MON = dt.datetime(2026, 10, 5)                                  # a Monday


def at(day: int, h: int, m: int = 0) -> float:
    return (MON + dt.timedelta(days=day, hours=h, minutes=m)).timestamp()


yaml.safe_dump({"habits": {
    "drawing": {"modality": "physical", "default_min": 30, "weekly_target_min": 210,
                "schedule": [{"days": list(config.DAYS), "at": "10:00", "min": 30}]},
    "cpp": {"modality": "digital", "default_min": 30, "weekly_target_min": 180},
    "running": {"source": "strava", "weekly_sessions": 3, "min_km": 5}},
    "verdict": {"done": 0.7, "partial": 0.4}}, open(config.HABITS_PATH, "w"))
con = db.connect()


def sess(habit, start, minutes, ratio, verdict, modality="physical"):
    con.execute("INSERT INTO sessions(habit,modality,declared_min,started_at,ends_at,ended_at,status,on_task_ratio,"
                "verdict) VALUES (?,?,?,?,?,?,'done',?,?)",
                (habit, modality, minutes, start, start + minutes * 60, start + minutes * 60, ratio, verdict))
    con.commit()


sess("drawing", at(0, 10), 30, 0.9, "done")                    # Mon block: done
sess("drawing", at(2, 10, 5), 30, 0.5, "partial")              # Wed block: partial; Tue has nothing -> missed
sess("cpp", at(1, 20), 45, 0.8, "done")
clock = Clock()
clock.t = at(3, 15)                                             # Thursday 15:00
c = TestClient(api.app)

r = c.get("/api/plan/overview", params={"week": "2026-10-07"})
check(r.status_code == 200, f"overview answers ({r.status_code})")
o = r.json()
check(o["milestones"] == [], "no goals.json -> milestones []")
check(o["week_start"] == at(0, 0), "any date in the week maps to its Monday")
check(sorted(x["habit"] for x in o["rows"]) == ["cpp", "drawing", "running"], "one row per habit")
d = next(x for x in o["rows"] if x["habit"] == "drawing")
check(len(d["blocks"]) == 7 and all(at(0, 0) <= b["start"] and b["end"] <= at(7, 0) for b in d["blocks"]),
      "seven drawing blocks, all inside the week")
st = [b["state"] for b in d["blocks"]]
check(st[:4] == ["done", "missed", "partial", "missed"] and set(st[4:]) == {"planned"},
      f"block states: done, missed, partial, missed (Thu 10:00 passed), then planned ({st})")
check([s["verdict"] for s in d["sessions"]] == ["done", "partial"] and d["verified_min"] == 42,
      f"sessions listed, verified = 27 + 15 ({d['verified_min']})")
check(d["status3"] in ("on_track", "at_risk", "off_track") and d["need_per_day_min"] >= 0
      and isinstance(d["buffer_days"], (int, float)), f"pace v2 fields present ({d['status3']}, {d['reason']!r})")
cp = next(x for x in o["rows"] if x["habit"] == "cpp")
check(cp["blocks"] == [] and cp["verified_min"] == 36 and cp["target_min"] == 180, "unscheduled habit: no blocks")

(config.DATA_DIR / "goals.json").write_text(json.dumps({"milestones": [
    {"key": "submit", "label": "Submit Claw challenge", "due": "2026-10-02", "done_at": None},
    {"key": "demo", "label": "Record the demo", "due": "2026-10-09", "done_at": None},
    {"key": "booth", "label": "Booth", "due": "2026-10-14", "done_at": None},
    {"key": "repo", "label": "Clean the repo", "due": "2026-10-01", "done_at": "2026-10-01T18:00"}]}))
ms = {m["key"]: m["status"] for m in c.get("/api/plan/overview").json()["milestones"]}
check(ms == {"submit": "off_track", "demo": "at_risk", "booth": "pending", "repo": "done"},
      f"milestones: past due -> off_track, ≤1 day -> at_risk, later -> pending, done_at -> done ({ms})")
check(c.get("/api/plan/overview", params={"week": "nope"}).status_code == 400, "a bad week is a 400")
print("Plan overview DoD passed.")
