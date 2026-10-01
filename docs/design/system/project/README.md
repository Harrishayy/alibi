Alibi checks your alibi. You say what you are about to do, a local agent gathers evidence, and Pinch, a small green detective lobster, tells you plainly what it saw. Every rule below serves one feeling: the calmest, most comfortable app on the desk, with a few moments of real theatre. Use the tokens, type styles and `window.Alibi` components named here, in both themes (`dark` first, then `light`), on all four surfaces: the web dashboard, the Mac notch island, the iPhone app and the Live Activity.

## Principles

1. **One idea per glance.** Lead every surface with one number and one sentence: "Claimed 2h 10m. Seen 1h 52m." Put charts, tables and history second. If a card needs two headlines, split it into two cards.
2. **Precision, not ornament.** Set everything in one sans superfamily (SF Pro, with SF Pro Rounded for big numerals). Build hierarchy from size, weight (400 / 500 / 600) and space, never from a second typeface. Give every number tabular figures so nothing jitters.
3. **Dark is the stage; colour is a signal.** Design in `dark` first: `bg` #000, `surface-1` #1A1A1A, `surface-2` #262626. Then check `light` as a full theme, not an inversion. Keep neutrals on at least 85% of any screen and `accent` green under 5% of the chrome. Show bad news as a dot, a word or a 10% wash, never as a red slab and never in green.
4. **Calm by default, theatre by exception.** Keep everyday motion under 300 ms with no bounce on structure. Spend the big motion on four rare moments: island bloom, nudge drop, verdict reveal and streak milestones.
5. **Honest, never shaming.** Pinch states facts in the first person, with numbers ("I've seen your phone for 3 minutes."). Make every verdict correctable in one click. Nothing is guilt-framed, nothing loses health, and nothing cries.
6. **One system, four surfaces.** The dashboard, island, iPhone app and Live Activity share these tokens, the same six springs and the same Pinch rig, so the product reads as one thing in a 60-second demo.

## Voice and copy

Write dry, honest and kind. Alibi is a witness, not a coach and not a cop.

- **Sentence case everywhere:** buttons, headings, labels, tabs, menu items. The only capitals in a row are the "ALIBI" wordmark.
- **Pinch speaks in the first person** ("I saw", "I've changed that one"). The UI chrome speaks in neutral imperatives with no "I" ("Start session", "Fix a moment").
- **Keep Pinch's lines to 12 words or fewer.** Lead with the fact and give the number as digits.
- **No "!" and no emoji**, ever, including on wins. A win is stated, not shouted.
- **Name the cause, not the person.** Set only the noun in `warn-ink` ("phone", "YouTube"), never the whole line. Never write "you failed", "lazy", "busted" or "are you even trying".
- **Always offer the fix.** Every error and every bad verdict ends with what to do next.
- Use British spelling, 24-hour times ("18:04"), "min" in chrome ("25 min"), "minutes" in Pinch's voice, and `2h 10m` for totals.

Ten real lines:

1. "You said drawing. I've seen your phone for 3 minutes."
2. "You said C++. That's been YouTube for 4 minutes."
3. "Back on the sketchbook. Noted."
4. "Done. 25 of 25 minutes at the desk, pencil in hand."
5. "Partly. 17 of 25 minutes on task. The phone had the rest."
6. "Slacked, by my count. Tap any frame if I got it wrong."
7. "Fair. I've changed that one."
8. "A week of alibis that checked out."
9. "Missed yesterday. I used your freeze; the streak's intact."
10. "Nothing claimed yet. What are you about to do?"

The full microcopy guide, with nudges, verdicts, empty states, errors, Live Activity strings and wing values, is the Voice section.

## Colour

Pick colours by token name only; never paste a hex into a component. Each theme defines every token.

