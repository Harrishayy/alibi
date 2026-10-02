"""Parse a declaration: "I'm going to draw for 1 hour" -> {habit, minutes, modality}."""
import re
from . import config, llm

SYSTEM = ("You map a person's sentence about what they are about to do onto one of their habits. "
          'Reply with JSON only: {"habit": "<one of the keys>", "minutes": <int>}.')


class DurationError(ValueError):
    """The habit was understood but the duration was not usable. str(e) is a reply for the user."""


def parse(text: str) -> dict:
    """Return {"habit": <key in habits.yaml>, "minutes": int, "modality": str}. Modality always comes from habits.yaml.

    Duration: what was said (bare trailing numbers count as minutes), else the habit's default_min. 0 or more than
    MAX_SESSION_MIN raises DurationError with a friendly reply."""
    said = said_minutes(text)            # raises DurationError on 0 / too long, before any model call
    habits = {k: h for k, h in config.habits()["habits"].items() if h.get("modality")}
    if config.TEXT_READY:
        try:
            menu = "\n".join(f"- {k}: {', '.join(map(str, h.get('aliases', [])))}" for k, h in habits.items())
            out = llm.chat_json(SYSTEM, f"Habits:\n{menu}\n\nSentence: {text}\nDefault minutes if none given: 0.",
                                interactive=True)
            if out.get("habit") in habits:
                key = out["habit"]
                return {"habit": key, "minutes": said or int(habits[key].get("default_min", 25)),
                        "modality": habits[key]["modality"]}
        except DurationError:
            raise
        except Exception:
            pass
    return _fallback(text)


WORDS = {"an": 1, "a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "fifteen": 15,
         "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45, "fifty": 50, "sixty": 60, "ninety": 90}


def _minutes(t: str) -> int | None:
    """Minutes actually said, or None if no duration was given."""
    t = t.lower()
    if re.search(r"\b(an?|one) hour and a half\b|\bhour and a half\b", t):
        return 90
    if "half an hour" in t or "half hour" in t:
        return 30
    if "quarter of an hour" in t or "quarter hour" in t:
        return 15
    total, hit = 0.0, False
    for n, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|m|min|mins|minute|minutes)\b", t):
        total += float(n) * (60 if unit.startswith("h") else 1)
        hit = True
    if not hit:
        for w, unit in re.findall(r"\b(an?|one|two|three|four|five|ten|fifteen|twenty|thirty|forty-five|forty|fifty|"
                                  r"sixty|ninety)\s+(hours?|minutes?|mins?)\b", t):
            total += WORDS[w] * (60 if unit.startswith("h") else 1)
            hit = True
    if not hit:
        m = re.search(r"\bfor\s+(\d+(?:\.\d+)?)\s*(?:more\s*)?[.!]?\s*$", t) or re.fullmatch(r"\s*[a-z+#]+\s+(\d+)\s*", t)
        if m:
            total, hit = float(m.group(1)), True
    return int(round(total)) if hit else None


def said_minutes(text: str) -> int | None:
    m = _minutes(text)
    if m is None:
        return None
    if m < 1:
        raise DurationError("0 minutes? Try 25.")
    if m > config.MAX_SESSION_MIN:
        raise DurationError(f"{m} minutes is longer than I'll watch in one go (max {config.MAX_SESSION_MIN}). "
                            "Say it in chunks.")
    return m


HEALTH_WORDS = {"steps": ["walk", "walking", "steps", "a walk"], "sleep_h": ["sleep", "sleeping", "bed", "bedtime"],
                "mindful_min": ["meditate", "meditating", "meditation", "mindful", "mindfulness"],
                "workout_min": ["workout", "work out", "gym", "exercise", "training"]}


def match_habits(text: str, include_sources: bool = False) -> list[str]:
    """Every habit the sentence names (key, alias or label), in habits.yaml order."""
    t = text.lower()
    out = []
    for key, h in config.habits()["habits"].items():
        if not h.get("modality") and not include_sources:
            continue
        extra = ["run", "running", "jog", "jogging"] if h.get("source") == "strava" else \
            HEALTH_WORDS.get(h.get("metric"), []) if h.get("source") == "health" else []
        if h.get("display") or h.get("label"):
            extra = [*extra, str(h.get("display") or h.get("label")).lower()]
        if re.search(rf"\b{re.escape(key)}\b", t) or any(re.search(rf"(?<!\w){re.escape(str(a).lower())}(?!\w)", t)
                                                          for a in [*h.get("aliases", []), *extra]):
            out.append(key)
    return out


def match_habit(text: str, include_sources: bool = False) -> str | None:
    m = match_habits(text, include_sources)
    return m[0] if m else None


def _fallback(text: str) -> dict:
    """Regex + alias matching: the path with no model, and the fallback when the LLM misbehaves."""
    key = match_habit(text)
    if not key:
        raise ValueError(f"Unknown habit in: {text!r}")
    h = config.habits()["habits"][key]
    minutes = said_minutes(text) or int(h.get("default_min", 25))
    return {"habit": key, "minutes": minutes, "modality": h["modality"]}
