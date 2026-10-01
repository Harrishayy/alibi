# Alibi — the habit tracker that checks your alibi

> You tell it what you're about to do. It watches the evidence (desk camera, laptop, Strava, phone, Health). The habit only gets ticked if the evidence agrees.

**One sentence for judges:** For anyone who writes habits down and quietly lies to the tracker, Alibi is a long-running agent that verifies each session with real evidence and tells you every night whether you're actually aligned with your goals.

**Deadline:** applications close **Oct 2, 2026** — check the exact cut-off time on the Airtable form before you start, and plan to submit with buffer.

---

## 1. Rules of this build (why 0→1 stalled before, and how we avoid it)

1. **Vertical slices, not layers.** Every prototype is a full loop: input → agent → output you can see. Never spend an hour on "infrastructure" that shows nothing.
2. **Freeze the contract first.** Two tables (`sessions`, `events`) are the only interface. Every data source *writes events*; only the verifier *reads* them. Adding Strava or Health never touches the verifier. Schema lives in `alibi/db.py` — don't change it after P0 unless forced.
3. **Done = a command and an output.** Each prototype has a *Definition of Done* (DoD): a command you run and what you must see. "Code written" is not done.
4. **Tag every working state.** At each DoD: `git add -A && git commit -m "pN works" && git tag pN`. If the next prototype goes sideways: `git stash` and you're back to something demoable.
5. **Record as you go.** At each DoD, record a 10–15 s screen/phone clip into `demo/clips/`. The final video is just these clips stitched — you're never left with "it works but I have nothing to show".
6. **Timebox hard.** When the box runs out, hardcode, fake, or cut — then move on. A hardcoded habit list that works beats a general parser that doesn't.
7. **Fake inputs before real ones.** P1 can run on a pre-recorded video file before the live webcam. Strava can be tested on a JSON fixture before OAuth.

---

## 2. Architecture

```
 OBSERVERS (write events)              CORE                         SURFACES
 ┌──────────────────────┐
 │ camera.py   (P1)     │──┐
 │ laptop_logger (P3)   │──┤      ┌──────────────┐   ┌──────────┐   ┌───────────────────┐
 │ strava.py   (P5)     │──┼────► │ SQLite       │──►│ verifier │──►│ notify: chat/     │
 │ webhook.py  (P6)     │──┘      │ sessions     │   │ evidence │   │ macOS / Telegram  │
 │  (phone, Health)     │         │ events       │   └──────────┘   │ OpenClaw (P2)     │
 └──────────────────────┘         └──────▲───────┘        │         └───────────────────┘
                                         │                ▼
                     cli.py: start / status / end / report   report.py (P4, nightly)
                                         ▲
                              daemon.py — the long-running process:
                              owns timers, camera sampling loop, nudges, nightly report
```

**Key design decision:** `daemon.py` owns everything time-based (session timers, sampling, nudges, nightly report). The chat layer (OpenClaw or Telegram) is just a front-end that calls the CLI. So if OpenClaw setup fights you, the core still works and is still long-running.

---

## 3. Data contract (frozen after P0)

```
sessions(id, habit, modality[physical|digital|hybrid], declared_min,
         started_at, ends_at, ended_at, status[active|done],
         on_task_ratio, verdict[done|partial|slacked], evidence_path, artefact)

events(id, ts, source[camera|laptop|phone|strava|health],
       kind[label|window|activity|focus|samples], session_id?, payload JSON)
```

Labels used everywhere (camera and laptop): `on_task | phone | idle | absent | off_task`.

Verdict: `on_task_ratio >= 0.7 → done`, `>= 0.4 → partial`, else `slacked` (thresholds in `habits.yaml`).

---

## 4. Pre-flight (10 min, before the clock starts)

