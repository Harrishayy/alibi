"""Deterministic session driver for the lab and the demo (IMPLEMENTATION §7 L6 K4).

    .venv/bin/python docs/design/demo/stage.py SCENARIO [--port 8775] [--data /tmp/alibi-lab] [--every 10]
                                               [--say TEXT] [--capture DIR] [--hold]
                                               [--live] [--phone] [--island]          (recording time only)

    done     on_task 60 s · phone 40 s · on_task 80 s   (3 min; nudge ~1:30; verdict done ~78%)
    partial  on_task 50 s · phone 60 s · on_task 10 s   (2 min; nudge; verdict partial ~50%)
    slacked  on_task 20 s · phone 70 s · absent 30 s    (2 min; nudge; verdict slacked ~17%)
    break    on_task 40 s, says "break 1", then on_task 60 s
    serve    API + daemon, no session (a dashboard / island target); Ctrl-C to stop

It starts its own `python -m alibi.daemon` on --port with --data (a freshly seeded week when the folder is new), the
mock witness and a colour-coded fixture video played in session time, then says --say and prints one line per
transition ("0:42 drifting phone", "1:31 [nudge] ...", "3:00 verdict done 78%"). Session lengths are the scenario's
at --every 10 and scale with --every (--every 5 -> half as long); segment lengths scale with the declared minutes.

Safety (other sessions share this Mac):
  - never touches data/ (refuses a --data inside it); never binds 8765/8766 unless you pass them
  - refuses a busy --port; the phone listener stays off unless --phone
  - --live (real camera + .env witness) refuses while any alibi daemon runs; --phone refuses while :8766 is bound;
    --island refuses while Alibi.app or another island runs
  - no macOS banners, no Shortcuts/Focus, no Mac signals, no pace reminders, no nightly report or digests from the
    stage daemon
  - exit (by itself or Ctrl-C) kills the daemon's process group, which releases the camera
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent

# (minutes at --every 10, [(label, seconds), ...], break after this many plan seconds or None)
SCENARIOS = {
    "done": (3, [("on_task", 60), ("phone", 40), ("on_task", 80)], None),
    "partial": (2, [("on_task", 50), ("phone", 60), ("on_task", 10)], None),
    "slacked": (2, [("on_task", 20), ("phone", 70), ("absent", 30)], None),
    "break": (2, [("on_task", 40), ("on_task", 60)], 40),
    "serve": (0, [], None),
}
BREAK_MIN = 1

# Recording cues for --live, as fractions of the session (DEMO.md take M2).
CUES = {
    "done": [(0.0, "draw"),
             (0.11, "open the Alibi app on the phone, tap \"Show on Lock Screen\", lock it, lay it face up"),
             (0.17, "raise the phone to wake it, then put it down"),
             (0.33, "pick the phone up in camera view, screen towards you, scroll for 40 s"),
             (0.53, "the nudge drops: click \"Back to it\", phone face down, draw"),
             (1.0, "verdict on the island")],
    "partial": [(0.0, "draw"), (0.42, "pick the phone up in camera view and scroll"), (0.92, "draw again"),
                (1.0, "verdict")],
    "slacked": [(0.0, "draw"), (0.17, "pick the phone up in camera view and scroll"), (0.75, "walk out of frame"),
                (1.0, "verdict")],
    "break": [(0.0, "draw"), (0.33, "break starts (said for you)"), (1.0, "verdict")],
}


def clock(s: float) -> str:
    s = max(0, int(s))
    return f"{s // 60}:{s % 60:02d}"


def port_busy(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def pgrep(pattern: str) -> list[str]:
    r = subprocess.run(["pgrep", "-fl", pattern], capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.strip() and str(os.getpid()) != l.split()[0]]


def refuse(msg: str) -> None:
    print(f"stage: {msg}", file=sys.stderr)
    sys.exit(2)


def said_minutes(text: str) -> int | None:
    m = re.search(r"(\d+)\s*(h|hr|hrs|hour|hours|m|min|mins|minute|minutes)\b", text.lower())
    if not m:
        return None
    return int(m.group(1)) * (60 if m.group(2).startswith("h") else 1)


# --- data dir ----------------------------------------------------------------------------------------------------

OFFLINE = dict(NOTIFY="print", MAC_SIGNALS="0", ALIBI_FOCUS_SHORTCUTS="0", VISION_BACKEND="mock", NVIDIA_API_KEY="",
               LLM_MODEL="")   # no banners, no Shortcuts, no model calls (a blank model also stops a Spark LLM_BASE_URL)


def seed(data: pathlib.Path) -> None:
    """A new folder gets a fresh, deterministic week from scripts/seed_demo.py. Copying data/demo would also copy
    whatever test sessions have landed there since it was seeded."""
    data.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("STRAVA_")}
    env.update(OFFLINE, ALIBI_DATA_DIR=str(data))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_demo.py")], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    if r.returncode or not (data / "alibi.db").exists():
        shutil.rmtree(data, ignore_errors=True)
        refuse(f"seeding {data} failed: {(r.stderr or r.stdout)[-600:]}")
    print(f"stage: new data dir {data} (a freshly seeded week)")


def prepare_data(data: pathlib.Path, phone: bool) -> None:
    real = (ROOT / "data").resolve()
    if data == real or real in data.parents:
        refuse(f"--data {data} is inside {real}; use a temp folder (e.g. /tmp/alibi-lab)")
    if not data.exists():
        seed(data)
    if not (data / "habits.yaml").exists():
        shutil.copyfile(ROOT / "habits.yaml", data / "habits.yaml")
    st_path = data / "integrations_state.json"
    try:
        st = json.loads(st_path.read_text())
    except (OSError, ValueError):
        st = {}
    st["phone_sync_enabled"] = bool(phone)
    st_path.write_text(json.dumps(st))
    if phone:
        try:
            key = json.loads((ROOT / "data" / "secrets.json").read_text()).get("phone_secret")
        except (OSError, ValueError):
            key = None
        if not key:
            refuse("--phone: data/secrets.json has no phone_secret (pair the phone with the main Alibi once)")
        sp = data / "secrets.json"
        try:
            sec = json.loads(sp.read_text())
        except (OSError, ValueError):
            sec = {}
        sec["phone_secret"] = key                       # the installed app was baked with the main key
        fd = os.open(sp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(sec, f, indent=1)


def fixture_video(data: pathlib.Path, name: str, plan: list[tuple[str, int]]) -> pathlib.Path:
    """The colour-coded desk video the mock witness reads (tests/make_fixtures.py), written into the stage dir."""
    sys.path.insert(0, str(ROOT / "tests"))
    import make_fixtures                                    # needs cv2: run stage.py with .venv/bin/python
    make_fixtures.OUT = data / "stage-video"
    return make_fixtures.video(name, plan)


# --- HTTP --------------------------------------------------------------------------------------------------------

class Api:
    def __init__(self, port: int):
        self.base = f"http://127.0.0.1:{port}"

    def call(self, path: str, body: dict | None = None):
        req = urllib.request.Request(self.base + path,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)

    def state(self) -> dict | None:
        try:
            return self.call("/api/state")
        except (OSError, ValueError):
            return None


# --- capture -----------------------------------------------------------------------------------------------------

class Capture:
    """Saves /api/state under the fixture names the lanes use; frames swapped for data/demo session 6 photos (the
    mock frames are flat colour cards and only resolve on the stage server); pinch recomputed with alibi.pinch."""

    def __init__(self, out: pathlib.Path | None, only: set[str] | None):
        self.out, self.only = out, only
        self.saved: set[str] = set()
        if out:
            sys.path.insert(0, str(ROOT))
            import importlib.util
            from alibi.pinch import pinch_state
            spec = importlib.util.spec_from_file_location("demo_make_fixtures", HERE / "make_fixtures.py")
            mf = importlib.util.module_from_spec(spec)      # K1's script; not tests/make_fixtures.py
            spec.loader.exec_module(mf)
            self.pinch_state = pinch_state
            self.pool, self.src = mf.frame_pool(None)
            out.mkdir(parents=True, exist_ok=True)

    def frame(self, label: str, i: int) -> str | None:
        frames = self.pool.get(label) or self.pool.get("phone" if label != "on_task" else "on_task") or []
        return frames[i % len(frames)] if frames else None

    def relabel(self, rows: list) -> None:
        seen: dict = {}
        for row in rows or []:
            if isinstance(row, dict) and row.get("frame_url"):
                lab = row.get("label", "on_task")
                row["frame_url"] = self.frame(lab, seen.get(lab, 0))
                seen[lab] = seen.get(lab, 0) + 1

    def save(self, name: str, st: dict, once: bool = False) -> None:
        if not self.out or (self.only and name not in self.only) or (once and name in self.saved):
            return
        st = self.clean(st)
        (self.out / f"{name}.json").write_text(json.dumps(st, indent=1, ensure_ascii=False) + "\n")
        self.saved.add(name)

    def clean(self, st: dict) -> dict:
        st = json.loads(json.dumps(st))
        ev = f"/files/evidence/{self.src}.jpg"
        for s in (st.get("session"), st.get("recent_verdict")):
            if s:
                self.relabel(s.get("labels"))
                if s.get("labels"):
                    s["last_frame_url"] = s["labels"][-1].get("frame_url") if "last_frame_url" in s else None
                if s.get("evidence_url"):
                    s["evidence_url"] = ev
                if "reel_url" in s:
                    s["reel_url"] = None
                if "last_frame_url" in s and not s.get("labels"):
                    s["last_frame_url"] = None
        a = st.get("alert")
        if a and a.get("kind") == "info" and str(a.get("text", "")).startswith("Alibi daemon up"):
            st["alert"] = a = None                          # the stage daemon's own boot line, not a moment
        if a and a.get("image_url"):
            a["image_url"] = ev
        if st.get("witness") == "mock":                     # fixtures show what the demo Mac runs (DEMO.md §3)
            st["witness"], st["witness_label"] = "apple", "Apple Vision"
        if a and a.get("image"):
            a["image"] = None                               # a local path on the stage machine
        for s in (st.get("session"), st.get("recent_verdict")):
            if s and s.get("evidence_path"):
                s["evidence_path"] = None
        st["pinch"] = self.pinch_state({k: st.get(k) for k in ("now", "session", "alert", "recent_verdict")})
        return st


# --- main --------------------------------------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Alibi demo stage: a scripted session on a lab daemon.")
    ap.add_argument("scenario", choices=sorted(SCENARIOS))
    ap.add_argument("--port", type=int, default=8775)
    ap.add_argument("--data", default="/tmp/alibi-lab")
    ap.add_argument("--every", type=int, default=10, help="seconds between camera samples")
    ap.add_argument("--say", help='what to declare (default "draw for N minutes", N from the scenario)')
    ap.add_argument("--capture", metavar="DIR", help="save /api/state at each transition (fixture names)")
    ap.add_argument("--capture-only", metavar="A,B", help="with --capture: only these fixture names")
    ap.add_argument("--hold", action="store_true", help="keep serving after the verdict (Ctrl-C to stop)")
    ap.add_argument("--live", action="store_true", help="recording only: real camera and the .env witness")
    ap.add_argument("--phone", action="store_true", help="recording only: phone listener on :8766, main key")
    ap.add_argument("--island", action="store_true", help="recording only: launch bin/alibi-island on --port")
    a = ap.parse_args()

    minutes0, plan0, break_at0 = SCENARIOS[a.scenario]
    data = pathlib.Path(a.data).expanduser().resolve()

    # Refusals first: nothing is started or written until every check passes.
    if port_busy(a.port):
        refuse(f"port {a.port} is in use (Alibi.app or another stage?). Quit it first or pick another --port.")
    if a.live:
        if pgrep("alibi.daemon"):
            refuse("--live: an Alibi daemon is running and may hold the camera. Run ./alibi.sh down first.")
    if a.phone and port_busy(8766):
        refuse("--phone: :8766 is already bound (the main Alibi's phone listener). Run ./alibi.sh down first.")
    if a.island:
        if pgrep("Alibi.app/Contents/MacOS/Alibi") or pgrep("alibi-island"):
            refuse("--island: Alibi.app or another island is running. Quit it first (./alibi.sh down).")
        if not (ROOT / "bin" / "alibi-island").exists():
            refuse("--island: bin/alibi-island is missing (bash scripts/build_native.sh)")
    if a.port in (8765, 8766) and not a.live and not a.island and not a.phone:
        print(f"stage: note: --port {a.port} is the main Alibi's port; fine only while it is down")

    session_s = 0
    say = None
    if a.scenario != "serve":
        default_min = max(1, round(minutes0 * a.every / 10))
        say = a.say or f"draw for {default_min} minute{'s' * (default_min != 1)}"
        session_s = 60 * (said_minutes(say) or default_min)

    prepare_data(data, a.phone)
    env = {k: v for k, v in os.environ.items() if not k.startswith("STRAVA_")}
    env.update(ALIBI_DATA_DIR=str(data), ALIBI_HABITS=str(data / "habits.yaml"), API_PORT=str(a.port),
               SAMPLE_EVERY_S=str(a.every), NOTIFY="print", ALIBI_FOCUS_SHORTCUTS="0", MAC_SIGNALS="0",
               PACE_HOURS="", REPORT_HOUR="-1", DIGESTS="0", PYTHONUNBUFFERED="1")
    if not a.phone:
        env["PHONE_PORT"] = str(a.port + 1 if a.port + 1 not in (8765, 8766) else a.port + 3)
    if not a.live:
        # Deterministic: mock witness on a colour-coded video, rule-based text (no model calls).
        env.update(VISION_BACKEND="mock", NVIDIA_API_KEY="", LLM_MODEL="")
        if session_s:
            total = sum(s for _, s in plan0)
            k = session_s / total
            plan = [(lab, max(1, round(s * k))) for lab, s in plan0]
            extra = (BREAK_MIN * 60 if break_at0 is not None else 0) + 120   # the bell and a margin hold the last label
            plan[-1] = (plan[-1][0], plan[-1][1] + extra)
            env["CAMERA_SOURCE"] = str(fixture_video(data, f"{a.scenario}-{session_s}s.mp4", plan))
        else:
            env["CAMERA_SOURCE"] = str(fixture_video(data, "serve.mp4", [("on_task", 3600)]))

    log = open(data / "stage-daemon.log", "a")
    daemon = subprocess.Popen([sys.executable, "-m", "alibi.daemon"], cwd=ROOT, env=env, stdout=log,
                              stderr=subprocess.STDOUT, start_new_session=True)
    island = None
    stopped = {"done": False}

    def stop() -> None:
        if stopped["done"]:
            return
        stopped["done"] = True
        for p in (island, daemon):
            if p and p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for p in (island, daemon):
            if p:
                try:
                    p.wait(5)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
        print("Stage stopped. Camera off.", flush=True)

    def on_signal(*_):
        print()
        stop()
        sys.exit(130)

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    api = Api(a.port)
    cap = Capture(pathlib.Path(a.capture).resolve() if a.capture else None,
                  set(a.capture_only.split(",")) if a.capture_only else None)
    try:
        for _ in range(80):
            if daemon.poll() is not None:
                refuse(f"daemon exited early; see {data / 'stage-daemon.log'}")
            if api.state() is not None:
                break
            time.sleep(0.25)
        else:
            refuse(f"daemon did not answer on :{a.port}; see {data / 'stage-daemon.log'}")
        st = api.state()
        if st.get("session"):
            api.call("/api/say", {"text": "end"})                       # a leftover session from an earlier run
            time.sleep(0.5)
            st = api.state()
        if a.island:
            ienv = {**os.environ, "ALIBI_API": api.base}
            island = subprocess.Popen([str(ROOT / "bin" / "alibi-island")], cwd=ROOT, env=ienv,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            time.sleep(1.5)
        mode = "live camera" if a.live else "mock witness"
        print(f"stage: {a.scenario} on {api.base} · data {data} · {mode} · a sample every {a.every} s", flush=True)
        if a.scenario == "serve":
            cap.save("idle", st)
            print("Serving. Ctrl-C to stop.", flush=True)
            while daemon.poll() is None:
                time.sleep(1)
            return 1

        cap.save("idle", st)
        print(f"stage: say \"{say}\" -> {api.call('/api/say', {'text': say}).get('reply', '')}", flush=True)
        return run(a, api, cap, session_s, break_at0, plan0, stop)
    finally:
        stop()
        log.close()


def run(a, api: Api, cap: Capture, session_s: int, break_at0, plan0, stop) -> int:
    st = api.state() or {}
    s = st.get("session")
    if not s:
        print("stage: no session started (check --say)", flush=True)
        return 1
    sid, t0 = s["id"], s["started_at"]
    cap.save("live_listening", st)
    if a.live:
        print("\nRecording cues:")
        for f, cue in CUES.get(a.scenario, []):
            print(f"  {clock(f * session_s)}  {cue}")
        print(flush=True)
    break_at = None if break_at0 is None else break_at0 * session_s / sum(x for _, x in plan0)
    said_break = False
    seen_alert = (st.get("alert") or {}).get("id")
    last = {"label": None, "drift": None, "brk": False, "samples": 0}
    verdict_line = None
    deadline = time.time() + session_s + 3 * 60 + 600
    while time.time() < deadline:
        st = api.state()
        if st is None:
            time.sleep(0.5)
            continue
        now = st.get("now") or time.time()
        t = clock(now - t0)
        s = st.get("session")
        al = st.get("alert")
        if s and s.get("id") == sid:
            if break_at is not None and not said_break and now - t0 >= break_at:
                said_break = True
                print(f"{t} say \"break {BREAK_MIN}\" -> {api.call('/api/say', {'text': f'break {BREAK_MIN}'}).get('reply', '')}",
                      flush=True)
                continue
            brk = bool(s.get("on_break"))
            if brk != last["brk"]:
                print(f"{t} {'break' if brk else 'back from break'}", flush=True)
                last["brk"] = brk
                if brk:
                    cap.save("break", st, once=True)
            drift = (s.get("drifting") or {}).get("label")
            lab = (s.get("last_seen") or {}).get("label")
            if drift != last["drift"]:
                print(f"{t} {'drifting ' + drift if drift else 'on task'}", flush=True)
                if drift:
                    cap.save("live_drifting", st, once=True)
                last["drift"] = drift
            elif lab and lab != last["label"] and not drift:
                print(f"{t} {lab.replace('_', ' ')}", flush=True)
            last["label"] = lab or last["label"]
            n = s.get("samples") or 0
            if n != last["samples"]:
                last["samples"] = n
                if not drift and not brk and lab == "on_task" and not s.get("warming_up") \
                        and "live_drifting" not in cap.saved and not (al and al.get("kind") == "nudge"):
                    cap.save("live_focused", st)                       # the last calm moment before the drift
        if al and al.get("id") != seen_alert:
            seen_alert = al["id"]
            print(f"{t} [{al.get('kind')}] {al.get('text', '')}", flush=True)
            if al.get("kind") == "nudge" and al.get("session_id") == sid:
                cap.save("nudge_phone" if al.get("label") != "off_task" else "nudge_window", st, once=True)
            if al.get("kind") == "verdict" and al.get("session_id") == sid:
                v = al.get("verdict")
                r = al.get("ratio")
                verdict_line = f"{t} verdict {v} {r:.0%}" if r is not None else f"{t} verdict {v}"
                print(verdict_line, flush=True)
                time.sleep(1.2)                                        # let recent_verdict settle, then capture
                cap.save(f"verdict_{v}", api.state() or st)
                break
        # The verdict alert can be buried within one poll (e.g. a planned-block prompt right after the bell), so the
        # session's own recent_verdict also counts.
        if not s and verdict_line is None and (st.get("recent_verdict") or {}).get("id") == sid:
            rv = st["recent_verdict"]
            verdict_line = f"{t} verdict {rv.get('verdict')} {rv.get('on_task_ratio', 0):.0%}"
            print(verdict_line, flush=True)
            break
        time.sleep(0.5)
    if verdict_line is None:
        print("stage: timed out waiting for the verdict", flush=True)
        return 1
    if cap.saved:
        print(f"stage: captured {', '.join(sorted(cap.saved))} -> {cap.out}", flush=True)
    if a.hold or a.live or a.island or a.phone:
        print(f"Serving on {api.base} (dashboard ?moment=verdict). Ctrl-C to stop.", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    stop()
    print(verdict_line.split(" ", 1)[1], flush=True)                   # the last line: "verdict done 78%"
    return 0


if __name__ == "__main__":
    sys.exit(main())
