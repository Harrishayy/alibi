"""A habit added at 21:29 with a 21:00-21:20 block today is never offered that block ("was planned for 21:00 — start
now?" two seconds after "Noted. ..."), the same rule plan_today uses; a habit that existed before the block still is."""
import datetime as dt
from harness import Clock, check
import yaml
from alibi import calendar_sync as cal, config, db, notify

cfg = config.habits()
for k in cfg["habits"]:
    cfg["habits"][k].pop("schedule", None)
base = {"modality": "physical", "default_min": 20, "weekly_target_min": 40, "aliases": [], "on_task_looks_like": "playing"}
cfg["habits"]["piano"] = dict(base, label="Piano", schedule=[{"days": ["fri"], "at": "21:00", "min": 20}],
                              created_at="2026-10-09 21:29")
yaml.safe_dump(cfg, open(config.HABITS_PATH, "w"), sort_keys=False)
con = db.connect()
clock = Clock()
clock.t = dt.datetime(2026, 10, 9, 21, 29, 27).timestamp()      # Friday, 9 min after the block ended
n0 = len(notify.recent_alerts(500))
cal.tick(con, clock.t)
new = [a for a in notify.recent_alerts(500)[n0:] if a["kind"] == "planned"]
check(not new, "a block that ended before the habit existed is not offered")

cfg["habits"]["piano"]["created_at"] = "2026-10-09 20:00"     # the habit existed before the block
yaml.safe_dump(cfg, open(config.HABITS_PATH, "w"), sort_keys=False)
cal.tick(con, clock.t)
new = [a for a in notify.recent_alerts(500)[n0:] if a["kind"] == "planned"]
check(len(new) == 1 and new[0]["habit"] == "piano" and "was planned for 21:00" in new[0]["text"],
      "a habit that existed before its block still gets the late offer")
print("Created-at prompt DoD passed.")
