"""REPORT_HOUR=-1 (nightly report off) must drop the night slot, not crash every tick."""
import os
os.environ["REPORT_HOUR"] = "-1"
from harness import check
import datetime as dt
from alibi import digest

s = digest.slots(dt.date.today())
check(all(k != "night" for k, _, _ in s) and len(s) == 4, f"REPORT_HOUR=-1 -> no night slot ({[x[1] for x in s]})")
check(digest.due(dt.datetime.combine(dt.date.today(), dt.time(23, 0)).timestamp())[0] == "checkpoint",
      "23:00 with the report off -> the 20:00 checkpoint is the latest slot")
print("Digest off DoD passed.")
