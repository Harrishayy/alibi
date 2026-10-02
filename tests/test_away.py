"""Days off DoD. data/away.json skips a day's blocks as "Day off", keeps them out of upcoming() and the
prompts, gives the night planner no gaps there and rejects a proposal on it; GET/PUT /api/calendar/away; ALIBI_AWAY=0
changes nothing; and with no away.json, plan(), free_gaps() and the proposal check match the code from before days off
existed (read from git) exactly."""
import datetime as dt, json, os, pathlib, subprocess, types
from harness import ROOT, Clock, check
import yaml
from fastapi.testclient import TestClient
from alibi import api, calendar_sync as cal, config, db, digest, notify

cfg = config.habits()
cfg["habits"]["drawing"]["schedule"] = [{"days": list(config.DAYS), "at": "10:00", "min": 30}]
cfg["habits"]["cpp"]["schedule"] = [{"days": ["mon", "tue", "wed", "thu", "fri"], "at": "14:00", "min": 30}]
cfg["habits"]["running"]["schedule"] = [{"days": ["mon"], "at": "07:00", "min": 30}]
yaml.safe_dump(cfg, open(config.HABITS_PATH, "w"), sort_keys=False)

con = db.connect()
clock = Clock()
FRI = dt.date(2026, 10, 2)
MON, TUE = dt.date(2026, 10, 5), dt.date(2026, 10, 6)
clock.t = dt.datetime(2026, 10, 2, 20, 0).timestamp()          # Friday 20:00
cal.start(con)
c = TestClient(api.app)
AWAY = config.DATA_DIR / "away.json"
PROPOSALS = [{"habit": "drawing", "day": "2026-10-05", "at": "16:00", "minutes": 25, "why": "Behind."},
             {"habit": "drawing", "day": "tomorrow", "at": "10:00", "minutes": 25},
             {"habit": "cpp", "day": "2026-10-06", "at": "06:00", "minutes": 30},
             {"habit": "cpp", "day": "2026-10-06", "at": "18:00", "minutes": 500},
             {"habit": "running", "day": "2026-10-05", "at": "18:00", "minutes": 30},
             {"habit": "drawing", "day": "2026-10-09", "at": "18:00", "minutes": 25}]


def baseline(path: str):
    """`path` as it was before days off existed: the parent of the commit that added away_days (HEAD while that's
    uncommitted). None when there's no git history to read."""
    try:
        shas = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%H", "-S", "def away_days", "--",
                               "alibi/calendar_sync.py"], capture_output=True, text=True, check=True).stdout.split()
        rev = f"{shas[-1]}^" if shas else "HEAD"
        src = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{path}"], capture_output=True, text=True,
                             check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None, None
    mod = types.ModuleType("alibi._before_away_" + pathlib.Path(path).stem)
    mod.__package__, mod.__file__ = "alibi", str(ROOT / path)
    exec(compile(src, f"{rev}:{path}", "exec"), mod.__dict__)
    return mod, rev


old_cal, rev = baseline("alibi/calendar_sync.py")
old_dig, _ = baseline("alibi/digest.py")
if old_dig is not None:
    old_dig.calendar_sync = old_cal                                # the old planner on the old plan


def same_as_before(what: str, now: float):
    if old_cal is None or old_dig is None:
        print(f"  SKIP  {what}: no git history here to compare with")
        return
    check(old_cal is not cal and not hasattr(old_cal, "away_days"), f"baseline {rev} has no days off")
    d0 = MON - dt.timedelta(days=3)
    check(cal.plan(con, d0, 7, now) == old_cal.plan(con, d0, 7, now), f"{what}: plan() == {rev}")
    check(cal.upcoming(now) == old_cal.upcoming(now), f"{what}: upcoming() == {rev}")
    check(all(digest.free_gaps(con, d, m, now) == old_dig.free_gaps(con, d, m, now) for d in (MON, TUE) for m in (25, 90)),
          f"{what}: free_gaps() == {rev}")
    check(all(digest.validate(con, p, now) == old_dig.validate(con, p, now) for p in PROPOSALS),
          f"{what}: the proposal check == {rev}")


def infos():
    return [a for a in notify.recent_alerts(500) if a["kind"] == "info"]


def put(days):
    return c.put("/api/calendar/away", json={"days": days})


