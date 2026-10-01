"""F5 digests (NEXT_PHASE §3): a 07:30 brief that remembers last night's promise, checkpoints at 12/16/20 that only
speak when something changed, and a night review that proposes one recovery block.

build(kind, now) -> dict    pure over report.build_json(prose=False), calendar_sync.plan and the day's signals
text(d) -> str              rules, always first, in Alibi's voice
run(kind, now)              build + store in DATA_DIR/digests.jsonl (+ notify unless suppressed)
replan(con, now)            the night proposal: a bounded tool loop against LLM_BASE_URL, validated in code; any failure
                            falls back to the rules picker (via "rules"). Never applied until someone accepts it.
                            Night rows carry turns (model calls made) and total_ms; each trace step a short `result`.
accept(slot) / undo(slot)   put the proposal on the plan (calendar_sync.add_once) / take it off again

Digests are derived output, not evidence, so they live in a JSONL file and never in `events` (AGENTS.md rule 1).
Reading `sessions` here is a reporting read, like report.py.
"""
import datetime as dt, json, os, threading, time
from . import calendar_sync, config, db, report

KINDS = ("morning", "checkpoint", "night")
MAX_TURNS = 4
BUDGET_S = 45                       # the whole night loop, every turn included (llm.BACKGROUND_TIMEOUT_S)
SOON_S = 4 * 3600                   # a checkpoint speaks anyway if a block starts within this
_lock = threading.RLock()


# --- storage: DATA_DIR/digests.jsonl ---------------------------------------------------------------------------------

def _path():
    return config.DATA_DIR / "digests.jsonl"


def _read() -> list:
    try:
        lines = _path().read_text().splitlines()
    except FileNotFoundError:
        return []
    out = []
    for l in lines:
        try:
            out.append(json.loads(l))
        except ValueError:
            continue                # a torn line never takes the history down
    return out


def append(row: dict) -> dict:
    """One line per digest, written with a single O_APPEND write so concurrent writers can't interleave."""
    with _lock:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        fd = os.open(_path(), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, (json.dumps(row, default=str) + "\n").encode())
        finally:
            os.close(fd)
    return row


def _rewrite(fn) -> None:
    """Change rows in place (accept): read, edit, write a temp file, atomic rename."""
    with _lock:
        rows = _read()
        fn(rows)
        tmp = _path().with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(r, default=str) + "\n" for r in rows))
        os.replace(tmp, _path())


def rows(limit: int = 20, kind: str | None = None) -> list:
    """Newest first."""
    out = [r for r in reversed(_read()) if kind is None or r.get("kind") == kind]
    return out[:max(0, int(limit))]


def latest(kind: str | None = None) -> dict | None:
    r = rows(1, kind)
    return r[0] if r else None


def get(slot: str) -> dict | None:
    return next((r for r in reversed(_read()) if r.get("slot") == slot), None)


def has(slot: str) -> bool:
    return any(r.get("slot") == slot for r in _read())


# --- slots ---------------------------------------------------------------------------------------------------------

def _hm(s: str) -> tuple:
    h, m = (int(x) for x in str(s).split(":")[:2])
    return h, m


def slots(day: dt.date) -> tuple:
    """(kind, slot_id, ts) for one day, in time order: YYYY-MM-DD-morning, -checkpoint-HH, -night."""
    at = lambda h, m=0: dt.datetime(day.year, day.month, day.day, h, m).timestamp()
    out = [("morning", f"{day}-morning", at(*_hm(config.MORNING_AT)))]
    out += [("checkpoint", f"{day}-checkpoint-{h:02d}", at(h)) for h in config.CHECK_HOURS if 0 <= h <= 23]
    if 0 <= config.REPORT_HOUR <= 23:                    # REPORT_HOUR=-1 turns the nightly report (and night slot) off
        out.append(("night", f"{day}-night", at(config.REPORT_HOUR)))
    return tuple(sorted(out, key=lambda x: x[2]))


def slot_id(kind: str, now: float) -> str:
    d = dt.datetime.fromtimestamp(now)
    return f"{d:%Y-%m-%d}-{kind}" + (f"-{d.hour:02d}" if kind == "checkpoint" else "")


def due(now: float) -> tuple | None:
    """The most recent slot of today that has begun. On wake only this one runs: older missed slots are skipped."""
    past = [s for s in slots(dt.date.fromtimestamp(now)) if s[2] <= now]
    return past[-1] if past else None


# --- helpers ---------------------------------------------------------------------------------------------------------

def _t(ts: float) -> str:
    return time.strftime("%H:%M", time.localtime(ts))


def _d0(day: dt.date) -> float:
    return dt.datetime(day.year, day.month, day.day).timestamp()


