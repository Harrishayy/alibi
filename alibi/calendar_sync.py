"""Apple Calendar + the plan. Three jobs (hooks.py plugin):

  PLAN      habits.yaml `schedule: [{days, at, min}]` -> one event per block in a calendar called "Alibi", 14 days ahead
  VERDICTS  after a session the matching event becomes "✓ Drawing — done 82%" (notes say what was seen, with a link)
  AUTO-START when a planned block begins and nothing is running: notify(kind="planned") -> the island drops down
            "Drawing is planned now — start?" [Start 25 min] [In 10 min] [Skip today]

Prompts work without Calendar access (they come from the schedule). Everything Calendar goes through one small
native helper (bin/alibi-calendar, or the copy inside Alibi.app so macOS asks on behalf of "Alibi"); tests point
ALIBI_CALENDAR_BIN at tests/fake_calendar.py. Helper calls run off the tick thread. State: data/calendar.json.
"""
import datetime as dt, hashlib, json, os, pathlib, subprocess, threading, time
from . import config, db
from .notify import notify

CAL_TITLE = "Alibi"
HORIZON_DAYS = 14
LATE_OK_S = 30 * 60          # after a block's end you can still be offered it for this long
MISSED_AFTER_S = 60 * 60     # a block with no session this long after its end is "didn't happen"
MATCH_BEFORE_S = 60 * 60     # a session started up to an hour early still counts for the block
RESYNC_S = 6 * 3600
DAYS = tuple(getattr(config, "DAYS", ("mon", "tue", "wed", "thu", "fri", "sat", "sun")))
DAY_WORDS = {"daily": DAYS, "every day": DAYS, "everyday": DAYS, "weekdays": DAYS[:5], "weekends": DAYS[5:],
             "weekend": DAYS[5:]}

_lock = threading.RLock()        # state file
_sync_lock = threading.Lock()    # one helper conversation at a time
_threads: list[threading.Thread] = []
_last_auto = {"sync": 0.0, "retry": 0.0, "recheck": 0.0}


class CalendarError(RuntimeError):
    pass


# --- helper -------------------------------------------------------------------------------------------------------

def helper_bin() -> str | None:
    """ALIBI_CALENDAR_BIN (tests), else the copy inside Alibi.app (access is then granted to "Alibi"), else bin/."""
    env = os.getenv("ALIBI_CALENDAR_BIN")
    if env:
        return env if os.path.exists(env) else None
    for p in (config.ROOT / "Alibi.app" / "Contents" / "MacOS" / "alibi-calendar", config.ROOT / "bin" / "alibi-calendar"):
        if p.exists():
            return str(p)
    return None


