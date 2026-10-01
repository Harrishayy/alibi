"""Fast DoD harness: temp data dir + fake clock, so a 4-minute session runs in milliseconds."""
import os, sys, tempfile, time, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["ALIBI_DATA_DIR"] = tempfile.mkdtemp(prefix="alibi-test-")
import shutil
os.environ["ALIBI_HABITS"] = shutil.copy(ROOT / "habits.yaml", os.environ["ALIBI_DATA_DIR"] + "/habits.yaml")
os.environ.setdefault("NOTIFY", "print")
os.environ.setdefault("VISION_BACKEND", "mock")
os.environ.setdefault("PACE_HOURS", "")             # pace reminders only where a test asks for them


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
