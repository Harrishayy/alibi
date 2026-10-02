"""Phone ingest DoD: phone Focus + Health samples POST /ingest with a shared secret -> events."""
import os
os.environ["INGEST_SECRET"] = "s3cret"
from harness import check
from fastapi.testclient import TestClient
from alibi import api, db

c = TestClient(api.app)
check(c.post("/ingest", json={"source": "phone", "kind": "focus", "payload": {"on": True}}).status_code == 401, "no secret -> 401")
h = {"X-Alibi-Secret": "s3cret"}
check(c.post("/ingest", headers=h, json={"source": "phone", "kind": "focus", "payload": {"focus": "Work", "on": True}}).json()["ok"], "focus event stored")
check(c.post("/ingest", headers=h, json={"source": "health", "kind": "samples", "payload": {"steps": 8412, "sleep_h": 6.6}}).json()["ok"], "health samples stored")
check(c.post("/ingest", headers=h, json={"source": "camera", "kind": "label"}).status_code == 400, "can't forge camera evidence")
n = db.connect().execute("SELECT count(*) FROM events WHERE source IN ('phone','health')").fetchone()[0]
check(n == 2, "2 events in the store")
print("Phone ingest DoD passed.")
