"""Round 3 DoD (build:habits): schedules + calendar flag survive saves, Apple Health habits validate, templates and the
first-run wizard API, the one-tap 'Add Guitar' card, plain-language copy, honest correction toasts, Health summary."""
import os, json, re, stat, time
os.environ["SAMPLE_EVERY_S"] = "15"
from harness import Clock, check, ROOT
os.environ["CAMERA_SOURCE"] = str(ROOT / "tests" / "fixtures" / "desk_4min.mp4")   # on_task 120 s, phone 60 s, absent 60 s
from fastapi.testclient import TestClient
from alibi import api, cli, config, daemon, db, health, intent, onboarding, report, templates

assert str(config.HABITS_PATH) != str(config.ROOT / "habits.yaml")
con = db.connect()
c = TestClient(api.app)
JARGON = re.compile(r"witness|modality|daemon|ingest|on_task_ratio|physical|digital|hybrid|alias", re.I)

# --- INT-1: schedule + calendar survive a save; bad schedules get plain errors ---------------------------------
hs = config.habits()["habits"]
hs["drawing"]["schedule"] = [{"days": ["wed", "mon", "Mon"], "at": "7:05", "min": "25"}]
health.save_habits(hs)
d = config.habits()["habits"]["drawing"]
check(d["schedule"] == [{"days": ["mon", "wed"], "at": "07:05", "min": 25}] and d["calendar"] is True,
      f"schedule kept + normalised, calendar defaults on: {d['schedule']} {d['calendar']}")
check("created_at" not in d, "existing habits are not re-stamped with created_at")
hs = config.habits()["habits"]
hs["drawing"]["calendar"] = "false"
hs["cpp"]["schedule"] = [{"days": "weekdays", "at": "20:00", "min": 30}]
r = c.put("/api/habits", json={"habits": hs})
check(r.status_code == 200 and config.habits()["habits"]["drawing"]["calendar"] is False
      and config.habits()["habits"]["cpp"]["schedule"][0]["days"] == ["mon", "tue", "wed", "thu", "fri"],
      "PUT /api/habits keeps schedule; 'false' turns calendar off; 'weekdays' expands")
for bad, why in [({"days": ["funday"], "at": "10:00", "min": 5}, "isn't a day"),
                 ({"days": ["mon"], "at": "25:00", "min": 5}, "isn't a time"),
                 ({"days": ["mon"], "at": "10:00", "min": 0}, "planned length"),
                 ({"days": [], "at": "10:00", "min": 5}, "at least one day")]:
    hs = config.habits()["habits"]
    hs["drawing"]["schedule"] = [bad]
    r = c.put("/api/habits", json={"habits": hs})
    check(r.status_code == 400 and why in r.json()["detail"], f"bad schedule rejected in plain words: {r.json()['detail']}")

# --- INT-2: Apple Health habits validate; display works as a label ---------------------------------------------
hs = config.habits()["habits"]
hs["steps"] = {"source": "health", "metric": "steps", "daily_target": "8000", "display": "Walk"}
hs["sleep"] = {"source": "health", "metric": "sleep_h", "daily_target": 7.5,
               "schedule": [{"days": ["sun", "mon"], "at": "23:00", "min": 30}]}
r = c.put("/api/habits", json={"habits": hs})
check(r.status_code == 200, f"health habits save: {r.text[:120]}")
h2 = config.habits()["habits"]
check(h2["steps"]["daily_target"] == 8000 and isinstance(h2["steps"]["daily_target"], int)
      and h2["sleep"]["daily_target"] == 7.5 and h2["sleep"]["schedule"][0]["days"] == ["mon", "sun"],
      "steps target int, sleep target float, schedule on a health habit")
check(config.display_name("steps") == "Walk" and "created_at" in h2["steps"], "display: is a label; new habit stamped")
check(config.habit_created_ts(h2["steps"]) and abs(config.habit_created_ts(h2["steps"]) - time.time()) < 120,
      "created_at parses back to now")
for bad in [{"source": "health", "metric": "heartbeats", "daily_target": 1},
            {"source": "health", "metric": "steps", "daily_target": 0},
            {"source": "telepathy"}]:
    r = c.put("/api/habits", json={"habits": {**config.habits()["habits"], "x": bad}})
    check(r.status_code == 400, f"bad health/source habit rejected: {r.json()['detail']}")
st = {x["key"]: x for x in c.get("/api/state").json()["habits"]}
check(st["steps"]["label"] == "Walk", "/api/state still lists health habits")

# INT-4 (my half): a Health habit said out loud is not 'not a habit'
r = cli.say(con, "walk 8000 steps")
check("Apple Health" in r and "isn't one of your habits" not in r, r)
r = cli.say(con, "go for a run")
check("Strava" in r and "5 km" in r and "≥" not in r, r)

