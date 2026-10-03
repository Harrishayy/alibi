"""Focus: a day's review from the iPhone and the Mac, counted by code and never by a model.

  day(con, date=None, now=None)  one day: phone pickups (by hour, the peak, against your week, inside planned blocks),
                                 the Mac's distracting minutes, per planned habit and per session, and up to three rules
                                 worded with digits (`text` names the site; `agent_text` says "video sites")
  week(con, now=None)            the last 7 days: pickups a day (avg_day over full earlier days), pickups an hour per
                                 habit, the habit that struggled
  agent_summary(con, now=None)   yesterday and today so far for the NemoClaw agent: numbers, habit names and hours
  agent_day(d) / snapshot(d)     the agent's subset of a day / the few numbers a digest or brief row keeps for its card
  phone_line(f)                  "Phone: 92 pickups, 11 at 17:00. 14 during planned blocks." for the night text

Pure reads (events, sessions, calendar_sync.plan): no writes, no network; the clock is time.time() at call time. A day
the phone sent nothing has null phone numbers, never 0: no data is not a miss. Site and app names stay in day(), for
the dashboard on this Mac; agent_summary(), the night model's focus_day tool and every line that reaches the Spark
carry counts, minutes, habit names and hours only.
"""
import bisect, datetime as dt, json, os, re, time
from . import calendar_sync, config, db, signals, verifier
from .nudges import GUARD_ALLOW, _host

SKEW_S = 300               # the phone's clock may run 5 min ahead (integrations clamps phone rows to now + 300)
GAP_CAP_S = 60             # a window row stands for at most a minute: a shut lid isn't time on the last tab
MIN_AVG_DAYS = 3           # "your week" needs 3 days of phone data behind it; fewer is an anecdote, not an average
MIN_AVG_PICKUPS = 10       # no percentage on a tiny base: 2 pickups at 01:00 against 0.3 by then isn't "+567%"
FULL_DAY_S = 12 * 3600     # a day joins the week's average when its phone rows span 12 h: the evening the sync was
                           # switched on (rows from 18:42 only), or a phone dead by noon, isn't a day of pickups
PER_HOUR_MIN_S = 600       # pickups an hour only over 10+ min of planned time: 1 pickup in 3 min isn't 20 an hour
HABIT_HOUR_MIN_S = 1800    # the week's pickups an hour per habit only over 30+ min of its time with phone data
MAX_RECS = 3
LINE = {"phone_away": 6.0, "peak": 8, "above_week": 30, "mac": 10, "none_happened": 40, "mac_week": 30}
WEIGHT = {"peak": 1.5}     # moving a block out of the phone's peak is the change that sticks: half again the rank
ORDER = ("none_happened", "peak", "phone_away", "mac", "above_week", "best_hour")     # ties, and the order of the rules
STATE_ORDER = ("live", "now", "missed", "slacked", "partial", "done", "nodata", "waiting", "planned")

# verifier.DISTRACTIONS words by kind: the agent hears "video sites", never "YouTube"
KINDS = {"youtube": "video", "netflix": "video", "twitch": "video", "prime video": "video", "disney+": "video",
         "tiktok": "social", "twitter": "social", "x.com": "social", "reddit": "social", "instagram": "social",
         "facebook": "social", "messages": "chat", "whatsapp": "chat", "discord": "chat", "spotify": "music"}
KIND_WORDS = {"video": "video sites", "social": "social apps", "chat": "chat apps", "music": "music apps"}
_ALIAS = {"youtu.be": "youtube"}                     # hosts that don't carry their site's word
_SEP = re.compile(r"\s[-|–—•·/:]\s")                 # tab titles: "Lofi - YouTube", "Home / X", "@a • Instagram"


# --- days, bounds, small reads ---------------------------------------------------------------------------------------

def _now(now) -> float:
    return time.time() if now is None else float(now)


def as_date(date=None, now: float | None = None) -> dt.date:
    """None, 'today', 'yesterday', 'YYYY-MM-DD' or a date -> a date. ValueError (one sentence) for anything else."""
    if isinstance(date, dt.datetime):
        return date.date()
    if isinstance(date, dt.date):
        return date
    today = dt.date.fromtimestamp(_now(now))
    s = str(date or "today").strip().lower()
    if s == "today":
        return today
    if s == "yesterday":
        return today - dt.timedelta(days=1)
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            raise ValueError
        return dt.date.fromisoformat(s)
    except ValueError:
        raise ValueError("date must look like 2026-10-01, today or yesterday.") from None


def _bounds(day: dt.date) -> tuple[float, float]:
    """Local midnight to local midnight (a DST day isn't 86400 s)."""
    return (dt.datetime.combine(day, dt.time()).timestamp(),
            dt.datetime.combine(day + dt.timedelta(days=1), dt.time()).timestamp())


