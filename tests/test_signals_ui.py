"""Signals page (alibi/web/signals.html, GET /signals): served, and every API it reads answers in the shape it uses —
on an empty install and on a seeded day (tests/seed_signals.py: phone, Mac, heart, Health, three sessions)."""
import datetime as dt, re, sys, time
from harness import ROOT, Clock, check
from fastapi.testclient import TestClient
from alibi import api

c = TestClient(api.app)
html = (ROOT / "alibi" / "web" / "signals.html").read_text()

r = c.get("/signals")
check(r.status_code == 200 and "Is Alibi" in r.text and r.headers["content-type"].startswith("text/html"), "GET /signals serves the page")
check(c.get("/web/signals.html").status_code == 200, "page also served at /web/signals.html")
for el in ("groups", "stats", "plot", "lanelabels", "sesstabs", "sessbody", "hgrid", "next-card", "meter"):
    check(f'id="{el}"' in html, f"page has #{el}")
css = ""                                              # tokens may live inline or in the shared linked stylesheet
if "/web/css/tokens.css" in html:
    css = (ROOT / "alibi" / "web" / "css" / "tokens.css").read_text()
    check(c.get("/web/css/tokens.css").status_code == 200, "linked tokens.css is served")
both = html + css
check(re.search(r"prefers-color-scheme:\s*dark", both) and '[data-theme="dark"]' in both and "#76B900" in both.upper(),
      "NVIDIA tokens + dark mode")
check(not re.search(r"<script[^>]+src=", html), "no external scripts")

urls = sorted(set(re.findall(r'get\(`?"?(/api/[a-z\-/]+)', html)))
check({"/api/signals/status", "/api/signals/live", "/api/health", "/api/signals", "/api/sessions", "/api/feed",
       "/api/apple-health/days"} <= set(urls), f"page reads the expected APIs ({', '.join(urls)})")

today = dt.date.today().isoformat()
# --- empty install: nothing crashes, the page gets empty shapes -------------------------------------------------------
st = c.get("/api/signals/status").json()
check(all({"key", "label", "state", "text", "fix"} <= set(x) for x in st["sources"]), "status rows carry key/label/state/text/fix")
d = c.get(f"/api/signals?day={today}").json()
check(d["timeline"] == [] and "screentime" in d["summary"], "empty day: empty timeline, summary shape intact")
check(c.get("/api/sessions?limit=200").json() == [], "no sessions yet")

# --- seeded day -------------------------------------------------------------------------------------------------------
clock = Clock()                                   # pin "now" to 18:00 today so the seeded day never straddles midnight
clock.t = dt.datetime.combine(dt.date.today(), dt.time(18, 0)).timestamp()
sys.argv = ["seed_signals.py", "--hours-back", "8"]
import seed_signals
seed_signals.main()
st = c.get("/api/signals/status").json()
keys = {x["key"] for x in st["sources"]}
page_keys = set(re.findall(r'"((?:phone|health|mac)\.[a-z_]+)"', html))
check(keys <= page_keys | {"phone.listener"}, f"every status key has a home on the page (missing: {keys - page_keys})")
ok = [x["key"] for x in st["sources"] if x["state"] == "ok"]
check({"phone.screentime", "phone.motion", "health.heart", "mac.presence", "mac.notifications"} <= set(ok),
      "seeded sources show as live")
d = c.get(f"/api/signals?day={today}").json()
kinds = {x["kind"] for x in d["timeline"]}
check({"screentime", "pickup", "motion", "heart", "notifications", "meeting", "location", "git"} <= kinds,
      f"day timeline feeds every lane ({sorted(kinds)})")
check(any(re.search(r"Heart \d+ bpm", x["text"]) for x in d["timeline"] if x["kind"] == "heart"), "heart text parses for the sparkline")
check(any(re.search(r"\+[\d.]+ min", x["text"]) for x in d["timeline"] if x["kind"] == "screentime"), "screen-time deltas parse")
check(d["summary"]["health"].get("sleep", {}).get("deep_h") is not None, "today's Health has sleep stages")
ss = [s for s in c.get("/api/sessions?limit=200").json() if s["day"] == today]
check(len(ss) == 3 and all("labels" in s and "on_task_ratio" in s for s in ss), "three sessions for the tabs and bands")
cpp = next(s for s in ss if s["habit"] == "cpp")
sd = c.get(f"/api/signals?session={cpp['id']}").json()
check(sd["cap"] and sd["cap"]["to"] < sd["cap"]["from"] and "Instagram" in sd["cap"]["reason"], "C++ score lowered, with the reason")
check(sd["off_s"]["phone"] > 0 and sd["hints"].get("off_task"), "off-task stretches + hint counts for the session card")
check(cpp.get("signals_reason"), "sessions list carries signals_reason (the 'lowered' tab mark)")
f = c.get(f"/api/feed?session={cpp['id']}&limit=200").json()
check(any(i["source"] == "screen" for i in f["items"]), "screen lane has per-window rows")
hd = c.get("/api/apple-health/days?days=60").json()["days"]
check(len(hd) >= 14 and hd[0]["date"] == today, "14 days of Health for the trend lines")
print("signals UI OK")
