"""Focus DoD: a day's review counted by code from iPhone pickups and Mac window titles. A Monday of 90
pickups peaking at 17:00 inside a planned Drawing block with YouTube on the Mac during it, six days of 60 behind it, a
day the phone sent nothing (nulls, never 0) and a day no block happened. Checks the numbers, every rule and their
order, the agent's copy (no site or app names, titles or URLs), /api/focus, the agent context, the night review's Focus
chips and phone line, the briefs' chips and the night model's focus_day tool. Fake clock, test data, no network."""
import datetime as dt, json
from harness import Clock, check
import yaml
from fastapi.testclient import TestClient
from alibi import api, cards, config, db, digest, focus, integrations, routes_agent, signals

D = dt.date(2026, 10, 5)                                         # a Monday


def at(day: int, h: int, m: int = 0, s: int = 0) -> float:
    return dt.datetime.combine(D + dt.timedelta(days=day), dt.time(h, m, s)).timestamp()


yaml.safe_dump({"habits": {
    "drawing": {"modality": "physical", "default_min": 25, "weekly_target_min": 210,
                "schedule": [{"days": list(config.DAYS), "at": "17:00", "min": 60}]},
    "cpp": {"modality": "digital", "default_min": 30, "weekly_target_min": 180, "label": "C++",
            "schedule": [{"days": ["mon", "tue"], "at": "09:00", "min": 30}]}},
    "verdict": {"done": 0.7, "partial": 0.4}}, open(config.HABITS_PATH, "w"))
con = db.connect()
clock = Clock()
c = TestClient(api.app)
TOKEN = routes_agent.agent_token()
tail = TestClient(integrations.phone_app(), client=("100.100.100.100", 5000))          # the Spark, on the tailnet
H = {"X-Alibi-Agent-Token": TOKEN}
YT = ("Google Chrome", "Lofi beats - YouTube - Google Chrome – Work", "https://www.youtube.com/watch?v=lofi")
CODE = ("Code", "main.cpp — c++")
NAMES = ("youtube", "reddit", "messages", "netflix", "instagram", "slack", "lofi", "funny cats", "main.cpp", "r/cpp",
         "chrome", "safari", "firefox", "http", "www.", ".com")


def leaks(obj) -> list:
    blob = (obj if isinstance(obj, str) else json.dumps(obj)).lower()
    return [w for w in NAMES if w in blob]


def pickup(t: float):
    signals.store(con, "phone", "pickup", {"ts": t}, ts=t)


def windows(t0: float, n: int, app: str, title: str = "", url: str = ""):
    """n window rows 30 s apart; each stands for the 30 s until the next."""
    for i in range(n):
        db.add_event(con, "laptop", "window", {"app": app, "title": title, "url": url}, ts=t0 + 30 * i)


# --- seed ------------------------------------------------------------------------------------------------------------
windows(at(-7, 17), 30, *YT)                                     # D-7: no phone at all; 15 min of YouTube in Drawing
windows(at(-7, 17, 15), 1, *CODE)
for day in range(-6, 0):                                         # D-6..D-1: 60 pickups, 4 an hour 07:00-21:59
    for h in range(7, 22):
        for m in (5, 20, 35, 50):
            pickup(at(day, h, m))
con.execute("INSERT INTO sessions(habit,modality,declared_min,started_at,ends_at,ended_at,status,on_task_ratio,"
            "verdict) VALUES ('drawing','physical',60,?,?,?,'done',0.5,'partial')", (at(0, 17), at(0, 18), at(0, 18)))
con.commit()
P = [at(0, 17, m) for m in (2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52)]     # D: 11 at 17:00, inside Drawing
P += [at(0, 9, m) for m in (5, 12, 20)]                                     # 3 inside the 09:00 C++ block
for i, h in enumerate((7, 8, 10, 11, 12, 13, 14, 15, 16, 18, 19, 20, 21)):  # 76 more, never 7 in another hour
    P += [at(0, h, 3 + 10 * j) for j in range(6 if i < 11 else 5)]
