"""The Plan page (next three days): one view and one edit for the dashboard and, behind the phone key, the iPhone.
Move, skip, bring back, add a one-off, remove it, day off and back; refusals in one sentence; a phone edit makes the
notch say it; an accepted night review block is labelled a catch-up. Calendar isn't connected: no EventKit."""
import datetime as dt, json, time
import yaml
from harness import Clock, check
from fastapi.testclient import TestClient
from alibi import api, calendar_sync as cal, config, digest, integrations, notify

clock = Clock()
clock.t = dt.datetime(2026, 10, 2, 9, 0).timestamp()                  # a Friday, 09:00
cfg = config.habits()
for h in cfg["habits"].values():
    h.pop("schedule", None)
cfg["habits"]["drawing"]["schedule"] = [{"days": list(config.DAYS), "at": "19:00", "min": 25}]
cfg["habits"]["math"]["schedule"] = [{"days": ["fri", "sat"], "at": "11:00", "min": 30}]
yaml.safe_dump(cfg, open(config.HABITS_PATH, "w"), sort_keys=False)

web = TestClient(api.app)


def view():
    return web.get("/api/calendar/days", params={"days": 3}).json()


def edit(**body):
    return web.post("/api/calendar/plan/edit", json=body)


def block(v, date, habit):
    d = next(d for d in v["days"] if d["date"] == date)
    return next((b for b in d["blocks"] if b["habit"] == habit), None)


v = view()
check([d["name"] for d in v["days"]] == ["Today", "Tomorrow", "Sunday"], f"three days: {[d['name'] for d in v['days']]}")
check([b["at"] for b in v["days"][0]["blocks"]] == ["11:00", "19:00"] and v["days"][0]["planned_min"] == 55,
      f"today: math 11:00 + drawing 19:00 = 55 min ({v['days'][0]})")
draw = block(v, "2026-10-02", "drawing")
check(draw["can"] == ["move", "skip"] and draw["from"] == "schedule" and draw["state_text"] == "Planned",
      f"a planned block can move or skip ({draw['can']})")
check(any(h["key"] == "running" for h in v["habits"]) and not v["calendar"]["connected"], "habits to add; calendar off")

# move
r = edit(op="move", key=draw["key"], at="20:30")
check(r.status_code == 200 and r.json()["reply"] == "Moved Drawing to 20:30 today.", f"move: {r.json().get('reply')}")
b = block(r.json(), "2026-10-02", "drawing")
check(b["at"] == "20:30" and b["moved"] and b["planned_at"] == "19:00", "the block is at 20:30, was 19:00")
r = edit(op="move", key=draw["key"], at="08:00")
check(r.status_code == 400 and "passed" in r.json()["detail"], f"a time that has passed is refused: {r.json()}")
r = edit(op="move", key=draw["key"], at="7pm")
check(r.status_code == 400 and r.json()["detail"] == "Use a time like 19:30.", "a bad time is refused")

# skip, bring back
math = block(view(), "2026-10-02", "math")
r = edit(op="skip", key=math["key"])
b = block(r.json(), "2026-10-02", "math")
check(r.json()["reply"] == "Skipped Math today." and b["state"] == "skipped" and b["can"] == ["unskip"],
      f"skip: {r.json()['reply']}, {b['state']}, {b['can']}")
check(r.json()["days"][0]["planned_min"] == 25, "a skipped block leaves the day's total")
r = edit(op="unskip", key=math["key"])
check(block(r.json(), "2026-10-02", "math")["state"] == "planned", "bring it back")

# add a one-off tomorrow, refuse a duplicate, remove it; a scheduled block can't be removed
r = edit(op="add", habit="running", date="2026-10-03", at="07:30", min=30)
check(r.status_code == 200 and r.json()["reply"] == "Added Running tomorrow at 07:30, 30 min.", f"add: {r.json()}")
run = block(r.json(), "2026-10-03", "running")
check(run and run["from"] == "you" and run["once"] and "remove" in run["can"], f"a one-off, yours, removable ({run})")
check(edit(op="add", habit="running", date="2026-10-03", at="07:30").status_code == 409, "the same block twice: 409")
check(edit(op="add", habit="piano", date="2026-10-03", at="07:30").status_code == 404, "an unknown habit: 404")
check(edit(op="add", habit="drawing", date="2026-10-30", at="07:30").status_code == 400, "beyond two weeks: 400")
check(edit(op="add", habit="drawing", date="2026-10-02", at="08:00").status_code == 400, "earlier today: 400")
check(edit(op="add", habit="drawing", date="2026-10-03", at="09:00", min=500).status_code == 400, "500 minutes: 400")
r = edit(op="remove", key=draw["key"])
check(r.status_code == 409 and "weekly schedule" in r.json()["detail"], f"remove a scheduled block: {r.json()}")
r = edit(op="remove", key=run["key"])
check(r.json()["reply"] == "Removed Running tomorrow." and block(r.json(), "2026-10-03", "running") is None, "removed")

