"""Phone writes DoD: the phone can start and end a session over the tailnet. Same op_id twice (and racing) gives one answer and
one session; a stale session_id and a stale start get 409; ?key= gets 401; a LAN source gets 403."""
import threading, time
from harness import check
from fastapi.testclient import TestClient
from alibi import db, integrations, routes_phone

KEY = integrations.phone_secret()
H = {"X-Alibi-Secret": KEY}
app = integrations.phone_app()
ph = TestClient(app, client=("127.0.0.1", 50000))         # tailscale serve arrives as loopback
tail = TestClient(app, client=("100.101.102.103", 50000))  # the phone's tailnet address
lan = TestClient(app, client=("192.168.1.5", 1234))
con = db.connect()


def say(text, op, ts=None, c=ph, headers=H):
    return c.post("/api/phone/say", json={"op_id": op, "client_ts": ts or time.time(), "text": text}, headers=headers)


# capabilities on the existing read
r = ph.get("/api/phone/session", headers=H)
check(r.status_code == 200 and r.json()["capabilities"] == {"say": True, "end": True, "ask": False},
      "/api/phone/session advertises capabilities {say, end, ask:false}")

# --- security ---------------------------------------------------------------------------------------------------------
r = ph.post(f"/api/phone/say?key={KEY}", json={"op_id": "k1", "client_ts": time.time(), "text": "draw for 25"})
check(r.status_code == 401, "?key= on a write -> 401")
r = ph.post(f"/api/phone/say?key={KEY}", json={"op_id": "k1", "client_ts": time.time(), "text": "draw for 25"}, headers=H)
check(r.status_code == 401, "?key= is refused even with the header too")
check(say("draw for 25", "w0", headers={"X-Alibi-Secret": "nope"}).status_code == 401, "wrong header -> 401")
for ip in ("192.168.1.5", "10.0.0.7", "172.20.1.1"):
    r = TestClient(app, client=(ip, 1234)).post("/api/phone/say", json={"op_id": "l1", "client_ts": time.time(),
                                                                      "text": "draw for 25"}, headers=H)
    check(r.status_code == 403 and r.json()["error"] == "lan_refused", f"LAN source {ip} -> 403")
check(db.active_session(con) is None, "nothing started by any refused write")
r = ph.post("/api/phone/say", content=b'{"op_id":"big","client_ts":1,"text":"' + b"x" * 17000 + b'"}',
            headers={**H, "Content-Type": "application/json"})
check(r.status_code == 413, "body over 16 KB -> 413")

# --- stale start ------------------------------------------------------------------------------------------------------
r = say("draw for 25", "s-old", ts=time.time() - 300)
check(r.status_code == 409 and r.json()["error"] == "stale_start" and db.active_session(con) is None,
      "a start said 5 min ago -> 409 stale_start, no session")
r = say("how am I doing", "s-old-status", ts=time.time() - 300)
check(r.status_code == 200 and r.json()["ok"], "an old non-start (status) still answers")

# --- same op_id twice, including two racing threads -> one reply, one session ------------------------------------------
res = []
ts = time.time()
th = [threading.Thread(target=lambda: res.append(say("draw for 25", "op-start-1", ts=ts, c=tail))) for _ in range(2)]
[t.start() for t in th]
[t.join() for t in th]
check([x.status_code for x in res] == [200, 200], "both racing copies answer 200")
check(res[0].json() == res[1].json() and res[0].json()["reply"].startswith("Started"),
      f"racing copies get the same reply: {res[0].json()['reply']}")
n = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
check(n == 1, "exactly one session from the same op_id")
again = say("draw for 25", "op-start-1", ts=ts)
check(again.json() == res[0].json() and again.headers.get("x-alibi-replay") == "1", "a later retry replays the answer")
body = res[0].json()
check(body["ok"] and body["session"]["active"] and body["session"]["habit"], "response is {ok, reply, session}")
sid = body["session"]["session_id"]
check(any(o["k"] == "say:op-start-1" for o in integrations.state()["phone_ops"]), "op recorded in integrations.state()")

# --- end: stale session_id -> 409; a late end is back-dated -----------------------------------------------------------
s = db.get_session(con, sid)
con.execute("UPDATE sessions SET started_at=started_at-600 WHERE id=?", (sid,)); con.commit()
r = ph.post("/api/phone/session/end", json={"op_id": "e-wrong", "client_ts": time.time(), "session_id": sid + 99}, headers=H)
check(r.status_code == 409 and r.json()["error"] == "already_ended" and db.active_session(con), "wrong session_id -> 409, still live")
tap = time.time() - 120
r = ph.post("/api/phone/session/end", json={"op_id": "e1", "client_ts": tap, "session_id": sid}, headers=H)
check(r.status_code == 200 and r.json()["ok"] and not r.json()["session"]["active"], f"end over the tailnet: {r.json()['reply']}")
done = db.get_session(con, sid)
check(done["status"] == "done" and abs(done["ended_at"] - tap) < 1, "a 2-min-late end is back-dated to the tap")
r2 = ph.post("/api/phone/session/end", json={"op_id": "e1", "client_ts": tap, "session_id": sid}, headers=H)
check(r2.status_code == 200 and r2.json() == r.json(), "the same end op replays, no second verdict")
r3 = ph.post("/api/phone/session/end", json={"op_id": "e2", "client_ts": time.time(), "session_id": sid}, headers=H)
check(r3.status_code == 409 and r3.json()["error"] == "already_ended", "ending an ended session -> 409 already_ended")

# --- shape checks and rate limit --------------------------------------------------------------------------------------
check(ph.post("/api/phone/say", json={"client_ts": time.time(), "text": "x"}, headers=H).status_code == 400, "no op_id -> 400")
check(ph.post("/api/phone/say", json={"op_id": "x", "text": "x"}, headers=H).status_code == 400, "no client_ts -> 400")
routes_phone._writes.clear()
codes = [say("how am I doing", f"rl{i}").status_code for i in range(31)]
check(codes[:30] == [200] * 30 and codes[30] == 429, "30 writes a minute, the 31st -> 429")
check(len(integrations.state()["phone_ops"]) <= routes_phone.OPS_KEEP, "op log bounded")
print("PASS")