for t in P:
    pickup(t)
pickup(P[0])                                                     # the phone resent a batch: still one pickup
windows(at(0, 9), 60, *CODE)
windows(at(0, 17), 20, *CODE)
windows(at(0, 17, 10), 50, *YT)                                  # 25 min of YouTube inside the Drawing block
windows(at(0, 17, 35), 10, *CODE)
windows(at(0, 17, 40), 10, "Google Chrome", "Focus mix - YouTube Music", "https://music.youtube.com/watch?v=mix")
windows(at(0, 17, 45), 30, *CODE)
windows(at(0, 18, 30), 10, "Messages")                           # 5 min of Messages
windows(at(0, 18, 35), 1, *CODE)
windows(at(0, 19), 4, "Firefox", "Funny cats - YouTube — Mozilla Firefox")  # 2 min, no URL: the title says YouTube
windows(at(0, 19, 2), 1, *CODE)
windows(at(0, 20), 20, "Safari", "r/cpp", "https://old.reddit.com/r/cpp/")  # 10 min of Reddit, outside the plan
windows(at(0, 20, 10), 1, *CODE)
windows(at(0, 21), 10, "Google Chrome", "How we stream - Netflix TechBlog", "https://netflixtechblog.com/how")
windows(at(0, 21, 5), 1, *CODE)
for t, n in ((at(0, 10), 5), (at(0, 15), 7), (at(0, 16), "x")):
    signals.store(con, "mac", "notifications", {"app": "Slack", "count": n, "phone": False}, ts=t)
signals.store(con, "phone", "screentime", {"app": "Instagram", "minutes": 10, "threshold_min": 5}, ts=at(0, 12))
signals.store(con, "phone", "screentime", {"app": "Instagram", "minutes": 20, "threshold_min": 5}, ts=at(0, 13))
for h in (10, 11, 12, 13, 14, 15, 16, 18, 19, 20, 21):           # D+1: 45 pickups, and no block happens
    for m in (5, 20, 35, 50):
        pickup(at(1, h, m))
pickup(at(1, 22, 30))

# --- 1. the day: 90 pickups, the 17:00 peak inside Drawing, 14 in plans, +50% on the week ----------------------------
clock.t = at(0, 22)
d = focus.day(con)
hours = [0] * 24
for h, n in zip(range(7, 22), (6, 6, 3, 6, 6, 6, 6, 6, 6, 6, 11, 6, 6, 5, 5)):
    hours[h] = n
check(d["date"] == "2026-10-05" and d["name"] == "Today" and d["phone"] is True and d["pickups"] == 90
      and d["pickups_by_hour"] == hours and d["peak"] == {"hour": 17, "pickups": 11},
      f"90 pickups (a resent one counted once), by hour, peak 17:00 with 11 ({d['pickups']}, {d['peak']})")
check(d["avg_7d"] == 60.0 and d["avg_days"] == 6 and d["vs_avg_pct"] == 50,
      f"against the week: 60 a day over the 6 days with phone data (D-7 had none), +50% "
      f"({d['avg_7d']}, {d['vs_avg_pct']})")
check(d["in_blocks"] == {"pickups": 14, "blocks": 2, "minutes": 90}, f"in planned blocks: 14 over 2 blocks, 90 min "
                                                                     f"({d['in_blocks']})")
check(d["by_habit"] == [
    {"habit": "cpp", "label": "C++", "planned_min": 30, "state": "missed", "pickups": 3, "per_hour": 6.0,
     "mac_distraction_min": 0},
    {"habit": "drawing", "label": "Drawing", "planned_min": 60, "state": "partial", "pickups": 11, "per_hour": 11.0,
     "mac_distraction_min": 25}], f"per habit over its blocks: C++ missed 3 (6.0/h), Drawing partial 11 (11.0/h), "
                                  f"25 min of YouTube ({d['by_habit']})")
