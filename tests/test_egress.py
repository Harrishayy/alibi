"""F6 DoD: the egress view says exactly where data goes (AGENTS.md rule 5), flips when the Spark stops answering,
hourly() gives 24 ints per key, the git row waits instead of nagging, Strava gets a row only when set up, and no secret
ever appears in the JSON."""
import json, os, subprocess, sys, time
from harness import check, ROOT
from fastapi.testclient import TestClient
from alibi import api, config, db, signals

SPARK = "http://100.76.35.21:8000/v1"
SECRET = "nvapi-PLANTEDsecret0123456789"
c = TestClient(api.app)
up = {"v": True}
probes = []
signals.PROBE = lambda base: probes.append(base) or up["v"]


def rows(d):
    return {r["what"]: r for r in d["rows"]}


def get():
    r = c.get("/api/signals/egress")
    assert r.status_code == 200, r.text
    return r.json()


# --- frames ---------------------------------------------------------------------------------------------------------
config.VISION_BACKEND = "apple"
d = get()
f = rows(d)["Camera frames"]
check(f["where"] == "mac" and f["active"] and f["why"].startswith("Frames never leave the Mac."),
      "apple: frames stay on the Mac, worded per rule 5")
check(d["summary"]["where"] == "mac" and not d["summary"]["active"], "no model: summary stays on the Mac")
config.VISION_BACKEND = "mock"
check(rows(get())["Camera frames"]["where"] == "mac", "mock: frames stay on the Mac")

# explicit VISION_BACKEND=nvidia, from the environment, through config at import (a fresh process)
code = ("import json; from alibi import signals; signals.PROBE = lambda b: True; "
        "print(json.dumps(signals.egress()))")
env = dict(os.environ, VISION_BACKEND="nvidia", VLM_BASE_URL="https://integrate.api.nvidia.com/v1",
           VLM_MODEL="meta/llama-3.2-11b-vision-instruct", NVIDIA_API_KEY=SECRET)
out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
check(out.returncode == 0, "egress runs in a fresh process with VISION_BACKEND=nvidia" + ("" if out.returncode == 0 else out.stderr[-400:]))
sub = json.loads(out.stdout.strip().splitlines()[-1])
fr = rows(sub)["Camera frames"]
check(fr["where"] == "nvidia_build" and "never leave" not in fr["why"].lower(),
      "explicit VISION_BACKEND=nvidia: frames go to nvidia_build, and it doesn't claim they stay")
check(SECRET not in out.stdout, "the nvapi key is not in the subprocess JSON")

# --- the Spark: probe up -> tailnet:spark active; probe down -> inactive and the summary is mac ----------------------
config.VISION_BACKEND = "apple"
config.TEXT_READY, config.LLM_BASE_URL, config.NVIDIA_API_KEY = True, SPARK, SECRET
os.environ["NEMOCLAW_URL"] = "https://spark.tail0000.ts.net:8443/v1"
os.environ["NEMOCLAW_TOKEN"] = "nemo-PLANTED-token-xyz"
signals._probe_cache.clear()
d = get()
t = rows(d)["Habit names and minutes"]
check(t["where"] == "tailnet:spark" and t["active"] and t["why"] == "Habit names and minutes go to your Spark over Tailscale.",
      "Spark up: habit names and minutes go to tailnet:spark, active, exact wording")
check(d["summary"] == {"where": "tailnet:spark", "active": True, "text": "Summaries go to your Spark over Tailscale.",
                       "leaves_tailnet": True}, "summary: tailnet:spark, active")
s = rows(d)["Search questions"]
check(s["where"] == "search_provider" and s["why"] == "Search questions go to the search provider.",
      "Ask configured: search questions go to the search provider")

n = len(probes)
get()
check(len(probes) == n, "the probe is cached (no second probe within 60 s)")

up["v"] = False
signals._probe_cache.clear()
d = get()
t = rows(d)["Habit names and minutes"]
check(t["where"] == "tailnet:spark" and not t["active"], "Spark down: the row stays, dimmed (active false)")
check(d["summary"]["where"] == "mac" and not d["summary"]["active"] and d["summary"]["text"] == "Summaries stay on this Mac.",
      "Spark down: summary falls back to mac")
