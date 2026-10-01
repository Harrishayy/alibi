"""Daemon plugin: what the Mac itself can say about whether you're working (docs/SIGNALS.md, "Mac" table).

Every 30 s while a session runs (5 min otherwise) it asks bin/alibi-sense for a cheap snapshot and writes
events(source='mac'):

  presence       {idle_s, locked, display_asleep, displays, on_battery, battery_pct}   every poll
  media          {app, title?, playing, via?}       Music/Spotify (sense) + browser video tabs (window events); on change
  meeting        {camera, mic, app?}                camera/mic in use by *another* app; on change
  focus          {on, mode?}                        macOS Focus (needs Full Disk Access); on change
  notifications  {app, id, count, phone, window_s}  counts per app since the last poll — never message text
  switches       {per_min, apps, window_s}          app-switch rate derived from laptop window events
  git            {repo, path, commits, files, insertions, deletions, uncommitted_files}   on change

Permission-gated reads degrade to a status string (status()) instead of raising: the notification database and
Focus need Full Disk Access. Nothing here ever prompts. Tests point ALIBI_SENSE_BIN at a fake helper and
ALIBI_NOTIF_DB at a fixture database.
"""
import json, os, pathlib, platform, shutil, sqlite3, subprocess, tempfile, threading, time
from . import config, db

IN_SESSION_EVERY_S = int(os.getenv("MAC_SIGNALS_EVERY_S", "30"))
IDLE_EVERY_S = int(os.getenv("MAC_SIGNALS_IDLE_EVERY_S", "300"))
GIT_SESSION_EVERY_S = int(os.getenv("MAC_GIT_EVERY_S", "300"))
GIT_IDLE_EVERY_S = int(os.getenv("MAC_GIT_IDLE_EVERY_S", "1800"))
SWITCH_WINDOW_S = 300
ENABLED = os.getenv("MAC_SIGNALS", "1") != "0"
THREADED = os.getenv("MAC_SIGNALS_THREAD", "1") == "1"      # tests poll inline
ASK_MEDIA = os.getenv("MAC_MEDIA_ASK", "0") == "1"           # 1 = allow the one-time Music/Spotify automation prompt

HOME = pathlib.Path.home()
NOTIF_DIR = HOME / "Library" / "Group Containers" / "group.com.apple.usernoted" / "db2"
FOCUS_DIR = HOME / "Library" / "DoNotDisturb" / "DB"
MAC_EPOCH = 978307200                                        # 2001-01-01 — Core Data / NSDate reference
FDA_TEXT = "needs Full Disk Access"
FDA_FIX = ("Open System Settings → Privacy & Security → Full Disk Access and turn on Alibi "
           "(or Terminal, if you start Alibi from Terminal)")

# iPhone apps whose notifications reach this Mac through iPhone Mirroring have no app here; give them their names.
PHONE_APP_NAMES = {
    "com.burbn.instagram": "Instagram", "net.whatsapp.WhatsApp": "WhatsApp", "com.atebits.Tweetie2": "X",
    "com.google.Gmail": "Gmail", "com.toyopagroup.picaboo": "Snapchat", "com.zhiliaoapp.musically": "TikTok",
    "ph.telegra.Telegraph": "Telegram", "com.facebook.Messenger": "Messenger", "com.facebook.Facebook": "Facebook",
    "com.reddit.Reddit": "Reddit", "com.hammerandchisel.discord": "Discord", "com.tinyspeck.chatlyio": "Slack",
    "com.apple.MobileSMS": "Messages", "com.strava.stravaride": "Strava", "com.linkedin.LinkedIn": "LinkedIn",
    "com.google.ios.youtube": "YouTube", "com.spotify.client": "Spotify", "com.netflix.Netflix": "Netflix",
    "com.amazon.Amazon": "Amazon", "com.ubercab.UberClient": "Uber", "com.duolingo.DuolingoMobile": "Duolingo",
    "com.apple.mobilemail": "Mail", "com.apple.mobilephone": "Phone", "com.apple.Health": "Health",
}
MIRROR_PREFIXES = ("com.apple.ScreenContinuity", "com.apple.iphonemirroring", "com.apple.iPhoneMirroring")
MEETING_IDS = {"us.zoom.xos": "Zoom", "com.microsoft.teams2": "Teams", "com.microsoft.teams": "Teams",
               "com.apple.FaceTime": "FaceTime", "com.cisco.webexmeetingsapp": "Webex", "com.hnc.Discord": "Discord",
               "com.tinyspeck.slackmacgap": "Slack", "com.google.Chrome": "Chrome", "com.apple.Safari": "Safari",
               "company.thebrowser.Browser": "Arc", "com.brave.Browser": "Brave"}
