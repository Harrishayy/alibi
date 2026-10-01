# NotchIsland

The Mac notch island on the web: one black shape whose clip morphs between states, always dark inside.

**Use it for** design reviews, demos and docs of the island, and any web mirror of it. The native island (`native/Island.swift`) follows the same sizes, radii and springs.

**You provide** `state`, `leading` and `trailing` (the wing contents, or the header's two sides when open), `children` for the panel, and optionally `width`, `shake` (one 360ms shake on entering `nudge`, phone drift only) and `label`.

| State | Size | Content |
|---|---|---|
| `idle` | 185 × 32, radius 10 | nothing |
| `live` | 277 × 32, radius 12 | 16px Pinch left, time left ("24m") right in `accent-ink`, wings at 70% |
| `peek` | 289 × 36, radius 14 | as live, wings at 100% |
| `break` | 277 × 32 | sleepy Pinch, `cup` and countdown in `partial-ink` |
| `expanded` | 400 × auto (180–360), radius 28 | header, composer, chips, next-up line |
| `nudge` | 400 × auto | 56px Pinch, one `al-island-voice` line, three buttons |
| `verdict` | 440 × auto | 64px Pinch, `VerdictPill`, three frames, two buttons |

Motion: opening uses `spring-island` (alerts drop on `spring-bouncy`); content follows at +60ms in three tiers 30ms apart with opacity, scale 0.96 and blur 8 → 0; closing fades the content in 100ms, then folds the shape on `spring-smooth`. The top flares scale with the state, and the open shape casts `shadow-island`. Inner content is inset 12px, so cards inside take `radius-md`.

Type helpers for island content: `al-wordmark` ("ALIBI", 12px heavy, +0.13em), `al-island-title` (17/600), `al-island-voice` (15/500) and `al-island-secondary` (12px at 60%).

- Do: keep the 185px centre of the band empty; it is the camera housing.
- Do: put the island on a surface that is not `#000` when showing it in docs, so the shape reads.
- Don't: add glass, blur or a border to the shape, or bounce it on close.
