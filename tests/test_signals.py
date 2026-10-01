"""Round 3 signals (docs/SIGNALS.md): phone batch ingest + session attach by ts, Health contract (new metrics, heart),
GET /api/phone/session, timeline hints, fusion that only LOWERS a score with a reason, signal nudges, live/status
routes (Full Disk Access degrades to a plain status), Focus Shortcuts toggled with sessions (faked), report rows."""
import datetime as dt, json, os, socket, time
from harness import Clock, check
os.environ["PHONE_HOST"] = "127.0.0.1"
s = socket.socket(); s.bind(("127.0.0.1", 0)); os.environ["PHONE_PORT"] = str(s.getsockname()[1]); s.close()
os.environ["ALIBI_FOCUS_SHORTCUTS"] = "1"                   # on, but every `shortcuts` call below is faked

import yaml
from fastapi.testclient import TestClient
from alibi import api, cli, config, db, integrations, nudges, report, signals, verifier

clock = Clock()
con = db.connect()

# --- fake Shortcuts: never the user's real ones -----------------------------------------------------------------------
CALLS = []
HAVE = {"names": "Alibi Focus On\nAlibi Focus Off\nSomething else\n"}

class P:
    def __init__(self, out="", rc=0): self.stdout, self.returncode = out, rc

def fake_shortcuts(*args, timeout=20):
    CALLS.append(args)
    return P(HAVE["names"]) if args[0] == "list" else P()
integrations._shortcuts = fake_shortcuts

# --- Health contract: new metrics, sleep stages, unknown keys kept ---------------------------------------------------
today = dt.date.fromtimestamp(clock.t).isoformat()
p = integrations.normalise_health({
    "date": today, "steps": "8,123", "distance_km": 6.2, "flights": 9, "active_kcal": "512 kcal", "exercise_min": 34,
    "stand_h": 10, "sleep": {"core_h": 4.1, "deep_h": 1.2, "rem_h": 1.6, "awake_h": 0.4, "bed": "23:40", "wake": "7:05"},
    "resting_hr": 57, "hrv_ms": 48, "resp_rate": 14.5, "mindful_min": 10, "daylight_min": 41, "headphone_db": 71,
    "workout_min": 30, "workouts": [{"type": "run", "start": "07:30", "min": 30, "km": 5.1, "avg_hr": 151}],
    "moods": [{"ts": clock.t, "valence": 0.4, "labels": ["calm"]}], "vo2max": 44.1, "BadKey!": 1, "steps_note": "x"})
check(p["steps"] == 8123 and p["distance_km"] == 6.2 and p["active_kcal"] == 512 and p["resting_hr"] == 57,
      "new Health metrics parsed (steps, distance, energy, resting HR)")
check(abs(p["sleep_h"] - 6.9) < 0.01 and p["sleep"]["bed"] == "23:40" and p["sleep"]["wake"] == "07:05",
      "sleep hours derived from stages; bed/wake kept")
check(p["vo2max"] == 44.1 and p["steps_note"] == "x" and "BadKey!" not in p, "unknown keys kept (safe names only)")
check(integrations.normalise_health({"resting_hr": 60})["resting_hr"] == 60, "a payload with only a new metric is accepted")
p2 = integrations.normalise_health({"steps": "abc", "hrv_ms": 40})
check("steps" not in p2, "junk in a known metric is dropped, never kept as a string")

# --- phone listener: secret, single rows, batches, heart, location privacy ------------------------------------------
ph = TestClient(integrations.phone_app())
key = integrations.phone_secret()
H = {"X-Alibi-Secret": key}
check(ph.post("/ingest", json={"source": "phone", "kind": "pickup"}).status_code == 401, "ingest without the key: 401")
check(ph.get("/api/phone/session").status_code == 401, "phone session without the key: 401")
r = ph.get("/api/phone/session", headers=H).json()
check(r["active"] is False and r["sync_every_s"] == integrations.IDLE_SYNC_S and r["shield"] is False,
      "no session: phone told to sync slowly, no shield")

