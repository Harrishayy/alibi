"""Intent DoD: rules before the model. "going for a run" is a Strava claim (never a camera session), "draw for 8" starts
at once, and only sentences the rules can't place reach the model. The model is a stub that always says drawing."""
from harness import check
from alibi import cli, config, db, intent, llm

con = db.connect()
calls = []
answer = {"habit": "drawing"}


def stub(system, user, max_tokens=500, interactive=False):
    calls.append(user)
    return dict(answer)


llm.chat_json = stub
config.TEXT_READY = True                    # as on the live install: a text model is configured


def claims():
    return con.execute("SELECT count(*) FROM events WHERE source='user' AND kind='claim'").fetchone()[0]


def sessions():
    return con.execute("SELECT count(*) FROM sessions").fetchone()[0]


r = cli.say(con, "going for a run")
check(claims() == 1 and sessions() == 0, f"'going for a run': 1 claim, 0 sessions ({claims()}, {sessions()})")
check("checked by Strava" in r and "5 km" in r, f"claim reply: {r}")
check(not calls, f"no model call for the claim ({len(calls)})")

r = cli.say(con, "draw for 8")
s = db.active_session(con)
check(s and s["habit"] == "drawing" and s["declared_min"] == 8, f"'draw for 8' starts drawing for 8 min: {r}")
check(r.startswith("Started Drawing for 8 min.") and "(your usual)" not in r, "the reply takes the said minutes")
check(not calls, f"no model call for a habit word plus minutes ({len(calls)})")
cli.cancel(con, force=True)

r = cli.say(con, "I'm going to sketch something")
check(len(calls) == 1 and db.active_session(con)["habit"] == "drawing", f"no minutes -> the model is asked once: {r}")
cli.cancel(con, force=True)

answer["habit"] = "portfolio"
r = cli.say(con, "build my portfolio website for 30 min")
s = db.active_session(con)
check(len(calls) == 2 and s["habit"] == "portfolio" and s["declared_min"] == 30,
      f"two habits named -> the model picks, the said minutes stay: {r}")
cli.cancel(con, force=True)

r = cli.say(con, "going for a run for 5 hours")
check("checked by Strava" in r and claims() == 2 and len(calls) == 2, f"a long run is still a claim: {r}")
check(intent.match_habits("draw and sketch for 8") == ["drawing"], "two aliases of one habit are one match")
check(sessions() == 0, "nothing above left a session behind")
print("PASS test_run_intent")
