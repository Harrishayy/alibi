"""Signals hardening: non-finite numbers never reach the DB or 500 the routes; a failing Focus shortcut backs off and
gives up (status says so); phone rows that arrive after the verdict re-run fusion and may only LOWER the score."""
import json, os, socket
from harness import Clock, check
os.environ["PHONE_HOST"] = "127.0.0.1"
s = socket.socket(); s.bind(("127.0.0.1", 0)); os.environ["PHONE_PORT"] = str(s.getsockname()[1]); s.close()
os.environ["ALIBI_FOCUS_SHORTCUTS"] = "1"                   # on, but every `shortcuts` call below is faked

from fastapi.testclient import TestClient
from alibi import api, cli, db, integrations, signals, verifier

clock = Clock()
con = db.connect()
CALLS, RC = [], {"Alibi Focus On": 0, "Alibi Focus Off": 0}


class P:
    def __init__(self, out="", rc=0): self.stdout, self.returncode = out, rc


def fake_shortcuts(*args, timeout=20):
    CALLS.append(args)
    if args[0] == "list":
        return P("Alibi Focus On\nAlibi Focus Off\n")
    return P(rc=RC[args[1]])
integrations._shortcuts = fake_shortcuts


def join_focus():
    for t in integrations._focus["threads"]:
        t.join(5)


ph = TestClient(integrations.phone_app())
H = {"X-Alibi-Secret": integrations.phone_secret(), "Content-Type": "application/json"}
web = TestClient(api.app)


def routes_ok(sid):
    urls = ["/api/signals/live", "/api/signals/status", "/api/signals", f"/api/signals?session={sid}"]
    for u in urls:
        r = web.get(u)
        if r.status_code != 200:
            return f"{u} -> {r.status_code}"
        json.loads(r.text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))   # strict JSON
    return None


# --- 1. Infinity / NaN / 1e400 -----------------------------------------------------------------------------------------
cli.start_habit(con, "cpp", 30)
sess = db.active_session(con)
join_focus()
t0 = sess["started_at"]
clock.advance(600)
raw = ('{"batch": ['
       '{"source":"phone","kind":"motion","payload":{"start":"inf","end":1e400,"state":"walking"}},'
       '{"source":"phone","kind":"motion","payload":{"start":"nan","end":"-inf","state":"running"}},'
       '{"source":"phone","kind":"pickup","ts":"inf","payload":{"ts":1e400}},'
       '{"source":"phone","kind":"pickup","payload":{"ts":"nan"}},'
       '{"source":"phone","kind":"screentime","payload":{"app":"X","minutes":1e400,"threshold_min":"nan"}},'
       '{"source":"phone","kind":"shield","payload":{"on":true,"apps":1e400}},'
       '{"source":"phone","kind":"custom_thing","payload":{"v":1e400,"w":[NaN, 2]}},'
       '{"source":"health","kind":"heart","payload":{"samples":[[1e400,70],["nan",71],[' + str(t0 + 60) + ',1e400]]}}'
       ']}')
r = ph.post("/ingest", headers=H, content=raw)
check(r.status_code == 200, f"non-finite batch accepted without a crash ({r.json().get('saved')} saved)")
bad = [x for (x,) in con.execute("SELECT payload FROM events WHERE source IN ('phone','health')")
       if "Infinity" in x or "NaN" in x]
check(not bad, f"no Infinity/NaN stored ({bad[:2]})")
lo, hi = clock.t - integrations.TS_PAST_S, clock.t + 300
for (p,) in con.execute("SELECT payload FROM events WHERE source='phone' AND kind IN ('motion','pickup')"):
    p = json.loads(p)
    vals = [p["start"], p["end"]] if "start" in p else [p["ts"]]
    check(all(lo <= v <= hi for v in vals), f"motion/pickup timestamps clamped to [now-7d, now+5min]: {p}")
st = json.loads(con.execute("SELECT payload FROM events WHERE kind='screentime'").fetchone()[0])
check(st["minutes"] == 0 and st["threshold_min"] == 5, f"screen time junk -> 0 min, 5 min step ({st})")
check(integrations._num(1e400) is None and integrations._num("9" * 400) is None and integrations._num("nan") is None
      and integrations._ts("inf") is None and integrations._ts(float("nan")) is None and integrations._ts(10 ** 400) is None,
      "_num/_ts reject inf, nan, 1e400 and 400-digit numbers")
check(routes_ok(sess["id"]) is None, f"every /api/signals* route still 200 ({routes_ok(sess['id'])})")

# a bad row already in the DB (written before this fix) can't 500 the routes either
db.add_event(con, "phone", "motion", {"start": clock.t - 60, "end": float("inf"), "state": "walking"},
             session_id=sess["id"], ts=clock.t - 30)
db.add_event(con, "phone", "pickup", {"ts": float("inf")}, session_id=sess["id"], ts=clock.t - 20)
db.add_event(con, "mac", "presence", {"idle_s": float("nan")}, session_id=sess["id"], ts=clock.t - 10)
db.add_event(con, "phone", "screentime", {"app": "Y", "minutes": float("inf")}, session_id=sess["id"], ts=clock.t - 5)
check(routes_ok(sess["id"]) is None, f"legacy Infinity/NaN rows: routes still 200 ({routes_ok(sess['id'])})")
check(signals._f(float("inf"), 3.0) == 3.0 and signals._f("nan", 1.0) == 1.0 and signals._f("1e999", 2.0) == 2.0,
      "signals._f falls back to the default for non-finite values")
