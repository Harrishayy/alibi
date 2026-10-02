"""First-run state + the plain-language habit helpers the wizard and the 'Add a habit' sheet share.

The flag is data/onboarded (under ALIBI_DATA_DIR). An install that already has sessions counts as onboarded.
Hooks (see hooks.py): start(con) marks an existing install as onboarded; on_verdict marks the practice run done.
"""
import json, re, time
from . import config, db, intent, templates

STEPS = [
    {"id": "welcome", "title": "Welcome to Alibi",
     "text": "Alibi checks that you actually did your habits — using your desk camera, what's on your screen, "
             "Strava and Apple Health. Photos stay on this Mac.",
     "button": "Get started"},
    {"id": "habits", "title": "What do you want to do more of?",
     "text": "Pick a few. You can change them any time.", "button": "Next"},
    {"id": "schedule", "title": "When will you do them?",
     "text": "Pick days and a time. Alibi can put these in Apple Calendar so they show up on your phone too.",
     "button": "Next"},
    {"id": "connect", "title": "Let Alibi check", "text": "Each one is optional. Skip anything you don't need.",
     "button": "Next"},
    {"id": "practice", "title": "Try it once",
     "text": "Start a 2-minute practice session. Do the habit for a bit, pick up your phone for a bit, and see "
             "what Alibi notices.", "button": "Start 2-minute practice", "skip": "Skip — go to my dashboard"},
]

CONNECT = [
    {"id": "camera", "title": "Desk camera", "needed_for": ["camera", "both"],
     "why": "For habits like drawing or reading, Alibi takes a photo every minute while you're doing them and checks "
            "you're at it. The camera is off the rest of the time. Photos stay on this Mac.",
     "button": "Test the camera", "skip": "Not now"},
    {"id": "screen", "title": "What's on your screen", "needed_for": ["screen", "both"],
     "why": "For habits on the computer, Alibi notes which app and website are in front. It never records the "
            "screen — just the window name.",
     "button": "Allow in System Settings", "skip": "Not now"},
    {"id": "strava", "title": "Strava", "needed_for": ["strava"],
     "why": "Alibi reads your runs from Strava every hour, so a run counts without you doing anything.",
     "button": "Connect Strava", "skip": "Not now"},
    {"id": "health", "title": "Apple Health", "needed_for": ["health"],
     "why": "Your iPhone can send steps, sleep and mindful minutes to Alibi each night with a Shortcut.",
     "button": "Set up my iPhone", "skip": "Not now"},
]


def _has_sessions(con) -> bool:
    return con.execute("SELECT 1 FROM sessions LIMIT 1").fetchone() is not None


def state(con=None) -> dict:
    con = con or db.connect()
    flag = config.ONBOARDED_PATH.exists()
    info = {}
    if flag:
        try:
            info = json.loads(config.ONBOARDED_PATH.read_text() or "{}")
        except ValueError:
            info = {}
    progress = _progress()
    replay = bool(progress.get("replay"))          # 'Run the welcome tour again': show it even with history
    onboarded = flag or (_has_sessions(con) and not replay)
    habits = config.habits().get("habits") or {}
    checks_needed = sorted({config.habit_check(h) for h in habits.values()})
    return {"onboarded": onboarded, "needs_onboarding": not onboarded, "onboarded_at": info.get("at"),
            "step": progress.get("step", "welcome"), "picked": progress.get("picked", []), "replay": replay,
            "steps": [dict(x, text=config.photo_text(x["text"])) for x in STEPS],
            "connect": [dict(c, why=config.photo_text(c["why"])) for c in
                        ([c for c in CONNECT if set(c["needed_for"]) & set(checks_needed)] or CONNECT[:2])],
            "templates": templates.public(), "habits": view_habits()}


def _progress() -> dict:
    p = config.DATA_DIR / "onboarding.json"
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save_progress(step: str, picked: list | None = None) -> dict:
    cur = _progress()
    cur["step"] = step
    if picked is not None:
        cur["picked"] = picked
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "onboarding.json").write_text(json.dumps(cur))
    return cur