VIDEO_HOSTS = ("youtube.com/watch", "youtube.com/shorts", "youtu.be/", "netflix.com/watch", "twitch.tv/",
               "primevideo.com", "disneyplus.com", "hulu.com/watch", "max.com", "tv.apple.com", "vimeo.com/")

_lock = threading.Lock()
_thread: threading.Thread | None = None
_installed_cache: dict[str, str | None] = {}
STATE: dict = {}          # last poll, last emitted values — reset() for tests
STATUS: dict = {}         # sense / notifications / focus / media: plain status strings for Setup


def reset() -> None:
    STATE.clear()
    STATE.update(last_poll=0.0, session=None, media={}, meeting=None, focus=None, notif_since=None,
                 notif_mtime=None, git={}, git_poll=0.0)
    STATUS.clear()


reset()


# --- the helper ----------------------------------------------------------------------------------------------------

def sense_bin() -> pathlib.Path | None:
    """ALIBI_SENSE_BIN (tests), else the copy inside Alibi.app (permissions belong to "Alibi"), else bin/."""
    env = os.getenv("ALIBI_SENSE_BIN")
    if env:
        return pathlib.Path(env)
    for p in (config.ROOT / "Alibi.app" / "Contents" / "MacOS" / "alibi-sense", config.ROOT / "bin" / "alibi-sense"):
        if p.exists():
            return p
    return None


def _run_sense(*args: str, timeout: float = 5) -> dict | None:
    b = sense_bin()
    if b is None or not b.exists():
        STATUS["sense"] = "missing — run scripts/build_native.sh"
        return None
    try:
        r = subprocess.run([str(b), *args], capture_output=True, text=True, timeout=timeout)
        d = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else None
    except Exception as e:
        STATUS["sense"] = f"error: {e!r}"[:200]
        return None
    if not isinstance(d, dict):
        STATUS["sense"] = f"error: no output (exit {r.returncode})"
        return None
    STATUS["sense"] = "ok"
    return d


def sense(ask_media: bool | None = None) -> dict | None:
    return _run_sense(*(["--ask-media"] if (ASK_MEDIA if ask_media is None else ask_media) else []))


def installed_names(ids: list[str]) -> dict[str, str | None]:
    """{bundle id: app name on this Mac | None}, cached for the life of the process."""
    todo = [i for i in ids if i not in _installed_cache]
    got = _run_sense("--installed", *todo) if todo else {}
    if got is None:                          # helper unavailable: "?" = don't know, and don't remember it
        return {i: _installed_cache.get(i, "?") for i in ids}
    for i in todo:
        _installed_cache[i] = got.get(i)
    return {i: _installed_cache.get(i) for i in ids}


# --- notifications (counts only) -------------------------------------------------------------------------------------

def notif_db_path() -> pathlib.Path:
    return pathlib.Path(os.getenv("ALIBI_NOTIF_DB", str(NOTIF_DIR / "db")))


def full_disk_access() -> str:
    """'ok' | 'needs Full Disk Access' | 'no notification database' — a directory listing, never a prompt."""
    p = notif_db_path()
    try:
        os.listdir(p.parent)
    except PermissionError:
        return FDA_TEXT
    except FileNotFoundError:
        return "no notification database"
    except OSError as e:
        return FDA_TEXT if e.errno in (1, 13) else f"error: {e.strerror}"
    return "ok" if p.exists() else "no notification database"