# 1. No away.json: exactly the old behaviour
check(not AWAY.exists() and cal.load_away() == [] and cal.away_days(MON, 7) == [], "no away.json, no days off")
check(c.get("/api/calendar/away").json() == {"days": []}, "GET with nothing stored")
same_as_before("no away.json", clock.t)
clock.t = dt.datetime(2026, 10, 4, 20, 0).timestamp()          # Sunday: Monday is the proposal's "tomorrow"
same_as_before("no away.json, Sunday", clock.t)
clock.t = dt.datetime(2026, 10, 2, 20, 0).timestamp()

# 2. Bad input: one sentence, a 400, nothing stored
bad = {"2026-13-01 isn't a date.": [{"date": "2026-13-01", "label": "x"}],
       "Pick a day between today and 60 days from now.": [{"date": "2026-10-01", "label": "Past"}],
       "Labels are 1–24 characters.": [{"date": "2026-10-05", "label": "x" * 25}],
       "At most 30 days off.": [{"date": (FRI + dt.timedelta(days=i)).isoformat(), "label": "Off"} for i in range(31)]}
for detail, days in bad.items():
    r = put(days)
    check(r.status_code == 400 and r.json() == {"detail": detail}, f"400: {detail}")
check(put([{"date": "2026-12-02", "label": "Too far"}]).status_code == 400, "61 days ahead is too far")
check(c.put("/api/calendar/away", json={}).status_code == 400 and not AWAY.exists(), "no list: 400, nothing stored")
check(cal.clean_away([{"date": "2026-10-07"}, {"date": "2026-10-08", "label": None}, "2026-10-09"], FRI)
      == [{"date": d, "label": "Day off"} for d in ("2026-10-07", "2026-10-08", "2026-10-09")], "no label reads Day off")

# 3. Monday off: every Monday block skipped as "Day off", one island line
r = put([{"date": "2026-10-05", "label": "Holiday"}])
check(r.status_code == 200 and r.json() == {"days": [{"date": "2026-10-05", "label": "Holiday"}], "cleared_blocks": 3},
      f"PUT stores Monday and clears its 3 blocks: {r.json()}")
check(c.get("/api/calendar/away").json() == {"days": [{"date": "2026-10-05", "label": "Holiday"}]}, "GET returns what PUT stored")
line = infos()[-1]
check(line["text"] == "Monday's a day off. I've cleared its 3 blocks." and line["actions"] == [{"label": "OK", "dismiss": True}],
      f"island line: {line['text']}")
mon = c.get("/api/calendar/plan", params={"date": "2026-10-05"}).json()["blocks"]
check(len(mon) == 3 and all(b["state"] == "skipped" and b["detail"] == "Day off" and b["away_label"] == "Holiday"
                            for b in mon), "every Monday block is skipped as Day off: " + str([b["key"] for b in mon]))
tue = cal.plan(con, TUE, 1, clock.t)
check(tue and all(b["state"] == "planned" and "away_label" not in b for b in tue), "Tuesday untouched")
up = cal.upcoming(clock.t)
check(not [b for b in up if b["date"] == "2026-10-05"] and [b for b in up if b["date"] == "2026-10-06"],
      "upcoming() leaves Monday out")
check(digest.free_gaps(con, MON, 25, clock.t) == [] and digest.free_gaps(con, TUE, 25, clock.t), "free_gaps(Mon) is []")
check(put([{"date": "2026-10-05", "label": "Holiday"}]).json()["cleared_blocks"] == 0 and len(infos()) == 1,
      "the same list again: nothing newly cleared, no second line")
real_away, mon_plan = cal.away_days, cal.plan(con, MON, 1, clock.t)
cal.away_days = lambda d0, n: (_ for _ in ()).throw(RuntimeError("patched by a test"))
check(cal.plan(con, MON, 1, clock.t) == mon_plan and digest.free_gaps(con, MON, 25, clock.t) == [],
      "the plan and the planner read days_off(): patching away_days() (as test_relay does) moves nothing")
cal.away_days = real_away

