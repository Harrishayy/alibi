"""Agent API (docs/AGENT.md): what the NemoClaw agent on the DGX Spark may read and write, over Tailscale.

Mounted inside integrations.phone_app() (the :8766 listener), never on the loopback dashboard app.

GET  /api/agent/ping              -> {ok, ts, tz, agent_last_seen}
GET  /api/agent/context           -> one snapshot for a brief (week, today, free gaps, last night, milestones, signals)
GET  /api/agent/digests?limit=5   -> Alibi's own recent rules digests
POST /api/agent/brief             -> the agent's version of a slot's brief; stored, never evidence. A timely one also
                                     drops down on the island once per slot (kind "brief"), unless a session is live

Security: X-Alibi-Agent-Token (or Authorization: Bearer) — its own secret (`nemoclaw_token` in data/secrets.json),
never the phone key; a token in the query string is refused. Loopback or tailnet source only. Body <= 16 KB, 30
writes a minute, idempotency_key dedupe. The agent can't start, stop or change sessions, habits, goals or evidence:
its only write is a brief, and a brief is derived output kept in DATA_DIR/agent_briefs.jsonl (AGENTS.md rule 1).
"""
import collections, datetime as dt, hmac, json, os, re, secrets as _rand, threading, time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from . import config, db, digest, integrations, report, secrets as store
from .routes_phone import BODY_MAX, WRITES_PER_MIN, _client_ok

router = APIRouter()

TZ = os.getenv("ALIBI_TZ", "Europe/London")
KINDS = ("morning", "checkpoint", "night", "risk")
SLOT_RE = re.compile(r"(\d{4}-\d{2}-\d{2})-(morning|checkpoint|night|risk)(?:-(\d{2}))?")
SHOW_WITHIN_S = 20 * 60              # a brief this close to its slot is shown above the rules brief
TEXT_MAX, LINKS_MAX = 600, 5
NEVER_INCLUDED = ["camera frames", "window titles", "app names", "location coordinates", "notification text"]

_lock = threading.Lock()
_writes: collections.deque = collections.deque()


def agent_token(create: bool = True) -> str:
    t = store.get("nemoclaw_token") or ""
    if not t and create:
        t = _rand.token_urlsafe(24)
        store.update(nemoclaw_token=t)
    return t


def _token_ok(request: Request) -> bool:
    want = agent_token(create=False)
    given = request.headers.get("x-alibi-agent-token") or \
        request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    return bool(want) and hmac.compare_digest(given.encode(), want.encode())


def _err(code: int, error: str) -> JSONResponse:
    return JSONResponse({"ok": False, "error": error, "ts": int(time.time()), "tz": TZ}, status_code=code)


def _guard(request: Request) -> JSONResponse | None:
    if not _client_ok(request.client.host if request.client else None):
        return _err(403, "not_tailnet")
    if any(k in request.query_params for k in ("key", "token", "agent_token")):
        return _err(401, "token_in_url")
    if not _token_ok(request):
        return _err(401, "bad_token")
    integrations.set_state(agent_last_seen=time.time())
    return None


def _base() -> dict:
    return {"ts": int(time.time()), "tz": TZ}


@router.get("/api/agent/ping")
def ping(request: Request):
    if (e := _guard(request)):
        return e
    return {"ok": True, **_base(), "agent_last_seen": integrations.state().get("agent_last_seen")}


