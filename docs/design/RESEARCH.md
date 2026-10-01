# Alibi design dossier

The design and build team works from this file. It condenses eight research notes in [`research/`](research/). Read the linked file when you need more depth. Where the research disagrees, the decisions here win (see §3). Budget: about 5 h wall-clock, including the demo.

Sources: [01 Claude & calm](research/01-claude-and-calm-products.md) · [02 NVIDIA brand & mascot](research/02-nvidia-brand-and-nemoclaw.md) · [03 Mascot animation](research/03-mascot-character-animation.md) · [04 Motion](research/04-motion-system.md) · [05 Island & Live Activity](research/05-island-and-live-activities.md) · [06 Habit UX](research/06-habit-ux-benchmarks.md) · [07 Typography](research/07-typography.md) · [08 Codebase audit](research/08-codebase-ui-audit.md)

---

## 1. The bar

"The most comfortable app in the world", applied to Alibi:

1. **One idea per glance.** Every surface leads with one number and one sentence: "Claimed 2h 10m. Seen 1h 52m." Charts come second. (06, 01)
2. **Two voices.** Alibi *speaks* in a roman serif. You *control* it in a sans. Every number uses tabular figures, so nothing jitters. (07, 01)
3. **Colour is a signal.** Neutrals cover at least 85% of any screen, and green stays under about 5% outside the mascot. Bad news is a dot, a word or a 10% tint. It is never a red slab and never green. (01, 02)
4. **Calm by default, theatre by exception.** Everyday motion runs under 300 ms with no bounce on structure. Four rare moments get the big motion: island bloom, nudge drop, verdict reveal, streak. (04)
5. **Honest, never shaming.** Pinch states facts in the first person, with numbers ("I've seen your phone for 3 minutes."). Every verdict can be corrected in one click. Nothing is guilt-framed, nothing loses health, and nothing cries. (03, 06)
6. **One system, three surfaces.** The dashboard, the island and the iPhone share the same tokens, the same six springs and the same mascot rig, so the demo reads as one product. (04, 08)

---

## 2. Decisions

### 2.1 Type: Pairing A (07)
*Reason: it keeps Claude's serif-voice / sans-control split, removes Inter (the only font the impeccable hook flags), and every numeral face it uses has tnum.*

- **Web:** Source Serif 4 (opsz 8–60, weight 400–600, roman only) for display, plus Figtree (400–700) for UI and numbers. Code uses `ui-monospace`. Drop Newsreader, Inter, JetBrains Mono and the unused italic axis. Use the metric-matched fallbacks in 07 §7.
- **Apple:** New York (`design: .serif`) for the voice, SF Pro for UI, and SF Pro Rounded with `.monospacedDigit()` for numbers. All system fonts, so nothing to bundle.
- **Web scale (px, size/line-height, weight):**
  - display timer: 56/1.0, Figtree 500
  - h1: 36/1.15, serif 400
  - h2: 24/1.25, serif 450
  - quote (verdict and report): 20/1.45, serif 400
  - h3: 17/1.35, Figtree 600
  - body: **16/1.55**, 400; in dark mode, line-height +0.05 and tracking +0.01em
  - small: 13/1.45
  - label: 12/1.3, 600
  - stat: 32/1.0, 600, tnum
- **Island (pt):**
  - wordmark: SF Heavy 12, tracking 1.6
  - wing value: Rounded 13 semibold
  - timer: Rounded 34
  - title: New York 19/17
  - body: 14
  - secondary: 12 at 60% white
  - floor: 11 (fix `Island.swift:603`)
- **iPhone:** Dynamic Type styles. `.largeTitle` and `.title3` in serif; stats in `.title` rounded semibold with monospaced digits. Live Activities use sans only.
- **Rules:** sentence case everywhere. No uppercase mono eyebrows; there are 59 today, so delete them. Display tracking stays between −0.01 and −0.025em. Use `text-wrap: balance` on headings and `pretty` on prose.

