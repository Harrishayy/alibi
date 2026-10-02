"""Laptop witness DoD: 3-min C++ session: 2 min VS Code + cppreference, 1 min YouTube -> ≈67% partial with title breakdown."""
import os
os.environ["LAPTOP_EVERY_S"] = "30"
from harness import Clock, check
from alibi import cli, daemon, db, laptop_logger, verifier

con = db.connect()
clock = Clock()
script = [({"app": "Visual Studio Code", "title": "main.cpp — learncpp", "url": ""}, 60),
          ({"app": "Google Chrome", "title": "std::vector - cppreference.com", "url": "https://en.cppreference.com"}, 60),
          ({"app": "Google Chrome", "title": "YouTube", "url": "https://youtube.com"}, 60)]
print(" ", cli.start(con, "learn C++ for 3 minutes"))
s0 = db.active_session(con)
for w, secs in script:
    for _ in range(secs // 5):
        laptop_logger.frontmost = lambda w=w: w
        daemon.tick(con); clock.advance(5)
daemon.tick(con)
s = con.execute("SELECT * FROM sessions WHERE id=?", (s0["id"],)).fetchone()
bd = verifier.window_breakdown(con, s)
for b in bd:
    print(f"    {b['share']:>4.0%}  {b['label']:<8} {b['title']}")
check(s["status"] == "done", "closed by timer")
check(s["verdict"] == "partial" and 0.6 <= s["on_task_ratio"] <= 0.72, f"≈67% partial (got {s['on_task_ratio']:.0%} {s['verdict']})")
check(any(b["label"] == "off_task" and "YouTube" in b["title"] for b in bd), "YouTube flagged off task")
check(con.execute("SELECT count(*) FROM title_cache WHERE habit='cpp'").fetchone()[0] == 3, "titles cached once each")
print("Laptop witness DoD passed.")