def _name(day: dt.date, now: float) -> str:
    return {0: "Today", 1: "Yesterday"}.get((dt.date.fromtimestamp(now) - day).days, f"{day:%A}")


def _cfg() -> dict:
    try:
        cfg = config.habits()
    except Exception:
        return {"habits": {}}
    return cfg if isinstance(cfg, dict) and isinstance(cfg.get("habits"), dict) else {"habits": {}}


def _has_phone(con, a: float, b: float) -> bool:
    """Any phone row in [a, b): the phone was talking to us, so a missing pickup is a real 0."""
    row = con.execute("SELECT 1 FROM events WHERE source='phone' AND ts>=? AND ts<? LIMIT 1", (a, b)).fetchone()
    return row is not None


def _full_day(con, a: float, b: float) -> bool:
    """The phone reported across [a, b): its rows there span FULL_DAY_S or more."""
    lo, hi = con.execute("SELECT min(ts), max(ts) FROM events WHERE source='phone' AND ts>=? AND ts<?", (a, b)).fetchone()
    lo, hi = signals._f(lo, None), signals._f(hi, None)
    return lo is not None and hi is not None and hi - lo >= FULL_DAY_S


def _pickups(con, a: float, b: float) -> list[float]:
    """Pickup times in [a, b), sorted, one per second: a batch the phone sent twice counts once."""
    seen = {}
    for (ts,) in con.execute("SELECT ts FROM events WHERE source='phone' AND kind='pickup' AND ts>=? AND ts<?", (a, b)):
        t = signals._f(ts, None)
        if t is not None:
            seen.setdefault(int(t), t)
    return sorted(seen.values())


def _count(ts: list[float], iv) -> int:
    """How many of the sorted times fall inside the intervals (half-open, overlaps counted once)."""
    return sum(bisect.bisect_left(ts, b) - bisect.bisect_left(ts, a) for a, b in signals._union(list(iv)))


def _intersect(iv, ranges) -> list[tuple[float, float]]:
    return signals._union([(max(a, x), min(b, y)) for a, b in iv for x, y in ranges if min(b, y) > max(a, x)])


def _elapsed(b: dict, a0: float, b0: float, now: float) -> tuple[float, float] | None:
    """A block's window inside [a0, b0) and up to now: a block still running counts the minutes so far."""
    a, z = max(b["start"], a0), min(b["end"], b0, now)
    return (a, z) if z > a else None


def _blocks(con, day0: dt.date, days: int, now: float, cfg: dict) -> list[dict]:
    """The planned focus blocks: calendar_sync.plan minus skipped ones (a skip or a day off isn't a plan to keep),
    Strava/Health ones (a phone moving in a pocket on a run isn't a distraction) and blocks that ended before their
    habit existed (as today.plan_today). Never raises: no plan reads as no blocks."""
    try:
        plan = calendar_sync.plan(con, day0, days, now)
    except Exception as e:
        print(f"[alibi] focus: no plan ({e!r})", flush=True)
        return []
    hs = cfg["habits"]
    out = []
    for b in plan:
        if b.get("state") == "skipped" or b.get("check") in ("strava", "health"):
            continue
        made = config.habit_created_ts(hs[b["habit"]]) if isinstance(hs.get(b["habit"]), dict) else None
        if made and b["end"] < made and not b.get("session_id"):
            continue
        out.append(b)
    return out


def _state(states: list[str]) -> str:
    """One state for a habit's blocks that day, the one to act on first: live, then missed, then how it went."""
    return next((s for s in STATE_ORDER if s in states), states[0] if states else "planned")


def _sessions(con, a: float, b: float, now: float) -> list[tuple]:
    """(row, end, intervals minus breaks) for sessions started in [a, b); a live one counts up to now. The end is
    capped at ends_at, as the verifier's own window is."""
    out = []
    for s in con.execute("SELECT * FROM sessions WHERE started_at>=? AND started_at<? ORDER BY started_at, id",
                         (a, b)).fetchall():
        end = max(s["started_at"], min(s["ended_at"] or now, s["ends_at"]))
        try:
            holes = db.breaks(con, s["id"], end)
        except Exception:
            holes = []
        out.append((s, end, signals._clip([(s["started_at"], end)], s["started_at"], end, holes)))
    return out


def _notifications(con, a: float, b: float) -> int:
    n = 0
    for (raw,) in con.execute("SELECT payload FROM events WHERE source='mac' AND kind='notifications' AND ts>=? "
                              "AND ts<?", (a, b)):
        try:
            p = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if isinstance(p, dict):
            n += max(0, int(signals._f(p.get("count"))))
    return n