# a day off clears the day; nothing can be added to it; back on restores it
r = edit(op="dayoff", date="2026-10-04")
sun = r.json()["days"][2]
check(r.json()["reply"] == "Sunday is a day off. I've cleared its block." and sun["off"] == "Day off",
      f"day off: {r.json()['reply']}")
check(all(b["state"] == "skipped" and b["can"] == [] for b in sun["blocks"]), "its blocks are skipped, not editable")
check(edit(op="add", habit="drawing", date="2026-10-04", at="10:00").status_code == 409, "no adding to a day off")
check(edit(op="skip", key=sun["blocks"][0]["key"]).status_code == 409, "no block edits on a day off")
r = edit(op="dayon", date="2026-10-04")
check(r.json()["reply"] == "Sunday is back on the plan." and not r.json()["days"][2]["off"], "back on")
check(edit(op="nap").status_code == 400, "an unknown op: 400")

# an accepted night review shows as a catch-up
cb = cal.add_once("math", "2026-10-03", "08:00", 60)
with open(config.DATA_DIR / "digests.jsonl", "a") as f:
    f.write(json.dumps({"slot": "2026-10-02-night", "kind": "night", "ts": clock.t, "accepted_at": clock.t,
                        "accepted_key": cb["key"]}) + "\n")
check(block(view(), "2026-10-03", "math")["from"] == "review", "an accepted night review block is a catch-up")

# past blocks are read-only: at 21:00 today's math (11:00) is over
clock.t = dt.datetime(2026, 10, 2, 21, 0).timestamp()
m = block(view(), "2026-10-02", "math")
check(m["can"] == [] and m["state"] in ("missed", "now"), f"a past block can't be edited ({m['state']}, {m['can']})")
r = edit(op="skip", key=m["key"])
check(r.status_code == 409, f"skipping a past block: {r.status_code}")
clock.t = dt.datetime(2026, 10, 2, 9, 30).timestamp()

# the phone: same view behind the key, tailnet or loopback only; an edit there is said on the notch
app = integrations.phone_app()
KEY = integrations.phone_secret()
ph = TestClient(app, client=("127.0.0.1", 50000))
lan = TestClient(app, client=("192.168.1.5", 1234))
check(ph.get("/api/phone/plan").status_code == 401, "no key: 401")
check(lan.get("/api/phone/plan", headers={"X-Alibi-Secret": KEY}).status_code == 403, "LAN: 403")
pv = ph.get("/api/phone/plan", headers={"X-Alibi-Secret": KEY}).json()
check(len(pv["days"]) == 3 and pv["days"][0]["name"] == "Today", "with the key: the same three days")
r = ph.post("/api/phone/plan/edit", headers={"X-Alibi-Secret": KEY}, json={"op": "skip", "key": math["key"]})
check(r.status_code == 400 and r.json()["error"] == "bad_op_id", "a phone write needs op_id")
r = ph.post("/api/phone/plan/edit", headers={"X-Alibi-Secret": KEY},
            json={"op_id": "p1", "client_ts": time.time(), "op": "move", "key": draw["key"], "at": "21:15"})
check(r.status_code == 200 and r.json()["reply"] == "Moved Drawing to 21:15 today.", f"phone move: {r.json().get('reply')}")
a = notify.recent_alerts(5)[-1]
check(a["kind"] == "info" and a["text"] == "From your iPhone: Moved Drawing to 21:15 today.", f"the notch says it: {a}")
r = ph.post("/api/phone/plan/edit", headers={"X-Alibi-Secret": KEY},
            json={"op_id": "p2", "client_ts": time.time(), "op": "move", "key": draw["key"], "at": "05:00"})
check(r.status_code == 400 and "passed" in r.json()["reply"], f"a phone refusal is one sentence: {r.json()}")

page = ph.get("/plan")
check(page.status_code == 200 and "Next three days" in page.text and "--accent:" in page.text
      and 'href="/web/css/tokens.css' not in page.text, "the phone page has tokens inlined")
check(web.get("/web/plan.html").status_code == 200, "the dashboard serves the page too")
check(KEY not in page.text, "the page never carries the key")
print("PASS test_plan_days")