def mark_done(how: str = "wizard") -> dict:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    cur = _progress()
    if cur.pop("replay", None) is not None:
        (config.DATA_DIR / "onboarding.json").write_text(json.dumps(cur))
    config.ONBOARDED_PATH.write_text(json.dumps({"at": time.time(), "how": how}))
    return {"onboarded": True}


def reset() -> dict:
    """'Run the welcome tour again'. Keeps habits and history: the replayed wizard adds to them (replace=False)."""
    config.ONBOARDED_PATH.unlink(missing_ok=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "onboarding.json").write_text(json.dumps({"step": "welcome", "replay": True}))
    return {"onboarded": False, "needs_onboarding": True, "replay": True}


# --- habits in plain words -------------------------------------------------------------------------------------

DAY_SHORT = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}


def days_text(days: list[str]) -> str:
    d = [x for x in config.DAYS if x in days]
    if len(d) == 7:
        return "Every day"
    if d == ["mon", "tue", "wed", "thu", "fri"]:
        return "Weekdays"
    if d == ["sat", "sun"]:
        return "Weekends"
    return ", ".join(DAY_SHORT[x] for x in d)


def schedule_text(sched: list[dict]) -> str:
    """'Mon, Wed, Fri at 19:00 · 25 min' (blocks joined with '; ')."""
    return "; ".join(f"{days_text(b['days'])} at {b['at']} · {b['min']} min" for b in sched or [])


def target_text(key: str, h: dict) -> str:
    src = h.get("source")
    if src == "strava":
        return f"{h.get('weekly_sessions', 3)} runs a week, {h.get('min_km', 5):g} km or more"
    if src == "health":
        m = h.get("metric", "steps")
        return f"{templates_fmt(m, h.get('daily_target'))} a {'night' if m == 'sleep_h' else 'day'}"
    t = h.get("weekly_target_min") or 0
    return f"{t} min a week" if t else f"{h.get('default_min', 25)} min a session"


def templates_fmt(metric: str, v) -> str:
    from .health import fmt_metric
    return fmt_metric(metric, v)


def how_text(h: dict) -> str:
    c = config.habit_check(h)
    if c == "health":
        return {"steps": "Your iPhone sends your step count from Apple Health each night.",
                "sleep_h": "Your iPhone sends last night's sleep from Apple Health.",
                "mindful_min": "Your iPhone sends your Mindful Minutes from Apple Health.",
                "workout_min": "Your iPhone sends your workout minutes from Apple Health."}.get(h.get("metric"),
                                                                                                 config.photo_text(templates.CHECK_HOW[c]))
    if c == "strava":
        return f"Alibi reads your runs from Strava every hour. Runs of {h.get('min_km', 5):g} km or more count."
    return config.photo_text(templates.CHECK_HOW[c])


def view_habits() -> list[dict]:
    """Habits as the UI should talk about them. Technical fields only under `details`."""
    cfg = config.habits()
    out = []
    for k, h in (cfg.get("habits") or {}).items():
        c = config.habit_check(h)
        out.append({"key": k, "label": config.display_name(k, cfg), "check": c, "check_text": config.CHECK_TEXT[c],
                    "how": how_text(h), "minutes": h.get("default_min"), "target_text": target_text(k, h),
                    "schedule": h.get("schedule", []), "schedule_text": schedule_text(h.get("schedule", [])),
                    "calendar": bool(h.get("calendar", bool(h.get("schedule")))),
                    "emoji": h.get("emoji") or _emoji(k, h), "created_at": h.get("created_at"),
                    "template": h.get("template"),
                    "startable": bool(h.get("modality")),
                    "details": {x: h[x] for x in ("modality", "aliases", "on_task_looks_like", "source", "metric",
                                                  "daily_target", "weekly_sessions", "min_km", "weekly_target_min")
                                if x in h}})
    return out


def _emoji(k: str, h: dict) -> str:
    for t in templates.TEMPLATES:
        if t["id"] == h.get("template") or t["id"] == k or (h.get("metric") and t["habit"].get("metric") == h["metric"]):
            return t["emoji"]
    return {"strava": "🏃", "health": "❤️", "screen": "💻", "both": "🎓"}.get(config.habit_check(h), "⭐")


