"""The long-running process. Owns timers, sampling, nudges, pace reminders, reels, the nightly report, and the API.

Run:  python -m alibi.daemon            (then open http://127.0.0.1:8765 or launch the island)
"""
import datetime as dt, json, os, threading, time
from . import camera, config, db, laptop_logger, nudges, verifier
from .notify import notify, recent_alerts

TICK_S = 5
_strava_synced = 0.0
_ticks = 0
_reel_threads: list[threading.Thread] = []


def tick(con) -> None:
    """One pass of everything time-based. Tests call this directly with a fake clock."""
    global _ticks
    _ticks += 1
    now = time.time()
    laptop_logger.log_once(con)                                       # free, runs always
    s = db.active_session(con)
    if s and now >= s["ends_at"]:
        _bell(con, s, now)
        s = None
    if s and s["modality"] in ("physical", "hybrid") and not db.in_break(con, s["id"], now):
        camera.maybe_sample(con, s)
    if not s or s["modality"] == "digital" or db.in_break(con, s["id"], now):
        camera.release()
    if s:
        nudges.check(con, s)
    else:
        _pace_nudge(con, now)
    _strava(con)
    if _ticks % 12 == 1:
        _reel_sweep(con)
    _nightly(con, now)


def _bell(con, s, now: float) -> None:
    """Time's up. One last look at the desk — unless the laptop slept through the bell (R4): then no camera, the
    session ends at ends_at (not wake time), and the verdict says so."""
    from . import cli
    late = now - s["ends_at"] > 2 * max(config.SAMPLE_EVERY_S, TICK_S)
    if not late and s["modality"] in ("physical", "hybrid") and not db.in_break(con, s["id"], now):
        camera.maybe_sample(con, s, force=True)
    camera.release()
    if late:
        cli.end(con, ended_at=s["ends_at"], missed=True)
        return
    with cli._lock:
        out = verifier.close(con, s)
    if out is None:
        return                                                       # someone ended it a moment ago
    done = out["session"]
    notify(f"Time's up. {out['voice']}{cli._streak_tail(con, done)}", image_path=done["evidence_path"],
           kind="verdict", session_id=done["id"], habit=done["habit"], verdict=done["verdict"],
           ratio=done["on_task_ratio"], ended_early=False, missed=False, line=out["line"],
           actions=[{"label": "Watch reel", "url": f"/api/reel?session={done['id']}"},
                    {"label": "Fix samples", "url": f"/#session-{done['id']}"},
                    {"label": f"Again {done['declared_min']}m", "say": f"{done['habit']} for {done['declared_min']} min"}])
    _reel_later(done["id"])


# --- F3: behind-pace reminders ------------------------------------------------------------------------------------

def _pace_nudge(con, now: float) -> str | None:
    d = dt.datetime.fromtimestamp(now)
    if d.hour not in config.PACE_HOURS:
        return None
    slot = f"{d:%Y-%m-%d}-{d.hour}"
    if any(a.get("kind") == "pace" and a.get("slot") == slot for a in recent_alerts(200)):
        return None
    from . import report
    r = report.build_json(now)
    rows = [x for x in r["rows"] if x["behind_by_min"] > 0]
    if not rows:
        return None
    worst = max(rows, key=lambda x: x["behind_by_min"])
    h = config.habits()["habits"].get(worst["habit"], {})
    mins = int(h.get("default_min", 25))
    pct = min(100, round(100 * mins / worst["behind_by_min"]))
    name = config.display_name(worst["habit"])
    text = f"{name}: {worst['behind_by_min']} min behind pace. {mins} min now closes {pct}% of it. Say 'yes'."
    notify(text, kind="pace", slot=slot, habit=worst["habit"], minutes=mins, behind_by_min=worst["behind_by_min"],
           actions=[{"label": f"Start {mins}m", "say": "yes"}, {"label": "Not now", "dismiss": True}])
    return text


# --- F9: Strava claims ------------------------------------------------------------------------------------------

def _strava(con) -> None:
    global _strava_synced
    if not os.getenv("STRAVA_REFRESH_TOKEN") or time.time() - _strava_synced < 3600:
        return
    _strava_synced = time.time()
    from . import strava
    try:
        new = strava.sync()
    except Exception as e:
        print(f"[alibi] strava sync failed: {e!r}", flush=True)
        return
    for r in new:
        notify(f"Strava: {r['name']}, {r['distance_km']} km — logged.", kind="info")
    check_claims(con)


