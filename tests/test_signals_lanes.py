"""Signals page lanes, in a real browser (headless Chromium, every request answered in-process by the API — no port):
  1. tooltips are plain text: a hostile window / media / notification title renders literally and never runs;
  2. a full day (Mac locked overnight, notifications every 2 min, heart every 5 min) keeps its morning in the lanes;
  3. change-based meeting rows (one "on", one "off" — what alibi/mac_signals.py writes) draw the whole call.
Static checks run even where Chromium can't start."""
import datetime as dt, json, re, sys, urllib.parse
from harness import ROOT, check
from fastapi.testclient import TestClient
from alibi import api, db, signals

html = (ROOT / "alibi" / "web" / "signals.html").read_text()
check("tip.innerHTML" not in html and "replaceChildren" in html, "tooltip is built with textContent, never innerHTML")
check(not re.search(r'data-tip="\$\{esc\(`<', html), "no HTML-templated data-tip attributes left")

c = TestClient(api.app)
con = db.connect()
day = dt.date.today() - dt.timedelta(days=1)
T = lambda h, m=0: dt.datetime.combine(day, dt.time(h, m)).timestamp()
EVIL = '<img src=x onerror="window.__pwn=1">'

# a full, noisy day
t = T(0, 5)
while t < T(9, 30):
    signals.store(con, "mac", "presence", {"idle_s": 900, "locked": True, "display_asleep": True}, ts=t); t += 300
t = T(0, 1)
while t < T(23, 59):
    signals.store(con, "mac", "notifications", {"app": "Slack" if int(t) % 3 else EVIL + "App", "count": 1, "phone": False}, ts=t); t += 120
t = T(0, 2)
while t < T(23, 59):
    signals.store(con, "health", "heart", {"samples": [[t - 60, 62], [t, 64]]}, ts=t); t += 300
signals.store(con, "phone", "pickup", {"ts": T(7, 0)}, ts=T(7, 0))
signals.store(con, "phone", "location", {"at_home": False}, ts=T(8, 0))
signals.store(con, "phone", "location", {"at_home": True}, ts=T(9, 0))
# a digital session with a hostile web page title, and hostile media
cur = con.execute("INSERT INTO sessions(habit, modality, declared_min, started_at, ends_at, ended_at, status, verdict, "
                  "on_task_ratio) VALUES (?,?,?,?,?,?,?,?,?)", ("cpp", "digital", 50, T(10), T(10, 50), T(10, 50), "done", "partial", .6))
con.commit()
sid = cur.lastrowid
for i in range(0, 50 * 60, 30):
    db.add_event(con, "laptop", "window", {"app": "Google Chrome", "title": EVIL + "learncpp", "url": ""}, session_id=sid, ts=T(10) + i)
signals.store(con, "mac", "media", {"app": "Google Chrome", "title": EVIL + "Lo-fi", "playing": True}, ts=T(10, 5))
signals.store(con, "mac", "media", {"app": "Google Chrome", "playing": False}, ts=T(10, 35))
# a 45-minute call, written on change exactly like the Mac sensor
signals.store(con, "mac", "meeting", {"camera": True, "mic": True, "app": "Zoom"}, ts=T(16, 10))
signals.store(con, "mac", "meeting", {"camera": False, "mic": False}, ts=T(16, 55))

d = c.get(f"/api/signals?day={day.isoformat()}").json()
tl = d["timeline"]
check(len(tl) > 400 and min(x["ts"] for x in tl) < T(1), f"day timeline is the whole day ({len(tl)} rows, from 00:xx), not the last 400")
check(d.get("from_ts") is None, "nothing trimmed on a normal day (from_ts null)")
check(any(x["kind"] == "pickup" and x["ts"] == T(7) for x in tl) and sum(x["kind"] == "location" for x in tl) == 2,
      "morning pickup and the geofence leave/return survive")