# --- unknown habit -> one-tap card ------------------------------------------------------------------------------

LEAD = re.compile(r"^(?:i\s*(?:'m| am)?\s*(?:want|wanna|going|gonna|need|plan|'d like|would like)\s+(?:to\s+)?|"
                  r"let'?s\s+|time to\s+|start\s+|add(?: habit)?\s+|go\s+)", re.I)
TAIL = re.compile(r"\s*(?:for\s+)?(?:about\s+)?(?:\d+(?:\.\d+)?\s*(?:h|hr|hrs|hours?|m|mins?|minutes?)\b.*|"
                  r"(?:an?|one|two|half an?|twenty|thirty|fifteen|ten|forty|sixty)\s+(?:hours?|minutes?|mins?)\b.*|"
                  r"for\s+\d+\s*$|now|today|tonight)\s*[.!?]*$", re.I)
CODE_WORDS = ("code", "coding", "program", "python", "javascript", "excel", "spreadsheet", "email", "write", "writing",
              "blog", "essay", "duolingo", "typing", "design", "figma", "c++", "rust", "swift")
BOTH_WORDS = ("study", "homework", "revise", "revision", "maths", "math", "language", "spanish", "french", "german")


def guess_name(text: str) -> str:
    """'I want to practice guitar for 20 minutes' -> 'Guitar'."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    for _ in range(3):
        t2 = LEAD.sub("", t).strip()
        if t2 == t:
            break
        t = t2
    t = TAIL.sub("", t).strip(" .!?,")
    for _ in range(3):
        t = re.sub(r"^(?:practi[cs]e|practi[cs]ing|do|doing|some|my|the|a|an|learn(?:ing)?(?: how)?(?: to)?|"
                   r"play(?:ing)?(?: the)?)\s+", "", t, flags=re.I).strip()
    t = " ".join(t.split()[:3])
    return t[:1].upper() + t[1:] if t else ""


def guess_check(name: str) -> str:
    n = name.lower()
    if any(w in n for w in CODE_WORDS):
        return "screen"
    if any(w in n for w in BOTH_WORDS):
        return "both"
    return "camera"


def suggest(text: str) -> dict:
    """What the 'not a habit yet' card needs. {known, draft, card_label, reply}."""
    known = intent.match_habit(text or "", include_sources=True)
    try:
        minutes = intent.said_minutes(text or "")
    except intent.DurationError:
        minutes = None
    if known:
        h = config.habits()["habits"][known]
        return {"known": known, "label": config.display_name(known), "check": config.habit_check(h), "draft": None,
                "card_label": None, "reply": None}
    name = guess_name(text)
    if not name:
        return {"known": None, "draft": None, "card_label": None,
                "reply": "Say what you're about to do, e.g. \"draw for 25\"."}
    m = minutes or 25
    chk = guess_check(name)
    draft = {"name": name, "key": templates.slug(name), "minutes": m, "check": chk,
             "check_text": config.CHECK_TEXT[chk], "how": config.photo_text(templates.CHECK_HOW[chk]), "schedule": [], "calendar": True,
             "start_after_add": True}
    return {"known": None, "draft": draft, "card_label": f"Add “{name}” · {m} min",
            "reply": f"{name} isn't one of your habits yet. Add it?"}


def add(body: dict) -> dict:
    """Add one habit from the sheet: {name, minutes?, check?, schedule?, calendar?, template?, target?,
    weekly_target_min?, phone_shield?}. Without weekly_target_min the template derives the goal from the schedule."""
    from . import health
    tid = body.get("template") or "custom"
    key, h = templates.build(tid, name=body.get("name"), minutes=body.get("minutes"), schedule=body.get("schedule"),
                             calendar=body.get("calendar"), check=body.get("check"), target=body.get("target"))
    if body.get("weekly_target_min") is not None and h.get("modality"):
        try:
            h["weekly_target_min"] = max(0, int(body["weekly_target_min"]))
        except (TypeError, ValueError):
            raise ValueError(f"weekly_target_min must be a number (got {body['weekly_target_min']!r})")
    if body.get("phone_shield") is not None:
        h["phone_shield"] = bool(body["phone_shield"])
    if body.get("key"):
        key = templates.slug(str(body["key"]))
    habits = config.habits().get("habits") or {}
    if key in habits:
        raise ValueError(f"{config.display_name(key)} is already one of your habits.")
    h["template"] = tid
    habits[key] = h
    health.save_habits(habits)
    return {"key": key, "label": config.display_name(key), "habit": config.habits()["habits"][key],
            "reply": f"Added {config.display_name(key)}." + (
                f" Say \"{config.spoken_name(key)} for {h['default_min']}\" to start." if h.get("modality") else "")}


def remove_new(con, key: str, max_age_s: float = 300) -> dict:
    """Undo of 'Add “X” and start': drop a habit added minutes ago that has no sessions yet. Anything older or with
    history is kept."""
    from . import health
    habits = dict(config.habits().get("habits") or {})
    h = habits.get(key)
    made = config.habit_created_ts(h) if h else None
    if not h or not made or time.time() - made > max_age_s or \
            con.execute("SELECT 1 FROM sessions WHERE habit=? LIMIT 1", (key,)).fetchone():
        return {"removed": None}
    label = config.display_name(key)
    habits.pop(key)
    health.save_habits(habits)
    return {"removed": key, "reply_extra": f"{label} is no longer one of your habits.", "habits": view_habits()}


def apply_picks(picks: list[dict], replace: bool = True) -> dict:
    """The wizard's 'Pick habits' + 'Schedule' result. replace=True swaps out whatever habits.yaml had (the
    developer's personal defaults) for exactly what was picked."""
    from . import health
    if not isinstance(picks, list) or not picks:
        raise ValueError("Pick at least one habit.")
    new = {} if replace else dict(config.habits().get("habits") or {})
    added = []
    for p in picks:
        if not isinstance(p, dict) or not p.get("template"):
            raise ValueError("Each pick needs a template id.")
        key, h = templates.build(p["template"], name=p.get("name"), minutes=p.get("minutes"),
                                 schedule=p.get("schedule"), calendar=p.get("calendar"), check=p.get("check"),
                                 target=p.get("target"))
        same = None if replace else next(
            (k for k, x in new.items() if k == key or (x.get("template") == p["template"] and p["template"] != "custom"
             and (not p.get("name") or config.display_name(k) == p["name"]))), None)
        if same:                           # replayed tour: an existing habit keeps its history, gets the new plan
            if h.get("schedule") and new[same].get("modality"):
                new[same]["schedule"] = h["schedule"]
            if "calendar" in h:
                new[same]["calendar"] = h["calendar"]
            added.append(same)
            continue
        base, n = key, 2
        while key in new:
            key = f"{base[:21]}_{n}"
            n += 1
        h["template"] = p["template"]
        if replace or not h.get("created_at"):   # pace and streaks count from now, not from an old habit
            h["created_at"] = time.strftime("%Y-%m-%d %H:%M")
        new[key] = h
        added.append(key)
    health.save_habits(new)
    save_progress("schedule" if replace else _progress().get("step", "habits"), picked=added)
    return {"added": added, "habits": view_habits()}


def practice(con=None, habit: str | None = None) -> dict:
    """'Try a 2-minute practice session now' — the first camera/screen habit (or the one asked for)."""
    from . import cli
    con = con or db.connect()
    habits = config.habits().get("habits") or {}
    key = habit if habit in habits and habits[habit].get("modality") else next(
        (k for k, h in habits.items() if h.get("modality")), None)
    if not key:
        return {"started": False, "reply": "Your habits are all checked by Strava or Apple Health — nothing to "
                                           "practise here. You're all set."}
    reply = cli.start_habit(con, key, 2)
    s = db.active_session(con)
    save_progress("practice")
    return {"started": bool(s and s["habit"] == key), "habit": key, "reply": reply,
            "session_id": s["id"] if s else None}


# --- hooks ------------------------------------------------------------------------------------------------------

def start(con):
    if not config.ONBOARDED_PATH.exists() and _has_sessions(con) and not _progress().get("replay"):
        mark_done("existing install")


def on_verdict(con, session):
    if not config.ONBOARDED_PATH.exists():
        mark_done("first session")
