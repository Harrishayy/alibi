# Surfaces

Four surfaces tell one story: "I said X, Alibi saw Y, here's the proof, it was fair to me." All four share the tokens, the six springs and Pinch. The Mac runs the agent, and every other surface mirrors it.

## Notch island

The island lives in the MacBook notch (185 × 32pt on a 14" or 16" MacBook Pro; width from `auxiliaryTopLeftArea`/`RightArea`, height from `safeAreaInsets.top`).

- **Fill.** Solid `island` #000 with no material or glass. Anything else shows a seam against the hardware notch.
- **Shape.** One `RoundedRectangle` whose frame and radii animate. Never crossfade two shapes.
- **Content.** Inset 12pt, so inner cards are `radius-md` 16 inside the open `radius-xl` 28.
- **Focus.** It never steals focus. The panel becomes key only when the composer is clicked, and it resigns on Esc, on send, or on a click outside.

| State | Trigger | Size (w × h) · radii | Springs | Content | Pinch | Copy |
|---|---|---|---|---|---|---|
| `idle` | no session, no alert, pointer elsewhere | exactly the notch, 185 × 32. Bottom radius matches the hardware (≈10), top flare 6 | — | nothing. Clicks pass through (`ignoresMouseEvents`) | hidden | none |
| `live` | a session is running, a planned block is "now", or a reply is waiting | notch + 2 × 46 = 277 × 32. Bottom 12, flare 6 | wings out on `spring-snappy`, right wing +60ms | leading wing: Pinch. Trailing wing: the time left in `island-wing`, `accent-ink`, `.numericText(countsDown: true)` | 16pt still: `focused`; side-eye while drifting | `24m`, `45s`, `now`. Drifting: ■ `phone` |
| `peek` | the pointer rests in the notch for 0–0.35s | 289 × 36 (+12, +4). Bottom 14 | `spring-snappy` | as `live`; the wings brighten from 0.7 to 1 opacity | tilts 8° toward the pointer | as `live` |
| `expanded` | still for 0.35s, a click, or ⌥⌘A | 400 × auto (180–360). Bottom `radius-xl` 28, flare 12, `shadow-island` | open `spring-island`; content `spring-snappy` at +60, three tiers 30ms apart; close `spring-smooth` | **Header:** "ALIBI" (`island-wordmark`), online dot, Pinch. **Idle:** composer card, up to 4 habit chips with ⌘1–⌘4, a "next up" line, then streak and honesty line. **Live:** a session card (habit in `island-title`, 44pt `RingTimer` beside "24:07" in `island-timer`, on-task % stat, last 6 samples, drift line in `island-voice`), then Break, +10 min, Finish | 28pt: `listening` (idle) or `focused` (live) | placeholder "What are you about to do?"; "Next up: Drawing at 19:00" |
| `nudge` | a new alert with `kind: "nudge"` | 400 × ≈150. Bottom 28 | drop on `spring-bouncy`; one 360ms shake for `phone` only; close `spring-smooth` | Pinch with one `island-voice` line (only the noun in `warn-ink`), then Back to it (primary), This counts (secondary), Quiet 5 min (quiet). Stays until one is chosen | 56pt `sideeye` → `nudge` | "You said drawing. I've seen your phone for 3 minutes." |
| `verdict` | a new alert with `kind: "verdict"` | 440 × ≈190. Bottom 28 | drop on `spring-bouncy`; content tiers at +60 | Pinch beside `VerdictPill` and the % stat, a three-frame strip (96 × 54 frames, `radius-xs`), then See proof (secondary), Fix a moment (quiet). Auto-folds after 15s unless the pointer is over it | 64pt `celebrate` / `partial` / `supportive` | "Done. 25 of 25 minutes at the desk, pencil in hand." |
| `break` | `session.on_break` is set | wings, 277 × 32 | `spring-snappy` | leading: Pinch. Trailing: `cup` icon plus the break countdown, both in `partial-ink` | 16pt still `sleepy` | `4m` beside the cup |

- **Hover and leave.**
  - The island opens only after a 0.35s still dwell. If the pointer is still moving faster than 200pt/s, the dwell restarts.
  - It folds only after the pointer has spent 0.8s outside a margin of 32pt to each side and 48pt below the drawn shape.
  - Re-entries within 150ms of a close are ignored.
  - A click inside pins it open until Esc, send, or a click elsewhere.
  - Never make the leave zone tighter than the drawn island.
- **Other alerts** (planned block, pace, recap, report, info, synced) reuse the 400pt `nudge` frame with no shake and no `warn-ink`.
  - Planned reads "Drawing is planned now. Start?" with Start 25 min (primary), In 10 min, Skip today.
  - Synced reads "Strava's in: 5.2 km run, 28 min." and auto-folds after 6s. The others fold after 10s.
  - Pinch appears at 56pt, holding `idle`.