def context(now: float | None = None) -> dict:
    """The facts a brief may use. Aggregates only: no frames, titles, app names, coordinates or notification text."""
    now = now or time.time()
    con = db.connect()
    r = report.build_json(now, prose=False)
    t0 = report.week_start(now)
    today = dt.date.fromtimestamp(now)
    plan = [b for b in digest.calendar_sync.plan(con, today, 1, now) if b["state"] != "skipped"]
    habits = []
    for x in [digest._hrow(x) for x in r["rows"]] + digest._running_row(r.get("running")):
        habits.append({"key": x["habit"], "label": x["label"], "unit": x["unit"], "target": x["target_min"],
                       "verified": x["verified_min"], "status3": x["status3"], "buffer_days": x["buffer_days"],
                       "need_per_day_min": x["need_per_day_min"], "need_today_min": x["need_today_min"],
                       "stale": x["status3"] == "stale", "reason": x["reason"]})
    snap = digest._snapshot(r, plan)
    gaps = digest.free_gaps(con, today + dt.timedelta(days=1), 30, now)
    last = None
    for row in digest.rows(20, "night"):
        if row.get("slot", "").startswith((today - dt.timedelta(days=1)).isoformat()):
            p = (row.get("json") or {}).get("proposal") or row.get("proposal")
            mem = digest.memory(con, now)
            last = {"slot": row["slot"], "proposal": p and {k: p.get(k) for k in ("habit", "day", "at", "minutes")},
                    "accepted": bool(row.get("accepted_at")),
                    "kept": mem and {"seen_min": mem["seen_min"], "of": mem["minutes"], "state": mem["state"]}}
            break
    try:
        from . import routes_plan, signals
        miles = [{"title": m["label"], "due": m["due"], "done": m["status"] == "done"} for m in routes_plan.milestones(now)]
        st = signals.status(con)
        total = len([s for s in st["sources"] if s["state"] not in ("not_applicable",)])
        sig = {"flowing": len(st["flowing"]), "total": total, "text": f"{len(st['flowing'])} of {total} sources flowing"}
    except Exception:
        miles, sig = [], None
    return {**_base(),
            "week": {"start": dt.date.fromtimestamp(t0).isoformat(), "end": dt.date.fromtimestamp(t0 + 6 * 86400).isoformat()},
            "habits": habits,
            "today": {"planned_min": sum(b["min"] for b in plan),
                      "seen_min": round(sum(x.get("today_seen_min") or 0 for x in r["rows"])),
                      "picked_apps_min": snap.get("picked_min"),
                      "phone_last_synced": _phone_seen(now),
                      "blocks": [{"key": b["key"], "habit": b["habit"], "at": b["at"], "min": b["min"],
                                  "state": b["state"]} for b in plan]},
            "free_gaps_tomorrow": [{"at": g["at"], "min": g["minutes"]} for g in gaps],
            "sessions_today": _or_empty(_sessions_today, con, today, now),
            "claims_today": _or_empty(_claims_today, con, today, now),
            "away": _or_empty(_away, today),
            "last_night": last, "milestones": miles, "signals": sig, "never_included": NEVER_INCLUDED}


def _hm(ts) -> str | None:
    return time.strftime("%H:%M", time.localtime(ts)) if isinstance(ts, (int, float)) else None


def _or_empty(fn, *args) -> list:
    """One context key, built on its own: a bad row or a missing helper costs that key ([]), never /context."""
    try:
        return fn(*args)
    except Exception as e:
        print(f"[alibi] agent context {fn.__name__} skipped: {type(e).__name__}", flush=True)
        return []


def _day_bounds(day: dt.date) -> tuple[float, float]:
    return (dt.datetime.combine(day, dt.time()).timestamp(),
            dt.datetime.combine(day + dt.timedelta(days=1), dt.time()).timestamp())


def _sessions_today(con, today: dt.date, now: float) -> list:
    """Sessions started today, oldest first. Counts and states only: no titles, apps or camera labels."""
    t0, t1 = _day_bounds(today)
    out = []
    for s in con.execute("SELECT * FROM sessions WHERE started_at>=? AND started_at<? ORDER BY started_at, id", (t0, t1)):
        end = s["ended_at"] or now
        nudges = con.execute("SELECT count(*) FROM events WHERE session_id=? AND source='alibi' AND kind='nudge'",
                             (s["id"],)).fetchone()[0]
        shields = con.execute("SELECT payload FROM events WHERE source='phone' AND kind='shield' AND "
                              "(session_id=? OR ts BETWEEN ? AND ?)", (s["id"], s["started_at"], end)).fetchall()
        out.append({"habit": s["habit"], "label": config.display_name(s["habit"]), "at": _hm(s["started_at"]),
                    "min": max(0, round((end - s["started_at"]) / 60)),
                    "verdict": s["verdict"] if s["status"] == "done" else None, "nudges": nudges,
                    # phone/shield payload is {on, apps} (integrations.normalise_phone): on = the iPhone blocked apps
                    "phone_blocked": any(_payload(p).get("on") is True for (p,) in shields)})
    return out