### 2.2 Colour (02, 01)
*Reason: CLAUDE.md's palette passes once three small fixes go in. Status colours also need a shape alongside the colour, because green and amber look identical to someone with protanopia (ΔE 0.6).*

| Pair | Ratio | Use |
|---|---|---|
| `#000` on `#76B900` | 8.71 | all text on a green fill |
| `#4E7A00` on `#FFF` / `#F2F2F2` | 5.11 / 4.57 | green text, light mode |
| `#477200` on green wash `#EAF4D6` | 5.01 | replaces `#4E7A00` on washes (4.48 fails) |
| `#8FD400` on `#1A1A1A` / `#262626` | 9.60 / 8.35 | green text, dark mode |
| `#8A5F00` on `#FFF` · `#FFC233` on `#1A1A1A` | 5.65 · 10.79 | partial/idle ink |
| `#C4161C` on `#FFF` · `#FF7A7E` on `#1A1A1A` | 6.04 · 6.91 | warn ink |
| `#000` on `#E5484D` | 5.37 | text on red; white fails at 3.91 |
| `--faint` → `#6E6E6E` light / `#8C8C8C` dark | 5.10 / 5.18 | replaces failing `#8C8C8C` / `#767676` |

- **Green ramp for the mascot** (hue 130.8°):
  - 300 `#97DC42`: belly and highlight
  - 500 `#76B900`: body
  - 600 `#588C05`: shade
  - 800 `#365900`: outline on light backgrounds
  - 200 `#AAF059`: sparks
- **Shape encoding** (required):
  - on-task: ● filled
  - idle: ○ amber ring
  - phone: ■ red rounded square
  - off-task: red with a 45° hatch. **Retire `#C8362B`**, which can't be told apart from `#E5484D`.
  - absent: dashed grey ring
  - Verdict pills always carry a glyph and a word: `✓ Done` · `◐ Partly` · `✕ Slacked`.
- **Remove leftovers** (08 §2): `#C8362B`, `%23A39E95`, confetti `#7FA7D9`. The contact-sheet pill uses white on green, which breaks the black-on-green rule (`evidence.py:47`). The island's absent colour must be `#A6A6A6`.
- **No gradients** except one celebration bloom, `radial-gradient(closest-side, rgba(118,185,0,.35), transparent)`, sized 1.6× the mascot.

### 2.3 Radii, spacing, depth (01, 05)
*Reason: a single concentric ladder, and depth from hairlines rather than shadows, is what makes Claude feel quiet.*

- **Radii:**
  - 6: chips and inline elements
  - 10: buttons and inputs
  - 16: cards, web and island
  - 22: composer and iOS sheets
  - 28: island open shape (12 padding, so inner cards are 16 and stay concentric)
  - 9999: pills and the send button
- **Spacing:** 4 · 8 · 12 · 16 · 24 · 32 · 48 · 72. Card padding is 24 on web, 20 on iOS and 16 on the island. Sections sit 48–72 apart.
- **Hairlines:** `1px rgba(0,0,0,.08)`, or `rgba(255,255,255,.08)` in dark mode.
- **Shadows:** one token, for floating layers only: `0 12px 32px -8px rgba(0,0,0,.12), 0 0 0 1px rgba(0,0,0,.06)`. The open island gets `black .5 r6 y2` plus `black .35 r24 y12`, and no shadow when collapsed.
- **Layout:** a single dashboard column with `max-width: 880px` and 24px gaps between cards. Prose is capped at 62ch.

### 2.4 Motion tokens (04, with island values from 05)
*Reason: one spring vocabulary across three platforms. The CSS `linear()` strings are simulated from the same physics as the Swift springs.*

