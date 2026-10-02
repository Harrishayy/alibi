"""Mac focus guard DoD. A guarded site in the browser's front tab mid-session gives one nudge naming
it, one alibi/guard event and one redirect; nothing again inside 120 s; nothing with FOCUS_GUARD off; max.com and
linux.com never match. _redirect is monkeypatched, and the real one is only run against a fake subprocess.run:
no osascript ever runs here."""
import datetime as dt, math, os, types
os.environ["LAPTOP_EVERY_S"] = "10"
from harness import Clock, check
os.environ["FOCUS_GUARD"] = "1"           # after the harness, which pins it off for every other test
from fastapi.testclient import TestClient
from alibi import api, config, daemon, db, laptop_logger, notify, nudges

con = db.connect()
clock = Clock()
clock.t = dt.datetime.fromtimestamp(clock.t).replace(hour=10, minute=0, second=0).timestamp()   # far from 22:00
real_redirect = nudges._redirect
redirects = []
nudges._redirect = lambda app, host: redirects.append((app, host))
YT = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def window(url, app="Google Chrome", title="A tab"):
    s = db.active_session(con)
    db.add_event(con, "laptop", "window", {"app": app, "title": title, "url": url},
                 session_id=s["id"] if s else None, ts=clock.t)


def alibi_rows(sid, kind):
    return [e for e in db.session_events(con, sid, "alibi") if e["kind"] == kind]


def nudge_alerts():
    return [a for a in notify.recent_alerts(500) if a["kind"] == "nudge"]


def left(s):
    return max(1, math.ceil((s["ends_at"] - clock.t) / 60))


# hosts: derived from verifier.DISTRACTIONS, matched exactly or as a dot-suffix
check(set(nudges.GUARD_HOSTS) == {"youtube.com", "youtu.be", "netflix.com", "twitter.com", "x.com", "reddit.com",
                                  "instagram.com", "tiktok.com", "twitch.tv"}, f"GUARD_HOSTS {nudges.GUARD_HOSTS}")
check(nudges.guard_match("m.youtube.com") == "youtube.com" and nudges.guard_match("youtu.be") == "youtu.be"
      and nudges.guard_match("X.com") == "x.com", "subdomains and case match")
check(not any(nudges.guard_match(h) for h in ("max.com", "linux.com", "notyoutube.com", "youtube.com.evil.io", "")),
      "max.com, linux.com, notyoutube.com and youtube.com.evil.io never match")
check(nudges.guard_match("music.youtube.com") is None, "YouTube Music in the background is left alone")
check(nudges._host(YT) == "www.youtube.com" and nudges._host("missing value") == "" and nudges._host("") == "",
      "URL host parsing")

# strike 1: a YouTube tab, FOCUS_GUARD=1
sid = db.create_session(con, "drawing", "physical", 25)
s = db.get_session(con, sid)
clock.advance(270)
window(YT, title="Never Gonna Give You Up - YouTube")
expect = f"You said drawing. YouTube can wait. {left(s)} min left."
r = nudges.check(con, s)
check(r == expect, f"nudge text: {r!r}")
al = nudge_alerts()
check(len(al) == 1 and al[0]["label"] == "off_task" and al[0]["text"] == expect and al[0]["session_id"] == sid
      and al[0]["strike"] is False and [a["say"] for a in al[0]["actions"]] == ["back", "snooze 5"],
      "1 nudge alert: off_task, the nudge line, I'm back and Snooze")
g = alibi_rows(sid, "guard")
check(len(g) == 1 and g[0]["payload"] == {"app": "Google Chrome", "host": "www.youtube.com", "action": "redirect"},
      f"1 alibi/guard event {g[0]['payload'] if g else None}")
n = alibi_rows(sid, "nudge")
check(len(n) == 1 and n[0]["payload"]["from"] == "guard" and n[0]["payload"]["label"] == "off_task",
      "1 alibi/nudge event from the guard (it starts the usual cooldown)")
check(redirects == [("Google Chrome", "www.youtube.com")], f"1 redirect {redirects}")
check(not alibi_rows(sid, "strike"), "first nudge of the session is no strike")

# a second row inside 120 s: nothing
clock.advance(60)
window(YT)
check(nudges.check(con, s) is None and len(nudge_alerts()) == 1 and len(alibi_rows(sid, "guard")) == 1
      and len(redirects) == 1, "a second YouTube row within 120 s gives 0")

# FOCUS_GUARD unset or 0: nothing, even outside the window
clock.advance(70)
window(YT)
for off in (None, "0"):
    if off is None:
        os.environ.pop("FOCUS_GUARD", None)
    else:
        os.environ["FOCUS_GUARD"] = off
    check(nudges._guard(con, s, clock.t) is None and len(alibi_rows(sid, "guard")) == 1 and len(redirects) == 1,
          f"FOCUS_GUARD={off or 'unset'} gives 0 (read at call time)")
