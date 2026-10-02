"""State DoD: /api/state gains plan_today, phrase, agent and clients with the 12 old keys untouched;
Pinch's moments for a habits save, an agent brief and the day's last block; a timely brief drops down on the island
once per slot (never mid-session); habits saves come back with a receipt and one island alert. Fake clock, test data."""
import datetime as dt, os, time
# Whatever .env says for recording takes (load_dotenv never overrides what's already set):
os.environ.update(ALIBI_BRIEF_ALERTS="all", ALIBI_AGENT_HOST="DGX Spark", REPORT_HOUR="22", CHECK_HOURS="12,16,20",
                  MORNING_AT="07:30")
from harness import Clock, check
from fastapi.testclient import TestClient
from alibi import api, calendar_sync, cli, config, db, health, integrations, notify, pinch, routes_agent

con = db.connect()
c = TestClient(api.app)
clock = Clock()
day = dt.date.fromtimestamp(time.time())
at = lambda h, m=0, s=0: dt.datetime.combine(day, dt.time(h, m, s)).timestamp()
DAY = config.DAYS[day.weekday()]
clock.t = at(12)
OLD = {"now", "session", "alert", "habits", "witness", "witness_label", "text_model", "daemon", "today",
       "recent_verdict", "status_text", "pinch"}
NEW = {"plan_today", "phrase", "agent", "clients"}
ITEM = {"key", "habit", "label", "at", "end_at", "start", "end", "minutes", "check", "glyph", "status", "verdict",
        "ratio", "session_id", "startable", "once", "moved", "unplanned"}
words_ok = lambda s: bool(s) and len(s.split()) <= 12 and "!" not in s
alerts = lambda kind: [a for a in notify.recent_alerts(1000) if a.get("kind") == kind]
state = lambda **h: c.get("/api/state", headers=h).json()

# --- 1. the old keys stay, four new ones arrive; nothing scheduled yet ----------------------------------------------
st = state(**{"X-Alibi-Client": "island"})
check(OLD | NEW == set(st), f"/api/state: the 12 old keys plus plan_today, phrase, agent, clients ({sorted(st)})")
check(set(st["pinch"]) == {"mood", "event", "seq", "age_s", "line", "moment"}, "pinch keeps its 5 keys, adds moment")
habits = config.habits()["habits"]
check(st["habits"] == [{"key": k, "label": config.display_name(k), "modality": h.get("modality", "strava" if
                        h.get("source") else "?"), "default_min": h.get("default_min", 25)} for k, h in habits.items()]
      and st["today"] == api._today(con, habits) and st["status_text"] == "Idle — nothing declared"
      and st["daemon"] == {"up_since": api.STARTED} and st["session"] is None and st["witness"] == "mock",
      "old keys keep their values")
pt = st["plan_today"]
check(pt["scheduled"] is False and pt["total"] == 0 and pt["left"] == [] and pt["next"] is None
      and pt["summary"] == "No set times yet." and pt["away"] is None and pt["date"] == day.isoformat(),
      f"no schedules: scheduled false, nothing planned ({pt['summary']})")
ph = st["phrase"]
check(ph["situation"] == "unscheduled" and ph["source"] == "rules" and words_ok(ph["text"]) and ph["slot"] is None,
      f"phrase: unscheduled, from the rules: {ph['text']!r}")
check(st["agent"] == {"last_seen": None, "ago_s": None, "online": False, "host": "DGX Spark"},
      "agent: never seen, offline, host DGX Spark")
check(st["clients"]["island_ago_s"] == 0.0 and st["clients"]["dashboard_ago_s"] is None,
      f"clients: the island just polled ({st['clients']})")
check(set(pinch.from_db(con)) == {"mood", "event", "seq", "age_s", "line", "moment"}, "the iPhone's pinch still builds")

