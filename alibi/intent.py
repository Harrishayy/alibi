"""P0 — "I'm going to draw for 1 hour" -> {habit, minutes, modality}."""
import re
from . import config, llm

SYSTEM = ("You map a person's sentence about what they are about to do onto one of their habits. "
          'Reply with JSON only: {"habit": "<one of the keys>", "minutes": <int>}.')


def parse(text: str) -> dict:
    """Return {"habit": <key in habits.yaml>, "minutes": int, "modality": str}. Modality always comes from habits.yaml."""
    habits = {k: h for k, h in config.habits()["habits"].items() if h.get("modality")}
    if config.TEXT_READY:
        try:
            menu = "\n".join(f"- {k}: {', '.join(map(str, h.get('aliases', [])))}" for k, h in habits.items())
            out = llm.chat_json(SYSTEM, f"Habits:\n{menu}\n\nSentence: {text}\nDefault minutes if none given: 60.")
            if out.get("habit") in habits and int(out.get("minutes", 0)) > 0:
                return {"habit": out["habit"], "minutes": int(out["minutes"]),
                        "modality": habits[out["habit"]]["modality"]}
        except Exception:
            pass
    return _fallback(text)


def _minutes(t: str) -> int:
    if "half an hour" in t or "half hour" in t:
        return 30
    if re.search(r"\ban hour\b", t) and not re.search(r"\d", t):
        return 60
    total, hit = 0.0, False
    for n, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|m|min|mins|minute|minutes)\b", t):
        total += float(n) * (60 if unit.startswith("h") else 1)
        hit = True
    return max(1, int(total)) if hit else 60


def _fallback(text: str) -> dict:
    """Regex + alias matching. Good enough to demo if the LLM misbehaves."""
    t = text.lower()
    minutes = _minutes(t)
    for key, h in config.habits()["habits"].items():
        if not h.get("modality"):
            continue
        if re.search(rf"\b{re.escape(key)}\b", t) or any(re.search(rf"(?<!\w){re.escape(str(a).lower())}(?!\w)", t)
                                                          for a in h.get("aliases", [])):
            return {"habit": key, "minutes": minutes, "modality": h["modality"]}
    raise ValueError(f"Unknown habit in: {text!r}")