def _screen_time(con, a: float, b: float) -> int | None:
    """The day's picked-app minutes from Screen Time (cumulative per app: its last value), None with no rows."""
    apps = {}
    for d in signals.screentime_deltas(con, a, b - 1e-3):
        apps[d["app"]] = max(apps.get(d["app"], 0.0), d["minutes"])
    return round(sum(apps.values())) if apps else None


# --- the Mac: which window rows are distractions ---------------------------------------------------------------------

def _squash(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower().replace("+", "plus"))


def site_name(kw: str) -> str:
    """'youtube' -> 'YouTube', 'x.com' -> 'X' (verifier.SITE_NAMES, the names Screen Time and Opal use)."""
    return verifier.SITE_NAMES.get(kw) or kw.title()


_HOSTS = tuple(kw for kw in verifier.DISTRACTIONS if "." in kw)                      # x.com: a whole host
_WORDS = {_squash(kw): kw for kw in verifier.DISTRACTIONS if "." not in kw}          # "primevideo" -> "prime video"
_TITLES = tuple((kw, site_name(kw).lower()) for kw in verifier.DISTRACTIONS)


def _title_kw(title: str) -> str | None:
    """A browser tab with no URL: the site is the title's last segment before the browser's own name and profile
    ('Lofi - YouTube - Google Chrome – Work' -> youtube), or its whole first segment ('TikTok - Make Your Day')."""
    parts = [x.strip() for x in _SEP.split(title or "") if x.strip()]
    for i, x in enumerate(parts):
        low = x.lower()
        if low in verifier.BROWSERS or low.removeprefix("mozilla ") in verifier.BROWSERS:
            parts = parts[:i]
            break
    if not parts:
        return None
    first, last = parts[0].lower(), parts[-1].lower()
    return next((kw for kw, name in _TITLES if first == name or last == name or last.startswith(name + " ")), None)


def site_kw(p) -> str | None:
    """The verifier.DISTRACTIONS word a window row shows ('youtube', 'x.com'), or None. A tab's URL host decides, by
    whole labels ('netflixtechblog.com' isn't Netflix, music.youtube.com is music to work to); else the app's own name
    ('Messages', 'Discord'); a browser with no URL falls back to the site in its tab title."""
    if not isinstance(p, dict):
        return None
    host = _host(p.get("url"))
    if host:
        if any(host == a or host.endswith("." + a) for a in GUARD_ALLOW):
            return None
        for a, kw in tuple(_ALIAS.items()) + tuple((h, h) for h in _HOSTS):
            if host == a or host.endswith("." + a):
                return kw
        return next((_WORDS[x] for x in host.split(".") if x in _WORDS), None)
    app = str(p.get("app") or "").strip()
    if _squash(app) in _WORDS:
        return _WORDS[_squash(app)]
    if app.lower() in verifier.BROWSERS:
        return _title_kw(str(p.get("title") or ""))
    return None


def _distractions(wins) -> list[tuple[float, float, str]]:
    """(start, end, word) for the window rows that are distractions. A tab stays up for minutes, so each distinct
    (app, title, url) is classified once."""
    seen, out = {}, []
    for a, b, p in wins:
        key = (p.get("app"), p.get("title"), p.get("url"))
        try:
            kw = seen[key]
        except KeyError:
            kw = seen[key] = site_kw(p)
        except TypeError:                          # an unhashable value in a hand-made row
            kw = site_kw(p)
        if kw:
            out.append((a, b, kw))
    return out


def _kinds(kws, cap: bool = True) -> str:
    """['youtube', 'reddit'] -> 'Video sites and social apps': what the agent may hear instead of the names."""
    words = list(dict.fromkeys(KIND_WORDS.get(KINDS.get(k, ""), "distracting apps") for k in kws))
    words = words or ["distracting apps"]
    s = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
    return s[:1].upper() + s[1:] if cap else s


def _windows(con, a: float, b: float) -> list[tuple[float, float, dict]]:
    """Laptop window rows in [a, b) as (start, end, payload). A row stands for the time to the next one, at most
    GAP_CAP_S, so a sleeping Mac or a shut lid is a gap, not minutes on the last thing shown."""
    rows = []
    for ts, raw in con.execute("SELECT ts, payload FROM events WHERE source='laptop' AND kind='window' AND ts>=? "
                               "AND ts<? ORDER BY ts, id", (a, b)):
        t = signals._f(ts, None)
        try:
            p = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if t is not None and isinstance(p, dict):
            rows.append((t, p))
    last = min(GAP_CAP_S, max(1, config.LAPTOP_EVERY_S))
    return [(t, min(rows[i + 1][0] if i + 1 < len(rows) else t + last, t + GAP_CAP_S, b), p)
            for i, (t, p) in enumerate(rows)]


