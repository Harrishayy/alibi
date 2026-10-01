"""Who judges a frame. nvidia = VLM on NVIDIA Build (or a local server); apple = on-device Vision; mock = colour code (tests)."""
import json, subprocess
from . import config, db, llm

SYSTEM = ("You verify whether a person at a desk is doing what they said. "
          "Reply with JSON only: {\"label\": \"on_task|phone|idle|absent|off_task\", \"note\": \"<12 words\"}.")
WITNESS_BIN = config.ROOT / "bin" / "alibi-witness"
PHONE_WORDS = ("phone", "cellphone", "smartphone", "telephone", "mobile")


def prompt_for(habit_key: str, habit_cfg: dict) -> str:
    return (f"The person declared they are doing: {habit_key}. "
            f"On task looks like: {habit_cfg.get('on_task_looks_like', habit_key)}. "
            "phone = holding or looking at a phone. idle = present but not working. absent = nobody there.")


def judge(jpeg: bytes, path: str, habit_key: str, habit_cfg: dict, backend: str | None = None) -> dict:
    backend = backend or config.VISION_BACKEND
    try:
        out = {"nvidia": _nvidia, "apple": _apple, "mock": _mock}[backend](jpeg, path, habit_key, habit_cfg)
    except Exception as e:
        out = {"label": "idle", "note": f"witness error: {type(e).__name__}"}
    if out.get("label") not in db.LABELS:
        out["label"] = "off_task"
    out["note"] = str(out.get("note", ""))[:80]
    out["backend"] = backend
    return out


def _nvidia(jpeg, path, habit_key, habit_cfg):
    return llm.vision_json(SYSTEM, prompt_for(habit_key, habit_cfg), jpeg)


def _apple(jpeg, path, habit_key, habit_cfg):
    r = json.loads(subprocess.run([str(WITNESS_BIN), path], capture_output=True, text=True, timeout=20).stdout or "{}")
    classes = r.get("classes", {})
    phone = max((v for k, v in classes.items() if any(w in k for w in PHONE_WORDS)), default=0)
    people = max(r.get("humans", 0), r.get("faces", 0))
    hands = r.get("hands", 0)
    if phone > 0.25:
        return {"label": "phone", "note": f"phone in frame ({phone:.0%})"}
    if not people and not hands:
        return {"label": "absent", "note": "nobody at the desk"}
    if hands:
        top = max(classes, key=classes.get) if classes else "desk"
        return {"label": "on_task", "note": f"{hands} hand(s) working, {top.replace('_', ' ')}"}
    return {"label": "idle", "note": "present, hands not on the work"}


def _mock(jpeg, path, habit_key, habit_cfg):
    """Tests paint frames: green=on_task, red=phone, blue=idle, dark=absent."""
    from PIL import Image
    r, g, b = Image.open(path).convert("RGB").resize((8, 8)).getdata()[27]
    if max(r, g, b) < 40:
        return {"label": "absent", "note": "dark frame"}
    if g > r and g > b:
        return {"label": "on_task", "note": "green frame"}
    if r > g and r > b:
        return {"label": "phone", "note": "red frame"}
    return {"label": "idle", "note": "blue frame"}
