"""P0 DoD: start "draw for 2 minutes" with the daemon ticking -> 2 min later a notification fires, no active session."""
from harness import Clock, check
from alibi import cli, daemon, db, intent, notify

con = db.connect()
clock = Clock()

for text, want in [("draw for 2 minutes", ("drawing", 2)), ("work on iggy for 45 minutes", ("building", 45)),
                   ("learn C++ for half an hour", ("cpp", 30)), ("maths for 1h 30m", ("math", 90)),
                   ("apply to internships for an hour", ("internships", 60))]:
    it = intent.parse(text)
    check((it["habit"], it["minutes"]) == want, f"intent {text!r} -> {it}")

print(" ", cli.start(con, "draw for 2 minutes"))
check(db.active_session(con) is not None, "session active after start")
check("drawing" in cli.status(con), "status shows drawing")
for _ in range(23):                        # 23 ticks x 5 s = 115 s
    clock.advance(5); daemon.tick(con)
check(db.active_session(con) is not None, "still active at 1:55")
clock.advance(10); daemon.tick(con)
check(db.active_session(con) is None, "no active session after 2:05")
check(any("Time's up" in a["text"] for a in notify.recent_alerts()), "notification fired")
print("P0 DoD passed.")