def _secs(dist, iv) -> dict[str, float]:
    """Seconds per distraction word inside the intervals."""
    iv = signals._union(list(iv))
    out = {}
    for a, b, kw in dist:
        s = sum(max(0.0, min(b, y) - max(a, x)) for x, y in iv)
        if s > 0:
            out[kw] = out.get(kw, 0.0) + s
    return out


def _switch_rate(wins) -> float | None:
    """App switches a minute from the window log (counted as mac_signals.switches counts them), over 10+ minutes."""
    seen = sum(b - a for a, b, _ in wins)
    if seen < 600:
        return None
    n = sum(1 for (a0, _, p0), (a1, _, p1) in zip(wins, wins[1:])
            if a1 - a0 <= GAP_CAP_S and p0.get("app") and p1.get("app") and p0.get("app") != p1.get("app"))
    return round(n / (seen / 60), 2)


def _top(secs: dict) -> list[str]:
    return [k for k, _ in sorted(secs.items(), key=lambda kv: (-kv[1], kv[0]))]


def _guard_act() -> str:
    """The focus guard only acts inside a session: off, turn it on; on, the block has to be a session."""
    if os.getenv("FOCUS_GUARD", "0") == "1":
        return "Start each block as a session so the focus guard can step in."
    return "Turn the focus guard on."


# --- the day ---------------------------------------------------------------------------------------------------------

def _synced_to(t0: float, hi: float) -> float:
    """How far a running day's phone data goes: the last batch the iPhone delivered (it syncs in batches, sometimes
    hours apart), else now. Without it a phone last heard from at 18:00 would read as 'below your week' at 22:00."""
    try:
        from . import integrations
        last = signals._f(integrations.state().get("phone_last_received"), None)
    except Exception:
        last = None
    return last if last is not None and t0 < last < hi else hi


def _week_avg(con, d0: dt.date, upto: float, t1: float) -> tuple[float | None, int]:
    """Mean pickups over the previous 7 days the phone covered in full (_full_day), and how many days that was. A day
    still running is compared like for like: each earlier day counts only up to the same clock time as `upto`."""
    clock = dt.datetime.fromtimestamp(upto).time() if upto < t1 else None
    counts = []
    for i in range(1, 8):
        di = d0 - dt.timedelta(days=i)
        a, b = _bounds(di)
        if not _full_day(con, a, b):
            continue
        cut = min(b, dt.datetime.combine(di, clock).timestamp()) if clock else b
        counts.append(len(_pickups(con, a, cut)))
    if len(counts) < MIN_AVG_DAYS:
        return None, len(counts)
    return round(sum(counts) / len(counts), 1), len(counts)


def _line(phone: bool, n, peak, ib, noun: str = "phone pickup") -> str:
    """'92 phone pickups, 11 at 17:00. 14 during planned blocks.' Counts and hours only, so it may go anywhere."""
    if not phone or n is None:
        return "No phone data for this day."
    if not n:
        return f"No {noun}s."
    s = f"{n} {noun}{'s' * (n != 1)}" + (f", {peak['pickups']} at {peak['hour']:02d}:00" if peak else "") + "."
    if isinstance(ib, dict) and ib.get("blocks"):
        s += f" {ib.get('pickups') or 'None'} during planned blocks."
    return s


