"""Pace v2 DoD: on_track / at_risk / off_track / done / stale with buffer days, on the fake clock."""
import datetime as dt
from harness import Clock, check
import yaml
from alibi import config, db, report, strava

con = db.connect()
clock = Clock()
MON = dt.datetime(2026, 10, 5)                                  # a Monday


def at(day: int, h: int, m: int = 0) -> float:
    return (MON + dt.timedelta(days=day, hours=h, minutes=m)).timestamp()


def habits(**hs):
    yaml.safe_dump({"habits": hs, "verdict": {"done": 0.7, "partial": 0.4}}, open(config.HABITS_PATH, "w"))
    con.execute("DELETE FROM sessions")
    con.execute("DELETE FROM events")
    con.commit()


def sess(habit: str, start: float, minutes: int, ratio: float = 1.0):
    con.execute("INSERT INTO sessions(habit,modality,declared_min,started_at,ends_at,ended_at,status,on_task_ratio,"
                "verdict) VALUES (?,?,?,?,?,?,'done',?,'done')",
                (habit, "physical", minutes, start, start + minutes * 60, start + minutes * 60, ratio))
    con.commit()


def row(key: str, now: float) -> dict:
    clock.t = now
    out = report.build_json()
    if out["running"] and out["running"]["habit"] == key:
        return out["running"]
    return next(r for r in out["rows"] if r["habit"] == key)


DRAW = {"modality": "physical", "default_min": 25, "weekly_target_min": 300}
FIELDS = ("status3", "buffer_days", "need_per_day_min", "need_today_min", "capacity_left_min", "stale", "reason")

# 1. Monday morning, nothing done yet: inside the 0.1T band, so on track.
habits(drawing=DRAW)
r = row("drawing", at(0, 9))
check(all(k in r for k in FIELDS) and "status" in r, "row carries every pace v2 field and keeps the old status")
check(r["status3"] == "on_track", f"1. Mon 09:00, 0 of 300: on_track ({r['status3']}, {r['reason']!r})")

# 2. Thursday evening with 60 of 300: off track, and the per-day need is right.
sess("drawing", at(1, 10), 60)
r = row("drawing", at(3, 20))
want = 240 / ((7 * 24 - (3 * 24 + 20)) / 24)
check(r["status3"] == "off_track", f"2. Thu 20:00, 60 of 300, unscheduled: off_track ({r['reason']!r})")
check(abs(r["need_per_day_min"] - want) <= 1, f"2. need_per_day_min {r['need_per_day_min']} ≈ {want:.1f}")
check(r["reason"].endswith("a day until Sunday.") and "behind" in r["reason"], f"2. reason reads dry: {r['reason']!r}")

# 3. Unscheduled, gap of 0.2T: the band makes at_risk reachable.
habits(drawing=DRAW)
p = 300 * (2 * 24 + 12) / 168
sess("drawing", at(0, 10), 50, (p - 60) / 50)
r = row("drawing", at(2, 12))
check(r["status3"] == "at_risk", f"3. Wed 12:00, gap 0.2T: at_risk ({r['reason']!r})")

# 4. Scheduled: 240 min of blocks left cover what's missing, so at risk, not off track.
habits(drawing=dict(DRAW, schedule=[{"days": list(config.DAYS), "at": "18:00", "min": 60}]))
sess("drawing", at(0, 18), 60)
r = row("drawing", at(3, 12))
check(r["capacity_left_min"] == 240, f"4. capacity_left_min is the remaining block minutes ({r['capacity_left_min']})")
check(r["status3"] == "at_risk", f"4. scheduled, blocks cover the gap: at_risk ({r['reason']!r})")

# 5. Running, counted in runs: 1 of 3 on Saturday is off track.
RUN = {"source": "strava", "weekly_sessions": 3, "min_km": 5}
habits(drawing=DRAW, running=RUN)
db.add_event(con, "strava", "activity", {"id": 1, "distance_km": 6.2, "moving_min": 35, "start_date": at(1, 7)},
             ts=at(1, 7))
r = row("running", at(5, 12))
check(r["unit"] == "runs" and r["status3"] == "off_track", f"5. Sat, 1 of 3 runs: off_track ({r['reason']!r})")

# 6. Strava configured but silent for a day: stale. The camera habit never is.
real = strava.connected, strava.state
strava.connected, strava.state = (lambda: True), (lambda: {"last_sync": at(1, 8)})
try:
    r = row("running", at(5, 12))
    d = row("drawing", at(5, 12))
finally:
    strava.connected, strava.state = real
check(r["status3"] == "stale" and r["stale"] and r["reason"].startswith("Can't see"), f"6. running stale ({r['reason']!r})")
check(d["status3"] != "stale" and d["stale"] is False, f"6. drawing (camera) never stale ({d['status3']})")

# 7. Sunday 20:00, 10 min short: at risk, not off track (need_per_day is gated by days_left ≥ 1).
habits(drawing=dict(DRAW, weekly_target_min=60))
p = 60 * (6 * 24 + 20) / 168
sess("drawing", at(2, 10), 50, (p - 10) / 50)
r = row("drawing", at(6, 20))
check(r["status3"] == "at_risk", f"7. Sun 20:00, gap 10 min: at_risk ({r['reason']!r})")

# Done and buffer: ahead of pace reads as days of buffer.
habits(drawing=DRAW)
sess("drawing", at(0, 10), 150)
r = row("drawing", at(1, 12))
check(r["status3"] == "on_track" and r["buffer_days"] >= 1 and "of buffer" in r["reason"],
      f"buffer: ahead of pace -> {r['buffer_days']} days ({r['reason']!r})")
sess("drawing", at(1, 13), 150)
check(row("drawing", at(1, 16))["status3"] == "done", "done: V ≥ T")
print("Pace v2 DoD passed.")
