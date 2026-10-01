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

`GET /api/phone/session` on the phone listener (secret) → `{active, habit, ends_at, shield: bool, sync_every_s,
capabilities: {say: true, end: true, ask: false}, ...}`.

## Phone → Mac writes (alibi/routes_phone.py, on the phone listener)

| endpoint | body | answer |
|---|---|---|
| `POST /api/phone/say` | `{op_id, client_ts, text}` | `{ok, reply, session}`; `409 stale_start` if the text is a start and `now − client_ts > 120 s` |
| `POST /api/phone/session/end` | `{op_id, client_ts, session_id, artefact?}` | `{ok, reply, session}`; `409 already_ended` if `session_id` isn't the live one. More than 30 s late → `ended_at = clamp(client_ts, started_at, now)` |

`session` is the `/api/phone/session` core (`active, habit, label, session_id, started_at, ends_at, shield, on_break,
sync_every_s`). Errors are `{ok: false, error, reply, session}`. Rules: `X-Alibi-Secret` header only (`?key=` → 401);
source must be loopback or tailnet (`100.64.0.0/10`, `fd7a:115c:a1e0::/48`; `tailscale serve` arrives as loopback),
anything else, including LAN `192.168.*`/`10.*`/`172.16–31.*`, → 403, so the phone must use its **tailnet** endpoint
for writes; body ≤ 16 KB (413); 30 writes a minute (429). `op_id` (1–128 of `[A-Za-z0-9_.:-]`) is deduped under one
lock spanning check → execute → record; a retry gets the first answer (header `X-Alibi-Replay: 1`). The last 500 ops
are kept in `integrations.state()["phone_ops"]`. `client_ts` is unix seconds from the phone at the moment of the tap.
The Mac also toggles an "Alibi" Focus via `shortcuts run "Alibi Focus On|Off"` if those Shortcuts exist (Focus shares to
the iPhone; the companion's Focus filter then shields apps and syncs every few minutes).

## Fusion (alibi/signals.py)

`signals.timeline(con, session)` → ordered evidence `[{ts, source, kind, verdict_hint: on_task|off_task|absent|neutral, text}]`.
Hints: phone screentime/pickup during a desk session → off_task; phone walking/automotive/at_home=false → absent;
mac idle_s > 300 on a digital habit → idle; meeting on → neutral (labelled); notifications → neutral (context);
health heart → neutral (shown on the timeline). The verifier may use hints to *lower* a score with a stated reason;
it never raises a score from phone/mac signals alone.

## Streams: what leaves the Mac (`signals.egress()`, `GET /api/signals/egress`)

Derived at call time from config plus a reachability probe of each self-hosted server (`GET {base}/models`, 2 s
timeout, any HTTP answer = up, no token sent, cached 60 s). `{now, rows: [{what, where, active, host, why}], summary:
{where, active, text, leaves_tailnet}}`. `where` is `mac` | `tailnet:spark` | `nvidia_build` | `search_provider`;
`host` is a bare host name or null, never a URL, key or value.

| what | where | why (exact) |
|---|---|---|
| Camera frames | `mac` for `VISION_BACKEND=apple`/`mock` or a loopback VLM; else `tailnet:spark` / `nvidia_build` | "Frames never leave the Mac." only when `mac` |
| Habit names and minutes | `mac` with no model; else by `LLM_BASE_URL` host | "Habit names and minutes go to your Spark over Tailscale." |
| Ask questions | by `NEMOCLAW_URL` host (row only when set) | "Your questions go to NemoClaw on your Spark over Tailscale." |
| Search questions | `search_provider` (row only when `NEMOCLAW_URL` is set) | "Search questions go to the search provider." |
| Window titles, app names, coordinates, notification text | `mac` | "Never sent." |

A row whose server isn't answering stays (UI dims it) with `active: false`; the summary then reads `mac`.

`GET /api/signals/hourly?keys=phone.pickup,mac.git&hours=24` → `{hours, series: {key: [int × hours]}}`: rows per
hour, oldest first, current hour last (a reporting read, like `live()`).

Status: the `mac.git` row is `waiting` ("No commits in the last N h.") when repos are configured but quiet; `missing`
only when no repo is configured.
