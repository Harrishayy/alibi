"""Habit templates for the first-run wizard and the 'Add a habit' sheet.

Each template is a ready-to-save habits.yaml entry plus the plain words the UI shows: a title, an emoji, one line on
how Alibi checks it, a suggested schedule. Nothing here says modality / alias / witness — those are generated.
"""
import copy, re
from . import config

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri"]
EVERY_DAY = list(config.DAYS)

TEMPLATES = [
    {"id": "drawing", "label": "Drawing", "title": "Draw", "emoji": "✏️", "check": "camera", "minutes": 25,
     "blurb": "Sketch, paint or doodle on paper or a tablet.",
     "how": "Your desk camera takes a photo every minute and checks your hands are on the drawing.",
     "schedule": [{"days": ["mon", "wed", "fri"], "at": "19:00", "min": 25}],
     "habit": {"modality": "physical", "aliases": ["draw", "drawing", "sketch", "sketching", "art", "paint"],
               "on_task_looks_like": "hands holding a pen, pencil or stylus working on paper or a drawing tablet"}},
    {"id": "reading", "label": "Reading", "title": "Read", "emoji": "📖", "check": "camera", "minutes": 20,
     "blurb": "A book, not your phone.",
     "how": "Your desk camera checks there's a book or e-reader in your hands — and no phone.",
     "schedule": [{"days": EVERY_DAY, "at": "21:30", "min": 20}],
     "habit": {"modality": "physical", "aliases": ["read", "reading", "book"],
               "on_task_looks_like": "a person reading a paper book or e-reader"}},
    {"id": "instrument", "title": "Practise an instrument", "emoji": "🎸", "check": "camera", "minutes": 20,
     "blurb": "Guitar, piano, violin — anything you play.", "ask_name": "Which instrument?",
     "how": "Your desk camera checks you're holding the instrument and playing.",
     "schedule": [{"days": WEEKDAYS, "at": "18:30", "min": 20}],
     "habit": {"modality": "physical", "aliases": ["instrument", "music practice", "music practise"],
               "on_task_looks_like": "hands playing a musical instrument"}},
    {"id": "coding", "label": "Coding", "title": "Learn to code", "emoji": "💻", "check": "screen", "minutes": 30,
     "blurb": "Courses, tutorials, your own project.",
     "how": "Alibi looks at which app and website are in front — code editors and tutorials count, YouTube doesn't.",
     "schedule": [{"days": WEEKDAYS, "at": "20:00", "min": 30}],
     "habit": {"modality": "digital", "aliases": ["code", "coding", "program", "programming", "learn to code"],
               "on_task_looks_like": "code editor, terminal, programming tutorial or documentation"}},
    {"id": "study", "label": "Study", "title": "Study", "emoji": "🎓", "check": "both", "minutes": 30,
     "blurb": "Notes on paper and course pages on screen.",
     "how": "Counts a minute if either the camera sees you writing or your screen shows study material.",
     "schedule": [{"days": WEEKDAYS, "at": "17:00", "min": 30}],
     "habit": {"modality": "hybrid", "aliases": ["study", "studying", "revise", "revision", "homework"],
               "on_task_looks_like": "writing notes in a notebook, or course material, PDFs or lecture videos on screen"}},
    {"id": "running", "title": "Run 3× a week", "emoji": "🏃", "check": "strava",
     "blurb": "At least 5 km each time.",
     "how": "Alibi reads your runs from Strava every hour. Runs of 5 km or more count.",
     "schedule": [{"days": ["tue", "thu", "sat"], "at": "07:30", "min": 30}],
     "habit": {"source": "strava", "weekly_sessions": 3, "min_km": 5}},
    {"id": "steps", "title": "Walk 8,000 steps", "emoji": "👟", "check": "health",
     "blurb": "Every day, counted by your iPhone.",
     "how": "Your iPhone sends last night's step count from Apple Health. 8,000 or more ticks the day.",
     "habit": {"source": "health", "metric": "steps", "daily_target": 8000}},
    {"id": "sleep", "title": "Sleep 7 hours", "emoji": "😴", "check": "health",
     "blurb": "Measured by your iPhone or Apple Watch.",
     "how": "Your iPhone sends last night's sleep from Apple Health. 7 hours or more ticks the night.",
     "habit": {"source": "health", "metric": "sleep_h", "daily_target": 7}},
    {"id": "meditate", "title": "Meditate 10 min", "emoji": "🧘", "check": "health",
     "blurb": "Any app that logs Mindful Minutes.",
     "how": "Your iPhone sends today's Mindful Minutes from Apple Health. 10 or more ticks the day.",
     "schedule": [{"days": EVERY_DAY, "at": "07:00", "min": 10}],
     "habit": {"source": "health", "metric": "mindful_min", "daily_target": 10}},
]

CUSTOM = {"id": "custom", "title": "Something else", "emoji": "➕", "check": "camera", "minutes": 25,
          "blurb": "Name it and choose how Alibi checks it.", "ask_name": "What's the habit?",
          "how": "You pick: the camera on your desk, what's on your screen, or both."}

