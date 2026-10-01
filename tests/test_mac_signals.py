"""Mac signals DoD (docs/SIGNALS.md, Mac table): presence every 30 s in a session / 5 min otherwise; notification
counts per app (iPhone ones marked phone, never text); media/meeting/focus on change; app-switch rate; git stats;
missing permissions or a missing helper degrade to plain status, never a crash. Uses tests/fake_sense.py and a
fixture copy of the usernoted database — never the real ones."""
import json, os, pathlib, sqlite3, stat, subprocess, tempfile, uuid
HERE = pathlib.Path(__file__).resolve().parent
FAKE = HERE / "fake_sense.py"
os.chmod(FAKE, os.stat(FAKE).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
TMP = pathlib.Path(tempfile.mkdtemp(prefix="alibi-mac-"))
STATE = TMP / "sense.json"
os.environ["ALIBI_SENSE_BIN"] = str(FAKE)
os.environ["FAKE_SENSE_STATE"] = str(STATE)
os.environ["MAC_SIGNALS_THREAD"] = "0"
os.environ["MAC_SIGNALS"] = "1"
NOTIF = TMP / "usernoted" / "db2" / "db"
os.environ["ALIBI_NOTIF_DB"] = str(NOTIF)
os.environ["CAMERA_SOURCE"] = str(HERE / "fixtures" / "desk_4min.mp4")   # Setup checks never ask the real camera
from harness import Clock, check
import yaml
from alibi import config, db, health, hooks, mac_signals as ms

MAC_EPOCH = 978307200
SNAP = {"idle_s": 3.0, "locked": False, "display_asleep": False, "displays": 2, "on_battery": False, "battery_pct": 80,
        "camera": False, "camera_devices": [], "mic": False, "mic_apps": [], "meeting_apps": ["Slack"], "media": [],
        "focus": {"on": None, "status": "unknown (needs Full Disk Access)"}, "front_app": "Cursor"}
INSTALLED = {"com.tinyspeck.slackmacgap": "Slack", "com.apple.ScreenContinuity": "iPhone Mirroring"}


def fake(**snap):
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    st["snap"] = {**SNAP, **snap}
    st["installed"] = INSTALLED
    STATE.write_text(json.dumps(st))


# --- a fixture usernoted database with the macOS layout (app + record; dates in seconds since 2001) ----------------
NOTIF.parent.mkdir(parents=True)
n = sqlite3.connect(NOTIF)
n.executescript("""
CREATE TABLE app(app_id INTEGER PRIMARY KEY, identifier VARCHAR, badge INTEGER NULL);
CREATE TABLE record(rec_id INTEGER PRIMARY KEY, app_id INTEGER, uuid BLOB, data BLOB, request_date REAL,
                    request_last_date REAL, delivered_date REAL, presented BOOL, style INTEGER, snooze_fire_date REAL);
""")
for i, ident in enumerate(["com.tinyspeck.slackmacgap", "com.burbn.instagram", "com.apple.ScreenContinuity",
                           "net.example.unknownphoneapp"], 1):
    n.execute("INSERT INTO app VALUES (?,?,0)", (i, ident))
n.commit()


def notify_at(app_id, ts):
    n.execute("INSERT INTO record(app_id, uuid, data, request_date, delivered_date, presented, style) VALUES (?,?,?,?,?,1,1)",
              (app_id, uuid.uuid4().bytes, b"SECRET MESSAGE TEXT", ts - MAC_EPOCH, ts - MAC_EPOCH))
    n.commit()


con = db.connect()
clock = Clock()
t0 = clock.t
fake()
for ts in (t0 - 3600, t0 - 100, t0 - 50):          # the hour-old one is outside the first window
    notify_at(1, ts)
notify_at(2, t0 - 20); notify_at(2, t0 - 10); notify_at(3, t0 - 5); notify_at(4, t0 - 5)

# --- 1. no session: one poll, presence + notifications ---------------------------------------------------------------
check("mac_signals" in hooks.PLUGINS, "mac_signals is a daemon plugin")
check(ms.sense_bin() == FAKE, "ALIBI_SENSE_BIN points at the fake helper")
ms.tick(con, clock.t)
ev = lambda kind=None: [e for e in db.events_between(con, 0, 1e12, "mac") if kind is None or e["kind"] == kind]
pres = ev("presence")
check(len(pres) == 1 and pres[0]["payload"]["idle_s"] == 3.0 and pres[0]["session_id"] is None
      and set(pres[0]["payload"]) >= {"idle_s", "locked", "display_asleep"}, "presence row: {idle_s, locked, display_asleep}")
notes = {e["payload"]["id"]: e["payload"] for e in ev("notifications")}
check(notes.get("com.tinyspeck.slackmacgap", {}).get("count") == 2 and notes["com.tinyspeck.slackmacgap"]["phone"] is False
      and notes["com.tinyspeck.slackmacgap"]["app"] == "Slack", "Slack (installed on the Mac): 2 in the window, phone=false")
check(notes.get("com.burbn.instagram", {}).get("count") == 2 and notes["com.burbn.instagram"]["phone"] is True
      and notes["com.burbn.instagram"]["app"] == "Instagram", "Instagram (not on this Mac): phone=true, named")
check(notes.get("com.apple.ScreenContinuity", {}).get("phone") is True, "iPhone Mirroring notifications: phone=true")
check(notes.get("net.example.unknownphoneapp", {}).get("phone") is True, "unknown non-Mac app id → phone")
check(all(set(p) >= {"app", "count", "phone", "window_s"} and p["window_s"] == 300 for p in notes.values()),
      "notifications payload {app, count, phone, window_s}")
check("SECRET" not in json.dumps([e["payload"] for e in ev()]), "notification text never leaves the database")
check(not ev("meeting") and not ev("focus") and not ev("media"), "nothing on, nothing to say: no meeting/focus/media rows")
check(ms.status()["focus"].startswith("unknown") and "Full Disk Access" in ms.status()["focus"],
      "Focus unreadable → 'unknown (needs Full Disk Access)'")

# --- 2. cadence: 5 min outside a session, 30 s inside ----------------------------------------------------------------
calls = lambda: json.loads(STATE.read_text())["calls"]
c0 = calls()
clock.advance(60); ms.tick(con, clock.t)
check(calls() == c0 and len(ev("presence")) == 1, "no session: no poll after 60 s")
clock.advance(241); ms.tick(con, clock.t)
check(len(ev("presence")) == 2, "no session: polls again after 5 min")
sid = db.create_session(con, "cpp", "digital", 30)
s_start = clock.t
clock.advance(1); ms.tick(con, clock.t)
check(len(ev("presence")) == 3 and ev("presence")[-1]["session_id"] == sid, "session start → immediate poll, attached")
clock.advance(10); ms.tick(con, clock.t)
check(len(ev("presence")) == 3, "in session: nothing 10 s later")
clock.advance(21); ms.tick(con, clock.t)
check(len(ev("presence")) == 4, "in session: polls every 30 s")
notify_at(2, clock.t + 10)
clock.advance(30); ms.tick(con, clock.t)
new = [e["payload"] for e in ev("notifications") if e["session_id"] == sid]
check(len(new) == 1 and new[0]["id"] == "com.burbn.instagram" and new[0]["count"] == 1 and new[0]["window_s"] == 30,
      "a new Instagram notification counted once, window 30 s, in the session")

# --- 3. media on change ------------------------------------------------------------------------------------------------
fake(media=[{"app": "Spotify", "id": "com.spotify.client", "playing": True, "title": "Song — Artist", "status": "allowed"}])
clock.advance(30); ms.tick(con, clock.t)
clock.advance(30); ms.tick(con, clock.t)
m = [e["payload"] for e in ev("media")]
check(len(m) == 1 and m[0] == {"app": "Spotify", "playing": True, "title": "Song — Artist"}, "Spotify playing → one row")
fake(media=[{"app": "Spotify", "id": "com.spotify.client", "playing": False, "status": "allowed"}])
clock.advance(30); ms.tick(con, clock.t)
check([e["payload"]["playing"] for e in ev("media")] == [True, False], "paused → playing=false row")
fake(media=[{"app": "Music", "id": "com.apple.Music", "playing": None, "status": "needs_permission"}])
clock.advance(30); ms.tick(con, clock.t)
check(len(ev("media")) == 2 and "needs_permission" in ms.status()["media"], "no automation permission: status, no guess")
db.add_event(con, "laptop", "window", {"app": "Google Chrome", "title": "Lecture 4 - YouTube",
                                       "url": "https://www.youtube.com/watch?v=abc"}, session_id=sid, ts=clock.t + 5)
clock.advance(30); ms.tick(con, clock.t)
bv = ev("media")[-1]["payload"]
check(bv["app"] == "Google Chrome" and bv["playing"] is True and bv["via"] == "window", "browser video tab → media row")

# --- 4. meeting: camera/mic in use by another app; Alibi's own camera doesn't count ---------------------------------
fake(mic=True, mic_apps=["us.zoom.xos"], meeting_apps=["Slack", "Zoom"])
clock.advance(30); ms.tick(con, clock.t)
mt = ev("meeting")
check(len(mt) == 1 and mt[0]["payload"] == {"camera": False, "mic": True, "app": "Zoom"}, "Zoom on the mic → meeting row")
clock.advance(30); ms.tick(con, clock.t)
check(len(ev("meeting")) == 1, "unchanged meeting: no repeat row")
fake()
clock.advance(30); ms.tick(con, clock.t)
check(ev("meeting")[-1]["payload"] == {"camera": False, "mic": False}, "meeting over → off row")
db.finish_session(con, sid, ended_at=clock.t)
old_cam = config.CAMERA_SOURCE
config.CAMERA_SOURCE = ""                     # pretend a live desk camera (nothing is opened: the helper is fake)
sid2 = db.create_session(con, "drawing", "physical", 25)
fake(camera=True, camera_devices=["FaceTime HD Camera"])
clock.advance(1); ms.tick(con, clock.t)
check(len(ev("meeting")) == 2, "Alibi's own desk camera during a camera habit is not a meeting")
config.CAMERA_SOURCE = old_cam

# --- 5. Focus (when readable) -------------------------------------------------------------------------------------------
fake(focus={"on": True, "mode": "Work", "status": "ok"})
clock.advance(30); ms.tick(con, clock.t)
fake(focus={"on": False, "status": "ok"})
clock.advance(30); ms.tick(con, clock.t)
check([e["payload"] for e in ev("focus")] == [{"on": True, "mode": "Work"}, {"on": False}], "Focus on/off rows on change")

# --- 6. app-switch rate from laptop window events ------------------------------------------------------------------------
base = clock.t
for i, app in enumerate(["Cursor", "Safari", "Cursor", "Messages", "Cursor", "Cursor", "Safari", "Cursor", "Cursor", "Cursor"]):
    db.add_event(con, "laptop", "window", {"app": app, "title": "", "url": ""}, ts=base + 1 + i * 25)
clock.advance(255); ms.tick(con, clock.t)
sw = ev("switches")[-1]["payload"]
check(sw["switches"] == 6 and 1.4 <= sw["per_min"] <= 1.7 and sw["apps"][:3] == ["Cursor", "Safari", "Messages"],
      f"switches: 6 in ~4 min → {sw['per_min']}/min, apps listed")

# --- 7. git stats for habits.yaml repos ---------------------------------------------------------------------------------
repo = TMP / "learncpp"
repo.mkdir()
env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t"}
git = lambda *a, when=None: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True,
                                           env={**env, **({"GIT_AUTHOR_DATE": f"@{int(when)} +0000",
                                                           "GIT_COMMITTER_DATE": f"@{int(when)} +0000"} if when else {})})