def check_claims(con) -> list[str]:
    """A 'go for a run' claim is verified by a qualifying Strava run between the claim and its deadline."""
    out = []
    claims = con.execute("SELECT id, ts, payload FROM events WHERE source='user' AND kind='claim'").fetchall()
    settled = {json.loads(r["payload"]).get("claim_id") for r in
               con.execute("SELECT payload FROM events WHERE source='alibi' AND kind='claim_settled'")}
    for c in claims:
        if c["id"] in settled:
            continue
        p = json.loads(c["payload"])
        runs = [e["payload"] for e in db.events_between(con, c["ts"] - 600, p["until"], "strava")
                if e["payload"].get("distance_km", 0) >= p.get("min_km", 0)]
        if runs:
            text = f"Run verified: {runs[0]['distance_km']} km."
        elif time.time() > p["until"]:
            text = f"You said you'd run. Strava has nothing ≥{p.get('min_km', 0):g} km. Logged as claimed, not seen."
        else:
            continue
        db.add_event(con, "alibi", "claim_settled", {"claim_id": c["id"], "verified": bool(runs)})
        notify(text, kind="verdict", habit=p["habit"], verdict="done" if runs else "slacked")
        out.append(text)
    return out


# --- R5: the daemon owns reels -----------------------------------------------------------------------------------

def _reel_later(session_id: int) -> threading.Thread:
    """Build the session's memories reel off the tick thread (ffmpeg takes a few seconds)."""
    from . import reel

    def run():
        try:
            reel.session_reel(db.connect(), session_id)
        except Exception as e:
            print(f"[alibi] reel failed: {e!r}", flush=True)
    t = threading.Thread(target=run, daemon=True, name=f"reel-{session_id}")
    t.start()
    _reel_threads.append(t)
    return t


def join_reels(timeout: float = 90) -> None:
    for t in list(_reel_threads):
        t.join(timeout)


def _reel_sweep(con) -> None:
    """Any recent finished camera session without a reel (CLI exited, or a correction invalidated it) gets one."""
    from . import reel
    rows = con.execute("SELECT id FROM sessions WHERE status='done' AND modality!='digital' AND ended_at>? "
                       "ORDER BY id DESC LIMIT 10", (time.time() - 2 * 86400,)).fetchall()
    for r in rows:
        if not (reel.REELS_DIR / f"session-{r['id']}.mp4").exists() and not reel.building(f"session-{r['id']}") \
                and db.session_events(con, r["id"], "camera"):
            _reel_later(r["id"])


# --- nightly report + day recap (R8: once per day even across restarts; F10) --------------------------------------

def _nightly(con, now: float) -> None:
    d = dt.datetime.fromtimestamp(now)
    if d.hour != config.REPORT_HOUR:
        return
    today = f"{d:%Y-%m-%d}"
    if any(a.get("kind") == "report" and dt.datetime.fromtimestamp(a["ts"]).strftime("%Y-%m-%d") == today
           for a in recent_alerts(300)):
        return
    from . import report
    notify(report.build_json(now)["summary"], kind="report", day=today)
    _recap_later(today, now)


def recap(con, day: str, now: float | None = None) -> str | None:
    """'Today: 3 sessions, 74 min seen. Your reel is ready.' (+ builds the day reel)."""
    from . import reel
    d0 = dt.datetime.fromisoformat(day).timestamp()
    ss = con.execute("SELECT * FROM sessions WHERE status='done' AND started_at BETWEEN ? AND ? ORDER BY started_at",
                     (d0, d0 + 86400)).fetchall()
    if not ss:
        return None
    seen = round(sum((s["on_task_ratio"] or 0) * s["declared_min"] for s in ss))
    path = reel.day_reel(con, day)
    first = next((s["evidence_path"] for s in ss if s["evidence_path"]), None)
    text = f"Today: {len(ss)} session{'s' * (len(ss) != 1)}, {seen} min seen." + (" Your reel is ready." if path else "")
    notify(text, image_path=first, kind="recap", day=day, reel=path,
           actions=[{"label": "Play", "url": f"/api/reel?date={day}"}] if path else [])
    return text


def _recap_later(day: str, now: float) -> threading.Thread:
    def run():
        try:
            recap(db.connect(), day, now)
        except Exception as e:
            print(f"[alibi] recap failed: {e!r}", flush=True)
    t = threading.Thread(target=run, daemon=True, name="recap")
    t.start()
    _reel_threads.append(t)
    return t


def main():
    from . import api
    con = db.connect()
    api.serve_in_thread()
    notify(f"Alibi daemon up — witness: {config.VISION_BACKEND}, "
           f"dashboard: http://{config.API_HOST}:{config.API_PORT}")
    while True:
        try:
            tick(con)
        except Exception as e:                      # a long-running agent must not die on one bad tick
            print(f"[alibi] tick error: {e!r}", flush=True)
        time.sleep(TICK_S)


if __name__ == "__main__":
    main()
