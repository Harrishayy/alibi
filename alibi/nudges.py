"""Nudge mid-session when the last N samples are not on task (camera AND screen), escalate on the second.

Cooldown is durable: nudges are recorded as events(source='alibi', kind='nudge'), so a daemon restart can't repeat
one, and only samples taken after the last nudge count towards the next.

Mac focus guard (FOCUS_GUARD=1): a distracting site in the browser's front tab mid-session is one strike per
GUARD_EVERY_S. It nudges with the site's name and sends the tab to the focus page, if the tab is still on that site.
"""
import json, math, os, subprocess, threading, time
from urllib.parse import quote, urlparse
from . import config, db
from .notify import notify
from .verifier import DISTRACTIONS, SITE_NAMES

LINES = {
    "phone": "Still {habit}? Your phone's been out for {mins}.",
    "absent": "Still {habit}? The desk has been empty for {mins}.",
    "idle": "Still {habit}? You're there, but nothing's moving — {mins} now.",
    "off_task": "Still {habit}? That doesn't look like {habit} — {mins} now.",
    "window": "Still {habit}? Your screen has been {title} for {mins}.",
    "window_then": "Still {habit}? Your screen has been {title} for {mins}, plus {rest}.",
    "window_mixed": "Still {habit}? Your screen has been everything but {habit} for {mins} ({names}).",
}
SECOND = "Second time. It's going in the report."

# verifier.DISTRACTIONS holds words ("youtube", "x.com"), not hosts. These are the ones that are websites; a word with
# no entry (messages, spotify, ...) is an app or fine in the background, so the guard leaves it to the usual nudges.
_WEB = {"youtube": ("youtube.com", "youtu.be"), "netflix": ("netflix.com",), "twitter": ("twitter.com",),
        "x.com": ("x.com",), "reddit": ("reddit.com",), "instagram": ("instagram.com",), "tiktok": ("tiktok.com",),
        "twitch": ("twitch.tv",)}
GUARD_SITES = {h: SITE_NAMES.get(w, w) for w in DISTRACTIONS for h in _WEB.get(w, ())}    # host -> "YouTube"
GUARD_HOSTS = tuple(GUARD_SITES)
GUARD_ALLOW = ("music.youtube.com",)       # music while you work is fine, like Spotify: never redirect it
GUARD_EVERY_S = 120
GUARD_LINE = "You said {habit}. {site} can wait. {left} min left."
FOCUS_URL = f"http://127.0.0.1:{config.API_PORT}/web/focus.html"       # api.py serves alibi/web at /web
REDIRECT_APPS = ("Google Chrome", "Safari")


def cooldown_s() -> float:
    cfg = config.habits()
    if "nudge_cooldown_min" in cfg and config.SAMPLE_EVERY_S >= 30:
        return float(cfg["nudge_cooldown_min"]) * 60
    if config.SAMPLE_EVERY_S < 30:                               # demo cadence: nudge ~150 s, strike ~210 s
        return max(3.0 * config.SAMPLE_EVERY_S, 60.0)
    return 600.0


def recent_samples(con, session, since: float = 0.0) -> list[dict]:
    """Camera labels + (digital/hybrid) classified window titles, merged by time: [{ts, label, source, title?}]."""
    from . import evidence, verifier
    out = [{"ts": e["ts"], "label": e["payload"]["label"], "source": "camera", "note": e["payload"].get("note", "")}
           for e in verifier.camera_labels(con, session)] if session["modality"] in ("physical", "hybrid") else []
    if session["modality"] in ("digital", "hybrid"):
        win = verifier._window_events(con, session)[-12:]
        labels = verifier.classify_titles(con, session["habit"], {evidence._title_key(e["payload"]) for e in win})
        for e in win:
            k = evidence._title_key(e["payload"])
            out.append({"ts": e["ts"], "label": "on_task" if labels.get(k) == "on_task" else "off_task",
                        "source": "screen", "title": k, "app": e["payload"].get("app", "")})
    return sorted((x for x in out if x["ts"] > since), key=lambda x: x["ts"])


def nudges_for(con, session_id: int) -> list[dict]:
    return [e for e in db.session_events(con, session_id, "alibi") if e["kind"] == "nudge"]


