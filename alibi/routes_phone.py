"""Phone writes: start a session by saying it, and end one, from the iPhone over the tailnet.

Mounted inside integrations.phone_app() (the :8766 listener), never on the loopback dashboard app.

POST /api/phone/say          {op_id, client_ts, text}                    -> {ok, reply, session}
POST /api/phone/session/end  {op_id, client_ts, session_id, artefact?}   -> {ok, reply, session}
GET  /api/phone/plan?days=3   the Plan page view (routes_calendar.days_view); GET /plan serves the page itself
POST /api/phone/plan/edit    {op_id, client_ts, op, ...}                -> routes_calendar.edit, and the notch says it

Security: the X-Alibi-Secret header (?key= is refused for writes), loopback or tailnet (100.64/10, fd7a:115c:a1e0::/48)
source only, because the LAN endpoint is cleartext and the header can be sniffed there; tailscale serve arrives as
loopback. Body <= 16 KB, 30 writes a minute. op_id dedupe: one lock spans check -> execute -> record, so a retry (or
two racing copies) gets the first answer and never a second session. The last 500 ops live in integrations.state().
"""
import collections, ipaddress, json, math, re, threading, time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from . import cli, db, integrations, intent

router = APIRouter()

BODY_MAX = 16 * 1024
WRITES_PER_MIN = 30
STALE_START_S = 120              # a start older than this would begin a session the user is no longer doing
LATE_END_S = 30                  # an end this late is back-dated to when it was tapped
OPS_KEEP = 500
TAILNET = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))

_op_lock = threading.Lock()
_writes: collections.deque = collections.deque()


def _client_ok(host: str | None) -> bool:
    try:
        ip = ipaddress.ip_address(host or "")
    except ValueError:
        return False
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return ip.is_loopback or any(ip in n for n in TAILNET if n.version == ip.version)


def _err(code: int, error: str, reply: str, session=None) -> JSONResponse:
    return JSONResponse({"ok": False, "error": error, "reply": reply, "session": session}, status_code=code)


async def _guard(request: Request) -> dict | JSONResponse:
    """Source, secret, size, rate, JSON shape. Returns the body or the refusal."""
    if not _client_ok(request.client.host if request.client else None):
        return _err(403, "lan_refused", "Phone writes only work over Tailscale. Turn Tailscale on and try again.")
    if request.query_params.get("key"):
        return _err(401, "key_in_url", "Send the key in the X-Alibi-Secret header, not the URL.")
    if not integrations._secret_ok(request.headers.get("x-alibi-secret", "")):
        return _err(401, "bad_secret", "Wrong or missing key.")
    try:
        if int(request.headers.get("content-length") or 0) > BODY_MAX:
            return _err(413, "too_big", "That request is too big.")
    except ValueError:
        return _err(400, "bad_length", "Bad Content-Length.")
    raw = await request.body()
    if len(raw) > BODY_MAX:
        return _err(413, "too_big", "That request is too big.")
    now = time.time()
    while _writes and now - _writes[0] > 60:
        _writes.popleft()
    if len(_writes) >= WRITES_PER_MIN:
        return _err(429, "rate_limited", "Too many writes. Wait a minute.")
    _writes.append(now)
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        return _err(400, "bad_json", "Send JSON.")
    if not isinstance(body, dict):
        return _err(400, "bad_json", "Send a JSON object.")
    op = body.get("op_id")
    if not isinstance(op, str) or not re.fullmatch(r"[\w.:-]{1,128}", op):
        return _err(400, "bad_op_id", "op_id must be 1-128 letters, digits, - _ . or :.")
    ts = body.get("client_ts")
    if isinstance(ts, bool) or not isinstance(ts, (int, float)) or not math.isfinite(ts):
        return _err(400, "bad_client_ts", "client_ts must be unix seconds.")
    return body


def _once(kind: str, op_id: str, run) -> JSONResponse:
    """op_id dedupe. The lock spans check -> execute -> record: two copies of one op can never both run."""
    key = f"{kind}:{op_id}"
    with _op_lock:
        for o in integrations.state().get("phone_ops") or []:
            if o.get("k") == key:
                return JSONResponse(o["body"], status_code=o["code"], headers={"X-Alibi-Replay": "1"})
        code, body = run()
        ops = (integrations.state().get("phone_ops") or []) + [{"k": key, "ts": time.time(), "code": code, "body": body}]
        integrations.set_state(phone_ops=ops[-OPS_KEEP:])
    return JSONResponse(body, status_code=code)


