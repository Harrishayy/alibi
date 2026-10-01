"""Settings + habits.yaml loader. Shared by every module."""
import os, pathlib, yaml
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

HABITS_PATH = pathlib.Path(os.getenv("ALIBI_HABITS", ROOT / "habits.yaml"))
DATA_DIR = pathlib.Path(os.getenv("ALIBI_DATA_DIR", ROOT / "data")).resolve()   # tests point this at a temp dir
FRAMES_DIR = DATA_DIR / "frames"
EVIDENCE_DIR = DATA_DIR / "evidence"

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "")
VLM_BASE_URL = os.getenv("VLM_BASE_URL", LLM_BASE_URL)
VLM_MODEL = os.getenv("VLM_MODEL", "")

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
# Judge a one-minute timelapse clip instead of a single frame (video VLM, e.g. nvidia/nemotron-3-nano-omni-30b-a3b-reasoning).
VLM_VIDEO = os.getenv("VLM_VIDEO", "0") == "1"
VLM_THINK = os.getenv("VLM_THINK", "1") == "1"         # let the video VLM reason before labelling
SAMPLE_EVERY_S = int(os.getenv("SAMPLE_EVERY_S", "60"))
MOTION_THRESHOLD = float(os.getenv("MOTION_THRESHOLD", "6.0"))
NOTIFY = os.getenv("NOTIFY", "print")
REPORT_HOUR = int(os.getenv("REPORT_HOUR", "22"))


def habits() -> dict:
    """Re-read every call so you can edit habits.yaml without restarting the daemon."""
    with open(HABITS_PATH) as f:
        return yaml.safe_load(f)

CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "")          # "" = live webcam, or a path to a video file
LAPTOP_EVERY_S = int(os.getenv("LAPTOP_EVERY_S", "30"))
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8765"))
INGEST_SECRET = os.getenv("INGEST_SECRET", "")
ALERTS_PATH = DATA_DIR / "alerts.jsonl"

# No key yet? Everything still runs: text falls back to rules, vision to Apple's on-device Vision framework.
def _local_llm(base_url: str) -> bool:
    """A self-hosted OpenAI-compatible server (e.g. the Spark over Tailscale) needs no nvapi key."""
    from urllib.parse import urlparse
    host = (urlparse(base_url).hostname or "").lower()
    return bool(host) and host != "nvidia.com" and not host.endswith(".nvidia.com")


_MODEL_OK = bool(LLM_MODEL and "<" not in LLM_MODEL)
TEXT_READY = _MODEL_OK and (
    (NVIDIA_API_KEY.startswith("nvapi-") and len(NVIDIA_API_KEY) > 12) or _local_llm(LLM_BASE_URL))
# Vision stays on the Mac unless asked otherwise: a text model being ready must never silently ship camera frames
# to Build or the Spark (AGENTS.md rule 5). Set VISION_BACKEND=nvidia explicitly to use VLM_MODEL.
VISION_BACKEND = os.getenv("VISION_BACKEND") or "apple"   # nvidia | apple | mock


def photo_where() -> str:
    """Where camera photos go, worded exactly (AGENTS.md rule 5): only apple/mock may say they stay on the Mac."""
    if VISION_BACKEND != "nvidia":
        return "Photos stay on this Mac."
    return ("Photos go to your own model server to be checked." if _local_llm(VLM_BASE_URL)
            else "Photos go to NVIDIA's model to be checked.")


def photo_text(text: str) -> str:
    return text.replace("Photos stay on this Mac.", photo_where())

# --- added: limits, pace reminders, drift consequences --------------------------------------------------------
MAX_SESSION_MIN = int(os.getenv("MAX_SESSION_MIN", "240"))       # longer claims must be said in chunks
PACE_HOURS = tuple(int(h) for h in os.getenv("PACE_HOURS", "11,15,19").split(",") if h.strip())
BLOCK_ON_DRIFT = os.getenv("BLOCK_ON_DRIFT", "0") == "1"           # hide the off-task app on the 2nd nudge (digital)
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALIBI_ALLOWED_HOSTS", "").split(",") if h.strip()]

