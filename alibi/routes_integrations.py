"""HTTP routes for Strava, Apple Health and phone sync. Mounted by api.py via hooks.routers().

GET  /api/integrations                 one summary for Setup: {strava, health, phone}
GET  /api/strava/status                {state: not_set_up|ready_to_authorize|connected|needs_reconnect, text, action, ...}
POST /api/strava/app {client_id, client_secret}      save your Strava API app (secrets.json, chmod 600)
GET  /strava/setup                     guided page: create the app -> paste id/secret -> Authorize
GET  /strava/connect                   302 to Strava's Authorize page (state-checked)
GET  /strava/callback                  Strava sends you back here; saves tokens, first sync, friendly page
POST /api/strava/sync                  check now -> {ok, added, error, status}
POST /api/strava/disconnect {forget_app?: bool}
GET  /api/strava/runs?days=7           newest version of each run
GET  /api/apple-health/status          {connected, latest_date, text, action, habits, phone_sync}
GET  /api/apple-health/days?days=14    [{date, steps, sleep_h, mindful_min, workout_min, workouts}]
POST /api/apple-health/samples {date?, steps?, sleep_h?, ...}   add a day by hand (this Mac only)
GET  /api/phone-sync                   {enabled, running, port, urls[], ingest_url, setup_url, secret}
POST /api/phone-sync/enable | /disable | /rotate
GET  /api/phone-sync/qr.svg            QR of the phone setup link
GET  /phone                            iPhone setup page (QR + exact Shortcut steps)
"""
import html, secrets as _rand, time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from . import config, db, integrations as integ, strava

router = APIRouter()


def _json_only(request: Request) -> None:
    """State-changing POSTs need a JSON content type, so a random web page can't fire them at localhost."""
    if "application/json" not in request.headers.get("content-type", ""):
        raise HTTPException(415, "send JSON")


async def _body(request: Request) -> dict:
    _json_only(request)
    try:
        b = await request.json()
    except Exception:
        b = {}
    return b if isinstance(b, dict) else {}


# --- summary ------------------------------------------------------------------------------------------------------

@router.get("/api/integrations")
def summary():
    con = db.connect()
    return {"strava": strava.status(), "health": integ.health_status(con), "phone": phone_info()}


# --- Strava -------------------------------------------------------------------------------------------------------

@router.get("/api/strava/status")
def strava_status():
    return strava.status()


