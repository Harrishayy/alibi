"""Agent API (docs/AGENT.md) + Spark relay: the Spark reads context and posts briefs over :8766 with its own token,
can't touch sessions, and the relay mirrors the Mac and degrades to the mirror when the Mac sleeps."""
import datetime as dt, json, os, socket, threading, time
from harness import check, Clock
s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
os.environ["MAC_URL"] = f"http://127.0.0.1:{PORT}"

import uvicorn
from fastapi.testclient import TestClient
from alibi import cli, db, digest, integrations, routes_agent

TOKEN = routes_agent.agent_token()
os.environ["ALIBI_AGENT_TOKEN"] = TOKEN
from alibi import relay
relay.MAC_TOKEN = TOKEN
H = {"X-Alibi-Agent-Token": TOKEN}
phone = integrations.phone_app()
tail = TestClient(phone, client=("100.100.100.100", 5000))       # the Spark, on the tailnet
lan = TestClient(phone, client=("192.168.1.20", 5000))

# --- the Mac's agent API --------------------------------------------------------------------------------------------
check(lan.get("/api/agent/ping", headers=H).status_code == 403, "agent API: LAN source refused (403)")
check(tail.get("/api/agent/ping").status_code == 401, "agent API: no token -> 401")
check(tail.get(f"/api/agent/ping?key={TOKEN}").status_code == 401, "agent API: token in the query string -> 401")
check(tail.get("/api/agent/ping", headers={"X-Alibi-Agent-Token": integrations.phone_secret()}).status_code == 401,
      "agent API: the phone key is not the agent token")
