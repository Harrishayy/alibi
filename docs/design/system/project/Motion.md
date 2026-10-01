# Motion

Motion explains where something came from and where it went. Keep it quiet for anything seen a hundred times a day, and spend the theatre on the rare moments below. One set of springs drives all three platforms: the CSS `linear()` strings are simulated from the same physics as the SwiftUI springs (mass 1, stiffness (2π/d)², damping 4π(1−bounce)/d), so a verdict pill on the web and in the island lands the same way.

## Tokens

### Springs

| Token | SwiftUI | CSS easing · duration | Overshoot | Use |
|---|---|---|---|---|
| `spring-micro` | `.spring(duration: 0.25, bounce: 0)` | `var(--spring-micro)` · `--spring-micro-dur` 376ms | 0 | toggles, chip select, StatusDot recolour, press release on iPhone |
| `spring-snappy` | `.spring(duration: 0.35, bounce: 0.15)` | `var(--spring-snappy)` · `--spring-snappy-dur` 484ms | 0.6% | popovers, island wings, inner island content, digit tickers, composer morph |
| `spring-smooth` | `.spring(duration: 0.5, bounce: 0)` | `var(--spring-smooth)` · `--spring-smooth-dur` 686ms | 0 | **every close and collapse**, sheets, ring start, FLIP section moves |
| `spring-island` | `.spring(duration: 0.45, bounce: 0.2)` | `var(--spring-island)` · `--spring-island-dur` 619ms | 1.5% | notch → panel open |
| `spring-bouncy` | `.spring(duration: 0.5, bounce: 0.3)` | `var(--spring-bouncy)` · `--spring-bouncy-dur` 720ms | 4.5% | alert drop, VerdictPill, streak bump, sample-dot pop |
| `spring-celebrate` | `.spring(duration: 0.6, bounce: 0.4)` | `var(--spring-celebrate)` · `--spring-celebrate-dur` 1003ms | 9.4% | Pinch only, never UI |

The CSS duration is the settle time, which is longer than the felt duration; always pair a spring with its own `-dur` token. Never put more than 0.3 bounce on UI. In SwiftUI, write the explicit `.spring(duration:bounce:)` above instead of relying on the presets.

```css
:root{
  --spring-micro:var(--ease-out); --spring-snappy:var(--ease-out); --spring-smooth:var(--ease-out);
  --spring-island:var(--ease-out); --spring-bouncy:var(--ease-out); --spring-celebrate:var(--ease-out);
  --spring-micro-dur:376ms; --spring-snappy-dur:484ms; --spring-smooth-dur:686ms;
  --spring-island-dur:619ms; --spring-bouncy-dur:720ms; --spring-celebrate-dur:1003ms;
}
/* var() hides an invalid linear() until computed time, so gate it rather than relying on a fallback line. */
@supports (transition-timing-function: linear(0, 1)){ :root{
  --spring-micro:linear(0,.086,.252,.419,.569,.688,.777,.844,.891,.925,.949,.965,.977,.984,.989,.993,.995,.997,.998,.999,1);
  --spring-snappy:linear(0,.077,.234,.413,.573,.705,.808,.882,.932,.966,.986,.997,1.003,1.005,1.006,1.005,1.004,1.003,1.002,1.002,1);
  --spring-smooth:linear(0,.072,.217,.373,.517,.637,.731,.805,.86,.899,.929,.95,.965,.976,.983,.988,.992,.994,.996,.997,1);
  --spring-island:linear(0,.076,.237,.419,.588,.727,.832,.908,.957,.988,1.005,1.012,1.015,1.014,1.012,1.009,1.006,1.004,1.003,1.001,1);
  --spring-bouncy:linear(0,.047,.155,.296,.443,.584,.707,.81,.892,.952,.995,1.022,1.038,1.044,1.045,1.042,1.036,1.029,1.023,1.017,1.011,1.007,1.004,1.001,1,.999,.998,.998,1);
  --spring-celebrate:linear(0,.062,.207,.387,.572,.738,.871,.972,1.039,1.077,1.093,1.092,1.082,1.066,1.048,1.032,1.017,1.007,.999,.994,.992,.991,.992,.993,.995,.996,.998,.999,1);
}}
```