git("init", "-q")
(repo / "a.cpp").write_text("int main(){}\n")
git("add", "."); git("commit", "-qm", "old", when=clock.t - 86400 * 3)
cfg = config.habits()
for h in cfg["habits"].values():                   # the user's real habits.yaml may list real repos; isolate the test
    h.pop("repos", None); h.pop("repo", None)
cfg["repos"] = [str(repo), str(TMP / "not-a-repo")]
yaml.safe_dump(cfg, open(config.HABITS_PATH, "w"), sort_keys=False)
check([p.name for p in ms.repos(con, clock.t)] == ["learncpp"], "repos from habits.yaml (non-repos skipped)")
ms.STATE["git_poll"] = 0
clock.advance(30); ms.tick(con, clock.t)
check(not ev("git"), "no work in this session yet → no git row")
(repo / "a.cpp").write_text("int main(){\n  return 0;\n}\n")
(repo / "b.h").write_text("#pragma once\n")
git("add", "."); git("commit", "-qm", "work", when=clock.t)
(repo / "c.cpp").write_text("// wip\n// more\n")
git("add", "c.cpp")
ms.STATE["git_poll"] = 0
clock.advance(30); ms.tick(con, clock.t)
g = ev("git")
check(len(g) == 1 and g[0]["payload"]["repo"] == "learncpp" and g[0]["payload"]["commits"] == 1
      and g[0]["payload"]["files"] == 3 and g[0]["payload"]["insertions"] >= 5 and g[0]["payload"]["uncommitted_files"] == 1
      and g[0]["session_id"] == sid2, "git row {repo, commits, files, insertions, deletions} for the session")