check(d["sessions"] == [{"id": 1, "habit": "drawing", "label": "Drawing", "start": at(0, 17), "end": at(0, 18),
                         "verdict": "partial", "pickups": 11, "mac_distraction_min": 25}],
      f"per session: the Drawing session had 11 pickups and 25 min of YouTube ({d['sessions']})")
mac = d["mac"]
check(mac["distraction_min"] == 42 and mac["top"] == [{"name": "YouTube", "min": 27}, {"name": "Reddit", "min": 10},
                                                       {"name": "Messages", "min": 5}]
      and mac["notifications"] == 12 and isinstance(mac["switches_per_min"], float),
      f"Mac: 42 min (YouTube by URL and by a Firefox title, Reddit, Messages; YouTube Music and the Netflix blog don't "
      f"count), 12 notifications ({mac})")
check(d["screen_time_picked_min"] == 20 and d["line"] == "90 phone pickups, 11 at 17:00. 14 during planned blocks.",
      f"Screen Time 20 min; the line: {d['line']!r}")

# --- 2. the rules: every one that fires, then the three that lead ----------------------------------------------------
real_max, focus.MAX_RECS = focus.MAX_RECS, 9
every = focus.day(con)["recommendations"]
focus.MAX_RECS = real_max
check([(r["rule"], r["habit"]) for r in every] == [("mac", "drawing"), ("peak", "drawing"), ("phone_away", "drawing"),
                                                   ("above_week", None), ("phone_away", "cpp")],
      f"five rules fire, biggest first: {[(r['rule'], r['habit']) for r in every]}")
recs = d["recommendations"]
check([r["text"] for r in recs] == ["YouTube took 25 min during your plans. Turn the focus guard on.",
                                    "Don't plan Drawing at 17:00: your phone peaks then (11 pickups).",
                                    "Phone away for Drawing: 11 pickups an hour during it."],
      f"the three that lead, worded with digits: {[r['text'] for r in recs]}")
check(recs[0]["agent_text"] == "Video sites took 25 min during your plans. Turn the focus guard on."
      and recs[1]["agent_text"] == recs[1]["text"]
      and all(not leaks(r["agent_text"]) and not leaks(r["why"]) for r in recs),
      "agent wording says 'Video sites', never the site; every why is name-free")
check(every[3]["text"] == "90 pickups, 50% above your week. Start tomorrow with one 20-minute block, phone in another "
      "room." and every[3]["why"] == "The 6 days before averaged 60 by 22:05."
      and every[4]["text"] == "Phone away for C++: 6 pickups an hour during it.",
      f"the week rule and C++'s rule are there, just smaller ({every[3]['why']!r})")
integrations.set_state(phone_last_received=at(0, 21, 50))       # the iPhone's last batch landed at 21:50
synced = focus.day(con)
integrations.set_state(phone_last_received=None)
check(synced["pickups"] == 90 and synced["avg_7d"] == 59.0 and synced["vs_avg_pct"] == 53,
      f"a running day is compared up to the phone's last batch: 59 by 21:50 on the other days ({synced['avg_7d']})")
check(all("!" not in r["text"] + r["agent_text"] + r["why"] for r in every), "no exclamation marks")

noon = focus.day(con, D, at(0, 12))
check(noon["pickups"] == 28 and noon["avg_7d"] == 20.0 and noon["vs_avg_pct"] == 40
      and noon["in_blocks"] == {"pickups": 3, "blocks": 1, "minutes": 30}
      and [r["rule"] for r in noon["recommendations"]] == ["above_week", "phone_away"],
      f"at noon, like for like: 28 so far against 20 by noon on the other days (+40%); Drawing hasn't started "
      f"({noon['pickups']}, {noon['avg_7d']}, {[r['rule'] for r in noon['recommendations']]})")
