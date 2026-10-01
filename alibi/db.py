"""THE CONTRACT. Freeze after P0. Observers write `events`; the verifier reads them."""
import json, sqlite3, threading, time
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


_write_lock = threading.RLock()     # FastAPI runs sync endpoints in a thread pool; serialise session state changes


def create_session(con, habit: str, modality: str, minutes: int) -> int | None:
    """Atomic: inserts only if no session is active (R2). Returns the new id, or None if one is already live."""
    now = time.time()
    with _write_lock:
        con.commit()
        con.execute("BEGIN IMMEDIATE")
        try:
            cur = con.execute(
                "INSERT INTO sessions(habit, modality, declared_min, started_at, ends_at) SELECT ?,?,?,?,? "
                "WHERE NOT EXISTS (SELECT 1 FROM sessions WHERE status='active')",
                (habit, modality, int(minutes), now, now + int(minutes) * 60),
            )
            con.commit()
        except Exception:
            con.rollback()
            raise
    return cur.lastrowid if cur.rowcount == 1 else None


def claim_session(con, session_id: int, ended_at: float) -> bool:
    """Atomic close (R3): exactly one caller (CLI end, API end, or the bell) wins; the rest get False."""
    with _write_lock:
        cur = con.execute("UPDATE sessions SET status='done', ended_at=? WHERE id=? AND status='active'",
                          (ended_at, session_id))
        con.commit()
    return cur.rowcount == 1


def get_session(con, session_id: int):
    return con.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()


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


def user_events(con, session_id: int, kind: str | None = None) -> list[dict]:
    return [e for e in session_events(con, session_id, "user") if kind is None or e["kind"] == kind]


def breaks(con, session_id: int, now: float | None = None) -> list[tuple[float, float]]:
    """Break windows [(start, end)] from user 'break' events, cut short by a later 'resume'. No schema change."""
    now = now or time.time()
    ev = session_events(con, session_id, "user")
    out = []
    for i, e in enumerate(ev):
        if e["kind"] != "break":
            continue
        end = float(e["payload"].get("until", e["ts"]))
        for r in ev[i + 1:]:
            if r["kind"] in ("resume", "break") and r["ts"] < end:
                end = r["ts"]
                break
        out.append((e["ts"], end))
    return out


def in_break(con, session_id: int, ts: float | None = None) -> tuple[float, float] | None:
    ts = ts or time.time()
    return next((b for b in breaks(con, session_id, ts) if b[0] <= ts < b[1]), None)


def finish_session(con, session_id: int, **fields) -> None:
    fields.setdefault("ended_at", time.time())
    fields["status"] = "done"
    cols = ", ".join(f"{k}=?" for k in fields)
    con.execute(f"UPDATE sessions SET {cols} WHERE id=?", (*fields.values(), session_id))
    con.commit()


if __name__ == "__main__":
    connect()
    print("DB ready at", DB_PATH)