| Token | SwiftUI | CSS (settle) | Use |
|---|---|---|---|
| spring-micro | `.spring(duration: .25, bounce: 0)` | 376 ms | toggles, dot recolour |
| spring-snappy | `.spring(duration: .35, bounce: .15)` | 484 ms | popovers, wings, inner island content, tickers |
| spring-smooth | `.spring(duration: .5, bounce: 0)` | 686 ms | **all closes**, sheets, ring start |
| spring-island | `.spring(duration: .45, bounce: .2)` | 619 ms | notch → panel open |
| spring-bouncy | `.spring(duration: .5, bounce: .3)` | 720 ms | **alert drop**, verdict pill, streak bump |
| spring-celebrate | `.spring(duration: .6, bounce: .4)` | 1003 ms | mascot only |

- **Durations:** 120 ms (micro), 180 ms (small), 260 ms (medium), 420 ms (drawer). Exits run at 0.65× the enter duration, with no bounce.
- **Easing:** `--ease-out: cubic-bezier(.23,1,.32,1)` and `--ease-drawer: cubic-bezier(.32,.72,0,1)`. Never use ease-in on UI.
- **CSS springs:** paste the `linear()` strings and the `@supports` gate verbatim from 04 §2.
- **Stagger:** 40 ms per item, capped at 6 items. In the island it is 30 ms across 3 tiers.
- **Blur:** 2–8 px to bridge swaps, 12 px at most.
- **Performance:** animate transform and opacity only. Meters move from `width` to `scaleX`.
- **Reduced motion:** replace the blanket kill at `index.html:719` with 04's "fewer, gentler" block. In SwiftUI: `accessibilityReduceMotion ? .easeOut(duration: .15) : spring`. Haptics stay.
- **Island:** the 6 ad-hoc springs collapse to island / smooth / snappy.

### 2.5 Mascot: "Pinch", a calm green lobster witness (02, 03)
*Reason: it is original, it is a cousin of OpenClaw's red lobster without copying it, and it uses no NVIDIA marks. It gives Duo's expressiveness without Duo's guilt. Never call it Nemo-anything.*

- **Look:**
  - "Bean with mitts": body ratio 1:1.15, two claws each about 45% of the body width, raised in a V.
  - Black dot eyes with one white highlight. Eye width is about 22% of the head.
  - Antennae and mouth appear only at 24 pt and above.
  - Body `#76B900`, outline `#4E7A00` at 1.5 px (in dark mode, a `#8FD400` rim instead).
  - Blush is `#F2A900` at 40%, never red. Code only, no images.
- **Sizes:**
  - island wing: 16 pt (5 shapes, silhouette only)
  - island expanded: 28 pt
  - nudge alert: 56 pt
  - verdict alert: 64 pt
  - web hero strip: 64 px
  - web Now card: 96 px
  - celebration: 160 px
  - iPhone Today: 160 pt
  - Live Activity: 20 / 44 / 32 pt
- **Rig** (shared contract, a `Pose` struct in Swift and an object in JS): `bodySquash` (with volume kept: scaleX = 1/√scaleY), `bodyY`, `tilt`, `clawL`, `clawR`, `pinch`, `eyeOpen`, `lookX`, `lookY`, `mouthCurve`, `blush`, `antennaSway`, `sparkle`, `sweat`, `zzz`.
- **Layers:** a loop layer (idle and focused), a pose layer (held states) and a one-shot layer, as in Duolingo's Rive setup but ported to an 80-line rAF engine on the web and to `KeyframeAnimator` plus a blink `Task` in SwiftUI. The keyframe tables in 03 are canonical.