- [ ] Get an API key at build.nvidia.com. Pick **one text model** and **one vision-language model**; copy their exact model IDs into `.env` (`cp .env.example .env`).
- [ ] `bash scripts/setup.sh` (venv + deps + data dirs).
- [ ] `python scripts/smoke_test.py` → must print a JSON reply from the text model **and** a JSON reply about a webcam frame from the VLM. **If the vision call fails, fix it now** (wrong model ID, model doesn't accept `image_url`) — everything in P1 depends on it.
- [ ] Grant camera permission to your terminal (macOS: System Settings → Privacy → Camera).
- [ ] Create the Strava API app now (strava.com/settings/api, callback domain `localhost`) so it's ready for P5.
- [ ] Point the camera at the desk. Check framing: hands + desk surface visible, your face optional.

---

## 5. Prototypes

Times are relative to T0. Total ≈ 2 h 45 min including demo and submission.

### P0 — Declare + timer (T0 → T+0:20)
**Goal:** "I'm going to draw for 1 hour" becomes a session with a timer that fires.

Build:
1. `db.py` is already written — run it once to create the DB.
2. `intent.py`: text LLM → `{habit, minutes, modality}`. Constrain `habit` to keys in `habits.yaml` (pass the list in the prompt; fall back to alias matching if the LLM output isn't a known key).
3. `cli.py start "<text>"` → insert session row, print it. `cli.py status` → active session + minutes left. `cli.py end` → mark done (no verdict yet).
4. `daemon.py`: loop every 5 s; if active session's `ends_at` passed → end it and call `notify("Time's up — let's see what you did.")`.
5. `notify.py`: start with print + macOS notification (`osascript -e 'display notification ...'`).

**DoD:** `python -m alibi.cli start "draw for 2 minutes"` with the daemon running → 2 min later a notification fires and `status` shows no active session.
**Clip:** typing the sentence → notification popping.
**If behind:** skip the LLM, use regex `(\d+)\s*(min|hour)` + alias lookup.

### P1 — Camera verification + evidence (T+0:20 → T+1:00) ← the core wow
**Goal:** during a physical session, the agent watches and gives a verdict with photographic evidence.

Build:
1. `camera.py`: OpenCV grab every 5 s. Every 60 s while a physical/hybrid session is active, take a sample:
   - Downscale to ~512 px wide, JPEG quality ~70, save to `data/frames/<session>/<ts>.jpg`.
   - **Motion gate:** compare 64×64 grayscale to the previous sample; if mean abs diff < threshold, **reuse the previous label** with no model call.
   - Otherwise call VLM with the declared habit + `on_task_looks_like` from `habits.yaml`; it must return `{"label": ..., "note": "<12 words"}`.
   - Write an `events` row (`source=camera, kind=label`).
2. `verifier.py`: at session end, `on_task_ratio = on_task samples / all samples`; verdict from thresholds.
3. `evidence.py`: contact sheet (PIL grid, ≤12 frames, each stamped with time + label, colour-coded border) → `data/evidence/<session>.jpg`; store path on the session.
4. Daemon calls verifier + evidence when the timer fires and notifies with the verdict.

**DoD:** 4-minute "drawing" session: draw 2 min, phone 1 min, leave 1 min → verdict ≈ 50 % `partial`, contact sheet shows green/red/grey frames.
**Clip:** split-screen of you slacking + the contact sheet appearing.
**If behind:** test on a pre-recorded video (`--source demo/test.mp4`) instead of the live cam; drop the motion gate.

> 🔖 **MVP line.** After P1 you have a submittable project. Everything after this makes it better, not possible.

### P2 — Agent shell + live nudges (T+1:00 → T+1:20)
**Goal:** talk to it in a chat; it nudges you mid-session when you drift.

Build:
1. **Path A (preferred, on-theme): OpenClaw.** Install via the challenge resources. Give the agent standing orders: when the user declares a habit → run `python -m alibi.cli start "<text>"`; "how am I doing" → `cli status`; "what did I do this week" → `cli report`. Send the evidence image path when a session ends.
2. **Path B (fallback, 10 min): Telegram bot** with the same four commands, plus free-text routed to `start`.
3. Nudge in the daemon: if the last N camera labels (`nudge_after_off_task_samples`, default 3) are not `on_task` → `notify("You said drawing. I've seen your phone for 3 minutes.")`. Max one nudge per 10 min.

**DoD:** you declare a session from your phone chat; you pick up your phone at the desk; within ~3 min the chat pings you.
**Clip:** the nudge arriving while you're scrolling — this is the funniest shot in the video.
**If behind:** Path B, or keep CLI + macOS notifications and show the daemon running in tmux.

### P3 — Laptop evidence for digital habits (T+1:20 → T+1:45)
**Goal:** C++/internship/math-on-laptop sessions verified without the camera and without asking you for links.

Build:
1. `laptop_logger.py`: every 30 s record frontmost app + window title (+ browser URL) → `events(source=laptop, kind=window)`. Runs always; costs nothing.
   - macOS: `osascript` via System Events (needs Accessibility permission once); Chrome/Safari URL via AppleScript.
   - Linux: X11 `xdotool getactivewindow getwindowname`; Hyprland `hyprctl activewindow -j`; KDE Wayland `kdotool`. Pick whichever your machine runs; don't fight it for more than 5 min.
2. Verifier for `digital` sessions: collect distinct titles in the session window, classify them **once each** in a single batch LLM call against the habit (cache in `title_cache`), weight by time spent → on_task_ratio.
3. Evidence = top 5 apps/titles by time + an optional artefact: at session end ask "what did you produce?" — accept a link, screenshot, or repo path (if repo, run `git diff --stat` for that window yourself).
4. `hybrid` (e.g. maths: notebook + laptop): a minute counts on-task if **either** camera or laptop says on-task.

**DoD:** 3-minute "C++" session: 2 min in VS Code + cppreference, 1 min on YouTube → ≈ 67 % `partial` with the title breakdown.
**Cut first if behind** (after P6, before P5) — the camera is the differentiator.

### P4 — Nightly alignment report (T+1:45 → T+2:05)
**Goal:** "Am I aligned?" answered every night without being asked.

Build:
1. `report.py`: for each habit in `habits.yaml` this week → verified minutes, sessions, verdict mix, streak, target vs actual → `aligned` / `behind by X`. Include Strava line once P5 exists.
2. One LLM call turns the table into 3 dry, honest sentences ("You declared 5 drawing hours; the camera saw 2.") — the tone is the personality of the project.
3. Daemon (or OpenClaw cron) fires it at 22:00 and posts text + the day's contact sheets.

**DoD:** `python -m alibi.cli report` prints the table + summary from today's real test sessions.
**Clip:** the report arriving in chat. This is the closing shot.

### P5 — Strava (T+2:05 → T+2:25)
**Goal:** running habit verified from real activity data.

Build:
1. OAuth once, by hand (no server needed):
   - Open `https://www.strava.com/oauth/authorize?client_id=ID&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=activity:read_all`
   - Approve → the browser lands on a dead localhost page; copy `code=` from the URL.
   - `python -m alibi.strava exchange <code>` → POST to `https://www.strava.com/oauth/token` (`grant_type=authorization_code`) → save `refresh_token` to `.env`.
   - Do this **while a P1 test session is running** so it costs no wall-clock time.
2. `strava.py sync`: refresh access token (`grant_type=refresh_token`), GET `/api/v3/athlete/activities?after=<monday epoch>` → `events(source=strava, kind=activity)` for runs.
3. Report rule from `habits.yaml`: runs/week ≥ N and each ≥ min_km.

**DoD:** `python -m alibi.strava sync` prints this week's runs; report shows `Running 2/3 — behind by 1`.
**If behind:** load a JSON fixture of your last few runs and say "live Strava sync" is wired but not shown.

### P6 — Phone + Apple Health (stretch, only if ahead)
- `webhook.py`: tiny FastAPI `POST /ingest` → events. Host it on the DGX Spark behind Tailscale so the phone can reach it privately.
- iOS Shortcuts personal automations: (a) Focus "Work" on/off → POST `{source: phone, kind: focus}`; (b) 21:30 daily: Find Health Samples (steps, sleep, workouts) → Get Contents of URL → POST.
- Report gains sleep/steps lines. **Cut first.** Mention as roadmap in the description.

---

## 6. Timeline and cut lines

| T+ | Doing | Checkpoint |
|---|---|---|
| −0:10 | Pre-flight | smoke test passes |
| 0:00 | P0 | tag `p0` |
| 0:20 | P1 (start daemon, leave it running from here on) | tag `p1` — **MVP** |
| 1:00 | P2 | tag `p2` |
| 1:20 | P3 | tag `p3` |
| 1:45 | P4 | tag `p4` |
| 2:05 | P5 | tag `p5` |
| 2:25 | Record + edit demo, write description, submit | submitted |

**Cut rules:**
- At **T+1:10**, if P1 isn't tagged → stop adding features. Fix P1, jump to P4 (report), then demo.
- At **T+2:00**, if P4 isn't tagged → skip P5, go straight to demo.
- Cut order when behind: P6 → P3 → P5 → P2-Path-A (use Telegram/CLI).
- Never cut: P0, P1, P4, the demo video.

---

## 7. Cost and privacy

- Zero model calls when no session is active. Laptop logger and Strava sync are free.
- Camera: 1 sample/min, motion-gated, ~512 px → a 1-hour session is ≤ 60 small VLM calls, usually far fewer.
- Titles are classified once each and cached.
- **Privacy note:** with NVIDIA Build endpoints, the downscaled frames *are* sent to the endpoint. For a "frames never leave my network" claim, point `VLM_BASE_URL` at a local OpenAI-compatible server on the DGX Spark — same code, one env var. Only say the stronger claim if you actually run it that way.

---

## 8. Demo video (60–90 s) — see `demo/shotlist.md`

Declare → timer → you drawing / on phone / gone → nudge arrives → verdict + contact sheet → "learn C++ for 30 min" → title verdict → nightly report "aligned on building, 1 run behind" → terminal showing daemon uptime + schedule.

## 9. Submission — see `submission.md` (draft description ready to paste)

---

## 10. Phase 2 — easy to use, then more capability (added 2026-10-01, after p6)

Same rules: vertical slices, DoD = a command + an output, tag each, `tests/run_all.sh` stays green.

### P7 — One-command life (`./alibi`) + Alibi.app
- `./alibi up|down|status|open|logs|test|demo|seed` at the repo root; pidfile in `data/`, `down` always turns the camera off.
- `Alibi.app` (double-click / Spotlight / login item). Camera + Accessibility permission get granted to *Alibi*, not your terminal.
**DoD:** `./alibi up` → `./alibi status` shows daemon + island running → `./alibi down` → nothing running.

### P8 — Island you never have to aim at
- Global hotkey **⌥⌘A** opens the island and focuses the prompt (Carbon hotkey, no extra permission).
- Idle island shows one-tap habit chips (`default_min` per habit in habits.yaml); quit button.
**DoD:** snapshot of the expanded idle island shows habit chips; hotkey registers without error.

### P9 — Setup without YAML
- `GET /api/health`: camera, window titles (Accessibility), witness, text model, Strava, island — each ok/needs-action with a one-line fix.
- `GET/PUT /api/habits`: edit habits + weekly targets from the dashboard (writes habits.yaml, keeps comments out of the way).
- Dashboard "Setup" drawer: health checklist + habits editor.
**DoD:** test PUTs a new habit → `intent.parse` recognises it; health lists every check.

### P10 — Memories reel (the original video idea)
- `alibi/reel.py`: a session's or a day's frames → H.264 timelapse with title card, timestamps and label colour bar.
- `GET /api/reel?session=ID` / `?date=YYYY-MM-DD`; dashboard plays it under the contact sheet; verdict alert links to it.
**DoD:** test builds a reel from the P1 fixture session → mp4 exists, plays in a browser (H.264), duration > 0.

### P11 — Annotations you can correct
- Click any label dot (dashboard) → relabel → `events(source='user', kind='correction')`; verifier honours corrections, re-scores the session, re-renders the contact sheet. The witness is fallible; *you* get the last word, on the record.
**DoD:** correct 2 phone samples to on_task → verdict moves from partial to done, contact sheet shows the "corrected" mark.

### P12 — Demo script + submit
- `./alibi demo`: fast scripted session (fixture video, 10 s samples) that triggers nudge → verdict → reel, for recording.
- Update submission.md, shotlist, record, submit.

Cut order if behind: P11 → P10 → P9 editor (keep health) → P8 chips (keep hotkey). Never cut P7, P12.

### P13 — Critique → build → review round (multi-agent workflow)
4 critics (island, dashboard, features vs Opal/Rize/Forest/Beeminder/notch apps, robustness) → backend, island, dashboard builders → adversarial reviewers → fix round.
Scores: island 5 → 6.5 → fixed; dashboard 6 → 8.2 (ship); backend 4.5 → 7.2 → fixed. Tests: tests/test_robust.py, test_features.py, test_backend_fixes.py.

### P14 — End-to-end round 2: onboarding, Calendar, Strava, Health (multi-agent workflow)
Audit (fresh-install journey 5.2, island 6.2, integrations 3.5) → calendar / strava+health / habits+onboarding builders → dashboard + island → reviewers (7.3 / 7.0 / 7.4) → fix round.
- Onboarding wizard: welcome → templates (plain-language "Checked by") → days/time/length → connections → first session.
- Apple Calendar via `bin/alibi-calendar` (EventKit): plan blocks in an "Alibi" calendar, verdicts written back, "planned now — start?" on the island.
- Strava: guided connect at /strava/setup (OAuth callback, tokens in data/secrets.json, refresh rotation, rate limits, all run types).
- Apple Health: opt-in phone listener + /phone setup page (QR + Shortcut steps); steps/sleep/mindful/workout habits.
Manual checks only the user can do: Calendar permission prompt, real Strava app, real iPhone Shortcut.

### P15 — Signals: everything the phone and laptop can tell Alibi (multi-agent workflow)
Contract: docs/SIGNALS.md. iPhone companion streams Health (activity, sleep stages, HR/HRV, mind, daylight, workouts), Watch
heart rate, motion + pickups, home geofence (in/out only), Screen Time (picked apps, 5-min thresholds) with Opal-style
shields during sessions, and an "Alibi" Focus filter. Mac: idle/lock, camera+mic in use, media, Focus, notification counts
(Full Disk Access), app-switch rate, git. Fusion only lowers scores, with a stated reason; signal nudges. Page: /signals.
Reviews: backend 6.5, iOS 7, UI 6 → all majors fixed in the fix round. 23 test suites green.
