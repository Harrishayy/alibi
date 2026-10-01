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
    cfg = config.habits()
    for key, h in cfg["habits"].items():
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
        streak, today_ok = _streak(con, key, now)
        strikes = con.execute("SELECT count(*) FROM events e JOIN sessions s ON s.id=e.session_id WHERE e.source='alibi' "
                              "AND e.kind='strike' AND s.habit=? AND e.ts>=?", (key, t0)).fetchone()[0]
        rows.append({"habit": key, "label": config.display_name(key, cfg), "modality": h.get("modality"),
                     "target_min": target,
                     "verified_min": round(verified), "declared_min": declared, "sessions": len(ss),
                     "verdicts": {v: sum(s["verdict"] == v for s in ss) for v in ("done", "partial", "slacked")},
                     "pace_target_min": round(pace), "status": "aligned" if behind <= 0.1 * target else "behind",
                     "behind_by_min": behind, "gap_to_pace_min": round(pace - verified),
                     "pct_of_target": round(verified / target, 3) if target else None,
                     "streak_days": streak, "streak_today": today_ok, "strikes": strikes,
                     "honesty": round(verified / declared, 3) if declared else None})
    worst = max((r for r in rows if r["behind_by_min"] > 0), key=lambda r: r["behind_by_min"], default=None)
    for i, r in enumerate(sorted(rows, key=lambda r: -r["gap_to_pace_min"])):
        r["rank"] = i                                   # 0 = furthest behind pace (sort the table by this)
        r["severity"] = "worst" if r is worst else "behind" if r["status"] == "behind" else "on_pace"
    tv = sum(r["verified_min"] for r in rows)
    td = sum(r["declared_min"] for r in rows)
    tt = sum(r["target_min"] for r in rows)
    out = {"week_start": t0, "generated_at": now, "rows": rows, "running": running,
           "alibi_score": round(tv / td, 3) if td else None,
           "totals": {"verified_min": tv, "declared_min": td, "target_min": tt, "pace_min": round(tt * frac),
                      "week_frac": round(frac, 3), "pct_of_target": round(tv / tt, 3) if tt else None,
                      "honesty": round(tv / td, 3) if td else None}}
    out["headline"] = _headline(out)
    out["table"] = table_text(out)
    out["summary"] = summarise(out)
    out["text"] = out["table"] + "\n\n" + out["summary"]
    return out


def _streak(con, habit: str, now: float) -> tuple[int, bool]:
    """Consecutive days (back from today) with at least one done/partial session. Today without one yet doesn't break
    the streak until midnight, as in Streaks."""
    days = {r[0] for r in con.execute(
        "SELECT DISTINCT date(started_at,'unixepoch','localtime') FROM sessions WHERE habit=? AND status='done' "
        "AND verdict IN ('done','partial')", (habit,))}
    d = dt.date.fromtimestamp(now)
    today_ok = d.isoformat() in days
    if not today_ok:
        d -= dt.timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= dt.timedelta(days=1)
    return n, today_ok


def _headline(r: dict) -> str:
    """One line for the top of the dashboard (D2)."""
    t = r["totals"]
    if not t["target_min"]:
        return "No targets set."
    line = (f"This week: {t['verified_min']:,} of {t['target_min']:,} target min verified · claimed {t['declared_min']:,}"
            f" · {t['verified_min'] / t['target_min']:.0%} of the way, pace says {t['week_frac']:.0%}.")
    if r["alibi_score"] is not None:
        line += f" {r['alibi_score']:.0%} of your claims held up."
    return line


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
    nm = lambda x: x.get("label") or x["habit"]
    gap = max(rows, key=lambda x: x["declared_min"] - x["verified_min"], default=None)
    worst = max(rows, key=lambda x: x["behind_by_min"], default=None)
    s1 = ("Verified this week: " + ", ".join(f"{x['verified_min']} min of {nm(x)}" for x in did) + ".") \
        if did else "Nothing verified this week. The witness has seen nothing."
    if gap and gap["declared_min"] - gap["verified_min"] > 0:
        s2 = (f"You declared {_hm(gap['declared_min'])} of {nm(gap)}; "
              f"the evidence supports {_hm(gap['verified_min'])}.")
    else:
        s2 = "What you claimed, you did."
    if r["running"] and r["running"]["behind_by"]:
        s2 += f" Strava has {r['running']['qualifying']} of {r['running']['target_sessions']} runs."
    when = "Today" if dt.datetime.fromtimestamp(r.get("generated_at") or time.time()).hour < 18 else "Tomorrow"
    s3 = (f"{when}: {nm(worst)}, you're {_hm(worst['behind_by_min'])} behind pace."
          if worst and worst["behind_by_min"] else f"{when}: keep the alibi clean.")
    strikes = [x for x in rows if x.get("strikes")]
    if strikes:
        x = max(strikes, key=lambda x: x["strikes"])
        s3 += f" {x['strikes']} strike{'s' * (x['strikes'] != 1)} on {nm(x)} this week."
    return " ".join([s1, s2, s3])


def _hm(m: int) -> str:
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min"


def build() -> str:
    return build_json()["text"]