ms.STATE["git_poll"] = 0
clock.advance(30); ms.tick(con, clock.t)
check(len(ev("git")) == 1, "unchanged repo → no repeat git row")

# --- 8. no Full Disk Access / broken helper: plain status, never a crash -------------------------------------------------
os.chmod(NOTIF.parent, 0)
try:
    clock.advance(30); ms.tick(con, clock.t)
    st = ms.status()
    check(st["full_disk_access"] == "needs Full Disk Access" and st["notifications"] == "needs Full Disk Access",
          "no Full Disk Access → 'needs Full Disk Access', presence still written")
    rows = {r["key"]: r for r in health.checks()["checks"]}
    fd = rows["full_disk"]
    check(not fd["ok"] and "Full Disk Access" in fd["fix"] and "Full Disk Access" in fd["sentence"],
          "Setup: plain-language Full Disk Access row with the fix")
finally:
    os.chmod(NOTIF.parent, 0o755)
check(ms.full_disk_access() == "ok" and {r["key"]: r for r in health.checks()["checks"]}["full_disk"]["ok"],
      "Full Disk Access granted → row turns green")
st = json.loads(STATE.read_text()); st["crash"] = True; STATE.write_text(json.dumps(st))
before = len(ev("presence"))
clock.advance(30); ms.tick(con, clock.t)
check(len(ev("presence")) == before and ms.status()["sense"].startswith("error"), "helper fails → no presence, status says so")
st["crash"] = False; STATE.write_text(json.dumps(st))
os.environ["ALIBI_SENSE_BIN"] = str(TMP / "nope")
clock.advance(30); ms.tick(con, clock.t)
check(ms.status()["sense"].startswith("missing"), "helper missing → 'missing — run scripts/build_native.sh'")
os.environ["ALIBI_SENSE_BIN"] = str(FAKE)

