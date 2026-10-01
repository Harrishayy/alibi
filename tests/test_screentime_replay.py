"""Screen Time backfill bursts must not count as fresh minutes; no Apple Watch => heart is 'not applicable'."""
import os
os.environ["ALIBI_APPLE_WATCH"] = "0"
from harness import Clock, check
from alibi import db, signals

con = db.connect()
clock = Clock()
t = clock.t
for m in (115, 120, 115, 120):                     # the burst the real iPhone sent at monitoring start
    db.add_event(con, "phone", "screentime", {"app": "Picked apps", "minutes": m, "threshold_min": 5}, ts=t)
clock.advance(300)
db.add_event(con, "phone", "screentime", {"app": "Picked apps", "minutes": 125, "threshold_min": 5}, ts=clock.t)
d = signals.screentime_deltas(con, t - 1, clock.t + 1)
total = sum(x["delta"] for x in d)
print("    deltas:", [x["delta"] for x in d])
check(total <= 15, f"backfill burst + one real step counts ≤ 15 min, not 115+ (got {total})")
check(d[-1]["delta"] == 5, "the next real 5-min step still counts")
st = signals.status(con)
heart = next(x for x in st["sources"] if x["key"] == "health.heart")
check(heart["state"] == "not_applicable" and heart not in st.get("missing", []), "heart is not applicable without a Watch")
print("Screen Time replay DoD passed.")