def check(con, session) -> str | None:
    cfg = config.habits()
    n = int(cfg.get("nudge_after_off_task_samples", 3))
    now = time.time()
    if db.in_break(con, session["id"], now) or _snoozed(con, session["id"], now):
        return None
    guarded = _guard(con, session, now)     # its own 120 s window, not the cooldown: an open YouTube tab can't wait
    if guarded:
        return guarded
    past = nudges_for(con, session["id"])
    last = past[-1]["ts"] if past else 0.0
    if now - last < cooldown_s():
        return None
    labels = recent_samples(con, session, since=last)[-n:]
    habit = config.spoken_name(session["habit"])
    screen = []
    if len(labels) < n or any(l["label"] == "on_task" for l in labels):
        sig = _signal_reason(con, session, last, now)      # the phone/Mac can drift while the desk looks fine
        if not sig:
            return None
        worst, text = sig[0], sig[1].format(habit=habit)
        source = "signals"
    else:
        source = "samples"
        secs = int(labels[-1]["ts"] - labels[0]["ts"]) + (config.SAMPLE_EVERY_S if labels[-1]["source"] == "camera"
                                                           else config.LAPTOP_EVERY_S)
        mins = round(secs / 60)
        span = f"{secs} seconds" if secs < 90 else f"{mins} minute{'s' * (mins != 1)}"
        screen = [l for l in labels if l["source"] == "screen"]
        if screen and (len(screen) * 2 >= len(labels) or session["modality"] == "digital"):
            text, worst = _window_line(habit, screen, span), "off_task"
        else:
            cams = [l["label"] for l in labels if l["source"] == "camera"]
            worst = max(set(cams), key=cams.count)
            text = LINES[worst].format(habit=habit, mins=span)
    strike = len(past) >= 1
    if strike:
        text = f"{text} {_nth(len(past))}"
        db.add_event(con, "alibi", "strike", {"n": len(past)}, session_id=session["id"], ts=now)
        if config.BLOCK_ON_DRIFT and screen:
            _hide(_most_common_app(screen))
    db.add_event(con, "alibi", "nudge", {"text": text, "label": worst, "strike": strike, "from": source},
                 session_id=session["id"], ts=now)
    notify(text, kind="nudge", session_id=session["id"], habit=session["habit"], label=worst, strike=strike,
           actions=[{"label": "I'm back", "say": "back"}, {"label": "It's on task", "say": "it's on task"},
                    {"label": "Snooze 5m", "say": "snooze 5"}])
    return text


def _signal_reason(con, session, since: float, now: float) -> tuple[str, str] | None:
    """('phone', 'Your phone says Instagram for 10 min. Still {habit}?') from docs/SIGNALS.md rows, or None."""
    try:
        from . import signals
        return signals.nudge_reason(con, session, since, now)
    except Exception as e:
        print(f"[alibi] signal nudge skipped: {e!r}", flush=True)
        return None


def _span(secs: float) -> str:
    secs = int(secs)
    mins = round(secs / 60)
    return f"{secs} seconds" if secs < 90 else f"{mins} minute{'s' * (mins != 1)}"


def _window_line(habit: str, screen: list[dict], span: str) -> str:
    """Name what the screen actually was: one site -> its name + the whole span; a mostly-one-site run -> that
    site's own duration, 'then X'; a mix -> 'everything but C++ (YouTube, Slack, RustDesk)'."""
    from collections import Counter
    from . import verifier
    names = [verifier.short_title(l.get("title", "")) for l in screen]
    cnt = Counter(names)
    top, n = cnt.most_common(1)[0]
    if n == len(names):
        return LINES["window"].format(habit=habit, title=top, mins=span)
    if n * 2 > len(names):
        rest = verifier.join_names([k for k, _ in cnt.most_common()[1:3]])
        return LINES["window_then"].format(habit=habit, title=top, mins=_span(n * config.LAPTOP_EVERY_S), rest=rest)
    return LINES["window_mixed"].format(habit=habit, mins=span,
                                        names=", ".join(k for k, _ in cnt.most_common(4)))


def _most_common_app(screen: list[dict]) -> str:
    from collections import Counter
    return Counter(l.get("app", "") for l in screen).most_common(1)[0][0]


def _snoozed(con, session_id: int, now: float) -> bool:
    return any(e["payload"].get("until", 0) > now for e in db.user_events(con, session_id, "snooze"))


def _nth(n: int) -> str:
    """What the next nudge adds when the session already has n: 'Second time. ...', then third, fourth, fifth."""
    return {1: SECOND}.get(n, f"{['Third', 'Fourth', 'Fifth'][min(n, 4) - 2]} time. It's all going in the report.")


# --- Mac focus guard ------------------------------------------------------------------------------------------------

def _host(url) -> str:
    """'https://www.youtube.com/watch?v=1' -> 'www.youtube.com'; '' when it isn't a web address."""
    u = str(url or "").strip()
    if not u or u == "missing value":
        return ""
    try:
        return (urlparse(u if "://" in u else "http://" + u).hostname or "").rstrip(".")
    except ValueError:
        return ""