def read_notifications(since: float, path: pathlib.Path | None = None) -> tuple[str, dict[str, int]]:
    """(status, {bundle id: count}) of notifications delivered after `since` (unix s). Copies the database (+WAL) to a
    temp dir and opens the copy read-only, so usernoted's locks never matter. Only app ids and counts are read."""
    path = path or notif_db_path()
    tmp = tempfile.mkdtemp(prefix="alibi-notif-")
    try:
        try:
            for suffix in ("", "-wal", "-shm"):
                src = pathlib.Path(str(path) + suffix)
                if suffix and not src.exists():
                    continue
                shutil.copyfile(src, os.path.join(tmp, "db" + suffix))
        except PermissionError:
            return FDA_TEXT, {}
        except FileNotFoundError:
            return "no notification database", {}
        except OSError as e:
            return (FDA_TEXT if e.errno in (1, 13) else f"error: {e.strerror}"), {}
        try:
            con = sqlite3.connect(f"file:{tmp}/db?mode=ro", uri=True, timeout=2)
            try:
                cols = {r[1] for r in con.execute("PRAGMA table_info(record)")}
                col = next((c for c in ("delivered_date", "request_date", "request_last_date") if c in cols), None)
                if not col or "app_id" not in cols:
                    return "error: unknown notification database layout", {}
                rows = con.execute(f"SELECT a.identifier, COUNT(*) FROM record r JOIN app a ON a.app_id = r.app_id "
                                   f"WHERE r.{col} > ? GROUP BY a.identifier", (since - MAC_EPOCH,)).fetchall()
            finally:
                con.close()
        except sqlite3.Error as e:
            return f"error: {e}", {}
        return "ok", {str(i): int(n) for i, n in rows if i}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def classify_app(bid: str, installed: str | None) -> tuple[str, bool]:
    """(display name, came from the iPhone?). iPhone Mirroring's own id, or an app that isn't on this Mac, is the
    phone; com.apple.* system ids and installed Mac apps are the Mac."""
    if bid.startswith(MIRROR_PREFIXES):
        return "iPhone", True
    if installed and installed != "?":
        return installed, False
    if bid.startswith("com.apple.") and bid not in PHONE_APP_NAMES:
        return bid.rsplit(".", 1)[-1], False
    if installed == "?":                       # helper unavailable: guess from the name only
        return PHONE_APP_NAMES.get(bid, bid.rsplit(".", 1)[-1]), bid in PHONE_APP_NAMES
    return PHONE_APP_NAMES.get(bid, bid.rsplit(".", 1)[-1].replace("-", " ").title()), True


def _notifications(now: float, every: float) -> list[dict]:
    since = STATE["notif_since"] or (now - every)
    p = notif_db_path()
    try:                                      # unchanged database + WAL → nothing new; skip the copy
        mt = max(os.stat(str(p) + s).st_mtime for s in ("", "-wal") if os.path.exists(str(p) + s))
    except (OSError, ValueError):
        mt = None
    if mt is not None and mt == STATE["notif_mtime"]:
        STATE["notif_since"] = now
        STATUS["notifications"] = "ok"
        return []
    status, counts = read_notifications(since, p)
    STATUS["notifications"] = status
    if status != "ok":
        return []
    STATE["notif_since"], STATE["notif_mtime"] = now, mt
    names = installed_names(sorted(counts))
    out = []
    for bid, n in sorted(counts.items()):
        app, phone = classify_app(bid, names.get(bid))
        out.append({"app": app, "id": bid, "count": n, "phone": phone, "window_s": int(round(now - since))})
    return out


# --- derived from laptop window events ------------------------------------------------------------------------------

def switches(con, now: float, window_s: int = SWITCH_WINDOW_S) -> dict | None:
    ev = db.events_between(con, now - window_s, now, "laptop")
    apps = [e["payload"].get("app") for e in ev if e["kind"] == "window" and e["payload"].get("app")]
    if len(apps) < 2:
        return None
    n = sum(a != b for a, b in zip(apps, apps[1:]))
    span = max(60.0, now - ev[0]["ts"]) if ev else window_s
    seen = list(dict.fromkeys(apps))[:8]
    return {"per_min": round(n / (span / 60), 2), "apps": seen, "window_s": int(window_s), "switches": n}


def browser_video(con, now: float) -> dict | None:
    r = con.execute("SELECT ts, payload FROM events WHERE source='laptop' AND kind='window' AND ts BETWEEN ? AND ? "
                    "ORDER BY ts DESC LIMIT 1", (now - 90, now)).fetchone()
    if not r:
        return None
    p = json.loads(r["payload"])
    url = (p.get("url") or "").lower()
    if any(h in url for h in VIDEO_HOSTS):
        return {"app": p.get("app") or "Browser", "title": (p.get("title") or "")[:120], "playing": True,
                "via": "window"}
    return None


# --- git ------------------------------------------------------------------------------------------------------------

