"""P5 — Strava runs -> events(source='strava', kind='activity').

  python -m alibi.strava exchange <code>   # once, after browser OAuth (see PLAN.md P5)
  python -m alibi.strava sync              # this week's runs from the API
  python -m alibi.strava sync --fixture tests/fixtures/strava.json   # same pipeline, no keys
"""
import datetime as dt, json, os, sys
import requests
from . import config, db, report

TOKEN_URL = "https://www.strava.com/oauth/token"


def exchange(code: str) -> None:
    r = requests.post(TOKEN_URL, data={"client_id": os.getenv("STRAVA_CLIENT_ID"),
                                       "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
                                       "code": code, "grant_type": "authorization_code"}, timeout=20)
    r.raise_for_status()
    print("STRAVA_REFRESH_TOKEN=" + r.json()["refresh_token"], "  <- paste into .env")


def access_token() -> str:
    r = requests.post(TOKEN_URL, data={"client_id": os.getenv("STRAVA_CLIENT_ID"),
                                       "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
                                       "refresh_token": os.getenv("STRAVA_REFRESH_TOKEN"),
                                       "grant_type": "refresh_token"}, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def fetch(after: float) -> list[dict]:
    r = requests.get("https://www.strava.com/api/v3/athlete/activities",
                     headers={"Authorization": f"Bearer {access_token()}"},
                     params={"after": int(after), "per_page": 50}, timeout=20)
    r.raise_for_status()
    return r.json()


def sync(fixture: str | None = None) -> list[dict]:
    con = db.connect()
    t0 = report.week_start()
    acts = json.load(open(fixture)) if fixture else fetch(t0)
    seen = {json.loads(p)["id"] for (p,) in con.execute("SELECT payload FROM events WHERE source='strava'")}
    added = []
    for a in acts:
        if (a.get("sport_type") or a.get("type")) != "Run":
            continue
        start = dt.datetime.fromisoformat(a["start_date"].replace("Z", "+00:00")).timestamp()
        if start < t0 or a["id"] in seen:
            continue
        p = {"id": a["id"], "name": a.get("name", "Run"), "distance_km": round(a["distance"] / 1000, 2),
             "moving_min": round(a.get("moving_time", 0) / 60), "start_date": start}
        db.add_event(con, "strava", "activity", p, ts=start)
        added.append(p)
    return added


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "exchange":
        exchange(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "sync":
        fx = sys.argv[sys.argv.index("--fixture") + 1] if "--fixture" in sys.argv else None
        new = sync(fx)
        for p in new:
            print(f"  + {p['name']}: {p['distance_km']} km, {p['moving_min']} min")
        r = report.build_json()["running"]
        if r:
            print(f"Running {r['qualifying']}/{r['target_sessions']} — "
                  + ("aligned" if not r["behind_by"] else f"behind by {r['behind_by']}"))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
