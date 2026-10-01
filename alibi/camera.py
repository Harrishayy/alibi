"""P1 — sample the desk cam once a minute during physical/hybrid sessions.

Contract: writes events(source='camera', kind='label', payload={label, note, frame, reused}).
"""
# TODO (P1):
#   - keep one cv2.VideoCapture open (module-level), read a frame every tick so the buffer stays fresh
#   - maybe_sample(con, session): if SAMPLE_EVERY_S elapsed since last sample:
#       * downscale to 512 px, JPEG q70, save to FRAMES_DIR/<session_id>/<ts>.jpg
#       * motion gate: 64x64 gray mean-abs-diff vs previous sample < MOTION_THRESHOLD -> reuse last label
#       * else llm.vision_json(SYSTEM, prompt_for(habit), jpeg) -> {label, note}; coerce unknown labels to off_task
#       * db.add_event(con, "camera", "label", {...}, session_id=session["id"])
#   - support CAMERA_SOURCE=path/to/video.mp4 for testing without the live cam

SYSTEM = ("You verify whether a person at a desk is doing what they said. "
          "Reply with JSON only: {\"label\": \"on_task|phone|idle|absent|off_task\", \"note\": \"<12 words\"}.")


def prompt_for(habit_key: str, habit_cfg: dict) -> str:
    return (f"The person declared they are doing: {habit_key}. "
            f"On task looks like: {habit_cfg.get('on_task_looks_like', habit_key)}. "
            "phone = holding or looking at a phone. idle = present but not working. absent = nobody there.")
