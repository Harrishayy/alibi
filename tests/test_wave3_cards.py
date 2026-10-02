"""Cards DoD (not paragraphs): the night review, digests, the agent's brief, a settled run claim, the day recap
and a habits save each reach the clients as a structured `card` next to their unchanged `text`; raw enums never reach
a screen; cards.clean() holds every cap and never raises; /api/state keeps its keys and its speed; a night card read
after midnight or after its slot says so. Fake clock, test data, no network."""
import datetime as dt, json, os, statistics, time
os.environ.update(ALIBI_BRIEF_ALERTS="all", ALIBI_AGENT_HOST="DGX Spark", REPORT_HOUR="22")
from harness import Clock, check
import yaml
from fastapi.testclient import TestClient
from alibi import api, cards, config, daemon, db, digest, integrations, notify, routes_agent

D = dt.date(2026, 10, 5)                                         # a Monday


def at(h: int, m: int = 0, day: int = 0) -> float:
    return dt.datetime.combine(D + dt.timedelta(days=day), dt.time(h, m)).timestamp()


yaml.safe_dump({"habits": {
    "drawing": {"modality": "physical", "default_min": 25, "weekly_target_min": 210},
    "math": {"modality": "physical", "default_min": 30, "weekly_target_min": 120,
             "schedule": [{"days": ["mon"], "at": "09:00", "min": 30}]}},
    "verdict": {"done": 0.7, "partial": 0.4}}, open(config.HABITS_PATH, "w"))
con = db.connect()
clock = Clock()
c = TestClient(api.app)
OLD = {"now", "session", "alert", "habits", "witness", "witness_label", "text_model", "daemon", "today",
       "recent_verdict", "status_text", "pinch"}
NEW = {"plan_today", "phrase", "agent", "clients"}
state = lambda: c.get("/api/state").json()
last = lambda kind: notify.last_alert(kind)

# --- 1. the night review through the API (rules mode): question, missed blocks, buffer bars, Accept ---------------------
clock.t = at(22)
row = c.post("/api/digests/run", json={"kind": "night"}).json()
cd = row.get("card") or {}
q = row["text"].splitlines()[0]
check(cd.get("v") == 1 and cd.get("kind") == "night" and "?" in q and cd.get("title") == q[:q.index("?") + 1],
      f"night card: v1, its title is the text's question ({cd.get('title')!r})")
g = {x["label"]: x for x in cd.get("groups", [])}
miss = (g.get("Missed today") or g.get("Today") or {}).get("items") or []
check(any(i["text"] == "Math 09:00" and i["tone"] == "warn" and i.get("icon") == "x" for i in miss),
      f"the missed 09:00 math block is a warn ✗ chip ({miss})")
bars = (g.get("Buffer") or {}).get("bars") or []
check(len(bars) == 2 and [b["value"] for b in bars] == sorted(b["value"] for b in bars)
      and all(b["min"] == -7 and b["max"] == 7 and b["caption"].endswith(" d") for b in bars),
      f"buffer bars, worst first: {[(b['label'], b['caption']) for b in bars]}")
check(cd.get("provenance") == {"text": "Alibi's rules", "source": "rules"} and cd["actions"][0]["post"].endswith(
      f"/api/digests/{row['slot']}/accept") and cd["actions"][1] == {"label": "Not now", "dismiss": True},
      "provenance: Alibi's rules; actions Accept (POST …/accept) and Not now")
latest = c.get("/api/digests/latest", params={"kind": "night"}).json()
check(latest["card"] == cd and latest["text"] == row["text"] and "card" not in digest.get(row["slot"]),
      "GET /latest carries the same card; the row on disk has none")
check(all("card" in r for r in c.get("/api/digests").json()["digests"]), "GET /api/digests: every row has a card")
st = state()
check(set(st) == OLD | NEW, f"/api/state keeps its 16 keys ({len(st)})")
ac = st["alert"].get("card") or {}
check(st["alert"]["kind"] == "digest" and ac.get("kind") == "night" and "actions" not in ac
      and st["alert"]["text"] == row["text"] and st["alert"]["actions"] == digest.actions(row),
      "the night alert: card kind night, no actions inside it, its text and buttons unchanged")