| Event (signal from 08 §4) | State | Length | Tier |
|---|---|---|---|
| nothing live | idle: breathe 1↔1.025 over 4 s, blink every 3–6 s | loop | MUST |
| session on task | focused: 4° lean, alternate claw taps every 1.5 s | loop | MUST |
| nudge alert fired | side-eye → pinch | 2400 ms | MUST |
| verdict done / streak 3, 7, 14, 30 | celebrate: crouch, jump −18, clap ×2, sparkles | 1600 ms | MUST |
| verdict partial | shrug: claw up 30°, nod ×2 | 1000 ms | MUST |
| verdict slacked | supportive: soft shrug, slow blink, stays green | 1400 ms | MUST |
| correction saved | surprise → "noted" nod | 700 ms | SHOULD |
| composer focused | listening: looks toward input | hold | SHOULD |
| break / 10 min idle | sleepy, with zzz | loop | SHOULD |
| onboarding / first open | hello wave | 1400 ms | COULD |
| VLM call in flight | thinking | loop | COULD |

- **Caps:** at most one one-shot per 90 s. Priority order is verdict > nudge > correction > connected > hello. At most 3 side-eyes per session. Pinch never reacts to a single sample. In the island wings Pinch is static, with no idle loop. Animation stops when the view is hidden, and after 2 min of idle. A "Quiet lobster" toggle is COULD.
- **Haptics:** iOS uses `.success` on done, `.warning` on a nudge and `.selection` on a correction. Mac sound and haptics are off by default.

### 2.6 Island states (05, 06; widths per the current CLAUDE.md)

