"""Calendar DoD: schedule -> events in an "Alibi" calendar; planned block begins -> one drop-down with Start / In 10 min /
Skip; session verdict -> the event says what happened; missed / skipped / moved / unplanned / Strava blocks; denied
permission and a flaky helper are handled. Uses tests/fake_calendar.py — never the real Calendar."""
import datetime as dt, json, os, pathlib, stat, sys, tempfile
os.environ["SAMPLE_EVERY_S"] = "10"
os.environ["LAPTOP_EVERY_S"] = "10"
HERE = pathlib.Path(__file__).resolve().parent
FAKE = HERE / "fake_calendar.py"
os.chmod(FAKE, os.stat(FAKE).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
FAKE_STATE = tempfile.mktemp(prefix="alibi-fakecal-", suffix=".json")
os.environ["ALIBI_CALENDAR_BIN"] = str(FAKE)
os.environ["FAKE_CALENDAR_STATE"] = FAKE_STATE
os.environ.pop("FAKE_CALENDAR_AUTH", None)
from harness import Clock, check
import make_fixtures
os.environ["CAMERA_SOURCE"] = str(make_fixtures.video("desk_cal.mp4", [("on_task", 200), ("phone", 100)]))
import yaml
from fastapi.testclient import TestClient
from alibi import api, calendar_sync as cal, cli, config, daemon, db, hooks, laptop_logger, notify, verifier

JARGON = ("witness", "daemon", "modality", "ingest", "on_task_ratio", "helper", "eventkit", "backend")
check(str(config.HABITS_PATH) != str(config.ROOT / "habits.yaml"), "scratch habits.yaml, never the real one")
check(cal.helper_bin() == str(FAKE), "ALIBI_CALENDAR_BIN points at the fake")

cfg = config.habits()
cfg["habits"]["drawing"]["schedule"] = [{"days": list(config.DAYS), "at": "10:00", "min": 3}]
cfg["habits"]["cpp"]["schedule"] = [{"days": ["mon", "tue", "wed", "thu", "fri"], "at": "14:00", "min": 30}]
cfg["habits"]["cpp"]["calendar"] = False
cfg["habits"]["running"]["schedule"] = [{"days": ["tue"], "at": "07:00", "min": 30}]
yaml.safe_dump(cfg, open(config.HABITS_PATH, "w"), sort_keys=False)

con = db.connect()
clock = Clock()
clock.t = dt.datetime(2026, 10, 5, 9, 59).timestamp()           # Monday 09:59
laptop_logger.frontmost = lambda: {"app": "Cursor", "title": "main.cpp", "url": ""}
hooks.start(con)
c = TestClient(api.app)


def fake():
    return json.load(open(FAKE_STATE))


def events():
    return sorted(fake()["events"].values(), key=lambda e: e["start"])


def alerts(kind="planned"):
    return [a for a in notify.recent_alerts(200) if a.get("kind") == kind]


def run_ticks(n, step=5):
    for _ in range(n):
        daemon.tick(con)
        clock.advance(step)
    cal.join()


def calls(cmd):
    return [x for x in fake()["calls"] if x["cmd"] == cmd]


# 1. Fresh: a plain sentence and one button. Reading status never asks for permission.
s = c.get("/api/calendar/status").json()
check(s["available"] and s["permission"] == "not_determined" and not s["connected"], f"fresh status: {s['permission']}")
check(s["action"] and s["action"]["label"] == "Add to Apple Calendar" and s["action"]["post"] == "/api/calendar/connect",
      f"one clear action: {s['action']}")
check(not any(j in s["message"].lower() for j in JARGON), "status message has no jargon: " + s["message"])
check(not calls("request"), "status never triggered a permission request")

# 2. The plan comes from habits.yaml schedules, with Calendar or without.
p = c.get("/api/calendar/plan", params={"date": "2026-10-05"}).json()
keys = [b["key"] for b in p["blocks"]]
check(keys == ["drawing@2026-10-05T10:00", "cpp@2026-10-05T14:00"], f"Monday's blocks: {keys}")
check(p["blocks"][0]["state"] == "planned" and p["next"]["habit"] == "drawing" and p["blocks"][0]["label"] == "Drawing",
      "drawing is next, planned")
check(p["blocks"][1]["calendar"] is False, "cpp has calendar: false")
tue = c.get("/api/calendar/plan", params={"date": "2026-10-06"}).json()["blocks"]
check([b["habit"] for b in tue] == ["running", "drawing", "cpp"] and tue[0]["check"] == "strava", "Tuesday includes the run")

# 3. Denied: honest sentence + Open Settings, nothing written.
os.environ["FAKE_CALENDAR_DENY"] = "1"
r = c.post("/api/calendar/connect").json()
check(not r["ok"] and r["status"]["permission"] == "denied", "Don't Allow -> not connected")
check(r["status"]["action"]["label"] == "Open System Settings" and "Privacy & Security" in r["status"]["message"],
      "denied: tells you where to switch it on")
check(not fake()["events"], "nothing written without access")
st = fake(); st["auth"] = "not_determined"; json.dump(st, open(FAKE_STATE, "w"))
os.environ.pop("FAKE_CALENDAR_DENY")

# 4. Connect: one request, an "Alibi" calendar, 14 days of drawing; cpp (calendar: false) stays out.
r = c.post("/api/calendar/connect").json()
check(r["ok"] and r["auth"] == "full" and r["status"]["connected"], f"connected: {r.get('sync')}")
check([c_["title"] for c_ in fake()["calendars"].values()] == ["Alibi"], "made exactly one calendar called Alibi")
evs = events()
draw = [e for e in evs if e["title"].startswith("Drawing")]
runs = [e for e in evs if e["title"].startswith("Running")]
check(len(draw) == 14 and all(e["title"] == "Drawing · 3 min" for e in draw), f"{len(draw)} drawing events, 'Drawing · 3 min'")
check(len(runs) == 2 and runs[0]["title"] == "Running · 30 min", f"two Tuesday runs in 14 days: {[e['title'] for e in runs]}")
check(len(evs) == 16, f"nothing else written ({len(evs)} events): C++ has calendar: false")
check(draw[0]["start"] == dt.datetime(2026, 10, 5, 10, 0).timestamp(), "first event Monday 10:00")
check(not any(j in draw[0]["notes"].lower() for j in JARGON), "event notes are plain: " + draw[0]["notes"].replace("\n", " "))
r2 = c.post("/api/calendar/sync").json()
check(r2["ok"] and r2["created"] == 0 and r2["deleted"] == 0 and r2["updated"] == 0 and r2["kept"] == 16,
      f"second sync is a no-op: {r2}")
check(len(events()) == 16, "no duplicates")

# 5. AUTO-START: nothing before 10:00; exactly one drop-down at 10:00.
run_ticks(6, 5)                      # 09:59:00 -> 09:59:30
check(not alerts(), "no prompt before the block starts")
clock.t = dt.datetime(2026, 10, 5, 10, 0, 2).timestamp()
run_ticks(4, 5)
a = alerts()
check(len(a) == 1, f"one prompt at 10:00 (got {len(a)})")
a = a[0]
check(a["text"] == "Drawing is planned now — start?", "says: " + a["text"])
labels = [x["label"] for x in a["actions"]]
check(labels == ["Start 3 min", "In 10 min", "Skip today"], f"actions {labels}")
check(a["actions"][0]["say"] == "drawing for 3 minutes" and a["block_key"] == "drawing@2026-10-05T10:00"
      and a["habit"] == "drawing" and a["minutes"] == 3, "Start says the right sentence")
check(a["actions"][1]["post"] == "/api/calendar/plan/snooze" and a["actions"][1]["body"]["min"] == 10, "In 10 min posts")
check(c.get("/api/calendar/plan").json()["blocks"][0]["state"] == "now", "plan state: now")

# 6. In 10 min -> quiet, then asked again (late wording).
r = c.post("/api/calendar/plan/snooze", json={"key": a["block_key"], "min": 10}).json()
check(r["ok"] and "10:10" in r["reply"], "snooze reply: " + r["reply"])
run_ticks(12, 30)                    # 6 min
check(len(alerts()) == 1, "quiet during the snooze")
clock.t = dt.datetime(2026, 10, 5, 10, 10, 30).timestamp()
run_ticks(2, 5)
check(len(alerts()) == 2 and alerts()[-1]["text"] == "Drawing was planned for 10:00 — start now?",
      "asked again after the snooze: " + alerts()[-1]["text"])

# 7. Start (exactly what the island's button says) -> event shows "in progress" -> verdict lands on the same event.
ev_id = cal.load()["events"]["drawing@2026-10-05T10:00"]
print("   ", cli.say(con, alerts()[-1]["actions"][0]["say"]))
cal.join()
check(fake()["events"][ev_id]["title"] == "● Drawing — in progress", "event: " + fake()["events"][ev_id]["title"])
check(c.get("/api/calendar/plan").json()["blocks"][0]["state"] == "live", "plan state: live")
run_ticks(50, 5)
sid = con.execute("SELECT id FROM sessions ORDER BY id DESC LIMIT 1").fetchone()["id"]
sess = db.get_session(con, sid)
check(sess["status"] == "done", f"session closed: {sess['verdict']} {sess['on_task_ratio']}")
ev = fake()["events"][ev_id]
pct = round(sess["on_task_ratio"] * 100)
check(ev["title"] == f"✓ Drawing — done {pct}%" if sess["verdict"] == "done" else ev["title"].startswith(("◐", "✗")),
      "verdict on the planned event: " + ev["title"])
check(ev["start"] == dt.datetime(2026, 10, 5, 10, 0).timestamp(), "event keeps its planned slot")
check(f"#session-{sid}" in ev["url"] and f"#session-{sid}" in ev["notes"], "event links to the session")
check("You started at 10:10" in ev["notes"] and "desk camera" in ev["notes"], "notes say what was seen: "
      + ev["notes"].replace("\n", " | "))
check(not any(j in ev["notes"].lower() for j in JARGON), "verdict notes have no jargon")
blk = c.get("/api/calendar/plan").json()["blocks"][0]
check(blk["state"] == sess["verdict"] and blk["session_id"] == sid, f"plan state: {blk['state']}")
check(len(alerts()) == 2, "no more prompts once it was done")

# 8. A correction re-scores the session -> the calendar follows.
before = ev["title"]
for lab in verifier.camera_labels(con, sess)[:6]:
    verifier.correct(con, sid, lab["ts"], "phone")
clock.advance(70)
run_ticks(2, 5)
after = fake()["events"][ev_id]["title"]
check(after != before and after.startswith(("◐", "✗", "✓")), f"calendar re-scored: {before} -> {after}")

# 9. An unplanned session is logged at its real time (log_unplanned default on).
clock.t = dt.datetime(2026, 10, 5, 12, 0).timestamp()
print("   ", cli.say(con, "code c++ for 2 minutes"))
run_ticks(30, 5)
cal.join()
sid2 = con.execute("SELECT id FROM sessions ORDER BY id DESC LIMIT 1").fetchone()["id"]
log = [e for e in events() if f"#session-{sid2}" in e["url"]]
check(len(log) == 1 and log[0]["title"].startswith(("✓ C++", "◐ C++", "✗ C++"))
      and abs(log[0]["start"] - db.get_session(con, sid2)["started_at"]) < 1, f"unplanned session logged: {log and log[0]['title']}")

# 10. Skip the 14:00 C++ block (not in calendar): no prompt at 14:00, plan says skipped, no calendar write.
n_apply = len(calls("apply"))
r = c.post("/api/calendar/plan/skip", json={"key": "cpp@2026-10-05T14:00"}).json()
check(r["ok"] and r["reply"] == "Skipped C++ for today.", r["reply"])
clock.t = dt.datetime(2026, 10, 5, 14, 0, 3).timestamp()
run_ticks(3, 5)
check(not [x for x in alerts() if x["habit"] == "cpp"], "no prompt for a skipped block")
check(len(calls("apply")) == n_apply, "skipping a calendar:false habit writes nothing")
check([b["state"] for b in c.get("/api/calendar/plan").json()["blocks"]][1] == "skipped", "plan: skipped")
check(c.post("/api/calendar/plan/skip", json={"key": "nope@2026-10-05T14:00"}).status_code == 404, "unknown key -> 404")

# 11. Move Wednesday's drawing to 11:15 -> its event follows.
r = c.post("/api/calendar/plan/move", json={"key": "drawing@2026-10-07T10:00", "at": "11:15"}).json()
check(r["ok"] and r["block"]["at"] == "11:15", r["reply"])
cal.join()
wed = [e for e in events() if dt.datetime.fromtimestamp(e["start"]).date() == dt.date(2026, 10, 7)]
check(len(wed) == 1 and dt.datetime.fromtimestamp(wed[0]["start"]).strftime("%H:%M") == "11:15", "Wednesday event moved")
check(c.post("/api/calendar/plan/move", json={"key": "drawing@2026-10-07T10:00", "at": "25:99"}).status_code == 400,
      "bad time -> 400")

# 12. Tuesday: run seen on Strava -> done; drawing never happened -> "didn't happen" (with a flaky helper first).
day2 = dt.datetime(2026, 10, 6)
db.add_event(con, "strava", "activity", {"id": 1, "name": "Morning Run", "distance_km": 5.4}, ts=(day2 + dt.timedelta(hours=7, minutes=5)).timestamp())
clock.t = (day2 + dt.timedelta(hours=7, minutes=0, seconds=3)).timestamp()
run_ticks(1)
check(not [x for x in alerts() if x["habit"] == "running"], "run already on Strava -> no prompt")
os.environ["FAKE_CALENDAR_FAIL"] = "apply"
clock.t = (day2 + dt.timedelta(hours=11, minutes=30)).timestamp()
run_ticks(1)
oc = cal.load()["outcomes"].get("drawing@2026-10-06T10:00", {})
check(oc.get("state") == "missed" and oc.get("synced") is False, "missed recorded, calendar push failed and is pending")
check(cal.status()["details"]["last_error"], "error kept for Details")
os.environ.pop("FAKE_CALENDAR_FAIL")
clock.advance(400)
run_ticks(2)
tue_draw = [e for e in events() if dt.datetime.fromtimestamp(e["start"]) == day2 + dt.timedelta(hours=10)]
check(tue_draw and tue_draw[0]["title"] == "✗ Drawing — didn't happen", f"retried later: {tue_draw and tue_draw[0]['title']}")
check(len([e for e in events() if dt.datetime.fromtimestamp(e["start"]) == day2 + dt.timedelta(hours=10)]) == 1,
      "the planned event was updated, not duplicated")
check(c.get("/api/calendar/plan", params={"date": "2026-10-06"}).json()["blocks"][0]["state"] == "done", "run: done (plan)")
clock.t = dt.datetime(2026, 10, 7, 7, 0).timestamp()
run_ticks(1)
run_ev = [e for e in events() if e["start"] == (day2 + dt.timedelta(hours=7)).timestamp()]
check(run_ev and run_ev[0]["title"].startswith("✓ Running — done") and "5.4 km" in run_ev[0]["title"],
      f"run event: {run_ev and run_ev[0]['title']}")

# 13. Schedule edit (dashboard saves habits.yaml) -> next tick re-syncs: drawing only Mon/Fri now.
cfg = config.habits()
cfg["habits"]["drawing"]["schedule"] = [{"days": ["mon", "fri"], "at": "09:00", "min": 20}]
yaml.safe_dump(cfg, open(config.HABITS_PATH, "w"), sort_keys=False)
clock.advance(30)
run_ticks(1)
cal.join()
fut = [e for e in events() if e["start"] >= clock.t and "/#plan" in e["url"]]
check(fut and all(e["title"] in ("Drawing · 20 min", "Running · 30 min") for e in fut)
      and all(dt.datetime.fromtimestamp(e["start"]).strftime("%a %H:%M") in ("Mon 09:00", "Fri 09:00", "Tue 07:00")
              for e in fut), f"future events follow the new schedule: {sorted({e['title'] for e in fut})}")
past = [e for e in events() if e["start"] < clock.t]
check(any(e["title"].startswith("✗ Drawing — didn't happen") for e in past), "history is never rewritten")

# 14. Disconnect, optionally clearing future plan events; status goes back to the Connect sentence.
r = c.post("/api/calendar/disconnect", json={"remove_future": True}).json()
check(r["ok"] and r["removed"] >= 1 and not r["status"]["connected"], f"disconnected, removed {r['removed']}")
check(not [e for e in events() if e["start"] >= clock.t and "/#plan" in e["url"]], "future plan events gone")
check(r["status"]["action"]["label"] == "Add to Apple Calendar", "can reconnect")

# 15. No helper at all -> a sentence, not a crash; prompts still work without Calendar.
os.environ["ALIBI_CALENDAR_BIN"] = "/nonexistent/alibi-calendar"
s = c.get("/api/calendar/status").json()
check(not s["available"] and "isn't installed" in s["message"] and s["action"] is None, s["message"])
check(c.post("/api/calendar/connect").json()["ok"] is False, "connect without helper fails politely")
os.environ["ALIBI_CALENDAR_BIN"] = str(FAKE)

# 16. Alibi.app asks for Calendar under its own name.
build = (config.ROOT / "scripts" / "build_native.sh").read_text()
check(build.count("NSCalendarsFullAccessUsageDescription") == 2 and "alibi-calendar" in build
      and "__info_plist" in build, "build: usage strings in Alibi.app + embedded in the helper, helper copied in")
for a in alerts():
    check(not any(j in a["text"].lower() for j in JARGON), "prompt has no jargon: " + a["text"])
os.remove(FAKE_STATE)
print("Calendar DoD passed.")
