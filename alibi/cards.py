"""Cards: one additive display shape for alerts, digest rows and agent briefs, so no surface has to show a
paragraph. Pure and cheap: builders read the alert/row they're given (plus one small file lookup for a digest or
brief), never call a model or the network, and never raise into a caller (for_* return None on any error, and the
client then shows `text` as before).

display(text)        raw enums -> words ("off_track" -> "off track"), for every agent / brief / phrase / LLM string
for_alert(a)         the card for one alerts.jsonl record, or None (api._alert_json calls it; a stored valid card wins)
for_digest(row)      the card for a digests.jsonl row (GET /api/digests, /latest, POST /run responses)
for_brief(row)       the card for an agent_briefs.jsonl row (GET /api/briefs, the brief alert)
clean(card)          caps, limits and tones enforced; every builder's output goes through it. Its output is always
                     JSON-safe (strings, finite floats, small dicts), so a card can never fail /api/state.

Cards are built when an alert or row is served, never stored: nothing on disk changes shape. So they're worded against
the clock at that moment: a 22:00 night review read after midnight says "today 08:00", not "tomorrow 08:00".
"""
import datetime as dt, math, os, re, time

V = 1
TONES = ("accent", "partial", "warn", "neutral")
SOURCES = ("nemotron", "agent", "rules", "apple_vision", "nvidia_vlm", "strava", "health", "calendar")
ICONS = ("check", "half", "x", "clock", "phone", "run", "calendar", "camera", "laptop", "heart", "moon", "flag")
CAP = {"title": 64, "subtitle": 110, "chip": 24, "label": 18, "bar": 16, "caption": 10, "stat_value": 6,
       "stat_unit": 8, "stat_caption": 24, "prov": 40, "prov_detail": 64}
MAX = {"chips": 6, "groups": 3, "items": 8, "bars": 8, "actions": 3}
STATUS_TONE = {"on_track": "accent", "done": "accent", "at_risk": "partial", "off_track": "warn"}
VERDICT_TONE = {"done": "accent", "partial": "partial", "slacked": "warn"}
VERDICT_ICON = {"done": "check", "partial": "half", "slacked": "x"}

# --- display: raw enums never reach a screen -------------------------------------------------------------------------

_ENUM = re.compile(r"(?<![\w/.-])([A-Za-z]+(?:_[A-Za-z0-9]+)+)(?![\w/-]|\.\w)")
WORDS = {"status3": "status", "buffer_days": "buffer", "need_today_min": "needed today", "verified_min": "seen",
         "target_min": "goal", "today_seen_min": "seen today", "today_planned_min": "planned today"}


def display(text) -> str:
    """'All habits off_track' -> 'All habits off track'; ON_TASK -> 'on task'. Idempotent; leaves paths, URLs, file
    names and model ids alone (a token touching '/', '.x' or '-' isn't an enum). The island and the web run the same
    regex on old alerts, so keep the three in step."""
    def word(m):
        t = m.group(1)
        return WORDS.get(t.lower()) or (t.lower() if t.isupper() else t).replace("_", " ")
    return _ENUM.sub(word, str(text or ""))


def _dry(s: str) -> str:
    """Model-written words in Alibi's voice: '!' becomes '.' (pinch.clean_brief does the same to briefs)."""
    return re.sub(r"([.?])?!+", lambda m: m.group(1) or ".", s)


# --- clean: the card's limits, enforced once -----------------------------------------------------------------------

def fit(s, n: int) -> str:
    """Collapse whitespace, normalise enums, cut at a word boundary with '…' past n characters."""
    s = " ".join(display(s).split())
    if len(s) <= n:
        return s
    cut = s[:n - 1]
    if s[n - 1] != " " and " " in cut:              # cut mid-word: back up to the last whole word
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-–—·") + "…"


