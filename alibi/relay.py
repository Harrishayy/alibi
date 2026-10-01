"""Spark relay: the one door between the NemoClaw sandbox and the Mac's Alibi daemon, over Tailscale.

Runs on the DGX Spark host (not in the sandbox), so the Mac's token never enters the sandbox. It mirrors the Mac's live
state and feed every RELAY_POLL_S into data/relay/ (the Spark keeps a running log even while the agent sleeps, and can
say "last seen 14:02" when the Mac is shut), and serves a small allow-listed API to the agent:

GET  /status                 mac_online, last_seen, last_error
GET  /state                  live /api/state, or the last mirrored copy with stale=true
GET  /feed?limit=20          live /api/feed, or mirrored
GET  /alerts?since=TS        Alibi's nudges / verdicts / reports seen by the mirror since TS (for the heartbeat)
GET  /report  /sessions      proxied
POST /say {text}  /end {artefact?}   proxied: the agent starts, checks and ends sessions by talking to Alibi
POST /v1/...                 bearer-only proxy to the Spark's local vLLM, so the Mac's witness can use it over Tailscale

Run:  MAC_URL=http://<mac tailscale ip>:8765 ALIBI_REMOTE_TOKEN=... python -m alibi.relay
"""
import hmac, ipaddress, json, os, threading, time
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from . import config

MAC_URL = os.getenv("MAC_URL", "").rstrip("/")
MAC_TOKEN = os.getenv("ALIBI_REMOTE_TOKEN", "")
RELAY_TOKEN = os.getenv("RELAY_TOKEN", "")                 # for tailnet callers (the Mac using /v1)
VLLM_URL = os.getenv("VLLM_URL", "http://127.0.0.1:8000").rstrip("/")
VLLM_KEY = os.getenv("VLLM_API_KEY", "")
POLL_S = float(os.getenv("RELAY_POLL_S", "20"))
# The sandbox egresses through the OpenShell gateway on a Docker bridge; those callers need no token.
TRUST_NETS = [ipaddress.ip_network(n.strip()) for n in
              os.getenv("RELAY_TRUST_NETS", "127.0.0.0/8,172.16.0.0/12").split(",") if n.strip()]
DIR = config.DATA_DIR / "relay"

app = FastAPI(title="Alibi relay")
mirror = {"online": False, "last_seen": None, "last_error": None, "state": None, "feed": None, "seen": set()}
_lock = threading.Lock()


def _trusted(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host == "testclient"
    return any(ip in n for n in TRUST_NETS)


def _token_ok(request: Request) -> bool:
    given = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    return bool(RELAY_TOKEN) and hmac.compare_digest(given.encode(), RELAY_TOKEN.encode())


@app.middleware("http")
async def _auth(request: Request, call_next):
    host = request.client.host if request.client else ""
    if request.url.path.startswith("/v1/"):
        ok = _token_ok(request)                    # model proxy: always a token, never open to the bridge
    else:
        ok = _trusted(host) or _token_ok(request)
    if not ok:
        return JSONResponse({"error": "not allowed"}, status_code=401)
    return await call_next(request)


def _mac(method: str, path: str, **kw):
    if not MAC_URL:
        raise RuntimeError("MAC_URL is not set on the Spark")
    r = requests.request(method, MAC_URL + path, headers={"Authorization": f"Bearer {MAC_TOKEN}"}, timeout=8, **kw)
    r.raise_for_status()
    return r.json()


def _log(name: str, row: dict):
    DIR.mkdir(parents=True, exist_ok=True)
    with open(DIR / name, "a") as f:
        f.write(json.dumps(row, default=str) + "\n")


def poll_once():
    """One mirror pass. Feed items and alerts are appended once each, so data/relay/*.jsonl is the Spark's own record."""
    try:
        st = _mac("GET", "/api/state")
        fd = _mac("GET", "/api/feed", params={"limit": 50})
    except Exception as e:
        with _lock:
            was = mirror["online"]
            mirror.update(online=False, last_error=f"{type(e).__name__}: {e}"[:200])
        if was:
            _log("feed.jsonl", {"ts": time.time(), "source": "relay", "text": "Lost the Mac (asleep or off Tailscale)"})
        return False
    now = time.time()
    with _lock:
        was = mirror["online"]
        mirror.update(online=True, last_seen=now, last_error=None, state=st, feed=fd)
        fresh = []
        for it in reversed(fd.get("items", [])):
            key = (it.get("ts"), it.get("source"), it.get("text"))
            if key not in mirror["seen"]:
                mirror["seen"].add(key)
                fresh.append(it)
    if not was:
        _log("feed.jsonl", {"ts": now, "source": "relay", "text": "Connected to the Mac"})
    for it in fresh:
        it.pop("ago_s", None)
        _log("feed.jsonl", {**it, "session_id": fd.get("session_id")})
        if it.get("source") == "alibi":
            _log("alerts.jsonl", it)
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "state.json").write_text(json.dumps({"fetched_at": now, "state": st}, default=str))
    return True