check(tail.get("/api/agent/ping", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200,
      "agent API: Bearer form accepted")
p = tail.get("/api/agent/ping", headers=H).json()
check(p["ok"] and p["tz"] == "Europe/London" and p["agent_last_seen"], "ping: ok, tz, agent_last_seen recorded")

con = db.connect()
clock = Clock()
cli.start(con, "draw for 25 minutes")
clock.advance(26 * 60)
cli.end(con)
today = dt.date.fromtimestamp(time.time())
kind, slot, slot_at = [x for x in digest.slots(today) if x[0] == "checkpoint"][-1]
clock.t = slot_at + 300                                          # five minutes after a real checkpoint slot
digest.run(kind, clock.t, send=False, slot=slot)
ctx = tail.get("/api/agent/context", headers=H).json()
check({"week", "habits", "today", "free_gaps_tomorrow", "last_night", "milestones", "signals"} <= set(ctx),
      "context: every contract section present")
check(any(h["key"] == "drawing" and "status3" in h and "buffer_days" in h for h in ctx["habits"]),
      "context: habit rows carry status3 and buffer_days")
blob = json.dumps(ctx).lower()
check("camera frames" in ctx["never_included"] and ".jpg" not in blob and "frame" not in json.dumps(ctx["habits"]),
      "context: no frames or file paths, and says what it never includes")

# --- today's sessions, the run claim and days off (on a day of their own, two days on) --------------------------------
from alibi import calendar_sync, config, signals
t_back = clock.t
day = dt.date.fromtimestamp(t_back) + dt.timedelta(days=2)
at = lambda h, m=0: dt.datetime.combine(day, dt.time(h, m)).timestamp()
clock.t = at(8)
db.add_event(con, "user", "claim", {"habit": "running", "min_km": 5.0, "until": at(10)}, ts=at(8))
claim_id = con.execute("SELECT max(id) FROM events WHERE source='user' AND kind='claim'").fetchone()[0]
db.add_event(con, "strava", "activity", {"name": "Evening Run", "distance_km": 5.2}, ts=at(8, 5))
db.add_event(con, "alibi", "claim_settled", {"claim_id": claim_id, "verified": True}, ts=at(8, 41))
clock.t = at(9)
cli.start(con, "draw for 8 minutes")
s1 = db.active_session(con)
signals.store(con, "phone", "shield", {"on": True, "apps": 2}, ts=at(9, 1))
signals.store(con, "phone", "app", {"opened": True, "reason": "YouTube"}, ts=at(9, 2))
db.add_event(con, "alibi", "nudge", {"label": "phone"}, session_id=s1["id"], ts=at(9, 2))
clock.t = at(9, 8)
cli.end(con)
clock.t = at(10)
db.add_event(con, "user", "claim", {"habit": "running", "min_km": 5.0, "until": at(12)}, ts=at(10))   # still open
cli.start(con, "math for 30 minutes")
signals.store(con, "phone", "shield", {"on": False, "apps": 0}, ts=at(10, 1))
clock.t = at(10, 12)
ctx = tail.get("/api/agent/context", headers=H).json()
S, C = ctx["sessions_today"], ctx["claims_today"]
check([set(x) for x in S] == [{"habit", "label", "at", "min", "verdict", "nudges", "phone_blocked"}] * 2 and
      [set(x) for x in C] == [{"habit", "label", "at", "km", "verified", "settled_at"}] * 2,
      "context: sessions_today and claims_today rows carry exactly the documented keys")
v1 = db.get_session(con, s1["id"])["verdict"]
check(v1 and S[0] == {"habit": "drawing", "label": "Drawing", "at": "09:00", "min": 8, "verdict": v1, "nudges": 1,
                      "phone_blocked": True}, f"context: a finished session: start, minutes, verdict, nudges, iPhone block {S[0]}")
check(S[1] == {"habit": "math", "label": "Math", "at": "10:00", "min": 12, "verdict": None, "nudges": 0,
               "phone_blocked": False}, f"context: a live session has no verdict yet; a shield-off row isn't a block {S[1]}")
check(C == [{"habit": "running", "label": "Running", "at": "08:00", "km": 5.2, "verified": True, "settled_at": "08:41"},
            {"habit": "running", "label": "Running", "at": "10:00", "km": None, "verified": None, "settled_at": None}],
      f"context: a settled claim shows its run and when; an open one is nulls {C}")
check(ctx["away"] == [] and not (config.DATA_DIR / "away.json").exists(), "context: away is [] with no away.json")
check("YouTube" not in json.dumps(ctx) and ctx["never_included"] == routes_agent.NEVER_INCLUDED,
      "context: aggregates only (no app names), never_included unchanged")
had_away, real_away, asked = hasattr(calendar_sync, "away_days"), getattr(calendar_sync, "away_days", None), []
calendar_sync.away_days = lambda d0, n: asked.append((d0, n)) or [{"date": dt.date(2026, 10, 5), "label": "Holiday", "x": 1}]
check(routes_agent.context(clock.t)["away"] == [{"date": "2026-10-05", "label": "Holiday"}] and asked == [(day, 14)],
      "context: away is calendar_sync.away_days(today, 14), date and label only")


def boom(*a):
    raise RuntimeError("away.json is corrupt")


calendar_sync.away_days, real_sessions, routes_agent._sessions_today = boom, routes_agent._sessions_today, boom
r = tail.get("/api/agent/context", headers=H)
check(r.status_code == 200 and r.json()["away"] == [] and r.json()["sessions_today"] == [] and
      len(r.json()["claims_today"]) == 2, "context: a helper that raises costs only its own key; still a 200")
routes_agent._sessions_today = real_sessions
if had_away:
    calendar_sync.away_days = real_away
else:
    del calendar_sync.away_days
cli.end(con)
clock.t = t_back

dg = tail.get("/api/agent/digests?limit=5", headers=H).json()
check(dg["items"] and dg["items"][0]["via"] == "rules", "digests: Alibi's own rules digests readable")

for path in ("/api/agent/say", "/api/agent/session/end", "/api/agent/habits"):
    check(tail.post(path, headers=H, json={}).status_code in (404, 405), f"agent can't write {path}")

good = {"idempotency_key": "t-1", "slot": slot, "kind": "checkpoint", "text": "Drawing slipped today.", "items": [],
        "links": [{"title": "x", "url": "https://example.com"}], "model": "nvidia/nemotron-3-super-120b-a12b"}
for bad, why in (({**good, "kind": "lunch"}, "bad_kind"), ({**good, "slot": "tomorrow"}, "bad_slot"),
                 ({**good, "text": "x" * 601}, "bad_text"), ({**good, "links": [{"url": "http://plain"}]}, "bad_links")):
    r = tail.post("/api/agent/brief", headers=H, json=bad)
    check(r.status_code == 400 and r.json()["error"] == why, f"brief rejected: {why}")
check(tail.post("/api/agent/brief", headers={**H, "Content-Type": "application/json"},
                content=json.dumps({**good, "text": "x" * 20000})).status_code == 413, "brief over 16 KB -> 413")
r1 = tail.post("/api/agent/brief", headers=H, json=good).json()
check(r1["ok"] and r1["stored"] == slot and r1["shown_as"] == "agent" and r1["rules_version_folded"],
      f"brief stored, shown as agent (on time), rules version exists: {r1}")
r2 = tail.post("/api/agent/brief", headers=H, json={**good, "text": "different"})
check(r2.headers.get("X-Alibi-Replay") == "1" and r2.json() == r1, "same idempotency_key -> the stored response")
late = {**good, "idempotency_key": "t-2", "slot": f"{today - dt.timedelta(days=2)}-morning", "kind": "morning"}
check(tail.post("/api/agent/brief", headers=H, json=late).json()["shown_as"] == "stored", "late brief stored, not shown")
check(routes_agent.briefs()[-1]["via"] == "nemoclaw" and not db.session_events(con, 1, "agent"),
      "briefs live in agent_briefs.jsonl tagged nemoclaw, never in events")

# --- relay against a live :8766 -------------------------------------------------------------------------------------
srv = uvicorn.Server(uvicorn.Config(phone, host="127.0.0.1", port=PORT, log_level="error"))
threading.Thread(target=srv.run, daemon=True).start()
for _ in range(100):
    if srv.started: break
    time.sleep(0.05)
sandbox = TestClient(relay.app, client=("172.18.0.2", 4000))       # OpenShell gateway on the Docker bridge
outsider = TestClient(relay.app, client=("100.64.205.70", 4000))   # another tailnet node
check(relay.poll_once(), "relay: first mirror pass reaches the Mac's agent API")
check(sandbox.get("/status").json()["mac_online"], "relay: /status says the Mac is online")
check(outsider.get("/status").status_code == 401, "relay: other tailnet nodes are refused")
lc = sandbox.get("/context").json()
check(lc.get("stale") is False and lc["slot_hint"]["night"].endswith("-night"), "relay: /context is live, with slot hints")
check(sandbox.post("/say", json={"text": "draw"}).status_code in (404, 405), "relay: no session writes exposed")
rb = sandbox.post("/brief", json={**good, "idempotency_key": "t-3"})
check(rb.status_code == 200 and rb.json()["ok"], "relay: /brief reaches the Mac")
n = len((relay.DIR / "digests.jsonl").read_text().splitlines())
relay.poll_once()
check(len((relay.DIR / "digests.jsonl").read_text().splitlines()) == n, "relay: digests are logged once, not every poll")

srv.should_exit = True
time.sleep(0.5)
check(not relay.poll_once(), "relay: poll notices the Mac is gone")
c = sandbox.get("/context").json()
check(c.get("stale") is True and c.get("last_seen"), "relay: /context falls back to the mirror, marked stale")
r = sandbox.post("/brief", json={**good, "idempotency_key": "t-4"})
check(r.status_code == 503 and "isn't reachable" in r.json()["error"], "relay: brief fails plainly while the Mac is away")
check("Lost the Mac" in (relay.DIR / "events.jsonl").read_text(), "relay: the outage is on the Spark's record")
print("Agent API + relay DoD passed.")