def _session(con) -> dict:
    return integrations._session_core(con)


def is_start(con, text: str) -> bool:
    """Would cli.say() start a session with this? (No model call: habit word or a duration, nothing live.)"""
    t = re.sub(r"\s+", " ", str(text).strip().lower())
    if not t or db.active_session(con):
        return False
    if re.match(r"^(status|how am i|how'?s it|time left|add habit|cancel|undo|never ?mind|nvm|end|stop|done|finish|"
                r"i'?m done|report)\b", t):
        return False
    if re.fullmatch(r"(yes|yeah|yep|ok|okay|sure|go|do it|start)[.!]?", t):
        return bool(cli._pace_offer())
    try:
        return intent.match_habit(t) is not None or intent._minutes(t) is not None
    except Exception:
        return False


@router.post("/api/phone/say")
async def phone_say(request: Request):
    body = await _guard(request)
    if isinstance(body, JSONResponse):
        return body
    text = body.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > 500:
        return _err(400, "bad_text", "Say what you're about to do, e.g. \"draw for 25\".")

    def run():
        con = db.connect()
        late = time.time() - float(body["client_ts"])
        if late > STALE_START_S and is_start(con, text):
            return 409, {"ok": False, "error": "stale_start", "session": _session(con),
                         "reply": f"That was said {round(late / 60)} min ago, so I didn't start it. "
                                  "Say it again if you're still going."}
        reply = cli.say(con, text)
        return 200, {"ok": True, "reply": reply, "session": _session(con)}
    return await run_in_threadpool(_once, "say", body["op_id"], run)   # cli work off the event loop


@router.post("/api/phone/session/end")
async def phone_end(request: Request):
    body = await _guard(request)
    if isinstance(body, JSONResponse):
        return body
    sid = body.get("session_id")
    if isinstance(sid, bool) or not isinstance(sid, int):
        return _err(400, "bad_session_id", "session_id must be the live session's id.")
    art = body.get("artefact")
    if art is not None and (not isinstance(art, str) or len(art) > 2000):
        return _err(400, "bad_artefact", "artefact must be a link or a path.")

    def run():
        con = db.connect()
        s = db.active_session(con)
        if not s or s["id"] != sid:
            done = db.get_session(con, sid)
            from . import verifier
            reply = verifier.voice(con, done) if done and done["status"] == "done" else "That session already ended."
            return 409, {"ok": False, "error": "already_ended", "reply": reply, "session": _session(con)}
        now = time.time()
        ended_at = None
        if now - float(body["client_ts"]) > LATE_END_S:     # the tap was a while ago: end it when it was tapped
            ended_at = min(max(float(body["client_ts"]), float(s["started_at"])), now)
        reply = cli.end(con, art or None, ended_at=ended_at)
        return 200, {"ok": True, "reply": reply, "session": _session(con)}
    return await run_in_threadpool(_once, "end", body["op_id"], run)


# --- the Plan page on the phone: the same view and edits as the dashboard's (routes_calendar), behind the key ---------

@router.get("/api/phone/plan")
def phone_plan(request: Request, days: int = 3):
    if not _client_ok(request.client.host if request.client else None):
        return _err(403, "lan_refused", "The plan only opens over Tailscale. Turn Tailscale on and try again.")
    if not integrations._secret_ok(request.headers.get("x-alibi-secret", "")):
        return _err(401, "bad_secret", "Wrong or missing key.")
    from . import routes_calendar
    return routes_calendar.days_view(days)


@router.post("/api/phone/plan/edit")
async def phone_plan_edit(request: Request):
    body = await _guard(request)
    if isinstance(body, JSONResponse):
        return body
    from fastapi import HTTPException
    from . import routes_calendar

    def run():                                   # every op is idempotent (same key, same state), so no op_id ledger
        try:
            return 200, routes_calendar.edit(body, source="phone")
        except HTTPException as e:
            return e.status_code, {"ok": False, "error": "refused", "reply": str(e.detail)}
    code, out = await run_in_threadpool(run)
    return JSONResponse(out, status_code=code)