early = focus.day(con, D, at(0, 7, 15))
check(early["pickups"] == 2 and early["avg_7d"] == 1.0 and early["vs_avg_pct"] is None
      and "above_week" not in [r["rule"] for r in early["recommendations"]],
      f"no percentage on a tiny base: 2 pickups by 07:20 against 1 then on the other days isn't +100% "
      f"({early['pickups']}, {early['avg_7d']}, {early['vs_avg_pct']})")

# --- 3. a day the phone sent nothing: nulls, never 0 -----------------------------------------------------------------
n0 = focus.day(con, "2026-09-28")
check(n0["phone"] is False and all(n0[k] is None for k in ("pickups", "pickups_by_hour", "peak", "avg_7d", "vs_avg_pct",
                                                            "screen_time_picked_min"))
      and n0["in_blocks"] == {"pickups": None, "blocks": 2, "minutes": 90}
      and all(h["pickups"] is None and h["per_hour"] is None for h in n0["by_habit"])
      and n0["line"] == "No phone data for this day.",
      f"no phone rows -> every phone number is null, the line says so ({n0['line']!r})")
check(n0["mac"]["distraction_min"] == 15 and [r["text"] for r in n0["recommendations"]] == [
      "YouTube took 15 min during your plans. Turn the focus guard on."],
      "the Mac still counts on that day; only the Mac rule speaks")

# --- 4. the agent's copy: numbers, habit names and hours, nothing named ----------------------------------------------
s = focus.agent_summary(con)
KEYS = {"date", "phone", "pickups", "peak", "avg_7d", "vs_avg_pct", "in_blocks", "by_habit", "mac",
        "screen_time_picked_min", "recommendations", "line"}
t = s["today_so_far"]
check(set(s) == {"yesterday", "today_so_far"} and set(t) == KEYS == set(s["yesterday"])
      and set(t["mac"]) == {"distraction_min", "notifications"}
      and all(set(h) == {"habit", "label", "state", "pickups", "per_hour", "mac_distraction_min"}
              for h in t["by_habit"])
      and all(set(r) == {"habit", "text", "why"} for r in t["recommendations"]),
      "agent_summary carries exactly the contract's keys")
check(t["pickups"] == 90 and s["yesterday"]["pickups"] == 60 and t["line"] == d["line"]
      and t["recommendations"][0]["text"] == "Video sites took 25 min during your plans. Turn the focus guard on.",
      "today so far 90, yesterday 60, the same line, rules in agent wording")
check(not leaks(s), f"agent_summary names no site, app, title or URL ({leaks(s)})")

# --- 5. /api/focus ---------------------------------------------------------------------------------------------------
r = c.get("/api/focus/day", params={"date": "2026-10-05"})
check(r.status_code == 200 and r.json() == json.loads(json.dumps(focus.day(con, D))),
      "GET /api/focus/day?date=… is day()")
check(c.get("/api/focus/day").json()["date"] == "2026-10-05" and c.get("/api/focus/day", params={"date": "yesterday"})
      .json()["pickups"] == 60, "no date is today; date=yesterday works")
r = c.get("/api/focus/day", params={"date": "2026-13-40"})
check(r.status_code == 400 and "2026-10-01" in r.json()["detail"],
      f"a bad date is a 400 with one sentence ({r.json()})")
w = c.get("/api/focus/week")
check(w.status_code == 200 and len(w.json()["days"]) == 7, "GET /api/focus/week")

# --- 6. the agent context gets it; a focus bug costs only that key ---------------------------------------------------
ctx = routes_agent.context(clock.t)
check(ctx["focus"] == focus.agent_summary(con, clock.t) and not leaks(ctx["focus"])
      and "YouTube" not in json.dumps(ctx), "context()['focus'] is agent_summary, name-free")
