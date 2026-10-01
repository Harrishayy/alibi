"""F5 DoD (NEXT_PHASE §3): digest slots, checkpoint suppression and deltas, the night replan tool loop against a local
stub (scripted tool_calls; invalid slot, no tools and server down all fall back to rules), accept -> add_once, and the
morning memory callback ("22 of 25"), undo, and the replan trace totals (turns, total_ms, per-step result). Fake clock, no network beyond 127.0.0.1."""
import os
os.environ["DIGESTS"] = "1"
import datetime as dt, json, socket, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from harness import ROOT, Clock, check
import yaml
from fastapi.testclient import TestClient
from alibi import api, calendar_sync, config, daemon, db, digest, notify

D = dt.date(2026, 10, 5)                                         # a Monday
T1, T2 = (D + dt.timedelta(days=1)).isoformat(), (D + dt.timedelta(days=2)).isoformat()


def at(day: int, h: int, m: int = 0) -> float:
    return dt.datetime.combine(D + dt.timedelta(days=day), dt.time(h, m)).timestamp()


yaml.safe_dump({"habits": {
    "drawing": {"modality": "physical", "default_min": 25, "weekly_target_min": 210},
    "building": {"modality": "physical", "default_min": 30, "weekly_target_min": 30,
                 "schedule": [{"days": list(config.DAYS), "at": "07:00", "min": 30}]}},
    "verdict": {"done": 0.7, "partial": 0.4}}, open(config.HABITS_PATH, "w"))
con = db.connect()


def sess(habit, start, minutes, ratio, verdict):
    con.execute("INSERT INTO sessions(habit,modality,declared_min,started_at,ends_at,ended_at,status,on_task_ratio,"
                "verdict) VALUES (?,'physical',?,?,?,?,'done',?,?)",
                (habit, minutes, start, start + minutes * 60, start + minutes * 60, ratio, verdict))
    con.commit()


def n_alerts(kind):
    return sum(a.get("kind") == kind for a in notify.recent_alerts(1000))


clock = Clock()
c = TestClient(api.app)

# --- slots: 07:30 writes one morning row, a second tick none ------------------------------------------------------------
sess("building", at(0, 7), 30, 1.0, "done")
clock.t = at(0, 7, 30)
daemon.tick(con); clock.advance(5); daemon.tick(con)
mornings = digest.rows(50, "morning")
check(len(mornings) == 1 and mornings[0]["slot"] == "2026-10-05-morning", "07:30 tick writes exactly one morning row")
m = mornings[0]
check("Drawing needs" in m["text"] and "First free gap:" in m["text"] and "!" not in m["text"],
      f"morning: need today and first free gap, no '!' ({m['text']!r})")
check(m["json"]["blocks"] and m["json"]["blocks"][0]["habit"] == "building", "morning lists today's blocks")

# --- 12:00 with nothing new: stored sent:false, no notification ---------------------------------------------------------
before = n_alerts("digest")
clock.t = at(0, 12)
daemon.tick(con)
r12 = digest.latest()
check(r12["slot"] == "2026-10-05-checkpoint-12" and r12["sent"] is False and r12["json"]["changes"] == [],
      f"12:00 no change -> stored with sent:false ({r12['slot']}, {r12['json']['changes']})")
check(n_alerts("digest") == before, "12:00 no change -> no notification")
clock.advance(5); daemon.tick(con)
check(len(digest.rows(50, "checkpoint")) == 1, "the 12:00 slot runs once")

# --- a session between 12 and 16 -> the 16:00 slot has the delta --------------------------------------------------------
sess("drawing", at(0, 13), 25, 0.8, "done")
clock.t = at(0, 16)
daemon.tick(con)
r16 = digest.latest()
ch = {(x["habit"], x["field"]): (x["from"], x["to"]) for x in r16["json"]["changes"]}
check(r16["slot"] == "2026-10-05-checkpoint-16" and ch.get(("drawing", "verified_min")) == (0, 20)
      and ch.get(("drawing", "done")) == (0, 1), f"16:00 delta: drawing 0 -> 20 min, one done ({ch})")
check(r16["sent"] is True and n_alerts("digest") == before + 1 and "+20 min" in r16["text"],
      f"16:00 is sent ({r16['text']!r})")

# --- wake after a sleep: only the most recent missed slot runs ----------------------------------------------------------
clock.t = at(0, 21, 10)                                          # asleep through 20:00
daemon.tick(con)
check([r["slot"] for r in digest.rows(50, "checkpoint")][:1] == ["2026-10-05-checkpoint-20"]
      and len(digest.rows(50, "checkpoint")) == 3, "on wake, the one missed slot (20:00) runs once")

# --- the replan tool loop against a local stub ---------------------------------------------------------------------------
SCRIPT, SEEN = [], []