r = ph.post("/ingest", headers=H, json={"source": "health", "kind": "samples", "payload": p})
check(r.status_code == 200 and "Resting heart rate 57 bpm" in r.json()["message"], f"health samples saved: {r.json().get('message')}")
r = ph.post("/ingest", headers=H, json={"batch": [{"source": "phone", "kind": "x"}] * 501})
check(r.status_code == 413, "batch over 500 rows refused with 413")

# a session: C++ (digital), 30 min
out = cli.start_habit(con, "cpp", 30)
sess = db.active_session(con)
check(sess is not None and sess["habit"] == "cpp", f"session started: {out}")
for _ in range(50):
    if integrations._focus["threads"] and not integrations._focus["threads"][-1].is_alive():
        break
    time.sleep(0.02)
check(("run", "Alibi Focus On") in CALLS, "session start runs the 'Alibi Focus On' Shortcut (it exists)")
r = ph.get("/api/phone/session", headers=H).json()
check(r["active"] and r["habit"] == "cpp" and r["shield"] and r["sync_every_s"] == integrations.SESSION_SYNC_S
      and r["ends_at"] == sess["ends_at"], "live session: phone told to shield + sync every few minutes")

t0 = sess["started_at"]
for i in range(60):                                       # 30 min of on-task editor windows
    db.add_event(con, "laptop", "window", {"app": "Cursor", "title": "main.cpp — learncpp"}, ts=t0 + i * 30 + 1)
clock.advance(29 * 60)                                    # the phone syncs near the end of the session
batch = [
    {"source": "phone", "kind": "screentime", "ts": t0 + 600, "payload": {"app": "Instagram", "minutes": 5, "threshold_min": 5}},
    {"source": "phone", "kind": "screentime", "ts": t0 + 900, "payload": {"app": "Instagram", "minutes": 10, "threshold_min": 5}},
    {"source": "phone", "kind": "screentime", "ts": t0 + 1200, "payload": {"app": "Instagram", "minutes": 15, "threshold_min": 5}},
    {"source": "phone", "kind": "pickup", "ts": (t0 + 300) * 1000, "payload": {}},           # ms timestamps accepted
    {"source": "phone", "kind": "motion", "ts": t0 + 1500,
     "payload": {"start": t0 + 1300, "end": t0 + 1340, "state": "walking", "confidence": "high"}},
    {"source": "phone", "kind": "location", "ts": t0 + 100, "payload": {"at_home": True, "lat": 51.5, "lon": -0.1}},
    {"source": "phone", "kind": "shield", "ts": t0 + 5, "payload": {"on": True, "apps": 4}},
    {"source": "health", "kind": "heart", "payload": {"samples": [[t0 + 60, 72], [t0 + 120, 75], [t0 - 7200, 60], [t0 + 5, 999]]}},
    {"source": "phone", "kind": "location", "payload": {"lat": 1}},                           # no at_home -> rejected
    {"source": "phone", "kind": "pickup", "ts": clock.t + 3600, "payload": {}},               # future: clamped to now
]
r = ph.post("/ingest", headers=H, json={"batch": batch})
j = r.json()
check(r.status_code == 200 and j["saved"] == 9 and len(j["rejected"]) == 1 and j["session"]["active"],
      f"batch: 9 saved, 1 rejected, session info returned ({j['kinds']})")
loc = [json.loads(x[0]) for x in con.execute("SELECT payload FROM events WHERE source='phone' AND kind='location'")]
check(loc == [{"at_home": True}], "location keeps only at_home — coordinates never stored")
pk = con.execute("SELECT ts, session_id FROM events WHERE source='phone' AND kind='pickup'").fetchone()
check(abs(pk["ts"] - (t0 + 300)) < 1 and pk["session_id"] == sess["id"], "ms timestamp normalised; row attached by ts")
fut = con.execute("SELECT MAX(ts) FROM events WHERE source='phone' AND kind='pickup'").fetchone()[0]
check(fut <= clock.t + 300, "a future timestamp is clamped to now (+5 min)")
hearts = con.execute("SELECT session_id, payload FROM events WHERE source='health' AND kind='heart' ORDER BY ts").fetchall()
check(len(hearts) == 2 and hearts[0]["session_id"] is None and hearts[1]["session_id"] == sess["id"]
      and len(json.loads(hearts[1]["payload"])["samples"]) == 2,
      "heart samples split by session (one before, two during); a 999 bpm reading dropped")

