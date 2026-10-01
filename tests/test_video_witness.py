"""Video witness (VLM_VIDEO=1): the camera keeps a frame per daemon tick between judgements, the VLM judges the minute
as one timelapse clip, a failed clip call falls back to the single frame, and VLM_VIDEO off changes nothing."""
import os
os.environ["SAMPLE_EVERY_S"] = "60"
os.environ["VLM_VIDEO"] = "1"
os.environ["VISION_BACKEND"] = "nvidia"
from harness import Clock, check
import make_fixtures
os.environ["CAMERA_SOURCE"] = str(make_fixtures.video("desk_video.mp4", [("on_task", 30), ("phone", 10), ("on_task", 100), ("phone", 40), ("on_task", 10), ("phone", 110)]))
from alibi import camera, cli, config, db, llm, witness

calls = {"clip": [], "frame": 0, "fail": False}
witness.encode_clip = lambda jpegs: b"mp4:%d" % len(jpegs)           # no ffmpeg needed in tests


def fake_video(system, prompt, mp4):
    if calls["fail"]:
        raise TimeoutError("omni down")
    calls["clip"].append((mp4, prompt))
    return {"label": "on_task", "note": "drawing the whole minute"}


def fake_frame(system, prompt, jpeg):
    calls["frame"] += 1
    return {"label": "phone", "note": "single frame"}


llm.vision_video_json, llm.vision_json = fake_video, fake_frame

con = db.connect()
clock = Clock()
cli.start(con, "draw for 30 minutes")
s = db.active_session(con)
first = camera.maybe_sample(con, s)
check(first and calls["frame"] == 1, "first sample has no history yet: single-frame judgement")
for _ in range(12):                                   # one minute of daemon ticks
    clock.advance(5)
    camera.maybe_sample(con, s)
check(len(calls["clip"]) == 1, f"one clip judgement per minute (got {len(calls['clip'])})")
mp4, prompt = calls["clip"][0]
n = int(mp4.split(b":")[1])
check(11 <= n <= 13, f"clip holds a frame per 5 s tick for the minute ({n} frames)")
check("timelapse of the last" in prompt and "drawing" in prompt.lower(), "prompt says it's a timelapse of the declared habit")
ev = db.session_events(con, s["id"], "camera")[-1]["payload"]
check(ev["backend"] == "nvidia-video" and ev["label"] == "on_task" and ev["clip_frames"] == n,
      "event records the video backend and clip size")
check(not camera._clip.get(s["id"]), "buffer cleared after judging")

calls["fail"] = True
clock.advance(90)                                      # into the phone scene so the motion gate doesn't reuse
camera.maybe_sample(con, s)                            # overdue: judged at once, then a fresh minute of frames
for _ in range(12):
    clock.advance(5)
    camera.maybe_sample(con, s)
ev = db.session_events(con, s["id"], "camera")[-1]["payload"]
check(ev["label"] == "phone" and ev.get("clip_error") == "TimeoutError", "clip failure falls back to the single frame")

config.VLM_VIDEO = False
before = (len(calls["clip"]), calls["frame"])
clock.advance(5)
camera.maybe_sample(con, s)
check(not camera._clip.get(s["id"]), "VLM_VIDEO off: no frames buffered between samples")
cli.end(con)
camera.release()
print("Video witness DoD passed.")