r = c.post(f"/api/digests/{row['slot']}/accept").json()
lc = c.get("/api/digests/latest", params={"kind": "night"}).json()["card"]
check(r["ok"] and lc["title"].startswith("On the plan: ") and lc["title"].endswith(" min.")
      and {"text": "Accepted", "tone": "accent", "icon": "check"} in lc.get("chips", []) and "actions" not in lc,
      f"after Accept: {lc['title']!r}, an Accepted chip, no actions")
notify.notify(row["text"], kind="report", day=D.isoformat(), slot=row["slot"], via="rules",
              actions=digest.actions(row), habit_label="Night review")
rc = state()["alert"].get("card") or {}
check(rc.get("kind") == "night" and rc["title"] == lc["title"], "a report alert with the slot gets the night card too")
notify.notify("This week: nothing seen.", kind="report", day=D.isoformat())
check("card" not in state()["alert"], "a report alert with no slot (the old fallback) gets no card key")
check(not any("card" in json.loads(x) for x in config.ALERTS_PATH.read_text().splitlines()),
      "alerts.jsonl never stores a card: it's built when served")

# --- 2. the agent's brief: enums turned into words everywhere, its items as chips ------------------------------------
TOKEN = routes_agent.agent_token()
tail = TestClient(integrations.phone_app(), client=("100.100.100.100", 5000))
clock.t = at(22, 5)
b = {"idempotency_key": "w3-1", "slot": f"{D}-night", "kind": "night", "links": [],
     "model": "nvidia/nemotron-3-super-120b-a12b", "tools_used": ["context"],
     "text": "All habits off_track. Math, C++ and Drawing blocks were missed today.",
     "items": [{"habit": "math", "note": "block missed"}]}
r = tail.post("/api/agent/brief", headers={"X-Alibi-Agent-Token": TOKEN}, json=b)
a = last("brief")
check(r.status_code == 200 and r.json()["shown_as"] == "agent" and a and "_" not in a["text"]
      and a["text"] == "All habits off track. Math, C++ and Drawing blocks were missed today.",
      f"the brief alert's text is words, not enums: {a and a['text']!r}")
st = state()
bc = st["alert"].get("card") or {}
check(bc.get("kind") == "brief" and bc.get("title") == "All habits off track."
      and bc.get("subtitle") == "Math, C++ and Drawing blocks were missed today.",
      f"brief card: the first sentence is the title, the next the subtitle ({bc.get('title')!r})")
check(bc.get("provenance") == {"text": "Your agent · DGX Spark", "source": "agent", "detail": "Nemotron 3 Super"}
      and bc.get("chips") == [{"text": "Math · block missed", "tone": "warn"}] and "actions" not in bc,
      "provenance: Your agent · DGX Spark (Nemotron 3 Super); the item is a warn chip")
br = c.get("/api/briefs", params={"limit": 1}).json()["briefs"][0]
check(br.get("card") == bc and "off_track" not in br["text"] and br["text"].startswith("All habits off track.")
      and {"ts", "slot", "kind", "text", "via", "model", "tools_used", "shown_as", "age_s", "source_line"} <= set(br),
      "/api/briefs: the row has the card, its text is words, every old key is there")
check("off_track" in json.loads(routes_agent._path().read_text().splitlines()[-1])["text"],
      "the stored brief row is untouched")
check(st["phrase"]["source"] == "agent" and st["phrase"]["text"] == "All habits off track.",
      f"Pinch's idle phrase is the brief, in words: {st['phrase']['text']!r}")

# --- 3. a run claim settled by Strava, and the day recap --------------------------------------------------------------
clock.t = at(22, 10)
db.add_event(con, "user", "claim", {"habit": "running", "min_km": 5, "until": at(23)})
db.add_event(con, "strava", "activity", {"id": 1, "name": "Run", "distance_km": 5.2, "moving_min": 27,
                                         "start_date": clock.t}, ts=clock.t + 60)
check(daemon.check_claims(con) == ["Run verified: 5.2 km."], "the claim settles; its text is unchanged")
v = last("verdict")
check(v["distance_km"] == 5.2 and v["min_km"] == 5.0 and v["moving_min"] == 27 and v["verdict"] == "done",
      "the verdict alert carries distance_km, min_km and moving_min")