def run(cmd: str, payload: dict | None = None, timeout: float = 30) -> dict:
    exe = helper_bin()
    if not exe:
        raise CalendarError("helper_missing")
    try:
        r = subprocess.run([exe, cmd], input=json.dumps(payload or {}), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise CalendarError(f"{cmd}: timed out")
    except OSError as e:
        raise CalendarError(f"{cmd}: {e}")
    try:
        out = json.loads((r.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise CalendarError(f"{cmd}: no answer (exit {r.returncode}) {r.stderr.strip()[:120]}")
    if isinstance(out, dict) and out.get("error") and cmd != "request":
        raise CalendarError(str(out["error"]))
    return out


def auth_status() -> str:
    """full | write_only | denied | restricted | not_determined | unavailable. Read-only: never shows a prompt."""
    try:
        return run("status", timeout=10).get("auth", "unknown")
    except CalendarError:
        return "unavailable"


# --- state ----------------------------------------------------------------------------------------------------------

def _path() -> pathlib.Path:
    return config.DATA_DIR / "calendar.json"


def load() -> dict:
    with _lock:
        try:
            st = json.loads(_path().read_text())
        except (FileNotFoundError, ValueError):
            st = {}
    for k in ("events", "outcomes", "prompted", "snoozed", "skipped", "moved", "once"):
        st.setdefault(k, {})
    st.setdefault("enabled", False)
    st.setdefault("log_unplanned", True)
    return st


def save(st: dict) -> None:
    with _lock:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _path().with_suffix(".tmp")
        tmp.write_text(json.dumps(st, indent=1, sort_keys=True))
        os.replace(tmp, _path())


def update(fn) -> dict:
    with _lock:
        st = load()
        fn(st)
        save(st)
        return st


# --- the plan -------------------------------------------------------------------------------------------------------

def _days(v) -> set[int]:
    if isinstance(v, str):
        v = DAY_WORDS.get(v.strip().lower(), [x.strip() for x in v.split(",")])
    out = set()
    for d in v or []:
        d = str(d).strip().lower()[:3]
        if d in DAYS:
            out.add(DAYS.index(d))
    return out


def _hm(s) -> tuple[int, int] | None:
    try:
        h, m = str(s).strip().split(":")[:2]
        h, m = int(h), int(m)
        return (h, m) if 0 <= h < 24 and 0 <= m < 60 else None
    except (ValueError, AttributeError):
        return None


def kind_of(h: dict) -> str:
    """camera | screen | both | strava | health"""
    if h.get("source") in ("strava", "health"):
        return h["source"]
    return {"physical": "camera", "digital": "screen", "hybrid": "both"}.get(h.get("modality", ""), "camera")


def blocks(day0: dt.date, days: int = 1, cfg: dict | None = None, st: dict | None = None) -> list[dict]:
    """Every planned block from habits.yaml schedules on [day0, day0+days), with one-off moves applied, by start."""
    cfg = cfg or config.habits()
    st = st if st is not None else load()
    out = []
    for key, h in (cfg.get("habits") or {}).items():
        if not isinstance(h, dict):
            continue
        for entry in h.get("schedule") or []:
            if not isinstance(entry, dict):
                continue
            wd, hm = _days(entry.get("days")), _hm(entry.get("at"))
            if not wd or not hm:
                continue
            mins = int(entry.get("min") or h.get("default_min") or 25)
            for i in range(days):
                d = day0 + dt.timedelta(days=i)
                if d.weekday() not in wd:
                    continue
                planned_at = f"{hm[0]:02d}:{hm[1]:02d}"
                k = f"{key}@{d.isoformat()}T{planned_at}"
                at = st["moved"].get(k, planned_at)
                mh = _hm(at) or hm
                start = dt.datetime.combine(d, dt.time(*mh)).timestamp()
                out.append({"key": k, "habit": key, "label": config.display_name(key, cfg), "date": d.isoformat(),
                            "at": f"{mh[0]:02d}:{mh[1]:02d}", "planned_at": planned_at, "min": mins,
                            "start": start, "end": start + mins * 60, "moved": k in st["moved"],
                            "check": kind_of(h), "calendar": h.get("calendar", True) is not False})
    # one-off blocks (add_once: an accepted night replan), keyed like scheduled ones so move/skip/prompt/sync just work
    for k, o in st["once"].items():
        h = (cfg.get("habits") or {}).get(o.get("habit"))
        hm = _hm(o.get("at"))
        try:
            d = dt.date.fromisoformat(str(o.get("date")))
        except ValueError:
            continue
        if not isinstance(h, dict) or not hm or not (day0 <= d < day0 + dt.timedelta(days=days)):
            continue
        mh = _hm(st["moved"].get(k, o["at"])) or hm
        mins = int(o.get("min") or h.get("default_min") or 25)
        start = dt.datetime.combine(d, dt.time(*mh)).timestamp()
        out.append({"key": k, "habit": o["habit"], "label": config.display_name(o["habit"], cfg), "date": d.isoformat(),
                    "at": f"{mh[0]:02d}:{mh[1]:02d}", "planned_at": f"{hm[0]:02d}:{hm[1]:02d}", "min": mins,
                    "start": start, "end": start + mins * 60, "moved": k in st["moved"], "once": True,
                    "check": kind_of(h), "calendar": h.get("calendar", True) is not False})
    # two entries producing the same key (duplicate schedule rows) collapse to one
    seen, uniq = set(), []
    for b in sorted(out, key=lambda b: (b["start"], b["habit"])):
        if b["key"] not in seen:
            seen.add(b["key"])
            uniq.append(b)
    return uniq


def upcoming(now: float, cfg: dict | None = None, st: dict | None = None) -> list[dict]:
    """Blocks the calendar should show as planned: not over yet, within 14 days, not skipped or already answered."""
    st = st if st is not None else load()
    return [b for b in blocks(dt.date.fromtimestamp(now) - dt.timedelta(days=1), HORIZON_DAYS + 2, cfg, st)
            if b["calendar"] and b["end"] > now and b["start"] < now + HORIZON_DAYS * 86400
            and b["key"] not in st["skipped"] and b["key"] not in st["outcomes"]]


def _sched_hash(cfg: dict) -> str:
    sch = {k: [h.get("schedule"), h.get("calendar", True), h.get("label"), h.get("display")]
           for k, h in (cfg.get("habits") or {}).items() if isinstance(h, dict) and h.get("schedule")}
    return hashlib.sha1(json.dumps(sch, sort_keys=True, default=str).encode()).hexdigest()[:12]


def match_session(con, b: dict):
    """The session that answers this block: same habit, started between an hour early and LATE_OK_S after its end."""
    rows = con.execute("SELECT * FROM sessions WHERE habit=? AND started_at BETWEEN ? AND ? ORDER BY started_at",
                       (b["habit"], b["start"] - MATCH_BEFORE_S, b["end"] + LATE_OK_S)).fetchall()
    return min(rows, key=lambda r: abs(r["started_at"] - b["start"])) if rows else None


def block_for_session(con, s, cfg: dict | None = None, st: dict | None = None) -> dict | None:
    day = dt.date.fromtimestamp(s["started_at"])
    cands = [b for b in blocks(day - dt.timedelta(days=1), 3, cfg, st) if b["habit"] == s["habit"]
             and b["start"] - MATCH_BEFORE_S <= s["started_at"] <= b["end"] + LATE_OK_S]
    return min(cands, key=lambda b: abs(b["start"] - s["started_at"])) if cands else None


def _source_result(con, b: dict, h: dict) -> dict | None:
    """Strava / Apple Health blocks are answered by data, not a session. None = no answer yet."""
    if b["check"] == "strava":
        d0 = dt.datetime.fromisoformat(b["date"]).timestamp()
        runs = [e["payload"] for e in db.events_between(con, d0, d0 + 86400, "strava")
                if e["kind"] == "activity" and (e["payload"].get("distance_km") or 0) >= float(h.get("min_km", 0) or 0)]
        if runs:
            return {"state": "done", "detail": f"{runs[-1].get('distance_km')} km on Strava"}
    elif b["check"] == "health":
        d0 = dt.datetime.fromisoformat(b["date"]).timestamp()
        metric, target = h.get("metric"), h.get("daily_target")
        sam = [e["payload"] for e in db.events_between(con, d0 - 86400, d0 + 4 * 86400, "health")
               if e["kind"] == "samples" and e["payload"].get("date") == b["date"]]
        v = sam[-1].get(metric) if sam and metric else None          # latest wins
        try:
            if v is not None and target is not None and float(v) >= float(target):
                fmt = getattr(config, "HEALTH_METRICS", {}).get(metric, (None, None, None, "{v:g} " + metric))[3]
                return {"state": "done", "detail": fmt.format(v=float(v))}
        except (TypeError, ValueError):
            pass
    return None


def _no_data_reason(con, b: dict, h: dict) -> str | None:
    """Why Alibi can't judge a Strava/Health block (so it must not say "didn't happen"), or None if it can."""
    d_end = dt.datetime.fromisoformat(b["date"]).timestamp() + 86400
    if b["check"] == "strava":
        from . import strava
        if not strava.connected():
            return "no Strava data"
        if (strava.state().get("last_sync") or 0) < d_end:
            return "no Strava data"      # connected, but nothing checked since that day ended
        return None
    metric = h.get("metric")
    sam = [e["payload"] for e in db.events_between(con, d_end - 2 * 86400, d_end + 4 * 86400, "health")
           if e["kind"] == "samples" and e["payload"].get("date") == b["date"]]
    if not sam or not metric or sam[-1].get(metric) is None:
        return "no data from iPhone"
    return None


def plan(con, day0: dt.date | None = None, days: int = 1, now: float | None = None) -> list[dict]:
    """Blocks with a state: planned | now | live | done | partial | slacked | missed | skipped | waiting (+ session)."""
    now = now or time.time()
    day0 = day0 or dt.date.fromtimestamp(now)
    st, cfg = load(), config.habits()
    out = []
    for b in blocks(day0, days, cfg, st):
        h = cfg["habits"].get(b["habit"], {})
        b = dict(b, state="planned", session_id=None, verdict=None, ratio=None, detail=None,
                 in_calendar=b["key"] in st["events"], snoozed_until=st["snoozed"].get(b["key"]))
        s = match_session(con, b) if b["check"] not in ("strava", "health") else None
        src = _source_result(con, b, h) if b["check"] in ("strava", "health") else None
        oc = st["outcomes"].get(b["key"], {})
        if b["key"] in st["skipped"]:
            b["state"] = "skipped"
        elif s is not None:
            b.update(session_id=s["id"], verdict=s["verdict"], ratio=s["on_task_ratio"],
                     state="live" if s["status"] == "active" else (s["verdict"] or "done"))
        elif src:
            b.update(state=src["state"], verdict="done", detail=src["detail"])
        elif oc.get("state") == "missed":
            b["state"] = "missed"
        elif oc.get("state") == "unknown":
            b.update(state="nodata",
                     detail="no Strava data" if b["check"] == "strava" else "no data from iPhone")
        elif b["check"] in ("strava", "health") and now >= b["end"]:
            b["state"] = "waiting"       # Strava/Health data usually lands later; decided the next morning
        elif now >= b["end"] + MISSED_AFTER_S:
            b["state"] = "missed"
        elif now >= b["start"]:
            b["state"] = "now" if now < b["end"] + LATE_OK_S else "missed"
        out.append(b)
    return out


# --- what the calendar says -------------------------------------------------------------------------------------

def dashboard() -> str:
    return f"http://127.0.0.1:{config.API_PORT}"


CHECK_WORDS = {"camera": "your desk camera", "screen": "what's on your screen", "both": "your desk camera and screen",
               "strava": "Strava", "health": "Apple Health"}
MARK = {"done": "✓", "partial": "◐", "slacked": "✗", "missed": "✗", "skipped": "–", "live": "●", "unknown": "?"}


def _t(ts: float) -> str:
    return time.strftime("%H:%M", time.localtime(ts))


def render_planned(b: dict) -> dict:
    how = CHECK_WORDS.get(b["check"], "Alibi")
    if b["check"] in ("strava", "health"):
        after = f"Afterwards Alibi checks {how} and marks this event with what actually happened."
    else:
        after = (f"When it starts, Alibi asks if you're ready (at the top of your screen). It checks with {how}, "
                 "then marks this event with what actually happened.")
    return {"title": f"{b['label']} · {b['min']} min", "start": b["start"], "end": b["end"],
            "notes": f"Planned in Alibi.\n{after}", "url": f"{dashboard()}/#plan"}


def render_outcome(b: dict | None, s=None, state: str | None = None, detail: str | None = None) -> dict:
    """'✓ Drawing — done 82%' / '◐ … partial 55%' / '✗ … slacked 12%' / '✗ … didn't happen' / '– … skipped'."""
    label = config.display_name(s["habit"]) if s is not None else b["label"]
    lines = []
    if b:
        lines.append(f"Planned {_t(b['start'])}–{_t(b['end'])}.")
    if s is not None:
        state = state or s["verdict"] or "done"
        pct = round((s["on_task_ratio"] or 0) * 100)
        title = f"{MARK.get(state, '✓')} {label} — {state} {pct}%" if state != "live" else f"● {label} — in progress"
        if state == "live":
            lines.append(f"Started at {_t(s['started_at'])}. Alibi is checking it now.")
        else:
            seen = round((s["on_task_ratio"] or 0) * s["declared_min"])
            how = CHECK_WORDS.get({"physical": "camera", "digital": "screen", "hybrid": "both"}.get(s["modality"], ""),
                                  "Alibi")
            lines.append(f"You started at {_t(s['started_at'])} and stopped at {_t(s['ended_at'] or s['ends_at'])}.")
            lines.append(f"On task {pct}% of the time — about {seen} of {s['declared_min']} minutes, seen by {how}.")
            lines.append({"done": "That counts as done.", "partial": "That counts as partly done.",
                          "slacked": "That doesn't count this time."}.get(state, ""))
        url = f"{dashboard()}/#session-{s['id']}"
        start, end = (b["start"], b["end"]) if b else (s["started_at"], s["ended_at"] or s["ends_at"])
        if state != "live":
            lines.append(f"\nSee the photos and the timelapse: {url}")
    else:
        src = "Strava" if b.get("check") == "strava" else "your iPhone"
        title = {"missed": f"✗ {label} — didn't happen", "skipped": f"– {label} — skipped",
                 "unknown": f"? {label} — {detail or 'no data'}",
                 "done": f"✓ {label} — done" + (f" ({detail})" if detail else "")}.get(state, f"{label}")
        missed_line = {"strava": "Strava was checked after that day, and no run long enough showed up.",
                       "health": "Your iPhone sent that day's numbers, and they fell short."}.get(
            b.get("check"), "Alibi didn't see a session for this one.")
        lines.append({"missed": missed_line, "skipped": "You skipped this one.",
                      "unknown": f"Alibi got nothing from {src} for this day, so it can't say. "
                                 "This doesn't count against you.",
                      "done": f"Confirmed: {detail}." if detail else "Confirmed."}.get(state, ""))
        url = f"{dashboard()}/#plan"
        start, end = b["start"], b["end"]
    return {"title": title, "start": start, "end": end, "notes": "\n".join(x for x in lines if x is not None).strip(),
            "url": url}


# --- talking to Calendar ----------------------------------------------------------------------------------------

def _bg(fn, *args) -> threading.Thread:
    def go():
        try:
            fn(*args)
        except Exception as e:
            print(f"[alibi] calendar: {e!r}", flush=True)
    t = threading.Thread(target=go, daemon=True, name="alibi-calendar")
    t.start()
    _threads[:] = [x for x in _threads if x.is_alive()] + [t]
    return t


def join(timeout: float = 30) -> None:
    for t in list(_threads):
        t.join(timeout)


def _ensure(st: dict) -> str:
    cal = run("ensure", {"title": CAL_TITLE, "id": st.get("calendar_id")})
    if cal.get("id") != st.get("calendar_id"):
        update(lambda x: x.update(calendar_id=cal["id"], calendar_source=cal.get("source", "")))
    return cal["id"]


def _apply(cal_id: str, ops: list[dict]) -> list[dict]:
    if not ops:
        return []
    return run("apply", {"calendar_id": cal_id, "ops": ops}, timeout=60).get("results", [])


def connect() -> dict:
    """Ask macOS for Calendar access (the only call that can show a prompt), make the "Alibi" calendar, sync."""
    if not helper_bin():
        return {"ok": False, "auth": "unavailable", "reason": "helper_missing"}
    auth = auth_status()
    if auth in ("not_determined", "write_only"):
        try:
            auth = run("request", timeout=200).get("auth", auth)
        except CalendarError as e:
            update(lambda st: st.update(last_error=str(e)))
            return {"ok": False, "auth": auth_status(), "reason": str(e)}
    if auth != "full":
        update(lambda st: st.update(enabled=False, last_error=f"access: {auth}"))
        return {"ok": False, "auth": auth, "reason": "no_access"}
    update(lambda st: st.update(enabled=True, connected_at=st.get("connected_at") or time.time(), last_error=None))
    res = sync(force=True)
    return {"ok": res.get("ok", False), "auth": auth, "sync": res}


def disconnect(remove_future: bool = False) -> dict:
    st = load()
    removed = 0
    if remove_future and st.get("calendar_id"):
        try:
            now = time.time()
            with _sync_lock:
                listed = run("list", {"calendar_id": st["calendar_id"], "from": now,
                                      "to": now + (HORIZON_DAYS + 1) * 86400}).get("events", [])
                ops = [{"op": "delete", "ref": e["id"], "id": e["id"]} for e in listed
                       if "/#plan" in (e.get("url") or "") and e["start"] >= now]
                _apply(st["calendar_id"], ops)
                removed = len(ops)
        except CalendarError as e:
            return {"ok": False, "reason": str(e)}
    def off(x):
        x["enabled"] = False
        if remove_future:
            x["events"] = {k: v for k, v in x["events"].items() if k in x["outcomes"]}
    update(off)
    return {"ok": True, "removed": removed}


def sync(force: bool = False) -> dict:
    """Make the next 14 days of the "Alibi" calendar match the schedule; push verdicts the calendar hasn't got yet.
    Only touches events Alibi made (url ends /#plan) that haven't started; past events and your own events stay."""
    st = load()
    if not st.get("enabled"):
        return {"ok": False, "reason": "off"}
    if not _sync_lock.acquire(timeout=0 if not force else 60):
        return {"ok": False, "reason": "busy"}
    try:
        cfg = config.habits()
        now = time.time()
        try:
            cal_id = _ensure(st)
            listed = run("list", {"calendar_id": cal_id, "from": now - 86400, "to": now + (HORIZON_DAYS + 1) * 86400}
                         ).get("events", [])
        except CalendarError as e:
            update(lambda x: x.update(last_error=str(e), last_try=now))
            return {"ok": False, "reason": str(e)}
        st = load()
        by_id = {e["id"]: e for e in listed}
        con = db.connect()
        want = [b for b in upcoming(now, cfg, st) if b["start"] > now or match_session(con, b) is None]
        ops, used, counts = [], set(), {"created": 0, "updated": 0, "deleted": 0, "kept": 0}
        for b in want:
            ev = render_planned(b)
            eid = st["events"].get(b["key"])
            cur = by_id.get(eid) if eid else None
            if cur is None:          # lost our id (new install, restored data): adopt an identical event we made
                cur = next((e for e in listed if e["id"] not in used and "/#plan" in (e.get("url") or "")
                            and abs(e["start"] - ev["start"]) < 1 and e["title"] == ev["title"]), None)
            if cur is not None:
                used.add(cur["id"])
                same = (cur["title"] == ev["title"] and abs(cur["start"] - ev["start"]) < 1
                        and abs(cur["end"] - ev["end"]) < 1 and (cur.get("notes") or "") == ev["notes"])
                if same:
                    counts["kept"] += 1
                    st["events"][b["key"]] = cur["id"]
                    continue
                ops.append({"op": "upsert", "ref": b["key"], "id": cur["id"], **ev})
                counts["updated"] += 1
            else:
                ops.append({"op": "upsert", "ref": b["key"], **ev})
                counts["created"] += 1
        outcome_ids = {o.get("event_id") for o in st["outcomes"].values()}
        for e in listed:
            if e["id"] not in used and "/#plan" in (e.get("url") or "") and e["start"] >= now \
                    and e["id"] not in outcome_ids and e["id"] not in {st["events"].get(k) for k in st["skipped"]}:
                ops.append({"op": "delete", "ref": "del:" + e["id"], "id": e["id"]})
                counts["deleted"] += 1
        # verdicts that never reached the calendar (helper failed, or Calendar was connected later)
        for k, oc in st["outcomes"].items():
            if not oc.get("synced") and oc.get("event"):
                ops.append({"op": "upsert", "ref": "oc:" + k, "id": oc.get("event_id") or st["events"].get(k),
                            **oc["event"]})
        try:
            results = _apply(cal_id, ops)
        except CalendarError as e:
            update(lambda x: x.update(last_error=str(e), last_try=now))
            return {"ok": False, "reason": str(e)}
        errors = [r for r in results if not r.get("ok")]

        def merge(x):
            x["events"].update({k: v for k, v in st["events"].items()})
            for r in results:
                ref = r.get("ref", "")
                if not r.get("ok"):
                    continue
                if ref.startswith("del:"):
                    x["events"] = {k: v for k, v in x["events"].items() if v != ref[4:]}
                elif ref.startswith("oc:"):
                    k = ref[3:]
                    if k in x["outcomes"]:
                        x["outcomes"][k].update(synced=True, event_id=r["id"])
                        if not k.startswith("session-"):
                            x["events"][k] = r["id"]
                else:
                    x["events"][ref] = r["id"]
            x.update(last_sync=now, last_try=now, sched_hash=_sched_hash(cfg), calendar_id=cal_id,
                     last_error=errors[0].get("error") if errors else None,
                     upcoming=len(want), synced_day=dt.date.fromtimestamp(now).isoformat())
        update(merge)
        return {"ok": not errors, **counts, "errors": len(errors), "upcoming": len(want)}
    finally:
        _sync_lock.release()


def _record(key: str, ev: dict, state: str, **extra) -> None:
    """Remember an outcome (so the plan sync never overwrites it) and push it to Calendar if connected."""
    update(lambda st: st["outcomes"].__setitem__(key, {**st["outcomes"].get(key, {}), "state": state, "event": ev,
                                                       "synced": False, "at": time.time(), **extra}))
    if load().get("enabled"):
        _bg(_push_outcome, key)


def _push_outcome(key: str) -> None:
    with _sync_lock:
        st = load()
        oc = st["outcomes"].get(key)
        if not oc or not st.get("enabled"):
            return
        try:
            cal_id = _ensure(st)
            res = _apply(cal_id, [{"op": "upsert", "ref": key, "id": oc.get("event_id") or st["events"].get(key),
                                   **oc["event"]}])
        except CalendarError as e:
            update(lambda x: x.update(last_error=str(e), last_try=time.time()))
            return
        r = res[0] if res else {}

        def done(x):
            if r.get("ok") and key in x["outcomes"]:
                x["outcomes"][key].update(synced=True, event_id=r["id"])
                if not key.startswith("session-"):
                    x["events"][key] = r["id"]
            elif not r.get("ok"):
                x["last_error"] = r.get("error", "calendar update failed")
        update(done)


# --- plugin hooks -----------------------------------------------------------------------------------------------

def start(con) -> None:
    def first(st):
        st.setdefault("since", time.time())
    update(first)


def on_session_start(con, s) -> None:
    b = block_for_session(con, s)
    if not b:
        return
    update(lambda st: (st["prompted"].__setitem__(b["key"], time.time()), st["snoozed"].pop(b["key"], None)))
    st = load()
    if st.get("enabled") and b["calendar"] and b["key"] in st["events"]:
        ev = render_outcome(b, s, state="live")
        def go():
            with _sync_lock:
                try:
                    _apply(_ensure(load()), [{"op": "upsert", "ref": b["key"], "id": load()["events"].get(b["key"]),
                                              **ev}])
                except CalendarError as e:
                    update(lambda x: x.update(last_error=str(e)))
        _bg(go)


def on_verdict(con, s) -> None:
    if s is None or not s["verdict"]:
        return
    st = load()
    b = block_for_session(con, s, st=st)
    if b and b["calendar"]:
        _record(b["key"], render_outcome(b, s), s["verdict"], session_id=s["id"], ratio=s["on_task_ratio"])
    elif not b and st.get("log_unplanned", True):
        _record(f"session-{s['id']}", render_outcome(None, s), s["verdict"], session_id=s["id"],
                ratio=s["on_task_ratio"])


def skip(key: str) -> dict:
    b = _find(key)
    if not b:
        raise LookupError("No planned session with that key.")
    update(lambda st: (st["skipped"].__setitem__(key, time.time()), st["snoozed"].pop(key, None)))
    if b["calendar"]:
        _record(key, render_outcome(b, state="skipped"), "skipped")
    return b


def unskip(key: str) -> None:
    def go(st):
        st["skipped"].pop(key, None)
        if st["outcomes"].get(key, {}).get("state") == "skipped":
            st["outcomes"].pop(key)
    update(go)
    if load().get("enabled"):
        _bg(sync, True)


def snooze(key: str, minutes: int = 10) -> dict:
    b = _find(key)
    if not b:
        raise LookupError("No planned session with that key.")
    until = time.time() + max(1, min(int(minutes), 180)) * 60
    update(lambda st: st["snoozed"].__setitem__(key, until))
    return dict(b, snoozed_until=until)


def move(key: str, at: str) -> dict:
    """Move one occurrence to another time the same day (Today strip 'Move'). The calendar event follows."""
    hm = _hm(at)
    if not hm:
        raise ValueError("Use a time like 19:30.")
    b = _find(key)
    if not b:
        raise LookupError("No planned session with that key.")
    at = f"{hm[0]:02d}:{hm[1]:02d}"
    def go(st):
        if at == b["planned_at"]:
            st["moved"].pop(key, None)
        else:
            st["moved"][key] = at
        st["prompted"].pop(key, None)
        st["snoozed"].pop(key, None)
    update(go)
    if load().get("enabled"):
        _bg(sync, True)
    return _find(key)


def add_once(habit: str, date: str, at: str, minutes: int) -> dict:
    """One extra planned block on one day (an accepted night replan; `move` only works within a day). Stored next to
    the moved/skipped overrides; the calendar event follows on the next sync when Calendar is connected."""
    cfg = config.habits()
    if habit not in (cfg.get("habits") or {}):
        raise LookupError(f"No habit called {habit}.")
    hm = _hm(at)
    if not hm:
        raise ValueError("Use a time like 07:30.")
    d = dt.date.fromisoformat(str(date)[:10])
    at = f"{hm[0]:02d}:{hm[1]:02d}"
    key = f"{habit}@{d.isoformat()}T{at}"
    m = max(1, int(minutes))
    update(lambda st: (st["once"].__setitem__(key, {"habit": habit, "date": d.isoformat(), "at": at, "min": m,
                                                     "added_at": time.time()}),
                       st["skipped"].pop(key, None)))
    if load().get("enabled"):
        _bg(sync, True)
    return _find(key)


def remove_once(key: str) -> dict | None:
    """Undo add_once: forget the one-off block and its overrides. The calendar event goes on the next sync (it deletes
    future /#plan events nothing wants), best effort like move/unskip. -> the removed entry, or None if there wasn't one."""
    gone = {}

    def go(st):
        gone["o"] = st["once"].pop(key, None)
        for k in ("moved", "prompted", "snoozed", "skipped"):
            st[k].pop(key, None)
    update(go)
    if gone["o"] is not None and load().get("enabled"):
        _bg(sync, True)
    return gone["o"]


def _find(key: str) -> dict | None:
    try:
        d = dt.date.fromisoformat(key.split("@", 1)[1][:10])
    except (IndexError, ValueError):
        return None
    return next((b for b in blocks(d, 1) if b["key"] == key), None)


def _prompt(b: dict, now: float, h: dict) -> None:
    late = now - b["start"] > 120
    name, k, m = b["label"], b["key"], b["min"]
    later = {"label": "In 10 min", "post": "/api/calendar/plan/snooze", "body": {"key": k, "min": 10}, "dismiss": True}
    skip_a = {"label": "Skip today", "post": "/api/calendar/plan/skip", "body": {"key": k}, "dismiss": True}
    if b["check"] == "health":
        text = (f"{name} is planned now." if not late else f"{name} was planned for {b['at']}.") + \
               " Apple Health will confirm it tonight."
        actions = [{"label": "OK", "dismiss": True}, skip_a]
    elif b["check"] == "strava":
        text = f"{name} is planned now — heading out?" if not late else f"{name} was planned for {b['at']} — still going?"
        actions = [{"label": "I'm going", "say": f"{b['habit']} for {m} minutes"}, later, skip_a]
    else:
        text = f"{name} is planned now — start?" if not late else f"{name} was planned for {b['at']} — start now?"
        actions = [{"label": f"Start {m} min", "say": f"{b['habit']} for {m} minutes"}, later, skip_a]
    notify(text, kind="planned", habit=b["habit"], habit_label=name, minutes=m, block_key=k, start=b["start"],
           end=b["end"], at=b["at"], late=late, check=b["check"], actions=actions)


def tick(con, now: float) -> None:
    st = load()
    cfg = config.habits()
    today = dt.date.fromtimestamp(now)
    active = db.active_session(con)
    since = st.get("since", now)
    prompted_any = False
    for b in blocks(today - dt.timedelta(days=1), 2, cfg, st):
        k = b["key"]
        if k in st["skipped"] or (k in st["outcomes"] and st["outcomes"][k].get("state") != "unknown"):
            continue     # "no data" stays open: late Strava/iPhone data can still settle it
        h = cfg["habits"].get(b["habit"], {})
        # --- missed: nothing seen an hour after the block ended (and it was planned while Alibi was running)
        if now >= b["end"] + MISSED_AFTER_S:
            if b["end"] < since:
                continue
            if b["check"] in ("strava", "health"):
                src = _source_result(con, b, h)
                if src:
                    if b["calendar"]:
                        _record(k, render_outcome(b, state="done", detail=src["detail"]), "done")
                    else:
                        update(lambda x: x["outcomes"].__setitem__(k, {"state": "done", "synced": True}))
                    continue
                if now < dt.datetime.fromisoformat(b["date"]).timestamp() + 86400 + 6 * 3600:
                    continue     # Health/Strava data lands overnight: decide the next morning
                why = _no_data_reason(con, b, h)
                if why:          # Alibi couldn't see it at all: say so, never "didn't happen"
                    if st["outcomes"].get(k, {}).get("state") == "unknown":
                        continue
                    if b["calendar"]:
                        _record(k, render_outcome(b, state="unknown", detail=why), "unknown")
                    else:
                        update(lambda x: x["outcomes"].__setitem__(k, {"state": "unknown", "synced": True}))
                    continue
            elif match_session(con, b) is not None:
                continue         # a session answered it; on_verdict records that
            if b["calendar"]:
                _record(k, render_outcome(b, state="missed"), "missed")
            else:
                update(lambda x: x["outcomes"].__setitem__(k, {"state": "missed", "synced": True}))
            continue
        # --- auto-start: the block has begun, nothing is running, not yet asked (or a snooze ran out)
        if prompted_any or not (b["start"] <= now < b["end"] + LATE_OK_S):
            continue
        if active is not None:
            continue                 # never interrupt a live session; it'll be offered when that ends, if still in time
        if b["check"] not in ("strava", "health") and match_session(con, b) is not None:
            continue
        if b["check"] in ("strava", "health") and _source_result(con, b, h):
            continue
        asked, snz = st["prompted"].get(k), st["snoozed"].get(k)
        if asked and not (snz and now >= snz and asked < snz):
            continue
        if snz and now < snz:
            continue
        _prompt(b, now, h)
        prompted_any = True          # one drop-down at a time
        update(lambda x: x["prompted"].__setitem__(k, now))
    _housekeeping(con, now, st, cfg)


def _housekeeping(con, now: float, st: dict, cfg: dict) -> None:
    """Background calendar sync when the schedule changed / a new day / every 6 h; re-push edited verdicts; prune."""
    if not st.get("enabled"):
        return
    busy = any(t.is_alive() for t in _threads)
    changed = st.get("sched_hash") != _sched_hash(cfg) or st.get("synced_day") != dt.date.fromtimestamp(now).isoformat()
    stale = now - (st.get("last_sync") or 0) > RESYNC_S
    pending = any(not o.get("synced") and o.get("event") for o in st["outcomes"].values())
    failed_recently = st.get("last_error") and now - (st.get("last_try") or 0) < 300
    if not busy and (changed or stale or pending) and not failed_recently and now - _last_auto["sync"] > 20:
        _last_auto["sync"] = now
        _bg(sync)
    # a correction re-scores a session after on_verdict ran: keep the calendar's verdict honest
    if now - _last_auto["recheck"] > 60:
        _last_auto["recheck"] = now
        for k, o in list(st["outcomes"].items()):
            sid = o.get("session_id")
            if not sid or now - o.get("at", now) > 3 * 86400:
                continue
            s = db.get_session(con, sid)
            if s and s["status"] == "done" and (s["verdict"] != o.get("state") or
                                                 abs((s["on_task_ratio"] or 0) - (o.get("ratio") or 0)) > 0.005):
                b = None if k.startswith("session-") else _find(k)
                _record(k, render_outcome(b, s), s["verdict"], session_id=sid, ratio=s["on_task_ratio"])
    # forget prompts/snoozes older than a few days so calendar.json doesn't grow forever
    if st["prompted"] and min(st["prompted"].values()) < now - 4 * 86400:
        def prune(x):
            for d in ("prompted", "snoozed", "skipped"):
                x[d] = {k: v for k, v in x[d].items() if v >= now - 4 * 86400}
        update(prune)


# --- what the Setup screen says -----------------------------------------------------------------------------------

SETTINGS_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_Calendars"


def status(con=None, check_auth: bool = True) -> dict:
    st = load()
    exe = helper_bin()
    auth = auth_status() if (exe and check_auth) else ("unavailable" if not exe else "unknown")
    cfg = config.habits()
    now = time.time()
    up = upcoming(now, cfg, st)
    scheduled = any((h or {}).get("schedule") for h in (cfg.get("habits") or {}).values() if isinstance(h, dict))
    connected = bool(st.get("enabled") and auth == "full")
    action = None
    if not exe:
        msg = "Calendar support isn't installed on this Mac yet. Run Alibi's setup again to add it."
    elif auth == "denied":
        msg = ("Alibi isn't allowed to use Calendar. Open System Settings › Privacy & Security › Calendars "
               "and switch on Alibi.")
        action = {"label": "Open System Settings", "post": "/api/calendar/open-settings"}
    elif auth == "restricted":
        msg = "Calendar access is blocked on this Mac (often by a work or school profile)."
    elif auth == "write_only":
        msg = ("Alibi can add events but can't update them afterwards. In System Settings › Privacy & Security › "
               "Calendars, set Alibi to Full Access.")
        action = {"label": "Open System Settings", "post": "/api/calendar/open-settings"}
    elif not connected:
        msg = ("Put your plan in Apple Calendar? Alibi makes its own calendar called “Alibi” and only ever "
               "touches that one. Afterwards, each event shows what actually happened.")
        action = {"label": "Add to Apple Calendar", "post": "/api/calendar/connect"}
    elif not scheduled:
        msg = ("Connected. Give a habit some days and a time, and it'll appear in the “Alibi” calendar.")
    elif st.get("last_error") and not st.get("last_sync"):
        msg = "Connected, but the first sync didn't go through. Try again."
        action = {"label": "Try again", "post": "/api/calendar/sync"}
    else:
        n = len(up)
        msg = (f"Your plan is in the “Alibi” calendar — {n} session{'s' * (n != 1)} in the next two weeks. "
               "After each one, the event shows what actually happened.")
        action = {"label": "Sync now", "post": "/api/calendar/sync"}
    ls = st.get("last_sync")
    return {
        "available": bool(exe), "permission": auth, "connected": connected, "enabled": bool(st.get("enabled")),
        "calendar_name": CAL_TITLE, "upcoming": len(up) if connected else 0, "scheduled": scheduled,
        "planned_next_14d": len(up), "log_unplanned": st.get("log_unplanned", True),
        "last_sync": ls, "last_sync_text": _ago(now - ls) if ls else None,
        "ok": connected and not st.get("last_error"), "message": msg, "action": action,
        "details": {"helper": exe, "permission": auth, "calendar_id": st.get("calendar_id"),
                    "calendar_account": st.get("calendar_source"), "last_error": st.get("last_error"),
                    "events_tracked": len(st["events"]), "outcomes": len(st["outcomes"])},
    }


def _ago(s: float) -> str:
    s = max(0, int(s))
    return "just now" if s < 60 else f"{s // 60} min ago" if s < 3600 else f"{s // 3600} h ago" if s < 86400 \
        else f"{s // 86400} d ago"