| State | Size | Content | Spring |
|---|---|---|---|
| Idle | exactly the notch | nothing; clicks pass through | — |
| Live wings | notch + 2×46 | L: 16 pt Pinch tinted by state · R: `24m`, Rounded 13 with `numericText(countsDown:)` | snappy; right wing +60 ms |
| Hover peek | +12 w, +4 h | wings go from 0.7 to 1 opacity; Pinch tilts 8° toward the pointer | snappy |
| Expanded | **400** × auto | composer + ≤4 chips, *or* session card (ring, %, strip, drift line) · "next up" line · streak and honesty line | open: island · close: smooth |
| Nudge | **400** × ~150 | 56 pt Pinch, side-eye · serif line with **only the noun** in red ink · [Back to it] [This counts] [Quiet 5 min] | bouncy drop + one 360 ms shake (phone only) |
| Verdict | **440** × ~190 | 64 pt Pinch reaction · `✓ Done` · 3-frame strip · [See proof] [Something's wrong?] | bouncy |
| Break | wings | amber cup · countdown · sleepy Pinch | snappy |

- **Choreography:**
  - Open: the shape moves first; content follows at +60–70 ms with opacity, blur 8→0 and scale 0.96 from the top, then 30 ms per tier.
  - Close: content leaves in 100–120 ms, then the shape collapses flat. Never bounce into the hardware notch.
  - ⌥⌘A: shape only at 0.3 s, no blur.
- **Fill and fallbacks:** solid `#000` with no glass. On a display without a notch, fall back to a 200×32 pill.

### 2.7 iPhone IA and Live Activity (06, 05, 08)
*Reason: the phone can't reach `:8765`, and it shouldn't, so it mirrors through the existing secret-gated listener on `:8766`.*

- **Backend (MUST before any phone work):** `GET /phone/state`, a trimmed `/api/state` (session without frame URLs, alert, today, recent_verdict, plan.next, and the new `pinch` field). Optional: `POST /phone/say`.
- **App:** dark only, using the same tokens (`Theme.swift`) and the shared `Mascot.swift`.
  - **Today:** 160 pt Pinch, a live ring with a `Text(timerInterval:)` countdown, on-task %, and the honesty line. When idle, plan blocks and "Start on Mac" chips. Polls every 2–3 s while in the foreground.
  - **Week:** 7 dots, plus paired claimed/seen `BarMark`s.
  - **Health:** the existing table, plus "Synced 2 min ago".
  - **Streaks** tab and the settings gear: COULD.
- **App icon:** render Pinch on `#000` to PNG with `ImageRenderer`.
- **Live Activity:** feasible in **about 90 min, medium risk**.
  - It needs an xcodegen widget-extension target, `NSSupportsLiveActivities`, and a second bundle ID signed under team 87P4DWU22Q.
  - The timer and ring tick on their own via `Text`/`ProgressView(timerInterval:)`.
  - Mid-session updates land only while the app is open. There is no APNs, so don't promise real-time drift alerts on the phone.
  - Layout:
    - compact leading: 20 pt Pinch
    - compact trailing: timer in a fixed 40 pt frame
    - minimal: a ring
    - Lock Screen: 32 pt Pinch, habit, timer, bar, and "On task 92%"

### 2.8 Dashboard IA: the 5-second story (06)
*"I said X → Alibi saw Y → here's the proof → it was fair to me."*

1. **Hero strip**, at most 120 px tall: 64 px Pinch, the honesty line in serif display, and the streak pill (claw glyph, "6 days · 1 freeze left").
2. **Now / composer**, swapping in place:
   - Idle: the composer (56 px tall, 22 px radius, serif placeholder "What are you about to do?", 36 px round green send button with a black arrow) plus 3 chips.
   - Live: a 160 px ring, the % stat, the last 6 samples and the drift line.
3. **Latest verdict:** the contact sheet as hero proof, 3 sentences, and "Fix a moment".
4. **Today timeline**, with a 2 px green now-line.
5. **This week:** dot grid, paired bars and the report quote.
6. **Sessions**, then **Setup** in the drawer.

Section moves animate with FLIP rather than jumping. The nudge toast becomes a neutral card with Pinch.

---

## 3. Conflicts and resolutions

| Conflict | Resolution |
|---|---|
| Fonts: keep Newsreader + Inter (01, 02) vs Source Serif 4 + Figtree (07) | **07.** Inter trips the hook, Newsreader is on the reject list and has a smaller x-height, and the swap is a 10-minute font-URL change. |
| Mono uppercase eyebrows (01) vs banned (07, `hero-eyebrow-chip`) | **Banned.** Use sentence-case labels. Mono only for keycaps and IDs. |
| Body 16 (01) vs 15 (07) | **16.** Comfort is the brief, and Figtree's high x-height keeps it compact. |
| Five different spring sets (01, 03, 05, 06, island code) | **04's six tokens.** 05's open 0.42/0.80 maps to spring-island, close 0.45/1.0 to spring-smooth, and alert drop 0.50/0.72 to spring-bouncy. |
| Island widths 440/430/460 (05, old CLAUDE.md) vs 400/440 (current CLAUDE.md and code) | **400 / 400 / 440.** Less churn, and the 56–64 pt mascot fits. |
| Mascot sizes differ in 02, 03, 05 and 06 | One ladder (§2.5). Silhouette only below 24 pt. |
| Mascot engine: rAF rig (03) vs `phaseAnimator` mood enum (05) vs CSS keyframes (06) | **03's rig as the contract.** rAF on web, `KeyframeAnimator` in Swift, a `Timer` for blinks, and no `TimelineView` while idle (05's performance rule). |
| Eyes: white sclera (02) vs black dot eyes (03) | **Black dots with a highlight.** They read better at 16 pt on black. |
| Confetti on every done (04, 06) vs streaks only (01) | **Small claw burst** (28 particles) on done. The **big version** (160 px Pinch, bloom) only on the first win and at days 3, 7, then every 7. |
| Streak flame (04) vs no emoji, mascot glyph (06) | **Claw glyph + digit roll.** Fire implies urgency, and it is Duolingo's mark. |
| Green budget ≤5% (01) vs 8–10% (02) | **≤5% of chrome.** The mascot is exempt. |
| Phone reads `/api/state` with the key (06) vs `:8765` unreachable (08) | **08.** Add `/phone/state` on `:8766`. |
| Liquid Glass on iPhone (05) vs "no glass" (02) | Only the system tab bar's default glass. No custom glass anywhere, and never on the island or the web. |
| Full JS/CSS split before parallel work (08) vs the time budget | **Partial split** (§7, step 0): new files only, plus `main.swift`. Don't carve up the existing JS. |
| Off-task `#C8362B` vs phone `#E5484D` | **Merge into `#E5484D`** and use the hatch to tell them apart. |

