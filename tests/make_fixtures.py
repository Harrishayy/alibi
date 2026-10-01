"""Synthetic desk videos for DoD tests (1 fps). Colour encodes ground truth for the mock witness."""
import pathlib, cv2, numpy as np

OUT = pathlib.Path(__file__).parent / "fixtures"
SCENES = {"on_task": ((95, 150, 90), "drawing"), "phone": ((70, 80, 210), "on phone"),
          "idle": ((200, 120, 60), "idle"), "absent": ((15, 15, 15), "away")}   # BGR


def video(name: str, plan: list[tuple[str, int]]):
    OUT.mkdir(exist_ok=True)
    w = cv2.VideoWriter(str(OUT / name), cv2.VideoWriter_fourcc(*"mp4v"), 1, (640, 480))
    t = 0
    for label, secs in plan:
        colour, text = SCENES[label]
        for _ in range(secs):
            f = np.full((480, 640, 3), colour, np.uint8)
            cv2.putText(f, f"{text}  t={t}s", (24, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            w.write(f); t += 1
    w.release()
    return OUT / name


if __name__ == "__main__":
    print(video("desk_4min.mp4", [("on_task", 120), ("phone", 60), ("absent", 60)]))
