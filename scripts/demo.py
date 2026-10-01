"""P12 — a fast, real run for recording the demo video.

  ./alibi.sh demo                 live camera + Apple Vision, samples every 10 s, 2-minute drawing session
  ./alibi.sh demo --fixture       no camera: replays a synthetic desk video with the mock witness (dry run)
  ./alibi.sh demo --say "build for 3 minutes" --every 8

Uses data/demo (seeded week, so the dashboard looks lived-in). Ctrl-C stops everything and turns the camera off.
"""
import argparse, json, os, pathlib, signal, subprocess, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8765"


def call(path, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--say", default="draw for 2 minutes")
    ap.add_argument("--every", type=int, default=10, help="seconds between camera samples")
    ap.add_argument("--fixture", action="store_true")
    a = ap.parse_args()

    subprocess.run([str(ROOT / "alibi.sh"), "down"], capture_output=True)
    env = {**os.environ, "ALIBI_DATA_DIR": str(ROOT / "data" / "demo"), "SAMPLE_EVERY_S": str(a.every),
           "NOTIFY": "macos"}
    if not (ROOT / "data" / "demo" / "alibi.db").exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_demo.py")], env=env, check=True)
    if a.fixture:
        sys.path.insert(0, str(ROOT / "tests"))
        import make_fixtures
        env["CAMERA_SOURCE"] = str(make_fixtures.video("demo_2min.mp4", [("on_task", 45), ("phone", 45), ("absent", 30)]))
        env["VISION_BACKEND"] = "mock"
    proc = subprocess.Popen([str(ROOT / "scripts" / "launch.sh")], env=env, start_new_session=True)

    def stop(*_):
        os.killpg(proc.pid, signal.SIGTERM)
        subprocess.run([str(ROOT / "alibi.sh"), "down"], capture_output=True)
        print("\nDemo stopped. Camera off.")
        sys.exit(0)
    signal.signal(signal.SIGINT, stop)

    for _ in range(60):
        try:
            call("/api/state"); break
        except OSError:
            time.sleep(0.5)
    time.sleep(1.5)   # let the island appear before the session starts
    print(call("/api/say", {"text": a.say})["reply"])
    s = call("/api/state")["session"]
    total = s["ends_at"] - s["started_at"]
    print(f"\nRecording cues ({int(total)} s session, a sample every {a.every} s):")
    print(f"  0:00  do the thing — draw, build, whatever you declared")
    print(f"  {int(total * .35) // 60}:{int(total * .35) % 60:02d}  pick up your phone and scroll → nudge drops from the notch")
    print(f"  {int(total * .75) // 60}:{int(total * .75) % 60:02d}  walk out of frame")
    print(f"  {int(total) // 60}:{int(total) % 60:02d}  verdict + contact sheet; the reel follows a few seconds later\n")
    sid = s["id"]
    seen = None
    while True:
        st = call("/api/state")
        al = st.get("alert")
        if al and al["id"] != seen:
            seen = al["id"]
            print(f"  [{al['kind']}] {al['text']}")
        if st["session"] is None:
            done = [x for x in call("/api/sessions?limit=5") if x["id"] == sid]
            if done and done[0].get("reel_url"):
                print(f"\nReel: {API}{done[0]['reel_url']}\nDashboard: {API}\nCtrl-C to stop.")
                break
        time.sleep(1)
    signal.pause()


if __name__ == "__main__":
    main()