def _mins(x) -> str:
    x = round(x or 0)
    return f"{x // 60} h {x % 60} min" if x >= 60 else f"{x} min"


def _hrow(x: dict) -> dict:
    keep = ("habit", "label", "status3", "reason", "buffer_days", "need_today_min", "need_per_day_min", "unit",
            "verified_min", "target_min", "today_seen_min", "today_planned_min", "verdicts")
    return {k: x.get(k) for k in keep}


def _running_row(g: dict | None) -> list:
    if not g:
        return []
    return [{"habit": g["habit"], "label": g["label"], "status3": g.get("status3"), "reason": g.get("reason"),
             "buffer_days": g.get("buffer_days"), "need_today_min": g.get("need_today_min"),
             "need_per_day_min": g.get("need_per_day_min"), "unit": "runs", "verified_min": g.get("qualifying"),
             "target_min": g.get("target_sessions"), "today_seen_min": None, "today_planned_min": None,
             "verdicts": None}]


def _block(b: dict) -> dict:
    return {"key": b["key"], "habit": b["habit"], "label": b["label"], "at": b["at"], "min": b["min"],
            "start": b["start"], "end": b["end"], "state": b["state"], "once": bool(b.get("once"))}


def _busy(con, day: dt.date, now: float) -> list:
    """Planned blocks (not skipped) and sessions on a day, as (start, end)."""
    iv = [(b["start"], b["end"]) for b in calendar_sync.plan(con, day, 1, now) if b["state"] != "skipped"]
    d0 = _d0(day)
    for s in con.execute("SELECT started_at, ended_at, ends_at FROM sessions WHERE started_at < ? AND "
                         "COALESCE(ended_at, ends_at) > ?", (d0 + 86400, d0)):
        iv.append((s["started_at"], s["ended_at"] or s["ends_at"]))
    return sorted(iv)


def _window(day: dt.date) -> tuple:
    d0 = _d0(day)
    (h0, m0), (h1, m1) = _hm(config.DIGEST_GAP_FROM), _hm(config.DIGEST_GAP_TO)
    return d0 + h0 * 3600 + m0 * 60, d0 + h1 * 3600 + m1 * 60