def _claims_today(con, today: dt.date, now: float) -> list:
    """Today's "going for a run" claims: the run that matches (as daemon.check_claims matches it) and how it settled."""
    t0, t1 = _day_bounds(today)
    settled = {}
    for r in con.execute("SELECT ts, payload FROM events WHERE source='alibi' AND kind='claim_settled' ORDER BY id"):
        p = _payload(r["payload"])
        settled.setdefault(p.get("claim_id"), (bool(p.get("verified")), r["ts"]))
    out = []
    for c in con.execute("SELECT id, ts, payload FROM events WHERE source='user' AND kind='claim' AND ts>=? AND ts<? "
                         "ORDER BY ts, id", (t0, t1)):
        p = _payload(c["payload"])
        habit = str(p.get("habit") or "")
        runs = [e["payload"].get("distance_km") for e in
                db.events_between(con, c["ts"] - 600, float(p.get("until") or c["ts"]), "strava")
                if (e["payload"].get("distance_km") or 0) >= (p.get("min_km") or 0)]
        st = settled.get(c["id"])
        out.append({"habit": habit, "label": config.display_name(habit), "at": _hm(c["ts"]),
                    "km": runs[0] if runs else None, "verified": st[0] if st else None,
                    "settled_at": _hm(st[1]) if st else None})
    return out


def _away(today: dt.date) -> list:
    """Days off in the next two weeks, when calendar_sync can say (getattr: the helper is optional)."""
    from . import calendar_sync
    fn = getattr(calendar_sync, "away_days", None)
    if not callable(fn):
        return []
    return [{"date": str(d["date"]), "label": str(d.get("label") or "")} for d in (fn(today, 14) or [])]


def _payload(s) -> dict:
    try:
        p = json.loads(s)
    except (TypeError, ValueError):
        return {}
    return p if isinstance(p, dict) else {}


def _phone_seen(now: float) -> str | None:
    """When the iPhone last delivered anything: a batch (/ingest) or a foreground poll, whichever is newer. Not today ->
    the weekday too, so yesterday's 20:29 never reads as today's."""
    st = integrations.state()
    ts = max((x for x in (st.get("phone_last_received"), st.get("phone_last_polled")) if isinstance(x, (int, float))),
             default=None)
    if ts is None:
        return None
    same = dt.date.fromtimestamp(ts) == dt.date.fromtimestamp(now)
    return time.strftime("%H:%M" if same else "%a %H:%M", time.localtime(ts))


@router.get("/api/agent/context")
def get_context(request: Request):
    if (e := _guard(request)):
        return e
    return context()


@router.get("/api/agent/digests")
def get_digests(request: Request, limit: int = 5):
    if (e := _guard(request)):
        return e
    rows = digest.rows(max(1, min(int(limit), 20)))
    return {**_base(), "items": [{"slot": x.get("slot"), "kind": x.get("kind"), "ts": x.get("ts"),
                                  "sent": x.get("sent"), "text": x.get("text"), "via": x.get("via", "rules")}
                                 for x in rows]}


# --- briefs ------------------------------------------------------------------------------------------------------------

def _path():
    return config.DATA_DIR / "agent_briefs.jsonl"


def briefs(limit: int = 20) -> list:
    try:
        lines = _path().read_text().splitlines()
    except FileNotFoundError:
        return []
    out = []
    for l in lines[-limit * 4:]:
        try:
            out.append(json.loads(l))
        except ValueError:
            continue
    return out[-limit:]


def slot_ts(slot: str) -> float | None:
    """When a slot is due: Alibi's own schedule for its kinds; risk slots at their hour."""
    m = SLOT_RE.fullmatch(slot)
    if not m:
        return None
    day = dt.date.fromisoformat(m.group(1))
    for kind, sid, ts in digest.slots(day):
        if sid == slot:
            return ts
    if m.group(3):
        return dt.datetime(day.year, day.month, day.day, int(m.group(3))).timestamp()
    return None


