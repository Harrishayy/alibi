# Alibi — build rules

Timeboxed entry for the NVIDIA London Claw Agent Challenge (applications close **Oct 2, 2026**). PLAN.md is the source of truth.

- Build strictly prototype by prototype, in order: P0 → P1 → P2 → P3 → P4 → P5 → P6. Don't start the next until the current one's DoD passes.
- `alibi/db.py` is the frozen contract (`sessions`, `events`). Do not change the schema without asking first. Observers write events; only the verifier reads them.
- A prototype is done only when its **Definition of Done** command produces the expected output — "code written" is not done. On pass: `git add -A && git commit -m "pN works" && git tag pN`, then stop and tell the user what 10–15 s clip to record into `demo/clips/`.
- Respect timeboxes. If something fights past its box: hardcode, fake, or fall back (see each P's "If behind"), and say so.
- Cut rules: P1 not tagged by T+1:10 → fix P1, jump to P4, then demo. P4 not tagged by T+2:00 → skip P5. Cut order: P6 → P3 → P5 → P2 Path A. Never cut P0, P1, P4, demo.
- Pre-flight gate: `python scripts/smoke_test.py` must return JSON from both the text and vision model before P0.
- Privacy: with NVIDIA Build endpoints, frames are sent to the endpoint. Only claim "frames never leave my network" if `VLM_BASE_URL` points at a local server.
- No AI co-author trailers in commit messages.

Phase 2 (P7–P12) is in PLAN.md §10. Day to day: `./alibi.sh up|down|status|test|demo`. `./alibi.sh test` must stay green.
Tests never touch real data: harness sets ALIBI_DATA_DIR + ALIBI_HABITS to temp copies. The camera must be off when no physical session runs.
Swift: `native/Island.swift` (notch island, owns the daemon inside Alibi.app), `native/witness.swift` (Apple Vision); rebuild with `bash scripts/build_native.sh`. Visual check without screen recording: `bin/alibi-island --snapshot DIR`.