# --- 2. blocks at 09:00, 15:00 and 18:00 -> missed, next, later ----------------------------------------------------
hs = config.habits()["habits"]
hs["math"]["schedule"] = [{"days": [DAY], "at": "09:00", "min": 30}]
hs["drawing"]["schedule"] = [{"days": [DAY], "at": "15:00", "min": 25}]
hs["cpp"]["schedule"] = [{"days": [DAY], "at": "18:00", "min": 30}]
health.save_habits(hs)                           # a direct save: no island alert
check(not alerts("habits_saved"), "health.save_habits called directly raises no habits_saved alert")
st = state()
pt = st["plan_today"]
check([(x["habit"], x["status"]) for x in pt["missed"]] == [("math", "missed")], "09:00 math is missed")
check([(x["habit"], x["status"]) for x in pt["left"]] == [("drawing", "next"), ("cpp", "later")],
      "15:00 drawing is next, 18:00 C++ later")
n = pt["next"]
check(n["key"] == f"drawing@{day}T15:00" and n["at"] == "15:00" and n["end_at"] == "15:25" and n["minutes"] == 25
      and n["start"] == at(15) and n["glyph"] == "camera" and n["startable"] and n["session_id"] is None,
      f"next is the 15:00 block ({n['key']})")
check(all(set(x) == ITEM for k in ("left", "done", "missed", "checking") for x in pt[k]), "every item has the shape")
check({x["habit"]: x["glyph"] for x in pt["left"] + pt["missed"]} == {"drawing": "camera", "cpp": "laptop",
                                                                      "math": "camera"}, "glyphs by check")
check(pt["left_min"] == 55 and pt["total"] == 3 and pt["kept"] == 0 and pt["scheduled"] is True,
      f"left_min 25 + 30, total 3 ({pt['left_min']}, {pt['total']})")
check(pt["summary"] == "2 left: drawing at 15:00 and C++ at 18:00.", f"summary: {pt['summary']}")
ph = st["phrase"]
check(ph["situation"] == "next" and ph["source"] == "rules" and words_ok(ph["text"]), f"phrase: next: {ph['text']}")
clock.t = at(12, 5)
p05 = state()["phrase"]["text"]
clock.t = at(12, 55)
check(state()["phrase"]["text"] == p05 == ph["text"], "the phrase holds for the whole hour")
cal = c.get("/api/calendar/plan", params={"days": 1}).json()
check({b["key"] for b in cal.get("blocks", [])} >= {x["key"] for x in pt["left"] + pt["missed"]},
      "the same keys /api/calendar/plan uses")

# --- 3. live -> done -> the day's last block ---------------------------------------------------------------------
clock.t = at(15, 2)
cli.start(con, "draw for 25 minutes")
sid = db.active_session(con)["id"]
st = state()
pt = st["plan_today"]
live = pt["left"][0]
check(live["status"] == "live" and live["session_id"] == sid and live["habit"] == "drawing",
      "a session inside the block's window makes it live")
check(pt["next"]["habit"] == "cpp" and pt["next"]["status"] == "next" and pt["left_min"] == 25 + 30,
      f"next is C++; left_min counts the live session's minutes left ({pt['left_min']})")
check(st["pinch"]["moment"] == "started" and st["phrase"]["situation"] == "live"
      and st["phrase"]["text"] == "After this, C++ at 18:00.", f"live phrase: {st['phrase']['text']}")
for i in range(25):
    db.add_event(con, "camera", "label", {"label": "on_task", "note": "pen on paper"}, session_id=sid,
                 ts=at(15, 2, 30) + i * 60)
clock.t = at(15, 27)
cli.end(con)
v = alerts("verdict")[-1]
check(v["session_id"] == sid and v["verdict"] == "done", f"the session ends done ({v['verdict']})")
st = state()
pt = st["plan_today"]
d = pt["done"][0]
check(d["status"] == "done" and d["verdict"] == "done" and d["session_id"] == sid and isinstance(d["ratio"], float)
      and d["ratio"] > 0.9, f"the block is done with its verdict and ratio ({d['ratio']})")
check(st["pinch"]["moment"] == "verdict" and st["pinch"]["event"] == "celebrate",
      "C++ is still left: a plain verdict")