DISPLAY_NAMES = {"cpp": "C++"}


def display_name(key: str, cfg: dict | None = None) -> str:
    """habits.yaml `label:` (or `display:`) wins; then a small map (cpp -> C++); else Capitalised key."""
    try:
        h = (cfg or habits())["habits"].get(key) or {}
    except Exception:
        h = {}
    return str(h.get("label") or h.get("display") or DISPLAY_NAMES.get(key) or key.replace("_", " ").capitalize())


LABEL_TEXT = {"on_task": "On task", "phone": "On your phone", "absent": "Away from desk", "idle": "Idle",
              "off_task": "Off task"}


def spoken_name(key: str) -> str:
    """Mid-sentence form: 'You said drawing.' but 'You said C++.'"""
    n = display_name(key)
    return key.replace("_", " ") if n == key.replace("_", " ").capitalize() else n


# --- round 3: plain-language habit kinds, schedules, health habits, secrets, first-run flag ---------------------
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
HEALTH_METRICS = {   # metric -> (plain name, unit, default target, how it's said in a sentence)
    "steps": ("Steps", "steps", 8000, "{v:,.0f} steps"),
    "sleep_h": ("Sleep", "h", 7, "{v:.1f} h of sleep"),
    "mindful_min": ("Meditate", "min", 10, "{v:.0f} mindful min"),
    "workout_min": ("Workout", "min", 30, "{v:.0f} workout min"),
}
# How Alibi checks a habit, in the words the dashboard/island show. Keys are what /api/habits/kinds returns.
CHECK_TEXT = {"camera": "Camera on my desk", "screen": "What's on my screen", "both": "Camera and screen",
              "strava": "Strava", "health": "Apple Health"}
MODALITY_TO_CHECK = {"physical": "camera", "digital": "screen", "hybrid": "both"}
CHECK_TO_MODALITY = {v: k for k, v in MODALITY_TO_CHECK.items()}
ONBOARDED_PATH = DATA_DIR / "onboarded"
SECRETS_PATH = DATA_DIR / "secrets.json"


def habit_check(h: dict) -> str:
    """camera | screen | both | strava | health — the plain answer to 'How should Alibi check it?'."""
    if h.get("source") in ("strava", "health"):
        return h["source"]
    return MODALITY_TO_CHECK.get(h.get("modality", ""), "camera")


def secrets() -> dict:
    """data/secrets.json (chmod 600, never in git) — a thin alias of alibi.secrets.load()."""
    from . import secrets as store
    return store.load()


def save_secrets(**kv) -> dict:
    """Merge keys into data/secrets.json (None deletes a key) — alias of alibi.secrets.update(), one writer."""
    from . import secrets as store
    return store.update(**kv)


def habit_created_ts(h: dict) -> float | None:
    """`created_at: "2026-10-01 18:02"` (stamped by health.save_habits on new habits) -> epoch seconds, else None."""
    import datetime as _dt
    v = (h or {}).get("created_at")
    if not v:
        return None
    try:
        return float(v) if isinstance(v, (int, float)) else _dt.datetime.fromisoformat(str(v)).timestamp()
    except ValueError:
        return None

# --- F5 digests: 07:30 brief, checkpoints, the night review (alibi/digest.py) ------------------------------------------
MORNING_AT = os.getenv("MORNING_AT", "07:30")                     # HH:MM, minute-aware
CHECK_HOURS = tuple(int(h) for h in os.getenv("CHECK_HOURS", "12,16,20").split(",") if h.strip())
DIGESTS = os.getenv("DIGESTS", "1") == "1"                        # morning + checkpoint slots (the night one always runs)
DIGEST_GAP_FROM, DIGEST_GAP_TO = os.getenv("DIGEST_DAY", "07:00-22:00").split("-")   # where replans may land
