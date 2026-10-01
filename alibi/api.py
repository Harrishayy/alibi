"""Local HTTP API on 127.0.0.1:8765 — what the notch island and the web dashboard talk to. Started by the daemon.

GET  /api/state            live session, recent labels, latest alert, witness info, today's tally, last verdict
GET  /api/feed?limit=20    agent activity: witness samples, screen titles, your actions, Alibi's alerts (newest first)
POST /api/say {text}       free text, routed like a chat message (start / status / end / report)
POST /api/end {artefact?}  end the active session now
GET  /api/sessions         finished sessions, newest first
GET  /api/report           weekly alignment table + summary
GET  /files/...            frames and contact sheets (from the data dir)
POST /ingest               P6: phone / Health events (X-Alibi-Secret header)
GET  /api/health           P9: setup checklist (camera, window titles, witness, model, Strava, island)
GET  /api/habits           P9: habits.yaml as JSON;  PUT /api/habits {habits: {...}} writes it back
GET  /api/reel?session=ID | ?date=YYYY-MM-DD    P10: build (or reuse) an H.264 timelapse -> {url}
POST /api/sessions/{id}/correct {ts, label}     P11: relabel a sample; re-scores the session
"""
import datetime as dt, hmac, pathlib, time
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from . import cli, config, db
from .notify import recent_alerts

app = FastAPI(title="Alibi")
WEB = config.ROOT / "alibi" / "web"
STARTED = time.time()
config.DATA_DIR.mkdir(parents=True, exist_ok=True)
# R10: only evidence media is public — never alibi.db or alerts.jsonl. Host check stops DNS rebinding.
for _sub in ("frames", "evidence", "reels"):
    (config.DATA_DIR / _sub).mkdir(parents=True, exist_ok=True)
    app.mount(f"/files/{_sub}", StaticFiles(directory=str(config.DATA_DIR / _sub)), name=f"files-{_sub}")
