"""Mesh fixes (iPhone <-> Mac <-> Spark): pushes go only where NTFY_TOPIC points, as ntfy JSON, and only for the kinds
worth a buzz; the claw's brief is pushed under its own title; the claw sees when the phone really last synced; an open
run claim polls Strava every 30 s instead of every 30 min; a phone Shortcut naming an app nudges at once. Loopback only:
the fake ntfy runs on 127.0.0.1."""
import contextlib, io, json, http.server, threading, time, types
from harness import check, Clock
from alibi import config, db, integrations, notify, nudges, routes_agent, signals, strava

# --- phone push: a fake ntfy on loopback ------------------------------------------------------------------------------
got = []


class Ntfy(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        got.append({"path": self.path, "title_header": self.headers.get("Title"), "ctype": self.headers.get("Content-Type"),
                    "raw": raw, "json": json.loads(raw.decode("utf-8"))})
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *a):
        pass


def sent(fn) -> dict | None:
    """Run one push; the request the fake ntfy got for it, or None if nothing went out."""
    n = len(got)
    t = fn()
    if t is None:
        return None
    t.join(5)
    return got[-1] if len(got) > n else None


srv = http.server.HTTPServer(("127.0.0.1", 0), Ntfy)
threading.Thread(target=srv.serve_forever, daemon=True).start()

check(notify.push("x", "nudge", {}) is None, "push: off without NTFY_TOPIC (the harness clears it)")
check(not any(r["where"] == "ntfy" for r in signals.egress()["rows"]), "egress: no push row while it's off")
config.NTFY_URL, config.NTFY_TOPIC = f"http://127.0.0.1:{srv.server_port}", "alibi-test-topic"

r = sent(lambda: notify.push("You said drawing. Your phone just opened YouTube.", "nudge", {"habit": "drawing"}))
check(r and r["path"] == "/" and r["ctype"] == "application/json" and r["json"] == {
    "topic": "alibi-test-topic", "title": "Alibi", "message": "You said drawing. Your phone just opened YouTube.",
    "priority": 5, "tags": ["rotating_light"]}, f"push: a nudge is ntfy JSON at the root, urgent (5): {r and r['json']}")
check(r["title_header"] is None, "push: no Title header (it would go out as latin-1)")
for kind, tag in (("verdict", "white_check_mark"), ("digest", "memo"), ("report", "crescent_moon"),
                  ("planned", "alarm_clock")):
    r = sent(lambda: notify.push("x", kind, {}))
    check(r and r["json"]["priority"] == 3 and r["json"]["tags"] == [tag] and r["json"]["title"] == "Alibi",
          f"push: {kind} is a normal buzz (3, {tag})")
for kind, extra in (("synced", {}), ("recap", {}), ("pace", {}), ("info", {}), ("info", {"source": "strava"}),
                    ("info", {"source": "nemoclaw"})):
    check(notify.push("Strava: Morning Run, 5.2 km — logged.", kind, extra) is None,
          f"push: {kind}{f' {extra}' if extra else ''} stays on the Mac (kind decides, never source)")
row = next((r for r in signals.egress()["rows"] if r["where"] == "ntfy"), None)
check(row and row["host"] == "127.0.0.1" and "ntfy" in row["why"], "egress: the push row says where alerts go")

# --- the claw's brief on the phone, under its own title -----------------------------------------------------------------
r = sent(lambda: notify.push("Alibi test. Your agent can reach this phone.", "digest", {"source": "nemoclaw"}))
check(r and r["json"]["title"] == "Alibi · your agent" and r["json"]["priority"] == 3,
      "brief: a NemoClaw digest is titled 'Alibi · your agent'")
check(b"\xb7" not in r["raw"].replace(b"\xc2\xb7", b""), "brief: the middle dot is never a bare latin-1 byte on the wire")
n0, p0 = len(notify.recent_alerts(500)), len(got)
notify.notify("Drawing is 30 min behind this week. 19:00 is free tonight.", kind="brief", habit_label="Your agent",
              via="nemoclaw", slot="2026-10-02-night")
for _ in range(100):
    if len(got) > p0:
        break
    time.sleep(0.05)
new = notify.recent_alerts(500)[n0:]
check(len(new) == 1 and new[0]["kind"] == "brief" and len(got) == p0 + 1 and got[-1]["json"]["title"] == "Alibi · your agent"
      and got[-1]["json"]["priority"] == 3, "brief: post_brief's alert (kind brief, via nemoclaw) lands and is pushed once")

