"""Local HTTP API on 127.0.0.1:8765 — what the notch island and the web dashboard talk to. Started by the daemon.

GET  /api/state            live session, recent labels, latest alert, witness info
POST /api/say {text}       free text, routed like a chat message (start / status / end / report)
POST /api/end {artefact?}  end the active session now
GET  /api/sessions         finished sessions, newest first
GET  /api/report           weekly alignment table + summary
GET  /files/...            frames and contact sheets (from the data dir)
POST /ingest               P6: phone / Health events (X-Alibi-Secret header)
"""
import time
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import cli, config, db
from .notify import recent_alerts

app = FastAPI(title="Alibi")
WEB = config.ROOT / "alibi" / "web"
STARTED = time.time()
config.DATA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(config.DATA_DIR)), name="files")


def file_url(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return "/files/" + str(__import__("pathlib").Path(path).resolve().relative_to(config.DATA_DIR.resolve()))
    except ValueError:
        return None


def _con():
    return db.connect()


def _session_json(con, s, live: bool) -> dict:
    cam = db.session_events(con, s["id"], "camera")
    labels = [{"ts": e["ts"], "label": e["payload"]["label"], "note": e["payload"].get("note", ""),
               "frame_url": file_url(e["payload"].get("frame")), "reused": e["payload"].get("reused", False)}
              for e in cam]
    now = time.time()
    out = {k: s[k] for k in s.keys()}
    out.update(evidence_url=file_url(s["evidence_path"]), labels=labels,
               on_task_so_far=(sum(l["label"] == "on_task" for l in labels) / len(labels)) if labels else None)
    if live:
        span = max(1.0, s["ends_at"] - s["started_at"])
        out.update(left_s=max(0.0, s["ends_at"] - now), progress=min(1.0, (now - s["started_at"]) / span),
                   last_frame_url=labels[-1]["frame_url"] if labels else None)
    if s["modality"] in ("digital", "hybrid"):
        out["windows"] = _windows(con, s)
    return out


def _windows(con, s) -> list[dict]:
    try:
        from . import verifier
        return verifier.window_breakdown(con, s)
    except (ImportError, AttributeError):
        return []


@app.get("/api/state")
def state():
    con = _con()
    s = db.active_session(con)
    alerts = recent_alerts(1)
    a = alerts[-1] if alerts else None
    if a:
        a = {**a, "image_url": file_url(a.get("image"))}
    habits = config.habits()["habits"]
    return {
        "now": time.time(),
        "session": _session_json(con, s, live=True) if s else None,
        "alert": a,
        "habits": [{"key": k, "modality": h.get("modality", "strava" if h.get("source") else "?")}
                   for k, h in habits.items()],
        "witness": config.VISION_BACKEND,
        "text_model": config.LLM_MODEL if config.TEXT_READY else "rules",
        "daemon": {"up_since": STARTED},
    }


class Say(BaseModel):
    text: str


class End(BaseModel):
    artefact: str | None = None


@app.post("/api/say")
def say(body: Say):
    return {"reply": cli.say(_con(), body.text)}


@app.post("/api/end")
def end(body: End | None = None):
    return {"reply": cli.end(_con(), body.artefact if body else None)}


@app.get("/api/sessions")
def sessions(limit: int = 50):
    con = _con()
    rows = con.execute("SELECT * FROM sessions WHERE status='done' ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_session_json(con, r, live=False) for r in rows]


@app.get("/api/report")
def report():
    from . import report as r
    return r.build_json()


class Ingest(BaseModel):
    source: str
    kind: str
    payload: dict = {}
    ts: float | None = None


@app.post("/ingest")
def ingest(body: Ingest, x_alibi_secret: str = Header(default="")):
    if not config.INGEST_SECRET or x_alibi_secret != config.INGEST_SECRET:
        raise HTTPException(401, "bad secret")
    if body.source not in ("phone", "health"):
        raise HTTPException(400, "source must be phone or health")
    con = _con()
    s = db.active_session(con)
    db.add_event(con, body.source, body.kind, body.payload, session_id=s["id"] if s else None, ts=body.ts)
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


if WEB.exists():
    app.mount("/web", StaticFiles(directory=str(WEB)), name="web")


def serve_in_thread():
    import threading, uvicorn
    server = uvicorn.Server(uvicorn.Config(app, host=config.API_HOST, port=config.API_PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True, name="alibi-api").start()
    return server