calendar_sync.skip(f"cpp@{day}T18:00")
st = state()
pt = st["plan_today"]
check(pt["left"] == [] and [x["status"] for x in pt["missed"]] == ["missed", "skipped"] and pt["kept"] == 1
      and pt["summary"] == "Nothing left today. 1 of 3 kept.", f"nothing left: {pt['summary']}")
pn = st["pinch"]
check(pn["moment"] == "plan_done" and pn["event"] == "celebrate" and pn["seq"] == int(v["ts"] * 1000)
      and pn["line"].endswith("That was today's last block.") and words_ok(pn["line"]),
      f"plan_done: the verdict's clip and seq, line {pn['line']!r}")
check(st["phrase"]["situation"] == "some_kept" and words_ok(st["phrase"]["text"]),
      f"phrase: some kept: {st['phrase']['text']}")

# --- 4. PUT /api/habits: the receipt, one island alert, the plan on the next poll ---------------------------------
clock.t = at(16)
before = c.get("/api/habits").json()["habits"]
m = c.get("/api/habits").json()["habits"]
m["internships"]["schedule"] = [{"days": [DAY], "at": "16:30", "min": 30}]
n0 = len(alerts("habits_saved"))
r = c.put("/api/habits", json={"habits": m}, headers={"X-Alibi-Client": "dashboard"})
j = r.json()
sv = j.get("saved") or {}
check(r.status_code == 200 and {"habits", "verdict", "saved"} <= set(j)
      and j["habits"]["internships"]["schedule"][0]["at"] == "16:30", "PUT returns the config plus saved")
check(sv["changes"] == [{"habit": "internships", "label": "Internships", "what": ["days"]}],
      f"saved.changes: {sv['changes']}")
check(sv["line"] == f"Noted. Internships is on {DAY.capitalize()} at 16:30." and words_ok(sv["line"]),
      f"saved.line: {sv['line']!r}")
new = alerts("habits_saved")
a = new[-1]
check(len(new) == n0 + 1 and a["text"] == sv["line"] and a["id"] == sv["alert_id"] and a["via"] == "web"
      and a["habit"] == "internships" and a["habit_label"] == "Internships" and a["minutes"] == 30
      and a["change"] == "days" and a["changes"] == sv["changes"], "exactly one habits_saved alert, the same line")
check(a["actions"] == [{"label": "Start 30 min", "say": "internships for 30 minutes"}, {"label": "OK", "dismiss": True}],
      f"actions: Start 30 min + OK ({a['actions']})")
check(any(x["key"] == f"internships@{day}T16:30" for x in sv["plan_today"]["left"]), "saved.plan_today has the block")
st = state()
check(st["plan_today"]["next"]["key"] == f"internships@{day}T16:30", "the next /api/state shows it as next")
check(st["pinch"]["moment"] == "habits_saved" and st["pinch"]["event"] == "surprise"
      and st["pinch"]["line"] == sv["line"], "Pinch nods with the same line")
check(st["alert"]["kind"] == "habits_saved" and st["alert"]["habit_label"] == "Internships", "the island gets it")
r2 = c.put("/api/habits", json={"habits": m}, headers={"X-Alibi-Client": "dashboard"}).json()["saved"]
check(r2["changes"] == [] and r2["line"] is None and r2["alert_id"] is None and len(alerts("habits_saved")) == n0 + 1,
      "the same PUT again: no changes, no alert")
u = c.put("/api/habits", json={"habits": before}, headers={"X-Alibi-Client": "island", "X-Alibi-Intent": "undo"})
uj = u.json()["saved"]
check(u.status_code == 200 and uj["line"] == "Back as it was." and alerts("habits_saved")[-1]["text"] == uj["line"]
      and alerts("habits_saved")[-1]["via"] == "island" and "schedule" not in config.habits()["habits"]["internships"],
      f"undo: {uj['line']!r}")
