"""Spark relay: the one door between the NemoClaw sandbox and the Mac's agent API (docs/NEMOCLAW.md §5), over Tailscale.

Runs on the DGX Spark host (not in the sandbox), so the Mac's agent token never enters the sandbox. It mirrors the
Mac's /api/agent/context and digests every RELAY_POLL_S into data/relay/ (the Spark keeps its own record, and the agent
can say "last seen 14:02" while the laptop sleeps), and serves the sandbox an allow-listed API:

GET  /status               mac_online, last_seen, last_error
GET  /context              live /api/agent/context, or the last mirrored copy with stale=true
GET  /digests?limit=5      live /api/agent/digests, or mirrored
POST /brief {...}          passed to /api/agent/brief: the agent's only write. It can't touch sessions or habits.

Only the sandbox (OpenShell gateway on the Docker bridge) and the host may call it; anyone else gets 401.
Run:  MAC_URL=http://<mac>:8766 ALIBI_AGENT_TOKEN=... python -m alibi.relay
"""
import datetime as dt, ipaddress, json, os, threading, time
from zoneinfo import ZoneInfo
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from . import config

MAC_URL = os.getenv("MAC_URL", "").rstrip("/")
MAC_TOKEN = os.getenv("ALIBI_AGENT_TOKEN", "")
POLL_S = float(os.getenv("RELAY_POLL_S", "20"))
# The sandbox egresses through the OpenShell gateway on a Docker bridge; nothing else is let in.
TRUST_NETS = [ipaddress.ip_network(n.strip()) for n in
              os.getenv("RELAY_TRUST_NETS", "127.0.0.0/8,172.16.0.0/12").split(",") if n.strip()]
DIR = config.DATA_DIR / "relay"

app = FastAPI(title="Alibi relay", docs_url=None, redoc_url=None, openapi_url=None)
mirror = {"online": False, "last_seen": None, "last_error": None, "context": None, "digests": None, "seen": set()}
_lock = threading.Lock()


def _trusted(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host == "testclient"
    return any(ip in n for n in TRUST_NETS)


@app.middleware("http")
async def _auth(request: Request, call_next):
    if not _trusted(request.client.host if request.client else ""):
        return JSONResponse({"error": "not allowed"}, status_code=401)
    return await call_next(request)


def _mac(method: str, path: str, **kw):
    if not MAC_URL:
        raise RuntimeError("MAC_URL is not set on the Spark")
    headers = {**kw.pop("headers", {}), "X-Alibi-Agent-Token": MAC_TOKEN}
    r = requests.request(method, MAC_URL + path, headers=headers, timeout=8, **kw)
    if r.status_code >= 500 or r.status_code in (401, 403):
        r.raise_for_status()
    return r


def _log(name: str, row: dict):
    DIR.mkdir(parents=True, exist_ok=True)
    with open(DIR / name, "a") as f:
        f.write(json.dumps(row, default=str) + "\n")


def poll_once():
    """One mirror pass. New digests are appended once each, so data/relay/digests.jsonl is the Spark's own record."""
    try:
        ctx = _mac("GET", "/api/agent/context").json()
        dg = _mac("GET", "/api/agent/digests", params={"limit": 10}).json()
    except Exception as e:
        with _lock:
            was = mirror["online"]
            mirror.update(online=False, last_error=f"{type(e).__name__}: {e}"[:200])
        if was:
            _log("events.jsonl", {"ts": time.time(), "text": "Lost the Mac (asleep or off Tailscale)"})
        return False
    now = time.time()
    with _lock:
        was = mirror["online"]
        mirror.update(online=True, last_seen=now, last_error=None, context=ctx, digests=dg)
        fresh = []
        for it in reversed(dg.get("items", [])):
            key = (it.get("slot"), it.get("ts"))
            if key not in mirror["seen"]:
                mirror["seen"].add(key)
                fresh.append(it)
    if not was:
        _log("events.jsonl", {"ts": now, "text": "Connected to the Mac"})
    for it in fresh:
        _log("digests.jsonl", it)
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "context.json").write_text(json.dumps({"fetched_at": now, "context": ctx}, default=str))
    return True


def _loop():
    while True:
        poll_once()
        time.sleep(POLL_S)


def _seed_seen():
    """Don't re-log digests already on disk after a relay restart."""
    try:
        for line in (DIR / "digests.jsonl").read_text().splitlines():
            it = json.loads(line)
            mirror["seen"].add((it.get("slot"), it.get("ts")))
    except FileNotFoundError:
        pass


def slot_hint(now: float | None = None) -> dict:
    """Today's slot ids in Alibi's timezone, so the agent never has to work out London time inside a UTC sandbox."""
    t = dt.datetime.fromtimestamp(now or time.time(), ZoneInfo(os.getenv("ALIBI_TZ", "Europe/London")))
    d = t.date().isoformat()
    check = max([h for h in (12, 16, 20) if h <= t.hour], default=12)
    return {"local_time": t.strftime("%Y-%m-%d %H:%M"), "morning": f"{d}-morning",
            "checkpoint": f"{d}-checkpoint-{check:02d}", "night": f"{d}-night", "risk": f"{d}-risk-{t.hour:02d}"}


def _offline(what: str):
    return JSONResponse({"error": f"The Mac isn't reachable, so I can't {what} right now.",
                         "mac_online": False, "last_seen": mirror["last_seen"], "last_error": mirror["last_error"]},
                        status_code=503)


@app.get("/status")
def status():
    return {"mac_online": mirror["online"], "last_seen": mirror["last_seen"],
            "last_seen_ago_s": round(time.time() - mirror["last_seen"]) if mirror["last_seen"] else None,
            "last_error": mirror["last_error"], "mac_url": MAC_URL, "poll_s": POLL_S}


@app.get("/context")
def context():
    try:
        return {"stale": False, "slot_hint": slot_hint(), **_mac("GET", "/api/agent/context").json()}
    except Exception:
        if mirror["context"] is None:
            return _offline("read Alibi's context")
        return {"stale": True, "last_seen": mirror["last_seen"], "slot_hint": slot_hint(), **mirror["context"]}


@app.get("/digests")
def digests(limit: int = 5):
    try:
        return _mac("GET", "/api/agent/digests", params={"limit": max(1, min(int(limit), 20))}).json()
    except Exception:
        try:
            rows = [json.loads(x) for x in (DIR / "digests.jsonl").read_text().splitlines()[-limit:]]
        except FileNotFoundError:
            rows = []
        return {"stale": True, "items": rows[::-1]}


@app.post("/brief")
async def brief(request: Request):
    raw = await request.body()
    try:
        r = _mac("POST", "/api/agent/brief", data=raw, headers={"Content-Type": "application/json"})
    except Exception:
        return _offline("post the brief")
    return JSONResponse(r.json(), status_code=r.status_code)


def main():
    import uvicorn
    _seed_seen()
    threading.Thread(target=_loop, daemon=True).start()
    uvicorn.run(app, host=os.getenv("RELAY_HOST", "0.0.0.0"), port=int(os.getenv("RELAY_PORT", "8770")),
                log_level="warning")


if __name__ == "__main__":
    main()
