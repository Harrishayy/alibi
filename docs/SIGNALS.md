# Signals contract (round 3)

Every new data point is an `events` row. **No SQL schema change.** `source` + `kind` + `payload` below are the contract;
writers and readers must match exactly. Timestamps are unix seconds (float). Phone rows arrive via the phone listener
`POST /ingest` (X-Alibi-Secret) as `{"source": ..., "kind": ..., "ts"?: ..., "payload": {...}}` or as a batch
`{"batch": [ {source, kind, ts, payload}, ... ]}` (≤ 500 rows). Rows are attached to the active session if their `ts`
falls inside it (writer passes `ts`; the store decides `session_id`).

## iPhone (ios/AlibiPhone — companion app)

| source | kind | payload | notes |
|---|---|---|---|
| health | samples | `{date, steps, distance_km, flights, active_kcal, exercise_min, stand_h, sleep_h, sleep: {core_h, deep_h, rem_h, awake_h, bed: "HH:MM", wake: "HH:MM"}, resting_hr, hrv_ms, resp_rate, mindful_min, daylight_min, headphone_db, workout_min, workouts: [{type, start, min, km?, avg_hr?, kcal?}], moods: [{ts, valence, labels: [..]}]}` | one per day, latest wins (existing contract, extended; unknown keys kept) |
| health | heart | `{samples: [[ts, bpm], ...]}` | Watch heart-rate samples since last sync |
| phone | motion | `{start, end, state: stationary|walking|running|automotive|cycling|unknown, confidence: low|medium|high}` | CMMotionActivity segments since last sync |
| phone | pickup | `{ts}` | phone moved after ≥ 2 min stationary (best-effort) |
| phone | screentime | `{app: <label or "Picked app">, category?, minutes: <cumulative today>, threshold_min}` | DeviceActivity threshold events (every 5 min of picked apps) |
| phone | shield | `{on: bool, apps: n}` | Opal-style blocking applied/removed |
| phone | focus | `{on: bool, name: "Alibi"}` | Focus filter activated/deactivated |
| phone | location | `{at_home: bool}` | geofence enter/exit only; no coordinates ever leave the phone |
| phone | app | `{opened: bool, reason}` | companion app lifecycle (debug/freshness) |

## Mac (alibi/mac_signals.py + bin/alibi-sense)

| source | kind | payload |
|---|---|---|
| mac | presence | `{idle_s, locked, display_asleep}` (every 30 s while a session runs, every 5 min otherwise) |
| mac | media | `{app, title?, playing: bool}` (Music, Spotify, browser video if detectable) |
| mac | meeting | `{camera: bool, mic: bool, app?}` (camera/mic in use by *another* app) |
| mac | focus | `{on: bool, mode?}` |
| mac | notifications | `{app, count, phone: bool, window_s}` (counts per app since last poll; never message text) |
| mac | switches | `{per_min, apps: [..]}` (app-switch rate from laptop window events, derived) |
| mac | git | `{repo, commits, files, insertions, deletions}` |

## Session → phone (near-live)

`GET /api/phone/session` on the phone listener (secret) → `{active, habit, ends_at, shield: bool, sync_every_s}`.
The Mac also toggles an "Alibi" Focus via `shortcuts run "Alibi Focus On|Off"` if those Shortcuts exist (Focus shares to
the iPhone; the companion's Focus filter then shields apps and syncs every few minutes).

## Fusion (alibi/signals.py)

`signals.timeline(con, session)` → ordered evidence `[{ts, source, kind, verdict_hint: on_task|off_task|absent|neutral, text}]`.
Hints: phone screentime/pickup during a desk session → off_task; phone walking/automotive/at_home=false → absent;
mac idle_s > 300 on a digital habit → idle; meeting on → neutral (labelled); notifications → neutral (context);
health heart → neutral (shown on the timeline). The verifier may use hints to *lower* a score with a stated reason;
it never raises a score from phone/mac signals alone.
