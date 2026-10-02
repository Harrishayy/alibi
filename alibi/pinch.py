"""Pinch's rulebook: what the mascot is doing right now, computed once on the server so the dashboard, the island
and the iPhone react the same way and never double-fire. Everything Pinch says is built here.

    pinch_state(state) -> {"mood", "event", "seq", "age_s", "line", "moment"}
    phrase(plan_today, now, brief, tomorrow, last_end) -> {"text", "source", "situation", "ts", "slot", "kind", "model"}
    habits_line(changes, before, after, intent) -> str | None      (the "Noted. ..." line after a habits save)
    summary_line(plan_today) -> str                                  (Today's one chrome sentence, not Pinch's voice)

- mood: the held, looping pose: idle | focused | listening | thinking | sleepy | reading
- event: the latest one-shot clip: hello | sideeye | nudge | celebrate | partial | supportive | surprise | connected,
  or None
- seq: milliseconds of the moment that triggered `event` (it only grows). A client plays `event` once, when `seq`
  is bigger than the last one it played AND `age_s` is small (a page that loads late doesn't replay old news).
- line: Pinch's line for this moment, at most 12 words, or None.
- moment: what produced `event` (started | nudge | verdict | plan_done | planned | synced | habits_saved | brief), or None.

`state` is the dict /api/state builds ({now, session, alert, recent_verdict, plan_today?, ...}); /api/phone/session
passes the same keys minus plan_today. Stdlib only, no I/O: every input is passed in. Frequency caps (one one-shot per
90 s, three side-eyes per session) live in the engines. Copy rules: dry, digits, no "!", and
anything in Pinch's voice is 12 words or fewer; a line that runs over takes its fallback.
"""
from __future__ import annotations

import datetime as dt
import re
import time
import zlib

MOODS = ("idle", "focused", "listening", "thinking", "sleepy", "reading")
CLIPS = ("hello", "sideeye", "nudge", "celebrate", "partial", "supportive", "surprise", "connected")
MOMENTS = ("started", "nudge", "verdict", "plan_done", "planned", "synced", "habits_saved", "brief")

FRESH_S = 15 * 60          # an alert older than this no longer drives an event
JUST_STARTED_S = 30        # a session younger than this gets a thumbs-up
REPORT_READING_S = 10 * 60  # how long Pinch "reads" after the nightly report lands
BRIEF_READING_S = 90       # ... and after a note from the agent on the Spark
AGENT_PHRASE_S = 6 * 3600  # a brief this fresh can be the idle phrase
RISK_PHRASE_S = 2 * 3600   # ... but a heartbeat risk note is about the pace at that hour, so it goes stale sooner
LINE_S = {"brief": 30, "plan_done": 600}     # how long a moment's line shows; every other moment 120 s
MAX_WORDS = 12
LAST_BLOCK = " That was today's last block."
FALLBACK_PHRASE = "Say what you're about to do. I'll check it."


def _clock(ts: float | None) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%H:%M") if ts else ""


def _mins(seconds: float | None) -> int:
    return max(1, round((seconds or 0) / 60))


def _habit(d: dict | None) -> str:
    """'Drawing' → 'drawing' mid-sentence, but names like 'C++' or 'YouTube' keep their case (same rule as the web)."""
    if not d:
        return "it"
    h = d.get("habit_label") or d.get("label") or d.get("habit") or "it"
    return h.lower() if re.fullmatch(r"[A-Z][a-z]+( [a-z]+)*", h) else h


def _ok(line: str | None) -> bool:
    return bool(line) and len(line.split()) <= MAX_WORDS and "!" not in line


def _fit(line: str | None, *fallbacks: str | None) -> str | None:
    """The first of line, fallbacks... that is 12 words or fewer with no '!', else None."""
    return next((x for x in (line, *fallbacks) if _ok(x)), None)


def _seen(v: dict, finished: dict | None = None) -> str | None:
    """'23 of 25 min seen' from a verdict alert (minutes come from the finished session when it matches), else '92% on task'."""
    ratio = v.get("ratio", v.get("on_task_ratio"))
    declared = v.get("declared_min")
    if not declared and finished and finished.get("id") == v.get("session_id"):
        declared = finished.get("declared_min")
    if declared and ratio is not None:
        return f"{round(declared * ratio)} of {declared} min seen"
    if ratio is not None:
        return f"{round(ratio * 100)}% on task"
    return None


def _last_block(plan: dict | None, session_id) -> bool:
    """The verdict's session answered a block on today's plan, and nothing is left on it."""
    if not plan or session_id is None or plan.get("left") or (plan.get("total") or 0) < 1:
        return False
    return any(x.get("session_id") == session_id and not x.get("unplanned") for x in plan.get("done") or [])


def _event(alert: dict | None, session: dict | None, now: float, finished: dict | None = None,
           plan: dict | None = None) -> tuple[str | None, float | None, str | None, str | None]:
    """(clip, trigger_ts, line, moment) for the newest thing worth reacting to."""
    best: tuple[str | None, float | None, str | None, str | None] = (None, None, None, None)
    if alert and now - (alert.get("ts") or 0) <= FRESH_S:
        kind, ts = alert.get("kind"), alert.get("ts")
        if kind == "nudge":
            clip = "sideeye" if alert.get("label") == "phone" else "nudge"
            best = (clip, ts, alert.get("text"), "nudge")
        elif kind == "verdict":
            v = alert.get("verdict")
            seen = _seen(alert, finished)
            clip, line = {"done": ("celebrate", f"Done. {seen}." if seen else "Done. Logged."),
                          "partial": ("partial", f"Partly. {seen}." if seen else "Partly done. Logged."),
                          "slacked": ("supportive", f"Not this time. {seen}." if seen else "Not this time. Tomorrow?"),
                          }.get(v, (None, None))
            if clip and v in ("done", "partial") and _last_block(plan, alert.get("session_id")):
                best = (clip, ts, _fit(line + LAST_BLOCK, line), "plan_done")     # same clip and seq: never replays
            elif clip:
                best = (clip, ts, line, "verdict")
        elif kind == "planned":
            best = ("hello", ts, f"It's time for {_habit(alert)}.", "planned")
        elif kind == "info" and str(alert.get("text", "")).startswith("Strava:"):
            best = ("connected", ts, "Run synced from Strava.", "synced")
        elif kind == "synced":
            text = str(alert.get("text") or "")
            best = ("connected", ts, text if _ok(text) else "Your iPhone checked in.", "synced")
        elif kind == "habits_saved":
            text = str(alert.get("text") or "")
            best = ("surprise", ts, text if _ok(text) else "Noted.", "habits_saved")
        elif kind == "brief":
            best = ("connected", ts, "A note from your agent.", "brief")
    started = (session or {}).get("started_at")
    if started and now - started <= JUST_STARTED_S and (best[1] is None or started > best[1]):
        best = ("connected", started, f"On it. Watching {_habit(session)}.", "started")
    return best