real = focus.agent_summary
focus.agent_summary = lambda *a: 1 / 0
ctx2 = routes_agent.context(clock.t)
focus.agent_summary = real
check(ctx2["focus"] is None and ctx2["habits"] and ctx2["today"], "a focus bug: context still answers, focus is null")
check(tail.get("/api/agent/context", headers=H).json()["focus"]["today_so_far"]["pickups"] == 90,
      "the Spark reads it over the tailnet")

# --- 7. the night review: phone line in the text, the Focus chips first on its card ----------------------------------
row = digest.run("night", clock.t, send=False)
lines = row["text"].splitlines()
i = next(n for n, x in enumerate(lines) if x.startswith("Day closed."))
check(lines[i + 1] == "Phone: 90 pickups, 11 at 17:00. 14 during planned blocks." and not leaks(row["text"]),
      f"night text: the phone line follows 'Day closed.', name-free ({lines[i + 1]!r})")
check(row["json"]["focus"]["pickups"] == 90 and row["json"]["focus"]["recommendations"][0]["agent_text"]
      == "Video sites took 25 min during your plans. Turn the focus guard on.",
      "the digest keeps the day's focus numbers")
FOCUS = {"label": "Focus", "items": [{"text": "90 pickups", "tone": "warn", "icon": "phone"},
                                     {"text": "Peak 17:00 · 11", "tone": "neutral", "icon": "clock"},
                                     {"text": "14 in plans", "tone": "neutral", "icon": "calendar"},
                                     {"text": "+50% vs week", "tone": "warn"}]}
cd = cards.for_digest(row, clock.t)
check(cd["groups"][0] == FOCUS and cd["groups"][1]["label"] == "Today" and len(cd["groups"]) <= 3,
      f"night card: Focus first (the island shows two groups), then the day ({[g['label'] for g in cd['groups']]})")
closed = cards.for_digest(dict(row, proposal=None, json=dict(row["json"], proposal=None)), clock.t)
check(closed["title"] == "Day closed." and closed["subtitle"] == recs[0]["text"],
      f"no proposal: the top rule is the subtitle ({closed['subtitle']!r})")
dg = tail.get("/api/agent/digests", headers=H).json()["items"][0]
check("Phone: 90 pickups" in dg["text"] and not leaks(dg["text"]),
      "the Spark's digest text has the phone line, no names")
old = dict(row, json={k: v for k, v in row["json"].items() if k != "focus"})
check(cards.for_digest(old, clock.t)["groups"][0]["label"] != "Focus" and "Phone:" not in digest.text(old["json"]),
      "a night row from before focus: no Focus group, no phone line")

# --- 8. the night model's focus_day tool -----------------------------------------------------------------------------
check(any(x["function"]["name"] == "focus_day" for x in digest.TOOLS) and "focus_day" in digest.SYSTEM
      and "peak" in digest.SYSTEM and digest.MAX_TURNS == 7, "focus_day is a tool; the prompt says to check it")
res = digest.tool_call(con, "focus_day", {}, clock.t, [])
check(res["pickups"] == 90 and res["peak"] == {"hour": 17, "pickups": 11} and res["pickups_by_hour"][17] == 11
      and res["recommendations"][1]["text"] == "Don't plan Drawing at 17:00: your phone peaks then (11 pickups)."
      and not leaks(res), f"focus_day: counts by hour and the rules, name-free ({leaks(res)})")
check(digest.tool_call(con, "focus_day", {"date": "yesterday"}, clock.t, [])["pickups"] == 60
      and digest.step_result("focus_day", {}, res, clock.t) == "90 pickups, peak 17:00"
      and digest.step_result("focus_day", {}, {"phone": False}, clock.t) == "no phone data",
      "focus_day for yesterday; its trace line reads plainly")
check(digest._provenance({"generated_at": clock.t, "total_ms": 6400, "model": "nvidia/nemotron-3-super-120b-a12b",
                          "trace": [{"tool": "week_status"}, {"tool": "focus_day"}, {"tool": "plan", "args": {
                              "day": (D + dt.timedelta(days=1)).isoformat()}}, {"tool": "free_gaps"}]})
      == "Checked your week, your pickups, tomorrow's plan and free gaps · Nemotron 3 Super · 6 s",
      "the card's provenance says the model checked your pickups")