vc = state()["alert"].get("card") or {}
check(vc.get("kind") == "claim" and vc.get("title") == "Run verified." and vc.get("stat") == {
      "value": "5.2", "unit": "km", "caption": "on Strava"} and vc.get("provenance", {}).get("source") == "strava"
      and [x["text"] for x in vc.get("chips", [])] == ["Done", "27 min"], f"claim card: {vc}")
db.add_event(con, "user", "claim", {"habit": "running", "min_km": 10, "until": at(22, 11)})
clock.t = at(22, 12)
out = daemon.check_claims(con)
vc = state()["alert"].get("card") or {}
check(out == ["You said you'd run. Strava has nothing ≥10 km. Logged as claimed, not seen."]
      and vc.get("title") == "Claimed, not seen." and vc.get("subtitle") == "Strava has no run of 10 km or more."
      and vc.get("tone") == "warn" and last("verdict")["min_km"] == 10.0 and "distance_km" not in last("verdict"),
      f"an unseen claim: {vc.get('title')!r} {vc.get('subtitle')!r}")
for h0, m, ratio, verdict in ((13, 25, 1.0, "done"), (15, 30, 0.5, "partial")):
    con.execute("INSERT INTO sessions(habit,modality,declared_min,started_at,ends_at,ended_at,status,on_task_ratio,"
                "verdict) VALUES ('drawing','physical',?,?,?,?,'done',?,?)",
                (m, at(h0), at(h0) + m * 60, at(h0) + m * 60, ratio, verdict))
con.commit()
text = daemon.recap(con, D.isoformat(), clock.t)
ra = last("recap")
rc = state()["alert"].get("card") or {}
check(text.startswith("Today: 2 sessions, 40 min seen.") and ra["sessions"] == 2 and ra["seen_min"] == 40
      and ra["text"] == text, f"the recap alert carries sessions and seen_min; text unchanged ({text!r})")
check(rc.get("kind") == "recap" and rc.get("stat") == {"value": "40", "unit": "min", "caption": "seen today"}
      and rc.get("chips") == [{"text": "2 sessions", "tone": "neutral", "icon": "camera"}], f"recap card: {rc}")

# --- 4. a habits save: the receipt as a card -----------------------------------------------------------------------
hs = c.get("/api/habits").json()["habits"]
hs["piano"] = {"modality": "physical", "default_min": 20, "weekly_target_min": 40}
r = c.put("/api/habits", json={"habits": hs}, headers={"X-Alibi-Client": "dashboard"})
a = last("habits_saved")
hc = state()["alert"].get("card") or {}
check(r.status_code == 200 and a["text"].startswith("Noted. ") and hc.get("kind") == "habits_saved"
      and hc.get("title") == a["text"][len("Noted. "):] and hc.get("chips") == [
          {"text": "Piano · added", "tone": "accent"}], f"habits_saved card: {hc.get('title')!r} + one accent chip")
check(state()["alert"]["actions"] == a["actions"], "the receipt's buttons stay the alert's own")

# --- 5. display(): no raw enums, idempotent, paths and model ids untouched -------------------------------------------
TABLE = {"All habits off_track.": "All habits off track.", "Math is OFF_TRACK": "Math is off track",
         "on_task 80%": "on task 80%", "C++ at_risk; deep_work on_track": "C++ at risk; deep work on track",
         "nvidia/nemotron-3-super-120b-a12b": "nvidia/nemotron-3-super-120b-a12b",
         "agent_briefs.jsonl": "agent_briefs.jsonl", "/api/digests/latest?kind=night": "/api/digests/latest?kind=night",
         "buffer_days -5": "buffer -5", "": "", None: ""}
bad = {k: cards.display(k) for k, want in TABLE.items() if cards.display(k) != want}
check(not bad, f"display(): every row of TABLE ({bad or 'all match'})")
check(all(cards.display(cards.display(k)) == cards.display(k) for k in TABLE), "display() is idempotent")