def free_gaps(con, day: dt.date, min_minutes: int, now: float) -> list:
    """Gaps between planned blocks and sessions, 07:00–22:00, at least `min_minutes` long. Starts round up to 5 min."""
    lo, hi = _window(day)
    lo = max(lo, -(-now // 300) * 300)
    gaps, cur = [], lo
    for s, e in _busy(con, day, now) + [(hi, hi)]:
        if e <= cur and s < hi:
            continue
        s = min(s, hi)
        if s > cur and (s - cur) / 60 >= min_minutes:
            gaps.append({"at": _t(cur), "until": _t(s), "minutes": int((s - cur) // 60), "start": cur})
        if s >= hi:
            break
        cur = max(cur, -(-e // 300) * 300)
    return gaps


def _sessions_on(con, day: dt.date) -> list:
    d0 = _d0(day)
    return con.execute("SELECT * FROM sessions WHERE status='done' AND started_at >= ? AND started_at < ? "
                       "ORDER BY started_at", (d0, d0 + 86400)).fetchall()


def _sleep(con, day: dt.date) -> float | None:
    """Last night's sleep as Health reported it for today's date. No sample, no claim."""
    v = None
    for (p,) in con.execute("SELECT payload FROM events WHERE source='health' AND kind='samples' ORDER BY id"):
        try:
            p = json.loads(p)
        except ValueError:
            continue
        if p.get("date") == day.isoformat() and isinstance(p.get("sleep_h"), (int, float)):
            v = float(p["sleep_h"])
    return v


def _snapshot(r: dict, plan_today: list) -> dict:
    sig = r.get("signals") or {}
    return {"habits": {x["habit"]: {"verified_min": x["verified_min"], "today_seen_min": x["today_seen_min"],
                                    "verdicts": x["verdicts"], "status3": x.get("status3")} for x in r["rows"]},
            "blocks_missed": sum(b["state"] == "missed" for b in plan_today),
            "picked_min": ((sig.get("screentime") or {}).get("total_min") or 0)}


def _diff(prev: dict | None, cur: dict) -> list:
    """What changed since the previous slot: verified minutes, verdicts, missed blocks, picked-app minutes, status."""
    prev = prev or {"habits": {}, "blocks_missed": 0, "picked_min": 0}
    out = []
    for h, c in cur["habits"].items():
        p = prev["habits"].get(h) or {"verified_min": 0, "verdicts": {}, "status3": None}
        if c["verified_min"] != p.get("verified_min", 0):
            out.append({"habit": h, "field": "verified_min", "from": p.get("verified_min", 0), "to": c["verified_min"]})
        for v, n in (c.get("verdicts") or {}).items():
            if n != (p.get("verdicts") or {}).get(v, 0):
                out.append({"habit": h, "field": v, "from": (p.get("verdicts") or {}).get(v, 0), "to": n})
        if p.get("status3") is not None and c.get("status3") != p.get("status3"):
            out.append({"habit": h, "field": "status3", "from": p["status3"], "to": c["status3"]})
    if cur["blocks_missed"] != prev.get("blocks_missed", 0):
        out.append({"habit": None, "field": "blocks_missed", "from": prev.get("blocks_missed", 0),
                    "to": cur["blocks_missed"]})
    if abs((cur["picked_min"] or 0) - (prev.get("picked_min") or 0)) >= 10:   # Screen Time drifts by a few min
        out.append({"habit": None, "field": "picked_min", "from": prev.get("picked_min"), "to": cur["picked_min"]})
    return out


# --- memory: did last night's promise happen? ------------------------------------------------------------------------

def memory(con, now: float) -> dict | None:
    """The newest accepted night proposal whose block is today or ended in the last 30 h, and what the sessions say."""
    for r in rows(50, "night"):
        p = r.get("proposal")
        if not (p and r.get("accepted_at")):
            continue
        try:
            start = dt.datetime.fromisoformat(f"{p['day']}T{p['at']}").timestamp()
        except (KeyError, ValueError):
            continue
        end = start + int(p["minutes"]) * 60
        today = dt.date.fromtimestamp(now)
        if start - now > 24 * 3600 or now - end > 30 * 3600:
            continue
        name = config.spoken_name(p["habit"])
        pday = dt.date.fromisoformat(p["day"])
        lead = f"Last night you moved {name} to {p['at']}." if pday == today \
            else f"You moved {name} to {p['at']} {'yesterday' if pday == today - dt.timedelta(days=1) else pday.strftime('%A')}."
        ss = con.execute("SELECT * FROM sessions WHERE habit=? AND started_at BETWEEN ? AND ?",
                         (p["habit"], start - calendar_sync.MATCH_BEFORE_S, end + calendar_sync.LATE_OK_S)).fetchall()
        seen = round(sum(s["declared_min"] * (s["on_task_ratio"] or 0) for s in ss if s["status"] == "done"))
        live = any(s["status"] == "active" for s in ss)
        if now < start and not ss:
            state, tail = "upcoming", "It's on today's plan."
        elif live:
            state, tail = "now", "You're on it now."
        elif seen > 0:
            state, tail = ("kept" if seen >= 0.8 * int(p["minutes"]) else "partial"), \
                f"You showed up for {seen} of {p['minutes']} minutes."
        elif now < end + calendar_sync.LATE_OK_S:
            state, tail = "now", "It's on now."
        else:
            state, tail = "missed", "You didn't make it."
        return {"slot": r["slot"], "habit": p["habit"], "label": p.get("label"), "day": p["day"], "at": p["at"],
                "minutes": p["minutes"], "seen_min": seen, "state": state, "text": f"{lead} {tail}"}
    return None


# --- the replan: tools, validator, rules picker, the loop -------------------------------------------------------------

def _day_arg(v, now: float) -> dt.date:
    today = dt.date.fromtimestamp(now)
    s = str(v or "tomorrow").strip().lower()
    if s in ("today",):
        return today
    if s in ("tomorrow", "tmrw"):
        return today + dt.timedelta(days=1)
    return dt.date.fromisoformat(s[:10])


def _cap(h: dict) -> int:
    return min(config.MAX_SESSION_MIN or 120, 2 * int(h.get("default_min") or 25))


def validate(con, p: dict, now: float, cfg: dict | None = None) -> tuple:
    """(ok, reason, normalised proposal). NEXT_PHASE §4 'Replan validator'."""
    cfg = cfg or config.habits()
    h = (cfg.get("habits") or {}).get(p.get("habit"))
    if not isinstance(h, dict) or h.get("source") in ("strava", "health"):
        return False, "unknown or untimed habit", None
    try:
        day = _day_arg(p.get("day"), now)
        hh, mm = _hm(p.get("at"))
        minutes = int(p.get("minutes"))
        start = dt.datetime(day.year, day.month, day.day, hh, mm).timestamp()
    except (TypeError, ValueError):
        return False, "bad day, time or minutes", None
    today = dt.date.fromtimestamp(now)
    if (day - today).days not in (1, 2):
        return False, "day must be tomorrow or the day after", None
    if not 0 < minutes <= _cap(h):
        return False, f"minutes must be 1–{_cap(h)}", None
    lo, hi = _window(day)
    end = start + minutes * 60
    if start < lo or end > hi:
        return False, f"outside {config.DIGEST_GAP_FROM}–{config.DIGEST_GAP_TO}", None
    if any(s < end and start < e for s, e in _busy(con, day, now)):
        return False, "overlaps a planned block or a session", None
    out = {"habit": p["habit"], "label": config.display_name(p["habit"], cfg), "day": day.isoformat(),
           "at": f"{hh:02d}:{mm:02d}", "minutes": minutes, "why": str(p.get("why") or "")[:200]}
    return True, "ok", out


def rules_pick(con, now: float, week: list, cfg: dict | None = None) -> dict | None:
    """The habit with the least buffer (ties: more needed per day) goes to the first gap ≥ its default length
    tomorrow (then the day after). Nothing behind, nothing to propose."""
    cfg = cfg or config.habits()
    cands = [x for x in week if x.get("unit") != "runs" and x.get("status3") not in ("done", "stale", None)
             and (x.get("need_per_day_min") or 0) > 0 and (x.get("buffer_days") or 0) < 1
             and isinstance(cfg["habits"].get(x["habit"]), dict)]
    if not cands:
        return None
    x = min(cands, key=lambda x: ((x.get("buffer_days") or 0), -(x.get("need_per_day_min") or 0)))
    h = cfg["habits"][x["habit"]]
    m = min(int(h.get("default_min") or 25), _cap(h))
    for i in (1, 2):
        day = dt.date.fromtimestamp(now) + dt.timedelta(days=i)
        g = free_gaps(con, day, m, now)
        if g:
            why = x.get("reason") or "Furthest behind this week."
            return {"habit": x["habit"], "label": x["label"], "day": day.isoformat(), "at": g[0]["at"], "minutes": m,
                    "why": why}
    return None


TOOLS = [
    {"type": "function", "function": {"name": "week_status", "description":
        "This week's pace per habit: status3 (on_track|at_risk|off_track|done|stale), buffer_days, need_per_day_min.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "plan", "description": "Planned blocks on a day.",
        "parameters": {"type": "object", "properties": {"day": {"type": "string", "description": "YYYY-MM-DD"}},
                       "required": ["day"]}}},
    {"type": "function", "function": {"name": "free_gaps", "description":
        "Free time on a day between planned blocks and sessions, 07:00-22:00.",
        "parameters": {"type": "object", "properties": {"day": {"type": "string"}, "min_minutes": {"type": "integer"}},
                       "required": ["day", "min_minutes"]}}},
    {"type": "function", "function": {"name": "history", "description": "Verified minutes per day for one habit.",
        "parameters": {"type": "object", "properties": {"habit": {"type": "string"}, "days": {"type": "integer"}},
                       "required": ["habit"]}}},
    {"type": "function", "function": {"name": "propose", "description":
        "Propose ONE recovery block. The user confirms it; nothing is applied automatically.",
        "parameters": {"type": "object", "properties": {
            "habit": {"type": "string"}, "day": {"type": "string", "description": "YYYY-MM-DD, tomorrow or the day after"},
            "at": {"type": "string", "description": "HH:MM, 24h"}, "minutes": {"type": "integer"},
            "why": {"type": "string"}}, "required": ["habit", "day", "at", "minutes", "why"]}}},
]

SYSTEM = ("You are Alibi's night planner. Recover the habit that is furthest behind this week with ONE block tomorrow "
          "(or the day after). Look before you propose: call week_status, then plan and free_gaps for the day, then "
          "call propose exactly once. Only use free time between 07:00 and 22:00. Keep `why` to one short sentence.")


def _history(con, habit: str, days: int, now: float) -> list:
    days = max(1, min(int(days or 14), 60))
    today = dt.date.fromtimestamp(now)
    got = {r[0]: round(r[1] or 0) for r in con.execute(
        "SELECT date(started_at,'unixepoch','localtime') d, SUM(declared_min*COALESCE(on_task_ratio,0)) FROM sessions "
        "WHERE habit=? AND status='done' AND started_at>=? GROUP BY d", (habit, _d0(today) - (days - 1) * 86400))}
    return [{"date": (today - dt.timedelta(days=i)).isoformat(),
             "min": got.get((today - dt.timedelta(days=i)).isoformat(), 0)} for i in range(days - 1, -1, -1)]


def tool_call(con, name: str, args: dict, now: float, week: list):
    """The in-process tools. Pure reads; `propose` only validates."""
    if name == "week_status":
        return [{k: x.get(k) for k in ("habit", "label", "status3", "buffer_days", "need_per_day_min",
                                       "need_today_min", "verified_min", "target_min", "reason")} for x in week]
    if name == "plan":
        day = _day_arg(args.get("day"), now)
        return [{"habit": b["habit"], "at": b["at"], "min": b["min"], "state": b["state"]}
                for b in calendar_sync.plan(con, day, 1, now)]
    if name == "free_gaps":
        day = _day_arg(args.get("day"), now)
        return [{k: g[k] for k in ("at", "until", "minutes")}
                for g in free_gaps(con, day, int(args.get("min_minutes") or 25), now)]
    if name == "history":
        return _history(con, str(args.get("habit")), args.get("days") or 14, now)
    if name == "propose":
        ok, why, p = validate(con, args, now)
        return {"ok": ok, "reason": why, "proposal": p}
    return {"error": f"no tool {name}"}


def _short(s: str, n: int = 60) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n - 1].rstrip(" ,") + "…"


def _signed(x) -> str:
    return "0" if not x else f"{x:+g}".replace("-", "−")


def _dayword(day: dt.date, now: float) -> str:
    n = (day - dt.date.fromtimestamp(now)).days
    return {0: "today", 1: "tomorrow"}.get(n, day.strftime("%a"))


def step_result(name: str, args: dict, res, now: float) -> str:
    """One plain line per trace step for the replan view (≤60 chars): what the tool found, not its JSON."""
    try:
        if isinstance(res, dict) and res.get("error"):
            return _short(f"error: {res['error']}")
        if name == "week_status":
            behind = [x for x in res if x.get("buffer_days") is not None and x.get("status3") not in ("done", "stale")]
            if not behind:
                return f"{len(res)} habit{'s' * (len(res) != 1)}, none behind"
            x = min(behind, key=lambda x: x["buffer_days"])
            if x["buffer_days"] >= 1:
                return "all on pace"
            return _short(f"{config.spoken_name(x['habit'])} {_signed(x['buffer_days'])} d behind most")
        if name == "plan":
            n = len([b for b in res if b.get("state") != "skipped"])
            return f"{n or 'no'} block{'s' * (n != 1)} {_dayword(_day_arg(args.get('day'), now), now)}"
        if name == "free_gaps":
            return _short(", ".join(f"{g['at']}–{g['until']}" for g in res) or "no free gaps")
        if name == "history":
            tot = sum(x["min"] for x in res)
            return f"{tot} min over {len(res)} d"
        if name == "propose":
            return "valid" if res.get("ok") else _short(f"invalid: {res.get('reason')}")
    except Exception:
        pass
    return ""


def _replan(con, now: float, use_llm: bool | None = None, base_url: str | None = None, model: str | None = None,
            budget_s: float = BUDGET_S, week: list | None = None) -> dict:
    """The replan with its totals: {proposal, trace, via, turns, total_ms}. turns = model calls that answered;
    total_ms = the whole thing, model calls and the rules fallback included."""
    t_all = time.perf_counter()
    if week is None:
        r = report.build_json(now, prose=False)
        week = [_hrow(x) for x in r["rows"]]
    use_llm = config.TEXT_READY if use_llm is None else use_llm
    trace, turns = [], 0

    def done(p, via):
        return {"proposal": p, "trace": trace, "via": via, "turns": turns,
                "total_ms": round((time.perf_counter() - t_all) * 1000)}

    if use_llm:
        from . import llm
        t_start = time.monotonic()
        tomorrow = dt.date.fromtimestamp(now) + dt.timedelta(days=1)
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Now: {dt.datetime.fromtimestamp(now):%A %Y-%m-%d %H:%M}. "
                                            f"Tomorrow is {tomorrow:%A %Y-%m-%d}. Plan the recovery."}]
        try:
            for _ in range(MAX_TURNS):
                left = budget_s - (time.monotonic() - t_start)
                if left <= 0.5:
                    trace.append({"tool": "timeout", "args": {}, "ms": 0, "result": "time budget spent"})
                    break
                m = llm.chat_tools(msgs, TOOLS, timeout=left, base_url=base_url, model=model)
                turns += 1
                calls = m.tool_calls or []
                if not calls:
                    break                                   # prose instead of tools: no tool support, or gave up
                msgs.append({"role": "assistant", "content": m.content or "", "tool_calls": [
                    {"id": c.id, "type": "function", "function": {"name": c.function.name,
                                                                  "arguments": c.function.arguments or "{}"}}
                    for c in calls]})
                for c in calls:
                    t0 = time.perf_counter()
                    try:
                        args = json.loads(c.function.arguments or "{}") or {}
                        args = args if isinstance(args, dict) else {}
                        res = tool_call(con, c.function.name, args, now, week)
                    except Exception as e:
                        args, res = {}, {"error": str(e)[:200]}
                    trace.append({"tool": c.function.name, "args": args, "ms": round((time.perf_counter() - t0) * 1000),
                                  "result": step_result(c.function.name, args, res, now)})
                    if c.function.name == "propose":
                        if res.get("ok"):
                            return done(dict(res["proposal"], via=llm.via_for(base_url)), llm.via_for(base_url))
                        trace[-1]["error"] = res.get("reason")
                        raise ValueError(f"invalid proposal: {res.get('reason')}")
                    msgs.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(res, default=str)[:4000]})
        except Exception as e:
            print(f"[alibi] replan loop fell back to rules: {e!r}"[:300], flush=True)
    t0 = time.perf_counter()
    p = rules_pick(con, now, week)
    res = (_short(f"{config.spoken_name(p['habit'])} {_dayword(dt.date.fromisoformat(p['day']), now)} {p['at']}, "
                  f"{p['minutes']} min") if p else "nothing behind, no proposal")
    trace.append({"tool": "rules picker", "args": {}, "ms": round((time.perf_counter() - t0) * 1000), "result": res})
    return done(dict(p, via="rules") if p else None, "rules")


def replan(con, now: float, use_llm: bool | None = None, base_url: str | None = None, model: str | None = None,
           budget_s: float = BUDGET_S, week: list | None = None) -> tuple:
    """-> (proposal | None, trace, via). The model may choose; code validates. Anything off -> rules."""
    r = _replan(con, now, use_llm, base_url, model, budget_s, week)
    return r["proposal"], r["trace"], r["via"]


# --- build + text ----------------------------------------------------------------------------------------------------

PINCH = {"morning": "Morning. I've got the plan. You've got the pen.",
         "checkpoint": "Something moved. I wrote it down.",
         "checkpoint_quiet": "Nothing new. Still watching.",
         "night": "Closing the file on today."}


def build(kind: str, now: float | None = None, con=None, prev: dict | None = None, replan_kw: dict | None = None) -> dict:
    """The digest as data. `prev` is the previous slot's stored JSON (checkpoint diff)."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    now = now or time.time()
    con = con or db.connect()
    cfg = config.habits()
    r = report.build_json(now, prose=False)
    today = dt.date.fromtimestamp(now)
    plan_today = calendar_sync.plan(con, today, 1, now)
    habits = [_hrow(x) for x in r["rows"]] + _running_row(r.get("running"))
    snap = _snapshot(r, plan_today)
    sig = r.get("signals") or {}
    d = {"kind": kind, "day": today.isoformat(), "at": _t(now), "generated_at": now, "habits": habits,
         "blocks": [_block(b) for b in plan_today if b["state"] != "skipped"], "snapshot": snap,
         "signals": {"picked_min": snap["picked_min"], "pickups": sig.get("pickups")} if sig else None,
         "alibi_score": r.get("alibi_score")}
    if kind == "morning":
        need = sorted((x for x in habits if x["unit"] == "min" and (x.get("need_today_min") or 0) > 0),
                      key=lambda x: -x["need_today_min"])
        d["need_today"] = [{"habit": x["habit"], "label": x["label"], "minutes": x["need_today_min"]} for x in need]
        top = cfg["habits"].get(need[0]["habit"], {}) if need else {}
        gm = int(top.get("default_min") or 25)
        g = free_gaps(con, today, gm, now)
        d["first_gap"] = dict({k: g[0][k] for k in ("at", "until", "minutes")}, for_habit=need[0]["habit"] if need else None,
                              min_minutes=gm) if g else None
        d["sleep_h"] = _sleep(con, today)
        d["memory"] = memory(con, now)
    elif kind == "checkpoint":
        d["changes"] = _diff((prev or {}).get("snapshot"), snap)
        soon = [b for b in plan_today if b["state"] == "planned" and now < b["start"] <= now + SOON_S]
        d["next_block"] = _block(soon[0]) if soon else None
        d["since"] = (prev or {}).get("at")
        d["send"] = bool(d["changes"] or d["next_block"])
        if d["next_block"]:
            b = d["next_block"]
            d["action"] = {"label": f"Start {b['min']} min", "say": f"{b['habit']} for {b['min']} minutes"}
        else:
            behind = [x for x in habits if x["unit"] == "min" and (x.get("need_today_min") or 0) > 0]
            x = max(behind, key=lambda x: x["need_today_min"], default=None)
            m = int((cfg["habits"].get(x["habit"]) or {}).get("default_min") or 25) if x else 0
            d["action"] = {"label": f"Start {m} min", "say": f"{x['habit']} for {m} minutes"} if x else None
    else:
        ss = _sessions_on(con, today)
        lst = lambda v: [{"habit": s["habit"], "label": config.display_name(s["habit"], cfg), "at": _t(s["started_at"]),
                          "seen_min": round(s["declared_min"] * (s["on_task_ratio"] or 0)), "declared_min": s["declared_min"]}
                         for s in ss if s["verdict"] == v]
        d.update(done=lst("done"), partial=lst("partial"), slacked=lst("slacked"),
                 missed=[_block(b) for b in plan_today if b["state"] == "missed"])
        d["buffers"] = [{"habit": x["habit"], "label": x["label"], "buffer_days": x["buffer_days"],
                         "status3": x["status3"]} for x in habits]
        rp = _replan(con, now, week=[x for x in habits if x["unit"] == "min"], **(replan_kw or {}))
        d.update({k: rp[k] for k in ("proposal", "trace", "via", "turns", "total_ms")})
        tomorrow = today + dt.timedelta(days=1)
        d["tomorrow"] = [_block(b) for b in calendar_sync.plan(con, tomorrow, 1, now) if b["state"] != "skipped"]
        worst = min((x for x in habits if x["status3"] in ("off_track", "at_risk")),
                    key=lambda x: x.get("buffer_days") or 0, default=None)
        d["fix_tomorrow"] = ({"habit": worst["habit"], "label": worst["label"], "reason": worst["reason"]}
                             if worst else None)
    d["pinch"] = PINCH["checkpoint_quiet" if kind == "checkpoint" and not d.get("send") else kind]
    return d


def _ask(p: dict, now: float) -> str:
    day = dt.date.fromisoformat(p["day"])
    when = "tomorrow" if (day - dt.date.fromtimestamp(now)).days == 1 else day.strftime("%A")
    return f"Move {config.spoken_name(p['habit'])} to {when} {p['at']}, {p['minutes']} min?"


def _need_line(x: dict) -> str:
    return f"{x['label']} needs {x['minutes']} min today."


def text(d: dict) -> str:
    """Rules, in Alibi's voice: dry, short, 24 h times, no exclamation marks."""
    k = d["kind"]
    out = []
    if k == "morning":
        if d.get("memory"):
            out.append(d["memory"]["text"])
        bl = d["blocks"]
        out.append("Today: " + ", ".join(f"{b['label']} {b['at']} ({b['min']} min)" if b["state"] in ("planned", "now")
                                         else f"{b['label']} {b['at']} ({b['state']})" for b in bl) + "."
                   if bl else "Nothing planned today.")
        if d.get("need_today"):
            out.append(" ".join(_need_line(x) for x in d["need_today"][:3]))
        else:
            out.append("Nothing needed today to stay on pace.")
        g = d.get("first_gap")
        if g:
            out.append(f"First free gap: {g['at']}–{g['until']}.")
        if d.get("sleep_h") is not None:
            out.append(f"Sleep: {d['sleep_h']:.1f} h.")
    elif k == "checkpoint":
        lines = []
        for c in d.get("changes") or []:
            name = config.display_name(c["habit"]) if c["habit"] else None
            if c["field"] == "verified_min":
                lines.append(f"{name}: {c['to'] - c['from']:+d} min seen, {c['to']} this week.")
            elif c["field"] in ("done", "partial", "slacked") and c["to"] > c["from"]:
                lines.append(f"{name}: {c['to'] - c['from']} {c['field']}.")
            elif c["field"] == "status3":
                lines.append(f"{name} is now {c['to'].replace('_', ' ')}.")
            elif c["field"] == "blocks_missed" and c["to"] > c["from"]:
                lines.append(f"{c['to'] - c['from']} planned block{'s' * (c['to'] - c['from'] != 1)} missed.")
            elif c["field"] == "picked_min":
                lines.append(f"Picked apps: {c['to']} min today.")
        since = f"Since {d['since']}: " if d.get("since") else ""
        out.append(since + (" ".join(lines) if lines else "nothing new."))
        b = d.get("next_block")
        if b:
            out.append(f"Next: {b['label']} at {b['at']}, {b['min']} min.")
    else:
        def names(xs, f=lambda x: f"{x['label']} {x['seen_min']} min"):
            return ", ".join(f(x) for x in xs) if xs else "none"
        parts = [f"{w}: {names(d[k], f) if f else names(d[k])}." for w, k, f in
                 (("Done", "done", None), ("Partial", "partial", None), ("Slacked", "slacked", None),
                  ("Missed", "missed", lambda b: f"{b['label']} {b['at']}")) if d[k]]
        out.append("Day closed. " + (" ".join(parts) if parts else "Nothing seen today."))
        bufs = [x for x in d["buffers"] if x.get("buffer_days") is not None and x["status3"] not in ("done", "stale")]
        if bufs:
            out.append("Buffer: " + ", ".join(f"{x['label']} {x['buffer_days']:+g} d" if x["buffer_days"]
                                              else f"{x['label']} 0 d" for x in bufs) + ".")
        if d.get("alibi_score") is not None:
            out.append(f"{d['alibi_score']:.0%} of this week's claims held up.")
        if d.get("fix_tomorrow"):
            f = d["fix_tomorrow"]
            out.append(f"Fix tomorrow: {f['label']}. {f['reason']}")
        if d.get("proposal"):
            out.append(_ask(d["proposal"], d["generated_at"]))
    return "\n".join(out)


# --- run: build, store, notify ---------------------------------------------------------------------------------------

def _prev_today(now: float) -> dict | None:
    day = dt.date.fromtimestamp(now).isoformat()
    for r in rows(50):
        if r.get("ts", 0) <= now and (r.get("json") or {}).get("day") == day:
            return r.get("json")
    return None


def run(kind: str, now: float | None = None, send: bool = True, slot: str | None = None, con=None,
        replan_kw: dict | None = None) -> dict:
    """Build, store one row and (if it has something to say and `send`) notify kind="digest". The night digest is
    sent by daemon._nightly as the nightly report (send=False here), so there is still one notification."""
    now = now or time.time()
    con = con or db.connect()
    base = slot or slot_id(kind, now)
    slot, n = base, 1
    while has(slot):                               # a manual re-run never overwrites the scheduled row
        n += 1
        slot = f"{base}-{n}"
    d = build(kind, now, con, prev=_prev_today(now) if kind == "checkpoint" else None, replan_kw=replan_kw)
    d["slot"] = slot
    body = text(d)
    sent = kind != "checkpoint" or d["send"]
    row = {"slot": slot, "kind": kind, "ts": now, "sent": bool(sent and (send or kind == "night")), "json": d,
           "text": body, "via": d.get("via", "rules")}
    if kind == "night":
        row.update(proposal=d.get("proposal"), trace=d.get("trace"), turns=d.get("turns"), total_ms=d.get("total_ms"),
                   accepted_at=None)
    append(row)
    if sent and send:
        from .notify import notify
        notify(body, kind="digest", slot=slot, digest_kind=kind, actions=actions(row))
    return row


def actions(row: dict) -> list:
    d = row.get("json") or {}
    if row.get("kind") == "night" and row.get("proposal"):
        return [{"label": "Accept", "post": f"/api/digests/{row['slot']}/accept", "body": {}, "dismiss": True},
                {"label": "Not now", "dismiss": True}]
    return [d["action"]] if d.get("action") else []


def accept(slot: str, now: float | None = None) -> dict:
    """Apply a night proposal through calendar_sync.add_once. Idempotent."""
    now = now or time.time()
    row = get(slot)
    if row is None:
        raise LookupError("No digest with that slot.")
    p = row.get("proposal")
    if not p:
        raise LookupError("That digest has no proposal.")
    when = _ask(p, row["ts"]).split(" to ", 1)[1].rstrip("?")
    if row.get("accepted_at"):
        return {"ok": True, "reply": f"Already on the plan: {config.spoken_name(p['habit'])} {when}.", "already": True}
    start = dt.datetime.fromisoformat(f"{p['day']}T{p['at']}").timestamp()
    if start <= now:
        return {"ok": False, "reply": "That slot has passed."}
    b = calendar_sync.add_once(p["habit"], p["day"], p["at"], p["minutes"])

    def mark(rs):
        for r in rs:
            if r.get("slot") == slot:
                r["accepted_at"] = now
                r["accepted_key"] = b["key"] if b else _once_key(p)
    _rewrite(mark)
    return {"ok": True, "reply": f"Done. {config.display_name(p['habit'])} {when}. It's on the plan.",
            "block": {k: b[k] for k in ("key", "habit", "date", "at", "min")} if b else None}


def _once_key(p: dict) -> str:
    return f"{p['habit']}@{p['day']}T{p['at']}"            # calendar_sync.add_once's key


class NotAccepted(Exception):
    """Undo of a proposal that isn't on the plan (409)."""


def undo(slot: str, now: float | None = None) -> dict:
    """Reverse accept: drop the add_once block and clear accepted_at (same atomic rewrite), so the morning memory
    never mentions it and accept works again."""
    now = now or time.time()
    row = get(slot)
    if row is None:
        raise LookupError("No digest with that slot.")
    p = row.get("proposal")
    if not p:
        raise LookupError("That digest has no proposal.")
    if not row.get("accepted_at"):
        raise NotAccepted("That proposal isn't on the plan.")
    calendar_sync.remove_once(row.get("accepted_key") or _once_key(p))

    def clear(rs):
        for r in rs:
            if r.get("slot") == slot:
                r["accepted_at"] = None
                r.pop("accepted_key", None)
    _rewrite(clear)
    day = dt.date.fromisoformat(p["day"])
    return {"ok": True, "reply": f"Removed {config.spoken_name(p['habit'])} from {_dayword(day, now)} {p['at']}."}


list = rows      # the spec's name (digest.list()); last line, so annotations above still see the builtin
