"""Settings + habits.yaml loader. Shared by every module."""
import os, pathlib, yaml
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
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
    with open(ROOT / "habits.yaml") as f:
        return yaml.safe_load(f)
