# Pinch

Pinch is Alibi's witness: a small, original green detective lobster that notices what you do and says so, plainly and kindly. It gives the product Duolingo-level expressiveness without Duolingo's guilt. When Pinch is on screen, Alibi is speaking.

## Identity

- **Species and lineage.** Pinch is a lobster, a cousin of the agent-world lobsters (OpenClaw's red one, and NVIDIA NemoClaw's "green lobster" nickname), and copies neither. Its rendering is smooth flat vector, never pixel or 8-bit. Its temperament is calm and observant, never chaotic.
- **Name.** Always "Pinch", referred to as "it". Never call it Nemo-anything, NemoClaw, Molty, Clawd or "Claw".
- **Silhouette ("bean with mitts").**
  - A rounded bean body, width to height 1 : 1.15.
  - Two oversized claws, each about 45% of the body width, raised in a V beside the face.
  - Black dot eyes (`pinch-eye`) at about 22% of the head width, each with one white highlight (`pinch-shine`).
  - A small mouth line and two antennae.
  - It uses no NVIDIA logo, no eye-mark shapes and no copied artwork.
- **The lens.** Pinch carries a magnifying lens in its left claw. The lens is the detective cue and the camera-on light, and it must always tell the truth:
  - **Camera sampling:** the glass fills with `pinch-lens-glow` at 35% opacity.
  - **Camera off,** or the session runs on window titles only: the lens is an empty `pinch-lens` ring.
  - **No session:** the lens rests at Pinch's side, empty. The camera is off whenever no session runs, so the lens never glows then.
  - Never fake the glow for decoration.
  - The lens appears at 28 and above. During `celebrate` it is set down (hidden over 120ms) so both claws can clap, and it returns as the clip settles.
- **No costume.** It has no hat, no pipe and no coat. The lens alone says detective.
- **Colour.** Pinch uses only its own tokens:
  - `pinch-body` #76B900 (body, claws).
  - `pinch-belly` #97DC42 (belly, highlight).
  - `pinch-shade` #588C05 (shading segments).
  - `pinch-outline`, 1.5px: #365900 on light grounds, a #8FD400 rim on dark (drawn only with `rim`; by default dark grounds show no outline).
  - `pinch-eye` #000.
  - `pinch-shine` #FFF.
  - `pinch-blush`: #F2A900 at 40%, never red.
  - `pinch-spark` #AAF059 (sparkles).
  - `pinch-lens` and `pinch-lens-glow`.

  Pinch stays green in every verdict. It never turns red, amber or grey.
