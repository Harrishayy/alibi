# Pinch

Static vector stills of Pinch, Alibi's green detective lobster, for places that cannot run the engine: decks, docs, the README of the repo, an `<img>` in an email or a design file. Anywhere a page can run script, mount the live mascot instead (`Alibi.Pinch` or `AlibiPinch.mount`), which animates, follows the theme and keeps the lens honest about the camera.

Every file was exported from `AlibiPinch.svg()` (docs/design/pinch/pinch.js) in headless Chromium, with each computed colour written into the shape as a plain `fill` / `stroke`. They hold no `<style>`, no CSS variables, no `currentColor`, no script and no `foreignObject`, so they look the same in an `<img>`, in Figma and in Keynote. Regenerate them from the engine; never hand-edit the paths.

## Files

| File | What it shows | Where it is used |
|---|---|---|
| `pinch.svg` | The `idle` key pose at the 160 rung: full rig with legs and tail fan, lens resting as an empty ring. | The default picture of Pinch: the brand book, the repo README, the iPhone Today empty state mock-ups, any "meet Pinch" slide. |
| `pinch-focused.svg` | The `focused` key pose with the lens glowing (`camera: true`): the camera is sampling during a live session. | Mock-ups of a live session (web Now card, iPhone Today live mirror). Use it only where the scene shows a live camera session, because the glow means "the camera is on". |
| `pinch-celebrate.svg` | The `celebrate` key frame: both claws up, ^ ^ eyes, blush, sparkles and the one allowed gradient, the celebration `bloom`, behind it. The lens is set down for the clap. | Done verdicts and streak milestones in decks and mock-ups; the reel title card. |
| `pinch-sideeye.svg` | The `sideeye` key frame: eyes narrowed, lens raised to one eye, a sweat drop. | Nudge mock-ups ("You said drawing. I've seen your phone for 3 minutes."). Never on its own as a scolding image. |
| `pinch-supportive.svg` | The `supportive` key frame: a soft shrug, claws out, slow-blink eyes. It stays green. | Slacked verdicts ("Slacked, by my count. Tap any frame if I got it wrong."). |
| `pinch-lod16.svg` | The 16-unit silhouette glyph: body, crusher claw, lens ring and flat-top eyes, nothing else. | Favicons, the island-wing size in mock-ups, list bullets. Show it at 16 or 20 px only; for anything larger use `pinch.svg`. |

## Geometry

- The five full-size stills share one viewBox, `-13 -1 180 171`, with an intrinsic size of 180 × 171. The rig's own 160 × 160 frame sits at (13, 1) inside it. The extra margin exists because claws, antennae and the lens reach outside the rig frame in some poses (the engine draws with `overflow: visible`; an `<img>` would clip). Because the box is shared, swapping one still for another in the same slot does not shift Pinch.
- The celebration `bloom` is a radial gradient centred on Pinch. It is larger than the viewBox and is cut by it, which is intended.
- `pinch-lod16.svg` is a 16 × 16 box. It has no outline and no glow.

## Inks

The stills use the light-ground inks from `tokens.json`. They also read on black, so one file serves both themes:

| Part | Token | Value | On white | On black |
|---|---|---|---|---|
| Body, claws | `pinch-body` | #76b900 | 2.41:1, carried by the outline | 8.71:1 |
| Belly, highlights | `pinch-belly` | #97dc42 | inside the outline | inside the body |
| Shade, inner claw, tail | `pinch-shade` | #588c05 | 4.1:1 | 5.2:1 |
| Outline (3-unit stroke under the fill) | `pinch-outline` (light) | #365900 | 8.1:1 | dark rim; the body carries the shape |
| Eyes | `pinch-eye` | #000000 | 21:1 | on the green body, 8.7:1 |
| Eye shine, lens glint | `pinch-shine` | #ffffff | on black eyes | on black eyes |
| Lens rim and handle | `pinch-lens` (light) | #5e5e5e | 6.5:1 | 3.2:1 |
| Sparkles | `pinch-spark` (light) | #588c05 | 4.1:1 | 5.2:1 |
| Blush | `pinch-blush` | #f2a900 at 40% | | |
| Lens glow (focused only) | `pinch-lens-glow` (light) | #76b900 at 40% | | |
| Bloom (celebrate only) | `bloom` (light) | #76b900 at 28%, fading to transparent | | |

The live component switches inks by theme: on dark grounds it drops the outline (or draws the bright `#8fd400` rim when `rim` is set), lightens the lens to #d7d7d7 and the sparkles to #aaf059. If a dark-only slide needs that look, export with the engine using `theme: 'dark'` rather than recolouring these files.

None of the files are single-ink marks, so do not tint them with CSS `color`; they ignore it. The 16 glyph is the only one meant to be recoloured, and only by re-exporting it, for example all `#a6a6a6` for the island's "nobody at the desk" wing.

## Rules that travel with the files

- Pinch stays green in every state. Never recolour it red, amber or grey to show a status; status belongs to `StatusDot`.
- One Pinch per view. Never place it on or beside evidence frames, inside a pill, meter, chart or button, or in consent, privacy or error copy.
- It is an original character. Never pair it with NVIDIA's logo or eye mark, or with OpenClaw's artwork, and never call it Nemo-anything.