def _mood(state: dict, now: float) -> tuple[str, str | None]:
    s = state.get("session")
    if s:
        if s.get("on_break"):
            back = s["on_break"].get("until")
            return "sleepy", f"Break. Back at {_clock(back)}." if back else "On a break."
        d = s.get("drifting")
        if d:
            return "thinking", f"Hm. {d.get('label_text') or d.get('label', 'something else')} for {_mins(d.get('since_s'))} min."
        if not s.get("samples"):
            return "listening", f"Watching {_habit(s)}. First check in a minute."
        ends = s.get("ends_at")
        return "focused", f"Watching {_habit(s)} until {_clock(ends)}." if ends else f"Watching {_habit(s)}."
    a = state.get("alert") or {}
    if a.get("kind") == "brief" and now - (a.get("ts") or 0) <= BRIEF_READING_S:
        return "reading", "Reading your agent's note."
    if a.get("kind") == "report" and now - (a.get("ts") or 0) <= REPORT_READING_S:
        return "reading", "Reading tonight's report."
    hour = dt.datetime.fromtimestamp(now).hour
    if hour >= 23 or hour < 6:
        return "sleepy", None
    return "idle", None


def pinch_state(state: dict | None) -> dict:
    state = state or {}
    now = float(state.get("now") or time.time())
    mood, mood_line = _mood(state, now)
    clip, ts, clip_line, moment = _event(state.get("alert"), state.get("session"), now, state.get("recent_verdict"),
                                         state.get("plan_today"))
    return {
        "mood": mood,
        "event": clip,
        "seq": int(ts * 1000) if ts else 0,
        "age_s": round(now - ts, 1) if ts else None,
        "line": clip_line if clip and now - ts <= LINE_S.get(moment, 120) else mood_line,
        "moment": moment if clip else None,
    }


# --- the idle phrase -----------------------------------------------------------------------------------------------

PHRASES = {   # situation -> pool. The first matching situation wins, in this order.
    "live": ("After this, {h} at {t}.", "This is the last block on today's plan."),
    "now": ("{H} is planned now. {m} minutes, then it's done.", "It's {t}. {H} now, and I'll keep the receipt.",
            "{H} now. Start small; every minute you show up counts."),
    "now_source": ("{H} is planned now. {src} will tell me how it went.",),
    "next": ("{H} at {t}. Keep the promise; I'll keep the receipt.", "Next: {h} at {t}. {m} minutes is plenty.",
             "Curiosity's easy. Devotion is {h} at {t}.", "{m} minutes of {h} beats an hour of meaning to.",
             "{n} left today. First up, {h} at {t}.", "Morning. {n} on today's plan, first {h} at {t}."),
    "late": ("Late one. Tomorrow: {h2} at {t2}.", "Sleep counts too. {H2} at {t2} tomorrow.", "Day's done. Sleep well."),
    "all_kept": ("That's today's plan done. Every block has a receipt.", "All {N} kept today. I've got the receipts.",
                 "{N} of {N} today. Promises kept, receipts filed."),
    "some_kept": ("{k} of {N} kept today. Tomorrow's another go.", "{k} of {N} kept today. Small wins still count."),
    "none_kept": ("Today slipped. Tomorrow starts with {h2} at {t2}.",
                  "Not today. {H2} at {t2} tomorrow is a clean start.", "Not today. Tomorrow's a fresh page."),
    # Only Strava/Health blocks are open and their data isn't in yet: claiming it slipped would be a guess.
    "checking": ("Waiting on {src} to confirm {h}.",),
    "rest": ("Nothing planned today. Rest is part of the plan.", "No blocks today. Say what you're doing and I'll check.",
             "A free day. Next up: {h2} at {t2} tomorrow."),
    "unscheduled": ("Give a habit a time and I'll plan around it.", "Say what you're about to do. I'll check it."),
}
PHRASE_FALLBACK = {"live": "After this, {h} at {t}.", "now": "{H} is planned now.", "now_source": "{H} is planned now.",
                   "next": "Next: {h} at {t}.", "checking": "Waiting on {src}."}
SOURCE_WORDS = {"strava": "Strava", "health": "Apple Health"}


def clean_brief(text, sentences: int = 1, cap: int = 140) -> str:
    """The agent's words as Alibi shows them: whitespace collapsed, markdown markers and '!' gone, the first
    `sentences` sentences (a '.' or '?' followed by a space or the end, so '5.2 km' stays whole), cut at a word
    boundary with '…' past `cap` characters."""
    t = re.sub(r"\s+", " ", str(text or "")).strip().replace("**", "").replace("__", "")
    t = re.sub(r"^(?:#+\s*|-\s+)+", "", t).strip()
    t = re.sub(r"([.?])?!+", lambda m: m.group(1) or ".", t)
    ends = [m.end() for m in re.finditer(r"[.?](?=\s|$)", t)]
    if len(ends) >= sentences:
        t = t[:ends[sentences - 1]]
    t = t.strip()
    if len(t) > cap:
        cut = t[:cap - 1]
        cut = cut.rsplit(" ", 1)[0] if " " in cut else cut
        t = cut.rstrip(" ,;:-–—") + "…"
    return t