# --- 9. the agent's briefs: the same Focus chips for the day each is about -------------------------------------------
clock.t = at(0, 22, 5)
brief = {"idempotency_key": "f-night", "slot": f"{D}-night", "kind": "night", "links": [], "items": [],
         "model": "nvidia/nemotron-3-super-120b-a12b",
         "text": "90 pickups today, 11 at 17:00, and Drawing took the hit. Tomorrow, phone in another room at 17:00."}
r = tail.post("/api/agent/brief", headers=H, json=brief)
br = routes_agent.briefs()[-1]
check(r.status_code == 200 and br["focus"]["date"] == "2026-10-05" and br["focus"]["pickups"] == 90
      and "recommendations" not in br["focus"] and not leaks(br["focus"]),
      "a night brief's row keeps that day's counts")
check(cards.for_brief(br)["groups"] == [FOCUS] and c.get("/api/state").json()["alert"]["card"]["groups"] == [FOCUS],
      "its card (and its island alert) shows the night's Focus chips")
clock.t = at(1, 7, 31)
morning = dict(brief, idempotency_key="f-morning", slot="2026-10-06-morning", kind="morning",
               text="Yesterday: 90 pickups, 50% above your week.")
r = tail.post("/api/agent/brief", headers=H, json=morning)
br = routes_agent.briefs()[-1]
check(r.json()["shown_as"] == "agent" and br["focus"]["date"] == "2026-10-05"
      and cards.for_brief(br)["groups"] == [FOCUS], "a morning brief gets yesterday's chips")
clock.t = at(1, 12, 1)
tail.post("/api/agent/brief", headers=H, json=dict(brief, idempotency_key="f-check", slot="2026-10-06-checkpoint-12",
                                                   kind="checkpoint", text="Nothing new."))
br = routes_agent.briefs()[-1]
check("focus" not in br and "groups" not in cards.for_brief(br), "a checkpoint brief has no Focus chips")

# --- 10. a day no block happened -------------------------------------------------------------------------------------
clock.t = at(2, 7, 30)
y = focus.day(con, "yesterday")
check(y["name"] == "Yesterday" and y["pickups"] == 45 and y["avg_days"] == 7 and y["vs_avg_pct"] == -30
      and [r["text"] for r in y["recommendations"]] == ["None of your 2 blocks happened; your phone was picked up 45 "
                                                        "times. One 20-minute block tomorrow, phone away."]
      and y["line"] == "45 phone pickups, 4 at 10:00. None during planned blocks.",
      f"nothing planned happened: that rule alone ({[r['rule'] for r in y['recommendations']]}, {y['line']!r})")
s2 = focus.agent_summary(con)
check(s2["yesterday"]["pickups"] == 45 and s2["today_so_far"]["phone"] is False
      and s2["today_so_far"]["pickups"] is None, "the morning after: yesterday 45, today no phone data yet (null)")

# --- 11. the week ----------------------------------------------------------------------------------------------------
clock.t = at(0, 22)
wk = focus.week(con)
check([x["pickups"] for x in wk["days"]] == [60] * 6 + [90] and [x["in_blocks_pickups"] for x in wk["days"]]
      == [6, 4, 4, 4, 4, 4, 14] and wk["days"][-1] == {"date": "2026-10-05", "pickups": 90, "in_blocks_pickups": 14,
                                                       "seen_min": 30} and wk["avg_day"] == 60.0,
      f"7 days, oldest first: pickups, pickups in plans, minutes seen; 60 a day before today ({wk['days'][-1]})")
