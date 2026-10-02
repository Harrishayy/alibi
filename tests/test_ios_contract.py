"""iPhone companion ↔ docs/SIGNALS.md contract (static; no Xcode needed).

Every iPhone row the companion writes must use the contract's source/kind and payload keys, the background task IDs
must match Info.plist, every permission the app asks for must have a usage string, and the Screen Time extension point
must be implemented: Family Controls entitlement, the DeviceActivity monitor / shield extensions embedded in the app,
5-minute usage thresholds, and phone.screentime / phone.shield rows the Mac accepts.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
IOS = ROOT / "ios"
SWIFT_DIRS = ("AlibiPhone", "Shared", "AlibiActivityMonitor", "AlibiShieldConfig", "AlibiShieldAction")
SRC = "\n".join(p.read_text() for d in SWIFT_DIRS if (IOS / d).is_dir() for p in sorted((IOS / d).rglob("*.swift")))
YML = (IOS / "project.yml").read_text()
DOC = (ROOT / "docs" / "SIGNALS.md").read_text()
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


# 1. Parse the iPhone table: | source | kind | `payload` | notes |
section = DOC.split("## iPhone", 1)[1].split("\n## ", 1)[0]
contract = {}
for line in section.splitlines():
    m = re.match(r"\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*`(.+?)`\s*\|", line)
    if m:
        payload = m.group(3)
        top = re.sub(r"\[[^\]]*\]", "", re.sub(r"\{[^{}]*\}", "", payload[1:-1]))   # drop nested objects/lists
        contract[(m.group(1), m.group(2))] = [k.strip().rstrip("?") for k in re.findall(r"(\w+\??)\s*:", top)]
check(len(contract) >= 9, f"expected >= 9 iPhone rows in SIGNALS.md, parsed {len(contract)}")

for (source, kind), keys in contract.items():
    # The app writes rows with row(source, kind, ...); the Screen Time extensions queue phone rows with push(kind:).
    written = re.search(rf'row\("{source}", "{kind}"', SRC) or (source == "phone" and re.search(rf'push\(kind: "{kind}"', SRC))
    check(written, f"{source}.{kind}: no row(\"{source}\", \"{kind}\", ...) in ios/")
    for k in keys:
        check(f'"{k}"' in SRC, f"{source}.{kind}: payload key {k!r} never written")

# Nested health.samples keys (sleep stages, workouts, moods).
for k in ("core_h", "deep_h", "rem_h", "awake_h", "bed", "wake", "start", "min", "km", "avg_hr", "kcal", "valence", "labels"):
    check(f'"{k}"' in SRC, f"health.samples nested key {k!r} missing")

# 2. Sync engine speaks the batch protocol, the session endpoint and the secret header.
check('["batch": rows]' in SRC, "SyncEngine must POST {batch: [...]}")
check("/api/phone/session" in SRC, "SyncEngine must poll /api/phone/session")
check("X-Alibi-Secret" in SRC, "requests must carry X-Alibi-Secret")
check(re.search(r"maxBatch\s*=\s*(\d+)", SRC) and int(re.search(r"maxBatch\s*=\s*(\d+)", SRC).group(1)) <= 500,
      "batches must be <= 500 rows")

# 3. Background task IDs registered in code are permitted in Info.plist.
for tid in re.findall(r'(?:refreshID|processingID)\s*=\s*"([^"]+)"', SRC):
    check(tid in YML, f"BG task id {tid} not in BGTaskSchedulerPermittedIdentifiers")

# 4. Usage strings for everything the app touches.
need = {"HealthKit": "NSHealthShareUsageDescription", "CoreMotion": "NSMotionUsageDescription",
        "CoreLocation": "NSLocationAlwaysAndWhenInUseUsageDescription"}
for framework, key in need.items():
    if f"import {framework}" in SRC:
        check(key in YML, f"{framework} used but {key} missing from project.yml")
check("NSLocationWhenInUseUsageDescription" in YML, "NSLocationWhenInUseUsageDescription missing")
check("group.app.theultras.alibi" in YML and "group.app.theultras.alibi" in SRC, "App Group must be declared and used")

# 5. Extension points.
check(re.search(r"protocol ShieldController\b.{0,600}?func apply\(on: Bool(, source: String)?\)", SRC, re.S),
      "ShieldController.apply(on:) missing")
check((IOS / "AlibiPhone" / "ScreenTime").is_dir(), "ios/AlibiPhone/ScreenTime/ folder missing")
check("SetFocusFilterIntent" in SRC, "Focus filter intent missing")
check(".immediate" in SRC and "HKObserverQuery" in SRC, "Health background delivery (.immediate observers) missing")
check("CLMonitor" in SRC, "home geofence (CLMonitor) missing")
# No coordinates in any row we send.
for m in re.finditer(r'row\("phone", "location",[^\n]*', SRC):
    check("lat" not in m.group(0) and "lon" not in m.group(0), "phone.location must never carry coordinates")

# 5b. Screen Time (Family Controls): entitlement everywhere, extensions embedded, thresholds, real shield, failsafe.
check(YML.count("com.apple.developer.family-controls: true") >= 4, "family-controls entitlement on the app + 3 extensions")
for point, cls in (("com.apple.deviceactivity.monitor-extension", "AlibiActivityMonitor"),
                   ("com.apple.ManagedSettingsUI.shield-configuration-service", "AlibiShieldConfig"),
                   ("com.apple.ManagedSettings.shield-action-service", "AlibiShieldAction")):
    check(point in YML, f"{point} extension missing from project.yml")
    check(f"- target: {cls}" in YML, f"{cls} not embedded in the app (dependencies)")
    check(re.search(rf"class {cls}\b", SRC), f"principal class {cls} missing")
check("requestAuthorization(for: .individual)" in SRC, "Screen Time must ask for .individual authorization")
check("familyActivityPicker" in SRC, "FamilyActivityPicker missing")
check("ManagedSettingsStore(named:" in SRC and "shield.applications" in SRC, "ManagedSettingsStore shields missing")
check(re.search(r"stepMin\s*=\s*5\b", SRC) and re.search(r"maxMin\s*=\s*120\b", SRC), "thresholds must be 5..120 min")
check("eventDidReachThreshold" in SRC and "intervalDidEnd" in SRC, "monitor must record thresholds and the failsafe end")
check("Shields.current = ScreenTimeShield.shared" in SRC, "real ShieldController not registered at launch")
check('source: "session"' in SRC and 'source: "focus"' in SRC, "session poller and Focus filter must both drive the shield")
check("drainExtension()" in SRC, "SyncEngine must ship rows the extensions queued")
# Extensions must not do networking (they can't, reliably); only the app talks to the Mac.
for d in ("AlibiActivityMonitor", "AlibiShieldConfig", "AlibiShieldAction", "Shared"):
    for f in (IOS / d).rglob("*.swift"):
        check("URLSession" not in f.read_text(), f"{f.name}: extensions must not network")

# 6. Rows shaped exactly like the app's are accepted by the Mac's phone listener (one batch, nothing rejected).
sys.path.insert(0, str(ROOT / "tests"))
import time  # noqa: E402
import harness  # noqa: E402,F401  (temp data dir before alibi is imported)
from alibi import db, integrations  # noqa: E402

now = time.time()
today = time.strftime("%Y-%m-%d")
app_rows = [
    {"source": "health", "kind": "samples", "ts": now - 3600, "payload": {
        "date": today, "steps": 8123.0, "distance_km": 6.1, "flights": 4.0, "active_kcal": 410.0, "exercise_min": 32.0,
        "stand_h": 9.0, "daylight_min": 41.0, "resting_hr": 58.0, "hrv_ms": 47.0, "resp_rate": 14.5, "headphone_db": 71.0,
        "sleep_h": 7.25, "sleep": {"core_h": 4.1, "deep_h": 1.2, "rem_h": 1.9, "awake_h": 0.3, "bed": "23:40", "wake": "07:05"},
        "mindful_min": 10.0, "workout_min": 31.0,
        "workouts": [{"type": "Run", "start": "07:30", "min": 31.0, "km": 5.02, "avg_hr": 151.0, "kcal": 320.0}],
        "moods": [{"ts": now - 7200, "valence": 0.4, "labels": ["calm", "content"]}]}},
    {"source": "health", "kind": "heart", "ts": now - 60, "payload": {"samples": [[now - 120, 72.0], [now - 60, 75.0]]}},
    {"source": "phone", "kind": "motion", "ts": now - 900,
     "payload": {"start": now - 900, "end": now - 300, "state": "stationary", "confidence": "high"}},
    {"source": "phone", "kind": "pickup", "ts": now - 300, "payload": {"ts": now - 300}},
    {"source": "phone", "kind": "location", "ts": now - 200, "payload": {"at_home": True}},
    {"source": "phone", "kind": "focus", "ts": now - 100, "payload": {"on": True, "name": "Alibi"}},
    {"source": "phone", "kind": "app", "ts": now - 50, "payload": {"opened": True, "reason": "foreground"}},
    # Exactly what AlibiShared.recordUsage / ScreenTimeShield.post write.
    {"source": "phone", "kind": "screentime", "ts": now - 40, "payload": {"app": "Picked apps", "minutes": 15, "threshold_min": 5}},
    {"source": "phone", "kind": "shield", "ts": now - 30, "payload": {"on": True, "apps": 4}},
    {"source": "phone", "kind": "shield", "ts": now - 20, "payload": {"on": False, "apps": 0}},
]
if hasattr(integrations, "ingest_body"):
    res = integrations.ingest_body(db.connect(), {"batch": app_rows})
    check(res.get("saved") == len(app_rows) and not res.get("rejected"), f"listener rejected app rows: {res}")
    check(isinstance(res.get("session"), dict) and "sync_every_s" in res["session"], "batch reply should carry session info")
    stored = integrations.health_days(db.connect()).get(today) or {}
    check(stored.get("sleep", {}).get("bed") == "23:40" and stored.get("workouts"), f"health extras not kept: {stored}")

# 7. Review fixes: regressions are cheap to reintroduce, so pin them.
HEALTH = (IOS / "AlibiPhone" / "Sensors" / "Health.swift").read_text()
SYNC = (IOS / "AlibiPhone" / "Sync" / "SyncEngine.swift").read_text()
PERMS = (IOS / "AlibiPhone" / "Views" / "Permissions.swift").read_text()
SHARED = (IOS / "Shared" / "AlibiShared.swift").read_text()
# 7a. Health observers/background delivery start after the permission sheet (once per process), errors surfaced.
check("func startObservers()" in HEALTH and "HKObserverQuery" in HEALTH and "observersStarted" in HEALTH,
      "Health.startObservers() (guarded once per process) must own the observer setup")
check("HKObserverQuery" not in SYNC, "observers must not be registered unconditionally from registerBackground()")
check(re.search(r"asked\(\)\s*\{\s*Health\.shared\.startObservers\(\)", SYNC),
      "launch must start observers only when Health was already asked")
check(re.search(r"try await Health\.shared\.authorize\(\)\s*\n\s*Health\.shared\.startObservers\(\)", PERMS),
      "requestHealth() must start observers right after authorization")
check("enableBackgroundDelivery(for: type, frequency: .immediate) { _, _ in }" not in HEALTH,
      "enableBackgroundDelivery errors must not be ignored")
# 7b. Only 400/422 fall back to per-row; 404/405 mean the endpoint is wrong; per-row non-200 non-400/422 fails.
pb = SYNC.split("func postBatch", 1)[1].split("// MARK:", 1)[0]
check("case 400, 422:" in pb and "404" not in pb.split("case 400, 422:")[0] and "case 400, 404" not in pb,
      "batch fallback must be limited to 400/422")
check('d["saved"] != nil' in pb, "a batch 200 must be an Alibi reply ({saved: n}) before the endpoint is trusted")
row_loop = pb.split("for r in rows", 1)[1]
check("default: throw SyncError.unreachable" in row_loop, "per-row loop must fail on any unexpected status")
# The Mac's replies really carry what the app checks for.
if hasattr(integrations, "ingest_body"):
    one = integrations.ingest_body(db.connect(), {"batch": [app_rows[3]]})
    check("saved" in one, f"batch reply lacks 'saved': {one}")
# 7c. Restarting Screen Time monitoring mid-day must not zero today's floor (replayed thresholds = phantom minutes).
rd = SHARED.split("static func resetDay", 1)[1].split("\n    }\n", 1)[0]
check("!= today(now) else { return false }" in rd, "resetDay() must only reset when the stored day is not today")


if fails:
    print("\n".join("FAIL " + f for f in fails))
    sys.exit(1)
print(f"ios contract OK ({len(contract)} iPhone rows checked)")