def _brief_ok(brief: dict | None, now: float, last_end: float | None) -> bool:
    """The agent's latest note can stand in for the rules phrase: it was shown as the agent's (a late one is only
    stored), it's fresh (6 h; 2 h for a risk note), and nothing newer has happened since (`last_end`: a session ended
    or the habits were saved)."""
    if not isinstance(brief, dict) or not isinstance(brief.get("ts"), (int, float)):
        return False
    if (brief.get("response") or {}).get("shown_as") not in (None, "agent"):
        return False
    window = RISK_PHRASE_S if brief.get("kind") == "risk" else AGENT_PHRASE_S
    return brief["ts"] >= now - window and (last_end is None or last_end <= brief["ts"])


def _subs(item: dict | None = None, tomorrow: dict | None = None, **extra) -> dict:
    d = dict(extra)
    if item:
        d.update(h=_habit(item), H=item.get("label") or item.get("habit") or "it", t=item.get("at") or "",
                 m=item.get("minutes", item.get("min")), src=SOURCE_WORDS.get(item.get("check"), "Alibi"))
    if tomorrow:
        d.update(h2=_habit(tomorrow), H2=tomorrow.get("label") or tomorrow.get("habit") or "it",
                 t2=tomorrow.get("at") or "")
    return d


def _pool(templates, subs: dict, fallback: str | None = None) -> list[str]:
    """Templates that can be filled and fit, else the situation's fallback (when that fits)."""
    out = []
    for tpl in templates:
        try:
            line = tpl.format(**subs)
        except (KeyError, IndexError, ValueError):
            continue
        if _ok(line):
            out.append(line)
    if not out and fallback:
        try:
            line = fallback.format(**subs)
        except (KeyError, IndexError, ValueError):
            line = None
        if _ok(line):
            out.append(line)
    return out


def _situation(plan: dict | None, now: float, tomorrow: dict | None, live: bool) -> tuple[str, list[str]]:
    """(situation, the lines that can be said) — in this order: live, now, next, late, end of day, rest,
    unscheduled."""
    if not plan:
        return "unknown", [FALLBACK_PHRASE]
    left, done = plan.get("left") or [], plan.get("done") or []
    total, kept = plan.get("total") or 0, plan.get("kept") or 0
    nxt = plan.get("next")
    hour = dt.datetime.fromtimestamp(now).hour
    t2 = tomorrow if isinstance(tomorrow, dict) and tomorrow.get("at") else None
    live_item = next((x for x in left if x.get("status") == "live"), None)
    after = next((x for x in left if x.get("status") in ("next", "later")), None) or \
        next((x for x in left if x.get("status") == "now"), None)
    if live_item or (live and after):
        tpl = PHRASES["live"][:1] if after else PHRASES["live"][1:]
        return "live", _pool(tpl, _subs(after), PHRASE_FALLBACK["live"] if after else None)
    if nxt and nxt.get("status") == "now":
        if nxt.get("check") in SOURCE_WORDS:
            return "now", _pool(PHRASES["now_source"], _subs(nxt), PHRASE_FALLBACK["now_source"])
        tpl = list(PHRASES["now"])
        if now - (nxt.get("start") or now) >= 300:       # "It's 21:00." stops being true a few minutes in
            tpl.remove(PHRASES["now"][1])
        return "now", _pool(tpl, _subs(nxt), PHRASE_FALLBACK["now"])
    if nxt and nxt.get("status") == "next":
        n, m = len(left), nxt.get("minutes") or 0
        src = nxt.get("check") in SOURCE_WORDS
        p = PHRASES["next"]
        tpl = [p[0], p[2]] + ([p[1]] if not src else []) + ([p[3]] if not src and m < 60 else []) + \
            ([p[4]] if n >= 2 else []) + ([p[5]] if n >= 2 and 5 <= hour < 10 else [])
        return "next", _pool(tpl, _subs(nxt, n=n), PHRASE_FALLBACK["next"])
    if not left:
        if hour >= 22 or hour < 6:
            p = PHRASES["late"]
            # After midnight, "tomorrow" would read as the day that has already started: no tomorrow lines then.
            tpl = ([p[0], p[1]] if t2 and hour >= 22 else []) + [p[2]]
            return "late", _pool(tpl, _subs(tomorrow=t2))
        if total >= 1:
            if kept >= total:
                p = PHRASES["all_kept"]
                return "all_kept", _pool([p[0], p[2]] + ([p[1]] if total >= 2 else []), _subs(N=total))
            if kept >= 1:
                return "some_kept", _pool(PHRASES["some_kept"], _subs(k=kept, N=total))
            checking = plan.get("checking") or []
            if checking and not plan.get("missed") and not done:
                return "checking", _pool(PHRASES["checking"], _subs(checking[0]), PHRASE_FALLBACK["checking"])
            p = PHRASES["none_kept"]
            return "none_kept", _pool(([p[0], p[1]] if t2 else []) + [p[2]], _subs(tomorrow=t2))
        if plan.get("scheduled"):
            p = PHRASES["rest"]
            return "rest", _pool([p[0], p[1]] + ([p[2]] if t2 else []), _subs(tomorrow=t2))
        return "unscheduled", _pool(PHRASES["unscheduled"], {})
    return "unknown", [FALLBACK_PHRASE]


def _pick(pool: list[str], now: float, situation: str) -> str:
    """Stable for the whole hour (crc32, never hash(): that's salted per process), new when the hour or the situation
    changes."""
    if not pool:
        return FALLBACK_PHRASE
    d = dt.datetime.fromtimestamp(now)
    return pool[zlib.crc32(f"{d.date().isoformat()}|{d.hour}|{situation}".encode()) % len(pool)]