# --- 9. Setup: Focus shortcuts + iPhone stream ---------------------------------------------------------------------------
health._SHORTCUTS.update(at=clock.t, names={"Alibi Focus On"})
rows = {r["key"]: r for r in health.checks()["checks"]}
check(not rows["focus_shortcuts"]["ok"] and "Alibi Focus Off" in rows["focus_shortcuts"]["fix"], "one Focus shortcut missing → says how")
health._SHORTCUTS.update(at=clock.t, names={"Alibi Focus On", "Alibi Focus Off", "Other"})
check({r["key"]: r for r in health.checks()["checks"]}["focus_shortcuts"]["ok"], "both Focus shortcuts → ready")
check(not rows["phone_stream"]["ok"] and "hasn't sent" in rows["phone_stream"]["detail"], "no phone rows → iPhone quiet")
db.add_event(con, "phone", "pickup", {"ts": clock.t - 120}, ts=clock.t - 120)
row = {r["key"]: r for r in health.checks()["checks"]}["phone_stream"]
check(row["ok"] and "2 min ago" in row["detail"], f"phone row 2 min ago → streaming ({row['detail']})")
check(health.checks()["ok"] in (True, False) and all("sentence" in r for r in health.checks()["checks"]), "rows have sentences")
print("Mac signals DoD passed.")
