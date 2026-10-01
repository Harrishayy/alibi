"""Seed one realistic day of phone/Mac/Health signals (docs/SIGNALS.md) into a scratch data dir, for the Signals page.

  ALIBI_DATA_DIR=/tmp/x/data ALIBI_HABITS=/tmp/x/habits.yaml python tests/seed_signals.py [--hours-back 10]

Sessions are placed relative to *now* (all finished, so no daemon is needed): C++ at the desk with an Instagram
stretch (score capped), a run outside (walking + left home + Strava), drawing with phone pickups, and internship
applications with a Zoom call and an idle Mac. 14 days of Health totals give the cards their trends.
Refuses to touch the real data dir or the real habits.yaml.
"""
import datetime as dt, os, pathlib, random, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if not os.environ.get("ALIBI_DATA_DIR") or pathlib.Path(os.environ["ALIBI_DATA_DIR"]).resolve() == (ROOT / "data").resolve():
    sys.exit("Set ALIBI_DATA_DIR to a scratch dir (never the real data/).")
if pathlib.Path(os.environ.get("ALIBI_HABITS", ROOT / "habits.yaml")).resolve() == (ROOT / "habits.yaml").resolve():
    sys.exit("Set ALIBI_HABITS to a scratch copy (never the real habits.yaml).")
from alibi import config, db, signals, verifier

R = random.Random(11)
NOW = time.time()
MIN = 60


def ev(con, source, kind, payload, ts, sid=None):
    db.add_event(con, source, kind, payload, session_id=sid, ts=ts)


PENDING, TO_CLOSE = [], []


def sig(con, source, kind, payload, ts):
    """Queued, then written in time order (like a real phone/Mac would), after every session row exists."""
    if ts <= NOW:
        PENDING.append((ts, len(PENDING), source, kind, payload))


def flush(con):
    for ts, _, source, kind, payload in sorted(PENDING, key=lambda x: x[:2]):
        signals.store(con, source, kind, payload, ts=ts)
    PENDING.clear()


def new_session(con, habit, start, minutes):
    h = config.habits()["habits"][habit]
    cur = con.execute("INSERT INTO sessions(habit, modality, declared_min, started_at, ends_at) VALUES (?,?,?,?,?)",
                      (habit, h["modality"], minutes, start, start + minutes * MIN))
    con.commit()
    return cur.lastrowid, h["modality"]


def close(con, sid):
    TO_CLOSE.append(sid)


def finalise(con, sid):
    s = con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    con.execute("UPDATE sessions SET ended_at=? WHERE id=?", (s["ends_at"], sid))
    con.commit()
    s = con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    print(" ", verifier.finalise(con, s, keep_end=True))


def windows(con, sid, start, minutes, on, off, off_spans=()):
    for i in range(minutes * 2):
        ts = start + i * 30
        bad = any(a <= i / 2 < b for a, b in off_spans) or R.random() < 0.06
        app, title = R.choice(off if bad else on)
        ev(con, "laptop", "window", {"app": app, "title": title, "url": ""}, ts, sid)


def camera(con, sid, habit, start, minutes, bad_at=()):
    from alibi import evidence  # noqa: F401  (imported so the contact sheet renderer is ready)
    import cv2, numpy as np
    tint = {"on_task": (95, 150, 90), "phone": (70, 80, 210), "idle": (60, 150, 215), "absent": (18, 18, 18)}
    for i in range(minutes):
        lab = next((l for a, b, l in bad_at if a <= i < b), "on_task")
        ts = start + i * MIN
        p = config.FRAMES_DIR / str(sid) / f"{int(ts)}.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        f = np.full((288, 512, 3), tint[lab], np.uint8)
        cv2.imwrite(str(p), cv2.add(f, np.random.default_rng(int(ts)).integers(0, 18, f.shape, dtype=np.uint8)))
        ev(con, "camera", "label", {"label": lab, "note": {"on_task": "pen on paper", "phone": "phone in hand",
                                                             "idle": "hands still", "absent": "nobody at the desk"}[lab],
                                    "frame": str(p), "reused": False, "backend": "apple"}, ts, sid)


def heart(con, t0, t1, base, every=5 * MIN, spread=6):
    t = t0
    while t < min(t1, NOW):
        n = R.randint(3, 6)
        samples = [[round(t - every + (k + 1) * every / n, 1), round(base + R.uniform(-spread, spread))] for k in range(n)]
        sig(con, "health", "heart", {"samples": samples}, t)
        t += every


