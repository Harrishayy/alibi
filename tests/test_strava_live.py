"""Strava claims DoD: one settle per claim. After a sync brings in the run, the Strava thread and the tick both check claims; on
one qualifying run that is one claim_settled and one verdict. And with Strava connected, daemon._strava leaves syncing
to integrations (no second sync, no second "logged" line). No network: strava.fetch is a stub."""
import datetime as dt, os, threading, time
from harness import check
from alibi import cli, daemon, db, integrations, notify, strava

con = db.connect()


def count(sql):
    return con.execute(sql).fetchone()[0]


def verdicts():
    return [a for a in notify.recent_alerts(1000) if a["kind"] == "verdict" and a.get("habit") == "running"]


r = cli.say(con, "going for a run")
check("checked by Strava" in r and count("SELECT count(*) FROM sessions") == 0, f"claim: {r}")
claim_ts = con.execute("SELECT ts FROM events WHERE source='user' AND kind='claim'").fetchone()[0]

# The run starts a minute after the claim; the sync pipeline stores it as a strava event.
start = dt.datetime.fromtimestamp(claim_ts + 60, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
strava.fetch = lambda after: [{"id": 4242, "name": "Evening Run", "sport_type": "Run", "distance": 5200.0,
                               "moving_time": 1800, "total_elevation_gain": 12, "start_date": start}]
added = strava.sync()
check(len(added) == 1 and added[0]["distance_km"] == 5.2, f"sync stored the run ({added})")

# Both callers at once: the Strava thread's claim check and the tick's. A slow read widens the race window so that,
# without the lock, both would read "unsettled" before either writes.
real_between = db.events_between


def slow_between(*a, **k):
    time.sleep(0.2)
    return real_between(*a, **k)


db.events_between = slow_between
gate = threading.Barrier(2)


def strava_thread():
    gate.wait()
    integrations._check_claims(db.connect())


def tick_thread():
    gate.wait()
    integrations.tick(db.connect(), time.time())


ts = [threading.Thread(target=strava_thread), threading.Thread(target=tick_thread)]
for t in ts:
    t.start()
for t in ts:
    t.join(10)
db.events_between = real_between

n = count("SELECT count(*) FROM events WHERE source='alibi' AND kind='claim_settled'")
v = verdicts()
check(n == 1, f"two racing checks -> 1 claim_settled (got {n})")
check(len(v) == 1 and v[0]["text"] == "Run verified: 5.2 km." and v[0]["verdict"] == "done",
      f"two racing checks -> 1 verdict alert ({[x['text'] for x in v]})")
check(daemon.check_claims(con) == [] and len(verdicts()) == 1, "a later check is quiet")

# daemon._strava: with Strava connected it doesn't sync (integrations does); with only the old env token it still does.
syncs = []
strava.sync = lambda *a, **k: syncs.append(1) or []
os.environ["STRAVA_REFRESH_TOKEN"] = "test-not-a-token"
strava.connected = lambda: True
daemon._strava_synced = 0.0
daemon._strava(con)
check(not syncs, f"connected -> daemon._strava leaves it to integrations ({len(syncs)} syncs)")
strava.connected = lambda: False
daemon._strava_synced = 0.0
daemon._strava(con)
check(len(syncs) == 1, "env token only -> the old hourly sync still runs")
print("PASS test_strava_live")