check(not rows(d)["Search questions"]["active"], "Spark down: search is inactive too")

# the cache expires after 60 s: the Spark comes back and the row flips on its own
up["v"] = True
signals.probe(SPARK, now=time.time() + 61)
check(signals.egress(now=time.time() + 62)["summary"]["where"] == "tailnet:spark", "after 60 s a fresh probe flips it back")

blob = c.get("/api/signals/egress").text
check(SECRET not in blob and "nemo-PLANTED" not in blob and "PLANTED" not in blob, "no planted secret appears in the JSON")

# --- Strava: a row only when it's set up; the token never appears ------------------------------------------------------
from alibi import secrets as store
for k in ("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN"):
    os.environ.pop(k, None)                                     # .env may hold real ones; this test plants its own
check("Strava runs" not in rows(get()), "Strava not set up: no Strava row")
up["v"] = False                                                 # the Spark is down: only Strava can leave the tailnet
signals._probe_cache.clear()
os.environ.pop("NEMOCLAW_URL", None)
check(get()["summary"]["leaves_tailnet"] is False, "nothing active leaves the tailnet before Strava")
STRAVA_TOKEN = "strava-PLANTED-refresh-987"
store.update(strava_client_id="PLANTEDcid42", strava_client_secret="strava-PLANTED-secret-654", strava_refresh_token=STRAVA_TOKEN)
d = get()
sv = rows(d).get("Strava runs")
check(sv == {"what": "Strava runs", "where": "strava", "active": True, "host": "www.strava.com",
             "why": "Alibi sends your Strava token to strava.com and reads your runs back."},
      f"Strava connected: row present, active ({sv})")
check(d["summary"]["leaves_tailnet"] is True, "an active Strava row counts as leaving the tailnet")
blob = c.get("/api/signals/egress").text
check(STRAVA_TOKEN not in blob and "PLANTED" not in blob, "no Strava token or secret in the JSON")
store.update(strava_refresh_token=None)
sv = rows(get()).get("Strava runs")
check(sv and sv["active"] is False, "Strava app saved but not authorized: row stays, inactive")

# --- hourly -----------------------------------------------------------------------------------------------------------
con = db.connect()
now = time.time()
signals.store(con, "phone", "pickup", {"ts": now}, ts=now)
signals.store(con, "phone", "pickup", {"ts": now - 3600}, ts=now - 3600)
signals.store(con, "phone", "pickup", {"ts": now - 30 * 3600}, ts=now - 30 * 3600)   # outside the window
h = signals.hourly(con, ["phone.pickup", "mac.git"])
check(all(len(v) == 24 and all(isinstance(x, int) for x in v) for v in h.values()), "hourly: 24 ints per key")
check(h["phone.pickup"][-1] == 1 and h["phone.pickup"][-2] == 1 and sum(h["phone.pickup"]) == 2 and sum(h["mac.git"]) == 0,
      "hourly: this hour last, older rows outside the window left out")
r = c.get("/api/signals/hourly?keys=phone.pickup,mac.git&hours=24")
check(r.status_code == 200 and len(r.json()["series"]["phone.pickup"]) == 24, "GET /api/signals/hourly")
check(c.get("/api/signals/hourly?keys=;drop").status_code == 400, "hourly rejects junk keys")

# --- git row: repos configured but quiet -> waiting, not missing ------------------------------------------------------
from alibi import mac_signals
real = mac_signals.repos
mac_signals.repos = lambda con, now: [ROOT]
g = next(x for x in signals.status(con)["sources"] if x["key"] == "mac.git")
check(g["state"] == "waiting" and g["text"].startswith("No commits in the last ") and g["fix"] is None,
      f"git with repos but no commits reads waiting: {g['text']}")
mac_signals.repos = lambda con, now: []
g = next(x for x in signals.status(con)["sources"] if x["key"] == "mac.git")
check(g["state"] == "missing" and "repos:" in g["fix"], "git with no repos still says how to add them")
mac_signals.repos = real
print("PASS")