@router.post("/api/strava/app")
async def strava_app(request: Request):
    b = await _body(request)
    try:
        strava.save_app(b.get("client_id", ""), b.get("client_secret", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "status": strava.status(), "connect_url": "/strava/connect"}


def _redirect_uri(request: Request) -> str:
    host = request.headers.get("host") or f"127.0.0.1:{request.url.port}"
    return f"{request.url.scheme}://{host}/strava/callback"


@router.get("/strava/connect")
def strava_connect(request: Request):
    if not strava.has_app():
        return RedirectResponse("/strava/setup", 303)
    state = _rand.token_urlsafe(16)
    from . import secrets as store
    store.update(strava_oauth_state={"v": state, "ts": time.time()})
    return RedirectResponse(strava.authorize_url(_redirect_uri(request), state), 302)


@router.get("/strava/callback", response_class=HTMLResponse)
def strava_callback(request: Request, code: str = "", state: str = "", scope: str = "", error: str = ""):
    from . import secrets as store
    want = store.get("strava_oauth_state") or {}
    store.update(strava_oauth_state=None)
    if error:
        return _page("Strava not connected", _card(
            "You chose not to connect Strava",
            "That's fine — Alibi just won't check your runs. You can connect any time from Setup.",
            [("Try again", "/strava/connect", True), ("Back to Alibi", "/", False)]))
    if not code or not want or state != want.get("v") or time.time() - want.get("ts", 0) > 1800:
        return _page("Strava not connected", _card(
            "That link has expired",
            "Start again from Alibi so the connection is linked to this Mac.",
            [("Connect Strava", "/strava/connect", True), ("Back to Alibi", "/", False)]))
    if "activity:read" not in scope:
        return _page("Strava not connected", _card(
            "Alibi needs to see your activities",
            "On the Strava page, leave the box <b>“View data about your activities”</b> ticked, then press Authorize.",
            [("Try again", "/strava/connect", True), ("Back to Alibi", "/", False)]))
    try:
        who = strava.exchange(code)
    except Exception as e:
        return _page("Strava not connected", _card(
            "Strava didn't accept the sign-in",
            "Usually this means the Client ID or Client Secret doesn't match your Strava app. "
            "Check them on strava.com/settings/api and paste them again.",
            [("Fix the app details", "/strava/setup", True), ("Back to Alibi", "/", False)],
            detail=str(e)))
    res = integ.strava_sync_now()
    runs = strava.latest_runs(db.connect(), _week_start(), time.time())
    if res["ok"]:
        km = next((float(h.get("min_km") or 0) for h in (config.habits().get("habits") or {}).values()
                   if isinstance(h, dict) and h.get("source") == "strava"), 0)
        good = [r for r in runs if r.get("distance_km", 0) >= km]
        found = (f"Found {len(runs)} run{'s' * (len(runs) != 1)} this week"
                 + (f" — {len(good)} of them {km:g} km or more, so {'it counts' if len(good) == 1 else 'they count'}"
                    if km and runs else "")
                 + (". Latest: " + ", ".join(f"{html.escape(r['name'])} {r['distance_km']:g} km" for r in reversed(runs[-3:]))
                    if runs else "") + ". Alibi checks again every 30 minutes.")
    else:
        found = "Connected. The first check didn't go through — Alibi will try again in a few minutes."
    name = f", {html.escape(who['athlete'].split()[0])}" if who.get("athlete") else ""
    return _page("Strava connected", _card(f"Strava is connected{name}", found,
                                          [("Back to Alibi", "/#setup", True)], ok=True,
                                          extra="<script>setTimeout(()=>location.href='/#setup',6000)</script>"))


def _week_start():
    from . import report
    return report.week_start()


@router.post("/api/strava/sync")
def strava_sync():
    if not strava.connected():
        raise HTTPException(400, "Strava isn't connected yet.")
    res = integ.strava_sync_now()
    return {**res, "status": strava.status()}


@router.post("/api/strava/disconnect")
async def strava_disconnect(request: Request):
    b = await _body(request)
    (strava.forget_app if b.get("forget_app") else strava.deauthorize)()
    return {"ok": True, "status": strava.status()}


@router.get("/api/strava/runs")
def strava_runs(days: int = 7):
    now = time.time()
    return {"runs": list(reversed(strava.latest_runs(db.connect(), now - max(1, min(days, 90)) * 86400, now)))}


@router.get("/strava/setup", response_class=HTMLResponse)
def strava_setup_page():
    st = strava.status()
    if st["state"] == "connected":
        when = f"Last checked {strava._ago(st['last_sync'])}." if st.get("last_sync") else ""
        body = _card(f"Strava is connected{' as ' + html.escape(st['athlete']) if st['athlete'] else ''}",
                     f"Alibi checks your runs every 30 minutes. {when}",
                     [("Back to Alibi", "/#setup", True)], ok=True,
                     extra="""<p class="small"><button class="link" onclick="disc()">Disconnect Strava</button></p>
<script>async function disc(){if(!confirm('Stop checking runs with Strava?'))return;
await fetch('/api/strava/disconnect',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});location.reload()}</script>""")
        return _page("Strava", body)
    reconnect = st["state"] == "needs_reconnect"
    have = st["has_app"]
    lead = ("Strava stopped accepting Alibi's access (this happens if you removed it in Strava's settings). "
            "Press the button to reconnect." if reconnect else
            "Alibi reads your runs from Strava, so a run counts without you doing anything. "
            "Strava only lets personal tools in through a small “API app” that you make yourself — it's free and "
            "takes about two minutes.")
    copy = lambda v: f'<code>{v}</code><button class="copy" onclick="cp(this,\'{v}\')">Copy</button>'
    step1 = f"""<li class="{'done' if have else ''}"><h3>Make your Strava app</h3>
<p>Open Strava's API page (log in if asked) and fill in the form like this:</p>
<table class="kv"><tr><td>Application Name</td><td>{copy('Alibi')}</td></tr>
<tr><td>Category</td><td>Training</td></tr>
<tr><td>Website</td><td>{copy('http://localhost')}</td></tr>
<tr><td>Authorization Callback Domain</td><td>{copy('localhost')}</td></tr></table>
<p class="small">Tick the agreement and press Create. If Strava asks for an icon, any square picture is fine.</p>
<a class="btn" href="https://www.strava.com/settings/api" target="_blank" rel="noopener">Open strava.com/settings/api ↗</a></li>"""
    step2 = f"""<li class="{'done' if have else ''}"><h3>Copy two codes from that page</h3>
<p>Strava now shows <b>Client ID</b> (a number) and <b>Client Secret</b> (press “show” to see it). Paste them here.
They stay on this Mac.</p>
<form id="app" onsubmit="save(event)"><label>Client ID<input name="client_id" inputmode="numeric" autocomplete="off"
placeholder="e.g. 123456"></label><label>Client Secret<input name="client_secret" autocomplete="off"
placeholder="40 letters and numbers"></label><button class="btn {'' if have else 'primary'}" type="submit">{'Save new codes' if have else 'Save and continue'}</button>
<p id="err" class="err" role="alert"></p></form></li>"""
    step3 = f"""<li><h3>Let Alibi read your runs</h3><p>Strava will ask “Authorize Alibi?” — leave the boxes ticked and press
<b>Authorize</b>. You'll come straight back here.</p>
<a class="btn {'primary' if have else 'off'}" id="auth" href="/strava/connect">{'Reconnect Strava' if reconnect else 'Authorize on Strava'}</a></li>"""
    body = f"""<main><a class="back" href="/#setup">← Alibi</a><h1>{'Reconnect' if reconnect else 'Connect'} Strava</h1>
<p class="lead">{lead}</p><ol class="steps">{'' if reconnect else step1 + step2}{step3}</ol>
<details><summary>Details</summary><p class="small">Alibi asks for read-only access to your activities
(<code>{strava.SCOPE}</code>). Runs, trail runs, treadmill runs and wheelchair runs count. The codes are stored in
<code>data/secrets.json</code>, readable only by you. Environment variables STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET
still override them.</p></details></main>
<script>
function cp(b,v){{navigator.clipboard.writeText(v);b.textContent='Copied';setTimeout(()=>b.textContent='Copy',1200)}}
async function save(e){{e.preventDefault();const f=new FormData(e.target);const r=await fetch('/api/strava/app',{{method:'POST',
headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{client_id:f.get('client_id'),client_secret:f.get('client_secret')}})}});
const j=await r.json().catch(()=>({{}}));if(!r.ok){{document.getElementById('err').textContent=j.detail||j.error||'Could not save.';return}}
location.href='/strava/connect'}}
</script>"""
    return _page("Connect Strava", body)


# --- Apple Health -------------------------------------------------------------------------------------------------

@router.get("/api/apple-health/status")
def health_status():
    return integ.health_status(db.connect())


@router.get("/api/apple-health/days")
def health_days(days: int = 14):
    import datetime as dt
    since = (dt.date.today() - dt.timedelta(days=max(1, min(days, 366)) - 1)).isoformat()
    d = integ.health_days(db.connect(), since)
    return {"days": [d[k] for k in sorted(d, reverse=True)]}


@router.post("/api/apple-health/samples")
async def health_add(request: Request):
    b = await _body(request)
    try:
        return {"ok": True, "saved": integ.save_health(db.connect(), b)}
    except ValueError as e:
        raise HTTPException(400, str(e))


# --- phone sync ---------------------------------------------------------------------------------------------------

def phone_info() -> dict:
    st = integ.phone_status()
    addrs = integ.addresses()
    key = integ.phone_secret(create=st["enabled"])
    base = lambda a: a.get("base") or f"http://{a['host']}:{st['port']}"
    urls = [{**a, "ingest_url": base(a) + "/ingest",
             "setup_url": base(a) + "/phone" + (f"#k={key}" if key else "")} for a in addrs]
    best = urls[0] if urls else None
    if not st["enabled"]:
        text = "Off. Turn on iPhone sync so a Shortcut on your phone can send Apple Health data each night."
    elif not st["running"]:
        text = "On, but not listening right now — is Alibi running?"
    else:
        text = "On. Your iPhone can send Health data to this Mac" + (" (same Wi-Fi or Tailscale)." if urls else ".")
    return {**st, "text": text, "urls": urls, "ingest_url": best and best["ingest_url"],
            "setup_url": best and best["setup_url"], "secret": key or None}


@router.get("/api/phone-sync")
def phone_get():
    return phone_info()


@router.post("/api/phone-sync/enable")
async def phone_enable(request: Request):
    _json_only(request)
    integ.set_state(phone_sync_enabled=True)
    integ.phone_secret()
    try:
        integ.phone_start()
    except Exception as e:
        raise HTTPException(409, str(e))
    return phone_info()


@router.post("/api/phone-sync/disable")
async def phone_disable(request: Request):
    _json_only(request)
    integ.set_state(phone_sync_enabled=False)
    integ.phone_stop()
    return phone_info()


@router.post("/api/phone-sync/rotate")
async def phone_rotate(request: Request):
    _json_only(request)
    integ.rotate_phone_secret()
    return phone_info()


@router.get("/api/phone-sync/qr.svg")
def phone_qr(which: int = 0):
    info = phone_info()
    if not info["urls"]:
        raise HTTPException(404, "no network address found")
    return Response(_qr_svg(info["urls"][min(which, len(info["urls"]) - 1)]["setup_url"]), media_type="image/svg+xml")


def _qr_svg(text: str) -> str:
    try:
        import segno
    except ImportError:
        return ""
    return segno.make(text, error="m").svg_inline(scale=5, dark="#111", light="#fff", border=2)


@router.get("/phone", response_class=HTMLResponse)
def phone_setup_page():
    return phone_page_html(on_phone=False)


SHORTCUT_STEPS = """
<li><h3>Make a new Shortcut</h3><p>Open the <b>Shortcuts</b> app → <b>+</b>. Name it <b>Send Health to Alibi</b>.</p></li>
<li><h3>Step count</h3><p>Add action <b>Find Health Samples</b>. Tap <b>Add Filter</b> → <b>Type is Steps</b>. Add another filter
→ <b>Start Date is today</b>.<br>Add <b>Calculate Statistics</b> → <b>Sum</b> of <i>Health Samples</i>.</p></li>
<li><h3>Sleep</h3><p>Add <b>Find Health Samples</b> → filters <b>Type is Sleep</b> and <b>Start Date is in the last 1 days</b>.
If you can, also add <b>Value is not In Bed</b> and <b>Value is not Awake</b>.<br>Add <b>Get Details of Health Samples</b> →
<b>Duration</b>, then <b>Calculate Statistics</b> → <b>Sum</b>, then <b>Convert Measurement</b> → convert the Statistics
result to <b>hours</b>.</p></li>
<li><h3>Meditation <span class="opt">optional</span></h3><p><b>Find Health Samples</b> → <b>Type is Mindful Minutes</b>,
<b>Start Date is today</b> → <b>Get Details</b> → <b>Duration</b> → <b>Calculate Statistics</b> → <b>Sum</b> →
<b>Convert Measurement</b> → to <b>minutes</b>.</p></li>
<li><h3>Workouts <span class="opt">optional</span></h3><p><b>Find Health Samples</b> → <b>Type is Workouts</b>,
<b>Start Date is today</b> → <b>Get Details</b> → <b>Duration</b> → <b>Calculate Statistics</b> → <b>Sum</b> →
<b>Convert Measurement</b> → to <b>minutes</b>.</p></li>
<li><h3>Send it to Alibi</h3><p>Add <b>Get Contents of URL</b> and paste the address below. Tap <b>Show More</b>:</p>
<table class="kv"><tr><td>Method</td><td>POST</td></tr>
<tr><td>Headers</td><td>Add header: key {KEYNAME}, value: the key below</td></tr>
<tr><td>Request Body</td><td>JSON — add four <b>Number</b> fields:<br><code>steps</code> = the Steps sum,
<code>sleep_h</code> = Sleep in hours, <code>mindful_min</code> = Meditation in minutes, <code>workout_min</code> = Workouts in
minutes</td></tr></table>
<p class="small">Tap each value and pick the <b>Converted Measurement</b> from that section. Use minutes for meditation and
workouts — a 1-minute session sent as “60” would read as an hour. If you'd rather send seconds, name the fields
<code>mindful_s</code> and <code>workout_s</code> instead.</p></li>
<li><h3>Test it</h3><p>Add <b>Show Result</b> (it shows what Alibi got), then press ▶︎. You should see something like
<i>“Alibi got 2026-10-01: Steps 8,123, Sleep 7 h 20”</i>. Allow Health access when iOS asks.</p></li>
<li><h3>Run it every night</h3><p><b>Automation</b> tab → <b>+</b> → <b>Time of Day</b> → 21:30, Daily → <b>Run Immediately</b>
→ pick <b>Send Health to Alibi</b>. Remove the Show Result step once it works.</p>
<p class="small">iOS can't read Health while the phone is locked, so pick a time you're usually on your phone.
Your Mac needs to be awake with Alibi running; a missed night just stays blank — it never counts against you.</p></li>"""


def phone_page_html(on_phone: bool) -> str:
    steps = SHORTCUT_STEPS.replace("{KEYNAME}", "<code>X-Alibi-Secret</code>")
    if on_phone:                                         # served on the LAN: the key only lives in the URL fragment
        top = """<p class="lead">Build one Shortcut that sends today's steps, sleep and meditation to Alibi on your Mac each night.
Copy these two things when the steps ask for them:</p>
<table class="kv"><tr><td>Address</td><td><code id="u"></code><button class="copy" onclick="cp(this,U)">Copy</button></td></tr>
<tr><td>Key</td><td><code id="k">—</code><button class="copy" onclick="cp(this,K)">Copy</button></td></tr></table>
<p id="nokey" class="err" hidden>No key in this link. Scan the QR code on your Mac again (Alibi → Setup → iPhone).</p>
<script>const U=location.origin+'/ingest';const K=new URLSearchParams(location.hash.slice(1)).get('k')||'';
document.getElementById('u').textContent=U;if(K)document.getElementById('k').textContent=K;else document.getElementById('nokey').hidden=false;
function cp(b,v){navigator.clipboard.writeText(v).then(()=>{b.textContent='Copied';setTimeout(()=>b.textContent='Copy',1200)})}</script>"""
        return _page("Alibi · iPhone setup", f"<main><h1>Send Apple Health to Alibi</h1>{top}<ol class='steps'>{steps}</ol></main>")
    info = phone_info()
    if not info["enabled"] or not info["running"]:
        top = f"""<p class="lead">Alibi can check walking, sleep and meditation habits with Apple Health. Your iPhone sends the
numbers to this Mac once a night with a Shortcut — over your home Wi-Fi, or Tailscale if you use it.</p>
<p>{html.escape(info['text'])}</p>
<p class="small">Turning this on lets devices on your network send Health numbers to Alibi if they have the key.
Nothing else on this Mac is reachable.</p>
<button class="btn primary" onclick="go('enable')">Turn on iPhone sync</button>"""
        tail = ""
    else:
        qr = _qr_svg(info["setup_url"]) if info["setup_url"] else ""
        alts = "".join(f"<li>{html.escape(u['label'])}: <code>{html.escape(u['ingest_url'])}</code></li>" for u in info["urls"])
        top = f"""<p class="lead">Scan this with your iPhone camera. It opens the steps on your phone, with the address and key ready to copy.</p>
<div class="qr">{qr or '<p class="err">QR code unavailable — type the address below instead.</p>'}</div>
<table class="kv"><tr><td>Address</td><td><code>{html.escape(info['ingest_url'] or '')}</code></td></tr>
<tr><td>Key</td><td><code>{html.escape(info['secret'] or '')}</code></td></tr></table>
<details><summary>Other addresses</summary><ul class="small">{alts}</ul>
<p class="small">The phone and Mac must be on the same Wi-Fi, or both signed in to Tailscale. Phone sync listens on port
{info['port']} and accepts only Health uploads with this key.</p>
<button class="link" onclick="go('rotate')">Make a new key</button> · <button class="link" onclick="go('disable')">Turn off iPhone sync</button></details>"""
        tail = f"<h2>Or follow the steps here</h2><ol class='steps'>{steps.replace('the key below', 'the key above').replace('paste the address below', 'paste the address above')}</ol>"
    return _page("iPhone setup", f"""<main><a class="back" href="/#setup">← Alibi</a><h1>Apple Health via your iPhone</h1>{top}{tail}</main>
<script>async function go(a){{const r=await fetch('/api/phone-sync/'+a,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});
if(!r.ok){{const j=await r.json().catch(()=>({{}}));alert(j.detail||'Could not do that.');}}location.reload()}}</script>""")


# --- tiny page kit (light + dark) ---------------------------------------------------------------------------------

CSS = """:root{--bg:#f2f2f2;--card:#fff;--ink:#1a1a1a;--mut:#5e5e5e;--line:#d7d7d7;--acc:#4e7a00;--ok:#4e7a00;--err:#c4161c;--code:#ebebeb}
@media (prefers-color-scheme:dark){:root{--bg:#000;--card:#1a1a1a;--ink:#eee;--mut:#a6a6a6;--line:#333;--acc:#76b900;--ok:#76b900;--err:#ff7a7e;--code:#262626}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text",system-ui,sans-serif}
main{max-width:640px;margin:0 auto;padding:28px 16px 64px}h1{font-size:28px;letter-spacing:-.02em;margin:8px 0 8px}
h2{font-size:18px;margin:36px 0 8px}h3{font-size:16px;margin:0 0 4px}.lead{color:var(--mut);font-size:17px}
.back{color:var(--mut);text-decoration:none;font-size:14px}.small{font-size:14px;color:var(--mut)}.err{color:var(--err)}
.steps{list-style:none;counter-reset:s;padding:0;margin:20px 0}.steps>li{counter-increment:s;position:relative;padding:16px 16px 16px 56px;
background:var(--card);border:1px solid var(--line);border-radius:14px;margin:10px 0}
.steps>li:before{content:counter(s);position:absolute;left:16px;top:16px;width:26px;height:26px;border-radius:50%;background:var(--ink);
color:var(--bg);font-weight:600;font-size:14px;display:grid;place-items:center}.steps>li.done:before{content:"✓";background:var(--ok)}
.steps p{margin:6px 0}.opt{font-weight:400;font-size:12px;color:var(--mut);border:1px solid var(--line);border-radius:99px;padding:1px 7px;margin-left:4px}
.kv{border-collapse:collapse;width:100%;margin:8px 0;font-size:14px}.kv td{padding:7px 0;border-top:1px solid var(--line);vertical-align:top}
.kv td:first-child{color:var(--mut);width:38%;padding-right:10px}code{background:var(--code);padding:2px 6px;border-radius:6px;font-size:13px;word-break:break-all}
.btn{display:inline-block;border:1px solid var(--line);background:var(--card);color:var(--ink);padding:10px 16px;border-radius:10px;
font:inherit;font-weight:600;text-decoration:none;cursor:pointer;margin-top:8px;min-height:44px}.btn.primary{background:#76b900;border-color:#76b900;color:#000}
.btn.off{opacity:.45;pointer-events:none}.copy{margin-left:8px;border:1px solid var(--line);background:none;color:var(--acc);border-radius:7px;
font-size:12px;padding:3px 8px;cursor:pointer}.link{border:0;background:none;color:var(--acc);font:inherit;font-size:14px;padding:0;cursor:pointer}
label{display:block;font-size:14px;color:var(--mut);margin:10px 0}input{display:block;width:100%;margin-top:4px;padding:11px 12px;font:inherit;
color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:10px}input:focus{outline:2px solid var(--acc);outline-offset:1px}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:28px;margin-top:12vh;text-align:center}
.card .mark{font-size:40px;line-height:1}.card.ok .mark{color:var(--ok)}.card p{color:var(--mut)}
.qr{background:#fff;border-radius:16px;padding:12px;width:max-content;max-width:100%;margin:16px 0}.qr svg{display:block;max-width:100%;height:auto}
details{margin-top:18px}summary{cursor:pointer;color:var(--mut);font-size:14px}"""


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,"
            f"initial-scale=1'><title>{html.escape(title)}</title><style>{CSS}</style></head><body>{body}</body></html>")


def _card(title, text, buttons, ok=False, detail="", extra="") -> str:
    bs = "".join(f'<a class="btn{" primary" if p else ""}" href="{u}">{html.escape(l)}</a> ' for l, u, p in buttons)
    d = f"<details><summary>Details</summary><p class='small'>{html.escape(detail)}</p></details>" if detail else ""
    return (f"<main><div class='card{' ok' if ok else ''}'><div class='mark'>{'✓' if ok else '·'}</div><h1>{html.escape(title)}</h1>"
            f"<p>{text}</p>{bs}{d}{extra}</div></main>")