def _rules(c: dict) -> list[dict]:
    """Up to MAX_RECS rules, biggest first. Each rule's size is how far past its own line it is (LINE: 6 pickups an
    hour, a peak of 8, 30% above the week, 10 min on the Mac); the plan not happening at all always leads."""
    out = []

    def add(rule, size, habit, text, why, agent=None):
        out.append((size, ORDER.index(rule), {"rule": rule, "habit": habit, "text": text, "agent_text": agent or text,
                                              "why": why}))
    n, now, blocks = c["n"], c["now"], c["blocks"]
    due = [b for b in blocks if b["end"] <= now]
    none = bool(c["phone"] and due and n >= LINE["none_happened"] and not any(b.get("session_id") for b in blocks))
    if none:
        k = len(due)
        lead = f"None of your {k} blocks happened" if k > 1 else f"Your {due[0]['label']} block didn't happen"
        add("none_happened", float("inf"), None,
            f"{lead}; your phone was picked up {n} times. One 20-minute block tomorrow, phone away.",
            f"{k} planned block{'s' * (k != 1)} ended with no session; {n} pickups.")
    if not none:                       # "phone away during it" says nothing new when no block happened at all
        for h in c["by_habit"]:
            if h["per_hour"] is not None and h["per_hour"] >= LINE["phone_away"] and (h["pickups"] or 0) >= 3:
                add("phone_away", h["per_hour"] / LINE["phone_away"], h["habit"],
                    f"Phone away for {h['label']}: {round(h['per_hour'])} pickups an hour during it.",
                    f"{h['pickups']} pickups in {round(c['habit_s'][h['habit']] / 60)} min of planned {h['label']}.")
    pk = c["peak"]
    if pk and pk["pickups"] >= LINE["peak"]:
        p0 = dt.datetime.combine(c["d0"], dt.time(pk["hour"])).timestamp()
        best = None
        for b in blocks:               # the block holding most of the peak's pickups (3 or more), longest overlap next
            w = _elapsed(b, c["t0"], c["t1"], now)
            x, y = (max(w[0], p0), min(w[1], p0 + 3600)) if w else (0, 0)
            k = _count(c["today"], [(x, y)]) if y > x else 0
            if k >= 3 and (best is None or (k, y - x, -b["start"]) > best[0]):
                best = ((k, y - x, -b["start"]), b, k)
        if best:
            _, b, k = best
            add("peak", pk["pickups"] / LINE["peak"] * WEIGHT["peak"], b["habit"],
                f"Don't plan {b['label']} at {pk['hour']:02d}:00: your phone peaks then ({pk['pickups']} pickups).",
                f"{k} of the {pk['pickups']} pickups at {pk['hour']:02d}:00 fell inside the {b['label']} block.")
    sec = _secs(c["dist"], c["biv"])
    m = round(sum(sec.values()) / 60)
    if m >= LINE["mac"]:
        top = _top(sec)[:2]
        worst = max(c["by_habit"], key=lambda h: h["mac_distraction_min"], default=None)
        act = _guard_act()
        add("mac", m / LINE["mac"], worst["habit"] if worst and worst["mac_distraction_min"] else None,
            f"{' and '.join(site_name(k) for k in top)} took {m} min during your plans. {act}",
            f"{m} min of {_kinds(top, cap=False)} inside planned blocks.",
            agent=f"{_kinds(top)} took {m} min during your plans. {act}")
    vs = c["vs"]
    if vs is not None and vs >= LINE["above_week"]:
        add("above_week", vs / LINE["above_week"], None,
            f"{n} pickups, {vs}% above your week. Start tomorrow with one 20-minute block, phone in another room.",
            f"The {c['avg_days']} days before averaged {c['avg']:g}" +
            (f" by {dt.datetime.fromtimestamp(c['upto']):%H:%M}." if c["upto"] < c["t1"] else "."))
    out.sort(key=lambda x: (-x[0], x[1]))
    return [r for _, _, r in out[:MAX_RECS]]