bh = {h["habit"]: h for h in wk["by_habit"]}
check(bh["drawing"] == {"habit": "drawing", "label": "Drawing", "pickups_per_hour": 5.0, "top_source": "mac",
                        "best_hour": 17, "sessions": 1}
      and bh["cpp"] == {"habit": "cpp", "label": "C++", "pickups_per_hour": 5.0, "top_source": None, "best_hour": None,
                        "sessions": 0} and wk["struggle"] is None and wk["recommendations"] == [],
      f"per habit: Drawing 5.0/h, pulled away by the Mac, best at 17:00; nothing over the line ({wk['by_habit']})")
for m in range(0, 56, 4):                                        # Sunday's Drawing hour gets 14 more pickups
    pickup(at(-1, 17, m, 30))
wk = focus.week(con)
check(wk["struggle"] == {"habit": "drawing", "label": "Drawing", "per_hour": 7.0,
                         "reason": "7 pickups an hour during Drawing this week."}
      and wk["recommendations"][0]["text"] == "Phone away for Drawing: 7 pickups an hour during it this week."
      and wk["recommendations"][0]["why"] == "49 pickups in 420 min of Drawing this week.",
      f"the habit that struggled: {wk['struggle']}")

# --- 12. only full days make "your week": an evening the phone sync began isn't one ----------------------------------
for m in range(0, 60, 6):                                        # D+2: 10 pickups 19:00-19:54, nothing else that day
    pickup(at(2, 19, m))
for h in range(8, 21):                                           # D+3: 39 pickups, 08:10-20:50
    for m in (10, 30, 50):
        pickup(at(3, h, m))
z = focus.day(con, D + dt.timedelta(days=3), at(4, 7, 30))
check(z["pickups"] == 39 and z["avg_days"] == 6 and z["avg_7d"] == 64.8 and z["vs_avg_pct"] == -40,
      f"a day the phone covered for under an hour stays out of the week: 6 days averaging 64.8, -40% "
      f"({z['avg_days']}, {z['avg_7d']}, {z['vs_avg_pct']})")
clock.t = at(3, 22)
wk = focus.week(con)
check([x["pickups"] for x in wk["days"]][-2:] == [10, 39] and wk["avg_day"] == 65.8,
      f"the week's 'a day' skips that evening and today so far: (60+60+74+90+45)/5 ({wk['avg_day']})")

# --- 13. before the phone's first row nothing was measured: a block that morning has no count, not 0 -----------------
from alibi import calendar_sync
calendar_sync.add_once("cpp", (D - dt.timedelta(days=6)).isoformat(), "06:00", 30)   # before the first pickup, 07:05
t = focus.day(con, D - dt.timedelta(days=6), at(0, 22))
cpp = next(h for h in t["by_habit"] if h["habit"] == "cpp")
check(cpp["pickups"] == 2 and cpp["per_hour"] == 4.0 and cpp["planned_min"] == 60,
      f"the day the phone began: C++ counts its 09:00 block only, 2 pickups in 30 min, not 2 in 60 ({cpp})")
clock.t = at(0, 22)
wk = focus.week(con)
check(next(h for h in wk["by_habit"] if h["habit"] == "cpp")["pickups_per_hour"] == 5.0,
      "the week's C++ rate leaves out the block before the phone's first row: still 5 in 60 min")

# --- 14. a lost day well above the week asks for one 20-minute block once, not twice ---------------------------------
for h in range(8, 22):                                           # D+4: 98 pickups, 7 an hour, no block happens
    for m in range(0, 56, 8):
        pickup(at(4, h, m, 15))
lost = focus.day(con, D + dt.timedelta(days=4), at(5, 7, 30))
check(lost["pickups"] == 98 and lost["vs_avg_pct"] >= 30
      and [r["rule"] for r in lost["recommendations"]] == ["none_happened"],
      f"{lost['pickups']} pickups, {lost['vs_avg_pct']}% above the week, no block: one rule, not the week's echo "
      f"({[r['rule'] for r in lost['recommendations']]})")
print("Focus DoD passed.")
