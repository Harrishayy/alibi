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