# Mac rows (normally written by mac_signals) for the timeline
signals.store(con, "mac", "notifications", {"app": "Slack", "count": 3, "phone": False, "window_s": 300}, ts=t0 + 400)
signals.store(con, "mac", "meeting", {"camera": True, "mic": True, "app": "zoom.us"}, ts=t0 + 450)
signals.store(con, "mac", "git", {"repo": "alibi", "commits": 2, "files": 3, "insertions": 40, "deletions": 4}, ts=t0 + 1700)
signals.store(con, "mac", "presence", {"idle_s": 30, "locked": False, "display_asleep": False}, ts=t0 + 30)

clock.advance(60 + 2)
# a phone row that only arrives after the session ended still lands on it (writer passes ts; the store decides)
check(signals.store(con, "phone", "pickup", {"ts": t0 + 1000}, ts=t0 + 1000) == sess["id"], "late row attached by its ts")
check(signals.store(con, "phone", "pickup", {"ts": t0 - 3600}, ts=t0 - 3600) is None, "row outside any session: no session")

tl = signals.timeline(con, sess)
kinds = {(x["source"], x["kind"]): x for x in tl}
check(tl == sorted(tl, key=lambda x: x["ts"]), "timeline is ordered")
check(kinds[("phone", "screentime")]["verdict_hint"] == "off_task" and "Instagram +5 min" in kinds[("phone", "screentime")]["text"],
      "screen time during a desk session -> off_task, as a delta of the day's cumulative minutes")
check(kinds[("phone", "pickup")]["verdict_hint"] == "off_task", "pickup -> off_task")
check(kinds[("phone", "motion")]["verdict_hint"] == "absent" and "walking" in kinds[("phone", "motion")]["text"], "walking -> absent")
check(kinds[("mac", "meeting")]["verdict_hint"] == "neutral" and "zoom" in kinds[("mac", "meeting")]["text"], "meeting -> neutral, labelled")
check(kinds[("mac", "notifications")]["verdict_hint"] == "neutral", "notifications -> neutral context")
check(kinds[("health", "heart")]["verdict_hint"] == "neutral" and "74 bpm" in kinds[("health", "heart")]["text"],
      "heart -> neutral on the timeline (avg 74 bpm)")
check(("mac", "presence") not in kinds and not any(x["kind"] == "app" for x in tl), "active Mac / app lifecycle rows stay off")
check(all(set(x) == {"ts", "source", "kind", "verdict_hint", "text"} for x in tl), "timeline rows match the contract shape")

# --- fusion: the editor looked perfect, but the phone says Instagram for 15 min -> lowered, with a reason -----------
CALLS.clear()
cli.end(con)
done = db.get_session(con, sess["id"])
st = verifier.stats(con, done)
voice = verifier.voice(con, done)
check(done["on_task_ratio"] <= 0.51 and done["verdict"] == "partial",
      f"score capped by phone screen time: {done['on_task_ratio']:.0%} -> {done['verdict']}")
check("Instagram" in (st["signals_reason"] or "") and "lowered because" in st["why"], f"why says so: {st['why']}")
check("Instagram" in voice, f"the verdict voice names it: {voice}")
cap = signals.last_cap(con, sess["id"])
check(cap and cap["from"] > cap["to"] and cap["phone_s"] == 900, "cap recorded with from/to and 15 min of phone")
for _ in range(50):
    if integrations._focus["threads"] and not integrations._focus["threads"][-1].is_alive():
        break
    time.sleep(0.02)
check(("run", "Alibi Focus Off") in CALLS and not integrations.state().get("mac_focus_on"),
      "session end runs 'Alibi Focus Off'")