- **Build.** It is drawn in code only: `AlibiPinch` / `Alibi.Pinch` on the web (SVG plus a rAF rig), and SwiftUI Shapes with `KeyframeAnimator` on Apple surfaces. The only raster Pinch images are the app icon (rendered on #000 with `ImageRenderer`) and the reel's title card.

## Personality

Pinch is observant, dry and kind. Think of a friend who happens to be a very good witness.

- **Observant.** It reports what it saw, with a number: "I've seen your phone for 3 minutes." It never guesses at motives.
- **Dry.** It is understated, with one beat of wit at most, and never a pun pile. A win is stated, not shouted.
- **Kind.** It never shames, sulks or cries, and it never loses health. A bad verdict gets a soft shrug and an offer to fix the record.
- **Cheeky, never guilt-tripping.** Duo's cheek is welcome ("Phone again. 4 minutes this time."). Duo's guilt is not ("These reminders don't seem to be working.").
- **Fair.** When you correct it, it agrees at once and changes the verdict: "Fair. I've changed that one."

## Size ladder and level of detail

Use only these sizes. Don't scale between rungs.

| Size | Where | Detail | Motion |
|---|---|---|---|
| 16pt | island wings | silhouette: body, 2 claws, 2 eyes (5 shapes), solid fills, snapped to whole pixels, smallest feature 2px | still poses only: `focused`, side-eye while drifting, `sleepy` on break |
| 20px / 20pt | `Alibi.PinchLine` avatar, Live Activity compact leading | silhouette plus eye shine | blink only (web); still (Live Activity) |
| 28pt | island panel header | + antennae, mouth, outline or rim, lens | moods and one-shots |
| 32pt | Live Activity Lock Screen | as 28 | still pose per status |
| 44pt | Live Activity expanded | as 28 | still pose per status |
| 56pt | island nudge alert | + belly, blush, sweat drop, sparkles (full rig) | `sideeye` → `nudge` |
| 64pt / 64px | island verdict alert, web hero strip (idle) | full rig | verdict clips; `idle`, `listening` and `reading` in the hero |
| 96px | web Now card while live or showing a verdict (the `Alibi.Pinch` default) | full rig | all moods and clips |
| 160px / 160pt | big celebration, iPhone Today | + three leg pairs, tail fan, cheek highlight; `bloom` behind it during a celebration | all moods and clips |

Below 24, Pinch has no antennae, mouth, outline or lens. The Live Activity minimal presentation uses a 10pt silhouette head inside the progress ring, and this is the only exception to the ladder.

## Moods and clips

Moods are held or looping states (set them with `inst.set(mood)`). Clips are one-shots (`inst.play(clip)`). Every clip opens with a 120–180ms anticipation move, and the antennae lag the body by 60–90ms. Pinch's own springs use `spring-celebrate`. Play each event once per surface, keyed by its alert id (or by `pinch.seq` when the state carries one), so three clients polling the same state never double-fire.

| Mood / clip | Kind | Trigger signal | Priority | Duration | Line (`PinchLine`, `voice`) |
|---|---|---|---|---|---|
| `idle` | loop | `state.session` is null and no alert is up | — | 4000 loop: breathe 1 ↔ 1.025, blink 140ms every 3–6s at random, gaze drifts every 4–8s | none (the hero shows the honesty line) |
| `listening` | hold | the composer has focus or is being typed in | — | hold: eyes 1.1, gaze toward the field, antennae forward 8° | none |
| `focused` | loop | live session; the latest label is `on_task`, not drifting | — | 3000 loop: 4° lean, calm eyes 0.8, alternate claw taps every 1.5s, lens glowing | none (silence while you work) |
| `thinking` | loop | a verifier or vision call has been in flight for over 600ms | — | 1200 loop: lens raised to the eye, gaze up-left, antennae wiggle | "Checking the alibi…" |
| `sleepy` | loop | `session.on_break` is set, or 10 min with no interaction and no session | — | 5000 loop: eyes 0.15, slow breathe, a "z" drifts up, antennae droop | "On a break. Back at 18:20." |
| `reading` | hold | the nightly report is open | — | hold: holds a slip of paper; eyes scan every 1200ms | the report's first sentence |
| `hello` | clip | onboarding step 1, then the first dashboard open of the day | 1 | 1400: crouch, pop up, right claw waves 3× | "I'm Pinch. You say what you'll do; I check." |
| `connected` | clip | Strava, iPhone Health or Calendar links for the first time | 2 | 1000: claw thumbs-up, sparkle 0.6 | "Strava's connected. Your runs count as evidence now." |
| `surprise` | clip | a correction saves (`POST /api/sessions/{id}/correct` succeeds) | 3 | 700: eyes 1.3, a squash pop, then a "noted" nod | "Fair. I've changed that one." |
| `sideeye` | clip | a new alert with `kind: "nudge"` | 4 | 1300: looks toward the cause, eyes narrow 0.55, tilt −6°, sweat drop | "You said drawing. I've seen your phone for 3 minutes." |
| `nudge` | clip | chained straight after `sideeye` (it counts as the same one-shot) | 4 | 900: claw pulls back −15°, snaps to +35°, pinches twice | (same line) |
| `celebrate` | clip | verdict `done`; streak milestone | 5 | 1600: crouch, jump −18, land squash, clap ×2, blush, sparkles | "Done. 25 of 25 minutes at the desk, pencil in hand." |
| `partial` | clip | verdict `partial` | 5 | 1000: one claw up 30°, nods twice. Honest, not a party | "Partly. 17 of 25 minutes on task. The phone had the rest." |
| `supportive` | clip | verdict `slacked` | 5 | 1400: soft shrug, claws out 20°, slow blink. It stays green with no frown | "Slacked, by my count. Tap any frame if I got it wrong." |

When a clip ends, Pinch returns to the mood that fits the current state.

## Frequency caps

1. **Global cooldown:** at most one one-shot per 90 seconds per surface. `inst.play` enforces this. A higher-priority clip pre-empts a lower one, even inside the cooldown. Equal or lower priority is dropped, not queued. Pass `{force: true}` only for verdicts and for the `nudge` that follows `sideeye`.
2. **Nudges ride the nudge cooldown.** React only when a nudge is actually sent, never to a single sample, and at most 3 side-eyes per session. After the third, the alert still shows its line and Pinch holds `focused`.
3. **Quiet while you work.** No one-shots during on-task focus except the verdict. No motion while you type except `listening`. No reaction to the polaroid develop.
4. **Big celebrations are rare:** the first win ever, then streak days 3, 7, 14, 21 and every 7th after, and at most one a day. Every other `done` gets `celebrate` at its rung size with the 28-particle claw burst and no bloom.
5. **One stage at a time.** While Pinch plays a clip, other motion on that surface holds still.
6. **Rest when unseen.** Stop the loop when the view is hidden (`document.hidden`, the island collapsed, the app backgrounded). Freeze on a neutral `idle` frame after 2 minutes without interaction. Never run a loop in the island wings.
7. **Quiet lobster.** The Setup toggle "Quiet lobster" hides every one-shot and keeps the still pose and the lines.

## Tone rules

| Do | Don't |
|---|---|
| "I've seen your phone for 3 minutes." | "You let me down." |
| "Logged: 18 of 25 minutes." | "Are you even trying?" |
| "Slacked, by my count. Tap any frame if I got it wrong." | "You failed your session." |
| "Tomorrow, 20 minutes? I'll be here." | "Don't break my heart tomorrow." |
| "Phone again. 4 minutes this time." | "Busted. Caught you on your phone." |
| "Fair. I've changed that one." | "Are you sure? The camera doesn't lie." |
| "Three days in a row. That's how it starts." | "Don't lose your streak." |
| A soft shrug and a slow blink on `slacked` | Tears, a frown, a red or grey Pinch, a health bar |

Pinch speaks in the first person, in 12 words or fewer, with digits for numbers. It uses no "!" and no emoji, and only the noun of a bad fact goes in `warn-ink`.

## Haptics and sound

- **iPhone (on by default):**
  - `.sensoryFeedback(.success)` on `done` and on a streak milestone.
  - `.sensoryFeedback(.warning)` when a nudge lands.
  - `.sensoryFeedback(.selection)` on a saved correction.
  - Nothing on `partial` or `slacked`.
  - Haptics stay under reduced motion.
- **Mac (off by default):** both are opt-in in Setup.
  - Sound: `NSSound(named: "Pop")` at volume 0.3, for celebrations only.
  - Trackpad haptic: `NSHapticFeedbackManager.defaultPerformer.perform(.levelChange, performanceTime: .now)`.
  - Nudges stay silent.
- **Web (off by default):** opt-in only. A two-note chime for `done` (660 Hz → 990 Hz, 80ms each, gain 0.08, 10ms attack, 120ms release).
- **Never** play a sound for bad news. Silence reads as kinder.
- **Live Activity:** silent. Verdict alerts use `AlertConfiguration` with no sound.

## Where Pinch must not appear

- **On the evidence.** Never over or beside contact-sheet frames inside the sheet, in the proof lightbox, in exported evidence PNGs, or in the reel's frames. The reel's title card is the one exception.
- **Inside data.** Never inside a `VerdictPill`, a `StatusDot`, a `Meter`, a chart, a table row or a button.
- **In consent and privacy copy.** Camera permission, data deletion and "where frames go" stay plain, still text with no character.
- **In system errors.** Show crashes, offline daemons and failed requests as plain chrome copy with a fix. No sad Pinch.
- **In the idle island.** When nothing is live, the island is exactly the notch and draws nothing.
- **Twice on one screen.** One Pinch per view. On the dashboard, the same Pinch sits in the hero strip at 64px while idle and FLIP-travels into the Now card at 96px when a session goes live (`spring-smooth`), returning when the state is idle again. During a big celebration the overlay's 160px Pinch replaces it. A `PinchLine` avatar in a toast is the one allowed second Pinch.
- **As a recoloured status signal.** Status belongs to `StatusDot`, never to Pinch's body colour.
- **Off-brand.** Never with NVIDIA's logo or eye mark, OpenClaw's artwork, or a pixel-art treatment.