- **No notch** (an external display): a 200 × 32 pill at the top centre with a 16pt radius. The same states grow from it.
- **Full screen:** the island stays visible (`.fullScreenAuxiliary`), but the wings hide while full-screen video is frontmost.
- **Type floor** is 11pt. Wing values are the only place SF Pro Rounded runs at 13pt.

## Web dashboard

The dashboard is `http://127.0.0.1:8765`, served by the local daemon.

- **Layout.** One column, `max-width: 880px`, side gutter `clamp(16px, 5vw, 48px)`.
- **Spacing.** `space-6` between cards and `space-12` to `space-18` between sections.
- **Theme.** It follows the system, with `dark` first. The `body` carries the state class (`idle`, `live` or `verdict`). Sections move between states with FLIP on `spring-smooth`; they never jump.

**The 5-second story.** A first-time viewer reads top to bottom: what I said (hero and Now), what Alibi saw (the ring or the verdict), the proof (the contact sheet) and that it was fair (Fix a moment).

1. **Header** (48px): the "ALIBI" wordmark (13px, weight 800, +0.13em, `ink`), a state pill ("Watching" with a pulsing `on_task` dot while live, "Idle" otherwise), and a `settings` `IconButton` that opens Setup.
2. **Hero strip** (120px tall at most): Pinch at 64px (idle only), the honesty line in `h1` ("Claimed 2h 10m. Seen 1h 52m."), and `Alibi.StreakBadge` on the right ("6 days · 1 freeze left").
3. **Now**, which swaps in place (below).
4. **Latest verdict:** the contact sheet as the hero proof (6 frames, `radius-sm`, `hairline-strong` keyline, timestamps in `small` tnum), the three-sentence verdict in `voice`, and Fix a moment.
5. **Today:** a timeline of plan blocks, with hour labels in `small` tnum and a 2px `accent` now-line. Finished blocks show their verdict glyph.
6. **This week:**
   - Seven day dots: ● done, ◐ partly, ✕ slacked, – rest, ◌ not yet.
   - Claimed-versus-seen paired bars per day: claimed as a hollow `hairline-strong` outline, seen in `accent`.
   - The report quote in `voice`, with Pinch `reading` when the report is open.
7. **Sessions:** one row per session (habit, time, claimed vs seen, verdict pill). A row expands on `spring-smooth` to show its frames.
8. **Setup**, in a drawer from the right (`dur-drawer`, `ease-drawer`), with tabs Connections, Habits and Your data.

**What swaps per state:**

| Slot | `idle` | `live` | `verdict` (up to 10 min, or until Done) |
|---|---|---|---|
| Hero Pinch | 64px `idle` / `listening` | moves into Now at 96px | stays in Now |
| Now | `Alibi.Composer`: 56px min height, `radius-lg`, `surface-2`, `hairline-strong`, placeholder "What are you about to do?", a 36px round `accent` send button with an `arrow-up` in `on-accent` (30% opacity until there is text), and 3 habit chips with ⌘1–⌘3 | session card: 96px Pinch `focused`, a 160px `RingTimer` (10px stroke, `accent` on `surface-2`) with "24:07" in `display`, on-task % as `Stat`, `SampleStrip` of the last 6 with `develop`, the drift line in `voice`, then Break, +10 min, Finish | verdict card: `VerdictPill`, % as `Stat`, `Meter` (ticks at 0.4 and 0.7), the three sentences in `voice`, the contact sheet, then See proof, Fix a moment, Go again (primary) |
| Latest verdict | shown | shown | hidden (it is the Now card) |
| Today | shown | the live block glows with a 2px `accent` keyline | the finished block takes its verdict glyph |
| Nudge | — | `Alibi.Toast kind="nudge"`, top-right, neutral `surface-2` with a `PinchLine` | — |

When the verdict card is dismissed, it FLIPs down into the Latest verdict slot and the composer returns to Now.

## iPhone app

The iPhone app is a full companion.

- **Data.** It reads the Mac through the secret-gated phone listener (`GET /phone/state`), polling every 2–3s while in the foreground and never in the background.
- **Theme.** It follows the system appearance, designed `dark` first.
- **Type.** Dynamic Type throughout, with every target at least 44 × 44pt.
- **Haptics.** `.success` on done, `.warning` on a nudge, `.selection` on a correction.
- **Glass.** None of its own; the system tab bar keeps its default glass.

**Tabs:** Today (`clock`), Week (`calendar`), Health (`heart`). Settings sits behind a `gearshape` toolbar button as a sheet holding the Mac address, phone sync, Health permissions, Haptics and Quiet lobster.

**Today:**

- **Idle:**
  - A 160pt Pinch, `idle`.
  - The honesty line in `ios-title` ("Claimed 2h 10m. Seen 1h 52m.").
  - Today's plan blocks as rows (`ios-headline` habit, `ios-footnote` time).
  - "Start on Mac" chips for the top 3 habits. Each sends the habit to the Mac as a claim, for example "draw for 25 min".