def phrase(plan: dict | None, now: float | None = None, brief: dict | None = None, tomorrow: dict | None = None,
           last_end: float | None = None, live: bool = False) -> dict:
    """Pinch's ambient line, never None. The agent's latest shown brief wins when it's fresh, nothing newer has
    happened since (`last_end`: the last session end or habits save) and no block is open right now; otherwise a
    rules line for the situation."""
    now = float(now or time.time())
    situation, pool = _situation(plan, now, tomorrow, live)
    if situation not in ("live", "now") and _brief_ok(brief, now, last_end):
        text = clean_brief(brief.get("text"), 1, 140)
        if text:
            return {"text": text, "source": "agent", "situation": "agent", "ts": float(brief["ts"]),
                    "slot": brief.get("slot"), "kind": brief.get("kind"), "model": brief.get("model") or None}
    hour0 = dt.datetime.fromtimestamp(now).replace(minute=0, second=0, microsecond=0).timestamp()
    return {"text": _pick(pool, now, situation), "source": "rules", "situation": situation, "ts": hour0,
            "slot": None, "kind": None, "model": None}


# --- Today's summary (chrome) -------------------------------------------------------------------------------------

def _item_text(x: dict) -> str:
    return f"{_habit(x)} now" if x.get("status") in ("live", "now") else f"{_habit(x)} at {x.get('at')}"


def summary_line(plan: dict | None) -> str:
    if not plan:
        return ""
    left = plan.get("left") or []
    total = plan.get("total") or 0
    if total == 0:
        return "Nothing planned today." if plan.get("scheduled") else "No set times yet."
    if not left:
        return f"Nothing left today. {plan.get('kept') or 0} of {total} kept."
    n = len(left)
    if n > 3:
        return f"{n} left, starting with {_item_text(left[0])}."
    items = [_item_text(x) for x in left]
    return f"{n} left: " + (items[0] if n == 1 else ", ".join(items[:-1]) + " and " + items[-1]) + "."


# --- habits saved -------------------------------------------------------------------------------------------------

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_WORDS = {"daily": DAYS, "every day": DAYS, "everyday": DAYS, "weekdays": DAYS[:5], "weekends": DAYS[5:],
             "weekend": DAYS[5:]}
METRIC_FMT = {"steps": "{v:,.0f} steps", "sleep_h": "{v:.1f} h of sleep", "mindful_min": "{v:.0f} mindful min",
              "workout_min": "{v:.0f} workout min"}     # health.fmt_metric, kept here so pinch stays I/O-free
STARTABLE = ("camera", "screen", "both")
CHECK_LINE = {"camera": "Noted. I'll use the desk camera for {h} now.",
              "screen": "Noted. I'll watch your screen for {h} now.",
              "both": "Noted. I'll check camera and screen for {h} now."}
WHAT_ORDER = ("added", "restored", "removed", "name", "check", "days", "time", "schedule", "unscheduled", "length",
              "goal", "calendar", "phone_shield", "other")


def kind_of(h: dict | None) -> str:
    """camera | screen | both | strava | health (calendar_sync.kind_of, I/O-free)."""
    h = h or {}
    if h.get("source") in ("strava", "health"):
        return h["source"]
    return {"physical": "camera", "digital": "screen", "hybrid": "both"}.get(h.get("modality", ""), "camera")


def day_list(v) -> list[str]:
    if isinstance(v, str):
        v = DAY_WORDS.get(v.strip().lower(), [x for x in re.split(r"[,\s]+", v) if x])
    got = {str(d).strip().lower()[:3] for d in (v or [])}
    return [d for d in DAYS if d in got]


def days_text(days) -> str | None:
    """'every day', 'weekdays', 'weekends', 'Fri', 'Tue and Thu', 'Mon, Wed and Fri'; None for five or more named
    days (the line then says how many)."""
    d = day_list(days)
    if len(d) == 7:
        return "every day"
    if d == list(DAYS[:5]):
        return "weekdays"
    if d == list(DAYS[5:]):
        return "weekends"
    if not d or len(d) >= 5:
        return None
    names = [x.capitalize() for x in d]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _rows(h: dict | None) -> list[dict]:
    rows = (h or {}).get("schedule") or []
    return [r for r in (rows if isinstance(rows, list) else [rows]) if isinstance(r, dict)]


def _num(v) -> str:
    try:
        return f"{float(v):g}"
    except (TypeError, ValueError):
        return str(v)


def _metric(metric, v) -> str | None:
    try:
        return METRIC_FMT[metric].format(v=float(v)).replace(".0 ", " ")
    except (KeyError, TypeError, ValueError):
        return None


def _spoken(key: str, label: str) -> str:
    """config.spoken_name, said mid-sentence: 'piano' for Piano, 'guitar' for a habit renamed Guitar, but 'C++' and
    other real names as written (the parser matches the label in any case)."""
    plain = (key or "").replace("_", " ")
    return plain if label == plain.capitalize() else _habit({"label": label})


def _days_line(H: str, row: dict) -> str | None:
    d = day_list(row.get("days"))
    words = days_text(d)
    t = row.get("at")
    return _fit(f"Noted. {H} is on {words} at {t}." if words else None, f"Noted. {H} is {len(d)} days a week at {t}.")


