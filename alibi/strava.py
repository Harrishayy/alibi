"""Strava runs -> events(source='strava', kind='activity').

Connecting is a browser flow (Setup -> Connect Strava, or http://127.0.0.1:8765/strava/setup):
your Strava API app's client id/secret go into data/secrets.json, you click Authorize, Strava redirects to
/strava/callback, tokens are saved there too. Nothing to paste into .env.

  python -m alibi.strava sync              # this week's runs from the API
  python -m alibi.strava sync --fixture tests/fixtures/strava.json   # same pipeline, no keys
  python -m alibi.strava status
"""
import datetime as dt, json, os, sys, threading, time, urllib.parse
import requests
from . import config, db, report, secrets as store

BASE = os.getenv("STRAVA_BASE", "https://www.strava.com").rstrip("/")   # tests/demos point this at a fake server
TOKEN_URL = BASE + "/oauth/token"
AUTH_URL = BASE + "/oauth/authorize"
DEAUTH_URL = BASE + "/oauth/deauthorize"
API_URL = BASE + "/api/v3"
SCOPE = "read,activity:read_all"          # read_all so private runs count too
RUN_TYPES = {"Run", "TrailRun", "VirtualRun", "Wheelchair"}
PER_PAGE, MAX_PAGES = 50, 4
STATE_FILE = "strava_state.json"           # non-secret sync status (last sync, error, backoff)
_sync_lock = threading.Lock()


class NeedsReconnect(Exception):
    """Strava refused our tokens (revoked in Strava settings, or expired app). The user must click Connect again."""


class RateLimited(Exception):
    def __init__(self, until: float):
        super().__init__(f"Strava rate limit; retry after {dt.datetime.fromtimestamp(until):%H:%M}")
        self.until = until


# --- credentials ------------------------------------------------------------------------------------------------

def client_id() -> str:
    return str(store.get("strava_client_id", "", env="STRAVA_CLIENT_ID") or "")


def client_secret() -> str:
    return str(store.get("strava_client_secret", "", env="STRAVA_CLIENT_SECRET") or "")


def refresh_token() -> str:
    """The stored token wins over STRAVA_REFRESH_TOKEN: Strava rotates refresh tokens, so the env copy goes stale."""
    return str(store.load().get("strava_refresh_token") or os.getenv("STRAVA_REFRESH_TOKEN") or "")


def has_app() -> bool:
    return bool(client_id() and client_secret())


def connected() -> bool:
    return bool(has_app() and refresh_token())


def save_app(cid: str, secret: str) -> None:
    cid, secret = str(cid).strip(), str(secret).strip()
    if not cid.isdigit():
        raise ValueError("The Client ID is a number, like 123456 — copy it from strava.com/settings/api.")
    if len(secret) < 20 or not all(c in "0123456789abcdefABCDEF" for c in secret):
        raise ValueError("The Client Secret is a long code of letters and numbers — click 'show' next to it on "
                         "strava.com/settings/api and copy the whole thing.")
    store.update(strava_client_id=cid, strava_client_secret=secret)


def authorize_url(redirect_uri: str, state: str) -> str:
    q = {"client_id": client_id(), "redirect_uri": redirect_uri, "response_type": "code",
         "approval_prompt": "auto", "scope": SCOPE, "state": state}
    return AUTH_URL + "?" + urllib.parse.urlencode(q)


def _save_tokens(j: dict) -> None:
    ath = j.get("athlete") or {}
    kv = {"strava_access_token": j.get("access_token"), "strava_expires_at": j.get("expires_at"),
          "strava_refresh_token": j.get("refresh_token") or None}
    if ath:
        kv["strava_athlete"] = {"id": ath.get("id"),
                                "name": " ".join(x for x in (ath.get("firstname"), ath.get("lastname")) if x)}
    store.update(**{k: v for k, v in kv.items() if v is not None})
    if os.getenv("STRAVA_REFRESH_TOKEN") and j.get("refresh_token"):
        os.environ["STRAVA_REFRESH_TOKEN"] = j["refresh_token"]      # keep any in-process reader current


def exchange(code: str) -> dict:
    """Authorization code -> tokens, saved to secrets.json. Returns {athlete, scope_ok}."""
    r = requests.post(TOKEN_URL, data={"client_id": client_id(), "client_secret": client_secret(),
                                       "code": code, "grant_type": "authorization_code"}, timeout=20)
    if r.status_code in (400, 401):
        raise NeedsReconnect("Strava didn't accept the sign-in (the Client ID or Secret may be wrong).")
    r.raise_for_status()
    j = r.json()
    _save_tokens(j)
    _state(needs_reconnect=None, last_error=None)
    return {"athlete": (store.get("strava_athlete") or {}).get("name", "")}