def validate(b: dict) -> str | None:
    if not isinstance(b.get("idempotency_key"), str) or not re.fullmatch(r"[\w.:-]{1,128}", b["idempotency_key"]):
        return "bad_idempotency_key"
    if b.get("kind") not in KINDS:
        return "bad_kind"
    m = SLOT_RE.fullmatch(str(b.get("slot", "")))
    if not m or m.group(2) != b["kind"]:
        return "bad_slot"
    if not isinstance(b.get("text"), str) or not b["text"].strip() or len(b["text"]) > TEXT_MAX:
        return "bad_text"
    links = b.get("links") or []
    if not isinstance(links, list) or len(links) > LINKS_MAX or not all(
            isinstance(l, dict) and str(l.get("url", "")).startswith("https://") for l in links):
        return "bad_links"
    if not isinstance(b.get("items") or [], list):
        return "bad_items"
    return None


@router.post("/api/agent/brief")
async def post_brief(request: Request):
    if (e := _guard(request)):
        return e
    raw = await request.body()
    if len(raw) > BODY_MAX:
        return _err(413, "too_big")
    now = time.time()
    while _writes and now - _writes[0] > 60:
        _writes.popleft()
    if len(_writes) >= WRITES_PER_MIN:
        return _err(429, "rate_limited")
    _writes.append(now)
    try:
        b = json.loads(raw or b"{}")
    except ValueError:
        return _err(400, "bad_json")
    if not isinstance(b, dict):
        return _err(400, "bad_json")
    if (why := validate(b)):
        return _err(400, why)
    with _lock:
        for x in briefs(500):
            if x.get("idempotency_key") == b["idempotency_key"]:
                return JSONResponse(x["response"], headers={"X-Alibi-Replay": "1"})
        due = slot_ts(b["slot"])
        timely = due is not None and abs(now - due) <= SHOW_WITHIN_S
        resp = {"ok": True, "stored": b["slot"], "shown_as": "agent" if timely else "stored",
                "rules_version_folded": digest.has(b["slot"])}
        row = {"ts": now, "via": "nemoclaw", "idempotency_key": b["idempotency_key"], "slot": b["slot"],
               "kind": b["kind"], "text": b["text"].strip(), "items": b.get("items") or [], "links": b.get("links") or [],
               "model": str(b.get("model") or "")[:80], "tools_used": [str(t)[:40] for t in (b.get("tools_used") or [])][:10],
               "response": resp}
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        fd = os.open(_path(), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, (json.dumps(row, default=str) + "\n").encode())
        finally:
            os.close(fd)
        try:                           # under the lock: two keys for one slot can't both raise it
            _brief_alert(row)
        except Exception as e:         # the brief is stored; a failed alert never fails the POST
            print(f"[alibi] agent brief alert failed: {e!r}", flush=True)
    return resp


def _brief_alert(row: dict) -> bool:
    """One island alert per timely slot: never during a session, never twice for a slot,
    and ALIBI_BRIEF_ALERTS=all|scheduled|off (scheduled = morning, checkpoint and night, no heartbeat risk briefs)."""
    from . import cards, pinch, today
    from .notify import notify, recent_alerts
    if row["response"].get("shown_as") != "agent":
        return False
    mode = os.getenv("ALIBI_BRIEF_ALERTS", "all").strip().lower()
    if mode in ("off", "0", "no", "none", "false") or (mode == "scheduled" and row["kind"] == "risk"):
        return False
    if any(a.get("kind") == "brief" and a.get("slot") == row["slot"] for a in recent_alerts(500)):
        return False
    if db.active_session(db.connect()) is not None:
        return False                   # the agent never interrupts a session; the brief stays stored
    text = pinch.clean_brief(cards.display(row["text"]), sentences=2, cap=160)     # "off_track" never reaches a screen
    if not text:
        return False
    notify(text, kind="brief", habit_label="Your agent", source="nemoclaw", via="nemoclaw", slot=row["slot"],
           digest_kind=row["kind"], model=row["model"] or None, source_line=today.source_line(row["model"]),
           actions=[{"label": "Got it", "dismiss": True}, {"label": "Open dashboard", "url": "/#agent"}])
    return True
