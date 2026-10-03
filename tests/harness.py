"""Fast DoD harness: temp data dir + fake clock, so a 4-minute session runs in milliseconds."""
import os, sys, tempfile, time, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["ALIBI_DATA_DIR"] = tempfile.mkdtemp(prefix="alibi-test-")
import shutil
# A frozen habits file, not the live habits.yaml: editing your real schedules must never change what tests expect.
os.environ["ALIBI_HABITS"] = shutil.copy(ROOT / "tests" / "habits.test.yaml", os.environ["ALIBI_DATA_DIR"] + "/habits.yaml")
os.environ.setdefault("NOTIFY", "print")
# Never the network, whatever .env says (load_dotenv doesn't override what's already set). Port 9 = discard: refused.
os.environ["NVIDIA_API_KEY"] = ""
os.environ["LLM_MODEL"] = ""
os.environ["LLM_BASE_URL"] = "http://127.0.0.1:9/v1"
os.environ["VLM_MODEL"] = ""
os.environ["NTFY_TOPIC"] = ""                       # never push to the real phone from a test
os.environ["FOCUS_GUARD"] = "0"                    # never redirect a real browser tab; guard tests switch it on
for _k in ("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN", "STRAVA_ACCESS_TOKEN"):
    os.environ[_k] = ""                            # never the real Strava account; blank, so load_dotenv can't refill it
# .env may carry a faster live cadence (20 s samples, Desk View camera); tests expect the defaults unless they ask
os.environ.setdefault("SAMPLE_EVERY_S", "60")
os.environ.setdefault("LAPTOP_EVERY_S", "30")
os.environ.setdefault("CAMERA_INDEX", "0")
# Never the real webcam: a desk session in a test without its own fixture video reads a file that isn't there and
# grabs no frame, like a closed camera. Tests that need frames set CAMERA_SOURCE to a fixture after importing this.
if not os.environ.get("CAMERA_SOURCE"):
    os.environ["CAMERA_SOURCE"] = str(ROOT / "tests" / "fixtures" / "no-camera")
os.environ.setdefault("STRAVA_CLAIM_EVERY_S", "30")
os.environ.setdefault("VISION_BACKEND", "mock")
os.environ.setdefault("ALIBI_FOCUS_SHORTCUTS", "0")  # never run the user's real Shortcuts from a test
os.environ.setdefault("MAC_SIGNALS", "0")          # the real Mac (idle, notifications, git) only where a test asks
os.environ.setdefault("PACE_HOURS", "")             # pace reminders only where a test asks for them
os.environ.setdefault("DIGESTS", "0")              # morning/checkpoint digests only where a test asks


class Clock:
    def __init__(self):
        self.t = time.time()
        self._real = time.time
        time.time = lambda: self.t           # every module reads time.time() at call time

    def advance(self, seconds: float):
        self.t += seconds


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        sys.exit(1)
