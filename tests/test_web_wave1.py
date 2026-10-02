"""Web habits DoD: the "Your habits" sheet is wired into the dashboard, its copy has no "!", and the writes it makes
(re-read-and-merge PUT, one-request add, plain 400s) round-trip through the real API without losing anything."""
import json, re
from harness import check, ROOT
from fastapi.testclient import TestClient
from alibi import api, config

c = TestClient(api.app)
WEB = ROOT / "alibi" / "web"


def strings(js: str) -> list[str]:
    """String literals in a JS source (quotes and the static parts of template literals), skipping comments and
    regex literals, so the copy rule never trips on a `!==` or a `!x`."""
    out, i, n, prev = [], 0, len(js), ""
    while i < n:
        ch = js[i]
        if js.startswith("//", i):
            i = js.find("\n", i)
            i = n if i < 0 else i
            continue
        if js.startswith("/*", i):
            i = js.find("*/", i + 2) + 2
            continue
        if ch == "/" and (prev in "(,=:[!&|?{};+-*%<>~^" or prev == ""):     # a regex literal
            j, cls = i + 1, False
            while j < n and (js[j] != "/" or cls):
                if js[j] == "\\":
                    j += 1
                elif js[j] == "[":
                    cls = True
                elif js[j] == "]":
                    cls = False
                j += 1
            i, prev = j + 1, "x"
            continue
        if ch in "\"'":
            j, buf = i + 1, []
            while j < n and js[j] != ch:
                buf.append(js[j:j + 2] if js[j] == "\\" else js[j])
                j += 2 if js[j] == "\\" else 1
            out.append("".join(buf))
            i, prev = j + 1, "x"
            continue
        if ch == "`":
            j, buf = i + 1, []
            while j < n and js[j] != "`":
                if js[j] == "\\":
                    buf.append(js[j:j + 2]); j += 2; continue
                if js.startswith("${", j):                      # skip the expression, nested templates included
                    k, d = j + 2, 1
                    while k < n and d:
                        if js[k] == "{": d += 1
                        elif js[k] == "}": d -= 1
                        elif js[k] in "\"'`":
                            q, k = js[k], k + 1
                            while k < n and js[k] != q:
                                k += 2 if js[k] == "\\" else 1
                        k += 1
                    j = k; buf.append(" "); continue
                buf.append(js[j]); j += 1
            out.append("".join(buf))
            i, prev = j + 1, "x"
            continue
        if not ch.isspace():
            prev = ch
        i += 1
    return out


# --- the page wires the sheet in ----------------------------------------------------------------------------------
r = c.get("/")
html = r.text
check(r.status_code == 200 and "/web/js/habits.js" in html and "/web/css/habits.css" in html,
      "/ serves index.html, which loads habits.js and habits.css")
check('id="habitsSheet"' in html and 'id="habitsBtn"' in html and 'aria-labelledby="hsTitle"' in html,
      "index.html has the #habitsSheet dialog and the header #habitsBtn")
check(html.index("/web/js/habits.js") < html.index("/web/js/boot.js"), "habits.js loads before boot.js (route() can open it)")
js = c.get("/web/js/habits.js")
check(js.status_code == 200 and "window.openHabits" in js.text and "X-Alibi-Client" in js.text and '"undo"' in js.text,
      "/web/js/habits.js is served, exposes openHabits, tags writes as the dashboard and undo as undo")
lits = strings(js.text)
bang = [s for s in lits if "!" in s]
check(len(lits) > 200 and not bang, f"no '!' in habits.js copy ({len(lits)} string literals checked){': ' + repr(bang[:3]) if bang else ''}")
check('data-close="' not in js.text, "the sheet never uses core.js's data-close (closeLayer would throw on it)")
for name in ("today_plan", "brief", "habits_saved"):
    f = c.get(f"/web/fixtures/{name}.json")
    j = f.json() if f.status_code == 200 else {}
    check(f.status_code == 200 and "plan_today" in j and "phrase" in j and "agent" in j, f"?stage={name} fixture is served with the plan_today, phrase and agent keys")