def repos(con, now: float) -> list[pathlib.Path]:
    """habits.yaml top-level `repos:` + any habit's `repo`/`repos`, plus session artefacts (30 days) that are git repos."""
    paths: list[str] = []
    try:
        cfg = config.habits() or {}
    except Exception:
        cfg = {}
    paths += [str(x) for x in (cfg.get("repos") or []) if x]
    for h in (cfg.get("habits") or {}).values():
        if isinstance(h, dict):
            v = h.get("repos") or h.get("repo") or []
            paths += [str(x) for x in ([v] if isinstance(v, str) else v) if x]
    try:
        paths += [r[0] for r in con.execute("SELECT DISTINCT artefact FROM sessions WHERE artefact IS NOT NULL "
                                            "AND artefact != '' AND started_at > ?", (now - 30 * 86400,))]
    except sqlite3.Error:
        pass
    out, seen = [], set()
    for p in paths:
        q = pathlib.Path(os.path.expanduser(p))
        if not (q / ".git").exists():
            continue
        real = q.resolve()
        if real not in seen:
            seen.add(real)
            out.append(real)
    return out[:10]


def _shortstat(line: str) -> tuple[int, int, int]:
    f = i = d = 0
    for part in line.split(","):
        w = part.strip().split(" ")
        if len(w) >= 2 and w[0].isdigit():
            if "file" in w[1]:
                f = int(w[0])
            elif "insertion" in w[1]:
                i = int(w[0])
            elif "deletion" in w[1]:
                d = int(w[0])
    return f, i, d


def git_stats(path: pathlib.Path, since: float) -> dict | None:
    """Commits since `since` (+ their shortstat), plus uncommitted changes. Read-only git commands, 5 s timeout."""
    try:
        log = subprocess.run(["git", "-C", str(path), "log", f"--since=@{int(since)}", "--no-merges", "--shortstat",
                              "--format=%H"], capture_output=True, text=True, timeout=5)
        wt = subprocess.run(["git", "-C", str(path), "diff", "HEAD", "--shortstat"], capture_output=True, text=True,
                            timeout=5)
    except Exception:
        return None
    if log.returncode != 0:
        return None
    commits = files = ins = dels = 0
    for line in log.stdout.splitlines():
        line = line.strip()
        if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            commits += 1
        elif "changed" in line:
            f, i, d = _shortstat(line)
            files, ins, dels = files + f, ins + i, dels + d
    uf, ui, ud = _shortstat(wt.stdout.strip()) if wt.returncode == 0 else (0, 0, 0)
    return {"repo": path.name, "path": str(path), "commits": commits, "files": files + uf, "insertions": ins + ui,
            "deletions": dels + ud, "uncommitted_files": uf}


def _git(con, now: float, session) -> list[dict]:
    every = GIT_SESSION_EVERY_S if session else GIT_IDLE_EVERY_S
    if now - STATE["git_poll"] < every and STATE["git_poll"]:
        return []
    STATE["git_poll"] = now
    if session:
        since = session["started_at"]
    else:
        t = time.localtime(now)
        since = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))
    out = []
    for path in repos(con, now):
        st = git_stats(path, since)
        if not st:
            continue
        sig = (since, st["commits"], st["files"], st["insertions"], st["deletions"])
        key = str(path)
        prev = STATE["git"].get(key)
        if prev == sig or (not st["commits"] and not st["files"] and (prev is None or prev[0] != since)):
            STATE["git"][key] = sig                  # nothing done yet in this window: no row
            continue
        STATE["git"][key] = sig
        out.append(st)
    return out


# --- the poll ---------------------------------------------------------------------------------------------------------

def _meeting_app(s: dict) -> str | None:
    for bid in s.get("mic_apps") or []:
        if bid in MEETING_IDS:
            return MEETING_IDS[bid]
    apps = [a for a in (s.get("meeting_apps") or []) if a != "Slack"] or list(s.get("meeting_apps") or [])
    if s.get("mic_apps"):
        bid = s["mic_apps"][0]
        return _installed_cache.get(bid) or bid.rsplit(".", 1)[-1]
    return apps[0] if apps else None