bad = {**before, "drawing": {**before["drawing"], "schedule": [{"days": [DAY], "at": "25:00", "min": 5}]}}
n1 = len(alerts("habits_saved"))
r = c.put("/api/habits", json={"habits": bad})
check(r.status_code == 400 and "isn't a time" in r.json()["detail"] and len(alerts("habits_saved")) == n1,
      "a bad time is still a plain 400, and no alert")
two = {**before, "math": {**before["math"], "default_min": 40}, "cpp": {**before["cpp"], "calendar": False}}
s2 = c.put("/api/habits", json={"habits": two}).json()["saved"]
a2 = alerts("habits_saved")[-1]
check(s2["line"] == "Noted. 2 habits changed; the plan follows." and a2["habit"] is None
      and a2["habit_label"] == "Habits" and a2["change"] == "several" and a2["via"] == "api"
      and a2["actions"] == [{"label": "OK", "dismiss": True}], f"two habits at once: {s2['line']!r}")
c.put("/api/habits", json={"habits": before})
days2 = [DAY, config.DAYS[(day.weekday() + 1) % 7]]
ed = {**before, "drawing": {**before["drawing"], "label": "Drawing", "phone_shield": True, "calendar": True,
                            "schedule": [{"days": days2, "at": "15:00", "min": 25}]}}     # the editor's toEntry()
s3 = c.put("/api/habits", json={"habits": ed}, headers={"X-Alibi-Client": "dashboard"}).json()["saved"]
check(s3["changes"] == [{"habit": "drawing", "label": "Drawing", "what": ["days"]}]
      and s3["line"] == f"Noted. Drawing is on {pinch.days_text(days2)} at 15:00.",
      f"an editor save that spells out label, calendar and phone_shield only reports the new day: {s3['line']!r}")
c.put("/api/habits", json={"habits": before})

# --- 5. POST /api/habits/add -----------------------------------------------------------------------------------------
n0 = len(alerts("habits_saved"))
r = c.post("/api/habits/add", json={"name": "Harp", "minutes": 20, "check": "camera", "start": True}).json()
check(r["reply"].startswith("Started Harp") and r["saved"]["alert_id"] is None and len(alerts("habits_saved")) == n0
      and r["saved"]["changes"] == [{"habit": "harp", "label": "Harp", "what": ["added"]}],
      "add with start: true raises no habits_saved alert (the session start says it)")
cli.cancel(con, force=True)
r = c.post("/api/habits/add", headers={"X-Alibi-Client": "dashboard"},
           json={"template": "instrument", "name": "Piano", "minutes": 20, "check": "camera", "calendar": True,
                 "schedule": [{"days": ["tue", "thu"], "at": "21:00", "min": 20}]})
pj = r.json()
p = config.habits()["habits"]["piano"]
check(r.status_code == 200 and pj["key"] == "piano" and p["weekly_target_min"] == 40 and p["label"] == "Piano",
      "Piano via the instrument template, Tue+Thu 20 min: key piano, goal 40")
check(pj["saved"]["line"] == "Noted. Piano is on Tue and Thu at 21:00." and len(alerts("habits_saved")) == n0 + 1
      and alerts("habits_saved")[-1]["id"] == pj["saved"]["alert_id"] and alerts("habits_saved")[-1]["via"] == "web",
      f"add without start: one alert ({pj['saved']['line']!r})")
r = c.post("/api/habits/add", json={"name": "Guitar", "minutes": 20, "check": "camera", "weekly_target_min": 55,
                                    "phone_shield": False})
g = config.habits()["habits"]["guitar"]
check(r.status_code == 200 and g["weekly_target_min"] == 55 and g["phone_shield"] is False
      and len(alerts("habits_saved")) == n0 + 2, "weekly_target_min 55 and phone_shield false are stored")
check(c.post("/api/habits/add", json={"name": "Piano"}).status_code == 400 and len(alerts("habits_saved")) == n0 + 2,
      "a duplicate add is still a 400, and no alert")

