"""P9 DoD: PUT a new habit from the dashboard API -> intent recognises it; health lists every check."""
from harness import check
from fastapi.testclient import TestClient
from alibi import api, config, intent

c = TestClient(api.app)
h = c.get("/api/health").json()
for x in h["checks"]:
    print(f"    {'ok ' if x['ok'] else 'fix'}  {x['label']:<16} {x['detail']}" + (f"  → {x['fix']}" if x["fix"] else ""))
check({x["key"] for x in h["checks"]} == {"camera", "windows", "witness", "text", "strava", "island"}, "every check present")
habits = c.get("/api/habits").json()["habits"]
habits["guitar"] = {"modality": "physical", "aliases": "guitar, practice scales", "weekly_target_min": 120,
                    "default_min": 20, "on_task_looks_like": "hands on a guitar"}
r = c.put("/api/habits", json={"habits": habits})
check(r.status_code == 200, "habits saved")
check(intent.parse("practice scales for 20 min") == {"habit": "guitar", "minutes": 20, "modality": "physical"},
      "new habit recognised by the parser")
check(c.put("/api/habits", json={"habits": {"Bad Name!": {"modality": "physical"}}}).status_code == 400, "bad name rejected")
check(c.put("/api/habits", json={"habits": {"x": {"modality": "telepathy"}}}).status_code == 400, "bad modality rejected")
check(str(config.HABITS_PATH) != str(config.ROOT / "habits.yaml"), "test never touched the real habits.yaml")
print("P9 DoD passed.")