def day(con, date=None, now: float | None = None) -> dict:
    """One day's focus review. Today counts up to now; a past day counts all of it."""
    now = _now(now)
    d0 = as_date(date, now)
    t0, t1 = _bounds(d0)
    hi = max(t0, min(t1, now + SKEW_S))
    cfg = _cfg()
    phone = _has_phone(con, t0, hi)
    blocks = _blocks(con, d0, 1, now, cfg)
    sess = _sessions(con, t0, t1, now)
    far = max([hi] + [end for _, end, _ in sess])           # a session past midnight still counts its own pickups
    picks = _pickups(con, t0, far)
    today = [t for t in picks if t < hi]
    wins = _windows(con, t0, far)
    dist = _distractions(wins)
    n = len(today) if phone else None

    hours = [0] * 24
    for t in today:
        hours[dt.datetime.fromtimestamp(t).hour] += 1
    peak = None
    if n:
        h = max(range(24), key=lambda i: (hours[i], -i))      # most pickups; the earlier hour on a tie
        peak = {"hour": h, "pickups": hours[h]}
    upto = _synced_to(t0, hi) if hi < t1 else t1
    avg, avg_days = _week_avg(con, d0, upto, t1)
    avg = avg if phone else None
    vs = round((n - avg) / avg * 100) if n is not None and avg is not None and avg >= MIN_AVG_PICKUPS else None

    started = [w for b in blocks if (w := _elapsed(b, t0, t1, now))]
    biv = signals._union(started)
    in_blocks = {"pickups": _count(today, biv) if phone else None, "blocks": len(started),
                 "minutes": round(signals._len(biv) / 60)}
    groups: dict[str, list] = {}
    for b in blocks:
        groups.setdefault(b["habit"], []).append(b)
    by_habit, habit_s = [], {}
    for k, bs in groups.items():
        iv = signals._union([w for b in bs if (w := _elapsed(b, t0, t1, now))])
        secs = signals._len(iv)
        m = _count(today, iv) if phone else None
        habit_s[k] = secs
        by_habit.append({"habit": k, "label": bs[0]["label"], "planned_min": sum(int(b["min"]) for b in bs),
                         "state": _state([b["state"] for b in bs]), "pickups": m,
                         "per_hour": round(m / (secs / 3600), 1) if m is not None and secs >= PER_HOUR_MIN_S else None,
                         "mac_distraction_min": round(sum(_secs(dist, iv).values()) / 60)})
    sessions = [{"id": s["id"], "habit": s["habit"], "label": config.display_name(s["habit"], cfg),
                 "start": s["started_at"], "end": end, "verdict": s["verdict"] if s["status"] == "done" else None,
                 "pickups": _count(picks, iv) if phone else None,
                 "mac_distraction_min": round(sum(_secs(dist, iv).values()) / 60)} for s, end, iv in sess]
    day_secs = _secs(dist, [(t0, hi)])
    mac = {"distraction_min": round(sum(day_secs.values()) / 60),
           "top": [{"name": site_name(k), "min": round(day_secs[k] / 60)} for k in _top(day_secs)
                   if round(day_secs[k] / 60) >= 1][:3],
           "notifications": _notifications(con, t0, hi),
           "switches_per_min": _switch_rate([w for w in wins if w[0] < hi])}
    recs = _rules({"phone": phone, "n": n or 0, "now": now, "d0": d0, "t0": t0, "t1": t1, "blocks": blocks,
                   "by_habit": by_habit, "habit_s": habit_s, "peak": peak, "today": today, "dist": dist, "biv": biv,
                   "vs": vs, "avg": avg, "avg_days": avg_days, "upto": upto})
    return {"date": d0.isoformat(), "name": _name(d0, now), "phone": phone,
            "pickups": n, "pickups_by_hour": hours if phone else None, "peak": peak,
            "avg_7d": avg, "avg_days": avg_days, "vs_avg_pct": vs, "in_blocks": in_blocks,
            "by_habit": by_habit, "sessions": sessions, "mac": mac,
            "screen_time_picked_min": _screen_time(con, t0, hi), "recommendations": recs,
            "line": _line(phone, n, peak, in_blocks)}


# --- what leaves this module for the agent, the night model and stored rows ------------------------------------------

def agent_day(d: dict, hours: bool = False) -> dict:
    """The day() subset the agent and the night model may see: counts, minutes, habit names and hours. No site or app
    names, window titles or URLs: rules come in their agent wording. hours=True adds pickups_by_hour (focus_day)."""
    out = {"date": d["date"], "phone": d["phone"], "pickups": d["pickups"],
           "peak": dict(d["peak"]) if d["peak"] else None, "avg_7d": d["avg_7d"], "vs_avg_pct": d["vs_avg_pct"],
           "in_blocks": dict(d["in_blocks"]),
           "by_habit": [{k: h[k] for k in ("habit", "label", "state", "pickups", "per_hour", "mac_distraction_min")}
                        for h in d["by_habit"]],
           "mac": {"distraction_min": d["mac"]["distraction_min"], "notifications": d["mac"]["notifications"]},
           "screen_time_picked_min": d["screen_time_picked_min"],
           "recommendations": [{"habit": r["habit"], "text": r["agent_text"], "why": r["why"]}
                               for r in d["recommendations"]],
           "line": _line(d["phone"], d["pickups"], d["peak"], d["in_blocks"])}
    if hours:
        out["pickups_by_hour"] = list(d["pickups_by_hour"]) if d["pickups_by_hour"] else None
    return out


def agent_summary(con, now: float | None = None) -> dict:
    """{yesterday, today_so_far} for /api/agent/context. Each day is built on its own: a bad one is null."""
    now = _now(now)
    today = dt.date.fromtimestamp(now)
    out = {}
    for key, d0 in (("yesterday", today - dt.timedelta(days=1)), ("today_so_far", today)):
        try:
            out[key] = agent_day(day(con, d0, now))
        except Exception as e:
            print(f"[alibi] focus {key} skipped: {type(e).__name__}", flush=True)
            out[key] = None
    return out


def snapshot(d: dict, recs: bool = True) -> dict:
    """The few numbers a night digest (recs too) or an agent brief (counts only) keeps for its Focus chips, so a card
    shows what was counted when the row was written and stays pure over the row."""
    out = {"date": d["date"], "phone": d["phone"], "pickups": d["pickups"],
           "peak": dict(d["peak"]) if d["peak"] else None, "avg_7d": d["avg_7d"], "vs_avg_pct": d["vs_avg_pct"],
           "in_blocks": dict(d["in_blocks"]), "line": _line(d["phone"], d["pickups"], d["peak"], d["in_blocks"])}
    if recs:
        out["recommendations"] = [{k: r[k] for k in ("habit", "text", "agent_text", "why")}
                                  for r in d["recommendations"]]
    return out


