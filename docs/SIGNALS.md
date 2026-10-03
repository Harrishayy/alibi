# Signals contract

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
| phone | shield | `{on: bool, apps: n}` | Opal-style blocking applied/removed; `on: true` = the picked apps are blocked (the agent context's `phone_blocked`) |
| phone | focus | `{on: bool, name: "Alibi"}` | Focus filter activated/deactivated |
| phone | location | `{at_home: bool}` | geofence enter/exit only; no coordinates ever leave the phone |
| phone | app | `{opened: bool, reason}` | companion app lifecycle (`reason` `foreground`/`background`: freshness only), or an iPhone Shortcut automation naming the app just opened (`{opened: true, reason: "YouTube"}`): during a session that nudges at once, see below |

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

**Phone app-open nudge** (`signals.nudge_reason`, every tick): a `phone/app` row with `opened: true` and a named
`reason` that arrived after the last nudge gives `("phone", "You said {habit}. Your phone just opened {reason}.")`.
`reason` is cut to 40 characters with braces stripped; `foreground`/`background` never count. The nudge cooldown
applies as for any nudge.

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

## Phone push (`alibi/notify.py`, ntfy)

Off while `NTFY_TOPIC` is empty (tests pin it empty). Otherwise every `notify()` of a pushed kind also goes to the ntfy
app on the phone: `POST {NTFY_URL}` (default `https://ntfy.sh`, the server root) with a JSON body
`{topic, title, message, priority, tags}`. JSON, never a `Title` header: a header sends "·" as latin-1 byte 0xB7.

| kind | priority | tag |
|---|---|---|
| `nudge` | 5 (urgent: the alarm) | `rotating_light` |
| `verdict` | 3 | `white_check_mark` |
| `digest` | 3 | `memo` |
| `report` | 3 | `crescent_moon` |
| `planned` | 3 | `alarm_clock` |
| `brief` | 3 | `memo` |

The kind alone decides: `info` (including "Strava: … logged."), `recap`, `pace` and `synced` never push, whatever
their source. `title` is "Alibi · your agent" for a `brief`, or an alert whose `source` or `via` is `nemoclaw`;
otherwise "Alibi". Delivery runs on a daemon thread (5 s timeout) and never raises; a failure prints
`[alibi] phone push failed: <ExceptionName>`, never the topic. The topic works like a password: keep it long and random.

`message` is the alert text exactly as the island shows it. A window nudge or a verdict names what the screen was
through `verifier.short_title`: a known app or site ("YouTube"), the app name, or, for a browser tab on an unknown site,
a piece of the tab title: its last segment, or the whole title, when that's 24 characters or fewer (else the browser's
name). The callers pass no URL, so it's the title, not the URL's host: "Still C++? Your screen has been Flat viewing
notes for 2 minutes." A phone nudge names the iPhone app. So with ntfy on, short window titles and app names leave the
Mac for the ntfy server, and the egress view says so.

## Streams: what leaves the Mac (`signals.egress()`, `GET /api/signals/egress`)

Derived at call time from config plus a reachability probe of each self-hosted server (`GET {base}/models`, 2 s
timeout, any HTTP answer = up, no token sent, cached 60 s). `{now, rows: [{what, where, active, host, why}], summary:
{where, active, text, leaves_tailnet}}`. `where` is `mac` | `tailnet:spark` | `nvidia_build` | `search_provider` | `strava` | `ntfy`;
`host` is a bare host name or null, never a URL, key or value.

