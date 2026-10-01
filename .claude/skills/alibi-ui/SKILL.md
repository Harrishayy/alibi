---
name: alibi-ui
description: Alibi's design system and UI rules (Claude-like calm layout, NVIDIA colours, all-sans type, dark-first, Pinch mascot, notch-island behaviour). Use for any visual or copy change to alibi/web/index.html, native/Island.swift, ios/AlibiPhone/Views, evidence images (alibi/evidence.py) or the integrations page CSS.
---

# Alibi UI

The spec lives in `docs/design/` (RESEARCH.md, research/01–08, tokens/tokens.css, pinch/). Read the relevant file
before a non-trivial change. The summary below is binding.

## Feel

Calm, roomy, soft rounded surfaces, quiet hairlines, like Claude. **Only the colours are NVIDIA's.** Don't make
layout or type "look NVIDIA"; the user explicitly rejected that.

- **Type: all-sans** (SF Pro superfamily on Apple, Onest fallback on web), tabular numerals for times and counts.
  No serif (the earlier Newsreader/New York rule is retired).
- **Dark-first**; light mode still supported via the same tokens.
- Cards: 16 pt continuous corners, `#1A1A1A`, hairline border. Buttons: 9–10 pt radius, hover wash, 0.97 press.
- Mascot **Pinch**: an original green detective lobster (lens = camera-on light). Moods come from `alibi/pinch.py`
  (`pinch_state(state)`), never decided ad hoc in the UI.

## Colour tokens

| Token | Value | Rule |
|---|---|---|
| Accent | `#76B900` | primary action, send, focus ring, progress, on-task/done |
| Accent ink | `#4E7A00` light · `#8FD400` dark | for green **text**; #76B900 fails contrast on white |
| On green | `#000` | text on a green fill is always black |
| Surfaces | `#000`, `#1A1A1A`, `#F2F2F2`, `#FFF` | |
| Neutrals | `#5E5E5E` `#A6A6A6` `#D7D7D7`, hairline white 9% | |
| Warn | `#E5484D` (ink `#C4161C` / `#FF7A7E`) | phone, slacked, behind, errors; never the accent |
| Partial/idle | `#F2A900` | partial verdicts, idle, breaks |

Tokens are duplicated in `docs/design/tokens/tokens.css`, `alibi/web/index.html` `:root` (+ dark block),
`native/Island.swift` (`palette`…), `alibi/evidence.py` `COLOURS`, `alibi/routes_integrations.py` `CSS` and
`ios/AlibiPhone/Views/Theme.swift`. Change one, then search for the old value and change all.

## Island (Dynamic-Island-like)

- Idle = exactly `notch.width × notch.height`, so it disappears into the camera housing. Never draw wings when idle.
- Live (session / block planned now / fresh reply) = two 46 pt wings: one glyph left, one short value right.
- Open = 400 pt (verdict 440). Titles go below the notch row.
- Hover/click timing and `FirstClickHostingView`: see the `native-build` skill.

## Copy

Dry, short, specific, evidence-first: "You said drawing. I've seen your phone for 3 minutes." No exclamation marks,
no guilt-tripping, no emoji in product copy.

## Check your work

- Web: `./alibi.sh up && ./alibi.sh open` (or the `run` / `webapp-testing` skills for screenshots), both themes,
  and ~375 px width.
- Island: `bin/alibi-island --snapshot DIR`, then look at the PNGs.
- Contrast: green text on light backgrounds uses accent ink, not #76B900.
