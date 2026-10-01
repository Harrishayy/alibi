"""No data is not a miss: Strava/Health blocks Alibi couldn't see say "no data" in the calendar, never "didn't happen";
they say "didn't happen" only when the source was connected, that day's data arrived, and it fell short. Late data
still settles a "no data" block. Health units: meditation/workout minutes are never guessed from the size."""
import datetime as dt, json, os, pathlib, stat, tempfile
HERE = pathlib.Path(__file__).resolve().parent
FAKE = HERE / "fake_calendar.py"
os.chmod(FAKE, os.stat(FAKE).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
FAKE_STATE = tempfile.mktemp(prefix="alibi-fakecal-", suffix=".json")
os.environ["ALIBI_CALENDAR_BIN"] = str(FAKE)
os.environ["FAKE_CALENDAR_STATE"] = FAKE_STATE
os.environ["FAKE_CALENDAR_AUTH"] = "full"
for k in ("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN"):
    os.environ.pop(k, None)
from harness import Clock, check
import yaml
from fastapi.testclient import TestClient
from alibi import api, calendar_sync as cal, config, db, integrations, secrets as store, strava

# --- INT-13: units -------------------------------------------------------------------------------------------------
n = integrations.normalise_health
check(n({"date": "2026-10-01", "mindful_min": 60})["mindful_min"] == 60, "mindful_min 60 stays 60 minutes (no guessing)")
check(n({"date": "2026-10-01", "mindful_min": 600})["mindful_min"] == 600, "mindful_min 600 stays 600 minutes")
check(n({"date": "2026-10-01", "mindful_s": 60})["mindful_min"] == 1, "mindful_s 60 -> 1 minute")
check(n({"date": "2026-10-01", "workout_s": 240})["workout_min"] == 4, "workout_s 240 -> 4 minutes")
check(n({"date": "2026-10-01", "workout_min": 240})["workout_min"] == 240, "workout_min 240 stays 240")
check(n({"date": "2026-10-01", "sleep_h": 27000})["sleep_h"] == 7.5, "sleep still accepts seconds")
from alibi import routes_integrations as ri
check("all fine" not in ri.SHORTCUT_STEPS and "Convert Measurement" in ri.SHORTCUT_STEPS and "mindful_s" in ri.SHORTCUT_STEPS,
      "Shortcut steps convert units explicitly and offer *_s keys")

# --- INT-12: no data is not a miss ---------------------------------------------------------------------------------
cfg = config.habits()
for h in cfg["habits"].values():
    h.pop("schedule", None)
cfg["habits"]["running"]["schedule"] = [{"days": list(config.DAYS), "at": "07:00", "min": 30}]
cfg["habits"]["walk"] = {"source": "health", "metric": "steps", "daily_target": 8000, "display": "Walk 8,000 steps",
                         "schedule": [{"days": list(config.DAYS), "at": "18:00", "min": 60}]}
yaml.safe_dump(cfg, open(config.HABITS_PATH, "w"), sort_keys=False)

con = db.connect()
clock = Clock()
clock.t = dt.datetime(2026, 10, 1, 6, 0).timestamp()
cal.start(con)
c = TestClient(api.app)
r = c.post("/api/calendar/connect").json()
check(r["ok"], "calendar connected (fake)")
check(not strava.connected(), "Strava not connected")


def title(key):
    ev = cal.load()["events"].get(key) or cal.load()["outcomes"].get(key, {}).get("event_id")
    return json.load(open(FAKE_STATE))["events"].get(ev, {}).get("title")


def tick_at(t):
    clock.t = t
    cal.tick(con, clock.t)
    cal.join()


# Day 1 (Thu 1 Oct): nothing connected, nothing sent. Next morning 07:00 -> "no data", never "didn't happen".
tick_at(dt.datetime(2026, 10, 2, 7, 0).timestamp())
oc = cal.load()["outcomes"]
run_k, walk_k = "running@2026-10-01T07:00", "walk@2026-10-01T18:00"
check(oc.get(run_k, {}).get("state") == "unknown" and oc.get(walk_k, {}).get("state") == "unknown",
      f"outcomes are unknown, not missed: {[(k, v.get('state')) for k, v in oc.items()]}")
check(title(run_k) == "? Running — no Strava data", f"run event: {title(run_k)}")
check(title(walk_k) == "? Walk 8,000 steps — no data from iPhone", f"walk event: {title(walk_k)}")
evs = json.load(open(FAKE_STATE))["events"]
check(not any("didn't happen" in e["title"] for e in evs.values()), "no event says didn't happen")
notes = evs[cal.load()["outcomes"][walk_k]["event_id"]]["notes"]
check("doesn't count against you" in notes, "notes say it doesn't count: " + notes.replace("\n", " "))
p = c.get("/api/calendar/plan", params={"date": "2026-10-01"}).json()["blocks"]
check({b["state"] for b in p} == {"nodata"} and all(b["state_text"] == "No data" for b in p), f"plan: {[b['state'] for b in p]}")

# Late iPhone data for day 1 arrives (and falls short): the block settles to "didn't happen".
integrations.save_health(con, {"date": "2026-10-01", "steps": 3000})
tick_at(clock.t + 60)
check(cal.load()["outcomes"][walk_k]["state"] == "missed", "late data that falls short -> missed")
check(title(walk_k) == "✗ Walk 8,000 steps — didn't happen", f"walk event now: {title(walk_k)}")

# Day 2: iPhone sends enough steps -> done; Strava connected and synced after the day, no run -> didn't happen.
integrations.save_health(con, {"date": "2026-10-02", "steps": 9100})
store.update(strava_client_id="123", strava_client_secret="a" * 40, strava_refresh_token="r")
strava._state(last_sync=dt.datetime(2026, 10, 3, 6, 30).timestamp())
check(strava.connected(), "Strava connected now")
tick_at(dt.datetime(2026, 10, 3, 7, 0).timestamp())
oc = cal.load()["outcomes"]
check(oc["walk@2026-10-02T18:00"]["state"] == "done", "enough steps -> done")
check(oc["running@2026-10-02T07:00"]["state"] == "missed", "Strava connected + synced, no run -> missed")
check(title("running@2026-10-02T07:00") == "✗ Running — didn't happen", title("running@2026-10-02T07:00"))
check(oc[run_k]["state"] == "unknown", "day 1's run stays 'no data' (Strava wasn't connected then)")
print("OK test_nodata")