def poll(con, now: float | None = None) -> list[tuple[str, dict]]:
    """One look. Writes events(source='mac') and returns [(kind, payload)] for what it wrote."""
    now = now or time.time()
    s = db.active_session(con)
    sid = s["id"] if s and s["started_at"] <= now <= max(s["ends_at"], now) else None
    new_session = sid is not None and sid != STATE["session"]
    STATE["session"] = sid
    every = IN_SESSION_EVERY_S if sid else IDLE_EVERY_S
    rows: list[tuple[str, dict]] = []
    snap = sense()
    if snap:
        if snap.get("idle_s") is not None:
            rows.append(("presence", {k: snap.get(k) for k in ("idle_s", "locked", "display_asleep", "displays",
                                                               "on_battery", "battery_pct") if k in snap}))
        # media: one row per player, only when something changed (or a session just began and it's playing)
        players = [m for m in (snap.get("media") or []) if isinstance(m, dict)]
        STATUS["media"] = ", ".join(f"{m.get('app')}: {m.get('status')}" for m in players) or "nothing running"
        current = {}
        for m in players:
            if m.get("playing") is None:
                continue
            current[m["app"]] = {"app": m["app"], "playing": bool(m["playing"]),
                                 **({"title": m["title"]} if m.get("title") else {})}
        bv = browser_video(con, now)
        if bv:
            current[bv["app"] + " video"] = bv
        for key, m in current.items():
            if STATE["media"].get(key) != m or (new_session and m["playing"]):
                rows.append(("media", m))
        for key, m in STATE["media"].items():
            if key not in current and m.get("playing"):
                rows.append(("media", {"app": m["app"], "playing": False, **({"via": m["via"]} if m.get("via") else {})}))
        STATE["media"] = current
        # meeting: camera/mic in use by another app. Alibi's own desk camera doesn't count.
        cam, mic = bool(snap.get("camera")), bool(snap.get("mic"))
        own = (s is not None and s["modality"] in ("physical", "hybrid") and not config.CAMERA_SOURCE)
        meet = {"camera": cam, "mic": mic}
        if own and cam and not mic:
            meet["camera"] = False
            meet["self_camera"] = True
        if meet["camera"] or meet["mic"]:
            app = _meeting_app(snap)
            if app:
                meet["app"] = app
        sig = (meet["camera"], meet["mic"], meet.get("app"))
        if sig != STATE["meeting"] and not (STATE["meeting"] is None and not (meet["camera"] or meet["mic"])):
            rows.append(("meeting", meet))
        elif new_session and (meet["camera"] or meet["mic"]):
            rows.append(("meeting", meet))
        STATE["meeting"] = sig
        # focus
        f = snap.get("focus") or {}
        STATUS["focus"] = f.get("status") or "unknown"
        if isinstance(f.get("on"), bool):
            fv = {"on": f["on"], **({"mode": f["mode"]} if f.get("mode") else {})}
            changed = fv != STATE["focus"] and not (STATE["focus"] is None and not fv["on"])
            if changed or (new_session and fv["on"]):
                rows.append(("focus", fv))
            STATE["focus"] = fv
    for n in _notifications(now, every):
        rows.append(("notifications", n))
    sw = switches(con, now)
    if sw:
        rows.append(("switches", sw))
    for g in _git(con, now, s if sid else None):
        rows.append(("git", g))
    for kind, payload in rows:
        db.add_event(con, "mac", kind, payload, session_id=sid, ts=now)
    STATE["last_poll"] = now
    STATUS["last_poll"] = now
    return rows


def _poll_in_thread(now: float) -> None:
    con = db.connect()
    try:
        poll(con, now)
    except Exception as e:
        print(f"[alibi] mac signals poll failed: {e!r}", flush=True)
    finally:
        con.close()


def due(con, now: float) -> bool:
    s = db.active_session(con)
    sid = s["id"] if s else None
    every = IN_SESSION_EVERY_S if sid else IDLE_EVERY_S
    return sid != STATE["session"] or now - STATE["last_poll"] >= every


def tick(con, now: float) -> None:
    """Called every daemon tick; polls on the contract's cadence (30 s in a session, 5 min otherwise)."""
    global _thread
    if not ENABLED or (platform.system() != "Darwin" and not os.getenv("ALIBI_SENSE_BIN")):
        return
    if not due(con, now):
        return
    if not THREADED:
        poll(con, now)
        return
    with _lock:
        if _thread and _thread.is_alive():
            return
        STATE["last_poll"] = now                     # don't re-trigger while the thread runs
        _thread = threading.Thread(target=_poll_in_thread, args=(now,), daemon=True, name="alibi-mac-signals")
        _thread.start()


def status() -> dict:
    """Plain words for Setup and the dashboard: what the Mac can and can't see right now."""
    fda = full_disk_access()
    b = sense_bin()
    return {"sense": STATUS.get("sense") or ("ready" if b and b.exists() else "missing — run scripts/build_native.sh"),
            "full_disk_access": fda, "notifications": STATUS.get("notifications") or fda,
            "focus": STATUS.get("focus") or ("unknown" if fda == "ok" else f"unknown ({FDA_TEXT})"),
            "media": STATUS.get("media") or "unknown", "last_poll": STATUS.get("last_poll"),
            "every_s": {"session": IN_SESSION_EVERY_S, "otherwise": IDLE_EVERY_S}}
