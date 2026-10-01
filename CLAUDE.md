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

## Design system — Claude-style UI, NVIDIA colours

The look is Claude's: calm, roomy, serif display type, soft rounded surfaces, quiet hairlines. **Only the colours are NVIDIA's** (to match the challenge hosts). Don't change layout or type to "look NVIDIA"; don't bring back the old coral/cream palette.

**Colours**

| Token | Value | Use |
|---|---|---|
| Accent | `#76B900` (NVIDIA green) | primary buttons, send button, focus ring, progress, on task / done |
| Accent ink | `#4E7A00` light · `#8FD400` dark | green *text* (pure #76B900 fails contrast on white) |
| Text on green | `#000` | always black on a green fill, never white |
| Surfaces | `#000` island/dark bg · `#1A1A1A` cards · `#F2F2F2`/`#FFF` light | |
| Neutrals | `#5E5E5E` · `#A6A6A6` · `#D7D7D7` · hairline `white 9%` on dark | muted text, rules |
| Warn | `#E5484D` (ink `#C4161C` light, `#FF7A7E` dark) | phone, slacked, behind, errors; never the accent |
| Partial / idle | `#F2A900` | partial verdicts, idle, breaks |

Tokens live in `alibi/web/index.html` `:root` (+ dark block), `native/Island.swift` (`palette`, `accent`, `cream`, `surface`, `hairline`, `green`/`amber`/`red`), `alibi/evidence.py` (`COLOURS`), `alibi/routes_integrations.py` (`CSS`).

**Type and shape (Claude-style):** serif for headings and conversational text (Newsreader on web, New York on the island), sans for UI and labels, rounded digits for numbers. Cards are 16 pt continuous corners on `#1A1A1A` with a hairline border; buttons are soft rounded rectangles (9–10 pt), with a hover wash and a 0.97 press.

**Island (`native/Island.swift`), like an iPhone Dynamic Island:**
- Closed and idle, it is exactly the notch (`notch.width × notch.height`), so it disappears into the camera housing. Never draw wings when idle.
- While something is live (a session, a block planned now, a fresh reply), it adds two compact wings of 46 pt: one glyph on the left (status dot, nudge count, break cup), one value on the right (`24m`, `45s`, `now`). Nothing longer.
- Opened: 400 pt wide (verdict 440). The notch row shows only its far edges, so it holds just the wordmark and icon buttons. Titles go below it.
- Clicks: the hosting view is `FirstClickHostingView` (`acceptsFirstMouse = true`). Alibi is never the active app, so without it every button click is dropped.
- Hover: opens after a 0.35 s still dwell. Folds only after the pointer has been 0.8 s outside a margin (32 pt each side, 48 pt below). A click inside pins it open until Esc, a send, or a click elsewhere.
- Check it visually with `bin/alibi-island --snapshot DIR [--state FILE]` (text fields render as a yellow placeholder there; that's the renderer, not the app).
