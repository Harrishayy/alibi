"""Synthetic desk videos for DoD tests (1 fps). Colour encodes ground truth for the mock witness."""
import os, pathlib, cv2, numpy as np

OUT = pathlib.Path(__file__).parent / "fixtures"
SCENES = {"on_task": ((95, 150, 90), "drawing"), "phone": ((70, 80, 210), "on phone"),
          "idle": ((200, 120, 60), "idle"), "absent": ((15, 15, 15), "away")}   # BGR


def video(name: str, plan: list[tuple[str, int]]):
    OUT.mkdir(exist_ok=True)
    final = OUT / name
    tmp = OUT / f".{name}.{os.getpid()}.mp4"          # write aside, then rename: readers never see a half-written video
    w = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), 1, (640, 480))
    t = 0
    for label, secs in plan:
        colour, text = SCENES[label]
        for _ in range(secs):
            f = np.full((480, 640, 3), colour, np.uint8)
            cv2.putText(f, f"{text}  t={t}s", (24, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            w.write(f); t += 1
    w.release()
    os.replace(tmp, final)
    return final


if __name__ == "__main__":
    print(video("desk_4min.mp4", [("on_task", 120), ("phone", 60), ("absent", 60)]))


def strava(name: str = "strava.json"):
    """This week's runs, Strava API shape: one long, one too short to count, plus a ride (ignored)."""
    import datetime as dt, json, sys
    sys.path.insert(0, str(OUT.parents[1]))
    from alibi import report
    t0 = dt.datetime.fromtimestamp(report.week_start(), dt.timezone.utc)
    iso = lambda h: (t0 + dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")
    acts = [{"id": 901, "name": "Morning Run", "sport_type": "Run", "distance": 5400.0, "moving_time": 1740, "start_date": iso(7)},
            {"id": 902, "name": "Shakeout", "sport_type": "Run", "distance": 3100.0, "moving_time": 1140, "start_date": iso(55)},
            {"id": 903, "name": "Commute", "sport_type": "Ride", "distance": 9000.0, "moving_time": 1800, "start_date": iso(30)}]
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(acts, indent=1))
    return OUT / name