def call(name, **args):
    return {"id": f"c{time.perf_counter_ns()}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class Stub(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        step = SCRIPT.pop(0) if SCRIPT else {"content": "I can't help with that."}
        msg = {"role": "assistant", "content": step.get("content"), **({"tool_calls": step["tools"]} if "tools" in step else {})}
        out = json.dumps({"id": "x", "object": "chat.completion", "created": 0, "model": "stub",
                          "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if "tools" in step else "stop"}],
                          "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=srv.serve_forever, daemon=True).start()
STUB = f"http://127.0.0.1:{srv.server_port}/v1"


def script(propose_at):
    SCRIPT[:] = [{"tools": [call("week_status")]},
                 {"tools": [call("plan", day=T1), call("free_gaps", day=T1, min_minutes=25)]},
                 {"tools": [call("propose", habit="drawing", day=T1, at=propose_at, minutes=25,
                                 why="Furthest behind; 07:30 is free after building.")]}]


clock.t = at(0, 22)
script("07:30")
p, trace, via = digest.replan(con, clock.t, use_llm=True, base_url=STUB, model="stub")
check(len(trace) >= 3 and [t["tool"] for t in trace][:3] == ["week_status", "plan", "free_gaps"],
      f"tool loop: trace has ≥3 real steps ({[t['tool'] for t in trace]})")
check(SEEN and SEEN[0].get("tools") and len(SEEN) == 3, "the model saw the tools, three turns")
check(via == "llm:spark" and p and (p["habit"], p["day"], p["at"], p["minutes"]) == ("drawing", T1, "07:30", 25)
      and digest.validate(con, p, clock.t)[0], f"the model's proposal validates, via llm:spark ({p})")

# trace totals: turns made, wall time, one short plain result per step
rp = (script("07:30"), digest._replan(con, clock.t, use_llm=True, base_url=STUB, model="stub"))[1]
res = {t["tool"]: t.get("result") for t in rp["trace"]}
check(rp["turns"] == 3 and isinstance(rp["total_ms"], int) and rp["total_ms"] >= 0
      and all(isinstance(t.get("result"), str) and 0 < len(t["result"]) <= 60 for t in rp["trace"]),
      f"stub loop: turns 3, total_ms, a result on every step ({rp['turns']}, {rp['total_ms']} ms)")
check(res["week_status"] == "drawing 0 d behind most" and res["plan"] == "1 block tomorrow"
      and res["free_gaps"].startswith("07:30–") and res["propose"] == "valid", f"step results read plainly ({res})")
rr = digest._replan(con, clock.t, use_llm=False)
check(rr["turns"] == 0 and isinstance(rr["total_ms"], int) and [t["tool"] for t in rr["trace"]] == ["rules picker"]
      and rr["trace"][0]["result"] == "drawing tomorrow 07:30, 25 min" and isinstance(rr["trace"][0]["ms"], int),
      f"rules fallback: turns 0, total_ms, one 'rules picker' step ({rr['trace']})")

script("07:00")                                                  # overlaps tomorrow's 07:00 building block
p, trace, via = digest.replan(con, clock.t, use_llm=True, base_url=STUB, model="stub")
err = next((t.get("error") for t in trace if t.get("error")), None)
check(via == "rules" and p and p["via"] == "rules" and p["at"] == "07:30" and err and trace[-1]["tool"] == "rules picker",
      f"an invalid slot is dropped -> rules picker ({p and p['at']}, {err})")

SCRIPT[:] = [{"content": "Draw tomorrow morning."}]
p, trace, via = digest.replan(con, clock.t, use_llm=True, base_url=STUB, model="stub")
check(via == "rules" and p and p["habit"] == "drawing", "no tool calls -> rules")

s = socket.socket(); s.bind(("127.0.0.1", 0)); dead = s.getsockname()[1]; s.close()
t0 = time.monotonic()
p, trace, via = digest.replan(con, clock.t, use_llm=True, base_url=f"http://127.0.0.1:{dead}/v1", model="stub")
check(via == "rules" and p and time.monotonic() - t0 < 2, f"stub down -> rules in {time.monotonic() - t0:.2f} s")

# --- the night slot is the nightly report: one notification, rules here (no model) --------------------------------------
reports = n_alerts("report")
daemon.tick(con); clock.advance(5); daemon.tick(con)
night = digest.get("2026-10-05-night")
check(night and n_alerts("report") == reports + 1, "22:00: one night digest, one report notification")
rep = notify.last_alert("report")
check(rep["text"] == night["text"] and rep.get("slot") == night["slot"], "the report's text is the night digest's")
check(night["via"] == "rules" and night["proposal"]["at"] == "07:30" and "Move drawing to tomorrow 07:30, 25 min?"
      in night["text"], f"night proposal via rules ({night['text']!r})")
check("Day closed." in night["text"] and "Buffer:" in night["text"], "night: lists and buffers")

# the same night through the API with a model on (the demo beat), via llm:spark, then accepted
config.TEXT_READY, config.LLM_BASE_URL, config.LLM_MODEL = True, STUB, "stub"
script("07:30")
row = c.post("/api/digests/run", json={"kind": "night"}).json()
config.TEXT_READY, config.LLM_BASE_URL, config.LLM_MODEL = False, "http://127.0.0.1:9/v1", ""
check(row["slot"] == "2026-10-05-night-2" and row["via"] == "llm:spark" and len(row["trace"]) >= 3,
      f"run night via API: llm:spark with a trace, scheduled row kept ({row['slot']})")
check(c.get("/api/digests/latest").json()["slot"] == row["slot"] and
      len(c.get("/api/digests", params={"limit": 3}).json()["digests"]) == 3, "GET /api/digests and /latest")
check(not any(b["habit"] == "drawing" for b in calendar_sync.plan(con, D + dt.timedelta(days=1), 1, clock.t)),
      "nothing is applied before accept")
a = c.post(f"/api/digests/{row['slot']}/accept").json()
plan1 = calendar_sync.plan(con, D + dt.timedelta(days=1), 1, clock.t)
check(a["ok"] and "07:30" in a["reply"] and any(b["habit"] == "drawing" and b["at"] == "07:30" and b["min"] == 25
                                                for b in plan1), f"accept -> plan(tomorrow) shows it ({a['reply']!r})")
check(digest.get(row["slot"])["accepted_at"] and c.post(f"/api/digests/{row['slot']}/accept").json().get("already"),
      "accepted_at stored; accepting twice is a no-op")
check(c.post("/api/digests/nope/accept").status_code == 404, "unknown slot -> 404")
check(row.get("turns") == 3 and isinstance(row.get("total_ms"), int) and all("result" in t for t in row["trace"]),
      "the stored night row carries turns, total_ms and step results")

# undo: the block leaves plan(tomorrow), accepted_at clears, a second undo is a 409, re-accept works
u = c.post(f"/api/digests/{row['slot']}/undo")
check(u.status_code == 200 and u.json() == {"ok": True, "reply": "Removed drawing from tomorrow 07:30."},
      f"undo -> {u.json()}")
check(not any(b["habit"] == "drawing" for b in calendar_sync.plan(con, D + dt.timedelta(days=1), 1, clock.t))
      and not digest.get(row["slot"])["accepted_at"], "undo: gone from plan(tomorrow), accepted_at cleared")
u2 = c.post(f"/api/digests/{row['slot']}/undo")
check(u2.status_code == 409 and u2.json()["ok"] is False, "undo when not accepted -> 409, ok:false")
check(c.post("/api/digests/nope/undo").status_code == 404, "undo unknown slot -> 404")
check(digest.memory(con, at(1, 7, 30)) is None, "an undone proposal is never remembered")
a = c.post(f"/api/digests/{row['slot']}/accept").json()
check(a["ok"] and not a.get("already") and any(b["habit"] == "drawing" and b["at"] == "07:30" for b in
                                               calendar_sync.plan(con, D + dt.timedelta(days=1), 1, clock.t)),
      "re-accept after undo puts it back")
(ROOT / "tests" / "fixtures").mkdir(exist_ok=True)
(ROOT / "tests" / "fixtures" / "digest_night.json").write_text(json.dumps(digest.get(row["slot"]), indent=1))

# --- memory: the next mornings remember ----------------------------------------------------------------------------------
clock.t = at(1, 7, 30)
m1 = digest.run("morning", clock.t)
check(m1["text"].startswith("Last night you moved drawing to 07:30.") and m1["json"]["memory"]["state"] == "now"
      and "Drawing 07:30 (25 min)" in m1["text"], f"the morning of: it's on now ({m1['text'].splitlines()[0]!r})")
check("It's on today's plan." in digest.run("morning", at(1, 7, 0))["text"], "earlier that morning: on today's plan")
sess("drawing", at(1, 7, 31), 22, 1.0, "done")
clock.t = at(2, 7, 30)
m2 = digest.run("morning", clock.t)
check("22 of 25" in m2["text"] and m2["json"]["memory"]["state"] == "kept",
      f"next morning remembers: {m2['text'].splitlines()[0]!r}")
con.execute("DELETE FROM sessions WHERE started_at=?", (at(1, 7, 31),)); con.commit()
check("You didn't make it." in digest.run("morning", clock.t)["text"], "no session -> \"You didn't make it.\"")
srv.shutdown()
daemon.join_reels()                                              # the 22:00 recap thread
print("Digest DoD passed.")
