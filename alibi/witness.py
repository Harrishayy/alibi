"""Who judges a frame. nvidia = VLM on NVIDIA Build (or a local server); apple = on-device Vision; mock = colour code (tests)."""
import json, subprocess, tempfile
from . import config, db, llm

SYSTEM = ("You verify whether a person at a desk is doing what they said. "
          "Reply with JSON only: {\"label\": \"on_task|phone|idle|absent|off_task\", \"note\": \"<12 words\"}.")
WITNESS_BIN = config.ROOT / "bin" / "alibi-witness"
PHONE_WORDS = ("phone", "cellphone", "smartphone", "telephone", "mobile")


def lessons(habit_key: str, limit: int = 5) -> list[dict]:
    """The user's last corrections for this habit: [{was, label, note}] (F6). Newest first."""
    try:
        con = db.connect()
        rows = con.execute("SELECT e.payload FROM events e JOIN sessions s ON s.id=e.session_id WHERE e.source='user' "
                           "AND e.kind='correction' AND s.habit=? ORDER BY e.ts DESC LIMIT ?", (habit_key, limit * 4))
        out = [json.loads(r["payload"]) for r in rows]
    except Exception:
        return []
    return [x for x in out if x.get("was") and x.get("was") != x.get("label")][:limit]


def prompt_for(habit_key: str, habit_cfg: dict) -> str:
    base = (f"The person declared they are doing: {habit_key}. "
            f"On task looks like: {habit_cfg.get('on_task_looks_like', habit_key)}. "
            "phone = holding or looking at a phone. idle = present but not working. absent = nobody there.")
    past = lessons(habit_key)
    if past:
        base += " The person has corrected you before; learn from it: " + " ".join(
            f'Previously "{x.get("note") or x["was"]}" ({x["was"]}) was corrected to {x["label"]}.' for x in past)
    return base


def _apply_lessons(out: dict, habit_key: str) -> dict:
    """On-device witnesses can't read a prompt, so apply the user's rule directly: the same (label, note) corrected
    the same way twice for this habit is overruled from now on."""
    from collections import Counter
    votes = Counter((x["was"], x.get("note", ""), x["label"]) for x in lessons(habit_key, 20))
    for (was, note, new), n in votes.items():
        if n >= 2 and was == out.get("label") and note == out.get("note"):
            return {**out, "label": new, "note": f"{out.get('note', '')} — you've overruled this before"[:80],
                    "learned_from": was}
    return out


def judge(jpeg: bytes, path: str, habit_key: str, habit_cfg: dict, backend: str | None = None) -> dict:
    backend = backend or config.VISION_BACKEND
    try:
        out = {"nvidia": _nvidia, "apple": _apple, "mock": _mock}[backend](jpeg, path, habit_key, habit_cfg)
    except Exception as e:
        out = {"label": "idle", "note": f"witness error: {type(e).__name__}"}
    if out.get("label") not in db.LABELS:
        out["label"] = "off_task"
    if backend != "nvidia":
        out = _apply_lessons(out, habit_key)
    out["note"] = str(out.get("note", ""))[:80]
    out["backend"] = backend
    return out


CLIP_FPS = 2                                     # timelapse playback rate; one frame per daemon tick when captured


def encode_clip(jpegs: list[bytes]) -> bytes:
    """JPEG frames -> small H.264 mp4 (ffmpeg, same as reels)."""
    with tempfile.TemporaryDirectory() as tmp:
        for i, j in enumerate(jpegs):
            with open(f"{tmp}/{i:05d}.jpg", "wb") as f:
                f.write(j)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(CLIP_FPS), "-i", f"{tmp}/%05d.jpg",
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        f"{tmp}/clip.mp4"], check=True, timeout=30)
        with open(f"{tmp}/clip.mp4", "rb") as f:
            return f.read()


def judge_clip(jpegs: list[bytes], path: str, habit_key: str, habit_cfg: dict, span_s: float) -> dict:
    """VLM_VIDEO: judge the last minute as a timelapse. Falls back to the newest frame alone if the clip call fails."""
    try:
        prompt = (f"This is a timelapse of the last {round(span_s)} seconds at the desk, {len(jpegs)} frames in order. "
                  "Judge the whole span, not one moment: a brief glance away is still on_task; label phone, idle or "
                  "absent only if that is what most of the clip shows. " + prompt_for(habit_key, habit_cfg))
        out = llm.vision_video_json(SYSTEM, prompt, encode_clip(jpegs))
        if out.get("label") not in db.LABELS:
            raise ValueError("no label")
        return {"label": out["label"], "note": str(out.get("note", ""))[:80], "backend": "nvidia-video",
                "clip_frames": len(jpegs)}
    except Exception as e:
        out = judge(jpegs[-1], path, habit_key, habit_cfg)
        out["clip_error"] = type(e).__name__
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
        return {"label": "absent", "note": "nobody at the desk"}
    if g > r and g > b:
        return {"label": "on_task", "note": "hands on the work"}
    if r > g and r > b:
        return {"label": "phone", "note": "phone in hand"}
    return {"label": "idle", "note": "at the desk, hands still"}
