"""P0 — "I'm going to draw for 1 hour" -> {habit, minutes, modality}."""
import re
from . import config, llm


def parse(text: str) -> dict:
    """Return {"habit": <key in habits.yaml>, "minutes": int, "modality": str}.

    TODO (P0):
      1. Build a prompt listing habit keys + aliases from config.habits().
      2. llm.chat_json(...) -> validate habit is a known key, minutes is an int.
      3. On any failure, fall back to _fallback(text).
      4. modality comes from habits.yaml, never from the LLM.
    """
    return _fallback(text)


def _fallback(text: str) -> dict:
    """Regex + alias matching. Good enough to demo if the LLM misbehaves."""
    t = text.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(h|hr|hour|hours|m|min|mins|minute|minutes)\b", t)
    minutes = 60
    if m:
        n = float(m.group(1))
        minutes = int(n * 60) if m.group(2).startswith("h") else int(n)
    for key, h in config.habits()["habits"].items():
        if key in t or any(a in t for a in h.get("aliases", [])):
            return {"habit": key, "minutes": minutes, "modality": h.get("modality", "physical")}
    raise ValueError(f"Unknown habit in: {text!r}")
