# Pinch rig spec

`build_pinch.py` generates everything here except `rig.js`, the param-to-transform mapping the engine reuses. Edit the generator's constants and rerun it; never hand-edit outputs.

## Part tree

Each movable part is a `<g id data-part>`. Its transform is an SVG attribute about the pivot listed in `rig.json`.

`bloom`, `pinch-root` (feet [80,148]) › `tail`, `legs`, `body` › [`antenna-l/r`, `belly`, `blush`, `eye-l` › `lid-l`, `eye-r` › `lid-r`, `mouth`], `arm-l` › `claw-l` › [`jaw-l-bottom`, `jaw-l-top`, `paper`], `arm-r` › `claw-r` › [`jaw-r-bottom`, `lens` › [`lens-glow`, `lens-view` › `lens-eye`, `lens-sweep`, `lens-glint`], `jaw-r-top`], `sweat`, `zzz`, `sparkle`.

The jaws meet at `close_deg` 13.5°, which the generator solves. The mouth is the only shape swap: smile, flat, open or o.

## Params

- **From research/03:** bodySquash, bodyY, tilt, clawL/R, pinch, eyeOpen, lookX/Y, mouthCurve, blush, antennaSway, sparkle, sweat, zzz.
- **Detective:**
  - `lens` is an IK macro that moves the glass onto eye-r. The magnified eye shows from 0.72.
  - `lensGlow`, `lensZoom`, `lensOut`, `glint`.
- **Extras:** lidL/R, browL/R, joy (^ ^), pinchL/R, wristL/R, antennaLift, mouthTilt, paper, bloom.

Squash keeps volume: scaleX = 1/√scaleY. lookX also leans the body 2°.

## LOD by rendered size

| Size | Art |
|---|---|
| ≥ 96 | full |
| 40–95 | no legs, outline 3.6 |
| 24–39 | `pinch-lod24.svg`: no legs, tail or blush, outline 5.5 |
| 16–23 | `pinch-lod16` / `pinch-lod20`: body, crusher, lens ring and flat-top eyes only |

Inline, `@container pinch` or `data-lod` picks the rung; as an `<img>`, `@media` does. On dark the outline is transparent unless `.rim` is set.

## Layers

1. **Loop:** the mood, on engine time.
2. **Pose:** held mood values.
3. **One-shot:** a clip, blended in over 120 ms and out over 240 ms.

- Blink multiplies `eyeOpen`.
- `lensGlow` is max(camera, clip), so the lens never lies about the camera.
- Clips run anticipation → action → follow-through → settle.
- Still mode and reduced motion render the `key` frame.

## Size to surface

| Size | Surface |
|---|---|
| 16 pt | island wing (lod16, static, tintable) |
| 20 | PinchLine and the Live Activity compact view (lod20) |
| 28 pt | island expanded (lod24) |
| 32 / 44 pt | Live Activity Lock Screen and expanded |
| 56 pt | nudge alert |
| 64 | verdict alert and web hero |
| 96 | web Now card |
| 160 | celebration and iPhone Today |

## SwiftUI port

`Pinch.swift` ports `rig.js` and the engine rules for the island, the iPhone app and the Live Activity. `gen_swift.py` compiles `pinch.svg`, the 16 and 20 glyphs, `rig.json`, `clips.json` and the `tokens.css` pinch colours into `PinchData.swift`. Rerun it after any change to those files, and never hand-edit its output.

To check the port, run `render_swift/compare.py`. It renders the same frames through the web rig and through `ImageRenderer`, then writes `swift-renders/compare.png` with web, Swift and diff side by side. Only anti-aliasing should differ.
