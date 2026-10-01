"""Starter /api/state fixtures for the dashboard's ?stage=NAME mode and the island's --snapshot --state.

    python3 docs/design/demo/make_fixtures.py [--api http://127.0.0.1:8775] [--copy-web]

Each fixture is a complete /api/state payload (same keys the real endpoint returns) for one moment of the demo
persona's evening: "Drawing", 25 min, started 17:58, a phone drift and a nudge at 18:07, a break, then three
alternative verdicts at 18:23 (done / partly / slacked), a C++ window nudge, the Health check-in and the nightly
report. `pinch` is never hand-written: it is alibi.pinch.pinch_state(payload), exactly as /api/state computes it.

Real data: habits come from the lab server's /api/state; camera frames come from the newest finished drawing
session in /api/sessions that has framed camera labels (data/demo session 6). With no lab server running, it falls
back to that session's known frame paths so the output stays the same.

Only writes docs/design/fixtures/state/ (and alibi/web/fixtures/ with --copy-web). Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import shutil
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from alibi.pinch import pinch_state  # noqa: E402

OUT = ROOT / "docs/design/fixtures/state"
WEB = ROOT / "alibi/web/fixtures"

DAY = dt.date(2026, 10, 1)
EVERY = 30                                   # camera cadence for the persona session (s)
LABEL_TEXT = {"on_task": "On task", "phone": "On your phone", "absent": "Away from desk", "idle": "Idle",
              "off_task": "Off task"}
NOTES = {"on_task": "pencil on paper, sketchbook open", "phone": "phone in hand, sketchbook untouched",
         "absent": "empty chair", "idle": "hands still"}
HABITS_FALLBACK = [
    {"key": "drawing", "label": "Drawing", "modality": "physical", "default_min": 25},
    {"key": "building", "label": "Building", "modality": "physical", "default_min": 45},
    {"key": "math", "label": "Math", "modality": "hybrid", "default_min": 30},
    {"key": "cpp", "label": "C++", "modality": "digital", "default_min": 30},
    {"key": "internships", "label": "Internships", "modality": "digital", "default_min": 30},
    {"key": "running", "label": "Running", "modality": "strava", "default_min": 25},
]


def at(h: int, m: int, s: int = 0) -> float:
    """Local wall clock on the demo day -> epoch seconds."""
    return dt.datetime.combine(DAY, dt.time(h, m, s)).timestamp()


def get(api: str, path: str):
    try:
        with urllib.request.urlopen(api + path, timeout=3) as r:
            return json.load(r)
    except Exception:
        return None


def frame_pool(sessions: list | None) -> tuple[dict, int | None]:
    """{label: [frame_url, ...]} from the newest finished drawing session with framed camera labels."""
    for s in sessions or []:
        if s.get("habit") == "drawing" and sum(1 for l in s.get("labels", []) if l.get("frame_url")) >= 20:
            pool: dict = {}
            for l in s["labels"]:
                if l.get("frame_url"):
                    pool.setdefault(l["label"], []).append(l["frame_url"])
            return pool, s["id"]
    # data/demo session 6, as the lab server serves it (one frame a minute from 1790798400)
    seq = ["on_task"] * 11 + ["phone"] * 3 + ["absent", "phone", "absent"] + ["phone"] * 10 + ["absent", "phone",
                                                                                                   "absent"]
    pool = {}
    for i, lab in enumerate(seq):
        pool.setdefault(lab, []).append(f"/files/frames/6/{1790798400 + 60 * i}.jpg")
    return pool, 6


class Persona:
    """One drawing session; labels are a script of (label) per 30 s sample, frames from the real pool."""

    def __init__(self, pool: dict):
        self.pool = pool
        self.used: dict = {}

    def frame(self, label: str) -> str | None:
        frames = self.pool.get(label) or self.pool.get("phone" if label != "on_task" else "on_task") or []
        if not frames:
            return None
        i = self.used.get(label, 0)
        self.used[label] = i + 1
        return frames[i % len(frames)]

    def labels(self, start: float, script: list[str]) -> list[dict]:
        self.used = {}
        out = []
        for i, lab in enumerate(script):
            out.append({"ts": start + 10 + EVERY * i, "label": lab, "note": NOTES.get(lab, lab),
                        "label_text": LABEL_TEXT.get(lab, lab), "frame_url": self.frame(lab), "reused": False,
                        "corrected_from": None, "learned_from": None})
        return out


def status_text(sj: dict | None) -> str:
    """Same wording as alibi/api.py _status_text (kept in step by hand; it is four lines)."""
    if not sj:
        return "Idle — nothing declared"
    left = int(sj["left_s"])
    if sj.get("on_break"):
        return f"On a break · {sj['label']} resumes in {sj['on_break']['left_s'] // 60 + 1} min"
    if sj.get("drifting"):
        return f"Drifting · {sj['drifting']['label_text']} · {sj['label']} {left // 60:02d}:{left % 60:02d}"
    return f"Watching · {sj['label']} {left // 60:02d}:{left % 60:02d}"


def live_session(now: float, *, sid: int, habit: str, label: str, modality: str, declared: int, start: float,
                 ends: float, labels: list[dict], recent_src: list[dict] | None = None, on_break: dict | None = None,
                 breaks: int = 0, nudges: int = 0, strikes: int = 0, windows: list | None = None,
                 so_far: float | None = None, last_seen_src: str = "camera") -> dict:
    smp = recent_src if recent_src is not None else labels
    smp = [x for x in smp if x["ts"] <= now]
    labels = [x for x in labels if x["ts"] <= now]
    tail = []
    for x in reversed(smp):
        if x["label"] == "on_task":
            break
        tail.append(x)
    last = smp[-1] if smp else None
    if so_far is None and labels:
        so_far = sum(l["label"] == "on_task" for l in labels) / len(labels)
    last_seen = None
    if last:
        who = "Witness" if last_seen_src == "camera" else "Screen"
        ago = round(now - last["ts"])
        last_seen = {"label": last["label"], "label_text": last["label_text"], "note": last["note"],
                     "source": last_seen_src, "ago_s": ago, "text": f"{who} · {ago} s ago · {last['note']}"}
    out = {
        "id": sid, "habit": habit, "modality": modality, "declared_min": declared, "started_at": start,
        "ends_at": ends, "ended_at": None, "status": "active", "on_task_ratio": None, "verdict": None,
        "evidence_path": None, "artefact": None,
        "label": label, "evidence_url": None, "labels": labels, "reel_url": None, "on_task_so_far": so_far,
        "day": DAY.isoformat(),
    }
    if windows is not None:
        out["windows"] = windows
    out.update(
        left_s=max(0.0, ends - now), progress=min(1.0, (now - start) / max(1.0, ends - start)),
        last_frame_url=labels[-1]["frame_url"] if labels else None,
        samples=len(smp), warming_up=len(smp) < 6, recent=[x["label"] for x in smp[-3:]],
        recent_on_task=(sum(x["label"] == "on_task" for x in smp[-3:]) / len(smp[-3:])) if smp else None,
        last_seen=last_seen,
        drifting=({"label": tail[0]["label"], "label_text": tail[0]["label_text"],
                   "since_s": round(now - tail[-1]["ts"]), "samples": len(tail)} if len(tail) >= 2 else None),
        on_break=on_break, breaks_taken=breaks, nudges=nudges, strikes=strikes,
    )
    return out


def finished_session(now: float, *, sid: int, start: float, declared: int, labels: list[dict], verdict: str,
                     summary: str, evidence_url: str | None) -> dict:
    r = sum(l["label"] == "on_task" for l in labels) / len(labels)
    ends = start + declared * 60
    if r >= 0.7:
        score = f"You were on task {r:.0%} — a full tick."
    elif r >= 0.4:
        score = f"You were on task {r:.0%} — {round((0.7 - r) * 100)}% short of a full tick."
    else:
        score = f"You were on task {r:.0%} — {round((0.4 - r) * 100)}% short of a partial."
    return {
        "id": sid, "habit": "drawing", "modality": "physical", "declared_min": declared, "started_at": start,
        "ends_at": ends, "ended_at": ends, "status": "done", "on_task_ratio": r, "verdict": verdict,
        "evidence_path": None, "artefact": None, "label": "Drawing", "evidence_url": evidence_url,
        "labels": labels, "reel_url": None, "on_task_so_far": r, "day": DAY.isoformat(),
        "done_at": 0.7, "partial_at": 0.4, "score_line": score, "coverage": 1.0, "time_coverage": 1.0,
        "elapsed_min": declared, "seen_ratio": r, "camera_ratio": r, "screen_ratio": None,
        "verified_min": round(r * declared), "signals_reason": None,
        "why": f"Score = how many camera checks showed you working (camera {r:.0%}).",
        "summary": summary, "ended_ago_s": round(now - ends),
    }


def today(sessions: list[tuple[str, int, float, str]]) -> dict:
    """[(habit, declared_min, ratio, verdict)] finished today -> the `today` block."""
    tracked = {"drawing", "building", "math", "cpp", "internships"}
    good = {h for h, _, _, v in sessions if v in ("done", "partial")}
    return {"sessions": len(sessions), "verified_min": round(sum(r * m for _, m, r, _ in sessions)),
            "declared_min": sum(m for _, m, _, _ in sessions), "habits_done": len(good & tracked),
            "habits_total": len(tracked), "tally": f"{len(good & tracked)}/{len(tracked)}",
            "verdicts": {v: sum(x[3] == v for x in sessions) for v in ("done", "partial", "slacked")}}


def alert(ts: float, kind: str, text: str, **extra) -> dict:
    a = {"id": int(round(ts * 1e6)) * 1000, "ts": ts, "kind": kind, "text": text, "image": None}
    a.update(extra)
    a.setdefault("image_url", None)
    return a


def payload(base: dict, now: float, *, session=None, alert_=None, recent_verdict=None, today_=None) -> dict:
    p = {
        "now": now, "session": session, "alert": alert_, "habits": base["habits"],
        "witness": base["witness"], "witness_label": base["witness_label"], "text_model": base["text_model"],
        "daemon": {"up_since": at(17, 30)}, "today": today_, "recent_verdict": recent_verdict,
        "status_text": status_text(session),
    }
    p["pinch"] = pinch_state({k: p[k] for k in ("now", "session", "alert", "recent_verdict")})
    return p


def build(api: str) -> dict[str, dict]:
    state = get(api, "/api/state") or {}
    sessions = get(api, "/api/sessions?limit=50")
    pool, src = frame_pool(sessions)
    base = {"habits": state.get("habits") or HABITS_FALLBACK, "witness": "apple", "witness_label": "Apple Vision",
            "text_model": "rules"}
    p = Persona(pool)
    ev = f"/files/evidence/{src}.jpg" if src else None

    math_today = ("math", 50, 1.0, "done")            # the morning's session, already in the day
    t0 = today([math_today])

    # The persona session: drawing, 25 min, 17:58 -> 18:23. 30 s samples from 17:58:10.
    sid, start = 11, at(17, 58)
    ends = start + 25 * 60
    script = (["on_task"] * 4 + ["phone"] + ["on_task"] * 8      # 13 samples to 18:04:10: 12/13 = 92%
              + ["phone"] * 7                                    # 18:04:40 .. 18:07:40: the drift
              + ["on_task"] * 14)                                # 18:08:10 .. 18:14:40, then a break at 18:15
    labels = p.labels(start, script)
    common = dict(sid=sid, habit="drawing", label="Drawing", modality="physical", declared=25, start=start)
    nudge_text = "You said drawing. I've seen your phone for 3 minutes."
    nudge_ts = at(18, 7, 50)
    nudge = alert(nudge_ts, "nudge", nudge_text, session_id=sid, habit="drawing", habit_label="Drawing",
                  label="phone", strike=False,
                  actions=[{"label": "Back to it", "say": "back"}, {"label": "This counts", "say": "it's on task"},
                           {"label": "Quiet 5 min", "say": "snooze 5"}])

    out: dict[str, dict] = {}
    now = at(17, 55)
    out["idle"] = payload(base, now, today_=t0)

    now = start + 5
    out["live_listening"] = payload(base, now, today_=t0,
                                    session=live_session(now, **common, ends=ends, labels=labels))

    now = start + 6 * 60 + 18                                   # 18:04:18 -> 18:42 left of 25:00
    out["live_focused"] = payload(base, now, today_=t0,
                                  session=live_session(now, **common, ends=ends, labels=labels))

    now = at(18, 7, 50)                                         # 7 phone samples, 190 s
    out["live_drifting"] = payload(base, now, today_=t0,
                                   session=live_session(now, **common, ends=ends, labels=labels))

    now = nudge_ts + 3
    out["nudge_phone"] = payload(base, now, today_=t0, alert_=nudge,
                                 session=live_session(now, **common, ends=ends, labels=labels, nudges=1))

    # Break at 18:15 for 5 min: the clock pauses, so ends_at moves out to 18:28; the witness stops.
    now = at(18, 16)
    brk_until = at(18, 20)
    out["break"] = payload(base, now, today_=t0, alert_=nudge,
                           session=live_session(now, **common, ends=ends + 300, labels=labels, nudges=1, breaks=1,
                                                on_break={"until": brk_until, "left_s": round(brk_until - now)}))

    # Window nudge: a C++ session (digital: screen samples, no camera frames), 19:30 -> 20:00.
    cs, cstart = 12, at(19, 30)
    scr = []
    for i in range(22):                                         # 30 s screen samples from 19:30:10
        lab = "off_task" if i >= 13 else "on_task"
        title = "YouTube" if lab == "off_task" else ("Xcode" if i % 4 else "cppreference")
        scr.append({"ts": cstart + 10 + 30 * i, "label": lab, "note": title, "label_text": title,
                    "frame_url": None})
    now = at(19, 41, 3)
    windows = [{"title": "Xcode — sorting.cpp", "share": 0.46, "label": "on_task"},
               {"title": "Google Chrome — std::sort - cppreference.com", "share": 0.13, "label": "on_task"},
               {"title": "Google Chrome — Lofi beats to code to - YouTube", "share": 0.41, "label": "off_task"}]
    cpp_nudge = alert(at(19, 41), "nudge", "You said C++. That's been YouTube for 4 minutes.", session_id=cs,
                      habit="cpp", habit_label="C++", label="off_task", strike=False,
                      actions=[{"label": "Back to it", "say": "back"}, {"label": "This counts", "say": "it's on task"},
                               {"label": "Quiet 5 min", "say": "snooze 5"}])
    t_after_draw = today([math_today, ("drawing", 25, 0.92, "done")])
    out["nudge_window"] = payload(base, now, today_=t_after_draw, alert_=cpp_nudge,
                                  session=live_session(now, sid=cs, habit="cpp", label="C++", modality="digital",
                                                       declared=30, start=cstart, ends=cstart + 1800, labels=[],
                                                       recent_src=scr, nudges=1, windows=windows, so_far=0.59,
                                                       last_seen_src="screen"))

    # Three alternative endings of the persona session, each 3 s after it ended at 18:23 (50 samples).
    endings = {
        "done": (["on_task"] * 13 + ["phone"] * 4 + ["on_task"] * 33,
                 "Done. 23 of 25 minutes at the desk, pencil in hand."),
        "partial": (["on_task"] * 13 + ["phone"] * 16 + ["on_task"] * 21,
                    "Partly. 17 of 25 minutes on task. The phone had the rest."),
        "slacked": (["on_task"] * 12 + ["phone"] * 30 + ["absent"] * 8,
                    "Slacked, by my count. 6 of 25 minutes on task. Tap any frame if I got it wrong."),
    }
    now = ends + 3
    for verdict, (vscript, line) in endings.items():
        vlabels = p.labels(start, vscript)
        rv = finished_session(now, sid=sid, start=start, declared=25, labels=vlabels, verdict=verdict, summary=line,
                              evidence_url=ev)
        a = alert(ends, "verdict", line, session_id=sid, habit="drawing", habit_label="Drawing", verdict=verdict,
                  ratio=rv["on_task_ratio"], ended_early=False, missed=False, line=line.split(". ")[0] + ".",
                  image_url=ev,
                  actions=[{"label": "See proof", "url": f"/#session-{sid}"},
                           {"label": "Fix a moment", "url": f"/#session-{sid}"},
                           {"label": "Go again", "say": "drawing for 25 min"}])
        out[f"verdict_{verdict}"] = payload(base, now, alert_=a, recent_verdict=rv,
                                            today_=today([math_today, ("drawing", 25, rv["on_task_ratio"], verdict)]))

    # Health check-in from the iPhone (quiet: a wing glint and Pinch `connected`).
    now = at(19, 10, 3)
    out["synced"] = payload(base, now, today_=t_after_draw,
                            alert_=alert(at(19, 10), "synced", "Your iPhone checked in: steps 6,412.",
                                         source="health", date=DAY.isoformat()))

    # The nightly report, 3 s old: Pinch reads it.
    now = at(21, 0, 3)
    t_night = today([math_today, ("drawing", 25, 0.92, "done"), ("cpp", 30, 0.59, "partial")])
    out["report"] = payload(base, now, today_=t_night,
                            alert_=alert(at(21, 0), "report",
                                         "You claimed three hours. I saw two and a half. Drawing carried the day.",
                                         day=DAY.isoformat()))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--api", default="http://127.0.0.1:8775", help="lab server to read habits and frames from")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--copy-web", action="store_true", help=f"also copy the fixtures into {WEB.relative_to(ROOT)}")
    args = ap.parse_args()
    fixtures = build(args.api.rstrip("/"))
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, p in fixtures.items():
        (out / f"{name}.json").write_text(json.dumps(p, indent=1, ensure_ascii=False) + "\n")
        pc = p["pinch"]
        print(f"  {name:16} mood={pc['mood']:9} event={str(pc['event']):11} age_s={pc['age_s']}  line={pc['line']!r}")
    if args.copy_web:
        WEB.mkdir(parents=True, exist_ok=True)
        for name in fixtures:
            shutil.copyfile(out / f"{name}.json", WEB / f"{name}.json")
    print(f"wrote {len(fixtures)} fixtures")


if __name__ == "__main__":
    main()