def access_token(force: bool = False) -> str:
    """Cached until 5 min before expiry; a refresh persists the rotated refresh token."""
    s = store.load()
    if not force and s.get("strava_access_token") and float(s.get("strava_expires_at") or 0) - 300 > time.time():
        return s["strava_access_token"]
    if not connected():
        raise NeedsReconnect("Strava isn't connected.")
    r = requests.post(TOKEN_URL, data={"client_id": client_id(), "client_secret": client_secret(),
                                       "refresh_token": refresh_token(), "grant_type": "refresh_token"}, timeout=20)
    if r.status_code in (400, 401):
        store.update(strava_access_token=None, strava_expires_at=None)
        raise NeedsReconnect("Strava no longer accepts Alibi's access. Click Reconnect Strava.")
    _rate_check(r)
    r.raise_for_status()
    j = r.json()
    _save_tokens(j)
    return j["access_token"]


def _next_quarter_hour(now: float) -> float:
    return (int(now) // 900 + 1) * 900 + 5


def _rate_check(r) -> None:
    if r.status_code == 429:
        raise RateLimited(_next_quarter_hour(time.time()))
    for h in ("X-ReadRateLimit-Usage", "X-RateLimit-Usage"):
        lim, use = r.headers.get(h.replace("Usage", "Limit")), r.headers.get(h)
        try:
            if lim and use and int(use.split(",")[0]) >= int(lim.split(",")[0]) - 1:
                _state(backoff_until=_next_quarter_hour(time.time()))
        except ValueError:
            pass


def fetch(after: float) -> list[dict]:
    """All activities after `after`, paging until a short page (max 4 x 50)."""
    out = []
    tok = access_token()
    get = lambda page: requests.get(API_URL + "/athlete/activities", headers={"Authorization": f"Bearer {tok}"},
                                    params={"after": int(after), "per_page": PER_PAGE, "page": page}, timeout=20)
    for page in range(1, MAX_PAGES + 1):
        r = get(page)
        if r.status_code == 401 and page == 1:          # token died early: one retry with a fresh one
            store.update(strava_access_token=None, strava_expires_at=None)
            tok = access_token(force=True)
            r = get(page)
        if r.status_code == 401:
            store.update(strava_access_token=None, strava_expires_at=None)
            raise NeedsReconnect("Strava no longer accepts Alibi's access. Click Reconnect Strava.")
        _rate_check(r)
        r.raise_for_status()
        batch = r.json()
        out += batch
        if len(batch) < PER_PAGE:
            break
    return out


def deauthorize() -> None:
    """Disconnect: tell Strava (best effort) and forget the tokens. The app id/secret stay so reconnecting is one click."""
    tok = store.load().get("strava_access_token")
    if tok:
        try:
            requests.post(DEAUTH_URL, data={"access_token": tok}, timeout=10)
        except Exception:
            pass
    store.update(strava_access_token=None, strava_expires_at=None, strava_refresh_token=None, strava_athlete=None)
    os.environ.pop("STRAVA_REFRESH_TOKEN", None)
    _state(needs_reconnect=None, last_error=None, backoff_until=None)


def forget_app() -> None:
    deauthorize()
    store.update(strava_client_id=None, strava_client_secret=None)


# --- sync status (not secret) -----------------------------------------------------------------------------------

def state() -> dict:
    try:
        return json.loads((config.DATA_DIR / STATE_FILE).read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _state(**kv) -> dict:
    d = state()
    for k, v in kv.items():
        if v is None:
            d.pop(k, None)
        else:
            d[k] = v
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = config.DATA_DIR / f".{STATE_FILE}.tmp"
    tmp.write_text(json.dumps(d))
    os.replace(tmp, config.DATA_DIR / STATE_FILE)
    return d


def status() -> dict:
    """Plain-language state for Setup: not_set_up | needs_app | ready_to_authorize | connected | needs_reconnect."""
    st = state()
    ath = (store.get("strava_athlete") or {}).get("name", "")
    if st.get("needs_reconnect") and has_app():
        code, text, action = "needs_reconnect", "Strava stopped accepting Alibi's access. Reconnect to keep checking runs.", "Reconnect Strava"
    elif connected():
        code = "connected"
        last = st.get("last_sync")
        text = (f"Connected{' as ' + ath if ath else ''}. Last checked "
                f"{_ago(last)}." if last else f"Connected{' as ' + ath if ath else ''}. Checking your runs now…")
        action = "Check now"
    elif has_app():
        code, text, action = "ready_to_authorize", "Almost there — click Authorize to let Alibi read your runs.", "Authorize on Strava"
    else:
        code, text, action = "not_set_up", "Connect Strava so Alibi can check your runs automatically.", "Connect Strava"
    bo = st.get("backoff_until")
    return {"state": code, "connected": code == "connected", "athlete": ath, "text": text, "action": action,
            "last_sync": st.get("last_sync"), "last_error": st.get("last_error"),
            "backoff_until": bo if bo and bo > time.time() else None,
            "runs_this_week": st.get("runs_this_week"), "has_app": has_app(),
            "env_override": bool(os.getenv("STRAVA_CLIENT_ID") or os.getenv("STRAVA_REFRESH_TOKEN"))}


def _ago(ts: float) -> str:
    s = max(0, time.time() - ts)
    return "just now" if s < 60 else f"{int(s // 60)} min ago" if s < 3600 else \
        f"{int(s // 3600)} h ago" if s < 86400 else dt.datetime.fromtimestamp(ts).strftime("%a %d %b")


# --- sync -------------------------------------------------------------------------------------------------------

def is_run(a: dict) -> bool:
    return a.get("sport_type") in RUN_TYPES or a.get("type") in RUN_TYPES


def _payload(a: dict, start: float) -> dict:
    return {"id": a["id"], "name": a.get("name") or "Run", "distance_km": round(float(a.get("distance") or 0) / 1000, 2),
            "moving_min": round(float(a.get("moving_time") or 0) / 60), "start_date": start,
            "sport_type": a.get("sport_type") or a.get("type") or "Run",
            "elevation_m": round(float(a.get("total_elevation_gain") or 0)),
            "url": f"https://www.strava.com/activities/{a['id']}"}


def latest_runs(con, t0: float, t1: float) -> list[dict]:
    """Strava events between t0 and t1, newest version per activity id (an edited run replaces the old one)."""
    by_id = {}
    for e in db.events_between(con, t0, t1, "strava"):
        p = e["payload"]
        if e["kind"] == "activity" and "id" in p:
            if p["id"] not in by_id or e["id"] > by_id[p["id"]][0]:
                by_id[p["id"]] = (e["id"], p)
    return sorted((p for _, p in by_id.values()), key=lambda p: p.get("start_date", 0))


def sync(fixture: str | None = None, after: float | None = None) -> list[dict]:
    """Fetch runs since Monday (or `after`), add new ones and re-add edited ones. Returns the added payloads."""
    with _sync_lock:
        con = db.connect()
        t0 = report.week_start() if after is None else after
        try:
            acts = json.load(open(fixture)) if fixture else fetch(t0)
        except NeedsReconnect as e:
            _state(needs_reconnect=True, last_error=str(e))
            raise
        except RateLimited as e:
            _state(backoff_until=e.until, last_error="Strava asked us to slow down; trying again shortly.")
            raise
        latest = {}
        for (eid, p) in con.execute("SELECT id, payload FROM events WHERE source='strava' AND kind='activity' ORDER BY id"):
            p = json.loads(p)
            if "id" in p:
                latest[p["id"]] = p
        added = []
        for a in acts:
            if not is_run(a) or "id" not in a or not a.get("start_date"):
                continue
            start = dt.datetime.fromisoformat(a["start_date"].replace("Z", "+00:00")).timestamp()
            if start < t0:
                continue
            p = _payload(a, start)
            old = latest.get(a["id"])
            if old and old.get("distance_km") == p["distance_km"] and old.get("moving_min") == p["moving_min"]:
                continue
            if old:
                p["edited"] = True
            db.add_event(con, "strava", "activity", p, ts=start)
            latest[a["id"]] = p
            added.append(p)
        if not fixture:
            now = time.time()
            _state(last_sync=now, last_error=None, needs_reconnect=None, backoff_until=None,
                   runs_this_week=len(latest_runs(con, report.week_start(), now)))
        return added


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "exchange":
        print(exchange(sys.argv[2]))
    elif len(sys.argv) >= 2 and sys.argv[1] == "status":
        print(json.dumps(status(), indent=1))
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