# --- 6. agent briefs -> one island alert per timely slot ------------------------------------------------------------
TOKEN = routes_agent.agent_token()
H = {"X-Alibi-Agent-Token": TOKEN}
tail = TestClient(integrations.phone_app(), client=("100.100.100.100", 5000))  # the Spark, on the tailnet
clock.t = at(17, 5)
slot = f"{day}-risk-17"
b1 = {"idempotency_key": "w1-1", "slot": slot, "kind": "risk", "items": [], "links": [],
      "model": "nvidia/nemotron-3-super-120b-a12b", "tools_used": ["context"],
      "text": "**Drawing** is 30 min behind this week! 19:00 tomorrow is free. Piano fits after that."}
n0 = len(alerts("brief"))
r = tail.post("/api/agent/brief", headers=H, json=b1)
check(r.status_code == 200 and r.json()["shown_as"] == "agent", "a timely brief is stored and shown")
bs = alerts("brief")
a = bs[-1]
check(len(bs) == n0 + 1 and a["source"] == "nemoclaw" and a["via"] == "nemoclaw" and a["habit_label"] == "Your agent"
      and a["slot"] == slot and a["digest_kind"] == "risk" and a["source_line"] == "DGX Spark · Nemotron 3 Super",
      f"one brief alert: {a.get('habit_label')} · {a.get('source_line')}")
check(a["text"] == "Drawing is 30 min behind this week. 19:00 tomorrow is free." and len(a["text"]) <= 160
      and not {"habit", "minutes", "start", "end", "label"} & set(a)
      and a["actions"] == [{"label": "Got it", "dismiss": True}, {"label": "Open dashboard", "url": "/#agent"}],
      f"its text is the first two sentences, cleaned: {a['text']!r}")
st = state()
check(st["pinch"]["moment"] == "brief" and st["pinch"]["event"] == "connected" and st["pinch"]["mood"] == "reading"
      and st["pinch"]["line"] == "A note from your agent.", "Pinch: connected, reading, 'A note from your agent.'")
ph = st["phrase"]
check(ph["source"] == "agent" and ph["text"] == "Drawing is 30 min behind this week." and ph["slot"] == slot
      and ph["kind"] == "risk" and ph["ts"] == at(17, 5), f"the phrase is the brief's first sentence: {ph['text']!r}")
check(st["agent"]["online"] and st["agent"]["ago_s"] == 0, "agent: online, just seen")
r = tail.post("/api/agent/brief", headers=H, json=b1)
check(r.headers.get("X-Alibi-Replay") == "1" and len(alerts("brief")) == n0 + 1, "a replay raises none")
r = tail.post("/api/agent/brief", headers=H, json={**b1, "idempotency_key": "w1-2", "text": "Again."})
check(r.json()["shown_as"] == "agent" and len(alerts("brief")) == n0 + 1, "a second key for the same slot raises none")
stale = {**b1, "idempotency_key": "w1-3", "slot": f"{day - dt.timedelta(days=2)}-morning", "kind": "morning",
         "text": "Old news from two days ago."}
r = tail.post("/api/agent/brief", headers=H, json=stale)
check(r.json()["shown_as"] == "stored" and len(alerts("brief")) == n0 + 1, "a stale brief raises none")
ph = state()["phrase"]
check(ph["source"] == "agent" and ph["text"] == "Again." and ph["slot"] == slot,
      f"a late (stored) brief never becomes the phrase; the newest shown one stays ({ph['text']!r})")
clock.t = at(17, 5, 40)
st = state()
check(st["pinch"]["mood"] == "reading" and st["pinch"]["line"] == "Reading your agent's note.",
      "40 s later Pinch is still reading")
clock.t = at(17, 6, 40)
check(state()["pinch"]["mood"] == "idle", "after 90 s the reading mood ends")
clock.t = at(17, 10)
cli.start(con, "draw for 5 minutes")
clock.t = at(17, 12)
cli.end(con)
check(state()["phrase"]["source"] == "rules", "once a session ends after the brief, the phrase is the rules' again")
clock.t = at(20, 3)
cli.start(con, "draw for 25 minutes")
r = tail.post("/api/agent/brief", headers=H, json={**b1, "idempotency_key": "w1-4", "slot": f"{day}-checkpoint-20",
                                                   "kind": "checkpoint"})