# never raises: a session with a weak score + phone 'on_task' git signals stays as low as the evidence says
clock.advance(600)
cli.start_habit(con, "internships", 10)
s2 = db.active_session(con)
for i in range(20):
    db.add_event(con, "laptop", "window", {"app": "Google Chrome", "title": "Funny cats - YouTube - Google Chrome"},
                 ts=s2["started_at"] + i * 30 + 1)
signals.store(con, "mac", "git", {"repo": "alibi", "commits": 9, "files": 9, "insertions": 900, "deletions": 0},
              ts=s2["started_at"] + 60)
clock.advance(10 * 60 + 2)
cli.end(con)
d2 = db.get_session(con, s2["id"])
check(d2["on_task_ratio"] == 0 and signals.last_cap(con, s2["id"]) is None, "signals never raise a score (git can't rescue YouTube)")

# a clean session with no off-task signals is untouched
clock.advance(600)
cli.start_habit(con, "cpp", 10)
s3 = db.active_session(con)
for i in range(20):
    db.add_event(con, "laptop", "window", {"app": "Cursor", "title": "vec.cpp — learncpp"}, ts=s3["started_at"] + i * 30 + 1)
clock.advance(10 * 60 + 2)
cli.end(con)
d3 = db.get_session(con, s3["id"])
check(d3["verdict"] == "done" and d3["on_task_ratio"] > 0.95 and signals.last_cap(con, s3["id"]) is None,
      "no phone/Mac drift -> score untouched")

# re-scoring after a correction re-runs the fusion (cap stays honest)
verifier.finalise(con, db.get_session(con, sess["id"]), keep_end=True)
check(db.get_session(con, sess["id"])["on_task_ratio"] == done["on_task_ratio"], "re-finalise gives the same capped score")

# --- signal nudges: the camera says on task, the phone says TikTok for 10 min ----------------------------------------
clock.advance(600)
cli.start_habit(con, "drawing", 25)
s4 = db.active_session(con)
for i in range(6):
    db.add_event(con, "camera", "label", {"label": "on_task", "note": "pen on paper"}, session_id=s4["id"],
                 ts=s4["started_at"] + i * 60 + 5)
check(nudges.check(con, s4) is None, "no drift yet -> no nudge")
clock.advance(500)
ph.post("/ingest", headers=H, json={"batch": [
    {"source": "phone", "kind": "screentime", "ts": s4["started_at"] + 180, "payload": {"app": "TikTok", "minutes": 5}},
    {"source": "phone", "kind": "screentime", "ts": s4["started_at"] + 480, "payload": {"app": "TikTok", "minutes": 10}}]})
txt = nudges.check(con, s4)
check(txt and "Your phone says TikTok for 10 min" in txt and "drawing" in txt, f"phone nudge: {txt}")
n = nudges.nudges_for(con, s4["id"])[-1]["payload"]
check(n["from"] == "signals" and n["label"] == "phone", "nudge recorded as from signals")
check(nudges.check(con, s4) is None, "cooldown holds for signal nudges too")
clock.advance(nudges.cooldown_s() + 1)
ph.post("/ingest", headers=H, json={"source": "phone", "kind": "motion", "ts": clock.t,
                                    "payload": {"start": clock.t - 400, "end": clock.t, "state": "automotive"}})
txt2 = nudges.check(con, s4)
check(txt2 and "driving" in txt2 and "Second time" in txt2, f"motion nudge escalates: {txt2}")

# --- routes ------------------------------------------------------------------------------------------------------------
c = TestClient(api.app)
r = c.get(f"/api/signals?session={sess['id']}").json()
check(r["timeline"] and r["cap"] and r["off_s"]["phone"] == 900, "GET /api/signals?session=ID: timeline + cap + off stretches")
check(c.get("/api/signals?session=99999").status_code == 404, "unknown session: 404")
check(c.get("/api/signals?day=nope").status_code == 400, "bad day: 400 with a plain message")
r = c.get(f"/api/signals?day={dt.date.fromtimestamp(t0).isoformat()}").json()
sm = r["summary"]
check(sm["screentime"]["apps"][0] == {"app": "Instagram", "minutes": 15} and sm["pickups"] >= 2
      and sm["notifications"]["total"] == 3 and sm["heart"]["avg"] in (69, 74) and sm["mac"]["commits"] == 11,
      f"day summary: screen time, pickups, notifications, heart, commits ({sm['screentime']['total_min']} min phone)")