con.execute("DELETE FROM events WHERE source IN ('phone','health','mac')")
con.commit()

# --- 2. a failing 'Alibi Focus Off' backs off, then gives up, and status says so --------------------------------------
cli.end(con)
join_focus()
RC["Alibi Focus Off"] = 1
integrations.set_state(mac_focus_on=True, mac_focus_fail={})
CALLS.clear()
runs = lambda: sum(1 for c in CALLS if c[:2] == ("run", "Alibi Focus Off"))
for _ in range(20):                                       # 20 daemon ticks, 5 s apart
    integrations.tick(con, clock.t)
    join_focus()
    clock.advance(5)
check(runs() <= 3, f"20 ticks with a broken Off shortcut -> {runs()} runs, not 20 (backoff)")
check(len(integrations._focus["threads"]) <= 1, "only the latest Focus thread is kept")
for _ in range(400):                                      # ~2 h of ticks
    integrations.tick(con, clock.t)
    join_focus()
    clock.advance(20)
check(runs() == integrations.FOCUS_MAX_FAILS, f"gives up after {integrations.FOCUS_MAX_FAILS} failures ({runs()} runs)")
row = next(x for x in signals.status(con)["sources"] if x["key"] == "mac.focus_shortcuts")
check(row["state"] == "stale" and not row["flowing"] and "Alibi Focus Off shortcut failed" in row["text"]
      and "stopped retrying" in row["text"] and row["fix"], f"status: {row['text']}")
RC["Alibi Focus Off"] = 0
check(integrations.set_mac_focus(False, wait=True) and not integrations.state().get("mac_focus_on"),
      "an explicit session-end attempt still runs, and a success turns it off")
check(integrations.focus_problem() is None, "a success clears the failure count")
row = next(x for x in signals.status(con)["sources"] if x["key"] == "mac.focus_shortcuts")
check(row["state"] == "ok", "status back to ok")
RC["Alibi Focus On"] = 1                                  # busy: no second run while one is in flight
import threading
gate = threading.Event()
integrations._shortcuts = lambda *a, timeout=20: (CALLS.append(a), gate.wait(5), P(rc=0))[2] if a[0] == "run" \
    else fake_shortcuts(*a)
CALLS.clear()
check(integrations.set_mac_focus(True) is True and integrations.set_mac_focus(True) is False,
      "a second Focus run is skipped while one is still running")
gate.set(); join_focus()
integrations._shortcuts = fake_shortcuts
RC["Alibi Focus On"] = 0
integrations.set_state(mac_focus_on=False)

# --- 3. phone rows after the verdict lower the score (never raise) ---------------------------------------------------
clock.advance(3600)
cli.start_habit(con, "cpp", 30)
sess = db.active_session(con)
join_focus()
t0 = sess["started_at"]
for i in range(60):
    db.add_event(con, "laptop", "window", {"app": "Cursor", "title": "main.cpp — learncpp"}, ts=t0 + i * 30 + 1)
clock.advance(30 * 60 + 2)
cli.end(con)
join_focus()
done = db.get_session(con, sess["id"])
check(done["verdict"] == "done" and done["on_task_ratio"] >= 0.95, f"session done first: {done['on_task_ratio']:.0%}")
clock.advance(240)                                        # the phone syncs four minutes later
r = ph.post("/ingest", headers=H, json={"source": "phone", "kind": "pickup", "ts": t0 + 100, "payload": {}})
check(r.status_code == 200 and "rescored" not in r.json()
      and db.get_session(con, sess["id"])["on_task_ratio"] == done["on_task_ratio"], "a lone pickup doesn't move it")
batch = [{"source": "phone", "kind": "screentime", "ts": t0 + 300 * k, "payload": {"app": "Instagram", "minutes": 5 * k}}
         for k in range(1, 5)]
r = ph.post("/ingest", headers=H, json={"batch": batch}).json()
late = db.get_session(con, sess["id"])
check(r.get("rescored") and late["on_task_ratio"] < done["on_task_ratio"] and late["verdict"] != "done",
      f"late Screen Time lowered it: {done['on_task_ratio']:.0%} done -> {late['on_task_ratio']:.0%} {late['verdict']}")
cap = signals.last_cap(con, sess["id"])
check(cap and cap.get("late") and "Instagram" in cap["reason"] and cap["verdict_was"] == "done",
      f"signals_cap recorded with late=true: {cap and cap['reason']}")
sig = web.get(f"/api/signals?session={sess['id']}").json()
check((sig.get("cap") or {}).get("late") is True, "GET /api/signals?session=N shows the late cap")
r = ph.post("/ingest", headers=H, json={"batch": batch}).json()
check(not r.get("rescored") and db.get_session(con, sess["id"])["on_task_ratio"] == late["on_task_ratio"],
      "re-sending the same rows changes nothing")
before = late["on_task_ratio"]
check(verifier.refuse_late(con, sess["id"]) is None and db.get_session(con, sess["id"])["on_task_ratio"] == before,
      "re-fusion never raises the score")
clock.advance(verifier.LATE_WINDOW_S + 60)
r = ph.post("/ingest", headers=H, json={"source": "phone", "kind": "screentime", "ts": t0 + 1700,
                                        "payload": {"app": "TikTok", "minutes": 25}}).json()
check(not r.get("rescored"), "a session older than the late window is left alone")
print("Signals hardening DoD passed.")