def habits_line(changes: list | None, before: dict | None = None, after: dict | None = None,
                intent: str | None = None) -> str | None:
    """Pinch's line for a habits save; the same string becomes the island alert's text. None when nothing changed.
    `before`/`after` are the habits maps ({key: entry}) around the save."""
    if not changes:
        return None
    if intent == "undo":
        return "Back as it was."
    if len(changes) > 1:
        return _fit(f"Noted. {len(changes)} habits changed; the plan follows.", "Noted.")
    c = changes[0]
    key, what = c.get("habit") or "", set(c.get("what") or [])
    b, a = (before or {}).get(key) or {}, (after or {}).get(key) or {}
    h = a or b
    H = c.get("label") or key.replace("_", " ").capitalize() or "It"
    hh = _habit({"label": H})
    kind, rows = kind_of(h), _rows(h)
    m = h.get("default_min")
    upd = _fit(f"Noted. {H} is updated.", "Noted.")
    if what & {"added", "restored"}:
        if len(rows) == 1:
            line = _days_line(H, rows[0])
        elif rows:
            line = _fit(f"Noted. {H} is on your plan {sum(len(day_list(r.get('days'))) for r in rows)} times a week.",
                        f"Noted. {H} is on your plan.")
        elif kind in STARTABLE:
            line = _fit(f"Noted. Say “{_spoken(key, H)} for {m}” to start it.")
        elif kind == "strava":
            line = _fit(f"Noted. Runs of {_num(h.get('min_km', 5))} km or more count.")
        else:
            line = _fit(f"Noted. {H} comes from Apple Health each night.", f"Noted. {H} is on your list.")
        return line or upd
    if "removed" in what:
        return _fit(f"{H} is off the plan. Past sessions stay put.", "Noted.")
    if "name" in what:
        return (_fit(f"Noted. Say “{_spoken(key, H)} for {m}” to start it.") if kind in STARTABLE and m else None) or upd
    if "check" in what:
        return _fit(CHECK_LINE[kind].format(h=hh)) if kind in CHECK_LINE else upd
    if "days" in what and len(rows) == 1:
        return _days_line(H, rows[0]) or upd
    if "time" in what and len(rows) == 1:
        return _fit(f"Noted. {H} moves to {rows[0].get('at')}.") or upd
    if "schedule" in what and rows:
        return _fit(f"Noted. {H} is on your plan {sum(len(day_list(r.get('days'))) for r in rows)} times a week.",
                    f"Noted. {H} is on your plan.") or upd
    if "unscheduled" in what:
        return _fit(f"Noted. {H} has no set time now.") or upd
    if "length" in what:
        mins = a.get("default_min") if a.get("default_min") != b.get("default_min") else \
            (rows[0].get("min") if len(rows) == 1 else m)
        return (_fit(f"Noted. {H} sessions are {mins} minutes now.") if mins else None) or upd
    if "goal" in what:
        if kind == "strava":
            line = _fit(f"Noted. {h.get('weekly_sessions', 3)} runs a week, {_num(h.get('min_km', 5))} km or more.")
        elif kind == "health":
            v = _metric(h.get("metric"), h.get("daily_target"))
            line = _fit(f"Noted. New daily goal for {hh}: {v}.") if v else None
        else:
            line = _fit(f"Noted. {h.get('weekly_target_min') or 0} minutes a week for {hh}.")
        return line or upd
    if "calendar" in what:
        on = h.get("calendar", True) is not False
        return _fit(f"Noted. {H} goes in Apple Calendar." if on else f"Noted. {H} stays off Apple Calendar.") or upd
    if "phone_shield" in what:
        on = h.get("phone_shield", True) is not False
        return _fit(f"Noted. Your iPhone blocks distractions during {hh}." if on
                    else f"Noted. Your iPhone stays open during {hh}.") or upd
    return upd


def from_db(con) -> dict:
    """pinch_state() for callers outside /api/state (the phone listener), built from the same helpers."""
    from . import api, db
    from .notify import recent_alerts
    s = db.active_session(con)
    alerts = recent_alerts(1)
    return pinch_state({"now": time.time(), "session": api._session_json(con, s, live=True) if s else None,
                        "alert": alerts[-1] if alerts else None,
                        "recent_verdict": None if s else api._recent_verdict(con)})


# --- self-test ------------------------------------------------------------------------------------------------------

EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")


def _clean(line: str | None) -> bool:
    return _ok(line) and not EMOJI.search(line)