# --- requests.post itself: JSON body, no Title header -------------------------------------------------------------------
import requests
real_post, calls = requests.post, []
requests.post = lambda url, **kw: calls.append((url, kw)) or types.SimpleNamespace(raise_for_status=lambda: None)
notify.push("You said drawing. Your phone just opened YouTube.", "nudge", {}).join(5)
notify.push("Your agent says hi.", "brief", {"via": "nemoclaw"}).join(5)
requests.post = real_post
(u1, k1), (u2, k2) = calls
check(u1 == config.NTFY_URL and k1["json"]["priority"] == 5 and "data" not in k1 and
      "Title" not in (k1.get("headers") or {}) and k1["timeout"] == 5, "requests.post: json= at the root, priority 5, 5 s timeout")
check(k2["json"]["title"] == "Alibi · your agent" and "Title" not in (k2.get("headers") or {}),
      "requests.post: the agent title rides in the JSON body")

# --- a failed push says so, by exception type only, and never raises ----------------------------------------------------
config.NTFY_URL = "http://127.0.0.1:9"                       # discard port: refused
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    notify.push("x", "nudge", {}).join(8)
check("phone push failed: ConnectionError" in buf.getvalue() and "alibi-test-topic" not in buf.getvalue(),
      f"push failure: one line, no topic ({buf.getvalue().strip()})")
config.NTFY_URL = f"http://127.0.0.1:{srv.server_port}"
clock = Clock()

# --- the claw sees when the phone really last synced ------------------------------------------------------------------
integrations.set_state(phone_last_polled=clock.t - 86400, phone_last_received=clock.t - 600)
check(routes_agent.context(clock.t)["today"]["phone_last_synced"] == time.strftime("%H:%M", time.localtime(clock.t - 600)),
      "context: a batch from the phone counts, not only foreground polls")
integrations.set_state(phone_last_received=None)
check(routes_agent.context(clock.t)["today"]["phone_last_synced"] ==
      time.strftime("%a %H:%M", time.localtime(clock.t - 86400)), "context: an older sync carries its weekday")

# --- an open run claim polls Strava every 30 s -------------------------------------------------------------------------
con = db.connect()
calls = []
strava.connected = lambda: True
strava.state = lambda: {}
integrations.strava_sync_now = lambda: calls.append(1) or {"ok": True}
integrations._strava_last_try = clock.t - 40
check(integrations._maybe_strava(clock.t, con=con) is None, "strava: no open claim -> the 30-min cadence holds")
db.add_event(con, "user", "claim", {"habit": "running", "min_km": 5, "until": clock.t + 3600})
th = integrations._maybe_strava(clock.t, con=con)
th and th.join(2)
check(th is not None and calls == [1], "strava: an open run claim polls 30 s after the last try")
check(integrations._maybe_strava(clock.t + 10, con=con) is None, "strava: and not faster than that")

# --- a phone Shortcut naming an app nudges at once ---------------------------------------------------------------------
from alibi import cli
cli.start(con, "draw for 25 minutes")
s = db.active_session(con)
check(signals.nudge_reason(con, s, 0, clock.t + 1) is None, "phone app: nothing yet -> no nudge")
db.add_event(con, "phone", "app", {"opened": True, "reason": "foreground"}, session_id=s["id"], ts=clock.t + 2)
check(signals.nudge_reason(con, s, 0, clock.t + 3) is None, "phone app: Alibi's own foreground row isn't drift")
db.add_event(con, "phone", "app", {"opened": True, "reason": "You{Tube}"}, session_id=s["id"], ts=clock.t + 4)
r = signals.nudge_reason(con, s, 0, clock.t + 5)
check(r and r[0] == "phone" and r[1].format(habit="drawing") == "You said drawing. Your phone just opened YouTube.",
      f"phone app: a named app nudges at once, braces stripped ({r and r[1]})")
check(signals.nudge_reason(con, s, clock.t + 4.5, clock.t + 6) is None, "phone app: counted once, not again after the nudge")
clock.t += 5
n0, p0 = len(notify.recent_alerts(500)), len(got)
nudges.check(con, s)
for _ in range(100):
    if len(got) > p0:
        break
    time.sleep(0.05)
a = [x for x in notify.recent_alerts(500)[n0:] if x["kind"] == "nudge"]
check(len(a) == 1 and a[0]["label"] == "phone" and a[0]["text"] == "You said drawing. Your phone just opened YouTube.",
      f"phone app: the island nudge names the app ({a and a[0]['text']})")
check(len(got) == p0 + 1 and got[-1]["json"]["priority"] == 5 and got[-1]["json"]["message"] == a[0]["text"],
      "phone app: and the phone gets it as the urgent push")
srv.shutdown()
print("Mesh fixes DoD passed.")