def main():
    con = db.connect()
    if con.execute("SELECT COUNT(*) FROM events WHERE source IN ('phone','mac')").fetchone()[0]:
        print("Already seeded:", config.DATA_DIR); return
    hb = float(sys.argv[sys.argv.index("--hours-back") + 1]) if "--hours-back" in sys.argv else 10.0
    day0 = NOW - hb * 3600                              # the seeded "day" starts here
    mid = dt.datetime.combine(dt.date.fromtimestamp(NOW), dt.time()).timestamp()
    day0 = max(day0, mid + 60)                          # keep it inside today so ?day=today shows all of it
    span = NOW - day0
    at = lambda f: day0 + f * span                      # a point f (0..1) through the seeded stretch

    # --- background: phone at home, Mac presence, notifications, resting heart, Health totals ----------------------
    sig(con, "phone", "app", {"opened": True, "reason": "launch"}, day0 + 30)
    sig(con, "phone", "location", {"at_home": True}, day0 + 40)
    t = day0
    while t < NOW:
        sig(con, "mac", "presence", {"idle_s": R.choice([2, 4, 11, 35, 60]), "locked": False, "display_asleep": False,
                                     "displays": 1, "on_battery": False, "battery_pct": 88}, t)
        t += 5 * MIN
    t = day0 + 7 * MIN
    apps = [("Messages", True, "com.apple.MobileSMS"), ("WhatsApp", True, "net.whatsapp.WhatsApp"),
            ("Slack", False, "com.tinyspeck.slackmacgap"), ("Mail", False, "com.apple.mail"),
            ("Instagram", True, "com.burbn.instagram"), ("Calendar", False, "com.apple.iCal")]
    while t < NOW:
        a, ph, bid = R.choice(apps)
        sig(con, "mac", "notifications", {"app": a, "count": R.choice([1, 1, 1, 2, 3, 5]), "phone": ph,
                                          "window_s": 30, "id": bid}, t)
        t += R.uniform(6, 22) * MIN
    heart(con, day0, NOW, 66, every=25 * MIN, spread=5)
    pickups = sorted(at(R.random()) for _ in range(22))
    for p in pickups:
        sig(con, "phone", "pickup", {"ts": p}, p)
        sig(con, "phone", "motion", {"start": p - 40 * MIN, "end": p, "state": "stationary", "confidence": "high"},
            p - 40 * MIN)
    sig(con, "mac", "git", {"repo": "alibi", "path": "~/Documents/nvidia_habits", "commits": 1, "files": 2,
                            "insertions": 18, "deletions": 4, "uncommitted_files": 3}, at(0.03))

    # cumulative Screen Time per app (DeviceActivity thresholds every 5 min of picked apps)
    used = {"Instagram": 0, "YouTube": 0, "Messages": 0, "X": 0}

    def screentime(app, ts, minutes, cat):
        for _ in range(int(minutes // 5)):
            used[app] += 5
            sig(con, "phone", "screentime", {"app": app, "category": cat, "minutes": used[app], "threshold_min": 5}, ts)
            ts += 5 * MIN

    screentime("Instagram", at(0.02), 15, "Social")
    screentime("X", at(0.30), 10, "Social")
    screentime("YouTube", at(0.62), 20, "Entertainment")
    screentime("Messages", at(0.80), 10, "Social")

    # --- 1. C++ at the desk, Instagram creeps in ------------------------------------------------------------------
    s0 = at(0.08)
    sid, _ = new_session(con, "cpp", s0, 50)
    windows(con, sid, s0, 50, [("Visual Studio Code", "vector.cpp — learncpp"),
                               ("Google Chrome", "std::vector - cppreference.com"), ("Terminal", "g++ -std=c++20")],
            [("Google Chrome", "YouTube"), ("Messages", "Messages")])
    sig(con, "mac", "focus", {"on": True, "mode": "Alibi"}, s0 + 5)
    sig(con, "phone", "focus", {"on": True, "name": "Alibi"}, s0 + 20)
    sig(con, "phone", "shield", {"on": False, "apps": 0}, s0 + 30)
    sig(con, "mac", "media", {"app": "Spotify", "title": "Lo-fi beats", "playing": True}, s0 + 2 * MIN)
    for k in range(10):
        sig(con, "mac", "presence", {"idle_s": R.choice([1, 3, 8, 20]), "locked": False, "display_asleep": False}, s0 + k * 5 * MIN + 60)
    sig(con, "mac", "switches", {"per_min": 2.4, "apps": ["Visual Studio Code", "Google Chrome", "Terminal"],
                                 "window_s": 600, "switches": 24}, s0 + 12 * MIN)
    sig(con, "mac", "switches", {"per_min": 6.1, "apps": ["Google Chrome", "Messages", "Visual Studio Code"],
                                 "window_s": 600, "switches": 61}, s0 + 32 * MIN)
    sig(con, "phone", "pickup", {"ts": s0 + 21 * MIN}, s0 + 21 * MIN)
    screentime("Instagram", s0 + 26 * MIN, 15, "Social")
    sig(con, "mac", "notifications", {"app": "Instagram", "count": 4, "phone": True, "window_s": 30}, s0 + 24 * MIN)
    sig(con, "mac", "git", {"repo": "learncpp", "path": "~/code/learncpp", "commits": 2, "files": 3, "insertions": 84,
                            "deletions": 12, "uncommitted_files": 0}, s0 + 47 * MIN)
    heart(con, s0, s0 + 50 * MIN, 71)
    sig(con, "mac", "focus", {"on": False}, s0 + 50 * MIN + 5)
    sig(con, "phone", "focus", {"on": False, "name": "Alibi"}, s0 + 50 * MIN + 20)
    close(con, sid)

    # --- 2. a run outside: walking, left home --------------------------------------------------------------------
    r0 = at(0.24)
    sig(con, "phone", "location", {"at_home": False}, r0)
    sig(con, "phone", "motion", {"start": r0, "end": r0 + 6 * MIN, "state": "walking", "confidence": "high"}, r0)
    sig(con, "phone", "motion", {"start": r0 + 6 * MIN, "end": r0 + 34 * MIN, "state": "running", "confidence": "high"}, r0 + 6 * MIN)
    sig(con, "phone", "motion", {"start": r0 + 34 * MIN, "end": r0 + 42 * MIN, "state": "walking", "confidence": "high"}, r0 + 34 * MIN)
    heart(con, r0, r0 + 42 * MIN, 152, every=3 * MIN, spread=10)
    sig(con, "phone", "location", {"at_home": True}, r0 + 44 * MIN)
    sig(con, "mac", "presence", {"idle_s": 2400, "locked": True, "display_asleep": True}, r0 + 40 * MIN)
    ev(con, "strava", "activity", {"id": 4242, "name": "Afternoon Run", "distance_km": 5.3, "moving_min": 28,
                                   "start_date": r0 + 6 * MIN}, r0 + 6 * MIN)

    # --- 3. drawing at the desk: phone pickups -------------------------------------------------------------------
    d0 = at(0.42)
    sid, _ = new_session(con, "drawing", d0, 45)
    camera(con, sid, "drawing", d0, 45, bad_at=[(17, 21, "phone"), (33, 35, "absent")])
    sig(con, "phone", "shield", {"on": True, "apps": 6}, d0 + 15)
    sig(con, "phone", "focus", {"on": True, "name": "Alibi"}, d0 + 20)
    sig(con, "mac", "presence", {"idle_s": 900, "locked": False, "display_asleep": False}, d0 + 20 * MIN)
    for m in (17, 33):
        sig(con, "phone", "pickup", {"ts": d0 + m * MIN}, d0 + m * MIN)
    sig(con, "phone", "motion", {"start": d0 + 33 * MIN, "end": d0 + 35 * MIN, "state": "walking", "confidence": "medium"}, d0 + 33 * MIN)
    heart(con, d0, d0 + 45 * MIN, 64)
    sig(con, "phone", "shield", {"on": False, "apps": 0}, d0 + 45 * MIN + 5)
    sig(con, "phone", "focus", {"on": False, "name": "Alibi"}, d0 + 45 * MIN + 20)
    close(con, sid)
    sig(con, "mac", "media", {"app": "Google Chrome", "title": "YouTube — Proko figure drawing", "playing": True,
                              "via": "window"}, d0 + 50 * MIN)
    sig(con, "mac", "media", {"app": "Google Chrome", "playing": False}, d0 + 70 * MIN)

    # --- 4. internship applications: a Zoom call, then the Mac sits idle ------------------------------------------
    i0 = at(0.70)
    sid, _ = new_session(con, "internships", i0, 40)
    windows(con, sid, i0, 40, [("Google Chrome", "Software Engineer Intern - Greenhouse"),
                               ("Pages", "Cover letter — NVIDIA"), ("Google Chrome", "LinkedIn Jobs")],
            [("Google Chrome", "YouTube")], off_spans=[(30, 33)])
    sig(con, "mac", "focus", {"on": True, "mode": "Alibi"}, i0 + 5)
    # change-based, exactly like alibi/mac_signals.py: one row when the call starts, one "off" row when it ends
    sig(con, "mac", "meeting", {"camera": True, "mic": True, "app": "Zoom"}, i0 + 3 * MIN)
    sig(con, "mac", "meeting", {"camera": False, "mic": False}, i0 + 14 * MIN)
    for k, idle in enumerate((420, 600, 780)):
        sig(con, "mac", "presence", {"idle_s": idle, "locked": False, "display_asleep": False}, i0 + (20 + 3 * k) * MIN)
    sig(con, "mac", "switches", {"per_min": 1.2, "apps": ["Google Chrome", "Pages"], "window_s": 600, "switches": 12}, i0 + 35 * MIN)
    sig(con, "phone", "pickup", {"ts": i0 + 27 * MIN}, i0 + 27 * MIN)
    heart(con, i0, i0 + 40 * MIN, 69)
    sig(con, "mac", "git", {"repo": "alibi", "path": "~/Documents/nvidia_habits", "commits": 0, "files": 0,
                            "insertions": 0, "deletions": 0, "uncommitted_files": 5}, i0 + 39 * MIN)
    sig(con, "mac", "focus", {"on": False}, i0 + 40 * MIN + 5)
    close(con, sid)

    flush(con)
    for sid in TO_CLOSE:
        finalise(con, sid)

    # --- live right now: the Mac and phone are talking ----------------------------------------------------------
    sig(con, "mac", "presence", {"idle_s": 3, "locked": False, "display_asleep": False, "displays": 1,
                                 "on_battery": True, "battery_pct": 72}, NOW - 20)
    sig(con, "phone", "app", {"opened": False, "reason": "background sync"}, NOW - 90)
    ev(con, "laptop", "window", {"app": "Visual Studio Code", "title": "signals.html — nvidia_habits", "url": ""}, NOW - 15)
    flush(con)

    # --- Health: 14 days of totals, today's with full sleep stages ----------------------------------------------
    today = dt.date.fromtimestamp(NOW)
    for i in range(13, -1, -1):
        d = today - dt.timedelta(days=i)
        deep, rem, awake = R.uniform(0.8, 1.6), R.uniform(1.2, 2.0), R.uniform(0.2, 0.7)
        core = R.uniform(3.2, 4.4)
        p = {"date": d.isoformat(), "steps": R.randint(4200, 12500), "distance_km": round(R.uniform(3, 9), 1),
             "flights": R.randint(2, 14), "active_kcal": R.randint(280, 720), "exercise_min": R.randint(8, 55),
             "stand_h": R.randint(7, 13), "sleep": {"core_h": round(core, 2), "deep_h": round(deep, 2),
                                                    "rem_h": round(rem, 2), "awake_h": round(awake, 2),
                                                    "bed": R.choice(["23:12", "23:48", "00:20", "00:41"]),
                                                    "wake": R.choice(["06:55", "07:20", "07:42", "08:05"])},
             "sleep_h": round(core + deep + rem, 2), "resting_hr": R.randint(54, 63), "hrv_ms": R.randint(38, 66),
             "resp_rate": round(R.uniform(13.2, 15.4), 1), "mindful_min": R.choice([0, 0, 5, 10, 12]),
             "daylight_min": R.randint(12, 95), "headphone_db": R.randint(62, 78),
             "workout_min": R.choice([0, 0, 28, 45]), "workouts": [], "moods": []}
        if i == 0:
            p.update(steps=8423, distance_km=6.4, active_kcal=544, exercise_min=34, resting_hr=56, hrv_ms=61,
                     daylight_min=48, mindful_min=10, workout_min=28,
                     sleep={"core_h": 3.9, "deep_h": 1.4, "rem_h": 1.7, "awake_h": 0.5, "bed": "23:48", "wake": "07:20"},
                     sleep_h=7.0, workouts=[{"type": "run", "start": dt.datetime.fromtimestamp(r0).strftime("%H:%M"),
                                             "min": 28, "km": 5.3, "avg_hr": 152, "kcal": 341}],
                     moods=[{"ts": at(0.35), "valence": 0.45, "labels": ["Calm", "Focused"]},
                            {"ts": at(0.9), "valence": -0.15, "labels": ["Tired"]}])
        ts = NOW - 60 if i == 0 else dt.datetime.combine(d, dt.time(23, 30)).timestamp()
        ev(con, "health", "samples", p, ts)
    try:
        from alibi import integrations
        integrations.set_state(health_last_received=NOW - 60)
    except Exception:
        pass
    print("Seeded signals into", config.DATA_DIR)


if __name__ == "__main__":
    main()
