"""Integrations: guided Strava OAuth (fake Strava), token cache/rotation, 429/401, run types, paging, edits;
Apple Health via the opt-in phone listener; health habit rows in the report; claims settle without Strava."""
import datetime as dt, json, os, socket, stat, time
from harness import check, ROOT
os.environ["PHONE_HOST"] = "127.0.0.1"                       # never LAN in tests
s = socket.socket(); s.bind(("127.0.0.1", 0)); os.environ["PHONE_PORT"] = str(s.getsockname()[1]); s.close()
for k in ("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN"):
    os.environ.pop(k, None)

import requests, yaml
from fastapi.testclient import TestClient
from alibi import api, config, db, integrations, report, secrets as store, strava

# --- a fake Strava ------------------------------------------------------------------------------------------------
class R:
    def __init__(self, code=200, body=None, headers=None):
        self.status_code, self._b, self.headers = code, body, headers or {}
    def json(self): return self._b
    def raise_for_status(self):
        if self.status_code >= 400: raise requests.HTTPError(str(self.status_code))

t0 = report.week_start()
iso = lambda h: dt.datetime.fromtimestamp(t0 + h * 3600, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
FAKE = {"posts": [], "gets": [], "refresh_n": 0, "refresh_status": 200, "acts_status": 200,
        "acts": [{"id": 1, "name": "Trail", "sport_type": "TrailRun", "distance": 8000, "moving_time": 2900, "start_date": iso(8)},
                 {"id": 2, "name": "Treadmill", "sport_type": "VirtualRun", "distance": 6000, "moving_time": 2000, "start_date": iso(20)},
                 {"id": 3, "name": "Old payload", "type": "Run", "distance": 5100, "moving_time": 1800, "start_date": iso(30)},
                 {"id": 4, "name": "Ride", "sport_type": "Ride", "distance": 20000, "moving_time": 3000, "start_date": iso(31)}]
        + [{"id": 100 + i, "name": "Walk", "sport_type": "Walk", "distance": 1000, "moving_time": 600, "start_date": iso(40)}
           for i in range(50)]}

def fpost(url, data=None, timeout=None, **kw):
    FAKE["posts"].append((url, dict(data or {})))
    if url.endswith("/oauth/token"):
        if data["grant_type"] == "authorization_code":
            ok = data["code"] == "good" and data["client_secret"] == "a" * 40
            return R(200 if ok else 400, {"access_token": "acc0", "refresh_token": "ref0", "expires_at": time.time() + 21600,
                                          "athlete": {"id": 7, "firstname": "Sam", "lastname": "Lee"}} if ok else {})
        FAKE["refresh_n"] += 1
        if FAKE["refresh_status"] != 200:
            return R(FAKE["refresh_status"], {"message": "Bad Request"})
        n = FAKE["refresh_n"]
        return R(200, {"access_token": f"acc{n}", "refresh_token": f"ref{n}", "expires_at": time.time() + 21600})
    return R(200, {})

def fget(url, headers=None, params=None, timeout=None, **kw):
    FAKE["gets"].append((url, dict(params or {}), headers))
    if FAKE["acts_status"] != 200:
        return R(FAKE["acts_status"], {})
    p, n = params["page"], params["per_page"]
    return R(200, FAKE["acts"][(p - 1) * n: p * n], {"X-ReadRateLimit-Limit": "100,1000", "X-ReadRateLimit-Usage": "3,40"})

REAL_POST, REAL_GET = requests.post, requests.get
strava.requests.post, strava.requests.get = fpost, fget
# real network must never be touched
real = requests.Session.request
requests.Session.request = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network call in test"))

c = TestClient(api.app)

# --- Strava connect flow ------------------------------------------------------------------------------------------
st = c.get("/api/strava/status").json()
check(st["state"] == "not_set_up" and st["action"] == "Connect Strava", f"fresh install: {st['text']}")
r = c.get("/strava/setup")
check(r.status_code == 200 and "Authorization Callback Domain" in r.text and "localhost" in r.text, "setup page explains the Strava app form")
check(c.post("/api/strava/app", content=json.dumps({"client_id": "123", "client_secret": "a" * 40}),
             headers={"content-type": "text/plain"}).status_code == 415, "non-JSON POST refused (no drive-by from web pages)")
bad = c.post("/api/strava/app", json={"client_id": "abc", "client_secret": "x"})
check(bad.status_code == 400 and "number" in bad.json().get("detail", bad.text), "bad client id gets a plain explanation")
check(c.post("/api/strava/app", json={"client_id": "123", "client_secret": "a" * 40}).json()["status"]["state"]
      == "ready_to_authorize", "app saved -> ready to authorize")
sp = config.DATA_DIR / "secrets.json"
check(stat.S_IMODE(os.stat(sp).st_mode) == 0o600, "secrets.json is chmod 600")
r = c.get("/strava/connect", follow_redirects=False)
loc = r.headers["location"]
from urllib.parse import urlparse, parse_qs
q = parse_qs(urlparse(loc).query)
check(r.status_code == 302 and loc.startswith(strava.AUTH_URL) and q["redirect_uri"] == ["http://testserver/strava/callback"]
      and "activity:read_all" in q["scope"][0], "Connect redirects to Strava Authorize with our callback")
r = c.get("/strava/callback", params={"code": "good", "state": "forged", "scope": "read,activity:read_all"})
check("expired" in r.text and not strava.connected(), "callback with a wrong state is refused")
c.get("/strava/connect", follow_redirects=False)
r = c.get("/strava/callback", params={"code": "x", "state": store.get("strava_oauth_state")["v"], "error": "access_denied"})
check("chose not to connect" in r.text, "Cancel on Strava -> friendly page")
loc = c.get("/strava/connect", follow_redirects=False).headers["location"]
state = parse_qs(urlparse(loc).query)["state"][0]
r = c.get("/strava/callback", params={"code": "good", "state": state, "scope": "read,activity:read_all"})
check(r.status_code == 200 and "Strava is connected, Sam" in r.text and "Found 3 runs" in r.text, "callback: tokens saved, first sync, friendly page")
check(store.get("strava_refresh_token") == "ref0" and strava.connected(), "tokens in secrets.json, not .env")
names = sorted(r["name"] for r in strava.latest_runs(db.connect(), t0, time.time()))
check(names == ["Old payload", "Trail", "Treadmill"], f"TrailRun/VirtualRun/type=Run kept, Ride/Walk dropped: {names}")
pages = [g[1]["page"] for g in FAKE["gets"]]
check(pages == [1, 2], f"paged until a short page: {pages}")
check(FAKE["refresh_n"] == 0, "fresh access token cached (no refresh call)")

# --- token cache / rotation / rate limit / revoked ------------------------------------------------------------------
store.update(strava_expires_at=time.time() + 100)            # inside the 5-minute margin
strava.access_token()
check(FAKE["refresh_n"] == 1 and store.get("strava_refresh_token") == "ref1", "refresh near expiry persists the rotated refresh token")
strava.access_token()
check(FAKE["refresh_n"] == 1, "then cached again")

FAKE["acts"][0]["distance"] = 8400                           # edited on Strava
added = strava.sync()
check([a["name"] for a in added] == ["Trail"] and added[0]["edited"], "edited run re-added")
rj = report.build_json()["running"]
trail = [x for x in rj["runs"] if x["id"] == 1]
check(len(trail) == 1 and trail[0]["distance_km"] == 8.4, "report keeps the newest copy per run")
check(rj["qualifying"] == 3 and rj["strava"]["connected"] and "3 of 3 runs" in rj["text"], f"running row: {rj['text']}")

FAKE["acts_status"] = 429
try:
    strava.sync(); check(False, "429 raises")
except strava.RateLimited as e:
    check(e.until % 900 == 5 and e.until > time.time(), "429 backs off to the next 15-minute window")
check(integrations._maybe_strava(time.time() + 10**4 * 0, force=False) is None, "tick respects the backoff")
FAKE["acts_status"] = 200

store.update(strava_expires_at=0)
FAKE["refresh_status"] = 401
res = integrations.strava_sync_now()
st = strava.status()
check(res["needs_reconnect"] and st["state"] == "needs_reconnect" and st["action"] == "Reconnect Strava", f"revoked access -> '{st['text']}'")
FAKE["refresh_status"] = 200
check("Reconnect Strava" in c.get("/strava/setup").text, "setup page offers Reconnect")

r = c.post("/api/strava/disconnect", json={})
check(r.json()["status"]["state"] == "ready_to_authorize" and not store.get("strava_refresh_token"), "disconnect forgets tokens, keeps the app")

# --- Apple Health via the phone listener ----------------------------------------------------------------------------
check(not integrations.phone_running(), "phone sync is off by default")
info = c.post("/api/phone-sync/enable", json={}).json()
check(info["enabled"] and info["running"] and info["secret"], "phone sync turned on, key generated")
key, port = info["secret"], int(os.environ["PHONE_PORT"])
base = f"http://127.0.0.1:{port}"
requests.Session.request = real
requests.post, requests.get = REAL_POST, REAL_GET
try:
    r401 = requests.post(base + "/ingest", json={"steps": 9000}, timeout=5)
    check(r401.status_code == 401, "phone ingest without key -> 401")
    today = dt.date.today().isoformat()
    ok = requests.post(base + "/ingest", headers={"X-Alibi-Secret": key},
                       json={"steps": "9,120", "sleep_h": "27000", "mindful_min": 600}, timeout=5)
    check(ok.status_code == 200 and "Steps 9,120" in ok.json()["message"] and "Sleep 7 h 30" in ok.json()["message"],
          f"flat Shortcut body accepted, units fixed: {ok.json()['message']}")
    yday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    requests.post(base + "/ingest", headers={"X-Alibi-Secret": key},
                  json={"source": "health", "kind": "samples", "payload": {"date": yday, "steps": 4000, "sleep_h": 8}}, timeout=5)
    requests.post(base + "/ingest", headers={"X-Alibi-Secret": key}, json={"date": yday, "steps": 8500, "sleep_h": 8}, timeout=5)
    page = requests.get(base + "/phone", timeout=5).text
    check("Get Contents of URL" in page and key not in page, "phone page has Shortcut steps and never prints the key")
    api404 = requests.get(base + "/api/state", timeout=5).status_code
    check(api404 == 404, "phone listener exposes nothing but /ingest and /phone")
finally:
    c.post("/api/phone-sync/disable", json={})
try:
    socket.create_connection(("127.0.0.1", port), timeout=1).close(); closed = False
except OSError:
    closed = True
check(closed and not integrations.phone_running(), "disable stops the listener")

con = db.connect()
ev = con.execute("SELECT * FROM events WHERE source='health' ORDER BY id").fetchall()
noon = dt.datetime.fromisoformat(today).replace(hour=12).timestamp()
check(all(e["session_id"] is None for e in ev) and any(e["ts"] == noon for e in ev), "health samples: no session id, ts = noon of the day")
days = integrations.health_days(con)
check(days[yday]["steps"] == 8500, "latest sample per day wins")

cfg = yaml.safe_load(open(config.HABITS_PATH))
cfg["habits"]["walk"] = {"source": "health", "metric": "steps", "daily_target": 8000, "display": "Walk 8,000 steps"}
cfg["habits"]["sleep"] = {"source": "health", "metric": "sleep_h", "daily_target": 7, "display": "Sleep 7 h"}
yaml.safe_dump(cfg, open(config.HABITS_PATH, "w"))
rep = report.build_json()
hw = {x["habit"]: x for x in rep["health"]}
check("walk" not in [x["habit"] for x in rep["rows"]], "health habits stay out of the minutes table")
check(hw["walk"]["today_met"] and hw["walk"]["today_text"] == "9,120", f"walk: {hw['walk']['text']}")
check(hw["walk"]["streak_days"] >= 1 and hw["sleep"]["status"] == "aligned", f"sleep: {hw['sleep']['text']}")
check("walk" in rep["table"] and "Walk 8,000 steps" in rep["summary"], "health rows in table + summary")
check(c.get("/api/apple-health/status").json()["connected"], "health status reports data")
check(len(c.get("/api/apple-health/days?days=3").json()["days"]) == 2, "days endpoint")
check(c.get("/api/integrations").status_code == 200, "integrations summary")
check(c.get("/phone").status_code == 200 and "Turn on iPhone sync" in c.get("/phone").text, "Mac phone page offers opt-in")

# --- claims settle every tick, with or without Strava ----------------------------------------------------------------
db.add_event(con, "user", "claim", {"habit": "running", "min_km": 5, "until": time.time() - 1})
integrations.tick(con, time.time())
settled = con.execute("SELECT count(*) FROM events WHERE kind='claim_settled'").fetchone()[0]
check(settled == 1, "expired run claim settled by the plugin tick")
check(".gitignore" and "data/secrets.json" in (ROOT / ".gitignore").read_text(), "secrets are git-ignored")
print("Integrations passed.")