---

## 4. Signature moments for the demo (ranked)

| # | Moment | What the viewer sees | Build |
|---|---|---|---|
| 1 | **Verdict reveal (done)** | Card rises · pill blurs in · % counts up while the meter fills (900 ms) · ring closes to 102% · Pinch celebrates · claw confetti · iPhone success haptic. Click to skip. Partial → shrug, slacked → supportive, no confetti. | web 45 + island 25 |
| 2 | **Nudge drop** | Alert drops out of the notch on bouncy · one shake · Pinch side-eye → pinch · "You said drawing. I've seen your phone for 3 minutes." | island 30 + web card 15 |
| 3 | **Island bloom** | Notch → 400 pt panel; content blurs in by tier; 28 pt Pinch is listening. The opening shot. | 30 |
| 4 | **Claimed vs seen + proof** | Hero honesty line plus the contact sheet. Nobody else shows this. | 25 (in M5) |
| 5 | **Composer → session** | Text blurs out; field FLIP-morphs into the ring card; wings slide out with `numericText`. | 35 |
| 6 | **Fix a moment** | Popover scales from the dot · dot recolours · % ticks · Pinch: "Fair. I've changed that one." | 20 |
| 7 | **Phone Lock Screen / Dynamic Island** | Pinch and a countdown ticking on the phone. | 90 (gated) |
| 8 | **Polaroid sample develop** | A new frame goes from grey/blur to sharp; the dot pops. | 15 |

---

## 5. Feature list (5 h wall-clock, 3–4 agent lanes)

| ID | Pri | Feature | Lane | Min |
|---|---|---|---|---|
| S0 | MUST | Baseline commit, `native/main.swift` split, `alibi/web/css/tokens.css` + `motion.css`, freeze token names, CLAUDE.md type section → Pairing A | serial | 20 |
| D1 | MUST | Design artifact: `alibi/web/pinch.html`, a pose sheet (every state × every size, light and dark) that doubles as the mascot test bench and a b-roll shot | mascot | (in M2) |
| M1 | MUST | Web tokens + type swap + colour fixes + radii + motion tokens + reduced-motion block + `width`→`scaleX` | web | 35 |
| M2 | MUST | Pinch web: SVG rig, rAF engine, 6 MUST clips, `window.pinch.play()` | mascot | 60 |
| M3 | MUST | `native/Mascot.swift`: Pose, shapes, KeyframeAnimator clips, LOD by size; no AppKit, so iOS reuses it | mascot | 60 |
| M4 | MUST | `/api/state` gains `pinch: {mood, event, seq}` (one server-side rulebook) + `/phone/state` | backend | 30 |
| M5 | MUST | Dashboard: hero strip, reorder, verdict reveal, nudge card, contact-sheet hero | web | 60 |
| M6 | MUST | Island: 3 springs, bloom choreography, Pinch at 16/28/56/64, nudge and verdict alerts, reduced motion, 11 pt floor | island | 60 |
| M7 | MUST | `evidence.py`: black-on-green pill, palette leftovers | backend | 10 |
| M8 | MUST | `./alibi.sh test` green, snapshot PNGs, fixtures for every alert | all | 15 |
| M9 | MUST | Demo: shot list, record (notch MacBook + phone), edit 60–90 s | user + F | 60 |
| S1 | SHOULD | iPhone Today/Week/Health on tokens, Pinch 160, haptics, app icon | phone | 60 |
| S2 | SHOULD | Composer→session FLIP + wing slide + polaroid develop | web/island | 35 |
| S3 | SHOULD | Correction surprise + listening + sleepy clips | mascot | 20 |
| S4 | SHOULD | Forgiving streak (1 free auto-freeze per week, rest days, partial ≥60% counts) + milestone big celebration | backend | 25 |
| S5 | SHOULD | Live Activity (start only if S1 is done by T+3:15; hard stop at 90 min) | phone | 90 |
| C1 | COULD | Hello/hatch onboarding step · thinking pose · "Quiet lobster" toggle | mascot | 25 |
| C2 | COULD | Digit-roll tickers · week paired bars on web | web | 30 |
| C3 | COULD | Detective lens = camera-on indicator · reel title card with Pinch · done chime | — | 30 |