# --- check: camera/screen/both instead of modality; aliases + looks-like generated ------------------------------
hs = config.habits()["habits"]
hs["journaling"] = {"check": "camera", "default_min": 15, "label": "Journal"}
r = c.put("/api/habits", json={"habits": hs})
j = config.habits()["habits"]["journaling"]
check(r.status_code == 200 and j["modality"] == "physical" and j["aliases"] and j["on_task_looks_like"],
      f"check: camera -> physical, aliases {j['aliases']} generated")
check(intent.parse("journaling for 10 min")["habit"] == "journaling", "generated aliases match")

# --- J3: unknown habit -> one-tap card ---------------------------------------------------------------------------
r = cli.say(con, "I want to practice guitar for 20 minutes")
check(r.startswith("Guitar isn't one of your habits yet") and "Add Guitar · 20 min" in r and "physical" not in r, r)
s = c.get("/api/habits/suggest").json()
check(s["draft"] and s["draft"]["name"] == "Guitar" and s["draft"]["minutes"] == 20 and s["card_label"] == "Add “Guitar” · 20 min"
      and s["draft"]["check"] == "camera", f"suggest (last reply) -> card: {s['card_label']}")
for text, name, chk in [("let's learn python for 30 min", "Python", "screen"), ("study spanish 45 min", "Study spanish", "both"),
                        ("time to do yoga", "Yoga", "camera")]:
    d = c.get("/api/habits/suggest", params={"text": text}).json()["draft"]
    check(d and d["name"] == name and d["check"] == chk, f"{text!r} -> {d and (d['name'], d['check'])}")
check(c.get("/api/habits/suggest", params={"text": "draw for 10"}).json()["known"] == "drawing", "known habit -> known")
r = c.post("/api/habits/add", json={"name": "Guitar", "minutes": 20, "check": "camera",
                                     "schedule": [{"days": ["tue", "thu"], "at": "18:30", "min": 20}], "start": True})
check(r.status_code == 200 and r.json()["key"] == "guitar" and r.json()["reply"].startswith("Started Guitar for 20 min"),
      f"Add + start in one tap: {r.json().get('reply')}")
g = config.habits()["habits"]["guitar"]
check(g["schedule"][0]["at"] == "18:30" and g["calendar"] is True and g["weekly_target_min"] == 40,
      "sheet's schedule saved, weekly target from schedule")
check(c.post("/api/habits/add", json={"name": "Guitar"}).status_code == 400, "duplicate add -> 400")
cli.end(con)
check("Added Reading" in cli.say(con, "add habit reading, 20 min") and
      config.habits()["habits"]["reading"]["modality"] == "physical", "typed add without the jargon")
check("checked by what's on my screen" in cli.say(con, "add habit coding, screen, 30 min"), "typed add with plain check word")

# --- J8: camera correction toast is honest ------------------------------------------------------------------------
clock = Clock()
cli.say(con, "draw for 4 minutes")
sid = db.active_session(con)["id"]
for _ in range(49):
    daemon.tick(con); clock.advance(5)
done = c.get("/api/sessions").json()[0]
check(done["score_line"] and "You were on task" in done["score_line"] and done["done_at"] == 0.7,
      f"session JSON has score_line: {done['score_line']}")
check(not JARGON.search(done["why"]), f"why line is plain: {done['why']}")
ph = [l for l in done["labels"] if l["label"] == "phone"]
r1 = c.post(f"/api/sessions/{sid}/correct", json={"ts": ph[0]["ts"], "label": "on_task"}).json()["reply"]
check(r1.startswith("Changed that moment (") and "New score:" in r1 and "from now on" not in r1, r1)
r2 = c.post(f"/api/sessions/{sid}/correct", json={"ts": ph[1]["ts"], "label": "on_task"}).json()["reply"]
check("from now on" in r2 and "twice" in r2, f"second identical fix becomes a rule, and says so: {r2}")
r3 = c.post(f"/api/sessions/{sid}/correct", json={"ts": ph[1]["ts"], "label": "on_task"}).json()["reply"]
check("nothing to change" in r3, r3)

# --- idle 'how am I doing' answers with a summary, not 'No active session' ----------------------------------------
db.add_event(con, "health", "samples", {"date": time.strftime("%Y-%m-%d"), "steps": 9120, "sleep_h": 6.0})
db.add_event(con, "health", "samples", {"date": time.strftime("%Y-%m-%d"), "steps": 9500, "sleep_h": 6.5})
r = cli.say(con, "how am I doing?")
check(r.startswith("Today:") and "Walk" in r, f"idle 'how am I doing': {r}")

# --- Health summary (INT-3 helper) ---------------------------------------------------------------------------------
rows = {x["habit"]: x for x in health.health_summary(con)}
check(rows["steps"]["today"] == 9500 and rows["steps"]["days_met"] == 1 and rows["steps"]["streak"] == 1,
      f"latest sample per day wins: {rows['steps']['line']}")
check(rows["sleep"]["days_met"] == 0 and "6.5 h of sleep last night, target 7.5 h —" in rows["sleep"]["line"], rows["sleep"]["line"])
hsum = c.get("/api/health/summary").json()
check(hsum["status"]["connected"] and "9,500 steps" in hsum["status"]["text"], hsum["status"]["text"])

