"""P4 — weekly alignment table + 3 dry sentences. Fired nightly by the daemon; `cli report` on demand."""
import datetime as dt, time
from . import config, db, llm

TONE = ("You are Alibi, a dry, honest witness. Given this week's verified habit table, write 3 short sentences: "
        "what was actually done, what was claimed but not seen, and the one thing to fix tomorrow. No cheerleading.")


def week_start(now: float | None = None) -> float:
    d = dt.datetime.fromtimestamp(now or time.time())
    monday = (d - dt.timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday.timestamp()


def build_json(now: float | None = None) -> dict:
    now = now or time.time()
    t0 = week_start(now)
    frac = min(1.0, (now - t0) / (7 * 86400))       # how far through the week we are
    con = db.connect()
    rows, running = [], None
    for key, h in config.habits()["habits"].items():
        if h.get("source") == "strava":
            running = _running(con, key, h, t0, now, frac)
            continue
        ss = con.execute("SELECT * FROM sessions WHERE habit=? AND status='done' AND started_at>=?",
                         (key, t0)).fetchall()
        verified = sum(s["declared_min"] * (s["on_task_ratio"] or 0) for s in ss)
        declared = sum(s["declared_min"] for s in ss)
        target = h.get("weekly_target_min", 0)
        pace = target * frac
        behind = max(0, round(pace - verified))
        rows.append({"habit": key, "modality": h.get("modality"), "target_min": target,
                     "verified_min": round(verified), "declared_min": declared, "sessions": len(ss),
                     "verdicts": {v: sum(s["verdict"] == v for s in ss) for v in ("done", "partial", "slacked")},
                     "pace_target_min": round(pace), "status": "aligned" if behind <= 0.1 * target else "behind",
                     "behind_by_min": behind})
    out = {"week_start": t0, "generated_at": now, "rows": rows, "running": running}
    out["table"] = table_text(out)
    out["summary"] = summarise(out)
    out["text"] = out["table"] + "\n\n" + out["summary"]
    return out


def _running(con, key, h, t0, now, frac) -> dict:
    runs = [e["payload"] for e in db.events_between(con, t0, now, "strava")]
    good = [r for r in runs if r.get("distance_km", 0) >= h.get("min_km", 0)]
    target = h.get("weekly_sessions", 0)
    behind = max(0, target - len(good))
    return {"habit": key, "target_sessions": target, "min_km": h.get("min_km", 0), "runs": runs,
            "qualifying": len(good), "status": "aligned" if len(good) >= round(target * frac) else "behind",
            "behind_by": behind}


def table_text(r: dict) -> str:
    lines = [f"{'habit':<12}{'verified':>10}{'declared':>10}{'target':>8}  status"]
    for x in r["rows"]:
        st = "aligned" if x["status"] == "aligned" else f"behind by {x['behind_by_min']} min"
        lines.append(f"{x['habit']:<12}{x['verified_min']:>9}m{x['declared_min']:>9}m{x['target_min']:>7}m  {st}")
    if r["running"]:
        g = r["running"]
        st = "aligned" if g["behind_by"] == 0 else f"behind by {g['behind_by']}"
        lines.append(f"{g['habit']:<12}{g['qualifying']:>4}/{g['target_sessions']} runs ≥{g['min_km']} km{'':>9}{st}")
    return "\n".join(lines)


def summarise(r: dict) -> str:
    if config.TEXT_READY:
        try:
            out = llm.chat_text(TONE, r["table"])
            if out:
                return out
        except Exception:
            pass
    return _dry(r)


def _dry(r: dict) -> str:
    """No-model fallback, same voice."""
    rows = r["rows"]
    did = [x for x in rows if x["verified_min"] > 0]
    gap = max(rows, key=lambda x: x["declared_min"] - x["verified_min"], default=None)
    worst = max(rows, key=lambda x: x["behind_by_min"], default=None)
    s1 = ("Verified this week: " + ", ".join(f"{x['verified_min']} min of {x['habit']}" for x in did) + ".") \
        if did else "Nothing verified this week. The witness has seen nothing."
    if gap and gap["declared_min"] - gap["verified_min"] > 0:
        s2 = (f"You declared {_hm(gap['declared_min'])} of {gap['habit']}; "
              f"the evidence supports {_hm(gap['verified_min'])}.")
    else:
        s2 = "What you claimed, you did."
    if r["running"] and r["running"]["behind_by"]:
        s2 += f" Strava has {r['running']['qualifying']} of {r['running']['target_sessions']} runs."
    s3 = (f"Tomorrow: {worst['habit']}, you're {_hm(worst['behind_by_min'])} behind pace."
          if worst and worst["behind_by_min"] else "Tomorrow: keep the alibi clean.")
    return " ".join([s1, s2, s3])


def _hm(m: int) -> str:
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min"


def build() -> str:
    return build_json()["text"]