CHECK_HOW = {
    "camera": "Your desk camera takes a photo every minute and checks you're doing it. Photos stay on this Mac.",
    "screen": "Alibi looks at which app and website are in front. Nothing is recorded but the window name.",
    "both": "A minute counts if either the camera sees you at it or your screen shows it.",
    "strava": "Alibi reads your runs from Strava every hour.",
    "health": "Your iPhone sends the numbers from Apple Health each night.",
}


def public() -> list[dict]:
    """What /api/onboarding/templates returns: everything the cards need, no YAML internals."""
    out = []
    for t in TEMPLATES + [CUSTOM]:
        x = {k: copy.deepcopy(v) for k, v in t.items() if k != "habit"}
        x["check_text"] = config.CHECK_TEXT[t["check"]]
        x.setdefault("schedule", [])
        out.append(x)
    return out


def get(tid: str) -> dict | None:
    return next((t for t in TEMPLATES + [CUSTOM] if t["id"] == tid), None)


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    if not s or not s[0].isalpha():
        s = "habit_" + s
    return s[:24].rstrip("_")


STOPWORDS = {"a", "an", "the", "my", "to", "for", "of", "and", "on", "at", "some", "practice", "practise", "do",
             "learn", "learning", "more", "go", "doing"}


def auto_aliases(name: str, key: str = "") -> list[str]:
    """'Practise guitar' -> ['practise guitar', 'guitar']. Enough for 'guitar for 20' to match."""
    n = re.sub(r"\s+", " ", (name or key).strip().lower())
    out = [n] if n else []
    words = [w for w in re.findall(r"[a-z0-9+#]+", n) if w not in STOPWORDS and len(w) > 2]
    for w in words:
        if w not in out:
            out.append(w)
        if w.endswith("ing") and len(w) > 5 and w[:-3] not in out:        # drawing -> draw
            out.append(w[:-3])
    k = key.replace("_", " ")
    if k and k not in out:
        out.append(k)
    return out[:8]


def auto_looks_like(name: str, check: str) -> str:
    n = (name or "the habit").strip().lower()
    return {"camera": f"a person doing {n} in front of the camera",
            "screen": f"apps, documents or websites about {n}",
            "both": f"a person doing {n} at the desk, or {n} material on screen"}.get(check, n)


def build(tid: str, name: str | None = None, minutes: int | None = None, schedule: list | None = None,
          calendar: bool | None = None, check: str | None = None, target: float | None = None) -> tuple[str, dict]:
    """A template (plus the user's tweaks) -> (key, habits.yaml entry). Validation happens in health.save_habits."""
    t = get(tid)
    if t is None:
        raise ValueError(f"unknown template {tid!r}")
    title = raw = (name or "").strip()
    if tid == "custom":
        if not title:
            raise ValueError("Give the habit a name.")
        check = check or "camera"
        if check in ("strava", "health"):
            raise ValueError("Pick the Run, Steps, Sleep or Meditate card for Strava or Apple Health.")
        h = {"modality": config.CHECK_TO_MODALITY.get(check, "physical"), "aliases": auto_aliases(title),
             "on_task_looks_like": auto_looks_like(title, check)}
    else:
        h = copy.deepcopy(t["habit"])
        if title and h.get("aliases") is not None:
            # a named instrument answers to its own name only — never to 'practise', or 'practise yoga' starts guitar
            h["aliases"] = auto_aliases(title) if tid == "instrument" else \
                list(dict.fromkeys(auto_aliases(title) + h["aliases"]))[:10]
            if tid == "instrument":
                h["on_task_looks_like"] = f"hands playing a {title.lower()}"
    key = slug(raw) if raw else t["id"]
    if h.get("source") == "health":
        h["display"] = title or {"steps": "Steps", "sleep": "Sleep", "meditate": "Meditate"}[tid]
        if target:
            h["daily_target"] = target
    elif h.get("source") == "strava":
        h["label"] = title or "Running"
        if target:
            h["weekly_sessions"] = int(target)
    else:
        m = int(minutes or t.get("minutes") or 25)
        h["default_min"] = m
        h["label"] = (title[:1].upper() + title[1:]) if title else (t.get("label") or t["title"])
        if tid == "instrument" and not title:
            h["label"] = "Music practice"
    sched = schedule if schedule is not None else copy.deepcopy(t.get("schedule", []))
    if minutes and sched and h.get("source") is None:
        for b in sched:
            b["min"] = int(minutes)
    if sched:
        h["schedule"] = sched
        h["calendar"] = True if calendar is None else bool(calendar)
        if h.get("modality"):
            per = sum(len(b.get("days", [])) * int(b.get("min", 0)) for b in sched)
            h["weekly_target_min"] = per
    elif h.get("modality"):
        h["weekly_target_min"] = int(h["default_min"]) * 4
    return key, h