### Durations and easing

| Token | CSS | SwiftUI | Use |
|---|---|---|---|
| `dur-micro` | 120ms | `0.12` | press scale, colour, focus ring, chip state |
| `dur-small` | 180ms | `0.18` | tooltip, popover, hover lift, shadow fade |
| `dur-medium` | 260ms | `0.26` | toast, card expand, content blur-in, list items |
| `dur-drawer` | 420ms | `0.42` | Setup drawer, iOS sheet, onboarding step |
| `dur-reveal` | 900ms | `0.9` | count-up, meter fill, frame develop |
| `dur-celebrate` | 1600ms | `1.6` | Pinch celebrate, claw confetti |
| `ease-out` | `cubic-bezier(0.23, 1, 0.32, 1)` | `.timingCurve(0.23, 1, 0.32, 1, duration: d)` | enter and exit |
| `ease-drawer` | `cubic-bezier(0.32, 0.72, 0, 1)` | `.timingCurve(0.32, 0.72, 0, 1, duration: d)` | drawers and sheets |
| `ease-in-out` | `cubic-bezier(0.65, 0, 0.35, 1)` | `.timingCurve(0.65, 0, 0.35, 1, duration: d)` | something already on screen moving to a new place; breathing loops |

Use `ease` for pure colour changes and `linear` for time (the ring's one-second tick). Never use ease-in on UI.

### Grammar

- **Exits.** Exit at 0.65× the enter duration, with no bounce: 260 → 170ms, 420 → 270ms, 180 → 120ms. Close structure on `spring-smooth`.
- **Stagger.** Enter only: 40ms per item, capped at 6, so the seventh item and later arrive with the sixth. Each item goes from translateY 6px → 0 plus opacity, over `dur-medium` `ease-out`. Exits leave together in 120–170ms. The island uses 30ms across at most three tiers.
- **Blur.** Use 2–8px of blur to bridge a swap: 4px out, 8px in. The ceiling is 12px. Blur only elements up to 440×600px, and only while the swap runs.
- **Properties.** Animate `transform` and `opacity` only. Meters use `transform: scaleX()` with `transform-origin: left`. Add `will-change: transform` on start and remove it on `transitionend`. Never animate `width`, `height`, `backdrop-filter` or a shadow (fade a `::after` that carries the shadow instead).
- **Start sizes.** Never start from `scale(0)`. Start popovers and content at 0.94–0.97, and grow popovers from their trigger.
- **Interruption.** Anything a user can retrigger uses transitions or springs, which retarget mid-flight. Keyframes are only for fire-and-forget moments: the shake, confetti, and Pinch's one-shot clips.
- **Staging.** One reaction at a time. While a signature moment plays, hold every other animation on that surface (the polaroid develop, tickers and Pinch's loop) and let it resume after.
- **Skip.** The verdict reveal and the big celebration jump to their end state on click, Esc or Space, crossfading over 120ms.

### Everyday interactions

| Interaction | Web | SwiftUI |
|---|---|---|
| Press | scale 0.97 over `dur-micro` `ease-out`; release on `spring-micro` | `.scaleEffect(pressed ? 0.97 : 1)` on `spring-micro` |
| Hover lift (cards, chips; `(hover:hover) and (pointer:fine)` only) | translateY −2px over `dur-small`; the shadow fades in on `::after` | none (the iPhone has press only) |
| Chip select | fill crossfades to `accent-wash` on `spring-micro` | same |
| Popover / tooltip | opacity plus scale 0.96 → 1 from the trigger, `dur-small` `ease-out`; exit 120ms opacity only | `.transition(.opacity.combined(with: .scale(0.96)))` |
| Toast | translateY −12 → 0 plus opacity plus blur 4 → 0, `dur-medium`; exit 170ms | same values |
| Setup drawer | translateX 100% → 0 over `dur-drawer` `ease-drawer`; exit 270ms. Drag to close past 30% of its width or above 0.11 px/ms, with 0.2× friction on over-drag | `.sheet` with `.presentationDetents([.medium, .large])` |
| Digit ticker | each digit is a 0–9 column moved by `translateY(-n × 1em)` on `spring-snappy` inside a 1em `overflow: hidden` box | `.contentTransition(.numericText(value:))` with `spring-snappy` |
| Ring timer, running | `stroke-dashoffset` ticks once a second, `linear 1000ms`. In the final 60s the stroke's opacity breathes 0.6 ↔ 1 over 2.4s `ease-in-out` | `Circle().trim(from: 0, to: p).animation(.linear(duration: 1), value: p)` |
| Loading | placeholders breathe opacity 0.5 ↔ 0.8 over 1.6s `ease-in-out`, with no shimmer sweep. Data blurs in (4 → 0, opacity, 240ms) while the placeholder fades out in 120ms | `.redacted(reason: .placeholder)` plus the same opacity breathe |
| Section reorder | FLIP: measure, invert, then transition `transform` to none on `spring-smooth` | `matchedGeometryEffect` plus `spring-smooth` |

## Reduced motion

Under `prefers-reduced-motion: reduce` (web) or `accessibilityReduceMotion` (SwiftUI), motion becomes fewer, gentler fades. Comprehension cues stay.

```css
@media (prefers-reduced-motion: reduce){
  :root{--spring-micro:ease;--spring-snappy:ease;--spring-smooth:ease;--spring-island:ease;--spring-bouncy:ease;--spring-celebrate:ease;
        --spring-micro-dur:150ms;--spring-snappy-dur:150ms;--spring-smooth-dur:150ms;--spring-island-dur:150ms;--spring-bouncy-dur:150ms;--spring-celebrate-dur:150ms}
  *,*::before,*::after{animation-duration:1ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important}
  .al-moves{transform:none!important;filter:none!important}
  .al-confetti,.al-bloom,.al-shake{display:none!important}
}
```

- Keep opacity and colour crossfades at 150ms. Drop translate, scale, blur, shake, confetti, the bloom, the ring's final-minute breathing, and the island's hover tilt.
- Count-ups and tickers jump to the final value. Meters and rings appear at their final value.
- Pinch: `AlibiPinch.mount(el, {still: true})` or `<Alibi.Pinch still>`. Moods hold a neutral frame, and each clip crossfades over 200ms to its most readable pose (`inst.seek(clip, ms)` at that pose).
- SwiftUI: `reduce ? .easeOut(duration: 0.15) : spring`. Swap `.scale` and `.blurReplace` transitions for `.opacity`.
- Haptics stay on iPhone.

## Signature moments

All times are in ms from the trigger. "Content in" always means opacity 0 → 1, blur 8 → 0 and scale 0.96 → 1 from the top, unless the recipe says otherwise.

### 1. Verdict reveal

The trigger is a new alert with `kind: "verdict"`. The budget is 2,600ms, and a click, Esc or Space skips to the end.

| t | Element | Change | Curve |
|---|---|---|---|
| 0 | live ring (island, iPhone) | closes to the final ratio. `done` overshoots to 102% and settles at 100% | `spring-bouncy` (`done`), `spring-smooth` (others) |
| 0 | web Now slot | live content leaves: opacity 1 → 0, blur 0 → 4, 120ms. The card shell FLIPs to the verdict height | `ease-out`, then `spring-smooth` |
| 120 | verdict card | rises 12 → 0px with opacity | `spring-smooth` |
| 270 | `VerdictPill` | content in, with scale from 0.94 | `spring-bouncy` |
| 420 | percentage (`stat`) | counts 0 → ratio in rAF, `tabular-nums` | `dur-reveal` `ease-out` (ends 1320) |
| 420 | `Meter` | `scaleX` 0 → ratio, in sync with the count | `dur-reveal` `ease-out` |
| 560 | contact-sheet frames | translateY 6 → 0 plus opacity, 40ms stagger, cap 6 | `dur-medium` `ease-out` |
| 1000 | Pinch | `celebrate` (1600) / `partial` (1000) / `supportive` (1400) | clip timeline |
| 1000 | verdict sentence (`voice`) and actions | opacity 0 → 1, translateY 4 → 0. Actions are clickable from 0 | `dur-medium` `ease-out` |
| 1000 | claw confetti (`done` only) | 28 particles in a 60° cone from Pinch's claws | 1100–1600ms each, `cubic-bezier(.2,.6,.4,1)` |
| 1000 | iPhone haptic (`done` only) | `.sensoryFeedback(.success)` | — |
| 2600 | end | everything at rest | — |

- **Confetti mix:** `accent` 50%, `accent-ink` 25%, #FFF 15%, `partial` 10%. Shapes are claw paths, four-point sparks and 3px dots. Each particle travels `translate(dx, −h)` → `translate(1.4dx, g)` across three keyframes, rotates ±240°, and fades over its last 30%. Use WAAPI and remove the nodes on `finish`.
- **Big celebration** (the first win ever, and streak days 3, 7, 14, 21 and every 7th after): Pinch plays at 160px in a centred overlay on `scrim`. The `bloom` fades in over `dur-medium` at 1000 and out over the last 400ms of the clip. Hold the overlay until 2600, then exit in 170ms. At most one big celebration per day.
- **Partial:** no confetti and no bloom. The meter fills in `partial`, and the pill is ◐ Partly.
- **Slacked:** no confetti, no shake and no bloom. The meter fills in `warn`, Pinch plays `supportive` and stays green, and the sentence offers the fix ("Tap any frame if I got it wrong.").
- **Island verdict alert:**
  - The shape drops from the wings to 440 × ~190 on `spring-bouncy`.
  - Content follows at +60 in three tiers 30ms apart: Pinch 64 with the pill, then the three-frame strip, then the actions.
  - Pinch's clip starts at +300 after the drop.
  - It auto-folds after 15s unless the pointer is over it.
- **Reduced motion:** the card, pill, sentence and frames fade in together over 150ms. The percentage and meter show their final values. Pinch holds the clip's end pose. There is no confetti and no bloom. The haptic stays.

### 2. Nudge drop

The trigger is a new alert with `kind: "nudge"`, which only fires once the nudge cooldown allows a nudge to be sent.

| t | Element | Change | Curve |
|---|---|---|---|
| 0 | island shape | wings → 400 × ~150; bottom radius 12 → 28; `shadow-island` fades in over `dur-small` | `spring-bouncy` |
| 60 | tier 1 | 56pt Pinch plus the line, content in | `spring-snappy` |
| 90 | tier 2 | the three buttons, content in plus translateY 6 → 0 | `spring-snappy` |
| 120 | Pinch | `sideeye` (1300: looks toward the cause, sweat drop), then `nudge` (900: claw pulls back −15°, snaps to +35°, pinches twice). It counts as one one-shot | clip timeline |
| 680 | island shape (`phone` only) | one shake: translateX 0, −6, 5, −3, 2, 0px over 360ms | `ease-out` keyframes |
| 680 | iPhone haptic | `.sensoryFeedback(.warning)` | — |

- **Copy:** "You said drawing. I've seen your phone for 3 minutes." Only "phone" is in `warn-ink`. The buttons are Back to it (primary), This counts (secondary) and Quiet 5 min (quiet).
- The alert stays until one of those is chosen. It closes like the island (recipe 3).
- **Soft drift** (`idle`, `off_task`, `absent`) gets the same drop with no shake.
- **Web:** `Alibi.Toast kind="nudge"` sits top-right on `surface-2` with `shadow-float`. It enters translateY −12 → 0 with opacity and blur 4 → 0 on `spring-bouncy` and carries a 20px `PinchLine`. It never shakes, never fills red, and leaves in 170ms.
- **Reduced motion:** the shape resizes on `.easeOut(duration: 0.15)` with no overshoot. Content fades in over 150ms. There is no shake, and Pinch holds the side-eye end pose. The haptic stays.

### 3. Island bloom

The trigger is the pointer resting still in the notch for 0.35s, or a click.

| t | Element | Change | Curve |
|---|---|---|---|
| 0 | shape | frame → 400 × auto; bottom radius 12 → 28; top flare 6 → 12. Anchored at the notch top centre, as one `RoundedRectangle` whose frame animates | `spring-island` |
| 0 | wings | opacity → 0, blur 0 → 4, scale → 0.9, over 100ms | `ease-out` |
| 0 | shadow | `shadow-island` fades in over `dur-small` | `ease-out` |
| 60 | tier 1: header | "ALIBI" wordmark, 28pt Pinch, online dot; content in | `spring-snappy` |
| 90 | tier 2: main | the composer (idle) or the session card (live); content in | `spring-snappy` |
| 120 | tier 3: footer | chips, "next up" line, streak and honesty line; content in plus translateY 6 → 0 | `spring-snappy` |
| 120 | Pinch | `idle` → `listening` (idle island), or holds `focused` (live) | mood crossfade 180ms |

- **Close** (the pointer has spent 0.8s outside the 32pt side and 48pt bottom margin, or Esc):
  - Content leaves first: opacity plus blur 4, 100ms `ease-out`.
  - At +100 the shape collapses on `spring-smooth`, with no bounce, because an overshoot inside the hardware notch reads as a glitch.
  - The wings return x ±24 → 0 with opacity on `spring-snappy`, the right wing 60ms after the left.
- **⌥⌘A** (keyboard): the same shape on `.spring(duration: 0.3, bounce: 0.2)`, with no blur and no stagger. Content fades over 120ms.
- **Hover peek** (0–0.35s, before the bloom): the shape grows 12pt wider and 4pt taller on `spring-snappy`, the wings brighten from 0.7 to 1 opacity, and the wing Pinch tilts 8° toward the pointer.
- **Reduced motion:** the shape resizes on `.easeOut(duration: 0.15)`. Content fades in over 150ms with no blur, scale or tilt.

### 4. Claimed vs seen, and the proof

The trigger is the first dashboard paint and every change to today's totals.

| t | Element | Change | Curve |
|---|---|---|---|
| 0 | dashboard sections | translateY 6 → 0 plus opacity, 40ms stagger, cap 6 | `dur-medium` `ease-out` |
| 0 | hero honesty line ("Claimed 2h 10m. Seen 1h 52m.") | set in `h1`, with no motion on first paint. When a value changes, only the changed digits roll | `spring-snappy` per digit |
| 120 | contact-sheet frames | translateY 6 → 0 plus opacity, 40ms stagger, cap 6 | `dur-medium` `ease-out` |
| 240 | This week paired bars | claimed (hollow, `hairline-strong`) and seen (`accent`) grow `scaleY` 0 → value from the baseline, 40ms per day, cap 6 | `spring-smooth` |
| on click | proof lightbox | the frame FLIPs from its thumbnail to the centred lightbox; `scrim` fades in over `dur-medium` | `spring-snappy`; close `spring-smooth` back into the thumbnail |

- The week's data loads once, then holds still. Never replay the bars on a 15-second refresh; only changed bars retarget.
- **Reduced motion:** sections, frames and bars fade in over 150ms at their final values. The lightbox crossfades.

### 5. Composer → session

The trigger is ↵ or the send button in the composer, on the web or in the island.

| t | Element | Change | Curve |
|---|---|---|---|
| 0 | send button | scale 0.97 | `dur-micro` `ease-out` |
| 0 | typed text | blur 0 → 2 with opacity → 0, over 120ms | `ease-out` |
| 0 | habit chips | leave together: opacity → 0 over 120ms, with no stagger | `ease-out` |
| 120 | composer field | FLIP-morphs into the session card's rect. The web measures both rects and inverts; SwiftUI uses `matchedGeometryEffect(id: "composer", in: ns)` | `spring-snappy` |
| 300 | session card content | habit title, then `RingTimer`, then `Stat`, then `SampleStrip`: content in, 40ms stagger | `spring-snappy` |
| 340 | ring | arc draws 0 → current progress | `spring-smooth` |
| 340 | Pinch | `listening` → `focused` | mood crossfade 180ms |
| 400 | island wings | slide out x ±24 → 0 with opacity; the right wing at +60. The value uses `.contentTransition(.numericText(countsDown: true))` | `spring-snappy` |

- **iPhone:** on the next poll (within 3s), Today swaps from idle to live with opacity and scale 0.96 → 1 on `spring-smooth`. A Live Activity starts if the app is in the foreground.
- **Reduced motion:** the composer and the session card crossfade over 150ms. The ring appears at its value, and the wings fade in.

### 6. Fix a moment

The trigger is a click on any sample dot or contact-sheet frame.

| t | Element | Change | Curve |
|---|---|---|---|
| 0 | correction popover | opacity plus scale 0.96 → 1, `transform-origin` at the clicked dot (computed, never a fixed corner) | `dur-small` `ease-out` |
| save | popover | leaves: opacity → 0 over 120ms, with no scale | `ease-out` |
| save + 0 | the corrected `StatusDot` | crossfades colour and morphs shape; pops scale 0.6 → 1 | `spring-micro`, pop `spring-bouncy` |
| save + 80 | on-task % | the digits roll to the new value | `spring-snappy` |
| save + 80 | `Meter` | `scaleX` retargets | `spring-smooth` |
| save + 160 | `VerdictPill` (if the verdict changes) | the old pill leaves with blur 4 over 120ms; the new pill enters scale 0.94 → 1 | `spring-bouncy` |
| save + 200 | Pinch | `surprise` (700), then a "noted" nod | clip timeline |
| save + 200 | `PinchLine` | "Fair. I've changed that one." content in | `dur-medium` `ease-out` |
| save + 0 | iPhone haptic | `.sensoryFeedback(.selection)` | — |

- An `Undo` quiet button stays in the PinchLine for 6s.
- Esc closes the popover without saving.
- **Reduced motion:** the popover fades. The dot recolours over 150ms with no pop, numbers jump, and Pinch holds the nod pose.

### 7. Live Activity

The system ignores `withAnimation` and `.animation` inside a Live Activity, so the motion comes from the system's own transitions plus views that tick by themselves.

| Event | What moves | How |
|---|---|---|
| Session start (app in the foreground) | the island grows from the camera to the compact presentation | system. Call `Activity.request` with `staleDate` set to the session end |
| Every second | timer and progress | `Text(timerInterval: start...end, countsDown: true)` and `ProgressView(timerInterval:countsDown:)`. They tick with zero updates |
| On-task % changes (app open) | the number | `.contentTransition(.numericText())`; the system blurs the change |
| Drift (app open) | compact trailing swaps the timer for the `phone` glyph plus "3m" in `warn-ink`; Pinch swaps to the side-eye still | system blur replace |
| Session end | the verdict pill word replaces the timer: `done`, `partly` or `slacked` | `activity.end(…, dismissalPolicy: .after(.now + 1800))`. An `AlertConfiguration` (silent) is sent for verdicts only, and it briefly expands the island |
| Always-On (`isLuminanceReduced`) | nothing | drop the lens glow and bar fills to outlines, and keep the text |

Pinch in a Live Activity is a still pose per status (`focused`, side-eye, `sleepy` on a break, `celebrate` end frame on done). Never animate it there. Don't promise real-time drift on the phone: updates land only while the app is open.

### 8. Polaroid develop

The trigger is a new sample in the live session (`labels` grows). It runs at most once per sample, and Pinch never reacts to it.

| t | Element | Change | Curve |
|---|---|---|---|
| 0 | `SampleStrip` | existing frames shift one slot left; the frame leaving the strip (beyond 6) fades out over 120ms | `spring-snappy` |
| 0 | new frame | enters translateY 6 → 0 with opacity | `dur-medium` `ease-out` |
| 0 | new frame | develops: `filter: grayscale(1) brightness(1.5) blur(6px)` → `none` | `dur-reveal` `ease-out` (ends 900) |
| 900 | its `StatusDot` | pops scale 0.6 → 1 in its status shape and colour | `spring-bouncy` |

- **SwiftUI:** `.saturation(0).brightness(0.4).blur(radius: 6)` → `1 / 0 / 0` with `.easeOut(duration: 0.9)`.
- Use `<Alibi.SampleStrip develop>` to opt in. Thumbnails stay at 64px or smaller so the filter stays cheap.
- **Reduced motion:** the new frame fades in already developed over 150ms, and the dot appears without a pop.

### Streak bump

The trigger is a streak increment after a verdict. `StreakBadge` scales 1 → 1.18 → 1 on `spring-bouncy`, and its digit rolls on `spring-snappy` at +80. On a milestone the big celebration (recipe 1) follows. Under reduced motion the digit crossfades over 150ms.