_hosts = config.ALLOWED_HOSTS or (["127.0.0.1", "localhost", "testserver", "::1"]
                                  if config.API_HOST in ("127.0.0.1", "localhost") else ["*"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)


_LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


@app.middleware("http")
async def _remote_auth(request: Request, call_next):
    """The Spark relay reaches this over Tailscale. Anyone not on this Mac needs ALIBI_REMOTE_TOKEN; no token set means
    remote callers are refused outright. /ingest keeps its own X-Alibi-Secret check."""
    host = request.client.host if request.client else ""
    if host not in _LOOPBACK and request.url.path != "/ingest":
        given = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not config.REMOTE_TOKEN or not hmac.compare_digest(given.encode(), config.REMOTE_TOKEN.encode()):
            return JSONResponse({"error": "remote callers need a valid ALIBI_REMOTE_TOKEN"}, status_code=401)
    return await call_next(request)


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    """R6: never a bare 'Internal Server Error' in the island or dashboard."""
    return JSONResponse({"detail": f"Alibi tripped: {type(exc).__name__}: {str(exc)[:160]}"}, status_code=500)


def file_url(path: str | None, bust: bool = False) -> str | None:
    if not path:
        return None
    try:
        p = pathlib.Path(path).resolve()
        url = "/files/" + str(p.relative_to(config.DATA_DIR.resolve()))
    except ValueError:
        return None
    if bust and p.exists():
        url += f"?v={int(p.stat().st_mtime)}"           # R5: a rebuilt reel is never served from browser cache
    return url


def _seen(request: Request | None, client: str | None):
    from . import health
    who = client or (request.headers.get("x-alibi-client") if request else None)
    if who:
        health.CLIENT_SEEN[who[:20]] = time.time()


def _con():
    return db.connect()


def _session_json(con, s, live: bool) -> dict:
    from . import nudges, verifier
    cam = verifier.camera_labels(con, s)
    labels = [{"ts": e["ts"], "label": e["payload"]["label"], "note": e["payload"].get("note", ""),
               "label_text": config.LABEL_TEXT.get(e["payload"]["label"], e["payload"]["label"]),
               "frame_url": file_url(e["payload"].get("frame")), "reused": e["payload"].get("reused", False),
               "corrected_from": e["payload"].get("corrected_from"), "learned_from": e["payload"].get("learned_from")}
              for e in cam]
    now = time.time()
    out = {k: s[k] for k in s.keys()}
    reel = config.DATA_DIR / "reels" / f"session-{s['id']}.mp4"
    windows = _windows(con, s) if s["modality"] in ("digital", "hybrid") else None
    cam_ratio = (sum(l["label"] == "on_task" for l in labels) / len(labels)) if labels else None
    scr_ratio = sum(w["share"] for w in windows if w["label"] == "on_task") if windows else None
    so_far = cam_ratio if s["modality"] == "physical" else (
        scr_ratio if s["modality"] == "digital" else
        (max(x for x in (cam_ratio, scr_ratio) if x is not None) if (cam_ratio, scr_ratio) != (None, None) else None))
    out.update(label=config.display_name(s["habit"]), evidence_url=file_url(s["evidence_path"]), labels=labels,
               reel_url=file_url(str(reel), bust=True) if reel.exists() else None,
               on_task_so_far=so_far, day=dt.date.fromtimestamp(s["started_at"]).isoformat())
    if windows is not None:
        out["windows"] = windows
    if live:
        span = max(1.0, s["ends_at"] - s["started_at"])
        smp = nudges.recent_samples(con, s)
        last = smp[-1] if smp else None
        tail = []
        for x in reversed(smp):
            if x["label"] == "on_task":
                break
            tail.append(x)
        brk = db.in_break(con, s["id"], now)
        out.update(left_s=max(0.0, s["ends_at"] - now), progress=min(1.0, (now - s["started_at"]) / span),
                   last_frame_url=labels[-1]["frame_url"] if labels else None,
                   samples=len(smp), warming_up=len(smp) < 6,
                   recent=[x["label"] for x in smp[-3:]],
                   recent_on_task=(sum(x["label"] == "on_task" for x in smp[-3:]) / len(smp[-3:])) if smp else None,
                   last_seen=_last_seen(last, now),
                   drifting=({"label": tail[0]["label"], "label_text": _ltext(tail[0]),
                              "since_s": round(now - tail[-1]["ts"]), "samples": len(tail)} if len(tail) >= 2 else None),
                   on_break=({"until": brk[1], "left_s": round(brk[1] - now)} if brk else None),
                   breaks_taken=len(db.user_events(con, s["id"], "break")),
                   nudges=len(nudges.nudges_for(con, s["id"])),
                   strikes=sum(1 for e in db.session_events(con, s["id"], "alibi") if e["kind"] == "strike"))
    else:
        out.update(verifier.stats(con, s, cam=cam, windows=None if windows is None else
                                  verifier.window_breakdown(con, s, top=99)))
        out["summary"] = verifier.voice(con, s) if s["verdict"] else None
    return out


def _ltext(x: dict) -> str:
    if x.get("source") == "screen":
        from . import verifier
        return verifier.short_title(x.get("title") or "screen")
    return config.LABEL_TEXT.get(x["label"], x["label"])


def _last_seen(x: dict | None, now: float) -> dict | None:
    """island: 'Witness · 12 s ago · hands on the work'."""
    if not x:
        return None
    src = "Witness" if x["source"] == "camera" else "Screen"
    note = x.get("note") or _ltext(x)
    return {"label": x["label"], "label_text": _ltext(x), "note": note, "source": x["source"],
            "ago_s": round(now - x["ts"]), "text": f"{src} · {round(now - x['ts'])} s ago · {note}"}


def _windows(con, s) -> list[dict]:
    try:
        from . import verifier
        return verifier.window_breakdown(con, s)
    except (ImportError, AttributeError):
        return []


@app.get("/api/state")
def state(request: Request, client: str | None = None):
    _seen(request, client)
    con = _con()
    s = db.active_session(con)
    alerts = recent_alerts(1)
    a = _alert_json(alerts[-1]) if alerts else None
    cfg = config.habits()
    habits = cfg["habits"]
    sj = _session_json(con, s, live=True) if s else None
    return {
        "now": time.time(),
        "session": sj,
        "alert": a,
        "habits": [{"key": k, "label": config.display_name(k, cfg),
                    "modality": h.get("modality", "strava" if h.get("source") else "?"),
                    "default_min": h.get("default_min", 25)} for k, h in habits.items()],
        "witness": config.VISION_BACKEND,
        "witness_label": {"nvidia": "NVIDIA VLM", "apple": "Apple Vision", "mock": "Demo witness"}.get(
            config.VISION_BACKEND, config.VISION_BACKEND),
        "text_model": config.LLM_MODEL if config.TEXT_READY else "rules",
        "daemon": {"up_since": STARTED},
        "today": _today(con, habits),
        "recent_verdict": None if s else _recent_verdict(con),
        "status_text": _status_text(sj),
    }


def _alert_json(a: dict) -> dict:
    out = {**a, "image_url": file_url(a.get("image"))}
    if a.get("reel"):
        out["reel_url"] = file_url(a["reel"], bust=True)
    if a.get("habit"):
        out["habit_label"] = config.display_name(a["habit"])
    return out


def _status_text(sj: dict | None) -> str:
    """D11: one plain-language state for the header pill."""
    if not sj:
        return "Idle — nothing declared"
    left = int(sj["left_s"])
    if sj.get("on_break"):
        return f"On a break · {sj['label']} resumes in {sj['on_break']['left_s'] // 60 + 1} min"
    if sj.get("drifting"):
        return f"Drifting · {sj['drifting']['label_text']} · {sj['label']} {left // 60:02d}:{left % 60:02d}"
    return f"Watching · {sj['label']} {left // 60:02d}:{left % 60:02d}"


def _today(con, habits: dict) -> dict:
    """island idle wing + dashboard header: '2/5' habits touched today, minutes seen."""
    d0 = dt.datetime.combine(dt.date.today(), dt.time()).timestamp()
    ss = con.execute("SELECT * FROM sessions WHERE status='done' AND started_at>=?", (d0,)).fetchall()
    tracked = [k for k, h in habits.items() if h.get("modality")]
    good = {x["habit"] for x in ss if x["verdict"] in ("done", "partial")}
    return {"sessions": len(ss), "verified_min": round(sum((x["on_task_ratio"] or 0) * x["declared_min"] for x in ss)),
            "declared_min": sum(x["declared_min"] for x in ss), "habits_done": len(good & set(tracked)),
            "habits_total": len(tracked), "tally": f"{len(good & set(tracked))}/{len(tracked)}",
            "verdicts": {v: sum(x["verdict"] == v for x in ss) for v in ("done", "partial", "slacked")}}


def _recent_verdict(con, within_s: float = 600) -> dict | None:
    """D3: the last finished session for ~10 min after it ends, so the Now panel can hold the verdict."""
    r = con.execute("SELECT * FROM sessions WHERE status='done' AND ended_at IS NOT NULL ORDER BY ended_at DESC LIMIT 1"
                    ).fetchone()
    if not r or time.time() - r["ended_at"] > within_s:
        return None
    j = _session_json(con, r, live=False)
    j["ended_ago_s"] = round(time.time() - r["ended_at"])
    return j


@app.get("/api/feed")
def feed(limit: int = 20, session: int | None = None):
    """F4: what the agent is doing right now. [{ts, source, who, label, text, thumb}] newest first.

    source: witness | screen | you | alibi. Scope: the given session, else the live one, else the last one if it ended
    in the past 10 minutes; Alibi's own alerts are always included."""
    from . import evidence, verifier
    con = _con()
    limit = max(1, min(int(limit), 200))
    s = db.get_session(con, session) if session else db.active_session(con)
    if s is None:
        r = con.execute("SELECT * FROM sessions WHERE status='done' ORDER BY ended_at DESC LIMIT 1").fetchone()
        s = r if r and r["ended_at"] and time.time() - r["ended_at"] < 600 else None
    items = []
    if s:
        for e in verifier.camera_labels(con, s)[-limit:]:
            p = e["payload"]
            items.append({"ts": e["ts"], "source": "witness", "who": "Witness", "label": p["label"],
                          "text": f"{config.LABEL_TEXT.get(p['label'], p['label'])} — {p.get('note', '')}".rstrip(" —")
                          + (" (you corrected this)" if p.get("corrected_from") else ""),
                          "thumb": file_url(p.get("frame"))})
        if s["modality"] in ("digital", "hybrid"):
            win = verifier._window_events(con, s)[-limit:]
            labels = verifier.classify_titles(con, s["habit"], {evidence._title_key(e["payload"]) for e in win})
            for e in win:
                k = evidence._title_key(e["payload"])
                lab = labels.get(k, "off_task")
                items.append({"ts": e["ts"], "source": "screen", "who": "Screen", "label": lab,
                              "text": f"{k[:60]} — {'on task' if lab == 'on_task' else 'off task'}", "thumb": None})
        for e in db.user_events(con, s["id"]):
            p, k = e["payload"], e["kind"]
            text = {"correction": lambda: f"Overruled a sample → {config.LABEL_TEXT.get(p.get('label'), p.get('label'))}",
                    "break": lambda: f"Took a {p.get('min', 5)} min break",
                    "resume": lambda: "Back from the break", "back": lambda: "Said they're back on it",
                    "extend": lambda: f"Added {p.get('min')} min", "snooze": lambda: "Snoozed nudges",
                    "change": lambda: f"Changed the session to {p.get('to')} min"}.get(k, lambda: k)()
            items.append({"ts": e["ts"], "source": "you", "who": "You", "label": k, "text": text, "thumb": None})
    for a in recent_alerts(10):
        if a.get("kind") == "info":
            continue
        items.append({"ts": a["ts"], "source": "alibi", "who": "Alibi", "label": a.get("kind"), "text": a["text"],
                      "thumb": file_url(a.get("image"))})
    items.sort(key=lambda x: -x["ts"])
    now = time.time()
    for x in items[:limit]:
        x["ago_s"] = round(now - x["ts"])
    return {"session_id": s["id"] if s else None, "items": items[:limit]}


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
    limit = max(1, min(int(limit), 500))
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


@app.get("/api/health")
def health():
    from . import health as h
    return h.checks()


@app.get("/api/habits")
def get_habits():
    return config.habits()


class HabitsBody(BaseModel):
    habits: dict


@app.put("/api/habits")
def put_habits(body: HabitsBody):
    from . import health as h
    try:
        return h.save_habits(body.habits)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/reel")
def reel(session: int | None = None, date: str | None = None):
    from . import reel as r
    con = _con()
    if session is None and not date:
        raise HTTPException(400, "pass ?session=ID or ?date=YYYY-MM-DD")
    try:
        if session is not None:
            existing = r.REELS_DIR / f"session-{session}.mp4"
            path = str(existing) if existing.exists() and not r.building(existing.stem) else r.session_reel(con, session)
        else:
            path = r.day_reel(con, date)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not path:
        raise HTTPException(404, "no frames to make a reel from")
    return {"url": file_url(path, bust=True)}


class Correction(BaseModel):
    ts: float | None = None
    label: str
    title: str | None = None      # digital sessions: re-label a window title (persists in title_cache)


@app.post("/api/sessions/{sid}/correct")
def correct(sid: int, body: Correction):
    from . import verifier
    if body.ts is None and not body.title:
        raise HTTPException(400, "pass ts (a sample) or title (a window)")
    con = _con()
    try:
        reply = verifier.correct(con, sid, body.ts, body.label, title=body.title)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    s = db.get_session(con, sid)
    if s["status"] == "done" and s["modality"] != "digital":
        from .daemon import _reel_later
        _reel_later(sid)
    return {"reply": reply, "session": _session_json(con, s, live=s["status"] == "active")}


from . import hooks as _hooks
for _r in _hooks.routers():
    app.include_router(_r)


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
