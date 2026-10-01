# Alibi — the habit tracker that checks your alibi

Entry for the NVIDIA London Claw Agent Challenge. Tell it what you're about to do; a long-running agent gathers
evidence (desk camera, laptop windows, Strava, phone/Health) and only ticks the habit if the evidence agrees.

## Use it

```bash
bash scripts/setup.sh      # once: venv, deps, builds Alibi.app + native helpers
./alibi.sh up              # start — or double-click Alibi.app
./alibi.sh down            # stop everything, camera off
```

Then **hover the notch** (or press **⌥⌘A** anywhere) and type what you're about to do — or tap a habit chip.
The dashboard is at http://127.0.0.1:8765 (`./alibi.sh open`); its **Setup** drawer shows what's working
(camera, window titles, witness, model, Strava) and lets you edit your habits and weekly targets.

| | |
|---|---|
| `./alibi.sh status` | what's running, current session |
| `./alibi.sh say "learn C++ for 30 min"` | talk to it from the terminal |
| `./alibi.sh demo` | 2-minute live session with fast sampling, for recording (`--fixture` = no camera) |
| `./alibi.sh test` | every prototype's Definition of Done, ~15 s, no keys |
| `./alibi.sh seed` | a pre-filled week in `data/demo` |

## What it does
- **Verdicts with evidence** — camera frames (physical), window titles (digital), both (hybrid) → done / partial / slacked, with a contact sheet.
- **Nudges** — "You said drawing. I've seen your phone for 3 minutes." drops out of the notch mid-session.
- **Memories reel** — every camera session becomes an H.264 timelapse; a whole day too.
- **Corrections** — click any sample on the dashboard to relabel it; the verdict re-scores, the correction stays on the record.
- **Nightly report** — claimed vs seen for the week, in three dry sentences, at 22:00.

## Witnesses (`VISION_BACKEND`)
- `apple` (default with no key): Apple Vision on-device — people, hands, phone. Frames never leave the Mac.
- `nvidia`: VLM on NVIDIA Build, or a local OpenAI-compatible server on the Spark via `VLM_BASE_URL`. Automatic once `.env` has a key + `VLM_MODEL`.
- `mock`: colour-coded frames for tests.

Layout: `alibi/` (daemon, api, camera, witness, verifier, evidence, nudges, reel, health, laptop_logger, report, strava, web/),
`native/` (Swift island + witness), `tests/` (one DoD per prototype), `PLAN.md` (tags p0–p12 mark each working state).