def _text(x) -> str:
    """A string field as text; numbers are allowed (a stat of 74), anything else (dicts, lists, bools) is no text."""
    if isinstance(x, str):
        return x
    return str(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else ""


def _number(x) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None


def _list(x) -> list:
    return list(x) if isinstance(x, (list, tuple)) else []


def _tone(t) -> str:
    return t if t in TONES else "neutral"


def _sentence(s: str) -> str:
    """A title ends with '.', '?' or the cut mark."""
    s = _dry(" ".join(display(s).split()))
    return s if not s or s[-1] in ".?…" else s.rstrip(" ,;:-–—·") + "."


def _chip(c) -> dict | None:
    if not isinstance(c, dict) or not _text(c.get("text")).strip():
        return None
    out = {"text": fit(_text(c["text"]), CAP["chip"]), "tone": _tone(c.get("tone"))}
    if c.get("icon") in ICONS:
        out["icon"] = c["icon"]
    return out


def _bar(b) -> dict | None:
    """Numbers only (no strings, no NaN or infinity: JSON can't carry them and /api/state would fail), min < max,
    value clamped into range."""
    if not isinstance(b, dict):
        return None
    lo, hi, v = _number(b.get("min")), _number(b.get("max")), _number(b.get("value"))
    if lo is None or hi is None or v is None or not lo < hi or not _text(b.get("label")).strip():
        return None
    return {"label": fit(_text(b["label"]), CAP["bar"]), "value": max(lo, min(hi, v)), "min": lo, "max": hi,
            "tone": _tone(b.get("tone")), "caption": fit(_text(b.get("caption")), CAP["caption"])}


def _action(a) -> dict | None:
    """An alert's action: {label (required), say?, url?, post?, body? (an object of scalars), dismiss?}."""
    if not isinstance(a, dict) or not isinstance(a.get("label"), str) or not a["label"].strip():
        return None
    out = {"label": a["label"]}
    for k in ("say", "url", "post"):
        if isinstance(a.get(k), str):
            out[k] = a[k]
    if isinstance(a.get("body"), dict):
        out["body"] = {k: v for k, v in a["body"].items() if isinstance(k, str) and
                       (v is None or isinstance(v, (str, bool, int)) or _number(v) is not None)}
    if isinstance(a.get("dismiss"), bool):
        out["dismiss"] = a["dismiss"]
    return out


def clean(card) -> dict | None:
    """The one gate every card passes: drops what's malformed, caps every string and list. None when there's no
    string title. Never raises on any input shape."""
    if not isinstance(card, dict) or not isinstance(card.get("title"), str) or not card["title"].strip():
        return None
    kind = card.get("kind") if isinstance(card.get("kind"), str) and card["kind"].strip() else "note"
    out = {"v": V, "kind": kind, "title": fit(_sentence(card["title"]), CAP["title"]), "tone": _tone(card.get("tone"))}
    if _text(card.get("subtitle")).strip():
        out["subtitle"] = fit(_text(card["subtitle"]), CAP["subtitle"])
    chips = [c for c in map(_chip, _list(card.get("chips"))) if c][:MAX["chips"]]
    if chips:
        out["chips"] = chips
    groups = []
    for g in _list(card.get("groups")):
        if not isinstance(g, dict) or not _text(g.get("label")).strip():
            continue
        label = fit(_text(g["label"]), CAP["label"])
        if g.get("bars"):
            bars = [b for b in map(_bar, _list(g["bars"])) if b][:MAX["bars"]]
            if bars:
                groups.append({"label": label, "bars": bars})
        elif g.get("items"):
            items = [c for c in map(_chip, _list(g["items"])) if c][:MAX["items"]]
            if items:
                groups.append({"label": label, "items": items})
    if groups:
        out["groups"] = groups[:MAX["groups"]]
    st = card.get("stat")
    if isinstance(st, dict) and _text(st.get("value")).strip():
        s = {"value": fit(_text(st["value"]), CAP["stat_value"])}
        for k, cap in (("unit", "stat_unit"), ("caption", "stat_caption")):
            if _text(st.get(k)).strip():
                s[k] = fit(_text(st[k]), CAP[cap])
        if st.get("tone") in TONES:
            s["tone"] = st["tone"]
        out["stat"] = s
    pv = card.get("provenance")
    if isinstance(pv, dict) and _text(pv.get("text")).strip():
        p = {"text": fit(_text(pv["text"]), CAP["prov"])}
        if pv.get("source") in SOURCES:              # unknown: no source (clients show no icon), never a wrong one
            p["source"] = pv["source"]
        if _text(pv.get("detail")).strip():
            p["detail"] = fit(_text(pv["detail"]), CAP["prov_detail"])
        out["provenance"] = p
    acts = [a for a in map(_action, _list(card.get("actions"))) if a]
    if acts:
        out["actions"] = acts[:MAX["actions"]]
    return out


# --- shared pieces ----------------------------------------------------------------------------------------------------

_cfg_cache: dict = {"key": None, "cfg": None}


def _cfg() -> dict:
    """habits.yaml for display names, parsed once per change: a parse costs ~5 ms and a card can name several habits."""
    from . import config
    try:
        st = os.stat(config.HABITS_PATH)
        key = (str(config.HABITS_PATH), st.st_mtime_ns, st.st_size, st.st_ino)
        if _cfg_cache["key"] != key:
            _cfg_cache.update(key=key, cfg=config.habits())
        cfg = _cfg_cache["cfg"]
        return cfg if isinstance(cfg, dict) and isinstance(cfg.get("habits"), dict) else {"habits": {}}
    except Exception:
        return {"habits": {}}


def _name(key, cfg: dict | None = None) -> str:
    from . import config
    return config.display_name(str(key), cfg or _cfg())


def _signed(x) -> str:
    """+25, −5 (U+2212), 0."""
    return "0" if not x else f"{x:+g}".replace("-", "−")


def _signed_days(x) -> str:
    return "0 d" if not x else f"{x:+g} d".replace("-", "−")


def buffer_group(buffers: list) -> dict | None:
    """Buffer per habit, worst first: [{label, value: buffer_days, min -7, max 7, tone by status3, caption '−5 d'}].
    The same rows and numbers as the text's 'Buffer:' line."""
    xs = [x for x in _list(buffers) if isinstance(x, dict) and _number(x.get("buffer_days")) is not None
          and x.get("status3") not in ("done", "stale")]
    xs.sort(key=lambda x: (x["buffer_days"], str(x.get("label"))))
    bars = [{"label": x.get("label") or x.get("habit"), "value": x["buffer_days"], "min": -7, "max": 7,
             "tone": STATUS_TONE.get(x.get("status3"), "neutral"), "caption": _signed_days(x["buffer_days"])} for x in xs]
    return {"label": "Buffer", "bars": bars} if bars else None


# --- digests ----------------------------------------------------------------------------------------------------------

def _date(s) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _when(day: dt.date, now: float) -> str:
    """'today', 'tomorrow', else the weekday ('Friday'), against the clock `now`."""
    return {0: "today", 1: "tomorrow"}.get((day - dt.date.fromtimestamp(now)).days, f"{day:%A}")


def _start(p) -> float | None:
    """When a night proposal's block starts (local time, as digest.accept reads it), or None."""
    try:
        return dt.datetime.fromisoformat(f"{p['day']}T{p['at']}").timestamp()
    except (KeyError, TypeError, ValueError):
        return None


def _until(row, now: float) -> float:
    """When a digest card's words next change: local midnight ('today' becomes a weekday), or the night proposal's
    start ('Move …?' becomes 'Proposed: …') if that's sooner."""
    nxt = dt.datetime.combine(dt.date.fromtimestamp(now) + dt.timedelta(days=1), dt.time()).timestamp()
    s = _start(row.get("proposal")) if isinstance(row, dict) else None
    return min(nxt, s) if s is not None and s > now else nxt


def night(d: dict, row: dict | None = None, now: float | None = None) -> dict | None:
    """The night review. A proposal leads as the question (Accept / Not now are the alert's own actions); then the
    day's blocks and sessions as chips, the buffer as bars, and where the proposal came from. Worded against `now`
    (default: the clock), not when it was written: read after midnight, the question is "today 08:00" and the blocks
    are "Missed Friday"; once the slot has started there's nothing left to accept, so it reads "Proposed: …"."""
    from . import config, digest
    row = row or {}
    now = time.time() if now is None else now
    day = _date(d.get("day"))
    on = "today" if day is None or day == dt.date.fromtimestamp(now) else f"{day:%A}"   # the review's own day
    p = d.get("proposal")
    card = {"kind": "night", "tone": "neutral", "groups": [], "chips": []}
    if p:
        why = _dry(" ".join(str(p.get("why") or "").split()))
        slot = digest._slot_words(p, now)                   # "tomorrow 08:00, 60 min"
        start = _start(p)
        if row.get("accepted_at"):
            card["title"] = f"On the plan: {config.spoken_name(p['habit'])} {slot}."
            card["chips"].append({"text": "Accepted", "tone": "accent", "icon": "check"})
            card["tone"] = "accent"
        elif start is not None and start <= now:            # digest.accept refuses it now: no question, no Accept
            card["title"] = f"Proposed: {config.spoken_name(p['habit'])} {slot}."
            card["chips"].append({"text": "Slot passed", "tone": "neutral", "icon": "clock"})
        else:
            card["title"] = digest._ask(p, now)             # "Move math to tomorrow 08:00, 60 min?"
            card["tone"] = "accent"
        card["subtitle"] = (why + ("" if why[-1] in ".?…" else ".")) if why else ""
    else:
        card["title"] = "Day closed."
        f = d.get("fix_tomorrow")
        fix = _when(day + dt.timedelta(days=1), now) if day else "tomorrow"
        card["subtitle"] = f"Fix {fix}: {f['label']}. {f['reason']}" if f else ""
    items = ([{"text": f"{x['label']} {x['seen_min']} min", "tone": "accent", "icon": "check"}
              for x in _list(d.get("done"))]
             + [{"text": f"{x['label']} {x['seen_min']} min", "tone": "partial", "icon": "half"}
                for x in _list(d.get("partial"))]
             + [{"text": f"{x['label']} {x['seen_min']} min", "tone": "warn", "icon": "x"}
                for x in _list(d.get("slacked"))]
             + [{"text": f"{b['label']} {b['at']}", "tone": "warn", "icon": "x"} for b in _list(d.get("missed"))])
    if items:                                   # all missed blocks: say so in the label, the chips stay short
        only_missed = len(items) == len(_list(d.get("missed")))
        card["groups"].append({"label": f"Missed {on}" if only_missed else "Today" if on == "today" else on,
                               "items": items})
    else:
        card["chips"].append({"text": f"Nothing seen {on}", "tone": "neutral"})
    bg = buffer_group(d.get("buffers"))
    if bg:
        card["groups"].append(bg)
    if _number(d.get("alibi_score")) is not None:
        card["stat"] = {"value": f"{round(d['alibi_score'] * 100)}", "unit": "%", "caption": "of claims held up"}
    if str(d.get("via") or "").startswith("llm") and p:
        s = (_number(d.get("total_ms")) or 0) / 1000
        name = digest._model_name(d.get("model")) or "Model"
        looked = digest._provenance(d, now).split(" · ")[0]
        card["provenance"] = {"text": f"{name} · {round(s)} s" if s >= 1 else f"{name} · <1 s", "source": "nemotron",
                              "detail": looked if looked.startswith("Checked") else ""}
    else:
        card["provenance"] = {"text": "Alibi's rules", "source": "rules"}
    return card


def for_digest(row: dict, now: float | None = None) -> dict | None:
    """The card for one digests.jsonl row (a copy is fine; the row is never changed), worded against `now` (default:
    the clock). A night row with a proposal not yet accepted carries Accept / Not now, exactly digest.actions(row),
    until the proposed slot starts (digest.accept refuses it from then on)."""
    try:
        if not isinstance(row, dict):
            return None
        now = time.time() if now is None else now
        d = row.get("json") if isinstance(row.get("json"), dict) else {}
        k = row.get("kind") or d.get("kind")
        c = {"night": lambda: night(d, row, now), "morning": lambda: morning(d),
             "checkpoint": lambda: checkpoint(d)}.get(k, lambda: None)()
        if (c is not None and k == "night" and row.get("proposal") and not row.get("accepted_at") and row.get("slot")
                and (_start(row["proposal"]) or 0) > now):
            c["actions"] = [{"label": "Accept", "post": f"/api/digests/{row['slot']}/accept", "body": {}, "dismiss": True},
                            {"label": "Not now", "dismiss": True}]
        return clean(c)
    except Exception as e:                                  # never fail a response over a card
        print(f"[alibi] card failed: {e!r}", flush=True)
        return None


STATE_CHIP = {"done": ("accent", "check"), "kept": ("accent", "check"), "partial": ("partial", "half"),
              "missed": ("warn", "x"), "slacked": ("warn", "x")}


def _block_chip(b: dict) -> dict:
    tone, icon = STATE_CHIP.get(b.get("state"), ("neutral", "clock"))
    return {"text": f"{b['label']} {b['at']}", "tone": tone, "icon": icon}


def morning(d: dict) -> dict:
    bl = [b for b in _list(d.get("blocks")) if isinstance(b, dict)]
    nxt = next((b for b in bl if b.get("state") in ("planned", "now")), None)
    need = [x for x in _list(d.get("need_today")) if isinstance(x, dict)]
    mem = d.get("memory") if isinstance(d.get("memory"), dict) else {}
    card = {"kind": "morning", "tone": "neutral", "chips": [], "groups": [],
            "title": f"First up: {nxt['label']} at {nxt['at']}." if nxt
            else "Nothing planned today." if not bl else "Nothing left on today's plan.",
            "subtitle": mem.get("text")
            or (f"{need[0]['label']} needs {need[0]['minutes']} min today." if need
                else "Nothing needed today to stay on pace."),
            "provenance": {"text": "Alibi's rules", "source": "rules"}}
    if bl:
        card["groups"].append({"label": "Today's plan", "items": [_block_chip(b) for b in bl]})
    if need:
        card["groups"].append({"label": "Needs today", "items": [{"text": f"{x['label']} {x['minutes']} min",
                                                                   "tone": "partial"} for x in need]})
    g = d.get("first_gap")
    if isinstance(g, dict) and g.get("at"):
        card["chips"].append({"text": f"Free {g['at']}–{g['until']}", "tone": "neutral", "icon": "clock"})
    if _number(d.get("sleep_h")) is not None:
        card["stat"] = {"value": f"{d['sleep_h']:.1f}", "unit": "h", "caption": "sleep"}
    return card


def checkpoint(d: dict) -> dict:
    """What changed since the last slot, one chip per change (the same changes digest.text() lists)."""
    cfg = _cfg()
    items = []
    for c in _list(d.get("changes")):
        if not isinstance(c, dict):
            continue
        name = _name(c["habit"], cfg) if c.get("habit") else ""
        f, b = c.get("field"), c.get("to")
        if f == "status3":
            if isinstance(b, str) and b:
                items.append({"text": f"{name} {display(b)}", "tone": STATUS_TONE.get(b, "neutral")})
            continue
        a, b = _number(c.get("from") or 0), _number(b)
        if a is None or b is None or b == a:
            continue
        n = b - a
        if f == "verified_min":
            items.append({"text": f"{name} {_signed(n)} min", "tone": "accent", "icon": "check"} if n > 0
                         else {"text": f"{name} {_signed(n)} min", "tone": "neutral"})       # a correction took some back
        elif f in VERDICT_TONE and n > 0:
            items.append({"text": f"{name} {f}" if n == 1 else f"{name} {n:g} {f}", "tone": VERDICT_TONE[f],
                          "icon": VERDICT_ICON[f]})
        elif f == "blocks_missed" and n > 0:
            items.append({"text": f"{n:g} block{'s' * (n != 1)} missed", "tone": "warn", "icon": "x"})
        elif f == "picked_min":
            items.append({"text": f"Picked apps {round(b)} min", "tone": "neutral", "icon": "phone"})
    nb, since = d.get("next_block"), d.get("since")
    if isinstance(nb, dict) and nb.get("label"):
        title = f"Next: {nb['label']} at {nb['at']}, {nb['min']} min."
    elif items:
        title = f"{len(items)} change{'s' * (len(items) != 1)} " + (f"since {since}." if since else "today.")
    else:
        title = f"Nothing new since {since}." if since else "Nothing new today."
    card = {"kind": "checkpoint", "tone": "neutral", "groups": [], "title": title,
            "provenance": {"text": "Alibi's rules", "source": "rules"}}
    if items:
        card["groups"].append({"label": f"Since {since}" if since else "Today", "items": items})
    return card


# --- the agent's brief -------------------------------------------------------------------------------------------------

def brief(b: dict) -> dict | None:
    """An agent_briefs.jsonl row, or a brief alert when the row is gone: first sentence as the title, the next as the
    subtitle, the row's items as chips, 'Your agent · DGX Spark' as provenance (the model's name as its detail)."""
    from . import pinch, today
    t = display(_text(b.get("text")))                      # a row whose text isn't a string has no card
    first = pinch.clean_brief(t, 1, 10_000)
    if not first:
        return None
    rest = pinch.clean_brief(t, 99, 10_000)[len(first):].strip()
    cfg = _cfg()
    chips = []
    for i in _list(b.get("items")):
        if isinstance(i, dict) and i.get("habit") and _text(i.get("note")).strip():
            note = _dry(display(_text(i["note"])))
            chips.append({"text": f"{_name(i['habit'], cfg)} · {note}",
                          "tone": "warn" if re.search(r"behind|missed|slack|off track", note, re.I) else "neutral"})
    k = b.get("digest_kind") if b.get("kind") == "brief" else b.get("kind")        # an alert, or a briefs row
    return {"kind": "brief", "tone": "partial" if k == "risk" else "neutral",
            "title": first, "subtitle": pinch.clean_brief(rest, 1, 10_000) if rest else "", "chips": chips,
            "provenance": {"text": f"Your agent · {today.agent_host()}", "source": "agent",
                           "detail": today.model_name(_text(b.get("model")))}}


# --- alerts ------------------------------------------------------------------------------------------------------------

def _num(pat: str, text: str):
    m = re.search(pat, text or "")
    try:
        return float(m.group(1)) if m else None
    except ValueError:
        return None


def claim(a: dict) -> dict:
    """A 'go for a run' claim settled by Strava (verdict alert with no session). distance_km / min_km / moving_min
    come from daemon.check_claims; an older alert falls back to the number in its text."""
    t = _text(a.get("text"))
    if a.get("verdict") == "done":
        km = _number(a.get("distance_km"))
        km = _num(r"([\d.]+) km", t) if km is None else km
        chips = [{"text": "Done", "tone": "accent", "icon": "check"}]
        mm = a.get("moving_min")
        if isinstance(mm, int) and not isinstance(mm, bool) and mm > 0:
            chips.append({"text": f"{mm} min", "tone": "neutral", "icon": "clock"})
        return {"kind": "claim", "tone": "accent", "title": "Run verified.", "chips": chips,
                "stat": {"value": f"{round(km, 2):g}", "unit": "km", "caption": "on Strava"} if km is not None else None,
                "provenance": {"text": "Strava", "source": "strava"}}
    mk = _number(a.get("min_km"))
    mk = _num(r"≥([\d.]+) km", t) if mk is None else mk
    return {"kind": "claim", "tone": "warn", "title": "Claimed, not seen.",
            "subtitle": f"Strava has no run of {mk:g} km or more." if mk else "Strava has no run for it.",
            "chips": [{"text": "Slacked", "tone": "warn", "icon": "x"}],
            "provenance": {"text": "Strava", "source": "strava"}}


def recap(a: dict) -> dict:
    t = _text(a.get("text"))
    n = a.get("sessions") if isinstance(a.get("sessions"), int) else _num(r"(\d+) sessions?", t)
    seen = _number(a.get("seen_min"))
    seen = _num(r"(\d+) min seen", t) if seen is None else seen
    return {"kind": "recap", "tone": "accent" if seen else "neutral",
            "title": "Today's reel is ready." if a.get("reel") or "reel is ready" in t else "Today, checked.",
            "chips": [{"text": f"{n:g} session{'s' * (n != 1)}", "tone": "neutral", "icon": "camera"}] if n else [],
            "stat": {"value": f"{seen:g}", "unit": "min", "caption": "seen today"} if seen is not None else None}


def habits_saved(a: dict) -> dict:
    t = display(_text(a.get("text")) or "Noted.")
    chips = []
    for c in _list(a.get("changes")):
        if isinstance(c, dict) and c.get("label") and c.get("what"):
            w = [str(x) for x in ([c["what"]] if isinstance(c["what"], str) else _list(c["what"]))][:2]
            if w:
                chips.append({"text": f"{c['label']} · {', '.join(display(x) for x in w)}",
                              "tone": "accent" if w[0] in ("added", "restored") else "warn" if w[0] == "removed"
                              else "neutral"})
    return {"kind": "habits_saved", "tone": "accent", "title": t[7:] if t.startswith("Noted. ") else t, "chips": chips}


_memo: dict = {}
_MISS = object()


def _mtime(p) -> int:
    try:
        return p.stat().st_mtime_ns
    except OSError:
        return 0


def _brief_row(a: dict) -> dict | None:
    """The agent_briefs.jsonl row this brief alert was raised for: the same slot and the same shown text. A second
    brief for a slot never raises a second alert, so the newest row for the slot may not be this alert's."""
    from . import pinch, routes_agent
    rows = [r for r in reversed(routes_agent.briefs(100)) if isinstance(r, dict) and r.get("slot") == a.get("slot")]
    for r in rows:
        if a.get("text") in (pinch.clean_brief(display(r.get("text")), 2, 160), pinch.clean_brief(r.get("text"), 2, 160)):
            return r
    return rows[0] if rows else None


def for_alert(a: dict) -> dict | None:
    """The card for one alert record, or None (the client shows `text`). A valid card the producer stored wins. Night,
    morning and checkpoint alerts are rebuilt from their digests.jsonl row (so a 22:00 report raised before a restart
    still gets a card), briefs from agent_briefs.jsonl; both memoised per alert id and file mtime (a digest card only
    until its words change: midnight, or its proposal's start). Never carries `actions`: the alert's own actions are
    the buttons."""
    try:
        if not isinstance(a, dict):
            return None
        if isinstance(a.get("card"), dict):
            c = clean(a["card"])
            if c:
                c.pop("actions", None)
                return c
        k = a.get("kind")
        if k in ("report", "digest") and a.get("slot"):
            from . import digest
            now, key = time.time(), (a.get("id"), "d", _mtime(digest._path()))
            hit = _memo.get(key)
            if hit is None or now >= hit[1]:
                row = digest.get(a["slot"])
                c = for_digest(row, now) if row else None
                if c:
                    c.pop("actions", None)
                hit = _memo[key] = (c, _until(row, now))
            return hit[0]
        if k == "brief":
            from . import routes_agent
            key = (a.get("id"), "b", _mtime(routes_agent._path()))
            c = _memo.get(key, _MISS)
            if c is _MISS:
                c = clean(brief(_brief_row(a) or a))
                _memo[key] = c
            return c
        build = {"recap": recap, "habits_saved": habits_saved}.get(k)
        if k == "verdict" and not a.get("session_id") and a.get("habit"):
            build = claim
        return clean(build(a)) if build else None
    except Exception as e:
        print(f"[alibi] card failed: {e!r}", flush=True)
        return None
    finally:
        if len(_memo) > 64:
            _memo.clear()


def for_brief(row: dict) -> dict | None:
    try:
        return clean(brief(row)) if isinstance(row, dict) else None
    except Exception as e:
        print(f"[alibi] card failed: {e!r}", flush=True)
        return None
