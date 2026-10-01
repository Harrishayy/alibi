# Pinch: art direction judgement

I reviewed variants A, B and C in `variants/{A,B,C}/`. For each one I read every SVG, NOTES.md, pivots.json and sheet.png. I also made three side-by-side renders of my own, saved in `judgement/`:

- `compare.png`: idle and the three poses at 160 px, the size ladder, notch capsules at 16 and 20 pt, and the 16 px glyph at 6x.
- `notch-16-20.png`: the glyph in a black notch wing next to a 24:10 timer, plus each variant's full art squeezed to 20 px.
- `rig-stress.png`: each variant's own pivots.json driven through neutral, jaws shut, jaws wide, half lids and look right.

## Winner: B, "Inspector with lens"

B is the only design where the detective prop does a product job at every size. The lens in his small claw is the camera light: clear means not looking, green means sampling. That still holds at 16 pt in the notch, where it works as a privacy indicator that also happens to be a mascot. B also has the strongest acting: the lids carry the expressions, and the side-eye has his magnified eye inside the glass. That side-eye is the "I've seen your phone for 3 minutes" moment for the demo video. The anatomy is real lobster (a crusher claw and a cutter claw, a tail fan, four legs), so B is clearly not OpenClaw's red lobster and not a NemoClaw look-alike.

C was a close second, and its build discipline is the best of the three. Most of the grafts below come from C.

## Scores (1–10)

| Criterion | A: Bean detective | B: Inspector with lens | C: Glyph-first |
|---|---|---|---|
| Appeal at 96–160 | 7: cute chibi, but the upturned mittens make him read as a cactus or bean | **9**: the most character; lids and asymmetry give him an inner life | 7: the celebrate pose is joyful, but the stick arms and six tentacle legs feel like a squid |
| Readability at 16–20 in the notch | 6: the mittens read as antlers (a moose) and there's no detective cue | 8: the lens ring survives at 16 and the flat-top eyes keep the lids, but the silhouette is slightly lopsided | **9**: the cleanest glyph, symmetric U-bites, and LOD built into the SVG |
| Detective identity without clutter | 6: the deerstalker is a stock costume and a grey mass on the head; the lens is hidden at idle | **9**: one prop, held in a claw, and it does a job | 7: the worn monocle is charming, but its handle crosses the cheek and it vanishes below 48 px |
| Rig-friendliness | 6: parts separate, but the jaws barely move in the mittens and the lids are a path swap | 8: 24 parts, jaws open and shut visibly, lids translate, the lens is a child of the claw | 8: jaw angles are given in local and world frames, lids scaleY from the brow, there's a parametric build.py, and LOD classes |
| Originality | 6: a deerstalker lobster is a common stock-art trope | **8**: teardrop body plus crusher/cutter asymmetry is distinctive | 6: a gumdrop with raised claws could be any cute bug or alien |
| Fit with an all-sans, dark-first, green UI | 5: the grey hat muddies dark grounds, and the chibi mass is the least precise | 7: illustrative, heavy outline, and the dark lens disc vanishes on #000 | **9**: built from circles and capsules, drops its outline in dark mode, and uses the one allowed bloom |
| **Total /60** | **36** | **49** | **46** |

## Grafts

