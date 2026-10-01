# Alibi — the habit tracker that checks your alibi

Entry for the NVIDIA London Claw Agent Challenge. Tell it what you're about to do; a long-running agent gathers
evidence (desk camera, laptop windows, Strava, phone/Health) and only ticks the habit if the evidence agrees.

```bash
bash scripts/setup.sh            # venv, deps, builds bin/alibi-witness + bin/alibi-island, DB
bash scripts/run.sh              # daemon (API + dashboard on :8765) + the notch island
bash tests/run_all.sh            # every prototype's Definition of Done, ~10 s, no keys needed
```

Surfaces
- **Notch island** (`native/Island.swift`): hover the MacBook notch → "What are you about to do?". Live countdown,
  label dots, nudges and verdicts drop out of the notch on their own.
- **Dashboard** at http://127.0.0.1:8765 — live frame, this week's claimed-vs-seen bars, the session record with contact sheets.
- **CLI**: `python -m alibi.cli start|status|end|report|say "<text>"`

Witnesses (`VISION_BACKEND`)
- `apple` (default with no key): on-device Apple Vision — people, hands, phone. Frames never leave the Mac.
- `nvidia`: VLM on NVIDIA Build (or a local OpenAI-compatible server on the Spark via `VLM_BASE_URL`). Auto when `.env` has a key + `VLM_MODEL`.
- `mock`: colour-coded frames for tests.

Other knobs: `CAMERA_SOURCE=video.mp4` (replay a recording in session time), `SAMPLE_EVERY_S`, `NOTIFY=print|macos`,
`ALIBI_DATA_DIR` (e.g. `data/demo` after `python scripts/seed_demo.py` for a pre-filled week).

Layout: `alibi/` (daemon, api, camera, witness, verifier, evidence, nudges, laptop_logger, report, strava, web/),
`native/` (Swift), `tests/` (DoD per prototype), `PLAN.md` (the build plan; tags p0–p6 mark each working state).
