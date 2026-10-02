"""Night order DoD: at REPORT_HOUR the day's recap goes out first and the night report (with Accept) last, so the report is the
alert left on the island. Checked on the inline path (no model) and on the night-digest thread (a model configured, as
live), each once a day. Fake clock; the model is a stub that fails, so the night falls back to rules."""
import datetime as dt
from harness import Clock, check
from alibi import config, daemon, db, digest, llm, notify

con = db.connect()
clock = Clock()
D = dt.date(2026, 10, 5)                                # a Monday: the week's maths (and so the proposal) never vary


def at(day: int, h: int, m: int = 0) -> float:
    return dt.datetime.combine(D + dt.timedelta(days=day), dt.time(h, m)).timestamp()


def finished(habit, start, minutes, ratio, verdict):
    con.execute("INSERT INTO sessions(habit,modality,declared_min,started_at,ends_at,ended_at,status,on_task_ratio,"
                "verdict) VALUES (?,'physical',?,?,?,?,'done',?,?)",
                (habit, minutes, start, start + minutes * 60, start + minutes * 60, ratio, verdict))
    con.commit()


def night(day: int) -> list:
    """Ticks at REPORT_HOUR on `day`, waits for any night thread, returns the alerts it produced."""
    n0 = len(notify.recent_alerts(10_000))
    clock.t = at(day, config.REPORT_HOUR)
    daemon.tick(con); clock.advance(5); daemon.tick(con)
    daemon.join_reels()
    clock.advance(5); daemon.tick(con)                      # the next tick sees the report and does nothing
    daemon.join_reels()
    return notify.recent_alerts(10_000)[n0:]


def check_night(alerts: list, day: int, how: str):
    kinds = [a["kind"] for a in alerts]
    rep = alerts[-1] if alerts else {}
    check(kinds.count("report") == 1 and kinds.count("recap") == 1, f"{how}: one recap, one report ({kinds})")
    check(kinds.index("recap") < kinds.index("report") and rep.get("kind") == "report",
          f"{how}: the recap comes first, the report is the last alert ({kinds})")
    acts = [x.get("label") for x in rep.get("actions") or []]
    check(acts == ["Accept", "Not now"] and rep.get("proposal"), f"{how}: the report carries Accept ({acts})")
    check(rep.get("slot") == f"{D + dt.timedelta(days=day)}-night" and rep.get("habit_label") == "Night review",
          f"{how}: night slot and island header ({rep.get('slot')}, {rep.get('habit_label')})")


# day 0, no model: the night runs inline on the tick
finished("drawing", at(0, 19), 20, 0.8, "done")
check_night(night(0), 0, "inline")

# day 1, a model configured (it fails, so rules): the night runs on its own thread
def down(*a, **k):
    raise ConnectionError("stub model is down")


llm.chat_tools = llm.chat_text = llm.chat_json = down
config.TEXT_READY = True
finished("drawing", at(1, 18), 15, 0.9, "done")
alerts = night(1)
check_night(alerts, 1, "night thread")
check(digest.get(f"{D + dt.timedelta(days=1)}-night")["via"] == "rules", "the failed model fell back to rules")
print("PASS test_night_order")