# --- 6. clean(): caps, limits, and a malformed card never raises --------------------------------------------------------
long = "word " * 40
k = cards.clean({"kind": "night", "title": long, "subtitle": long, "tone": "nope",
                 "chips": [{"text": long, "tone": "warn", "icon": "rocket"}] * 9,
                 "groups": [{"label": long, "bars": [{"label": long, "value": -99, "min": -7, "max": 7, "tone": "warn",
                                                      "caption": "−99 d"}] * 12}] * 5,
                 "stat": {"value": "1234567", "unit": "minutes!", "caption": long},
                 "provenance": {"text": long, "source": "elsewhere", "detail": long},
                 "actions": [{"label": "A", "dismiss": True}] * 5})
check(len(k["title"]) <= 64 and k["title"].endswith("…") and len(k["subtitle"]) <= 110 and k["subtitle"].endswith("…")
      and all(len(x["text"]) <= 24 and x["text"].endswith("…") and "icon" not in x for x in k["chips"])
      and all(len(x["label"]) <= 16 and x["label"].endswith("…") for x in k["groups"][0]["bars"])
      and len(k["groups"][0]["label"]) <= 18 and k["tone"] == "neutral",
      "caps: title 64, subtitle 110, chip 24, bar label 16, group label 18, each cut with '…'; unknown tone/icon dropped")
check(len(k["chips"]) == 6 and len(k["groups"]) == 3 and len(k["groups"][0]["bars"]) == 8 and len(k["actions"]) == 3
      and k["groups"][0]["bars"][0]["value"] == -7.0 and len(k["stat"]["value"]) <= 6
      and "source" not in k["provenance"] and len(k["provenance"]["text"]) <= 40,
      "limits: 6 chips, 3 groups, 8 bars, 3 actions; a value is clamped into range; an unknown source is dropped")
BAD = [None, 42, "x", [], {}, {"title": 42}, {"title": "  "}, {"v": 1, "title": 42, "chips": "nope"},
       {"title": "Ok", "chips": "nope", "groups": 7, "actions": 3, "stat": 4, "provenance": "x"},
       {"title": "Ok", "chips": [None, 1, {"text": {"a": 1}}, {"text": "Fine", "tone": "warn"}],
        "groups": [{"label": "Buffer", "bars": [{"label": "x", "value": "bad", "min": -7, "max": 7},
                                                  {"label": "y", "value": float("nan"), "min": -7, "max": 7},
                                                  {"label": "z", "value": 1, "min": 7, "max": -7}]},
                   {"label": "Items", "items": "nope"}, "junk"],
        "stat": {"value": None}, "actions": [{"label": 1}, {"dismiss": True}, {"label": "Go", "body": {"x": [1]}}]}]
try:
    res = [cards.clean(x) for x in BAD]
    ok = True
except Exception as e:
    res, ok = [], False
check(ok and res[:8] == [None] * 8 and res[8] == {"v": 1, "kind": "note", "title": "Ok.", "tone": "neutral"}
      and res[9]["chips"] == [{"text": "Fine", "tone": "warn"}] and "groups" not in res[9] and "stat" not in res[9]
      and res[9]["actions"] == [{"label": "Go", "body": {}}],
      "malformed cards: None without a string title, otherwise the bad parts dropped; never raises")
json.dumps(res, allow_nan=False)                                 # raises if NaN or infinity got through
check(cards.for_alert({"kind": "report", "slot": "nope", "id": 1}) is None and cards.for_alert(None) is None
      and cards.for_digest({"kind": "night", "json": {"proposal": "junk", "generated_at": "x"}}) is None
      and cards.for_brief({"text": {"a": 1}, "items": 3}) is None
      and cards.for_digest({"kind": "night", "json": "junk"})["title"] == "Day closed.",
      "for_* return None on rows they can't read, never raise; an empty night is just 'Day closed.'")

# --- 7. no regressions: the night text is byte-identical with display() switched off --------------------------------------
d = digest.get(row["slot"])["json"]
t1 = digest.text(d)
real, cards.display = cards.display, (lambda x: x)
t0 = digest.text(d)
cards.display = real
check(t1 == t0 == row["text"], "digest.text() of the test night is byte-identical with or without display()")
p = dict(d["proposal"], why="Math is off_track.")
check("Math is off track." in digest.text(dict(d, proposal=p)) and "off_track" not in digest.text(dict(d, proposal=p)),
      "a model's enum in the proposal's why is shown as words")