def _loop():
    while True:
        poll_once()
        time.sleep(POLL_S)


def _seed_seen():
    """Don't re-log items already on disk after a relay restart."""
    try:
        for line in (DIR / "feed.jsonl").read_text().splitlines():
            it = json.loads(line)
            mirror["seen"].add((it.get("ts"), it.get("source"), it.get("text")))
    except FileNotFoundError:
        pass


def _offline(what: str):
    return JSONResponse({"error": f"The Mac isn't reachable, so I can't {what} right now.",
                         "mac_online": False, "last_seen": mirror["last_seen"], "last_error": mirror["last_error"]},
                        status_code=503)


@app.get("/status")
def status():
    return {"mac_online": mirror["online"], "last_seen": mirror["last_seen"],
            "last_seen_ago_s": round(time.time() - mirror["last_seen"]) if mirror["last_seen"] else None,
            "last_error": mirror["last_error"], "mac_url": MAC_URL, "poll_s": POLL_S}


@app.get("/state")
def state():
    try:
        return {"stale": False, **_mac("GET", "/api/state")}
    except Exception:
        if mirror["state"] is None:
            return _offline("see the current session")
        return {"stale": True, "last_seen": mirror["last_seen"], **mirror["state"]}


@app.get("/feed")
def feed(limit: int = 20):
    try:
        return _mac("GET", "/api/feed", params={"limit": max(1, min(int(limit), 200))})
    except Exception:
        try:
            rows = [json.loads(x) for x in (DIR / "feed.jsonl").read_text().splitlines()[-limit:]]
        except FileNotFoundError:
            rows = []
        return {"stale": True, "items": rows[::-1]}


@app.get("/alerts")
def alerts(since: float = 0, limit: int = 20):
    try:
        rows = [json.loads(x) for x in (DIR / "alerts.jsonl").read_text().splitlines()]
    except FileNotFoundError:
        rows = []
    return {"items": [r for r in rows if (r.get("ts") or 0) > since][-limit:], "now": time.time()}


@app.get("/report")
def report():
    try:
        return _mac("GET", "/api/report")
    except Exception:
        return _offline("build the report")


@app.get("/sessions")
def sessions(limit: int = 20):
    try:
        return _mac("GET", "/api/sessions", params={"limit": max(1, min(int(limit), 100))})
    except Exception:
        return _offline("list sessions")


@app.post("/say")
async def say(request: Request):
    body = await request.json()
    try:
        return _mac("POST", "/api/say", json={"text": str(body.get("text", ""))[:500]})
    except Exception:
        return _offline("pass that on")


@app.post("/end")
async def end(request: Request):
    body = await request.json() if await request.body() else {}
    try:
        return _mac("POST", "/api/end", json={"artefact": body.get("artefact")})
    except Exception:
        return _offline("end the session")


@app.api_route("/v1/{path:path}", methods=["GET", "POST"])
async def v1(path: str, request: Request):
    r = requests.request(request.method, f"{VLLM_URL}/v1/{path}", data=await request.body(), timeout=120,
                         headers={"Content-Type": "application/json",
                                  **({"Authorization": f"Bearer {VLLM_KEY}"} if VLLM_KEY else {})})
    return JSONResponse(r.json(), status_code=r.status_code)


def main():
    import uvicorn
    _seed_seen()
    threading.Thread(target=_loop, daemon=True).start()
    uvicorn.run(app, host=os.getenv("RELAY_HOST", "0.0.0.0"), port=int(os.getenv("RELAY_PORT", "8770")),
                log_level="warning")


if __name__ == "__main__":
    main()
