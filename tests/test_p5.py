"""P5 DoD: strava sync prints this week's runs; report shows Running 1/3 — behind by 2 (fixture, no keys)."""
import subprocess, sys, os
from harness import check
import make_fixtures
fx = make_fixtures.strava()
cmd = [sys.executable, "-m", "alibi.strava", "sync", "--fixture", str(fx)]
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = subprocess.run(cmd, capture_output=True, text=True, cwd=root, env=os.environ).stdout
print("\n".join("    " + l for l in out.splitlines()))
check("Morning Run: 5.4 km" in out and "Commute" not in out, "runs synced, ride ignored")
check("Running 1/3 — behind by 2" in out, "5 km rule applied: 1/3, behind by 2")
again = subprocess.run(cmd, capture_output=True, text=True, cwd=root, env=os.environ).stdout
check("+" not in again, "re-sync dedupes on activity id")
print("P5 DoD passed.")