def guard_match(host: str) -> str | None:
    """The guarded host a host belongs to, exact or as a subdomain: m.youtube.com -> youtube.com; max.com -> None."""
    host = (host or "").lower().rstrip(".")
    if any(host == a or host.endswith("." + a) for a in GUARD_ALLOW):
        return None
    return next((h for h in GUARD_HOSTS if host == h or host.endswith("." + h)), None)


def _guard(con, session, now: float) -> str | None:
    """FOCUS_GUARD=1 (read on every call, so .env and the kill switch need no code): the newest window row of this
    session is fresh (2 x LAPTOP_EVERY_S) and its URL is a guarded site -> one strike, at most one per GUARD_EVERY_S.
    Browsers only: a native app is left to the usual nudges."""
    if os.getenv("FOCUS_GUARD", "0") != "1":
        return None
    row = con.execute("SELECT ts, payload FROM events WHERE source='laptop' AND kind='window' AND ts>=? AND ts<=? "
                      "ORDER BY ts DESC LIMIT 1", (session["started_at"], now)).fetchone()
    if not row or now - row[0] > 2 * config.LAPTOP_EVERY_S:
        return None
    try:
        w = json.loads(row[1])
    except ValueError:
        return None
    host = _host(w.get("url")) if isinstance(w, dict) else ""
    site = guard_match(host)
    if not site or con.execute("SELECT 1 FROM events WHERE source='alibi' AND kind='guard' AND session_id=? AND ts>?",
                               (session["id"], now - GUARD_EVERY_S)).fetchone():
        return None
    past = nudges_for(con, session["id"])
    strike = len(past) >= 1
    text = GUARD_LINE.format(habit=config.spoken_name(session["habit"]), site=GUARD_SITES[site],
                             left=max(1, math.ceil((session["ends_at"] - now) / 60)))
    if strike:
        text = f"{text} {_nth(len(past))}"
        db.add_event(con, "alibi", "strike", {"n": len(past)}, session_id=session["id"], ts=now)
    app = str(w.get("app") or "")
    action = "redirect" if app in REDIRECT_APPS else "none"
    db.add_event(con, "alibi", "guard", {"app": app, "host": host, "action": action}, session_id=session["id"], ts=now)
    db.add_event(con, "alibi", "nudge", {"text": text, "label": "off_task", "strike": strike, "from": "guard"},
                 session_id=session["id"], ts=now)                   # starts the usual cooldown too
    notify(text, kind="nudge", session_id=session["id"], habit=session["habit"], label="off_task", strike=strike,
           actions=[{"label": "I'm back", "say": "back"}, {"label": "Snooze 5m", "say": "snooze 5"}])
    if action == "redirect":
        _redirect(app, host)
    return text


_TAB = {"Google Chrome": ("windows", "active tab of front window"), "Safari": ("documents", "front document")}


def _osa(script: str, *args: str) -> str:
    try:
        return subprocess.run(["osascript", "-e", script, *args], capture_output=True, text=True,
                              timeout=3).stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _redirect(app: str, host: str) -> threading.Thread | None:
    """Send the browser's front tab to the focus page, only if it's still on a guarded site: read the URL, check its
    host here, then set it only if the tab still shows that exact URL. Off the tick thread; never raises.
    MAC_SIGNALS=0 (tests, a headless server) means hands off the real Mac."""
    if app not in _TAB or os.getenv("MAC_SIGNALS", "1") == "0":
        return None
    coll, tab = _TAB[app]

    def go():
        try:
            url = _osa(f'if application "{app}" is running then\ntell application "{app}"\n'
                       f'if (count of {coll}) > 0 then return URL of {tab}\nend tell\nend if\nreturn ""')
            h = guard_match(_host(url))
            if not h:
                return                                         # it moved on by itself: leave the tab alone
            _osa(f'on run argv\nif application "{app}" is not running then return ""\ntell application "{app}"\n'
                 f'if (count of {coll}) > 0 and (URL of {tab}) is (item 1 of argv) then '
                 f'set URL of {tab} to (item 2 of argv)\nend tell\nreturn ""\nend run',
                 url, f"{FOCUS_URL}?site={quote(GUARD_SITES[h])}")
        except Exception as e:
            print(f"[alibi] focus redirect skipped: {e!r}", flush=True)
    t = threading.Thread(target=go, daemon=True, name="alibi-guard")
    t.start()
    return t


def _hide(app: str) -> None:
    """Opal-style consequence: hide the off-task app. Opt-in (BLOCK_ON_DRIFT=1). Never hides Alibi or a terminal."""
    from .verifier import CODE_APPS
    if not app or app.lower() in ("alibi", "finder") or app.lower() in CODE_APPS:
        return
    safe = app.replace('"', "")
    subprocess.Popen(["osascript", "-e", f'tell application "System Events" to set visible of process "{safe}" to false'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