check(r.json()["shown_as"] == "agent" and len(alerts("brief")) == n0 + 1 and db.active_session(con),
      "a brief during a live session is stored, not shown")
cli.cancel(con, force=True)
os.environ["ALIBI_BRIEF_ALERTS"] = "off"
r = tail.post("/api/agent/brief", headers=H, json={**b1, "idempotency_key": "w1-5", "slot": f"{day}-risk-20"})
check(r.json()["shown_as"] == "agent" and len(alerts("brief")) == n0 + 1, "ALIBI_BRIEF_ALERTS=off raises none")
os.environ["ALIBI_BRIEF_ALERTS"] = "scheduled"
clock.t = at(21, 3)
tail.post("/api/agent/brief", headers=H, json={**b1, "idempotency_key": "w1-6", "slot": f"{day}-risk-21"})
check(len(alerts("brief")) == n0 + 1, "scheduled: a heartbeat risk brief raises none")
clock.t = at(22, 3)
night = {**b1, "idempotency_key": "w1-7", "slot": f"{day}-night", "kind": "night", "model": "other/model"}
tail.post("/api/agent/brief", headers=H, json=night)
check(len(alerts("brief")) == n0 + 2 and alerts("brief")[-1]["source_line"] == "DGX Spark",
      "scheduled: the night brief raises one; an unknown model shows just the host")
os.environ["ALIBI_BRIEF_ALERTS"] = "all"

# --- 7. GET /api/briefs ----------------------------------------------------------------------------------------------
br = c.get("/api/briefs", params={"limit": 5}).json()["briefs"]
check([x["slot"] for x in br] == [f"{day}-night", f"{day}-risk-21", f"{day}-risk-20", f"{day}-checkpoint-20",
                                  stale["slot"]], f"newest first: {[x['slot'] for x in br]}")
check(all({"ts", "slot", "kind", "text", "via", "model", "tools_used", "shown_as", "age_s"} <= set(x)
          and "idempotency_key" not in x and "links" not in x for x in br)
      and br[0]["shown_as"] == "agent" and br[-1]["shown_as"] == "stored" and br[0]["age_s"] == 0
      and br[1]["age_s"] == 3600, "rows carry shown_as and age_s, never the idempotency key or links")
check(len(c.get("/api/briefs", params={"limit": 0}).json()["briefs"]) == 1
      and len(c.get("/api/briefs", params={"limit": 999}).json()["briefs"]) == 7, "limit is clamped to 1–20")

# --- 7b. a habits save after the brief is newer news: the phrase goes back to the rules (and the new plan) -----------
ph = state()["phrase"]
check(ph["source"] == "agent" and ph["slot"] == f"{day}-night", f"22:03: the night brief is the phrase ({ph['text']!r})")
clock.t = at(22, 4)
same = c.put("/api/habits", json={"habits": c.get("/api/habits").json()["habits"]}).json()["saved"]
check(same["alert_id"] is None and state()["phrase"]["source"] == "agent", "a save that changes nothing keeps the note")
m = c.get("/api/habits").json()["habits"]
m["math"]["default_min"] = 35
c.put("/api/habits", json={"habits": m}, headers={"X-Alibi-Client": "dashboard"})
clock.t = at(22, 7)                                       # the 120 s "Noted." line has gone
st = state()
check(st["phrase"]["source"] == "rules" and st["pinch"]["line"] is None and words_ok(st["phrase"]["text"]),
      f"a habits save after the brief: the rules again ({st['phrase']['text']!r})")

# --- 8. budget ----------------------------------------------------------------------------------------------------
real = clock._real
t0 = real()
for _ in range(100):
    c.get("/api/state")
avg = (real() - t0) / 100 * 1000
check(avg < 40, f"100 GET /api/state average {avg:.1f} ms (< 40)")
print("State DoD passed.")
