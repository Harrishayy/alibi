# 03 — Mascot: character animation for Alibi's lobster

**Takeaway:** build one parametric lobster rig (about 14 numeric parameters), drive it with layered keyframe timelines (a loop layer, a pose layer and a one-shot layer), and let it react **rarely and with facts, not guilt**. That covers the Duo charm without the Duo nagging, and it fits in about 2 h of code: SVG + a rAF tween on the web, Shapes + `KeyframeAnimator`/`TimelineView` in SwiftUI.

## What the references actually do

- **Duolingo / Rive.** Duolingo animates its World Characters in Rive. Body poses and mouths are **separate states blended at the same time** by a State Machine. Each character has 20+ mouth shapes (visemes), idle behaviours (head nods, blinks, eyebrow moves) run underneath, and reactions are triggered by correct/incorrect answers. Instead of shipping video, they ship timing data that fires state-machine inputs ([Duolingo blog: visemes](https://blog.duolingo.com/world-character-visemes), [Rive: Lily video call](https://rive.app/blog/duolingo-s-ai-powered-video-call-brings-lily-to-life)). Rive inputs come in three kinds: **boolean** (held states such as `isThinking`), **number** (such as `mouthShape`) and **trigger** (true for one frame, used for `success`/`error`/`celebrate`) ([Rive web inputs](https://rive.app/docs/runtimes/web/inputs), [dev.to Duo-style rig](https://dev.to/uianimation/building-a-duolingo-style-interactive-mascot-in-rive-step-by-step-guide-2d5c)). **What to copy:** layering (loop + pose + one-shot) and the input types. Skip the Rive editor. Our "state machine" is a 60-line JS/Swift switch.
- **Duo's persona** is "#1 fan", "persistent", "emotive", "extra", and openly willing to guilt-trip. That works for retention but gets memed as passive-aggressive ([TechCrunch](https://techcrunch.com/?p=2145036)). **What to copy:** the expressiveness. **What to drop:** the shame.
- **Finch** uses kawaii, caregiving and "gentle reminders, non-judgmental support" ([Pratt IxD critique](https://ixd.prattsi.org/2025/09/design-critique-finch-ios-app-2/)). **Forest** uses a *small, real* consequence: the tree withers if you leave ([Forest](https://apptopia.com/ios/app/866450515/about)). **Alibi's version of this:** the lobster *notices* and *says so*. It never loses health and never cries.
- **Apple Fitness ring-close** (from use, no source opened): the big celebration is reserved for a true milestone, comes with a single success haptic, and sits inside a calm UI. Copy that ratio: about 1 big celebration per day at most.
- **NemoClaw** is NVIDIA's enterprise wrap of OpenClaw, nicknamed "the green lobster" against OpenClaw's red one ([Gigazine](https://gigazine.net/gsc_news/en/20260310-nvidia-nemoclaw/), [Inside](https://www.inside.com.tw/article/40811-nvidia-green-lobster-nemoclaw-is-rumored-to-debut-at-gtc-2026)). Draw an **original** lobster: round, chibi, two big claws, two antennae, dot eyes. Use no NVIDIA logo shapes.

## Look (tokens)

| Part | Value |
|---|---|
| Body / claws fill | `#76B900` |
| Shading segments, outline 1.5px | `#4E7A00` (dark mode: `#8FD400` rim light) |
| Eyes | `#000`, 1 highlight dot `#FFF` |
| Blush | `#F2A900` @ 40% (avoid red so it never reads as "bad") |
| Sparkles | `#76B900` + `#FFF`, 4-point stars |
| Worry sweat drop | `#A6A6A6` |
| Sizes | web hero 96px, card 48px; island alert 56pt, expanded 40pt, compact wing 20pt (**silhouette only below 24pt**: no antennae, no mouth) |

## 12 principles applied to a UI mascot

| Principle | Rule for the lobster |
|---|---|
| Squash & stretch | `bodySquash` 0.88–1.12. **Preserve volume**: `scaleX = 1/sqrt(scaleY)` ([IxDF](https://ixdf.org/literature/article/ui-animation-how-to-apply-disney-s-12-principles-of-animation-to-ui-design)). Origin at the feet. |
| Anticipation | Every one-shot opens with a 120–180 ms opposite move (crouch before a jump, claw pulls back before a pinch). |
| Staging | One reaction at a time. Freeze other UI motion while it plays. |
| Straight-ahead / pose-to-pose | Pose-to-pose only: keyframes. |
| Follow-through / overlap | Antennae lag the body by 60–90 ms and overshoot about 1.5×. Claws settle 40 ms after the body. |
| Slow in / out | Anticipation `cubic-bezier(.5,0,.75,0)`, action `cubic-bezier(.2,.9,.3,1.25)` (overshoot), settle spring `response 0.35, damping 0.6`. |
| Arcs | Jumps move y with ease-out up and ease-in down. Claws rotate around the shoulder pivot, never translate. |
| Secondary action | Antenna sway, blinks and claw idle-clicks while the main pose holds. |
| Timing | Blink 140 ms, pinch 120 ms, nudge 900 ms, celebrate 1600 ms, idle loop 4000 ms. |
| Exaggeration | Push to about 1.3× of "real" for one-shots only. Loops stay subtle (±2.5%). |
| Solid drawing | Keep the silhouette readable at 20pt. Test with `--snapshot`. |
| Appeal | Big eyes (eye ≈ 22% of head width), round body, small mouth. |

## Emotion set (mapped to real Alibi events)

| State | Trigger | Type | Duration | Key poses |
|---|---|---|---|---|
| **idle** | nothing live | loop | 4000 ms | breathe squash 1.0↔1.025, antenna ±4° (3200 ms, out of phase), blink every 3–6 s random, look drifts every 4–8 s |
| **hello** | onboarding step 1, first open of the day | one-shot | 1400 ms | crouch → pop up, right claw waves 3× (±25°, 180 ms each), mouth 0.8 |
| **listening** | composer focused / typing | hold | — | lookX/lookY toward input, eyeOpen 1.1, antennae forward 8° |
| **focused** | session running, on task | loop | 3000 ms | slight lean tilt 4°, eyes 0.8 (calm), claws "tap" alternately every 1.5 s (8°). Drop to compact glyph in the wings |
| **thinking** | verifier / VLM call in flight | loop | 1200 ms | lookY −0.6 (up-left), antennae wiggle ±10° at 6 Hz, 3 dots |
| **side-eye** | phone detected / drift ≥ threshold | one-shot → hold | 2400 ms | lookX → +1 toward the cause, eyeOpen 0.55, tilt −6°, mouth −0.3, sweat drop, then nudge |
| **nudge (pinch)** | the drift nudge alert fires | one-shot | 900 ms | claw pulls back −15° → snaps forward +35°, pinch 0→1→0 ×2 (120 ms) |
| **sleepy** | break, or no interaction for 10 min | loop | 5000 ms | eyeOpen 0.15, squash 0.97, slow breathe, "z" drifts up, antennae droop −12° |
| **proud / celebrate** | verdict **done**, streak 3/7/14/30 | one-shot | 1600 ms | crouch → jump −18px → land squash → claw clap ×2, blush, sparkles |
| **partial** | verdict partial | one-shot | 1000 ms | small nod ×2, one claw up 30°, mouth 0.3. Honest, not a party |
| **supportive** | verdict **slacked** | one-shot | 1400 ms | soft shrug: both claws out 20°, tilt 5°, mouth 0 → 0.2, blink slow. Copy: "Tomorrow, 20 min?" No tears, no frown < −0.3 |
| **surprise** | correction applied | one-shot | 700 ms | eyeOpen 1.3, squash 1.08 pop, antennae straight up, then "noted" nod |
| **connected** | Strava / iPhone / Calendar linked | one-shot | 1000 ms | claw thumbs-up (clawR +60°, pinch 1), sparkle 0.6 |
| **reading** | nightly report open | hold | — | tiny "paper" held in claws, eyes scan lookX −0.5↔+0.5 every 1.2 s |

## Frequency caps and anti-annoyance rules

1. **Global cooldown:** at most 1 one-shot per 90 s. A higher-priority event pre-empts a lower one: verdict > nudge > correction > connected > hello.
2. **Nudges ride the existing nudge cooldown.** Only react when a nudge is *actually sent*, never on a single bad sample. Cap: 3 side-eyes per session.
3. **Stay quiet while the user is working:** no one-shots during on-task focus, no reaction per sample, no motion while the user is typing (except `listening`).
4. **Big celebrate only for** `done` and streak milestones (3, 7, 14, 30, 50, 100). Everything else gets the small version.
5. **Tone:** dry and observational, Duo's cheek without guilt. *Do:* "I've seen your phone for 3 minutes." / "Logged: 18 of 25 min." *Don't:* "You let me down", sad crying faces, health loss, "Are you even trying?"
6. **Reduced motion** (`prefers-reduced-motion` / `accessibilityReduceMotion`): crossfade between static poses over 200 ms, with no jumps, sway or sparkles.
7. **Performance:** stop the rAF/TimelineView when the view is hidden or after 2 min of idle (freeze on a neutral frame). Never run the idle loop in the compact wings.
8. **A mute toggle** ("Quiet lobster") in Setup hides one-shots and keeps the static glyph.

## Rig parameters

`bodySquash` (scaleY, 1), `bodyY` (px, 0), `tilt` (deg, 0), `clawL`/`clawR` (deg, 0, +up), `pinch` (0..1, open→shut), `eyeOpen` (0..1.3), `lookX`/`lookY` (−1..1 → ±3px pupils), `mouthCurve` (−1..1), `blush` (0..1), `antennaSway` (deg), `sparkle` (0..1), `sweat` (0..1), `zzz` (0..1).

### Keyframe tables (ms → value; ease after the arrow)

**idle (loop 4000)**: `bodySquash` 0:1.0 → 2000:1.025 → 4000:1.0 (sine) · `antennaSway` 0:−4 → 1600:4 → 3200:−4 (sine, period 3200) · `eyeOpen` blink at random 3–6 s: 1 → 60ms:0.05 → 140ms:1.

**side-eye → nudge (one-shot 2400)**

| t | lookX | eyeOpen | tilt | mouth | sweat | clawR | pinch | antenna |
|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 200 | 1 (out) | 0.55 | −6 | −0.3 | 0 | 0 | 0 | −8 |
| 600 | 1 | 0.55 | −6 | −0.3 | 1 | 0 | 0 | −6 |
| 1300 | 1 | 0.6 | −3 | −0.2 | 1 | −15 (anticip.) | 0 | −4 |
| 1450 | 0.6 | 0.7 | 0 | −0.1 | 1 | 35 (overshoot) | 1 | 6 |
| 1570 | 0.6 | 0.7 | 0 | −0.1 | 0.8 | 32 | 0 | 2 |
| 1690 | 0.6 | 0.7 | 0 | 0 | 0.5 | 32 | 1 | 0 |
| 1810 | 0.6 | 0.8 | 0 | 0 | 0.2 | 30 | 0 | 0 |
| 2400 | 0 | 1 | 0 | 0 | 0 | 0 (spring) | 0 | 0 |

**celebrate (one-shot 1600)**

| t | bodySquash | bodyY | clawL / clawR | pinch | mouth | blush | sparkle | antenna |
|---|---|---|---|---|---|---|---|---|
| 0 | 1.0 | 0 | 0 / 0 | 0 | 0.2 | 0 | 0 | 0 |
| 160 | 0.88 | 4 | −10 / −10 | 0 | 0.2 | 0 | 0 | 6 |
| 380 | 1.12 | −18 | 70 / 70 | 0 | 1 | 0.6 | 0.4 | −12 (lag) |
| 520 | 0.90 | 0 | 55 / 55 | 0 | 1 | 0.8 | 1 | 10 |
| 640 | 1.04 | 0 | 60 / 60 | 1 | 1 | 0.8 | 1 | −4 |
| 800 | 1.0 | 0 | 60 / 60 | 0 | 1 | 0.8 | 0.8 | 2 |
| 960 | 1.0 | 0 | 60 / 60 | 1 | 1 | 0.8 | 0.5 | 0 |
| 1120 | 1.0 | 0 | 60 / 60 | 0 | 1 | 0.6 | 0.2 | 0 |
| 1600 | 1.0 | 0 | 0 / 0 (spring) | 0 | 0.6 | 0 | 0 | 0 |

## Web: SVG + tiny rAF engine (about 80 lines total)

```html
<svg id="lob" viewBox="0 0 120 120" width="96" height="96" aria-hidden="true">
  <g id="body" style="transform-origin:60px 104px">
    <g id="antL" style="transform-origin:50px 40px"><path d="M50 40 Q40 15 28 10" stroke="#4E7A00" stroke-width="2.5" fill="none" stroke-linecap="round"/></g>
    <g id="antR" style="transform-origin:70px 40px"><path d="M70 40 Q80 15 92 10" stroke="#4E7A00" stroke-width="2.5" fill="none" stroke-linecap="round"/></g>
    <ellipse cx="60" cy="72" rx="30" ry="34" fill="#76B900" stroke="#4E7A00" stroke-width="1.5"/>
    <g id="clawL" style="transform-origin:34px 70px"><!-- arm + two jaw paths (#jawL1/#jawL2) --></g>
    <g id="clawR" style="transform-origin:86px 70px"><!-- ditto --></g>
    <g id="eyes"><ellipse id="eL" cx="50" cy="60" rx="5" ry="6"/><ellipse id="eR" cx="70" cy="60" rx="5" ry="6"/></g>
    <path id="mouth" fill="none" stroke="#000" stroke-width="2" stroke-linecap="round"/>
  </g>
</svg>
```

```js
const P0 = {bodySquash:1,bodyY:0,tilt:0,clawL:0,clawR:0,pinch:0,eyeOpen:1,lookX:0,lookY:0,mouthCurve:0,blush:0,antennaSway:0,sparkle:0,sweat:0};
const ease = {lin:t=>t, out:t=>1-(1-t)**3, in:t=>t*t*t, back:t=>1+2.7*(t-1)**3+1.7*(t-1)**2, sine:t=>.5-.5*Math.cos(Math.PI*t)};
// clip = {dur, loop, tracks:{param:[[ms,value,ease?],...]}}
function sample(track, ms){ let a=track[0]; for(const b of track){ if(b[0]>=ms){ const k=(ms-a[0])/((b[0]-a[0])||1); return a[1]+(b[1]-a[1])*ease[b[2]||'out'](k);} a=b;} return a[1]; }
const layers = {loop:IDLE, pose:null, shot:null}; let shotT0=0, last=0;
function play(clip){ const now=performance.now(); if(now-last<90000 && clip.prio<3) return; last=now; layers.shot=clip; shotT0=now; }
function frame(now){
  const p = {...P0};
  for (const L of ['loop','pose','shot']) { const c=layers[L]; if(!c) continue;
    let t = L==='shot' ? now-shotT0 : now % c.dur;
    if (L==='shot' && t>c.dur){ layers.shot=null; continue; }
    for (const [k,tr] of Object.entries(c.tracks)) p[k] = (k==='bodySquash') ? p[k]*sample(tr,t) : (L==='loop'? p[k]+sample(tr,t) : sample(tr,t));
  }
  render(p); if (!document.hidden) requestAnimationFrame(frame);
}
function render(p){
  const sx = 1/Math.sqrt(p.bodySquash);
  $('#body').style.transform = `translateY(${p.bodyY}px) rotate(${p.tilt}deg) scale(${sx},${p.bodySquash})`;
  $('#clawL').style.transform = `rotate(${-p.clawL}deg)`; $('#clawR').style.transform = `rotate(${p.clawR}deg)`;
  $('#antL').style.transform = `rotate(${p.antennaSway}deg)`; $('#antR').style.transform = `rotate(${-p.antennaSway*0.8}deg)`;
  for (const e of ['#eL','#eR']) { $(e).setAttribute('ry', 6*p.eyeOpen); $(e).style.transform=`translate(${p.lookX*3}px,${p.lookY*3}px)`; }
  $('#mouth').setAttribute('d', `M54 78 Q60 ${78+p.mouthCurve*6} 66 78`);
  // pinch: rotate jaw halves ±(1-p.pinch)*18deg; blush/sparkle/sweat: opacity
}
```

Wire it up with `window.alibiMascot.play('celebrate')` from the existing SSE/poll handlers (verdict, nudge, correction). With `matchMedia('(prefers-reduced-motion: reduce)')`, skip `frame` and set the end pose of each clip.

## SwiftUI (macOS island and iOS)

```swift
struct Pose { var squash = 1.0, y = 0.0, tilt = 0.0, clawL = 0.0, clawR = 0.0, pinch = 0.0,
              eye = 1.0, lookX = 0.0, mouth = 0.0, blush = 0.0, sparkle = 0.0, antenna = 0.0 }

struct Lobster: View {               // pure drawing of a Pose
    var p: Pose
    var body: some View {
        ZStack {
            Antennae(sway: p.antenna)
            Ellipse().fill(Color(hex: 0x76B900)).overlay(Ellipse().stroke(Color(hex: 0x4E7A00), lineWidth: 1.5))
            Claw(pinch: p.pinch).rotationEffect(.degrees(-p.clawL), anchor: .trailing).offset(x: -30)
            Claw(pinch: p.pinch).scaleEffect(x: -1).rotationEffect(.degrees(p.clawR), anchor: .leading).offset(x: 30)
            Eyes(open: p.eye, look: p.lookX); Mouth(curve: p.mouth); Sparkles(t: p.sparkle)
        }
        .scaleEffect(x: 1/sqrt(p.squash), y: p.squash, anchor: .bottom)
        .rotationEffect(.degrees(p.tilt), anchor: .bottom).offset(y: p.y)
    }
}

struct Mascot: View {
    @State private var celebrate = 0          // bump to fire
    @Environment(\.accessibilityReduceMotion) var reduce
    var body: some View {
        TimelineView(.animation(paused: reduce)) { ctx in         // idle loop layer
            let t = ctx.date.timeIntervalSinceReferenceDate
            KeyframeAnimator(initialValue: Pose(), trigger: celebrate) { shot in
                var p = shot
                p.squash *= 1 + 0.0125 * (1 - cos(t * .pi * 2 / 4))   // breathe 4 s
                p.antenna += 4 * sin(t * .pi * 2 / 3.2)
                return Lobster(p: p)
            } keyframes: { _ in
                KeyframeTrack(\.squash) {
                    CubicKeyframe(0.88, duration: 0.16); SpringKeyframe(1.12, duration: 0.22)
                    CubicKeyframe(0.90, duration: 0.14); SpringKeyframe(1.0, duration: 0.40, spring: .init(response: 0.35, dampingRatio: 0.6))
                }
                KeyframeTrack(\.y) { CubicKeyframe(4, duration: 0.16); CubicKeyframe(-18, duration: 0.22); CubicKeyframe(0, duration: 0.14) }
                KeyframeTrack(\.clawR) { CubicKeyframe(-10, duration: 0.16); SpringKeyframe(70, duration: 0.22); LinearKeyframe(60, duration: 0.7); SpringKeyframe(0, duration: 0.5) }
                KeyframeTrack(\.pinch) { LinearKeyframe(0, duration: 0.52); for _ in 0..<2 { LinearKeyframe(1, duration: 0.12); LinearKeyframe(0, duration: 0.12) } }
                KeyframeTrack(\.sparkle) { LinearKeyframe(0, duration: 0.3); CubicKeyframe(1, duration: 0.22); CubicKeyframe(0, duration: 0.9) }
            }
        }
    }
}
```

Use one `trigger` counter per one-shot (celebrate, nudge, surprise), or a single `@State var shot: (kind, n)` with a `switch` in `keyframes:`. Blinks: a `Task` loop that sleeps a random 3–6 s and then animates `eye` 1→0.05→1 with `.easeInOut(duration: 0.07)`. `KeyframeAnimator` needs iOS 17 / macOS 14, so it is fine on both targets ([WWDC23 10157 notes](https://wwdcnotes.com/notes/wwdc23/10157), [AppCoda KeyframeAnimator](https://appcoda.com/keyframeanimator/)). In the island, render the lobster only in the expanded panel and in alerts. Compact wings get a static 20pt silhouette tinted by status.

## Sound and haptics (all optional)

- **iOS:** `.sensoryFeedback(.success, trigger: celebrate)` on done, `.warning` on nudge, `.selection` on correction. On by default; that is the iOS norm.
- **macOS:** **off by default.** If enabled: `NSHapticFeedbackManager.defaultPerformer.perform(.levelChange, performanceTime: .now)` (trackpad only), and `NSSound(named: "Pop")` at volume 0.3 for celebrations only.
- **Web:** off by default. A WebAudio two-note chime (660 Hz → 990 Hz, 80 ms each, gain 0.08, 10 ms attack / 120 ms release) for done. Nothing for bad events: silence reads as kinder.

## Demo beats (60–90 s)

hello wave in onboarding → listening while typing "draw for 25 min" → focused in the island → phone up: side-eye + pinch nudge alert → correction: surprise nod → verdict done: celebrate with sparkles plus iPhone success haptic → nightly report: reading.