lv = c.get("/api/signals/live").json()["signals"]
check("phone.screentime" in lv and "health.heart" in lv and lv["phone.motion"]["fresh"] is True
      and lv["phone.motion"]["age_s"] >= 0, "GET /api/signals/live: last value per source/kind + freshness")

from alibi import mac_signals
real_status = mac_signals.status
mac_signals.status = lambda: {"sense": "missing — run scripts/build_native.sh", "full_disk_access": "needs Full Disk Access",
                              "notifications": "needs Full Disk Access", "focus": "unknown (needs Full Disk Access)"}
st = c.get("/api/signals/status").json()
mac_signals.status = real_status
by = {x["key"]: x for x in st["sources"]}
check(by["mac.notifications"]["state"] == "ok", "notifications flowing (recent rows) wins over a stale permission read")
check(by["mac.focus"]["state"] == "needs_permission" and "Full Disk Access" in by["mac.focus"]["text"],
      "Mac Focus without Full Disk Access: 'needs Full Disk Access', no crash")
check(by["phone.screentime"]["flowing"] and by["phone.location"]["flowing"], "phone sources flowing")
check(by["phone.listener"]["state"] == "missing" and "Setup" in by["phone.listener"]["fix"], "listener off -> plain fix")
check(by["mac.focus_shortcuts"]["flowing"], "Focus Shortcuts found")
check(by["mac.media"]["state"] == "missing" and by["mac.media"]["fix"], "missing Mac source has a fix")
check(st["text"].startswith(f"{len(st['flowing'])} of"), f"status headline: {st['text'][:90]}")

# Focus: without the Shortcuts nothing runs; a cancelled session still turns it off (sweep)
HAVE["names"] = "Other\n"
integrations._focus["checked"] = 0
CALLS.clear()
check(integrations.set_mac_focus(True) is False and ("run", "Alibi Focus On") not in CALLS, "no Shortcuts -> nothing runs")
HAVE["names"] = "Alibi Focus On\nAlibi Focus Off\n"
integrations._focus["checked"] = 0
cli.end(con)
for t in integrations._focus["threads"]:                  # one Focus run at a time: let the session-end one finish
    t.join(5)
integrations.set_state(mac_focus_on=True)
CALLS.clear()
integrations.tick(con, clock.t)
integrations._focus["threads"][-1].join(5)
check(("run", "Alibi Focus Off") in CALLS, "Focus left on with no live session -> turned off by the tick")
os.environ["ALIBI_FOCUS_SHORTCUTS"] = "0"
check(integrations.focus_shortcuts()["enabled"] is False and integrations.set_mac_focus(True) is False,
      "ALIBI_FOCUS_SHORTCUTS=0 disables it")

# --- report: health habits on the new metrics -------------------------------------------------------------------------
cfg = yaml.safe_load(open(os.environ["ALIBI_HABITS"]))
cfg["habits"]["heart"] = {"source": "health", "metric": "resting_hr", "daily_target": 60, "display": "Resting HR"}
cfg["habits"]["daylight"] = {"source": "health", "metric": "daylight_min", "daily_target": 30}
yaml.safe_dump(cfg, open(os.environ["ALIBI_HABITS"], "w"))
rep = report.build_json(clock.t)
hr = {x["habit"]: x for x in rep["health"]}
check(hr["heart"]["today_met"] is True and hr["heart"]["lower_is_better"] and "or less" in hr["heart"]["text"],
      f"resting HR 57 meets a ≤ 60 target: {hr['heart']['text']}")
check(hr["daylight"]["today_met"] is True and hr["daylight"]["today_text"] == "41 min", "daylight 41 min ≥ 30")
check("resting heart rate ≤ 60 bpm" in rep["table"], "report table says ≤ for lower-is-better metrics")
check(rep["signals"] and "screentime" in rep["signals"], "report carries today's signal summary")

print("Signals DoD passed.")
