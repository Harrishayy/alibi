"""Report DoD: `cli report` prints the table + summary from real sessions; daemon fires it at REPORT_HOUR once."""
import datetime as dt, os
os.environ["SAMPLE_EVERY_S"] = "60"
from harness import Clock, check
import make_fixtures
os.environ["CAMERA_SOURCE"] = str(make_fixtures.video("desk_4min.mp4", [("on_task", 120), ("phone", 60), ("absent", 60)]))
from alibi import cli, config, daemon, db, notify

con = db.connect()
clock = Clock()
noon = dt.datetime.fromtimestamp(clock.t).replace(hour=12, minute=0).timestamp()
clock.t = noon
cli.start(con, "draw for 4 minutes")
for _ in range(50):
    daemon.tick(con); clock.advance(5)
out = cli.report(con)
print("\n".join("    " + l for l in out.splitlines()))
check("drawing" in out and "behind by" in out, "table has drawing + status")
check("declared" in out.lower() and "evidence supports" in out, "dry summary contrasts claimed vs seen")
clock.t = dt.datetime.fromtimestamp(noon).replace(hour=config.REPORT_HOUR, minute=0).timestamp()
daemon.tick(con); clock.advance(5); daemon.tick(con)
check(sum(a["kind"] == "report" for a in notify.recent_alerts()) == 1, "nightly report fired exactly once at REPORT_HOUR")
print("Report DoD passed.")