ends = [x for x in tl if x["kind"] == "meeting"]
check(len(ends) == 2 and not ends[0].get("end") and ends[1].get("end") and ends[1]["ts"] == T(16, 55),
      "meeting off row reaches the timeline as end=True")
check(any(x["kind"] == "media" and x.get("end") for x in tl), "media stopped row reaches the timeline as end=True")

# --- in a browser -----------------------------------------------------------------------------------------------------
try:
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch()
except Exception as e:  # no browser here (sandbox / not installed): the API and static checks above still ran
    print(f"  SKIP  browser checks: {str(e).splitlines()[0][:120]}")
    print("signals lanes OK")
    sys.exit(0)

BASE = "http://alibi.test"


def answer(route):
    u = urllib.parse.urlsplit(route.request.url)
    if u.netloc != "alibi.test":
        return route.abort()
    r = c.get(u.path + (("?" + u.query) if u.query else ""))
    route.fulfill(status=r.status_code, body=r.content, headers={"content-type": r.headers.get("content-type", "text/plain")})


try:
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.route("**/*", answer)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/signals?day={day.isoformat()}")
    page.wait_for_selector("#plot svg [data-kind=meeting]", timeout=15000)
    page.wait_for_timeout(300)
    n = page.evaluate("""() => { const tip = document.getElementById('tip'); const out = [];
        for (const el of document.querySelectorAll('[data-tip]')) {
          el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
          out.push(tip.textContent); }
        return {n: out.length, evil: out.filter(t => t.includes('<img src=x onerror')).length,
                imgs: document.querySelectorAll('#tip img, #plot img').length, pwn: window.__pwn === 1}; }""")
    check(n["n"] > 100 and not errors, f"hovered every mark ({n['n']}), no page errors {errors[:2]}")
    check(not n["pwn"] and n["imgs"] == 0, "hostile titles never run (window.__pwn unset, no <img> in the tooltip)")
    check(n["evil"] >= 3, f"hostile titles show as literal text in tooltips ({n['evil']} marks)")
    m = page.evaluate("""() => [...document.querySelectorAll('[data-kind=meeting]')].map(r => [r.dataset.tt, +r.getAttribute('width')])""")
    hour = page.evaluate("""() => { const xs = [...document.querySelectorAll('#plot svg line')].map(l => +l.getAttribute('x1')).filter(v => v > 0);
        const s = [...new Set(xs)].sort((a, b) => a - b); return s[2] - s[1]; }""")
    check(len(m) == 1 and m[0][0] == "16:10–16:55" and m[0][1] > hour * 0.7,
          f"45-min call drawn as one 16:10–16:55 span ({m}, hour={hour:.0f}px)")
    md = page.evaluate("""() => [...document.querySelectorAll('[data-kind=media]')].map(r => r.dataset.tt)""")
    check(md == ["10:05–10:35"], f"media drawn from start to stop ({md})")
    lanes = page.evaluate("""() => [...document.querySelectorAll('#plot .lane-empty')].map(t => t.textContent)""")
    check(not any(x in lanes for x in ("No motion or pickups", "No geofence events", "No heart readings")),
          f"morning lanes are populated (empty: {lanes})")
    tips = page.evaluate("""() => [...document.querySelectorAll('[data-tip]')].map(e => (e.dataset.tt || '') + ' ' + e.dataset.tip)""")
    check(any(t.startswith("07:00 ") and "Picked up" in t for t in tips), "07:00 pickup has a mark")
    check(any(t.startswith("10:") and "learncpp" in t and EVIL in t for t in tips), "screen lane carries the window title, literally")
    check("No sessions this day" not in lanes and "No screen sessions" not in lanes, "session band + screen lane drawn")
    check(any("Phone away from home" in t and t.startswith("08:00") for t in tips), "08:00–09:00 away-from-home span drawn")
    if "--shot" in sys.argv:
        page.screenshot(path=sys.argv[sys.argv.index("--shot") + 1], full_page=True)
finally:
    browser.close(); pw.stop()
print("signals lanes OK")
