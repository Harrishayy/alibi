# AGENTS.md — Alibi

Guide for any coding agent (Claude Code, Codex, Cursor, …) working in this repo. Humans: start with README.md.

**Alibi** is a habit tracker that checks your alibi: you declare a habit session, a long-running agent gathers
evidence (desk camera, laptop window titles, macOS signals, Strava, iPhone/Health) and only ticks the habit if
the evidence agrees. Entry for the NVIDIA London Claw Agent Challenge (entries close **11:59 PM PT, Fri 2 Oct 2026** ≈ 08:00 Sat 3 Oct UK; we aim
for Friday evening UK. Rules, submission form and judging criteria: `docs/CHALLENGE.md`).
`PLAN.md` is the source of truth for scope and order.

## Commands

| Task | Command |
|---|---|
| First-time setup (venv, deps, native build) | `bash scripts/setup.sh` |
| Start / stop / status | `./alibi.sh up` · `./alibi.sh down` · `./alibi.sh status` |
| **All tests** (every prototype's DoD, ~15 s, no keys, no camera) | `./alibi.sh test` |
| One test | `.venv/bin/python tests/test_p1.py` |
| Rebuild Swift (island, witness, sense, calendar, Alibi.app) | `bash scripts/build_native.sh` |
| Island visual check, no screen recording | `bin/alibi-island --snapshot DIR [--state FILE.json]` |
| Model pre-flight (needs `.env` key) | `.venv/bin/python scripts/smoke_test.py` |
| Pinch mood rules self-test | `.venv/bin/python -m alibi.pinch --selftest` |
| Talk to it | `./alibi.sh say "draw for 25 minutes"` |
| Demo data / recording run | `./alibi.sh seed` · `./alibi.sh demo [--fixture]` |
| iPhone companion (USB) | `bash ios/build_install.sh` |
| Spark agent (NemoClaw sandbox + relay) | `bash scripts/spark_setup.sh` · docs/SPARK.md |

Dashboard: http://127.0.0.1:8765. Phone API: :8766 (needs the `X-Alibi-Secret` header).

## Layout

```
alibi/            Python daemon + FastAPI (api.py, routes_*.py), verifier, witness, evidence, nudges, report, …
  db.py           FROZEN data contract: tables `sessions`, `events`
  web/            dashboard: index.html + css/*.css + js/*.js (tokens in css/tokens.css), fixtures/ for ?stage=
  pinch.py        mascot mood rulebook (pure function of state)
  relay.py        DGX Spark side: sandbox <-> Mac bridge over Tailscale, mirrors state into data/relay/
native/           Swift: Island.swift (notch island, hosts the daemon in Alibi.app), witness.swift (Apple Vision),
                  sense.swift (macOS signals), calendar.swift
spark/            NemoClaw/OpenClaw: `alibi` skill, HEARTBEAT.md, egress policy preset for the relay
ios/              iPhone companion (XcodeGen: project.yml) + Screen Time / Shield extensions, Shared/
tests/            one script per DoD, run by tests/run_all.sh; harness.py = temp data dir + fake clock
scripts/          setup, build_native, demo, seed, smoke_test
docs/             SIGNALS.md (signals contract), design/ (redesign spec, tokens, research, Pinch)
habits.yaml       the user's habits and weekly targets
data/             runtime data — personal, git-ignored, never commit
```

## Hard rules

1. **Data contract.** `alibi/db.py` (`sessions`, `events`) is frozen. Ask before changing the schema.
   Observers only *write* events; only the verifier *reads* them.
2. **Tests stay green and stay hermetic.** Run `./alibi.sh test` before you call anything done. Tests must never
   touch real data: `tests/harness.py` sets `ALIBI_DATA_DIR` and `ALIBI_HABITS` to temp copies, `VISION_BACKEND=mock`,
   and turns off Mac signals and Shortcuts. New tests start with `from harness import ...`, print `PASS`/`FAIL` lines
   via `check()`, and get added to the list in `tests/run_all.sh`.
3. **Done means proven.** A prototype or feature is done when its Definition of Done command prints the expected
   output, not when the code is written.
4. **Camera off** whenever no physical session is running. Never leave a capture loop alive in a test or script.
5. **Privacy claims are exact.** With NVIDIA Build endpoints, frames leave the machine. Only say "frames never
   leave the Mac" for `VISION_BACKEND=apple` or a local `VLM_BASE_URL`. Witness on the Spark over Tailscale: say
   "never leave your network", not "never leave the Mac".
6. **Secrets.** Keys live in `.env` (template: `.env.example`) and `data/secrets.json`. Never print, log, commit or
   paste them into tool output. Never commit anything under `data/` except `.gitkeep` files.
7. **Offline first.** Everything must work with no API key (Apple Vision witness + rule fallbacks). NVIDIA models
   switch on automatically when `.env` has a real key and model IDs. Don't add a hard dependency on the network.

## Git

- Several agent sessions may share this working tree. **Stage by explicit pathspec** (`git add path/a path/b`),
  never `git add -A` / `git add .`, and don't commit files you didn't change.
- Commit messages: imperative, short subject, body explains *why*. **No AI co-author trailers** (no
  `Co-Authored-By: Claude…` or similar), ever.
- Prototype milestones are tagged `p0`…`p14` (see PLAN.md). Tag only after the DoD passes.
- Remote: `origin` → private GitHub repo `nvidia_habits`. Don't force-push `main`.
- **Squash before push.** Commit small and often locally, but before any push, fold the unpushed commits
  (`git log origin/main..main`) into a handful of logical commits, so the pushed history stays at roughly 10–15
  commits per push, not one per step. Group by feature/prototype, not by time. Show the user the proposed grouping
  and wait for an OK before rewriting. Only rewrite commits that aren't on `origin`; re-point any local `pN` tags
  to the squashed commit that contains their work; and check `git status` first so you don't rewrite under another
  session's in-flight commit. Details: `.claude/skills/safe-commit`.

## Code style

- Python 3, stdlib-first, small modules, plain functions. Match the surrounding code: terse comments that say *why*.
- Time comes from `time.time()` at call time (the test harness replaces it); don't cache "now" at import.
- Paths come from `alibi/config.py` (honours `ALIBI_DATA_DIR`), never hard-coded `data/…`.
- Swift: single-file tools compiled with `swiftc -O` (no Xcode project on the Mac side). Island buttons need
  `FirstClickHostingView` (Alibi is never the active app).
- User-facing copy: dry, short, specific ("I've seen your phone for 3 minutes."), no exclamation marks.

## Design system

Calm, roomy, Claude-like spacing and soft rounded surfaces; **NVIDIA colours**. Current direction (2026-10-01
redesign, spec in `docs/design/`): **all-sans** type (SF Pro / Onest fallback, tabular numerals), **dark-first**,
mascot **Pinch** (original green detective lobster — not NVIDIA artwork).

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
the margin; a click pins it open until Esc / send / click elsewhere. Don't reintroduce serif type or the old
coral/cream palette.