**Surfaces.** Paint the page with `bg`, cards with `surface-1`, raised rows, inputs and the composer with `surface-2`, and pressed or selected rows with `surface-3`. Paint the island with `island` (#000 in both themes, because it has to merge with the hardware notch) and dimmed backdrops with `scrim`. Don't add any other surface colour.

**Ink.** Set primary text in `ink`, secondary text and meta in `ink-2`, timestamps and placeholders in `ink-3`, and text on a dark chip in a light theme in `ink-inverse`. `ink-3` is the faintest text allowed: #8F8F8F in dark (5.38:1 on `surface-1`, 4.68:1 on `surface-2`) and #6E6E6E in light (4.55:1 on #F2F2F2). It fails on `surface-3`; use `ink-2` there. Never set text fainter than `ink-3`.

**Lines.** Separate with `hairline` (rgba(255,255,255,.08) dark, rgba(0,0,0,.08) light). Use `hairline-strong` for input edges, the composer edge and the contact-sheet keyline.

**The green budget.** `accent` (#76B900) covers at most 5% of the chrome; Pinch is exempt. A full `accent` fill is allowed only on:

- the one primary button per view (`Alibi.Button variant="primary"`) and the composer send button;
- the progress stroke of `Alibi.RingTimer` and the fill of `Alibi.Meter`;
- the `on_task` `Alibi.StatusDot`;
- the 2px now-line on the Today timeline;
- the claw confetti and the celebration `bloom`.

Set text on any green fill in `on-accent` (#000, 8.71:1). It is never white. Set green *text* in `accent-ink` (#8FD400 dark, 9.60:1 on `surface-1`; #477200 light, which is `green-700`, 5.71:1 on #FFF and 5.01:1 on `accent-wash`). #4E7A00 is retired for light text because it fails on the wash (4.48:1). Use `accent-hover` and `accent-press` for button states only. Reserve the `green-*` ramp for Pinch, confetti and those wash-text cases; never build UI chrome from it.

**Status is colour plus shape, always.** Under protanopia, green and amber are indistinguishable (ΔE 0.6), so every status mark carries a shape, and every list or legend carries the word. Draw marks with `Alibi.StatusDot`:

| Status | Glyph | Token (mark · text) | Meaning |
|---|---|---|---|
| `on_task` | ● filled circle | `on-task` · `on-task-ink` | I saw you doing what you said. |
| `idle` | ○ 2px ring, hollow | `idle` · `idle-ink` | At the desk, but nothing happening. |
| `phone` | ■ filled rounded square | `phone` · `warn-ink` | Phone in hand. |
| `off_task` | ▨ disc with a 45° hatch | `off-task` · `warn-ink` | Something else on screen or desk. |
| `absent` | ◌ 1.5px dashed ring | `absent` · `absent-ink` | Not at the desk. |

`phone` and `off-task` share the red (#E5484D); the hatch is what tells them apart. In the `light` theme, draw marks smaller than 16px in their `-ink` token, because the bright fills fall under 3:1 on white (#76B900 is 2.41:1, #F2A900 is 2.01:1).

**Verdicts carry a glyph and a word.** Render them with `Alibi.VerdictPill`. The aliases `done`, `partly` and `slacked` point at the status tokens:

| Verdict | Pill | Fill · text |
|---|---|---|
| `done` | ✓ Done | `accent-wash` · `green-700` in light, `accent-ink` in dark |
| `partial` | ◐ Partly | `partial-wash` · `partial-ink` |
| `slacked` | ✕ Slacked | `warn-wash` · `warn-ink` |

Never paint a slab of `warn` or `partial`. Bad news is a `StatusDot`, a `warn-ink` noun, or a `warn-wash` 10% tint (`Alibi.Card tone="warn"`). When text must sit on a solid `warn` fill, set it in `on-warn` (#000, 5.37:1); white fails at 3.91:1.

**One gradient.** The only gradient in the product is the celebration bloom: `radial-gradient(closest-side, var(--bloom), transparent)`, with `bloom` = rgba(118,185,0,.35), sized 1.6× Pinch and centred behind it. Show it only on a big celebration (the first win, and streak days 3, 7, then every 7th). Don't use gradients on surfaces, text, buttons or borders, and don't use glass anywhere except the iPhone's system tab bar.

## Type

One superfamily, two registers. Use `--font-sans` for every word, `--font-rounded` for large numerals, and `--font-mono` only for keycaps (`Alibi.Kbd`) and IDs. Never load a serif, an italic or a third family.

- `--font-sans`: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Onest", system-ui, sans-serif`
- `--font-rounded`: `ui-rounded, -apple-system, "SF Pro Rounded", "Onest", system-ui, sans-serif`
- `--font-mono`: `ui-monospace, "SF Mono", Menlo, monospace`

Onest comes from Google Fonts (weights 400–600) and is only a fallback for viewers who aren't on a Mac.

**Rules.**

- Give every number `font-variant-numeric: tabular-nums` on the web, and `.monospacedDigit()` on Apple surfaces. That covers timers, percentages, counts, dates and table cells.
- Use three weights: 400 for body, 500 for voice and mono, 600 for headings, labels and numerals. The "ALIBI" wordmark is the only heavy (800) setting.
- Floors: 12px on the web and 11pt on Apple surfaces. On the web, only `label` and `mono` sit at 12px.
- **No uppercase eyebrows.** Name sections with sentence-case `h2` or `label`, never small tracked capitals. Only the wordmark is uppercase.
- Keep tracking between −0.025em and +0.01em. The only exception is the wordmark, at +0.13em.
- Put `text-wrap: balance` on `h1`–`h3` and `text-wrap: pretty` on prose. Cap prose at 62ch.
- In `dark`, body runs at line-height 1.6 with +0.01em tracking, because light text on black needs the air.

**Alibi's voice** is a style, not a font. Set Pinch's lines, the verdict sentence and the nightly report's sentences in `voice` (20/1.45, weight 500, −0.01em, `ink`). That weight step is what tells you Alibi is speaking rather than labelling.

**Web styles** (px, applied as `.t-<style>`):

| Style | Size / line-height | Weight | Tracking | Use |
|---|---|---|---|---|
| `display` | 56 / 1.0 | 600 | −0.025em | the live timer "24:07" (`--font-rounded`, tnum) |
| `h1` | 32 / 1.15 | 600 | −0.02em | the hero honesty line, greeting, onboarding step titles |
| `h2` | 22 / 1.25 | 600 | −0.015em | section titles: "Now", "This week" |
| `h3` | 17 / 1.35 | 600 | −0.01em | card titles, session names |
| `voice` | 20 / 1.45 | 500 | −0.01em | Pinch's lines, the verdict sentence, report sentences, the drift line |
| `body` | 16 / 1.55 (dark 1.6) | 400 | 0 (dark +0.01em) | default text |
| `small` | 13 / 1.45 | 400 | 0 | meta, timestamps, helper text |
| `label` | 12 / 1.3 | 600 | +0.01em | chips, field labels, table heads |
| `stat` | 32 / 1.0 | 600 | −0.02em | "82%", totals (`--font-rounded`, tnum) |
| `mono` | 12 / 1.4 | 500 | 0 | keycaps, session IDs |

**Island styles** (pt, dark only): `island-wordmark` SF Pro 12 heavy, tracking 1.6, "ALIBI" · `island-wing` Rounded 13 semibold, monospaced digits · `island-timer` Rounded 34 semibold · `island-title` 17 semibold · `island-voice` 15 medium · `island-body` 14 regular · `island-secondary` 12 regular at 60% white. The floor is 11pt.

**iPhone styles** use Dynamic Type. `ios-largetitle` is `.largeTitle` semibold, `ios-title` is `.title2`/`.title3` semibold, `ios-headline` is `.headline`, `ios-body` is `.body`, and `ios-footnote` is `.subheadline`/`.footnote`. `ios-caption` is `.caption` semibold, in sentence case. `ios-stat` is `.title` rounded semibold `.monospacedDigit()`, and `ios-timer` is 56pt rounded semibold `.monospacedDigit()`, scaled with `@ScaledMetric`.

**Live Activity styles** are sans only: `la-title` 15 semibold, `la-timer` 34 rounded semibold, `la-compact` 14 rounded semibold, and `la-expanded-center` 17 semibold. All numerals are monospaced.

## Space and shape

**Spacing.** Use only the ladder: `space-1` 4 · `space-2` 8 · `space-3` 12 · `space-4` 16 · `space-6` 24 · `space-8` 32 · `space-12` 48 · `space-18` 72.

- Card padding is `space-6` on the web and `space-4` in the island. On iPhone it is 20pt, the system inset and the one off-ladder value.
- Leave `space-6` between cards in a column, and `space-12` to `space-18` between dashboard sections.
- Inside a control, the gap between icon and label is `space-2`.
- The dashboard is one column at `max-width: 880px`, with a `clamp(16px, 5vw, 48px)` side gutter. Nothing scrolls sideways at 375px.

**Radii are concentric:** inner radius = outer radius − inset.

| Token | Value | Use |
|---|---|---|
| `radius-xs` | 6 | chips, keycaps, inline tags, sample thumbnails in the strip |
| `radius-sm` | 10 | buttons, inputs, contact-sheet frames, rows inside popovers |
| `radius-md` | 16 | cards on every surface, popovers, toasts |
| `radius-lg` | 22 | the composer, iOS sheets, the Live Activity's Lock Screen inner card |
| `radius-xl` | 28 | the open island shape |
| `radius-pill` | 9999 | pills, the send button, `StatusDot`, `StreakBadge` |

The island chain is the model to copy: the open shape is `radius-xl` 28, the content inset is 12, so cards inside are `radius-md` 16. A card with a 6px inset holds `radius-sm` 10 frames.

**Depth comes from hairlines, not shadows.** Separate a `surface-1` card from `bg` with a `hairline` edge and no shadow. Use the one float shadow, `shadow-float` (`0 12px 32px -8px rgba(0,0,0,.12), 0 0 0 1px rgba(0,0,0,.06)` in light), only on layers that float above the page: popovers, toasts, the correction popover, the Setup drawer and the proof lightbox. `shadow-island` (black 50% r6 y2 plus black 35% r24 y12) belongs to the open island only; the collapsed island has no shadow, because it would outline the hardware notch.

## Motion

Motion has one vocabulary on every platform. The Motion section has the full token table and the choreography for each signature moment.

- **Six springs.**
  - `spring-micro`: toggles, chip select, dot recolour.
  - `spring-snappy`: popovers, wings, inner island content, tickers.
  - `spring-smooth`: every close, sheets, ring start.
  - `spring-island`: notch to panel.
  - `spring-bouncy`: alert drop, verdict pill, streak bump.
  - `spring-celebrate`: Pinch only.

  On the web, write `transition: transform var(--spring-snappy-dur) var(--spring-snappy)`. In SwiftUI, write the explicit `.spring(duration:bounce:)` from the table.
- **Durations.**
  - `dur-micro` 120ms: press, colour, focus.
  - `dur-small` 180ms: tooltip, hover lift, chip.
  - `dur-medium` 260ms: toast, content blur-in.
  - `dur-drawer` 420ms: drawer and sheet.
  - `dur-reveal` 900ms: count-up, meter fill, frame develop.
  - `dur-celebrate` 1600ms: Pinch celebrate, confetti.

  Easing: `ease-out` for enter and exit, `ease-in-out` for moving on screen, `ease-drawer` for drawers. Never use ease-in on UI.
- **Enter slow, leave fast.** An exit runs at 0.65× the enter duration with no bounce (260 → 170ms, 420 → 270ms). Close anything structural on `spring-smooth`.
- **Stagger.** Stagger entering lists by 40ms per item, capped at 6. The seventh item and later arrive with the sixth. Exits never stagger. The island uses 30ms across at most 3 tiers. Elements are clickable from frame 0.
- **Blur bridges swaps.** Use 2–8px of blur while content crossfades, and never more than 12px. Don't blur the island's black shape, only its content.
- **Animate `transform` and `opacity` only.** Meters fill with `scaleX`, never `width`. Never animate `backdrop-filter`. Never start from `scale(0)`; start at 0.94–0.97.
- **Reduced motion means fewer and gentler, not none.** Under `prefers-reduced-motion: reduce` or `accessibilityReduceMotion`, keep 150ms opacity and colour crossfades. Drop translate, scale, blur, shake, confetti and the bloom. Count-ups jump to their final value. Pinch crossfades between still poses over 200ms. Haptics stay. In SwiftUI, use `reduce ? .easeOut(duration: 0.15) : spring`.

## Iconography

Use `Alibi.Icon` for every icon on the web. It is a 1.5px stroke on a 24 grid with round caps and joins, drawn in `currentColor`. The set is: play, pause, stop, plus, check, x, camera, laptop, phone, run, heart, moon, calendar, settings, lens, cup, arrow-up, arrow-right, chevron-right, chevron-down, clock, flag, eye, sparkle, claw, undo, film.

- Render icons at 16, 20 or 24px. They inherit `ink-2`, or `ink` when active. Icons go green only inside a primary button (as `on-accent`) or as the active tab.
- **Never use emoji**, as icons, decoration or status. Evidence sources are `camera`, `laptop`, `run` (Strava) and `heart` (Health); plan blocks use `calendar`; breaks use `cup`.
- The streak glyph is `claw` with a digit, never a flame.
- Delete an icon that repeats its own label. Give an icon-only control (`Alibi.IconButton`) an `ariaLabel` and a target of at least 28px.
- On Apple surfaces, use the matching SF Symbol at regular weight: `camera`, `laptopcomputer`, `iphone`, `figure.run`, `heart`, `moon`, `calendar`, `gearshape`, `magnifyingglass`, `cup.and.saucer`, `clock`, `flag`, `eye`, `sparkle`, `arrow.uturn.backward`, `film`, `play.fill`, `pause.fill`, `stop.fill`. `claw` has no SF Symbol; draw it from Pinch's claw path.
- Show keyboard shortcuts with `Alibi.Kbd` (`--font-mono` 12, `radius-xs`, `surface-2`, `hairline-strong` edge), for example ⌥⌘A, ↵, esc, ⌘1.

## Pinch

Pinch is Alibi's witness: an original green detective lobster whose magnifying lens doubles as the camera-on light. It appears where Alibi has something to say, and it stays still the rest of the time. The Pinch section (Mascot.md) has the full identity, mood map and rules.

- **Where it appears.** It appears in the dashboard hero strip and Now card, in the island wings, panel and alerts, on iPhone Today, in the Live Activity, and beside any line Alibi speaks (`Alibi.PinchLine`). Render it with `Alibi.Pinch` or `AlibiPinch.mount`, never as an image.
- **Size ladder:**
  - 16pt: island wing.
  - 20px: `PinchLine` avatar, Live Activity compact.
  - 28pt: island panel.
  - 32pt: Live Activity Lock Screen.
  - 44pt: Live Activity expanded.
  - 56pt: nudge alert.
  - 64pt / 64px: verdict alert and web hero strip.
  - 96px: web Now card.
  - 160px / 160pt: web celebration and iPhone Today.

  Below 24, Pinch is a five-shape silhouette with no antennae, mouth or lens. Don't invent sizes in between.
- **Caps.**
  - At most one one-shot clip per 90 seconds per surface. The priority order is verdict > nudge > correction > connected > hello.
  - At most three side-eyes per session.
  - It never reacts to a single sample, and it never plays a one-shot while you are on task.
  - It is still in the island wings.
  - Its loop stops when the view is hidden and after 2 minutes without interaction.
- **Colour.** Pinch is always green (`pinch-body`), whatever the verdict. Bad news shows in its pose and in the copy, never by turning it red.

## Surfaces

**Dashboard** (`http://127.0.0.1:8765`). It is a single 880px column that tells the 5-second story, "I said X, Alibi saw Y, here's the proof, it was fair to me", in this order: hero strip, Now (the composer when idle, the live ring when running, the verdict when finished), latest verdict with its contact sheet, Today timeline, This week, Sessions. Setup lives in a drawer. Sections move with FLIP on `spring-smooth` when the state changes; they never jump. Nudges arrive as a neutral `Alibi.Toast kind="nudge"` with Pinch, never a red slab. It is dark-first and follows the system theme.

**Notch island** (`native/Island.swift`). It is solid `island` black with no material, and exactly the notch (185×32) when nothing is live. A live session adds 46pt wings: Pinch on the left, the time on the right. Hover opens it after a 0.35s still dwell to a 400pt panel (440pt for the verdict). It folds only after the pointer has spent 0.8s outside a margin of 32pt to each side and 48pt below, and a click pins it open until Esc, send, or a click outside. ⌥⌘A toggles it. Only `spring-island`, `spring-smooth` and `spring-snappy` move the shape and its content. On a display without a notch it becomes a 200×32 pill with a 16pt radius.

**iPhone** (`ios/AlibiPhone`). It is a full companion with three tabs: Today (a live mirror of the Mac session with 160pt Pinch, ring, timer and on-task %), Week (seven day dots and claimed-versus-seen bars) and Health (sync status and daily totals). Settings sits behind a toolbar gear. It polls the Mac's phone listener every 2–3s in the foreground, follows the system theme with `dark` as the reference design, and uses haptics for done, nudge and correction.

**Live Activity** (Lock Screen and Dynamic Island). It shows the live session at a glance: Pinch, the habit, a countdown that ticks on its own (`Text(timerInterval:)`), and the on-task %. It uses a black background, sans only, `accent` as the keyline tint, and no custom animation. Mid-session changes land only while the app is open, so it never promises real-time drift alerts. When the session ends it shows the verdict pill word and dismisses after 30 minutes.

## Accessibility

- **Contrast floors.** Text needs 4.5:1, and 3:1 at 24px+ or bold 19px+. Marks that carry meaning (status glyphs, icons, focus rings, meter fills) need 3:1. Check both themes.
  - Dark: `ink` #F2F2F2 is 15.55:1 on `surface-1`; `ink-2` #A6A6A6 is 7.15:1; `ink-3` #8F8F8F is 5.38:1; `accent-ink` is 9.60:1; `partial-ink` #FFC233 is 10.79:1; `warn-ink` #FF7A7E is 6.91:1.
  - Light: `ink-2` #5E5E5E is 6.48:1 on #FFF; `accent-ink` #477200 is 5.71:1; `partial-ink` #8A5F00 is 5.65:1; `warn-ink` #C4161C is 6.04:1.
  - Text on a green, amber or red fill is #000 (8.71, 10.45 and 5.37:1).
- **Focus ring.** Every interactive element shows a 2px solid `focus-ring` with a 2px offset on `:focus-visible`, drawn in `dur-micro`. It resolves to #76B900 in dark (6.28:1 on `surface-2`) and to `green-600` #588C05 in light (3.63:1 on #F2F2F2, 4.06:1 on #FFF). The offset keeps the ring on the page surface, so it stays visible around a green button. Never remove an outline without replacing it.
- **Targets.** Make targets at least 44×44pt on iPhone and at least 28×28px on the web and in the island; 36px is the default web button height. Leave `space-2` between adjacent targets.
- **Keyboard.** Every action works from the keyboard:
  - ⌥⌘A toggles the island.
  - `/` focuses the composer.
  - ↵ starts a session.
  - esc closes, in the island and on the web.
  - ⌘1–⌘9 pick a habit chip.

  Show the shortcuts with `Alibi.Kbd`.
- **Reduced motion.** Follow the Motion rules above, and test every signature moment with reduced motion on before shipping it. Each one has a fade fallback, so its meaning survives.
- **Colour plus shape plus word.** No state relies on hue alone: status uses the shape table, verdicts use glyph and word, and a nudge names its cause in text.
- **Screen readers.**
  - Pinch is decorative (`aria-hidden="true"`, `accessibilityHidden(true)`), and its line is real text.
  - `StatusDot` and `VerdictPill` expose their word ("Verdict: partly, 68%").
  - Nudges and verdicts announce politely (`role="status"`, `aria-live="polite"`).
  - Charts carry a sentence summary: "Claimed 2h 10m, seen 1h 52m."
- **Dynamic Type.** iPhone layouts reflow up to the accessibility sizes. The Today ring stacks above its stats at `.accessibility1` and larger.