def phone_line(f) -> str | None:
    """'Phone: 92 pickups, 11 at 17:00. 14 during planned blocks.' from a snapshot, or None without phone data. Counts
    only: the night text reaches the Spark through /api/agent/digests."""
    if not isinstance(f, dict) or not f.get("phone") or not isinstance(f.get("pickups"), int):
        return None
    if not f["pickups"]:
        return "Phone: no pickups."
    return "Phone: " + _line(True, f["pickups"], f.get("peak"), f.get("in_blocks"), noun="pickup")


# --- the week --------------------------------------------------------------------------------------------------------

def _top_source(con, sess, picks, dist) -> str | None:
    """What pulled you away most in a habit's sessions: phone (the camera saw it, Screen Time minutes, each pickup a
    minute), mac (distracting sites and apps) or away (the desk empty, on the move, the Mac idle). None under 2 min."""
    s_phone = s_mac = s_away = 0.0
    cad = max(1, config.SAMPLE_EVERY_S)
    for s, end, iv in sess:
        try:
            cam = verifier.camera_labels(con, s)
        except Exception:
            cam = []
        s_phone += cad * sum(1 for e in cam if e["payload"].get("label") == "phone") + 60 * _count(picks, iv)
        s_away += cad * sum(1 for e in cam if e["payload"].get("label") == "absent")
        try:
            off = signals.off_intervals(con, s)
            s_phone += signals._len(off["phone"])
            s_away += signals._len(off["moving"]) + signals._len(off["idle"])
        except Exception:
            pass
        s_mac += sum(_secs(dist, iv).values())
    src, s = max((("phone", s_phone), ("mac", s_mac), ("away", s_away)), key=lambda kv: kv[1])
    return src if s >= 120 else None


def _best_hour(sess) -> int | None:
    """The start hour whose finished done/partial sessions scored best (more sessions, then earlier, on a tie)."""
    by: dict[int, list] = {}
    for s, _, _ in sess:
        if s["status"] == "done" and s["verdict"] in ("done", "partial"):
            by.setdefault(dt.datetime.fromtimestamp(s["started_at"]).hour, []).append(float(s["on_task_ratio"] or 0))
    return max(by, key=lambda h: (sum(by[h]) / len(by[h]), len(by[h]), -h)) if by else None


