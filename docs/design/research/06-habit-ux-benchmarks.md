# 06 — Habit / focus app UX benchmarks → what Alibi borrows

Scope: home-screen IA, honest progress, streaks without shame, celebrations, empty states, onboarding, nudge tone, data-viz. Then Alibi IA for laptop / island / iPhone, a 5-hour feature cut, and microcopy.

## 1. What the best apps do (and the one thing to steal from each)

| App | Pattern worth stealing | Alibi translation |
|---|---|---|
| **Duolingo** | Streak + **Streak Freeze** (now up to 2 equipped). Milestone animations alone moved new-user retention **+1.7%**; doubling freeze capacity **+0.38% DAU**; 7-day streakers are **3.6x** likelier to finish ([Duolingo blog](https://blog.duolingo.com/how-duolingo-streak-builds-habit)). Early streaks feel big (2→3 = +50%), late ones run on loss aversion. Push copy is chosen by a bandit ([Duolingo KDD'20](https://research.Duolingo.com/papers/yancey.kdd20.pdf)); the "these reminders don't seem to be working" line works but is [famously passive-aggressive](https://vicki.substack.com/p/duo-the-push-and-the-bandits). | Celebrate days 1-7 loudly, then go quiet. Freezes are free and automatic (1 per week), never sold. Take Duo's timing, not his guilt-trips. |
| **Apple Fitness rings** | One glyph = three goals; closing a ring is the reward; awards collect in a trophy case ([Apple](https://images.apple.com/ie/watch/close-your-rings/)). | One **on-task ring** per session (seen ÷ claimed). Ring closes at the verdict with one spring. |
| **Forest** | Main screen shows only the timer, the growing tree and points; leave and the tree withers. Loss aversion with no blocking ([Pratt critique](https://ixd.prattsi.org/2022/09/design-critique-forest-ios-app/), [Wikipedia](https://en.wikipedia.org/wiki/Forest_(application))). | Mascot "grows" a contact-sheet tile per good sample. Drift dims the lobster but never kills it. |
| **Finch** | The pet makes the app gentle: you look after it by doing things, onboarding hatches it, energy bar = progress, no shaming ([screensdesign](https://screensdesign.com/showcase/finch-self-care-pet), [Pratt 2026](https://ixd.prattsi.org/2026/02/design-critique-finch-self-care-pet-ios-app/)). | The lobster owns the emotions so the UI doesn't have to. Bad news comes as the mascot's reaction plus a plain sentence, never in red capitals. |
| **Beeminder** | The "yellow brick road": honest data against a line you drew. You can change the slope, but only one week ahead (the "akrasia horizon") ([Beeminder blog](https://blog.beeminder.com/dial), [LessWrong](https://lesswrong.com/posts/6oYETaG248zGF45aD)). | **Claimed vs seen** is Alibi's road: show both bars side by side. Habit target edits apply from tomorrow. |
| **Streaks** (ADA winner) | ≤24 big circular tiles, one tap; "negative tasks" (a day without the bad thing extends the streak) ([App Store](https://apps.apple.com/no/app/id963034692), [MacStories](https://www.macstories.net/?p=49979)). | Habit chips as big tap targets. "No phone during drawing" works as a negative habit. |
| **Habitify** | Separates **Skip** (planned rest, arrow), **Fail** (cross) and **Done** (solid dot) in calendar/heatmap ([Habitify help](https://intercom.help/habitify-app/en/articles/11203360-view-the-progress-of-a-habit-on-website-desktop-app)). | Four day states: done ● green, partial ◐ amber, slacked ○ red ring (hollow, not filled), rest → grey. Rest days don't break streaks. |
| **Structured / Tiimo** | The day as a vertical, colour-coded **timeline** of blocks with icons. Built with neurodivergent users ([Tiimo](https://tiimoapp.com/product/webapp), [screensdesign](https://screensdesign.com/showcase/tiimo-ai-plan-focus-to-do)). | Today's plan blocks show as a timeline with a "now" line. The live block glows. |
| **Rize** | Auto-tracked desktop timeline, Focus/Break scores, menu-bar timer, weekly report ([Rize](https://rize.io/guides/categories-and-rules), [review](https://freshvanroot.com/blog/rize-productivity-tracker-review/)). | Window titles become a thin category strip under the camera samples: proof from two sources. |
| **Opal** | **Focus Score** on top of home, live from pickups/apps; named "Focus Gems" for milestones ([Opal blog](https://www.opal.so/blog/introducing-the-new-opal-home-screen-track-your-screen-time-and-improve-your-focus)). | One number at the top: today's **honesty score** (seen ÷ claimed minutes). Named lobster "shells" for milestones (COULD). |
| **Things 3** | Mostly white space, bold-but-few colours, the Magic Plus as the single delightful input ([MacStories](https://www.macstories.net/?p=48965)). | The composer ("What are you about to do?") is Alibi's Magic Plus: one input that is always visible. |

**Honesty is our niche.** No benchmark shows claimed vs actual for the same session. Opal/Rize measure, Beeminder self-reports. Alibi's contact sheet is the proof and should be the hero visual everywhere.

## 2. Principles (do / don't)

- **Do** put one number + one sentence on top (Opal, Fitness). **Don't** lead with charts.
- **Do** make the streak forgiving: free auto-freeze 1/week, rest days, partial counts as "kept" at ≥60% seen. **Don't** sell freezes or show "streak lost" in red.
- **Do** celebrate big for the first win, days 3 and 7, then every 7 days. Otherwise just a ring close plus haptic. **Don't** use confetti for every session (it stops meaning anything).
- **Do** let nudges state facts in first person with a number ("I've seen your phone for 3 minutes"). **Don't** guilt ("Duo is sad"), and don't use exclamation marks for bad news.
- **Do** make every bad verdict correctable in one click (Habitify-style status override). **Don't** let an incorrect verdict stand without a way to fix it.
- **Do** keep onboarding to ≤4 screens, ≤60 s, with a 30 s practice session at the end. Finch hatches the pet first; we hatch the lobster.
- **Do** design empty states as invitations with one primary button plus mascot idle.

## 3. Laptop dashboard IA — the 5-second story

A judge should read, top to bottom: **"I said X → Alibi saw Y → here's the proof → it was fair to me."**

1. **Hero strip (≤120 px tall):** mascot (64 px) · today's honesty line in serif display ("Claimed 2h 10m. Seen 1h 52m.") · streak pill (mascot SVG glyph + "6 days · 1 freeze left"; no emoji). One idea per element.
2. **Now / Composer (swap in place):** idle shows the composer + 3 habit chips. Live shows the ring timer (160 px, 10 px stroke, `#76B900` on `#262626`), on-task %, the last 6 samples, the drift line. Mascot mirrors the state.
3. **Today timeline:** plan blocks in Tiimo style, with a now-line (`#76B900` 2 px). Each finished block shows a verdict dot.
4. **Latest verdict card:** contact sheet (the hero proof) + 3-sentence verdict + "Fix a moment" link.
5. **This week:** 7-day dot grid (Habitify states) + claimed-vs-seen paired bars per day + the report quote.
6. **Sessions archive**, then **Setup** in the drawer (already there).

Today the dashboard opens with plan blocks. Move hero + Now above them. Keep `max-width: 880px` with `gap: 24px` between cards.

## 4. Island IA — one hover

- **Collapsed idle:** notch size, nothing drawn. **Live:** left wing = 18 pt mascot head (state-tinted), right wing = "24m" (tabular). **Drift:** right wing goes `#E5484D` "phone".
- **Expanded (440 pt), in order:** (a) live card: habit name, ring 44 pt, remaining time, on-task %, End button; or idle: composer + up to 4 chips. (b) one-line "next up" from the calendar. (c) streak + today's honesty line. That's the limit; history lives on the dashboard ("Open dashboard ↗").
- **Alerts:** nudge = mascot + 1 sentence + [I'm back] [Pause 5m]. Verdict = mascot reaction + verdict word + contact-sheet thumbnail (120×68) + [See proof]. Auto-fold after 6 s, or never fold while the pointer is over it.

## 5. iPhone companion IA (iOS 17+, 4 tabs)

Data: poll the Mac's `GET /api/state` (live session) and `/api/sessions`, `/api/report` every 5 s while foregrounded, sending the existing shared key. The server must accept the key on these GETs.

1. **Today:** big mascot (160 pt), live ring + `Text(timerInterval:)` countdown, on-task %, last sample. Idle shows today's honesty line + plan blocks + "Start on Mac" chips (POST `/api/say`).
2. **Week:** 7-day dot row + paired bars (Swift Charts `BarMark`, two series).
3. **Streaks:** current/best streak, freeze tokens, milestone shells (trophy-case grid, Apple awards style).
4. **Health:** existing sync table + "Synced 2 min ago" + Sync now. **Settings** goes in a toolbar gear, not a tab.

**Live Activity** (widget extension, `NSSupportsLiveActivities = YES`). Compact leading = mascot glyph, trailing = minutes left. Expanded = habit, ring, on-task %. Lock Screen ≤160 pt tall. Max 8 h active, up to 4 h on the Lock Screen after end; payload ≤4 KB. Text animates with system blur transitions, and `withAnimation` is ignored ([ActivityKit docs](https://developer.apple.com/documentation/activitykit/displaying-live-data-with-live-activities.md)).

```swift
struct SessionAttrs: ActivityAttributes {
  struct ContentState: Codable, Hashable { var onTask: Double; var mood: String; var drift: String? }
  var habit: String; var start: Date; var end: Date
}
// trailing: Text(timerInterval: ctx.attributes.start...ctx.attributes.end, countsDown: true).monospacedDigit()
```

Starting needs the app in the foreground (or a `LiveActivityIntent`). For the demo, start it from the Today tab when it sees a live session.

## 6. Feature cut (~5 h total, AI agents)

| Pri | Feature | Min |
|---|---|---|
| MUST | SVG lobster mascot with 5 states (idle/focus/happy/worried/sleep) + CSS keyframes; same paths as a SwiftUI `Shape` | 60 |
| MUST | Dashboard hero strip + honesty line + reorder (§3) | 30 |
| MUST | Verdict celebration: ring close (spring 600 ms) + mascot happy + 24-particle green burst on "done" only | 30 |
| MUST | Island: mascot in left wing + mascot in nudge/verdict alerts | 40 |
| MUST | Forgiving streak (auto-freeze, rest days, partial≥60%) computed server-side + pill | 25 |
| SHOULD | iPhone Today tab mirroring `/api/state` with mascot + ring | 45 |
| SHOULD | Live Activity (compact + lock screen) | 45 |
| SHOULD | Week dot grid + claimed-vs-seen paired bars | 25 |
| COULD | Milestone shells (trophy case), iPhone Streaks tab | 30 |
| COULD | Onboarding "hatch the lobster" first screen | 15 |

MUST total ≈ 3 h, leaving ~1 h of SHOULD and ~45 min for recording. Cut the Live Activity before the phone Today tab, because the tab is the prerequisite.

**Motion tokens:** state change 220 ms `cubic-bezier(.2,.8,.2,1)`; ring close spring `response 0.55, damping 0.72`; mascot idle breathe 3.2 s ease-in-out scale 1→1.03; worried shake 2× ±3° 400 ms; celebration once per verdict. Respect `prefers-reduced-motion` / `accessibilityReduceMotion` by swapping all of these for a 150 ms fade.

## 7. Microcopy — dry, honest, kind

Rules: first person ("I saw"), numbers over adjectives, ≤14 words, no exclamation marks except on wins, never "you failed", always offer the fix. Bad news uses the mascot plus `#E5484D` ink only on the noun ("phone"), never the whole line.

1. Nudge: "You said drawing. I've seen your phone for 3 minutes."
2. Nudge (window): "You said C++. That's been YouTube for 4 minutes."
3. Nudge, recovery: "Back on the sketchbook. Noted."
4. Verdict done: "Done. 25 of 25 minutes at the desk, pencil in hand."
5. Verdict partial: "Partial. 17 of 25 minutes on task — the phone had the rest."
6. Verdict slacked: "Slacked, by my count. Tap any frame if I got it wrong."
7. Correction ack: "Fair. I've changed that one and the verdict with it."
8. Streak day 3: "Three days in a row. That's how it starts."
9. Streak day 7: "A week of alibis that checked out."
10. Freeze used: "Missed yesterday. I used your freeze — the streak's intact."
11. Rest day: "Rest day. Nothing to check."
12. Empty today: "Nothing claimed yet. What are you about to do?"
13. Empty week: "A week from now, this will tell you something true."
14. Nightly report: "You claimed three hours. I saw two and a half. Drawing carried the day."
15. Camera off: "Camera's off. I'm only going on window titles."
