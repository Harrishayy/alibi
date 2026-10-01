"""B1-B4: a closed lid isn't an alibi; IDEs count as code; verdicts/nudges name sites, not half a tab title;
the 4-minute demo gets its strike."""
import os
os.environ["SAMPLE_EVERY_S"] = "10"
os.environ["LAPTOP_EVERY_S"] = "10"
from harness import Clock, check
import make_fixtures
os.environ["CAMERA_SOURCE"] = str(make_fixtures.video("desk_b4.mp4", [("on_task", 120), ("phone", 60), ("absent", 60)]))
from alibi import cli, daemon, db, laptop_logger, notify, nudges, verifier

con = db.connect()
clock = Clock()
laptop_logger.frontmost = lambda: {"app": "", "title": "", "url": ""}

# B3: short names, never half a tab title
yt = "Google Chrome — But how do AI images and videos actually work? - YouTube - Google Chrome – Harrish"
check(verifier.short_title(yt) == "YouTube", "short_title(YouTube tab) = " + verifier.short_title(yt))
check(verifier.short_title("Google Chrome — Meet - abc-defg-hij") == "Google Meet", "Meet tab -> Google Meet")
check(verifier.short_title("RustDesk") == "RustDesk" and verifier.short_title("Cursor") == "Cursor", "bare app names")
check(verifier.short_title("Google Chrome — Some page", "https://www.example.org/x") == "example.org", "URL host")

# B2a: editors and terminals are code
for app in ("Cursor", "Xcode — main.cpp", "CLion", "iTerm2", "Terminal", "Zed"):
    check(verifier._rule_label("cpp", app) == "on_task", f"{app} is on task for C++")
check(verifier._rule_label("cpp", "Google Chrome — YouTube") == "off_task", "YouTube still off task")
check(verifier._rule_label("drawing", "Cursor") == "off_task", "Cursor isn't drawing")

# B4: the 4-minute fixture gets a nudge (phone) AND a strike (absent) before the bell
cli.say(con, "draw for 4 minutes")
sid = db.active_session(con)["id"]
seen = []
for _ in range(50):
    daemon.tick(con); clock.advance(5)
    seen += [a for a in notify.recent_alerts(5) if a["kind"] == "nudge" and a["id"] not in [s["id"] for s in seen]]
check(len(seen) >= 2, "two nudges in 4 min: " + " | ".join(a["text"] for a in seen))
check("phone" in seen[0]["text"] and "Second time" in seen[1]["text"], "phone nudge, then strike")
check(sum(e["kind"] == "strike" for e in db.session_events(con, sid, "alibi")) >= 1, "strike recorded")
check(db.get_session(con, sid)["status"] == "done", "session closed at the bell")

# B2b + B3: mixed off-task screen -> 'everything but C++', and the verdict names the sites
seq = [{"app": "RustDesk", "title": "", "url": ""},
       {"app": "Google Chrome", "title": yt, "url": ""},
       {"app": "Slack", "title": "", "url": ""}]
i = [0]
def front():
    i[0] += 1
    return seq[i[0] % 3]
laptop_logger.frontmost = front
cli.say(con, "code c++ for 3 minutes")
sid = db.active_session(con)["id"]
first = None
for _ in range(40):
    daemon.tick(con); clock.advance(5)
    n = nudges.nudges_for(con, sid)
    if n and first is None:
        first = n[0]["payload"]["text"]
check(first and "everything but C++" in first and "YouTube" in first and "Slack" in first, f"mixed nudge: {first}")
s = db.get_session(con, sid)
if s["status"] != "done":
    cli.end(con)
s = db.get_session(con, sid)
v = verifier.voice(con, s)
check(v.startswith("C++: slacked.") and "none of it C++" in v and "But how" not in v, "mixed verdict: " + v)

# B2a live: Cursor with an empty title is not a nudge
laptop_logger.frontmost = lambda: {"app": "Cursor", "title": "", "url": ""}
cli.say(con, "code c++ for 3 minutes")
sid = db.active_session(con)["id"]
for _ in range(30):
    daemon.tick(con); clock.advance(5)
check(not nudges.nudges_for(con, sid), "no nudge while in Cursor")
cli.end(con)
check(db.get_session(con, sid)["verdict"] == "done", "Cursor session done: " + str(db.get_session(con, sid)["verdict"]))

# B1: lid closed mid-session — one sample, then nothing until long after the bell
laptop_logger.frontmost = lambda: {"app": "", "title": "", "url": ""}
start = clock.t - 30 * 60
cur = con.execute("INSERT INTO sessions(habit, modality, declared_min, started_at, ends_at) VALUES (?,?,?,?,?)",
                  ("drawing", "physical", 25, start, start + 25 * 60))
con.commit()
sid = cur.lastrowid
db.add_event(con, "camera", "label", {"label": "on_task", "note": "hands on the work"}, session_id=sid, ts=start + 30)
daemon.tick(con)
s = db.get_session(con, sid)
check(s["status"] == "done" and s["verdict"] == "slacked" and s["on_task_ratio"] < 0.2,
      f"lid closed -> {s['verdict']} {s['on_task_ratio']:.0%}")
msg = next(a["text"] for a in notify.recent_alerts(10) if a["kind"] == "verdict" and a.get("session_id") == sid)
check("laptop slept" in msg and "1 samples" not in msg, "missed verdict: " + msg)
check("laptop asleep" in verifier.stats(con, s)["why"], "why: " + verifier.stats(con, s)["why"])
print("Backend fixes DoD passed.")