# 4. The night planner keeps off Monday
clock.t = dt.datetime(2026, 10, 4, 21, 0).timestamp()          # Sunday night: Monday is tomorrow
ok, why, _ = digest.validate(con, PROPOSALS[0], clock.t)
check(not ok and why == "Monday is a day off; pick the other day", f"proposal on Monday rejected: {why}")
check(digest.validate(con, dict(PROPOSALS[0], day="2026-10-06"), clock.t)[0], "the same proposal on Tuesday is fine")
week = [{"habit": "drawing", "label": "Drawing", "unit": "min", "status3": "off_track", "need_per_day_min": 30,
         "buffer_days": 0, "reason": "Behind."}]
pick = digest.rules_pick(con, clock.t, week)
check(pick and pick["day"] == "2026-10-06", f"rules picker skips the day off: {pick and pick['day']}")
tool = digest.tool_call(con, "plan", {"day": "2026-10-05"}, clock.t, week)
check(tool and all(b["state"] == "skipped" and b["day_off"] == "Holiday" for b in tool), "the model's plan tool says why")

# 5. Monday itself: no prompt, never "didn't happen"; a session you do anyway still counts
clock.t = dt.datetime(2026, 10, 5, 10, 0, 30).timestamp()
cal.tick(con, clock.t)
check(not [a for a in notify.recent_alerts(500) if a["kind"] == "planned"], "no planned prompt on a day off")
sid = db.create_session(con, "drawing", "physical", 30)
b = next(b for b in cal.plan(con, MON, 1, clock.t) if b["habit"] == "drawing")
check(b["state"] == "live" and b["away_label"] == "Holiday", f"drawing anyway on a day off shows as {b['state']}")
db.finish_session(con, sid, verdict="done", on_task_ratio=0.9)
clock.t = dt.datetime(2026, 10, 5, 16, 0).timestamp()
cal.tick(con, clock.t)
check(not [k for k in cal.load()["outcomes"] if "2026-10-05" in k], "no Monday block recorded as missed")
clock.t = dt.datetime(2026, 10, 6, 10, 0, 30).timestamp()
cal.tick(con, clock.t)
check([a for a in notify.recent_alerts(500) if a["kind"] == "planned" and a["block_key"] == "drawing@2026-10-06T10:00"],
      "Tuesday is prompted as usual")

# 6. The past stays: Monday is over, GET drops it, a later PUT keeps it as history
r = put([{"date": "2026-10-09", "label": "Trip"}, {"date": "2026-10-09", "label": "Long weekend"},
         {"date": "2026-10-12", "label": "Long weekend"}])
check(r.json()["days"] == [{"date": "2026-10-09", "label": "Long weekend"}, {"date": "2026-10-12", "label": "Long weekend"}],
      "a repeated date keeps its last label")
check(c.get("/api/calendar/away").json()["days"] == r.json()["days"], "GET drops Monday once it's past")
check(all(b["detail"] == "Day off" for b in cal.plan(con, MON, 1, clock.t) if b["habit"] != "drawing"),
      "Monday's plan still reads Day off afterwards")
check(infos()[-1]["text"] == "2 days off added. I've cleared 5 blocks." and r.json()["cleared_blocks"] == 5,
      f"two days at once: {infos()[-1]['text']} ({r.json()['cleared_blocks']})")

# 7. The kill switch: stored, but nothing changes
os.environ["ALIBI_AWAY"] = "0"
n = len(infos())
r = put([{"date": "2026-10-09", "label": "Long weekend"}, {"date": "2026-10-12", "label": "Long weekend"},
         {"date": "2026-10-13", "label": "Off"}])
check(r.status_code == 200 and r.json()["cleared_blocks"] == 0 and len(infos()) == n, "ALIBI_AWAY=0: PUT stores, clears nothing, says nothing")
check(c.get("/api/calendar/away").json()["days"][-1]["date"] == "2026-10-13", "ALIBI_AWAY=0: GET still returns what's stored")
check(cal.away_days(TUE, 30) == [], "ALIBI_AWAY=0: away_days() is []")
same_as_before("ALIBI_AWAY=0", clock.t)
os.environ.pop("ALIBI_AWAY")
check(cal.away_days(TUE, 30), "the switch is read on every call")

# 8. An empty list is no days off: identical again
r = put([])
check(r.json() == {"days": [], "cleared_blocks": 0} and json.loads(AWAY.read_text())["days"], "PUT [] clears the future (the past stays as history)")
AWAY.write_text(json.dumps({"days": []}))
same_as_before("empty away.json", clock.t)
print("PASS test_away")
