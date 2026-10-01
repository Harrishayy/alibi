"""Spark relay + Mac remote guard: the sandboxed agent reaches Alibi only through the relay; the Mac refuses tailnet
callers without the token; the relay mirrors state/feed/alerts and degrades to the mirror when the Mac sleeps."""
import os, socket, threading, time
from harness import check, Clock
os.environ["ALIBI_REMOTE_TOKEN"] = "mac-token"
os.environ["RELAY_TOKEN"] = "relay-token"
s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
os.environ["MAC_URL"] = f"http://127.0.0.1:{PORT}"

import uvicorn
from fastapi.testclient import TestClient
from alibi import api, relay

# --- the Mac's API: loopback is open, tailnet needs the token ------------------------------------------------------
local = TestClient(api.app)
remote = TestClient(api.app, client=("100.97.1.2", 5000))
check(local.get("/api/state").status_code == 200, "Mac API: loopback callers need no token")
check(remote.get("/api/state").status_code == 401, "Mac API: tailnet caller without token -> 401")
check(remote.get("/api/state", headers={"Authorization": "Bearer nope"}).status_code == 401, "Mac API: wrong token -> 401")
check(remote.get("/api/state", headers={"Authorization": "Bearer mac-token"}).status_code == 200,
      "Mac API: tailnet caller with ALIBI_REMOTE_TOKEN -> 200")
check(remote.post("/ingest", json={"source": "phone", "kind": "x"}).status_code == 401, "Mac API: /ingest keeps its own secret")

# --- relay against a live Mac daemon --------------------------------------------------------------------------------
srv = uvicorn.Server(uvicorn.Config(api.app, host="127.0.0.1", port=PORT, log_level="error"))
threading.Thread(target=srv.run, daemon=True).start()
for _ in range(100):
    if srv.started: break
    time.sleep(0.05)

sandbox = TestClient(relay.app, client=("172.18.0.2", 4000))       # OpenShell gateway on the Docker bridge
tailnet = TestClient(relay.app, client=("100.66.0.9", 4000))
check(relay.poll_once(), "relay: first mirror pass reaches the Mac")
check(sandbox.get("/status").json()["mac_online"], "relay: /status says the Mac is online")
check(tailnet.get("/status").status_code == 401, "relay: tailnet caller without RELAY_TOKEN -> 401")
check(sandbox.post("/v1/chat/completions", json={}).status_code == 401, "relay: model proxy is never open to the bridge")

r = sandbox.post("/say", json={"text": "draw for 25 minutes"}).json()
check("draw" in str(r.get("reply", "")).lower(), f"relay: /say starts a session on the Mac ({r.get('reply')!r})")
st = sandbox.get("/state").json()
check(st["stale"] is False and st["session"] and st["session"]["habit"] == "drawing", "relay: /state shows the live session")
clock = Clock()
clock.advance(26 * 60)                                         # past the timer: a real verdict, not a cancel
sandbox.post("/end", json={})
relay.poll_once()
check((relay.DIR / "feed.jsonl").exists() and (relay.DIR / "state.json").exists(), "relay: mirror written to data/relay/")
n = len((relay.DIR / "feed.jsonl").read_text().splitlines())
relay.poll_once()
check(len((relay.DIR / "feed.jsonl").read_text().splitlines()) == n, "relay: feed items are logged once, not every poll")
check(any(a["source"] == "alibi" for a in sandbox.get("/alerts").json()["items"]), "relay: Alibi's alerts reach /alerts")

# --- Mac goes to sleep ----------------------------------------------------------------------------------------------
srv.should_exit = True
time.sleep(0.5)
check(not relay.poll_once(), "relay: poll notices the Mac is gone")
st = sandbox.get("/state").json()
check(st.get("stale") is True and st.get("last_seen"), "relay: /state falls back to the mirror, marked stale")
r = sandbox.post("/say", json={"text": "status"})
check(r.status_code == 503 and "isn't reachable" in r.json()["error"], "relay: writes fail plainly while the Mac is away")
check("Lost the Mac" in (relay.DIR / "feed.jsonl").read_text(), "relay: the outage is on the Spark's record")
print("Relay DoD passed.")