def _selftest() -> None:
    now = 1_790_870_000.0
    idle = pinch_state({"now": now})
    assert idle["mood"] in MOODS and idle["event"] is None and idle["seq"] == 0 and idle["moment"] is None, idle
    live = {"now": now, "session": {"habit": "drawing", "label": "Drawing", "started_at": now - 600,
                                    "ends_at": now + 900, "samples": 8}}
    assert pinch_state(live)["mood"] == "focused"
    assert pinch_state(live)["line"].startswith("Watching drawing until"), pinch_state(live)
    cpp = {**live, "session": {**live["session"], "habit": "cpp", "label": "C++"}}
    assert pinch_state(cpp)["line"].startswith("Watching C++ until"), pinch_state(cpp)
    fresh = {**live, "session": {**live["session"], "started_at": now - 5, "samples": 0}}
    r = pinch_state(fresh)
    assert r["mood"] == "listening" and r["event"] == "connected" and r["seq"] == int((now - 5) * 1000), r
    assert r["moment"] == "started", r
    drift = {**live, "session": {**live["session"], "drifting": {"label": "phone", "label_text": "Phone", "since_s": 190}}}
    assert pinch_state(drift)["mood"] == "thinking"
    nudge = {**drift, "alert": {"kind": "nudge", "label": "phone", "ts": now - 3,
                                "text": "You said drawing. I've seen your phone for 3 minutes."}}
    r = pinch_state(nudge)
    assert r["event"] == "sideeye" and r["line"].startswith("You said drawing") and r["moment"] == "nudge", r
    brk = {**live, "session": {**live["session"], "on_break": {"until": now + 240, "left_s": 240}}}
    assert pinch_state(brk)["mood"] == "sleepy"
    for v, clip in (("done", "celebrate"), ("partial", "partial"), ("slacked", "supportive")):
        r = pinch_state({"now": now, "alert": {"kind": "verdict", "verdict": v, "ts": now - 2, "declared_min": 25,
                                              "ratio": 0.92}})
        assert r["event"] == clip and r["mood"] in MOODS and r["moment"] == "verdict", r
    r = pinch_state({"now": now, "alert": {"kind": "verdict", "verdict": "done", "ts": now - 2, "declared_min": 25,
                                          "ratio": 0.92}})
    assert r["line"] == "Done. 23 of 25 min seen.", r
    r = pinch_state({"now": now, "alert": {"kind": "verdict", "verdict": "done", "ts": now - 2, "session_id": 7,
                                          "ratio": 0.92}, "recent_verdict": {"id": 7, "declared_min": 25}})
    assert r["line"] == "Done. 23 of 25 min seen.", r
    r = pinch_state({"now": now, "alert": {"kind": "verdict", "verdict": "partial", "ts": now - 2, "ratio": 0.5}})
    assert r["line"] == "Partly. 50% on task.", r
    r = pinch_state({"now": now, "alert": {"kind": "verdict", "verdict": "slacked", "ts": now - 2, "declared_min": 25,
                                          "ratio": 0.3}})
    assert r["line"] == "Not this time. 8 of 25 min seen.", r
    stale = pinch_state({"now": now, "alert": {"kind": "verdict", "verdict": "done", "ts": now - FRESH_S - 1}})
    assert stale["event"] is None and stale["moment"] is None, stale
    strava = pinch_state({"now": now, "alert": {"kind": "info", "text": "Strava: Morning run, 5.1 km — logged.",
                                               "ts": now - 1}})
    assert strava["event"] == "connected" and strava["moment"] == "synced", strava
    synced = pinch_state({"now": now, "alert": {"kind": "synced", "source": "health", "ts": now - 2,
                                               "text": "Your iPhone checked in: steps 2,022."}})
    assert synced["event"] == "connected" and synced["line"].startswith("Your iPhone"), synced
    a, b = pinch_state(nudge), pinch_state({**nudge, "now": now + 1})
    assert a["seq"] == b["seq"], "the same alert must keep the same seq across polls"
    for r in (idle, pinch_state(live), pinch_state(nudge)):
        assert r["line"] is None or _ok(r["line"]), r

    # --- moments: brief, habits_saved, plan_done --------------------------------------------------------------------
    brief = {"kind": "brief", "ts": now - 4, "text": "Drawing is 30 min behind this week. 19:00 tomorrow is free.",
             "habit_label": "Your agent", "slot": "2026-10-02-night"}
    r = pinch_state({"now": now, "alert": brief})
    assert (r["event"], r["moment"], r["mood"], r["line"]) == ("connected", "brief", "reading",
                                                               "A note from your agent."), r
    r2 = pinch_state({"now": now + 40, "alert": brief})
    assert r2["seq"] == r["seq"] and r2["mood"] == "reading" and r2["line"] == "Reading your agent's note.", r2
    r3 = pinch_state({"now": now + 120, "alert": brief})
    assert r3["mood"] != "reading" and r3["line"] is None and r3["moment"] == "brief", r3
    assert pinch_state({**live, "alert": brief})["mood"] == "focused", "a live session outranks the note"
    saved = {"kind": "habits_saved", "ts": now - 1, "text": "Noted. Piano is on Tue and Thu at 21:00.", "habit": "piano"}
    r = pinch_state({"now": now, "alert": saved})
    assert (r["event"], r["moment"], r["line"]) == ("surprise", "habits_saved", saved["text"]), r
    assert pinch_state({"now": now + 121, "alert": saved})["line"] is None, "habits line shows for 120 s"
    pt = {"total": 2, "kept": 2, "left": [], "done": [{"session_id": 41, "status": "done", "verdict": "done"},
                                                       {"session_id": 40, "status": "done", "verdict": "partial"}]}
    v = {"kind": "verdict", "verdict": "done", "ts": now - 3, "session_id": 41, "declared_min": 25, "ratio": 0.92}
    r = pinch_state({"now": now, "alert": v, "plan_today": pt})
    assert (r["event"], r["moment"], r["line"]) == ("celebrate", "plan_done",
                                                    "Done. 23 of 25 min seen. That was today's last block."), r
    assert r["seq"] == pinch_state({"now": now, "alert": v})["seq"], "plan_done reuses the verdict's seq"
    assert pinch_state({"now": now + 400, "alert": v, "plan_today": pt})["line"].endswith("last block."), "600 s"
    assert pinch_state({"now": now + 400, "alert": v})["line"] is None, "a plain verdict line goes after 120 s"
    assert pinch_state({"now": now, "alert": v, "plan_today": {**pt, "left": [{"status": "later"}]}})["moment"] == \
        "verdict", "something still left: a plain verdict"
    assert pinch_state({"now": now, "alert": {**v, "session_id": 99}, "plan_today": pt})["moment"] == "verdict", \
        "an unplanned session: a plain verdict"
    off = {**pt, "done": [dict(x, unplanned=x["session_id"] == 41) for x in pt["done"]]}
    assert pinch_state({"now": now, "alert": v, "plan_today": off})["moment"] == "verdict", \
        "kept off the plan (listed in done as unplanned): never the day's last block"
    assert pinch_state({"now": now, "alert": {**v, "verdict": "slacked"}, "plan_today": pt})["moment"] == "verdict"

    # --- every template with worst-case values: a 3-word 24-character label, 240 min, 21:00, 12 items ---------------
    lab = "Morning guitar practices"
    assert len(lab) == 24 and len(lab.split()) == 3
    worst = dict(h=_habit({"label": lab}), H=lab, t="21:00", m=240, n=12, N=12, k=11, h2=_habit({"label": lab}),
                 H2=lab, t2="07:30", src="Apple Health")
    for sit, pool in PHRASES.items():
        lines = _pool(pool, worst, PHRASE_FALLBACK.get(sit))
        assert lines and all(_clean(x) for x in lines), (sit, lines)
    for tpl in [x for pool in PHRASES.values() for x in pool] + list(PHRASE_FALLBACK.values()):
        line = tpl.format(**worst)
        assert "!" not in line and not EMOJI.search(line), line          # over 12: dropped from its pool
    moment_lines = ["A note from your agent.", "Reading your agent's note.", f"On it. Watching {worst['h']}.",
                    f"It's time for {worst['h']}.", "Done. 240 of 240 min seen." + LAST_BLOCK,
                    "Partly. 100% on task." + LAST_BLOCK, "Done. Logged." + LAST_BLOCK]
    assert all(_clean(x) for x in moment_lines), moment_lines

    # situations, end to end, with the worst-case label and with a plain one
    def item(status, label=lab, at="21:00", minutes=240, check="camera", sid=None, start=now + 600, verdict=None):
        return {"key": f"x@{at}", "habit": "x", "label": label, "at": at, "minutes": minutes, "check": check,
                "status": status, "start": start, "session_id": sid, "verdict": verdict}

    tmw = {"label": lab, "habit": "x", "at": "07:30"}

    def plan(left=(), done=(), missed=(), checking=(), scheduled=True):
        left, done = list(left), list(done)
        nxt = next((x for x in left if x["status"] == "now"), None) or next((x for x in left if x["status"] == "next"),
                                                                             None)
        return {"left": left, "done": done, "missed": list(missed), "checking": list(checking), "next": nxt,
                "total": len(left) + len(done) + len(missed) + len(checking), "scheduled": scheduled,
                "kept": sum(x.get("verdict") in ("done", "partial") for x in done)}

    day = dt.datetime.fromtimestamp(now).replace(minute=0, second=0, microsecond=0)
    at = lambda h, mi=0: day.replace(hour=h, minute=mi).timestamp()
    many = [item("next")] + [item("later", start=now + 900 + i) for i in range(11)]
    cases = {
        "live": (plan([item("live", sid=5), item("next")]), at(15)),
        "now": (plan([item("now", start=at(15))]), at(15, 2)),
        "next": (plan(many), at(15)),
        "late": (plan(done=[item("done", verdict="done")]), at(22, 30)),
        "all_kept": (plan(done=[item("done", verdict="done")] * 12), at(15)),
        "some_kept": (plan(done=[item("done", verdict="done")] * 11, missed=[item("missed")]), at(15)),
        "none_kept": (plan(missed=[item("missed")] * 12), at(15)),
        "checking": (plan(checking=[item("checking", check="health")]), at(15)),
        "rest": (plan(), at(15)),
        "unscheduled": (plan(scheduled=False), at(15)),
    }
    for want, (p, t) in cases.items():
        for label in (lab, "C++"):
            if label != lab:
                p = {**p, **{k: [dict(x, label=label) for x in p[k]] for k in ("left", "done", "missed", "checking")}}
                p["next"] = p["left"][0] if p["left"] and p["left"][0]["status"] in ("now", "next") else None
            got = phrase(p, t, tomorrow=tmw)
            assert got["situation"] == want and got["source"] == "rules" and _clean(got["text"]), (want, got)
            h0 = dt.datetime.fromtimestamp(t).replace(minute=0, second=0, microsecond=0)
            m05, m55 = ((h0 + dt.timedelta(minutes=x)).timestamp() for x in (5, 55))
            if want != "now":                                    # stable within the hour ("now" drops "It's 21:00")
                assert phrase(p, m05, tomorrow=tmw)["text"] == phrase(p, m55, tomorrow=tmw)["text"], (want, label)
    nxt_plan = cases["next"][0]
    texts = {phrase(nxt_plan, at(h, 30), tomorrow=tmw)["text"] for h in range(10, 22)}
    assert len(texts) > 1, "the next hour can differ"
    assert phrase(nxt_plan, at(15, 5))["text"] == phrase(nxt_plan, at(15, 55))["text"], "minute 05 == minute 55"
    assert phrase(None, at(15))["text"] == FALLBACK_PHRASE, "no plan: still a line"
    late_after_midnight = phrase(plan(done=[item("done", verdict="done")]), at(1), tomorrow=tmw)
    assert late_after_midnight["situation"] == "late" and late_after_midnight["text"] == "Day's done. Sleep well."
    src_now = phrase(plan([item("now", check="strava", label="Running", start=at(15))]), at(15, 1))
    assert src_now["text"] == "Running is planned now. Strava will tell me how it went.", src_now
    assert phrase(plan([item("now", check="health", start=at(15))]), at(15, 1))["text"] == f"{lab} is planned now."
    assert "It's 21:00" not in phrase(plan([item("now", start=at(15))]), at(15, 40))["text"]

    # agent phrase: fresh brief, first sentence, cleaned; stale or answered by a later session -> rules
    b = {"ts": at(15), "slot": "2026-10-02-risk-15", "kind": "risk", "model": "nvidia/nemotron-3-super-120b-a12b",
         "text": "**Drawing** is 5.2 km… no: 30 min behind this week! 19:00 tomorrow is free."}
    got = phrase(nxt_plan, at(15, 10), brief=b)
    assert got["source"] == "agent" and got["situation"] == "agent" and got["slot"] == b["slot"], got
    assert got["text"] == "Drawing is 5.2 km… no: 30 min behind this week.", got
    assert phrase(nxt_plan, at(15, 10), brief=b, last_end=at(15, 5))["source"] == "rules", "a session ended since"
    assert phrase(nxt_plan, at(22, 1), brief=b)["source"] == "rules", "older than 6 h"
    assert phrase(nxt_plan, at(16, 55), brief=b)["source"] == "agent", "a risk note holds for 2 h"
    assert phrase(nxt_plan, at(17, 5), brief=b)["source"] == "rules", "a risk note is stale after 2 h"
    assert phrase(nxt_plan, at(17, 5), brief={**b, "kind": "night"})["source"] == "agent", "other briefs hold for 6 h"
    assert phrase(nxt_plan, at(15, 10), brief={**b, "response": {"shown_as": "stored"}})["source"] == "rules", \
        "a late (stored) brief is never the phrase"
    assert phrase(nxt_plan, at(15, 10), brief={**b, "response": {"shown_as": "agent"}})["source"] == "agent"
    assert phrase(cases["now"][0], at(15, 2), brief=b)["source"] == "rules", "a block open now outranks the note"
    assert clean_brief("- " + "word " * 60, 1, 140).endswith("…") and len(clean_brief("word " * 60, 1, 140)) <= 140
    assert clean_brief("One. Two? Three.", 2, 160) == "One. Two?"
    assert clean_brief("Wow!! Great?! Yes.", 2, 160) == "Wow. Great?"

    # --- summary (chrome) --------------------------------------------------------------------------------------------
    pl = lambda *items: plan([item(s, label=n, at=t) for s, n, t in items])
    assert summary_line(plan(scheduled=False)) == "No set times yet."
    assert summary_line(plan()) == "Nothing planned today."
    assert summary_line(plan(done=[item("done", verdict="done")], missed=[item("missed")])) == \
        "Nothing left today. 1 of 2 kept."
    assert summary_line(pl(("next", "Drawing", "19:00"))) == "1 left: drawing at 19:00."
    assert summary_line(pl(("now", "Piano", "21:00"), ("next", "Drawing", "22:00"))) == \
        "2 left: piano now and drawing at 22:00."
    assert summary_line(pl(("next", "Drawing", "15:00"), ("later", "C++", "18:00"), ("later", "Math", "20:00"))) == \
        "3 left: drawing at 15:00, C++ at 18:00 and math at 20:00."
    assert summary_line(plan(many)).startswith("12 left, starting with")

    # --- habits lines: every rule, worst case --------------------------------------------------------------------
    cam = {"modality": "physical", "default_min": 240, "weekly_target_min": 3000,
           "schedule": [{"days": ["mon", "tue", "wed", "thu"], "at": "21:00", "min": 240}]}
    one = lambda what, b=None, a=None, key="morning_guitar_practices", label=lab: habits_line(
        [{"habit": key, "label": label, "what": what}], {key: b or cam}, {key: a or cam})
    lines = {
        "undo": habits_line([{"habit": "x", "label": lab, "what": ["restored"]}], {}, {"x": cam}, "undo"),
        "several": habits_line([{"habit": "a", "label": "A", "what": ["days"]}] * 7, {}, {}),
        "added_row": one(["added"]),
        "added_rows": one(["added"], a={**cam, "schedule": cam["schedule"] * 2}),
        "added_nosched": one(["added"], a={**cam, "schedule": []}),
        "added_strava": one(["added"], a={"source": "strava", "weekly_sessions": 14, "min_km": 10.5}),
        "added_health": one(["added"], a={"source": "health", "metric": "steps", "daily_target": 8000}),
        "removed": one(["removed"]),
        "name": one(["name"]),
        "check_both": one(["check"], a={**cam, "modality": "hybrid"}),
        "check_screen": one(["check"], a={**cam, "modality": "digital"}),
        "check_camera": one(["check"]),
        "days": one(["days"]),
        "time": one(["time"]),
        "schedule": one(["schedule"], a={**cam, "schedule": cam["schedule"] * 3}),
        "unscheduled": one(["unscheduled"], a={**cam, "schedule": []}),
        "length": one(["length"], a={**cam, "default_min": 240}, b={**cam, "default_min": 25}),
        "goal_min": one(["goal"]),
        "goal_runs": one(["goal"], a={"source": "strava", "weekly_sessions": 14, "min_km": 10.5}),
        "goal_health": one(["goal"], a={"source": "health", "metric": "sleep_h", "daily_target": 7}),
        "calendar_on": one(["calendar"]),
        "calendar_off": one(["calendar"], a={**cam, "calendar": False}),
        "shield_on": one(["phone_shield"]),
        "shield_off": one(["phone_shield"], a={**cam, "phone_shield": False}),
        "other": one(["other"]),
    }
    for k, line in lines.items():
        assert _clean(line), (k, line)
    assert lines["undo"] == "Back as it was."
    assert lines["added_row"] == f"Noted. {lab} is 4 days a week at 21:00.", lines["added_row"]   # the fallback
    assert lines["goal_health"] == "Noted. New daily goal for morning guitar practices: 7 h of sleep."
    assert habits_line([], {}, {}) is None
    piano = {"modality": "physical", "default_min": 20,
             "schedule": [{"days": ["tue", "thu", "fri"], "at": "21:00", "min": 20}]}
    assert habits_line([{"habit": "piano", "label": "Piano", "what": ["added"]}], {}, {"piano": piano}) == \
        "Noted. Piano is on Tue, Thu and Fri at 21:00."
    assert habits_line([{"habit": "piano", "label": "Piano", "what": ["added"]}], {},
                       {"piano": {**piano, "schedule": []}}) == "Noted. Say “piano for 20” to start it."
    assert habits_line([{"habit": "cpp", "label": "C++", "what": ["check"]}], {}, {"cpp": {"modality": "digital"}}) == \
        "Noted. I'll watch your screen for C++ now."
    assert habits_line([{"habit": "drawing", "label": "Drawing", "what": ["days"]}], {},
                       {"drawing": {**piano, "schedule": [{"days": ["mon", "tue", "wed", "thu", "fri"], "at": "19:00",
                                                           "min": 25}]}}) == "Noted. Drawing is on weekdays at 19:00."
    assert days_text(["sat", "mon", "wed", "thu", "tue"]) is None and days_text("weekends") == "weekends"
    print("pinch rulebook ok")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    else:
        import json
        print(json.dumps(pinch_state({"now": time.time()}), indent=2))