os.environ["FOCUS_GUARD"] = "1"

# max.com / linux.com: no strike
for url in ("https://max.com/shows", "https://www.linux.com/news", "https://notyoutube.com/"):
    window(url)
    check(nudges._guard(con, s, clock.t) is None, f"{url} gives 0")
check(len(alibi_rows(sid, "guard")) == 1 and len(redirects) == 1, "no guard events or redirects from them")

# a stale row (older than 2 x LAPTOP_EVERY_S) is no evidence
window(YT)
clock.advance(2 * config.LAPTOP_EVERY_S + 1)
check(nudges._guard(con, s, clock.t) is None, "a YouTube row older than 2 x LAPTOP_EVERY_S gives 0")

# strike 2, after 120 s: the second-time line, a strike event, a second redirect (youtu.be counts)
window("https://youtu.be/dQw4w9WgXcQ")
r = nudges._guard(con, s, clock.t)
check(r == f"You said drawing. YouTube can wait. {left(s)} min left. {nudges.SECOND}", f"repeat strike: {r!r}")
check(len(alibi_rows(sid, "strike")) == 1 and len(redirects) == 2 and redirects[-1] == ("Google Chrome", "youtu.be"),
      "strike event + second redirect")

# a browser the redirect can't drive (Arc): still a nudge, action none, no redirect
clock.advance(121)
window("https://www.reddit.com/r/all", app="Arc")
r = nudges._guard(con, s, clock.t)
g = alibi_rows(sid, "guard")
check(r and r.startswith("You said drawing. Reddit can wait.") and "Third time." in r
      and g[-1]["payload"]["action"] == "none" and len(redirects) == 2, f"Arc: nudge, no redirect: {r!r}")

# snooze and breaks silence it
clock.advance(121)
db.add_event(con, "user", "snooze", {"until": clock.t + 300}, session_id=sid, ts=clock.t)
window(YT)
check(nudges.check(con, s) is None and len(alibi_rows(sid, "guard")) == 3, "snoozed: 0")
clock.advance(301)
db.add_event(con, "user", "break", {"until": clock.t + 300, "min": 5}, session_id=sid, ts=clock.t)
window(YT)
check(nudges.check(con, s) is None and len(alibi_rows(sid, "guard")) == 3, "on a break: 0")
db.finish_session(con, sid)

# wired into the daemon tick: the laptop logger's row is acted on in the same tick (a screen session: no camera)
laptop_logger.frontmost = lambda: {"app": "Google Chrome", "title": "YouTube", "url": "https://m.youtube.com/"}
laptop_logger._last_log = 0.0
clock.advance(400)
sid2 = db.create_session(con, "cpp", "digital", 30)
daemon.tick(con)
g2 = alibi_rows(sid2, "guard")
check(len(g2) == 1 and redirects[-1] == ("Google Chrome", "m.youtube.com") and "You said C++. YouTube can wait."
      in nudge_alerts()[-1]["text"], "daemon.tick -> guard in one tick: " + nudge_alerts()[-1]["text"])
db.finish_session(con, sid2)

# the real _redirect, against a fake osascript: off with MAC_SIGNALS=0, only redirects a tab still on a guarded site
calls = []


def fake_run(cmd, **kw):
    calls.append(cmd)
    return types.SimpleNamespace(stdout=fake_run.url + "\n", returncode=0)


real_run, nudges.subprocess.run = nudges.subprocess.run, fake_run
os.environ["MAC_SIGNALS"] = "0"
check(real_redirect("Google Chrome", "www.youtube.com") is None and not calls, "MAC_SIGNALS=0: hands off the Mac")
os.environ["MAC_SIGNALS"] = "1"
check(real_redirect("Arc", "www.youtube.com") is None and not calls, "only Chrome and Safari are driven")
fake_run.url = YT
real_redirect("Google Chrome", "www.youtube.com").join(5)
check(len(calls) == 2 and calls[1][-2:] == [YT, nudges.FOCUS_URL + "?site=YouTube"]
      and "set URL of active tab" in calls[1][2], "still on YouTube: set the tab, guarded by that exact URL")
calls.clear()
fake_run.url = "https://www.google.com/search?q=pencils"
real_redirect("Safari", "www.youtube.com").join(5)
check(len(calls) == 1 and "front document" in calls[0][2], "moved on to another site: leave the tab alone")
os.environ["MAC_SIGNALS"] = "0"
nudges.subprocess.run = real_run

# the focus page is served where the redirect points, without an api.py change
c = TestClient(api.app)
page = c.get("/web/focus.html")
check(nudges.FOCUS_URL == f"http://127.0.0.1:{config.API_PORT}/web/focus.html" and page.status_code == 200
      and "Nothing's running." in page.text and "/api/state" in page.text, "focus page served at /web/focus.html")
print("PASS test_focus_guard")