- **Live:**
  - A 160pt Pinch, `focused`.
  - A 240pt ring (12pt stroke, `accent` on `surface-2`, round caps) driven by `ProgressView(timerInterval:)`.
  - Inside the ring, `Text(timerInterval:countsDown:)` in `ios-timer`.
  - On-task % in `ios-stat`, and "Last seen 18:04" with its `StatusDot` in `ios-footnote`.
  - The drift line in `ios-body`.
  - Break and Finish buttons.
  - A Live Activity starts here when none exists.
- **Verdict:**
  - Pinch's clip.
  - `VerdictPill` with the % in `ios-stat`.
  - The three sentences in `ios-body`.
  - "See proof on your Mac." The phone never receives frames.
- **Offline:** a card reading "Can't reach your Mac. Check you're both on Tailscale, then pull to refresh."

**Week:**

- Seven day dots, using the same glyphs as the web.
- Swift Charts `BarMark` pairs per day: claimed as a hollow outline, seen in `accent`.
- The week's honesty line, `StreakBadge` ("6 days · 1 freeze left"), and the report quote in `ios-body`.

**Health:**

- The daily totals the phone syncs to the Mac.
- "Synced 2 min ago" in `ios-footnote`.
- A Sync now button (secondary).
- The connection's state with its `StatusDot`.

## Live Activity

The Live Activity covers the Lock Screen and the Dynamic Island, on iOS 17 and later.

- **Presentation.** The background is `activityBackgroundTint(.black)` and `keylineTint` is `accent`. It is sans only, and every numeral uses `.monospacedDigit()`.
- **Budgets.** The payload stays under 4 KB. An activity lives up to 8 hours.
- **Starting.** It starts only while the app is in the foreground.
- **Ticking.** The timer and progress tick on their own through `Text(timerInterval:)` and `ProgressView(timerInterval:)`. Everything else updates only while the app is open.

Slot sizes for a 393pt-wide phone (430pt-wide in brackets):

| Presentation | Slot | Content | Style |
|---|---|---|---|
| Lock Screen | 371 [408] × ≈110, 14pt margins | **Row 1** (44pt): 32pt Pinch · habit ("Drawing") · the timer, right-aligned. **Row 2:** time-progress bar, 6pt tall, radius 3, `accent` on `surface-2`. **Row 3:** `StatusDot` + "On task 92% · last seen 18:04" | habit `la-title` 15 semibold; timer `la-timer` 34 rounded semibold, `ink`; row 3 13pt regular, `ink-2` |
| Compact leading | 52.33 [62.33] × 36.67 | 20pt Pinch silhouette, `pinch-body` | — |
| Compact trailing | 52.33 [62.33] × 36.67 | `Text(timerInterval:countsDown:)` in a fixed 40pt frame (the fixed frame stops `0:00:00` bloating the island). Drifting: the `iphone` glyph plus "3m" | `la-compact` 14 rounded semibold, `accent-ink`; drifting `warn-ink` |
| Minimal | 36.67 × 36.67 | circular `ProgressView(timerInterval:countsDown:)`, 2.5pt stroke, with a 10pt Pinch head inside. The ring is `accent` on task, `partial` on a break, `warn` while drifting | — |
| Expanded leading | system region | 44pt Pinch, still pose per status | — |
| Expanded center | system region | habit ("Drawing") over "On task 92%" | `la-expanded-center` 17 semibold; second line 13pt medium, `ink-2` |
| Expanded trailing | system region | the timer | 22pt rounded semibold, `ink` |
| Expanded bottom | system region | on-task bar (6pt, radius 3, `accent` fill to on-task %, `surface-2` track), then the drift or last-seen line | 13pt regular, `ink-2`; only the noun in `warn-ink` |

**Strings by status:**

| Status | Lock Screen row 3 / expanded bottom | Compact trailing | Pinch pose |
|---|---|---|---|
| `on` | "On task 92% · last seen 18:04" | `24:07` | `focused` |
| `drift` | "■ Phone · 3 min" | `iphone` glyph + `3m` | side-eye |
| `break` | "On a break · back 18:20" (the timer counts down the break in `partial-ink`) | `cup` glyph + `4m` | `sleepy` |
| `done` | "25 of 25 min on task" (the timer slot shows "✓ Done" in `accent-ink`) | `✓` | `celebrate` end frame |
| `partial` | "17 of 25 min on task" (timer slot "◐ Partly" in `partial-ink`) | `◐` | `partial` end frame |
| `slacked` | "6 of 25 min on task" (timer slot "✕ Slacked" in `warn-ink`) | `✕` | `supportive` end frame |

After the verdict, end with `dismissalPolicy: .after(.now + 1800)`. When `isLuminanceReduced` is true, drop the bar fills and the lens glow to outlines and keep all the text.