| what | where | why (exact) |
|---|---|---|
| Camera frames | `mac` for `VISION_BACKEND=apple`/`mock` or a loopback VLM; else `tailnet:spark` / `nvidia_build` | "Frames never leave the Mac." only when `mac` |
| Habit names and minutes | `mac` with no model; else by `LLM_BASE_URL` host | "Habit names and minutes go to your Spark over Tailscale." |
| Ask questions | by `NEMOCLAW_URL` host (row only when set) | "Your questions go to NemoClaw on your Spark over Tailscale." |
| Search questions | `search_provider` (row only when `NEMOCLAW_URL` is set) | "Search questions go to the search provider." |
| Strava runs | `strava`, host `www.strava.com` (row only when a Strava app or token is set up; `active` = connected) | "Alibi sends your Strava token to strava.com and reads your runs back." |
| Alerts on your phone | `ntfy`, host of `NTFY_URL` (row only while `NTFY_TOPIC` is set) | "Nudges, verdicts, runs and briefs go to your phone through ntfy, the same text the island shows. A nudge or verdict can name the app, site or short window title you drifted to." |
| Window titles, app names and what you type | by `LLM_BASE_URL` host (row only while a text model is set up) | "Window titles, app names and what you type go to NVIDIA Build." (or "… to your Spark over Tailscale.") |
| Coordinates, notification text | `mac` (row while a text model is set up or `NTFY_TOPIC` is set) | "Never sent. Location reaches this Mac only as home or away, and notifications only as counts." |
| Window titles, app names, coordinates, notification text | `mac` (row only with no text model and no `NTFY_TOPIC`) | "Never sent. They are read on this Mac and stay here." |

With a text model, window titles do leave: `verifier.classify_titles` sends "App — title" keys, and `intent.parse` sends
the sentence you typed. With ntfy on, they leave in the pushes: a nudge or verdict names the app, site or short window
title (see Phone push). "Never sent" is said of titles and app names only while neither is set up.

A row whose server isn't answering stays (UI dims it) with `active: false`; the summary then reads `mac`.
`leaves_tailnet` is true when any active row goes to `nvidia_build`, `search_provider`, `strava` or `ntfy`.

`GET /api/signals/hourly?keys=phone.pickup,mac.git&hours=24` → `{hours, series: {key: [int × hours]}}`: rows per
hour, oldest first, current hour last (a reporting read, like `live()`).

Status: the `mac.git` row is `waiting` ("No commits in the last N h.") when repos are configured but quiet; `missing`
only when no repo is configured.

## Agent context (`GET /api/agent/context` on the phone listener, `alibi/routes_agent.py`)

Read by NemoClaw on the Spark (mirrored by the relay). Aggregates only: no frames, titles, app names, URLs,
coordinates or notification text (`never_included`). Each key below is built on its own and falls back to `[]`, so
`/context` never fails because of one bad row.

| key | rows |
|---|---|
| `today.phone_last_synced` | the newer of the phone's last `/ingest` batch and last foreground poll: "HH:MM" today, "Ddd HH:MM" otherwise, `null` if never |
| `sessions_today` | sessions started today (local), oldest first: `{habit, label, at: "HH:MM", min, verdict, nudges, phone_blocked}`. `min` = (ended_at or now − started_at) / 60, rounded; `verdict` is `null` while live; `nudges` counts `alibi/nudge` events; `phone_blocked` is true if any `phone/shield` row in the session has `on: true` |
| `claims_today` | today's `user/claim` events: `{habit, label, at, km, verified, settled_at}`. `km` = the first Strava run of at least `min_km` from 10 min before the claim to `until` (as `daemon.check_claims` matches it), else `null`; `verified` and `settled_at` ("HH:MM") come from `alibi/claim_settled`, `null` while open |
| `away` | `calendar_sync.away_days(today, 14)` as `{date, label}` when that helper exists, else `[]` |
| `focus` | `focus.agent_summary()`: `{yesterday, today_so_far}`, each `{date, phone, pickups, peak: {hour, pickups}, avg_7d, vs_avg_pct, in_blocks: {pickups, blocks, minutes}, by_habit: [{habit, label, state, pickups, per_hour, mac_distraction_min}], mac: {distraction_min, notifications}, screen_time_picked_min, recommendations: [{habit, text, why}], line}`, counted by code from `phone/pickup`, `laptop/window`, `mac/notifications`, Screen Time and the plan. `phone: false` makes every phone number `null`, never 0. `vs_avg_pct` needs 3 earlier days the phone covered in full (rows 12 h apart) and a like-for-like average of 10 or more. Rules say "video sites" or "social apps", never a site or app name. A focus bug makes the key `null`, never the whole `/context` |