**Timeline:**

| Time | Work |
|---|---|
| T+0:00–0:20 | S0 |
| T+0:20–2:20 | M1–M7 in lanes. Island uses a placeholder circle until M3 lands, around T+1:20. |
| T+2:20–3:20 | Integration, S1, S2 |
| T+3:20–4:00 | S3–S5 and polish. If behind, cut S5, then C\*. |
| T+4:00–5:00 | M8 and M9 (never cut) |

---

## 6. Open questions for the user

1. **Name:** "Pinch" (recommended), or Bailey / Alby?
2. **Fonts:** OK to swap Newsreader + Inter for **Source Serif 4 + Figtree**? It looks almost the same, and it passes the impeccable hook.
3. **Live Activity:** spend up to 90 risky minutes on it (a second bundle ID to sign), or ship the in-app Today screen only?
4. **Confetti:** a small burst on every "done" plus the big moment on milestones (recommended), or milestones only?
5. **Recording setup:** the notch MacBook's built-in screen (not an external display, which falls back to a pill) and the iPhone on the same Tailscale? Is the phone on iOS 26?

---

## 7. Risks

- **Merge hotspots.**
  - `index.html` (2211 lines), `Island.swift` (1838), `api.py` `/api/state`, `integrations.py` `phone_app`, and `CLAUDE.md`. Its design section has been rewritten twice, so a stale copy can make an agent revert the serif type.
  - Give each file one owner (08 §8). New code goes into new files: `mascot.js`, `Mascot.swift`, `Theme.swift`, `tokens.css`.
- **Baseline commit.** The working tree has uncommitted UI edits and an **untracked `data/backup-20261001-1636/`** that `.gitignore` doesn't cover. Never run `git add -A` blindly; stage paths, or ignore `data/backup-*`. Commit messages carry no AI co-author trailers.
- **Swift build.**
  - `swiftc Island.swift Mascot.swift` fails on top-level code. Move `Island.swift:1820–1838` into `native/main.swift`, update `build_native.sh` and the freshness check at `alibi.sh:24`.
  - `KeyframeAnimator` and `.blurReplace` need macOS 14 / iOS 17. Pass `-target arm64-apple-macos14` if `swiftc` complains.
  - `Mascot.swift` must import only SwiftUI, so iOS can add `../native/Mascot.swift` to its `sources` in `project.yml`.
  - Clicks rely on `FirstClickHostingView`, so don't replace the hosting view.
- **Snapshots.** Text fields render as yellow placeholders. Animations need fixture end states, so add a `--pose` or final-frame flag.
- **iOS signing.**
  - The widget extension needs its own provisioned bundle ID (`…alibi.widgets`). If 87P4DWU22Q is a personal team, App ID limits and 7-day profiles apply.
  - `Activity.request` only works in the foreground.
  - `Text(timerInterval:)` width bloat: use a fixed frame.
- **Event fragility.** `/api/state` carries only the latest alert, and Health and Strava have no real event. Without M4's `seq`, the mascot misfires or double-fires across three clients.
- **Time.** Polish keeps growing. Each lane gets a hard box, the demo hour is protected, and the cut order is S5 → C\* → S3 → S2.
- **Reduced motion and accessibility:** every celebration needs a fade fallback, or the demo machine's settings can hide it.
