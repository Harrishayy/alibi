# Build lanes: final ownership and amendments to IMPLEMENTATION.md

Read this before `IMPLEMENTATION.md`. Where the two disagree, **this file wins** (it reflects what actually happened
between 17:20 and 18:15, including agreements with the other session, `nvidia-habits-fe`).

## What is already done

| Item | State |
|---|---|
| Pinch rulebook (IMPLEMENTATION K2/K3) | **Done.** `alibi/pinch.py`: `pinch_state(state) -> {mood, event, seq, age_s, line}`, stateless; `seq` = milliseconds of the triggering alert/session start (monotonic, identical across polls and across surfaces). `/api/state` and `/api/phone/session` both carry `pinch`. Self-test: `.venv/bin/python -m alibi.pinch --selftest` (first step of `tests/run_all.sh`). |
| Event mapping (differs from Appendix B) | nudge with `label == "phone"` → `sideeye`; any other nudge → `nudge`; verdict done/partial/slacked → `celebrate`/`partial`/`supportive`; `planned` → `hello`; `synced` (Health check-in) and Strava `info` → `connected`; a session younger than 30 s → `connected`. Moods: break → `sleepy`; drifting → `thinking`; no samples yet → `listening`; live → `focused`; report < 10 min → `reading`; 23:00–06:00 → `sleepy`; else `idle`. Clients play `event` once when `seq` > last seen and `age_s` < 15; on first load they record `seq` without playing. `line` is Pinch's caption for the moment. |
| `/api/phone/session` fields | Done by the other session: flat coupling keys + `session{id, habit, habit_label, modality, started_at, ends_at, declared_min, on_break, on_task_ratio, last_label, drifting{label, since_s}, nudges}`, `today{habits_done, habits_total, verified_min}`, `recent_verdict{habit, verdict, ratio, ended_at}`, `streak_days`, `plan_next{habit, starts_at}`, `pinch`. There is **no `week` field**: the phone Week tab uses the fallback in P3. |
| `synced` alerts | Health ingest now emits `notify(kind="synced", source="health", …)` at most hourly. The island must treat `synced` quietly (a wing glint + Pinch `connected`, no full alert). |
| Dashboard split (Wave 0 step 3) | Done differently: `alibi/web/css/{base,shell,now,week,sessions,setup}.css` and `alibi/web/js/{core,now,week,sessions,setup,onboarding}.js`, loaded by `index.html` (no `app.css`/`app.js`). |
| Island multi-file build (Wave 0 step 4) | Done differently: top-level entry code lives in `native/main.swift`; shared SwiftUI files live in **`native/shared/`** (`Theme.swift`, `Pinch.swift`, `PinchData.swift`); `scripts/build_native.sh` compiles `native/main.swift native/Island.swift native/shared/*.swift`. `scripts/sync_shared_swift.sh` copies `native/shared/*.swift` to **`ios/AlibiPhone/Views/Shared/`** (the iOS app target already compiles everything under `ios/AlibiPhone/`, so **no project.yml source lines** are added for the app). Never edit the iOS copies by hand. |

## Tags (the other session already used `p15`)

`p16-design` (foundation) · `p17-dashboard` · `p18-island` · `p19-iphone` · `p20-live-activity`. Never `p15*`.

## Lanes and exclusive ownership

| Lane | Owns (may create/edit) |
|---|---|
| **F** foundation (Wave 0b) | everything it is told to touch in its prompt, then hands over |
| **W1** web shell + Now | `alibi/web/index.html`, `css/tokens.css`, `css/components.css`, `css/base.css`, `css/shell.css`, `css/now.css`, `js/boot.js`, `js/core.js`, `js/now.js`, `js/icons.js`, `alibi/web/fixtures/**` |
| **W2** web week + sessions | `css/week.css`, `css/sessions.css`, `js/week.js`, `js/sessions.js` |
| **W3** web setup + signals + pages | `css/setup.css`, `js/setup.js`, `js/onboarding.js`, `alibi/web/signals.html`, the CSS/HTML strings in `alibi/routes_integrations.py` (visual only: same routes, same data), `alibi/evidence.py` colours/fonts/pill (same signatures and outputs), `alibi/reel.py` title card (same signatures) |
| **M** web moments + Pinch | `js/moments.js`, `js/pinch-wire.js`, `js/confetti.js`, `js/pinch.js` (installed copy of `docs/design/pinch/pinch.js`), `css/moments.css` |
| **I** island | `native/Island.swift`, `native/main.swift`, `native/shared/*.swift` (canonical shared rig + theme; run `scripts/sync_shared_swift.sh` after every change and commit the iOS copies with yours), `scripts/build_native.sh` (island line only), `docs/design/fixtures/island/**` |
| **P** iPhone | `ios/AlibiPhone/Views/**` except `Views/Live/**` and `Views/Shared/**`; `ios/AlibiPhone/Assets.xcassets/**` (AppIcon) and the single line `ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon` in the AlibiPhone target of `ios/project.yml` (approved by the other session) |
| **L** Live Activity | `ios/AlibiLive/**`, `ios/AlibiPhone/Views/Live/**`, the new `AlibiLive` target block in `ios/project.yml` plus exactly two lines in the AlibiPhone target (`- target: AlibiLive` under dependencies, `NSSupportsLiveActivities: true` under info properties) — approved by the other session. The extension's sources reference `AlibiPhone/Views/Shared/*.swift`. |
| **S** demo staging | `docs/design/demo/**`, `docs/design/fixtures/state/**` (and it may copy fixtures into `alibi/web/fixtures/` until W1 starts) |

Shared files touched by several lanes (one tiny edit each, commit that file alone within 2 minutes, re-read right
before editing): `ios/project.yml` (P: 1 line; L: its block + 2 lines). `CLAUDE.md` now just imports `AGENTS.md`; its
design section was updated by the orchestrator (04a2a6f) — lanes don't edit either file.

## Rules for every lane (in addition to IMPLEMENTATION §0, §3, §9)

- **Never** run `./alibi.sh up|down|demo|restart`, never kill or relaunch the user's `Alibi.app`/daemon, never take the
  real camera. Use the lab server (IMPLEMENTATION §3.3) on a spare port with temp data. The island is verified with a
  **temp build** + `--snapshot`. **No lane runs `bash scripts/build_native.sh`.** It deletes and re-signs the running
  Alibi.app, and the first launch after the re-sign asks once for Documents access. The orchestrator runs it only once the
  user confirms they're at the Mac to click Allow, after messaging `nvidia-habits-fe`, then relaunches with
  `./alibi.sh down && ./alibi.sh up`. If that hasn't happened by 21:15, it moves into the 21:30 pre-flight.
- Leave the phone listener on `:8766` and the `tailscale serve` HTTPS proxy alone; the user's iPhone syncs through them.
- `ios/project.yml` also holds the other session's Screen Time targets and entitlements: keep every existing line
  byte-identical. `ios/build_install.sh` (device build) is theirs.
- Commit by pathspec only; if `git` reports `index.lock` exists, wait 2 s and retry (never delete the lock).
- No AI co-author trailers. Plain imperative messages.
- `./alibi.sh test` must stay green (hermetic). `python3 docs/design/tools/lint_design.py --paths <your files>` must end
  `lint_design OK` for the files you own.
- Look at your renders/screenshots with the Read tool before declaring a package done.