# --- the re-read-and-merge PUT (one habit per write) --------------------------------------------------------------
before = c.get("/api/habits").json()["habits"]
order = list(before)
fresh = c.get("/api/habits").json()["habits"]
fresh["drawing"]["schedule"] = [{"days": ["mon", "wed", "fri"], "at": "19:00", "min": 25}]
r = c.put("/api/habits", json={"habits": fresh}, headers={"X-Alibi-Client": "dashboard"})
check(r.status_code == 200, f"PUT with a schedule for drawing: {r.status_code}")
before = c.get("/api/habits").json()["habits"]
m = json.loads(json.dumps(before))                      # the editor's structuredClone
m["drawing"]["schedule"][0]["days"] = ["mon", "wed", "fri", "sat"]
r = c.put("/api/habits", json={"habits": m}, headers={"X-Alibi-Client": "dashboard"})
after = r.json()["habits"]
check(r.status_code == 200 and after["drawing"]["schedule"][0]["days"] == ["mon", "wed", "fri", "sat"],
      "re-read-and-merge PUT adds sat to drawing")
check(list(after) == order and all(after[k] == before[k] for k in order if k != "drawing"),
      "every other habit is untouched and the order is kept")

# --- add is one request; a second add of the same name is a plain 400 ---------------------------------------------
piano = {"template": "instrument", "name": "Piano", "minutes": 20, "check": "camera",
         "schedule": [{"days": ["tue", "thu"], "at": "21:00", "min": 20}], "calendar": True}
r = c.post("/api/habits/add", json=piano, headers={"X-Alibi-Client": "dashboard"})
j = r.json()
h = config.habits()["habits"].get("piano") or {}
check(r.status_code == 200 and j.get("key") == "piano" and h.get("schedule") == piano["schedule"] and h.get("default_min") == 20,
      f"POST /api/habits/add Piano (instrument, Tue/Thu 21:00, 20 min) -> key piano: {j.get('key')} {h.get('schedule')}")
check(list(config.habits()["habits"])[-1] == "piano" and list(config.habits()["habits"])[:len(order)] == order,
      "the new habit goes last; the others keep their places")
r = c.post("/api/habits/add", json=piano)
check(r.status_code == 400 and "is already one of your habits" in r.json().get("detail", ""), f"adding Piano twice: 400 {r.json().get('detail')}")

# --- validation comes back as a 400 the editor maps to a field ----------------------------------------------------
m = c.get("/api/habits").json()["habits"]
m["drawing"]["schedule"][0]["at"] = "25:00"
r = c.put("/api/habits", json={"habits": m})
check(r.status_code == 400 and "isn't a time" in r.json()["detail"], f"a 25:00 time: 400 {r.json()['detail']}")
check(config.habits()["habits"]["drawing"]["schedule"][0]["at"] == "19:00", "a rejected PUT changes nothing")

# --- phone_shield off and an Apple Health schedule survive a round trip (setup.js:237 used to drop the latter) ------
m = c.get("/api/habits").json()["habits"]
m["drawing"]["phone_shield"] = False
m["meditate"] = {"source": "health", "metric": "mindful_min", "daily_target": 10, "display": "Meditate",
                 "schedule": [{"days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"], "at": "07:00", "min": 10}]}
r = c.put("/api/habits", json={"habits": m}, headers={"X-Alibi-Client": "dashboard"})
check(r.status_code == 200, f"PUT with phone_shield false and a Health habit: {r.status_code}")
r = c.put("/api/habits", json={"habits": c.get("/api/habits").json()["habits"]})    # a second, unchanged write
got = c.get("/api/habits").json()["habits"]
check(got["drawing"].get("phone_shield") is False, "phone_shield: false survives a round trip")
check(got["meditate"].get("schedule") == m["meditate"]["schedule"] and got["meditate"].get("calendar") is True,
      f"the Health habit keeps its 07:00 schedule: {got['meditate'].get('schedule')}")

# --- the old Setup form, still the fallback, no longer drops Health schedules -------------------------------------
setup = (WEB / "js" / "setup.js").read_text()
check("delete out[key].schedule; delete out[key].calendar; if (label)" not in setup, "setup.js keeps Health schedules on save")

print("Web habits DoD passed.")
