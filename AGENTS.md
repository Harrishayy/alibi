# AGENTS.md — Alibi

Guide for coding agents working in this repo. Humans: start with README.md.

**Alibi** is a habit tracker that checks your alibi: you declare a habit session, Alibi gathers evidence (desk
camera, laptop window titles, macOS signals, Strava, iPhone/Health) and only ticks the habit if the evidence agrees.
An always-on agent on a DGX Spark writes the briefs (docs/AGENT.md).

## Commands

| Task | Command |
|---|---|
| First-time setup (venv, deps, native build) | `bash scripts/setup.sh` |
| Start / stop / status | `./alibi.sh up` · `./alibi.sh down` · `./alibi.sh status` |
| **All tests** (about 3 min, no keys, no camera) | `./alibi.sh test` |
| One test | `.venv/bin/python tests/test_p1.py` |
| Rebuild Swift (island, witness, sense, calendar, Alibi.app) | `bash scripts/build_native.sh` |
| Island visual check, no screen recording | `bin/alibi-island --snapshot DIR [--state FILE.json]` |
| Model pre-flight (needs `.env` key) | `.venv/bin/python scripts/smoke_test.py` |
| Pinch mood rules self-test | `.venv/bin/python -m alibi.pinch --selftest` |
| Talk to it | `./alibi.sh say "draw for 25 minutes"` |
| Demo data / fast demo session | `./alibi.sh seed` · `./alibi.sh demo [--fixture]` |
| iPhone companion (USB) | `bash ios/build_install.sh` |
| Spark agent (NemoClaw sandbox + relay) | `bash scripts/spark_setup.sh` · docs/SPARK.md |

Dashboard: http://127.0.0.1:8765. Phone API: :8766 (needs the `X-Alibi-Secret` header).

## Layout

```
alibi/            Python daemon + FastAPI (api.py, routes_*.py), verifier, witness, evidence, nudges, report, …
  db.py           FROZEN data contract: tables `sessions`, `events`
  web/            dashboard: index.html + css/*.css + js/*.js (tokens in css/tokens.css), fixtures/ for ?stage=
  pinch.py        mascot mood rulebook (pure function of state)
  relay.py        DGX Spark side: sandbox <-> Mac agent API bridge over Tailscale, mirrors into data/relay/
  routes_agent.py /api/agent/* on :8766 for the Spark agent (docs/AGENT.md): read context, post briefs
native/           Swift: Island.swift (notch island, hosts the daemon in Alibi.app), witness.swift (Apple Vision),
                  sense.swift (macOS signals), calendar.swift
spark/            NemoClaw/OpenClaw: `alibi` skill, HEARTBEAT.md, brief cron jobs, egress policy preset for the relay
ios/              iPhone companion (XcodeGen: project.yml) + Screen Time / Shield extensions, Shared/
tests/            one script per feature, run by tests/run_all.sh; harness.py = temp data dir + fake clock
scripts/          setup, build_native, demo, seed, smoke_test, spark_setup
docs/             AGENT.md (the Spark agent), SPARK.md (its setup), SIGNALS.md (signals contract),
                  design/ (tokens, design system, Pinch)
habits.yaml       your habits and weekly targets
data/             runtime data — personal, git-ignored, never commit
```

## Hard rules

1. **Data contract.** `alibi/db.py` (`sessions`, `events`) is frozen. Ask before changing the schema.
   Observers only *write* events; only the verifier *reads* them.
2. **Tests stay green and stay hermetic.** Run `./alibi.sh test` before you call anything done. Tests must never
   touch real data: `tests/harness.py` sets `ALIBI_DATA_DIR` and `ALIBI_HABITS` to temp copies, `VISION_BACKEND=mock`,
   and turns off Mac signals and Shortcuts. New tests start with `from harness import ...`, print `PASS`/`FAIL` lines
   via `check()`, and get added to the list in `tests/run_all.sh`.
3. **Done means proven.** A feature is done when its test prints the expected output, not when the code is written.
4. **Camera off** whenever no physical session is running. Never leave a capture loop alive in a test or script.
5. **Privacy claims are exact.** With NVIDIA Build endpoints, frames leave the machine. Only say "frames never
   leave the Mac" for `VISION_BACKEND=apple` or a local `VLM_BASE_URL`. The Omni video witness on Build
   (`VLM_VIDEO=1`) sends one-minute clips to NVIDIA.
6. **Secrets.** Keys live in `.env` (template: `.env.example`) and `data/secrets.json`. Never print, log, commit or
   paste them into tool output. Never commit anything under `data/` except `.gitkeep` files.
7. **Offline first.** Everything must work with no API key (Apple Vision witness + rule fallbacks). NVIDIA models
   switch on automatically when `.env` has a real key and model IDs. Don't add a hard dependency on the network.

## Code style

- Python 3, stdlib-first, small modules, plain functions. Match the surrounding code: terse comments that say *why*.
- Time comes from `time.time()` at call time (the test harness replaces it); don't cache "now" at import.
- Paths come from `alibi/config.py` (honours `ALIBI_DATA_DIR`), never hard-coded `data/…`.
- Swift: single-file tools compiled with `swiftc -O` (no Xcode project on the Mac side). Island buttons need
  `FirstClickHostingView` (Alibi is never the active app).
- User-facing copy: dry, short, specific ("I've seen your phone for 3 minutes."), no exclamation marks.
- Commits: imperative, short subject; the body explains *why*.

## Design system

Calm, roomy spacing and soft rounded surfaces; **NVIDIA colours**. Spec in `docs/design/`: **all-sans** type
(SF Pro / Onest fallback, tabular numerals), **dark-first**, mascot **Pinch** (original green detective lobster —
not NVIDIA artwork).

| Token | Value | Use |
|---|---|---|
| Accent | `#76B900` | primary buttons, focus ring, progress, on task / done |
| Accent ink | `#4E7A00` light · `#8FD400` dark | green *text* (#76B900 fails contrast on white) |
| Text on green | `#000` | always black on green, never white |
| Surfaces | `#000` · cards `#1A1A1A` · light `#F2F2F2`/`#FFF` | |
| Neutrals | `#5E5E5E` `#A6A6A6` `#D7D7D7`, hairline white 9% on dark | |
| Warn | `#E5484D` (ink `#C4161C` / `#FF7A7E`) | phone, slacked, errors — never the accent |
| Partial / idle | `#F2A900` | partial verdicts, idle, breaks |

Tokens: source in `docs/design/tokens/` (`tokens.css`, `Theme.swift`). Copies: `alibi/web/css/tokens.css`,
`native/shared/Theme.swift` (copied into `ios/AlibiPhone/Views/Shared/` by `scripts/sync_shared_swift.sh`; never edit
those copies), `alibi/evidence.py` `COLOURS`, the page CSS in `alibi/routes_integrations.py`. Change one → change all.
Usage rules and components: `docs/design/system/project/README.md`. Pinch's mood always comes from `alibi/pinch.py`.

Island (Dynamic-Island-like): idle = exactly the notch size, no wings. Live = two 46 pt wings (one glyph left,
one short value right). Open = 400 pt wide (verdict 440). Hover opens after 0.35 s dwell, folds 0.8 s after leaving
the margin; a click pins it open until Esc / send / click elsewhere. No serif type, and no colours outside the tokens.
