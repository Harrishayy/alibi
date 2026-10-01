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
TEXT_READY = bool(NVIDIA_API_KEY.startswith("nvapi-") and len(NVIDIA_API_KEY) > 12 and LLM_MODEL and "<" not in LLM_MODEL)
VISION_BACKEND = os.getenv("VISION_BACKEND") or (
    "nvidia" if TEXT_READY and VLM_MODEL and "<" not in VLM_MODEL else "apple")   # nvidia | apple | mock
