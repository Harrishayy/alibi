"""P1 — sample the desk cam once a minute during physical/hybrid sessions.

Contract: writes events(source='camera', kind='label', payload={label, note, frame, reused, backend, motion}).
CAMERA_SOURCE=path/to/video.mp4 plays the video in session time (second N of the session = second N of the video).
"""
import time
import cv2
import numpy as np
from . import config, db, witness

_cap = None
_last = {}          # session_id -> {"ts", "small", "label", "note"}


def _open():
    global _cap
    if _cap is None or not _cap.isOpened():
        _cap = cv2.VideoCapture(config.CAMERA_SOURCE or config.CAMERA_INDEX)
    return _cap


def release() -> None:
    """Let go of the webcam (light off) whenever no physical/hybrid session needs it."""
    global _cap
    if _cap is not None:
        _cap.release()
        _cap = None


def grab(session) -> np.ndarray | None:
    cap = _open()
    if config.CAMERA_SOURCE:
        fps = cap.get(cv2.CAP_PROP_FPS) or 1
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(int((time.time() - session["started_at"]) * fps), n - 1))
        ok, frame = cap.read()
        return frame if ok else None
    frame = None
    for _ in range(4):                       # flush the driver's buffer so we judge *now*, not 20 s ago
        ok, f = cap.read()
        frame = f if ok else frame
    return frame


def maybe_sample(con, session, force: bool = False) -> dict | None:
    now = time.time()
    last = _last.get(session["id"])
    if not force and last and now - last["ts"] < config.SAMPLE_EVERY_S:
        return None
    frame = grab(session)
    if frame is None:
        return None
    h, w = frame.shape[:2]
    frame = cv2.resize(frame, (512, int(512 * h / w)))
    jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()
    d = config.FRAMES_DIR / str(session["id"])
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{int(now)}.jpg"
    path.write_bytes(jpeg)

    small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (64, 64)).astype(np.float32)
    motion = float(np.abs(small - last["small"]).mean()) if last else 999.0
    habits = config.habits()["habits"]
    if last and motion < config.MOTION_THRESHOLD:
        out = {"label": last["label"], "note": last["note"], "reused": True, "backend": "motion-gate"}
    else:
        out = witness.judge(jpeg, str(path), session["habit"], habits.get(session["habit"], {}))
        out["reused"] = False
    payload = {**out, "frame": str(path), "motion": round(min(motion, 999.0), 2)}
    db.add_event(con, "camera", "label", payload, session_id=session["id"], ts=now)
    _last[session["id"]] = {"ts": now, "small": small, "label": out["label"], "note": out["note"]}
    return payload