# --- 8. cost: a night card on /api/state stays within 2 ms of a plain alert -------------------------------------------------
notify.notify(row["text"], kind="report", day=D.isoformat(), slot=row["slot"], via="rules", actions=digest.actions(row))


def p50(n=200) -> float:
    real_t, xs = clock._real, []
    for _ in range(n):
        t0 = time.perf_counter()
        c.get("/api/state")
        xs.append((time.perf_counter() - t0) * 1000)
    return statistics.median(xs)


p50(20)
night_ms = p50()
check((state()["alert"].get("card") or {}).get("kind") == "night", "the night report is the latest alert")
notify.notify("Your iPhone checked in.", kind="synced")
p50(20)
plain_ms = p50()
check(night_ms <= plain_ms + 2, f"GET /api/state p50: {night_ms:.2f} ms with the night card, {plain_ms:.2f} ms without")

# --- 9. read after midnight: the night card is worded against the clock, not when it was written ----------------------
p = row["proposal"]                                              # Tuesday 07:00, written Monday 22:00
name, slot = config.spoken_name(p["habit"]), f"{p['at']}, {p['minutes']} min"
fresh = dict(digest.get(row["slot"]), accepted_at=None)          # the same row, not accepted
llm = dict(fresh, json=dict(fresh["json"], via="llm:build", model="nvidia/nemotron-3-super-120b-a12b", total_ms=4768,
                             trace=[{"tool": "week_status", "args": {}}, {"tool": "plan", "args": {"day": p["day"]}}]))
closed = dict(fresh, proposal=None, json=dict(fresh["json"], proposal=None,
                                              fix_tomorrow={"habit": "math", "label": "Math", "reason": "1 h behind."}))
notify.notify(row["text"], kind="report", day=D.isoformat(), slot=row["slot"], via="rules", actions=digest.actions(row))
clock.t = at(23, 50)
k0, a0 = cards.for_digest(fresh), state()["alert"]["card"]      # the alert's card is memoised from here
check(k0["title"] == f"Move {name} to tomorrow {slot}?" and k0["groups"][0]["label"] == "Missed today"
      and a0["title"] == f"On the plan: {name} tomorrow {slot}." and cards.for_digest(llm)["provenance"]["detail"]
      == "Checked your week and tomorrow's plan", f"23:50, same night: tomorrow, Missed today ({k0['title']!r})")
clock.t = at(0, 30, day=1)
k1, a1, kl, kc = cards.for_digest(fresh), state()["alert"]["card"], cards.for_digest(llm), cards.for_digest(closed)
check(k1["title"] == f"Move {name} to today {slot}?" and k1["groups"][0]["label"] == "Missed Monday"
      and [x["label"] for x in k1["actions"]] == ["Accept", "Not now"],
      f"00:30 Tuesday: 'today {p['at']}', 'Missed Monday', Accept still offered ({k1['title']!r})")
check(a1["title"] == f"On the plan: {name} today {slot}." and kl["provenance"]["detail"] == "Checked your week and "
      "today's plan" and kc["subtitle"] == "Fix today: Math. 1 h behind.",
      f"the alert's memoised card turns at midnight ({a1['title']!r}); provenance and 'Fix today' follow")
c.post(f"/api/digests/{row['slot']}/undo")
r = c.post(f"/api/digests/{row['slot']}/accept").json()
check(r["ok"] and r["reply"] == f"Done. {config.display_name(p['habit'])} today {slot}. It's on the plan.",
      f"accepted after midnight, the reply says today: {r['reply']!r}")
clock.t = dt.datetime.fromisoformat(f"{p['day']}T{p['at']}").timestamp() + 60      # the slot has started
k2 = cards.for_digest(fresh)
check(k2["title"] == f"Proposed: {name} today {slot}." and "actions" not in k2 and k2["tone"] == "neutral"
      and {"text": "Slot passed", "tone": "neutral", "icon": "clock"} in k2["chips"]
      and c.get("/api/digests/latest", params={"kind": "night"}).json()["card"]["title"]
      == f"On the plan: {name} today {slot}.",
      f"after the slot starts: no question and no Accept ({k2['title']!r}); the accepted one stays on the plan")
print("Cards DoD passed.")