# --- setup checks: plain words up front, tech behind details ---------------------------------------------------------
for x in c.get("/api/health").json()["checks"]:
    check(not JARGON.search(x["label"] + x["detail"] + x["fix"]) and "details" in x and "sentence" in x,
          f"plain setup row: {x['sentence']}")

# --- secrets.json is 0600 ---------------------------------------------------------------------------------------------
config.save_secrets(strava_client_id="123", nothing=None)
check(stat.S_IMODE(os.stat(config.SECRETS_PATH).st_mode) == 0o600 and config.secrets()["strava_client_id"] == "123",
      "secrets.json written 0600")

# --- first run: templates + wizard ---------------------------------------------------------------------------------
config.ONBOARDED_PATH.unlink(missing_ok=True)
(config.DATA_DIR / "onboarding.json").unlink(missing_ok=True)
t = c.get("/api/onboarding/templates").json()["templates"]
ids = [x["id"] for x in t]
check(ids == ["drawing", "reading", "instrument", "coding", "study", "running", "steps", "sleep", "meditate", "custom"],
      f"template cards: {ids}")
for x in t:
    check(x["how"] and x["check_text"] and not JARGON.search(json.dumps({k: x[k] for k in ("title", "blurb", "how")})),
          f"template '{x['title']}' explains itself: {x['how']}")
st = c.get("/api/onboarding").json()
check(st["onboarded"] is True, "an install with sessions counts as onboarded")
onboarding.reset()
st = c.get("/api/onboarding").json()
check(st["needs_onboarding"] and st["replay"], "'Run the welcome tour again' reopens the wizard even with history")
onboarding.mark_done("test")
(config.DATA_DIR / "onboarding.json").unlink(missing_ok=True)
config.ONBOARDED_PATH.unlink(missing_ok=True)
con.execute("DELETE FROM sessions"); con.commit()
st = c.get("/api/onboarding").json()
check(st["needs_onboarding"] and [s["id"] for s in st["steps"]][0] == "welcome"
      and "Photos stay on this Mac" in st["steps"][0]["text"], "fresh install -> wizard from Welcome")
for s in st["steps"] + st["connect"]:
    check(not JARGON.search(json.dumps(s)), f"wizard copy plain: {s['title']}")
r = c.post("/api/onboarding/habits", json={"picks": [
    {"template": "drawing", "schedule": [{"days": ["mon", "wed", "fri"], "at": "19:00", "min": 25}], "calendar": True},
    {"template": "instrument", "name": "Piano", "minutes": 15},
    {"template": "running"}, {"template": "steps", "target": 10000}, {"template": "sleep"},
    {"template": "custom", "name": "Duolingo", "check": "screen", "minutes": 10}]})
check(r.status_code == 200, r.text[:200])
hs = config.habits()["habits"]
check(set(hs) == {"drawing", "piano", "running", "steps", "sleep", "duolingo"},
      f"wizard replaces the developer's defaults: {sorted(hs)}")
check(hs["piano"]["label"] == "Piano" and "practise" not in hs["piano"]["aliases"] and hs["piano"]["default_min"] == 15
      and all(b["min"] == 15 for b in hs["piano"]["schedule"]), "instrument template named + minutes applied to plan")
check(hs["steps"]["daily_target"] == 10000 and hs["running"]["calendar"] and hs["duolingo"]["modality"] == "digital",
      "health target, strava schedule, custom screen habit")
check(all("created_at" in h for h in hs.values()), "every wizard habit has created_at (pace starts there)")
check(intent.match_habit("practise yoga for 15 minutes") is None, "'practise yoga' doesn't start piano")
check(intent.parse("piano for 10")["habit"] == "piano" and intent.parse("duolingo")["habit"] == "duolingo",
      "wizard habits are recognised when spoken")
v = {x["key"]: x for x in c.get("/api/habits/view").json()["habits"]}
check(v["drawing"]["schedule_text"] == "Mon, Wed, Fri at 19:00 · 25 min" and v["steps"]["target_text"] == "10,000 steps a day"
      and v["sleep"]["target_text"] == "7 h of sleep a night" and v["running"]["check_text"] == "Strava",
      f"habit view in plain words: {v['drawing']['schedule_text']} | {v['steps']['target_text']} | {v['sleep']['target_text']}")
check(c.post("/api/onboarding/habits", json={"picks": [{"template": "custom"}]}).status_code == 400,
      "custom without a name -> 400")
check(c.post("/api/onboarding/progress", json={"step": "connect"}).json()["step"] == "connect"
      and c.get("/api/onboarding").json()["step"] == "connect", "wizard resumes where it left off")
p = c.post("/api/onboarding/practice", json={}).json()
check(p["started"] and p["habit"] == "drawing" and "2 min" in p["reply"], f"practice: {p['reply']}")
cli.end(con)
check(c.post("/api/onboarding/done").json()["onboarded"] and c.get("/api/onboarding").json()["onboarded"], "done flag")
print("Habits + onboarding DoD passed.")
