"""THE CONTRACT. Freeze after P0. Observers write `events`; the verifier reads them."""
import json, sqlite3, time
from . import config

DB_PATH = config.DATA_DIR / "alibi.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY,
  habit TEXT NOT NULL,
  modality TEXT NOT NULL CHECK (modality IN ('physical','digital','hybrid')),
  declared_min INTEGER NOT NULL,
  started_at REAL NOT NULL,
  ends_at REAL NOT NULL,
  ended_at REAL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','done')),
  on_task_ratio REAL,
  verdict TEXT CHECK (verdict IN ('done','partial','slacked')),
  evidence_path TEXT,
  artefact TEXT
);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY,
  ts REAL NOT NULL,
  source TEXT NOT NULL,      -- camera | laptop | phone | strava | health
  kind TEXT NOT NULL,        -- label | window | activity | focus | samples
  session_id INTEGER REFERENCES sessions(id),
  payload TEXT NOT NULL      -- JSON
);
CREATE INDEX IF NOT EXISTS ev_ts ON events(ts);
CREATE INDEX IF NOT EXISTS ev_session ON events(session_id);
CREATE TABLE IF NOT EXISTS title_cache(
  habit TEXT NOT NULL, title TEXT NOT NULL, label TEXT NOT NULL,
  PRIMARY KEY (habit, title)
);
"""

LABELS = ("on_task", "phone", "idle", "absent", "off_task")


def connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")   # daemon + CLI + logger can write concurrently
    con.executescript(SCHEMA)
    return con


def add_event(con, source: str, kind: str, payload: dict, session_id=None, ts=None) -> None:
    con.execute(
        "INSERT INTO events(ts, source, kind, session_id, payload) VALUES (?,?,?,?,?)",
        (ts or time.time(), source, kind, session_id, json.dumps(payload)),
    )
    con.commit()


def create_session(con, habit: str, modality: str, minutes: int) -> int:
    now = time.time()
    cur = con.execute(
        "INSERT INTO sessions(habit, modality, declared_min, started_at, ends_at) VALUES (?,?,?,?,?)",
        (habit, modality, minutes, now, now + minutes * 60),
    )
    con.commit()
    return cur.lastrowid


def active_session(con):
    return con.execute(
        "SELECT * FROM sessions WHERE status='active' ORDER BY id DESC LIMIT 1"
    ).fetchone()


def session_events(con, session_id: int, source: str | None = None):
    q = "SELECT * FROM events WHERE session_id=?"
    args = [session_id]
    if source:
        q += " AND source=?"
        args.append(source)
    return [dict(r, payload=json.loads(r["payload"])) for r in con.execute(q + " ORDER BY ts", args)]


def events_between(con, t0: float, t1: float, source: str):
    rows = con.execute(
        "SELECT * FROM events WHERE source=? AND ts BETWEEN ? AND ? ORDER BY ts", (source, t0, t1)
    )
    return [dict(r, payload=json.loads(r["payload"])) for r in rows]


def finish_session(con, session_id: int, **fields) -> None:
    fields.setdefault("ended_at", time.time())
    fields["status"] = "done"
    cols = ", ".join(f"{k}=?" for k in fields)
    con.execute(f"UPDATE sessions SET {cols} WHERE id=?", (*fields.values(), session_id))
    con.commit()


if __name__ == "__main__":
    connect()
    print("DB ready at", DB_PATH)
