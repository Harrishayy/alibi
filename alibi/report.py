"""P4 — weekly alignment table + 3 dry sentences. Fired nightly by the daemon; `cli report` on demand."""
import datetime as dt, time
from . import config, db, llm

TONE = ("You are Alibi, a dry, honest witness. Given this week's verified habit table, write 3 short sentences: "
        "what was actually done, what was claimed but not seen, and the one thing to fix tomorrow. No cheerleading.")


def week_start(now: float | None = None) -> float:
    d = dt.datetime.fromtimestamp(now or time.time())
    monday = (d - dt.timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday.timestamp()


NEW_GRACE_S = 24 * 3600        # a habit added less than a day ago is never 'behind'


def _blocks(h: dict, t_from: float, t_to: float):
    """(start_ts, minutes) for each planned block of the habit that starts in [t_from, t_to)."""
    d, end = dt.date.fromtimestamp(t_from), dt.date.fromtimestamp(t_to)
    while d <= end:
        day = config.DAYS[d.weekday()]
        for b in h.get("schedule") or []:
            if day not in (b.get("days") or []):
                continue
            try:
                hh, mm = (int(x) for x in str(b.get("at", "")).split(":")[:2])
            except ValueError:
                continue
            ts = dt.datetime(d.year, d.month, d.day, hh, mm).timestamp()
            if t_from <= ts < t_to:
                yield ts, int(b.get("min") or 0)
        d += dt.timedelta(days=1)


def _sched_minutes(h: dict, t_from: float, t_to: float) -> int:
    return sum(m for _, m in _blocks(h, t_from, t_to))


def _pace(h: dict, t0: float, now: float) -> dict:
    """This week's target and 'even pace' for one habit, counted from when it was added (not Monday) and, when
    it has a plan, from its planned blocks (a block counts toward pace once it has ended)."""
    t1 = t0 + 7 * 86400
    target = h.get("weekly_target_min", 0) or 0
    created = config.habit_created_ts(h)
    since = max(t0, created or t0)
    new = bool(created and now - created < NEW_GRACE_S)
    week_plan = _sched_minutes(h, t0, t1)
    if week_plan:
        left_plan = _sched_minutes(h, since, t1)
        eff = target * left_plan / week_plan
        done_plan = sum(m for ts, m in _blocks(h, since, now) if ts + m * 60 <= now)
        pace = target * done_plan / week_plan
    else:
        eff = target * (t1 - since) / (t1 - t0)
        pace = eff * min(1.0, max(0.0, (now - since) / max(1.0, t1 - since)))
    if new:
        pace = 0.0
    return {"target": round(eff), "pace": pace, "new": new, "partial_week": since > t0,
            "frac": min(1.0, max(0.0, (now - since) / max(1.0, t1 - since)))}


def _today(con, key: str, h: dict, now: float) -> tuple[int, int]:
    """(planned minutes today, minutes Alibi saw today) for one habit."""
    d = dt.date.fromtimestamp(now)
    day0 = dt.datetime(d.year, d.month, d.day).timestamp()
    planned = _sched_minutes(h, day0, day0 + 86400)
    seen = con.execute("SELECT COALESCE(SUM(declared_min*COALESCE(on_task_ratio,0)),0) FROM sessions WHERE habit=? "
                       "AND status='done' AND started_at>=?", (key, day0)).fetchone()[0]
    return planned, round(seen)


def build_json(now: float | None = None) -> dict:
    now = now or time.time()
    t0 = week_start(now)
    frac = min(1.0, (now - t0) / (7 * 86400))       # how far through the week we are
    con = db.connect()
    rows, running = [], None
    cfg = config.habits()
    for key, h in cfg["habits"].items():
        if h.get("source") == "strava":
            running = _running(con, key, h, t0, now, _pace(h, t0, now)["frac"], cfg)
            continue
        if h.get("source") == "health":
            continue                                    # Health habits are daily targets: see out["health"]
        ss = con.execute("SELECT * FROM sessions WHERE habit=? AND status='done' AND started_at>=?",
                         (key, t0)).fetchall()
        verified = sum(s["declared_min"] * (s["on_task_ratio"] or 0) for s in ss)
        declared = sum(s["declared_min"] for s in ss)
        pc = _pace(h, t0, now)
        target, pace = pc["target"], pc["pace"]
        behind = max(0, round(pace - verified))
        today_plan, today_seen = _today(con, key, h, now)
        streak, today_ok = _streak(con, key, now)
        strikes = con.execute("SELECT count(*) FROM events e JOIN sessions s ON s.id=e.session_id WHERE e.source='alibi' "
                              "AND e.kind='strike' AND s.habit=? AND e.ts>=?", (key, t0)).fetchone()[0]
        rows.append({"habit": key, "label": config.display_name(key, cfg), "modality": h.get("modality"),
                     "target_min": target, "weekly_target_min": h.get("weekly_target_min", 0),
                     "is_new": pc["new"], "partial_week": pc["partial_week"],
                     "today_planned_min": today_plan, "today_seen_min": today_seen,
                     "verified_min": round(verified), "declared_min": declared, "sessions": len(ss),
                     "verdicts": {v: sum(s["verdict"] == v for s in ss) for v in ("done", "partial", "slacked")},
                     "pace_target_min": round(pace), "status": "aligned" if behind <= 0.1 * target or pc["new"] else "behind",
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
    tp = sum(r["pace_target_min"] for r in rows)
    out = {"week_start": t0, "generated_at": now, "rows": rows, "running": running, "health": _health(con, now, cfg),
           "alibi_score": round(tv / td, 3) if td else None,
           "totals": {"verified_min": tv, "declared_min": td, "target_min": tt, "pace_min": tp,
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


def _running(con, key, h, t0, now, frac, cfg=None) -> dict:
    from . import strava
    runs = strava.latest_runs(con, t0, now)             # an edited run replaces its old copy
    good = [r for r in runs if r.get("distance_km", 0) >= h.get("min_km", 0)]
    target = h.get("weekly_sessions", 0)
    behind = max(0, target - len(good))
    try:
        st = strava.status()
    except Exception:
        st = {"state": "unknown", "connected": False, "text": ""}
    km = round(sum(r.get("distance_km", 0) for r in runs), 1)
    if not st.get("connected") and not runs:
        text = "Connect Strava and Alibi will check your runs."
    elif len(good) >= target:
        text = f"{len(good)} of {target} runs done this week — target hit."
    else:
        text = (f"{len(good)} of {target} runs of {h.get('min_km', 0):g} km or more this week"
                + (f" ({len(runs) - len(good)} shorter run{'s' * (len(runs) - len(good) != 1)} didn't count)."
                   if len(runs) > len(good) else "."))
    return {"habit": key, "label": config.display_name(key, cfg), "target_sessions": target,
            "min_km": h.get("min_km", 0), "runs": runs,
            "qualifying": len(good), "status": "aligned" if len(good) >= round(target * frac) else "behind",
            "behind_by": behind, "week_km": km, "longest_km": max((r.get("distance_km", 0) for r in runs), default=0),
            "strava": {"state": st.get("state"), "connected": st.get("connected"), "last_sync": st.get("last_sync"),
                       "text": st.get("text")},
            "text": text}


def _health(con, now, cfg) -> list[dict]:
    try:
        from . import integrations
        return integrations.health_rows(con, now, cfg)
    except Exception as e:
        print(f"[alibi] health rows failed: {e!r}", flush=True)
        return []


def table_text(r: dict) -> str:
    lines = [f"{'habit':<12}{'verified':>10}{'declared':>10}{'target':>8}  status"]
    for x in r["rows"]:
        st = ("new this week" if x.get("is_new") else "aligned") if x["status"] == "aligned" \
            else f"behind by {x['behind_by_min']} min"
        lines.append(f"{x['habit']:<12}{x['verified_min']:>9}m{x['declared_min']:>9}m{x['target_min']:>7}m  {st}")
    if r["running"]:
        g = r["running"]
        st = "aligned" if g["behind_by"] == 0 else f"behind by {g['behind_by']}" if g["status"] == "behind" \
            else f"on pace, {g['behind_by']} to go"
        lines.append(f"{g['habit']:<12}{g['qualifying']:>4}/{g['target_sessions']} runs ≥{g['min_km']} km{'':>9}{st}")
    for x in r.get("health") or []:
        st = "no data yet" if x["status"] == "no_data" else f"{x['days_met']}/{x['days_checked']} days"
        lines.append(f"{x['habit']:<12}{x['metric_label'].lower()} ≥ {x['target_text']}/day{'':>4}{st}")
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
        if did else "Nothing checked off this week yet — Alibi hasn't seen a session."
    if gap and gap["declared_min"] - gap["verified_min"] > 0:
        s2 = (f"You declared {_hm(gap['declared_min'])} of {nm(gap)}; "
              f"the evidence supports {_hm(gap['verified_min'])}.")
    else:
        s2 = "What you claimed, you did."
    if r["running"] and r["running"]["behind_by"]:
        s2 += f" Strava has {r['running']['qualifying']} of {r['running']['target_sessions']} runs."
    hl = [x for x in r.get("health") or [] if x["days_checked"]]
    if hl:
        s2 += " " + "; ".join(f"{nm(x)}: {x['days_met']} of {x['days_checked']} days at target" for x in hl) + "."
    when = "Today" if dt.datetime.fromtimestamp(r.get("generated_at") or time.time()).hour < 18 else "Tomorrow"
    left = [(x["today_planned_min"] - x["today_seen_min"], x) for x in rows if x.get("today_planned_min")]
    left = max((t for t in left if t[0] > 0), key=lambda t: t[0], default=None)
    if when == "Today" and left:
        x = left[1]
        s3 = (f"Today: {nm(x)} — {_hm(x['today_planned_min'])} planned, "
              + (f"{x['today_seen_min']} min done so far." if x["today_seen_min"] else "none done yet."))
    elif worst and worst["behind_by_min"]:
        s3 = f"{when}: {nm(worst)}, you're {_hm(worst['behind_by_min'])} behind pace."
    else:
        s3 = f"{when}: keep the alibi clean."
    strikes = [x for x in rows if x.get("strikes")]
    if strikes:
        x = max(strikes, key=lambda x: x["strikes"])
        s3 += f" {x['strikes']} strike{'s' * (x['strikes'] != 1)} on {nm(x)} this week."
    return " ".join([s1, s2, s3])


def _hm(m: int) -> str:
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min"


def build() -> str:
    return build_json()["text"]
