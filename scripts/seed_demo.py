"""Seed a realistic week into a data dir (default data/demo) so the UI has something to show.

  ALIBI_DATA_DIR=data/demo python scripts/seed_demo.py
"""
import os, pathlib, random, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ALIBI_DATA_DIR", str(ROOT / "data" / "demo"))
import cv2, numpy as np
from alibi import config, db, evidence, report, verifier

random.seed(7)
TINT = {"on_task": (95, 150, 90), "phone": (70, 80, 210), "idle": (60, 150, 215), "absent": (18, 18, 18),
        "off_task": (60, 60, 170)}
NOTES = {"on_task": "hands on the work", "phone": "phone in hand", "idle": "at the desk, hands still",
         "absent": "nobody at the desk", "off_task": "something else on the desk"}
HABIT_LOOK = {"drawing": "pen on paper", "piano": "hands on the keys", "cooking": "knife and board",
              "math": "notebook + equations"}


def frame(path, label, habit, t):
    f = np.full((288, 512, 3), TINT[label], np.uint8)
    noise = np.random.default_rng(int(t)).integers(0, 18, f.shape, dtype=np.uint8)
    f = cv2.add(f, noise)
    txt = HABIT_LOOK.get(habit, habit) if label == "on_task" else label.replace("_", " ")
    cv2.putText(f, txt, (18, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), f)


def session(con, habit, minutes, start, mix):
    h = config.habits()["habits"][habit]
    cur = con.execute("INSERT INTO sessions(habit, modality, declared_min, started_at, ends_at) VALUES (?,?,?,?,?)",
                      (habit, h["modality"], minutes, start, start + minutes * 60))
    sid = cur.lastrowid
    con.commit()
    if h["modality"] in ("physical", "hybrid"):
        labels = random.choices(list(mix), weights=list(mix.values()), k=minutes)
        labels.sort(key=lambda l: (l != "on_task") * random.random())     # mostly work first, drift later
        for i, l in enumerate(labels):
            ts = start + i * 60
            p = config.FRAMES_DIR / str(sid) / f"{int(ts)}.jpg"
            frame(p, l, habit, ts)
            db.add_event(con, "camera", "label", {"label": l, "note": NOTES[l], "frame": str(p),
                                                  "reused": False, "backend": "apple"}, session_id=sid, ts=ts)
    if h["modality"] in ("digital", "hybrid"):
        on = {"cpp": [("Visual Studio Code", "main.cpp — learncpp"), ("Google Chrome", "std::vector - cppreference.com")],
              "math": [("Preview", "Linear Algebra Done Right.pdf")]}.get(habit, [("Code", habit)])
        off = [("Google Chrome", "YouTube"), ("Messages", "Messages")]
        for i in range(minutes * 2):
            app, title = random.choice(on if random.random() < mix.get("on_task", .7) else off)
            db.add_event(con, "laptop", "window", {"app": app, "title": title, "url": ""}, session_id=sid,
                         ts=start + i * 30)
    s = con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    print(verifier.finalise(con, s))
    con.execute("UPDATE sessions SET ended_at=? WHERE id=?", (start + minutes * 60, sid))
    con.commit()


def main():
    if db.DB_PATH.exists():
        print("Data dir already seeded:", config.DATA_DIR); return
    con = db.connect()
    t0 = report.week_start()
    day = 86400
    plan = [  # (day offset, hour, habit, minutes, mix)
        (0, 10, "piano", 45, {"on_task": .85, "phone": .1, "absent": .05}),
        (0, 20, "drawing", 45, {"on_task": .5, "phone": .35, "idle": .15}),
        (1, 9, "cpp", 40, {"on_task": .8}),
        (1, 18, "cooking", 50, {"on_task": .9, "absent": .1}),
        (2, 14, "cpp", 30, {"on_task": .55}),
        (2, 21, "drawing", 30, {"on_task": .3, "phone": .5, "absent": .2}),
        (3, 10, "math", 50, {"on_task": .75, "idle": .25}),
    ]
    now = time.time()
    for d, hr, habit, mins, mix in plan:
        start = t0 + d * day + hr * 3600
        if start + mins * 60 < now and habit in config.habits()["habits"]:
            session(con, habit, mins, start, mix)
    for d, km, mins in [(0, 5.4, 29), (2, 3.1, 19)]:
        ts = t0 + d * day + 7 * 3600
        if ts < now:
            db.add_event(con, "strava", "activity", {"id": 1000 + d, "name": "Morning Run", "distance_km": km,
                                                     "moving_min": mins, "start_date": ts}, ts=ts)
    seed_plan_and_health(con, t0, now)
    from alibi import onboarding
    onboarding.mark_done("seed")              # a seeded demo is past the first-run wizard
    print(report.build())


def seed_plan_and_health(con, t0, now):
    """Planned blocks (schedule + calendar) and Apple Health habits/samples — only into a scratch
    habits.yaml (ALIBI_HABITS), never the real one."""
    import datetime as dt
    from alibi import health
    if config.HABITS_PATH.resolve() == (ROOT / "habits.yaml").resolve():
        print("habits.yaml is the real one — not adding schedules/Health habits (set ALIBI_HABITS to a copy).")
    else:
        hs = config.habits()["habits"]
        plan = {"drawing": [{"days": ["mon", "wed", "fri"], "at": "19:00", "min": 25}],
                "cpp": [{"days": ["mon", "tue", "wed", "thu", "fri"], "at": "09:00", "min": 40}],
                "piano": [{"days": ["mon", "tue", "thu", "sat"], "at": "18:00", "min": 30}],
                "running": [{"days": ["tue", "thu", "sat"], "at": "07:30", "min": 30}]}
        for k, sched in plan.items():
            if k in hs:
                hs[k]["schedule"], hs[k]["calendar"] = sched, True
        hs.setdefault("steps", {"source": "health", "metric": "steps", "daily_target": 8000, "display": "Steps"})
        hs.setdefault("sleep", {"source": "health", "metric": "sleep_h", "daily_target": 7, "display": "Sleep"})
        health.save_habits(hs)
    monday = dt.date.fromtimestamp(t0)
    for i in range(7):
        d = monday + dt.timedelta(days=i)
        ts = dt.datetime.combine(d, dt.time(23, 30)).timestamp()
        if ts > now:
            ts = now - 60                        # today's numbers so far
            if d != dt.date.today():
                break
        db.add_event(con, "health", "samples", {
            "date": d.isoformat(), "steps": random.choice([4210, 6890, 8412, 9120, 11873, 7650]),
            "sleep_h": random.choice([5.8, 6.4, 7.2, 7.6, 6.9]), "mindful_min": random.choice([0, 5, 10, 12]),
            "workout_min": random.choice([0, 0, 29, 45]), "workouts": []}, ts=ts)


if __name__ == "__main__":
    main()
