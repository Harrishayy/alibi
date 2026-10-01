"""Pre-flight: both model calls must return JSON before you start P0."""
import io, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from alibi import config, llm

print("Text model:", config.LLM_MODEL)
print(llm.chat_json("Reply with JSON only.", 'Return {"ok": true, "habit": "drawing"}'))

jpeg = None
try:
    import cv2
    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    for _ in range(5):          # let auto-exposure settle
        ok, frame = cap.read()
    cap.release()
    if ok:
        frame = cv2.resize(frame, (512, int(512 * frame.shape[0] / frame.shape[1])))
        jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()
        print("Webcam frame captured.")
except Exception as e:
    print("Webcam failed:", e)

if jpeg is None:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (512, 384), "white")
    ImageDraw.Draw(img).rectangle([150, 120, 360, 260], outline="black", width=6)
    buf = io.BytesIO(); img.save(buf, "JPEG"); jpeg = buf.getvalue()
    print("Using synthetic image instead.")

print("Vision model:", config.VLM_MODEL)
print(llm.vision_json("Reply with JSON only.",
                      'Describe the scene. Return {"label": "on_task|phone|idle|absent", "note": "<12 words>"}',
                      jpeg))
print("If both lines above are non-empty JSON, you're clear for P0.")
