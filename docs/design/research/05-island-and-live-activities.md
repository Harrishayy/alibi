# 05 — Mac notch island + iPhone Live Activity

Scope: (A) a spec for the Alibi notch island (`native/Island.swift`), (B) an ActivityKit Live Activity for `ios/AlibiPhone`. Local toolchain: Xcode 26.3, xcodegen 2.46.0.

## A. Mac notch island

### What the reference apps do
- **boring.notch** (open source SwiftUI). Open spring `response 0.42, dampingFraction 0.8`. Close `0.45, 1.0`, which is critically damped, so it doesn't bounce on the way out. Interactive spring `0.38 / 0.8`. Content comes in with `scale 0.8, anchor .top` plus opacity over 0.35 s, and the panel closes 100 ms after the pointer leaves ([ContentView.swift](https://github.com/TheBoredTeam/boring.notch/blob/main/boringNotch/ContentView.swift)). Corner radii: closed top 6 / bottom 14, open top 19 / bottom 24. Open size 640×190, plus 20 pt shadow padding ([matters.swift](https://github.com/TheBoredTeam/boring.notch/blob/main/boringNotch/sizing/matters.swift)). Window: `level = .mainMenu + 3`, `[.fullScreenAuxiliary, .stationary, .canJoinAllSpaces, .ignoresCycle]`, `isOpaque = false`, `hasShadow = false` (it draws its own shadow) ([BoringNotchWindow.swift](https://github.com/TheBoredTeam/boring.notch/blob/main/boringNotch/components/Notch/BoringNotchWindow.swift)).
- **NotchNook**: on hover, the notch "lightly pulses outward" and gains a drop shadow. When it opens, it "expands before gently bouncing back into place". When you leave, it "quickly returns". Opening is slow and bouncy; closing is fast and flat ([Digital Trends review](https://digitaltrends.com/?p=3656463)). Alcove sells the same promise of fluid transitions plus Lock Screen presence ([AlternativeTo](https://alternativeto.net/software/alcove/?p=2)).
- **Apple's Dynamic Island** ([HIG](https://developer.apple.com/design/human-interface-guidelines/live-activities), [WWDC23 "Design dynamic Live Activities"](https://developer.apple.com/videos/play/wwdc2023/10194/)):
  - The outer radius is 44 pt.
  - Content should sit concentric with even margins, which means inner radius = outer radius − margin.
  - Compact content should be "snug against the sensor… no wider than it needs to be".
  - Don't leave a "forehead" above the content.
  - Keep relative positions the same between compact and expanded.
  - Use numeric content transitions for counters.

### Alibi tokens (Swift)
| Token | Value |
|---|---|
| `open` spring | `.spring(response: 0.42, dampingFraction: 0.80)` (Island.swift currently uses 0.38/0.86, which feels a little dead) |
| `close` spring | `.spring(response: 0.45, dampingFraction: 1.0)` (no bounce on close) |
| `alertDrop` spring | `.spring(response: 0.50, dampingFraction: 0.72)` (one visible overshoot; this is what people notice in the demo) |
| `wing` spring | `.spring(response: 0.35, dampingFraction: 0.85)` |
| Outer bottom radius | collapsed = hardware notch (~10) · wings 12 · peek 14 · expanded/alerts 28 |
| Top "flare" radius (concave shoulders) | 6 collapsed → 12 open |
| Content padding | 12 pt on open shapes, so inner cards are 28 − 12 = **16 pt**. The existing 16 pt cards are already concentric. |
| Shadow | none when collapsed (it would outline the hardware notch). Open: two layers, `black 0.5 r6 y2` plus `black 0.35 r24 y12` |
| Fill | pure `#000` everywhere the shape touches the notch. Cards use `#1A1A1A`, hairline `white 0.08` |

### States
Widths come from `NSScreen.main.auxiliaryTopLeftArea/RightArea`. The notch is about 185×32 pt on a 14"/16" MBP, and its height is `safeAreaInsets.top`.

| State | Size (w × h) | Content | Mascot |
|---|---|---|---|
| Idle | notch × notch | nothing; the window ignores the mouse | hidden |
| Live wings | notch + 2×46 × notch h | leading: status glyph; trailing: `24m` in SF Mono 13 semibold with `.contentTransition(.numericText(countsDown: true))` | 16 pt head in the leading wing, blinking every 4–6 s at random |
| Hover peek (pointer still in the notch for 0–0.35 s) | +12 w, +4 h, `wing` spring | same as wings, but brighter (opacity 0.7 → 1) | head tilts 8° toward the pointer |
| Expanded composer | **440** × 180–360 (auto) | "What are you about to do?" field, chips, today ring | 28 pt, top-left, idle bob ±2 pt over 2.4 s |
| Session card (expanded with a session running) | 440 × ~260 | ring timer, on-task %, sample strip, drift line | 28 pt; mood follows on-task % |
| Nudge alert | **430** × ~150 | "You said drawing. I've seen your phone for 3 minutes." with [Back to it] [This counts] [Quiet 5 min] | **56 pt**, eyes on the phone, claws up, one 4° shake |
| Verdict alert | **460** × ~190 | verdict word + 3-photo strip + [Watch replay] [Something's wrong?] | **64 pt**. Done: claw-clap + 6 green sparks. Slacked: slumps 6 pt with eyes half closed (no red mascot; red is only for the word) |
| Break | wings | leading `cup.and.saucer` in `#F2A900`, trailing break countdown | 16 pt, eyes closed (sleeping) |
| Planned-block prompt | 430 alert | "Drawing is planned now — start?" [Start 25 min] [In 10 min] [Skip today] | 48 pt, waving |
| Reply bubble | composer + bubble | agent reply rises from under the field, 14 pt, max 3 lines, auto-fold after 6 s | 28 pt, mouth open, 2-frame talk loop |
| Onboarding hint (first run) | wings for 8 s | trailing shows a `⌥⌘A` keycap chip | 16 pt, single wave |

Note: Island.swift returns 400 for expanded and nudge and 440 for verdict. CLAUDE.md says 440 / 430 / 460. Change the code to match CLAUDE.md.

### Choreography
The shape leads and the content follows. On open, the content arrives in three parts:

1. **0 ms**: the shape starts the `open` spring and the shadow fades in over 180 ms.
2. **+70 ms**: the content comes in with `.opacity`, `.blur(radius: 8 → 0)` and `.scale(0.96, anchor: .top)` over 260 ms using `easeOut`.
3. **+120 ms**: secondary rows (chips, buttons) follow with the same transition, offset 6 → 0 pt, staggered 30 ms per row. Cap the stagger at 4 rows.

Close runs in reverse: content fades out over 120 ms with `easeIn` (no blur, which reads faster), then the shape starts the `close` spring at +80 ms. Wing values change through `numericText` only and never cross-fade the whole wing. Respect `accessibilityReduceMotion`: drop the blur and scale and keep opacity at 150 ms.

```swift
.transition(.asymmetric(
  insertion: .modifier(active: Reveal(p: 0), identity: Reveal(p: 1)).animation(.easeOut(duration: 0.26).delay(0.07)),
  removal: .opacity.animation(.easeIn(duration: 0.12))))
struct Reveal: ViewModifier { var p: CGFloat
  func body(content: Content) -> some View {
    content.opacity(p).blur(radius: (1-p)*8).scaleEffect(0.96 + 0.04*p, anchor: .top) } }
```

### Mascot rendering
Draw the mascot with SwiftUI `Shape`/`Path` (shell, two claws, eyes) so it scales cleanly from 16 to 64 pt. Animate it from a small `enum Mood { idle, focus, worried, proud, sleepy, wave }` with `.phaseAnimator` (macOS 14+).

Don't run a `TimelineView` while the island is idle. Blinking can be a `Timer` that toggles a Bool.

### Pitfalls
- **Click-through.** Keep `ignoresMouseEvents = true` except while the pointer is inside the drawn shape plus the leave margin (Island.swift already does this). Hit-test against the current shape, not the 640×460 panel.
- **Focus.** Use a `.nonactivatingPanel` style so opening the island never takes focus from the user's app. Become key only when the composer field is tapped, and `resignKey` on Esc, send, or a click outside.
- **Hover jitter.** Use hysteresis: 0.35 s dwell to open, 0.8 s outside the margin to close. Ignore re-entries within 150 ms of close. Never animate the size while the pointer is on the boundary. A peek nudge of `NSHapticFeedbackManager.defaultPerformer.perform(.alignment, …)` on open is free polish on Force Touch trackpads.
- **No-notch displays** (external monitor, demo capture): fall back to a 200×32 pill at top centre with a 16 pt radius.
- **Full-screen apps**: `.fullScreenAuxiliary` keeps the island visible. Hide the wings when a full-screen video is front-most.
- **The black must be exactly `#000`**, with no material and no glass. Anything else shows a seam against the hardware notch in screen recordings.

## B. iPhone Live Activity (ActivityKit, iOS 17+)

### Facts that constrain the design
- **Sizes.** On a 393-pt-wide phone, compact leading and trailing are **52.33×36.67 pt** each and minimal is **36.67–45×36.67**. Expanded and Lock Screen are **371 × 84–160**. On a 430-pt-wide phone they are 62.33 and 408 respectively. ([HIG specs](https://developer.apple.com/design/human-interface-guidelines/live-activities))
- **Margins.** Lock Screen margin is 14 pt and island radius is 44. Tint the keyline to match the content. Show the logo mark without a container, never the whole app icon.
- **Limits.** Truncation starts above 160 pt. Static plus dynamic data must stay **≤ 4 KB**. Images must not be larger than the presentation (minimal ≤ 45×36.67). An activity lives 8 h, then up to 4 h more on the Lock Screen. ([ActivityKit guide](https://developer.apple.com/documentation/activitykit/displaying-live-data-with-live-activities.md))
- **Animation.** The system ignores `withAnimation`/`.animation`. Text changes get a blur transition, and `.numericText(countsDown:)` works. Check `isLuminanceReduced` before animating, because Always-On skips animations.
- **Starting.** `Activity.request` needs the app in the **foreground**. You can update and end from the background, or start from the background via a `LiveActivityIntent`. Buttons in a Live Activity use App Intents.
- **Without APNs** there is no server-driven update. The only update paths are (a) the app in the foreground or briefly in the background, and (b) `Text(timerInterval:)` / `ProgressView(timerInterval:)`, which **tick on their own with zero updates**. Push-to-start (17.2+) and remote updates need a .p8 APNs key and an HTTP/2 sender, so skip them for the deadline.

### Layouts
- **Compact leading**: 20 pt mascot head (vector `Shape`, no oversized PNG) in `#76B900`.
- **Compact trailing**: `Text(timerInterval: start...end, countsDown: true)`, `.monospacedDigit()`, `.frame(width: 40)`, colour `#8FD400`.
  - Pitfall: the timer text reserves width for `0:00:00`, which bloats the island. Fix the frame width, or use a 20 pt `ProgressView(timerInterval:)` ring instead.
  - If drifting, switch to a `#FF7A7E` `iphone` glyph.
- **Minimal**: a circular `ProgressView(timerInterval:countsDown:)` ring in green, amber or red, with a 10 pt head inside.
- **Expanded**:
  - `.leading`: 44 pt mascot plus the habit name (15 semibold).
  - `.trailing`: timer at 28 pt, rounded, monospaced.
  - `.bottom`: on-task bar (6 pt, radius 3) plus the drift line in 13 pt `#A6A6A6`.
  - Optional [I'm back] button as a `LiveActivityIntent` that POSTs `/say back` to the Mac.
  - Set `keylineTint(#76B900)`.
- **Lock Screen**: `activityBackgroundTint(.black)`, 14 pt padding, about 96 pt tall.
  - Row 1: mascot 32, then "Drawing", then the timer right-aligned.
  - Row 2: progress bar.
  - Row 3: "On task 92% · last seen 18:04" in the muted colour.
  - On end, show the verdict word (Done in green / Partial in amber / Slacked in red ink) and use `dismissalPolicy: .after(.now + 1800)`.

### Liquid Glass (iOS 26 / macOS 26)
`.glassEffect(.regular.tint(...).interactive(), in: shape)` combines with `GlassEffectContainer(spacing:)` to merge and morph glass shapes ([Apple docs](https://developer.apple.com/documentation/swiftui/glasseffectcontainer.md)).

- **Where it helps.** iPhone app chrome (tab and nav bars adopt glass automatically with the 26 SDK). Floating buttons over the contact-sheet photos. A `GlassEffectContainer` morph between [Start] and the running-timer pill.
- **Where it fights the look.** Don't use glass on the Mac island (it must be solid `#000`), in Live Activities, or on the web dashboard. Glass over black reads as muddy grey, and green-tinted glass turns lime-candy and breaks the "text on green is #000" rule.
- **Availability.** Gate every use with `if #available(iOS 26, *)` and fall back to `#1A1A1A` cards.

### Implementation checklist (about 80–95 min)
1. **xcodegen target (15 min).** Add this to `ios/project.yml`. In the app target, add `NSSupportsLiveActivities: true` to `info.properties` and `- target: AlibiWidgets` (embedded) to its dependencies. Use the widget extension point ID shown, as [OneSignal's setup guide](https://documentation.onesignal.com/docs/en/live-activities-developer-setup.md) also confirms.
   ```yaml
   AlibiWidgets:
     type: app-extension
     platform: iOS
     sources: [AlibiWidgets, {path: Shared}]
     info:
       path: AlibiWidgets/Info.plist
       properties:
         CFBundleDisplayName: Alibi
         NSExtension: {NSExtensionPointIdentifier: com.apple.widgetkit-extension}
     settings: {base: {PRODUCT_BUNDLE_IDENTIFIER: app.theultras.alibi.widgets, GENERATE_INFOPLIST_FILE: NO}}
     dependencies: [{sdk: WidgetKit.framework}, {sdk: SwiftUI.framework}]
   ```
   Also add `Shared` to the app target's `sources`.
2. **Shared attributes (5 min).** Put this in `Shared/AlibiActivity.swift`.
   ```swift
   struct AlibiAttributes: ActivityAttributes {
     struct ContentState: Codable, Hashable {
       var start: Date; var end: Date; var onTask: Int   // 0–100
       var status: String  // "on" | "drift" | "break" | "done" | "partial" | "slacked"
       var line: String    // "Seen your phone 3 min"
     }
     var habit: String     // "Drawing"
   }
   ```
3. **Widget views (30 min).** `@main struct AlibiWidgets: WidgetBundle { var body: some Widget { AlibiLive() } }`, with `ActivityConfiguration(for: AlibiAttributes.self) { lock } dynamicIsland: { DynamicIsland { … } compactLeading: { … } compactTrailing: { … } minimal: { … }.keylineTint(green) }`.
4. **Start, update and end in the app (20 min).**
   - When the app comes to the foreground (`scenePhase == .active`), poll the Mac's `/api/state`, which it already reaches for `/ingest`.
   - If a session is live and there's no activity, call `Activity.request(attributes:content: .init(state:, staleDate: end))`.
   - If it changed, call `await activity.update(...)`. Pass `AlertConfiguration` only for verdicts.
   - If the session ended, call `end(…, dismissalPolicy: .after(.now+1800))`.
   - Add a "Start on iPhone" button so the demo can start it by hand.
5. **Device build (15–25 min).** Run `xcodegen && xcodebuild -scheme AlibiPhone -destination 'platform=iOS,name=…'`. Automatic signing under team 87P4DWU22Q has to provision the second bundle ID.

### Feasibility verdict
**Feasible in about 90 min with medium risk**, provided you accept that mid-session updates only land when the phone app is opened. The countdown and ring tick on their own, which covers about 90% of what the demo shows. The Lock Screen shot plus the island shot is a strong 5 s in the video.

The risks, in order:
1. Signing or provisioning the extension.
2. Width bloat from `Text(timerInterval:)`.
3. The `LiveActivityIntent` button, which you can cut if it fights back.

Real-time drift alerts on the phone need APNs, so don't promise them.