def week(con, now: float | None = None) -> dict:
    """The last 7 days (oldest first, today so far last): pickups a day and their mean over the full earlier days
    (avg_day), pickups an hour per habit over its planned blocks and sessions (on days with phone data), what pulled
    it away, its best hour, and the habit that struggled."""
    now = _now(now)
    today = dt.date.fromtimestamp(now)
    first = today - dt.timedelta(days=6)
    days = [first + dt.timedelta(days=i) for i in range(7)]
    bounds = {d.isoformat(): _bounds(d) for d in days}
    w0, w1 = bounds[first.isoformat()][0], bounds[today.isoformat()][1]
    hi = max(w0, min(w1, now + SKEW_S))
    cfg = _cfg()
    phone_days = [k for k, (a, b) in bounds.items() if _has_phone(con, a, min(b, hi))]
    ph_iv = [(bounds[k][0], min(bounds[k][1], hi)) for k in phone_days]
    blocks = _blocks(con, first, 7, now, cfg)
    sess = _sessions(con, w0, w1, now)
    far = max([hi] + [end for _, end, _ in sess])
    picks = _pickups(con, w0, far)
    wins = _windows(con, w0, far)
    dist = _distractions(wins)
    bwin = [(b, w) for b in blocks if b["date"] in bounds and (w := _elapsed(b, *bounds[b["date"]], now))]

    rows = []
    for k, (a, b) in bounds.items():
        ph = k in phone_days
        biv = [w for bk, w in bwin if bk["date"] == k]
        seen = sum(s["declared_min"] * (s["on_task_ratio"] or 0) for s, _, _ in sess
                   if a <= s["started_at"] < b and s["status"] == "done")
        rows.append({"date": k, "pickups": _count(picks, [(a, min(b, hi))]) if ph else None,
                     "in_blocks_pickups": _count(picks, biv) if ph else None, "seen_min": round(seen)})
    # the week's "a day": earlier days the phone covered in full, never today so far or the evening sync began
    full = [r["pickups"] for r in rows[:-1] if r["pickups"] is not None and _full_day(con, *bounds[r["date"]])]
    avg_day = round(sum(full) / len(full), 1) if full else None

    present = {b["habit"] for b in blocks} | {s["habit"] for s, _, _ in sess}
    order = [k for k in cfg["habits"] if k in present] + sorted(present - set(cfg["habits"]))
    by_habit, stats = [], {}
    for k in order:
        hs = [x for x in sess if x[0]["habit"] == k]
        iv = signals._union([w for b, w in bwin if b["habit"] == k] + [seg for _, _, ivs in hs for seg in ivs])
        piv = _intersect(iv, ph_iv)
        secs = signals._len(piv)
        m = _count(picks, piv)
        stats[k] = (m, secs)
        by_habit.append({"habit": k, "label": config.display_name(k, cfg),
                         "pickups_per_hour": round(m / (secs / 3600), 1) if secs >= HABIT_HOUR_MIN_S else None,
                         "top_source": _top_source(con, hs, picks, dist), "best_hour": _best_hour(hs),
                         "sessions": len(hs)})
    cand = [h for h in by_habit if h["pickups_per_hour"] is not None and h["pickups_per_hour"] >= LINE["phone_away"]]
    worst = max(cand, key=lambda h: h["pickups_per_hour"], default=None)
    struggle = None
    if worst:
        struggle = {"habit": worst["habit"], "label": worst["label"], "per_hour": worst["pickups_per_hour"],
                    "reason": f"{round(worst['pickups_per_hour'])} pickups an hour during {worst['label']} this week."}

    out = []

    def add(rule, size, habit, text, why, agent=None):
        out.append((size, ORDER.index(rule), {"rule": rule, "habit": habit, "text": text, "agent_text": agent or text,
                                              "why": why}))
    if struggle:
        m, secs = stats[struggle["habit"]]
        add("phone_away", struggle["per_hour"] / LINE["phone_away"], struggle["habit"],
            f"Phone away for {struggle['label']}: {round(struggle['per_hour'])} pickups an hour during it this week.",
            f"{m} pickups in {round(secs / 60)} min of {struggle['label']} this week.")
    if phone_days:
        tot = [0] * 24
        for t in picks:
            if t < hi:
                tot[dt.datetime.fromtimestamp(t).hour] += 1
        h = max(range(24), key=lambda i: (tot[i], -i))
        per_day = tot[h] / len(phone_days)
        hits: dict[str, int] = {}
        for b, w in bwin:
            p0 = dt.datetime.combine(dt.date.fromisoformat(b["date"]), dt.time(h)).timestamp()
            if b["date"] in phone_days and min(w[1], p0 + 3600) > max(w[0], p0):
                hits[b["habit"]] = hits.get(b["habit"], 0) + 1
        k = max(hits, key=lambda x: hits[x], default=None)
        if per_day >= LINE["peak"] and k and hits[k] >= 2:
            label = config.display_name(k, cfg)
            add("peak", per_day / LINE["peak"] * WEIGHT["peak"], k,
                f"Don't plan {label} at {h:02d}:00: your phone peaks then ({round(per_day)} pickups a day).",
                f"{label} sat in that hour on {hits[k]} days this week.")
    sec = _secs(dist, [w for _, w in bwin])
    m = round(sum(sec.values()) / 60)
    if m >= LINE["mac_week"]:
        top, act = _top(sec)[:2], _guard_act()
        add("mac", m / LINE["mac_week"], None,
            f"{' and '.join(site_name(x) for x in top)} took {m} min of your plans this week. {act}",
            f"{m} min of {_kinds(top, cap=False)} inside planned blocks this week.",
            agent=f"{_kinds(top)} took {m} min of your plans this week. {act}")
    for hb in by_habit:
        bh = hb["best_hour"]
        planned = {dt.datetime.fromtimestamp(b["start"]).hour for b in blocks if b["habit"] == hb["habit"]}
        at = [s for s, _, _ in sess if s["habit"] == hb["habit"] and s["status"] == "done"
              and s["verdict"] in ("done", "partial") and dt.datetime.fromtimestamp(s["started_at"]).hour == bh]
        if bh is not None and planned and bh not in planned and len(at) >= 2:
            pct = round(100 * sum(float(s["on_task_ratio"] or 0) for s in at) / len(at))
            add("best_hour", 1.0, hb["habit"], f"{hb['label']} went best at {bh:02d}:00 this week. Plan it there.",
                f"{len(at)} sessions at {bh:02d}:00 averaged {pct}% on task.")
    out.sort(key=lambda x: (-x[0], x[1]))
    return {"days": rows, "avg_day": avg_day, "by_habit": by_habit, "struggle": struggle,
            "recommendations": [r for _, _, r in out[:MAX_RECS]]}
