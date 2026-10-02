"""Week Gantt data, mounted by api.py through hooks.routers(). Pure arithmetic, no model.

GET /api/plan/overview?week=YYYY-MM-DD   any date in the week (default: this week). One row per habit (planned blocks,
                                         verified sessions, pace status) plus milestones from DATA_DIR/goals.json.
"""
import datetime as dt, json, time
from fastapi import APIRouter, HTTPException
from . import calendar_sync, config, db, report

router = APIRouter()

BLOCK_STATES = {"done": "done", "partial": "partial", "slacked": "slacked", "missed": "missed", "skipped": "missed"}


def _block_state(b: dict) -> str:
    """planned | done | partial | slacked | missed. Live, waiting and no-data blocks are still 'planned'."""
    return BLOCK_STATES.get(b.get("state"), "planned")


def milestones(now: float) -> list[dict]:
    """Manual milestones from goals.json: a list, or {"milestones": [...]}. Missing or unreadable file -> []."""
    try:
        raw = json.loads((config.DATA_DIR / "goals.json").read_text())
    except (FileNotFoundError, ValueError):
        return []
    items = raw.get("milestones", raw.get("goals", [])) if isinstance(raw, dict) else raw
    today = dt.date.fromtimestamp(now)
    out = []
    for m in items if isinstance(items, list) else []:
        if not isinstance(m, dict):
            continue
        due = None
        try:
            due = dt.date.fromisoformat(str(m.get("due"))[:10]) if m.get("due") else None
        except ValueError:
            pass
        if m.get("done_at"):
            st = "done"
        elif due is None:
            st = "pending"
        elif today > due:
            st = "off_track"
        elif (due - today).days <= 1:
            st = "at_risk"
        else:
            st = "pending"
        out.append({"key": m.get("key"), "label": m.get("label") or m.get("key"), "due": m.get("due"),
                    "done_at": m.get("done_at"), "status": st})
    return out


def overview(week: str | None = None, now: float | None = None) -> dict:
    now = now or time.time()
    try:
        day = dt.date.fromisoformat(week) if week else dt.date.fromtimestamp(now)
    except ValueError:
        raise HTTPException(400, "week must look like 2026-09-28.")
    t0 = report.week_start(dt.datetime(day.year, day.month, day.day, 12).timestamp())
    t1 = t0 + 7 * 86400
    at = min(max(now, t0), t1)                      # a past week is judged at its end, a future one at its start
    live = t0 <= now < t1
    con, cfg = db.connect(), config.habits()
    plan = calendar_sync.plan(con, dt.date.fromtimestamp(t0), 7, now)
    rows = []
    for key, h in (cfg.get("habits") or {}).items():
        if not isinstance(h, dict) or h.get("source") == "health":
            continue                                # daily health targets have no weekly pace
        if report.is_count(h):
            from . import strava
            runs = strava.latest_runs(con, t0, min(t1, now))
            mk = float(h.get("min_km", 0) or 0)
            sessions = [{"id": r.get("id"), "start": r.get("start_date"),
                         "end": (r.get("start_date") or 0) + (r.get("moving_min") or 0) * 60,
                         "verdict": "done" if (r.get("distance_km") or 0) >= mk else "partial", "ratio": None}
                        for r in runs]
            verified = sum(s["verdict"] == "done" for s in sessions)
            q90 = 0.0
        else:
            ss = con.execute("SELECT * FROM sessions WHERE habit=? AND started_at>=? AND started_at<? "
                             "ORDER BY started_at", (key, t0, t1)).fetchall()
            sessions = [{"id": s["id"], "start": s["started_at"], "end": s["ended_at"] or s["ends_at"],
                         "verdict": s["verdict"], "ratio": s["on_task_ratio"]} for s in ss]
            verified = sum(s["declared_min"] * (s["on_task_ratio"] or 0) for s in ss
                           if s["status"] == "done" and (s["ended_at"] or 0) <= at)
            q90 = report._q90_daily(con, key, at)
        p = report.pace3(h, t0, at, verified, stale=live and report._stale(con, h, now), q90=q90,
                         stale_source=h.get("source"))
        target = h.get("weekly_sessions", 0) if report.is_count(h) else report._pace(h, t0, at)["target"]
        rows.append({"habit": key, "label": config.display_name(key, cfg), "unit": p["unit"],
                     "target_min": target, "verified_min": round(verified, 1) if p["unit"] == "runs" else round(verified),
                     "pace_min": p["pace_min"], "status3": p["status3"], "buffer_days": p["buffer_days"],
                     "need_per_day_min": p["need_per_day_min"], "reason": p["reason"],
                     "blocks": [{"start": b["start"], "end": b["end"], "state": _block_state(b), "key": b["key"]}
                                for b in plan if b["habit"] == key],
                     "sessions": sessions})
    return {"week_start": t0, "now": now, "rows": rows, "milestones": milestones(now)}


@router.get("/api/plan/overview")
def get_overview(week: str | None = None):
    return overview(week)