1. **From C: the construction method.** Rebuild B in a parametric generator modelled on C's `build.py`. Every curve sits on a circle or capsule grid, so polish passes stay reproducible. The engine's `AlibiPinch.svg()` output must match the generated file byte for byte.
2. **From C: level of detail inside the SVG.** Use `@media (max-width:47px)` and `@container pinch` to hide `.lod-48` (tail segment lines, leg outlines, belly stripes, blush) and `.lod-24` (antennae, legs). Below 24 px, swap to the silhouette.
3. **From C: outline that follows the theme.** In dark mode `--pinch-outline` is transparent by default, and the `.rim` class opts into the #8FD400 rim. In light mode it's #365900. B's heavy outline on #000 is the main reason it looks illustrative rather than precise.
4. **From C: the celebrate pose.** Take the happy closed ^ ^ eyes, the open mouth and the soft green bloom. The bloom is the system's one allowed gradient, used here and nowhere else.
5. **From C: the claw construction.** A palm plus a hinged dactyl on a single rotate pivot. Replace B's crusher claw, which reads as a hand holding a ball, with C's clean two-jaw pincer at B's larger crusher scale. Adopt C's jaw spec format: per-jaw `local`/`world` pivots plus `close_deg`/`open_deg`, so both claws close with the same signed angle.
6. **From C: state tinting in the wing.** The silhouette body fill is `var(--pinch-silhouette, var(--pinch-body))`, so the island can tint it on-task green, idle amber, phone red or absent grey. Lens glow stays a separate shape, so "camera on" never collides with the state tint.
7. **From A: the eyes.** Make the eyes about 23% of body width (B's are about 18%) and set them a touch lower. Keep one shine per eye. This is the cheapest charm upgrade available.
8. **From A: two small props.** Take A's sweat drop for nudge and surprise, and its sparkle placement for celebrate, with sparkles at the claw tips rather than floating around the head.
9. **From B (keep): the acting.** Keep the lids as a translate-plus-rotate cap on each eye, the side-eye with the lens raised to one eye and #lens-view clipping a magnified eye, the kind lids that tilt outward for supportive, and the lens as a child of claw-r.

## Directives for the final polish

1. **Make the idle face open and curious, not dry.** B's resting lids cover about 40% of the eye, which reads as unimpressed, and the dossier's rule is never shaming. Idle lids cover at most 12%. The 40% dry lid is reserved for `sideeye`, and even then only on one eye, paired with a raised brow, never a frown.
2. **Fix the lens glass.** The current near-black disc disappears on #000 and looks like a hole.
   - Camera off: the glass is transparent, with a white specular arc (two strokes at 10 and 2 o'clock, `--pinch-shine` at 70%) so it reads as glass on any ground.
   - Camera on: a `--pinch-lens-glow` inner wash at 35%, plus a 2 px green ring outside the #D7D7D7 rim.
   - The two states differ by shape (the glint and the ring), not only by colour.
   - At 16 pt the lit state fills the 2.2 px lens hole with `--pinch-spark`.
3. **Balance the 16 px glyph.** Keep B's five shapes (body, crusher V, lens ring with stem, two flat-top eyes).
   - Nudge the body 0.5 px right so the glyph's optical centre sits under the wing's centre line.
   - The lens hole must be at least 2 px at 16 and at least 2.5 px at 20, and every gap at least 1 px.
   - Ship a matching 20 px master rather than scaling the 16. Wing size and placement follow the island spec.
   - The PinchLine avatar (20 px, in toasts) uses the silhouette, never the full art. The full art at 20 px turns to mush in all three variants (see `notch-16-20.png`).
4. **Body.** Keep the teardrop but widen the base by about 6% so it reads as a lobster, not a pickle or avocado. Keep two carapace lines at most on the belly. Keep the tail fan on the left, since it's the asymmetric signature. Legs are four stubby capsules, with no tentacle reads.
5. **Colours, all tokens.**
   - `pinch-body` #76B900, `pinch-belly` #97DC42, `pinch-shade` #588C05, `pinch-outline` #365900 (light) or transparent/#8FD400 rim (dark), `pinch-eye` #000.
   - `pinch-shine` #FFF, `pinch-blush` #F2A900 at 35%, `pinch-spark` #AAF059, `pinch-lens` #D7D7D7, `pinch-lens-glow` #76B900. The lens handle is #5E5E5E.
   - No red anywhere on Pinch, no hardcoded hex outside the `var()` fallbacks, and no NVIDIA eye-swirl or logo geometry. Never call it Nemo-anything.
6. **One rig, transforms only.**
   - Use B's 24 `<g id>` parts with `transform-box: view-box` and one pivots.json in B's format, extended with C's jaw fields.
   - Every mood and clip is transforms and opacity on those parts. The only exception is the mouth, which swaps between exactly four shapes: smile, flat, open, o.
   - Lids are driven 0–1 by `eyeOpen` and brow angle. Gaze is `lookAt(x,y)`, which moves eye-* ±3.5/±2.5 with the lids riding along, plus a 2° body lean toward the gaze.
   - Squash happens at the feet [80,148] with scaleX = 1/sqrt(scaleY).
7. **Jaws must visibly pinch.** At `close_deg` the jaw tips meet at 96 px or larger. Every clip that ends a beat (hello, celebrate, connected) includes a two-snap claw click: shut 90 ms, open 140 ms, shut 90 ms, then rest. That snap is Pinch's signature move and gives him his name.
8. **Expression set, matching the engine contract.**
   - Moods:
     - `idle`: slow 4 s breath, and a blink every 3–6 s at random.
     - `focused`: lids at 20%, lens lit.
     - `listening`: lean in, with the antennae tilted forward.
     - `thinking`: lens tapping the chin, eyes up-left.
     - `sleepy`: lids at 70%, with slow sways.
     - `reading`: lens over the eyes, which scan left to right.
   - Clips:
     - `hello`: crusher wave plus snap.
     - `sideeye`: lens to the eye with the magnified eye showing, one lid dry.
     - `nudge`: a lens tap toward the viewer, plus the sweat drop.
     - `celebrate`: C's ^ ^ eyes, the bloom, a hop, a double snap and sparkles from the claw tips.
     - `partial`: a half smile, one claw up, a small shrug.
     - `supportive`: kind outward lids, a slow nod, claws lowered.
     - `surprise`: eyes widen 115%, antennae spring.
     - `connected`: the lens glints green once.
   - Nothing frowns, scolds, cries or turns red.
9. **Light theme.** The outline is #365900 at 3 px for 96 px and up, 3.6 at 56 and 5.5 at 28 (B's `--pinch-ow` ladder). On white, the lens glint switches to `--pinch-shade` so it stays visible.
10. **Reduced motion.** `still: true` and `prefers-reduced-motion` both render the held pose for the mood, or the clip's key frame (`seek(clip, keyMs)`), with no idle breathing. The lens glow state still changes, because it carries information.
11. **Deliverables in `docs/design/pinch/`.**
    - `pinch.svg` (master, idle), `silhouette-16.svg`, `silhouette-20.svg`, `pivots.json`, a generator script, and `pinch.js` per the AlibiPinch contract.
    - A sheet showing every mood and clip on #000 and #FFF at 160, 96, 56 and 28, the notch at 16 and 20 pt (camera off and on, all four state tints), the in-context nudge toast, and the rig stress test from `judgement/rig-stress.png`.
