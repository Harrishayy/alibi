# 01 — Claude and other calm products: a recipe for Alibi

Short version: Claude feels calm because of **one warm canvas, ink-only text, a serif voice for "the assistant" and a sans for chrome, colour held back for the few things that matter, hairlines instead of shadows, a 720px reading column, and short motion (120–360ms) with no bounce on structure.** Alibi already ships Newsreader + Inter (`alibi/web/index.html:9`). Keep that. The work left is discipline: fewer sizes, fewer colours, more space, one moving thing at a time.

---

## 1. Claude / Anthropic visual language

### Typefaces: what they actually are
- **Now:** custom **Anthropic Sans** (UI, body, nav), **Anthropic Serif** (display + editorial prose), **Anthropic Mono** (code, uppercase eyebrows). claude.ai sets body in Anthropic Sans 17px/400 and hero lines in Anthropic Serif at **56px, weight ~330**. That very light serif display is the signature move ([design-md: claude.ai](https://www.webdesignhot.com/api/design-md/claude-ai/export/google-alpha), [opendesigner: Claude](https://opendesigner.io/design-systems/claude)).
- **Earlier claude.ai:** Styrene (sans UI), Tiempos (response text) and Copernicus (a Plantin-inspired display serif) ([Copernicus note](https://ux.rufuspollock.com/Copernicus+font+alternatives), [Styrene alternatives](https://fontalternatives.com/alternatives/styrene/)). The anthropic.com token dump still lists `"Anthropic Serif", "Tiempos", Georgia` as the fallback chain ([webdesignhot: Anthropic](https://www.webdesignhot.com/design.md/anthropic/)).
- **Free look-alikes:** serif → **Newsreader** (variable `opsz` 6–72 and weight 200–800, so you can set it light at display sizes) or Source Serif 4. Sans → **Inter** (neutral; Styrene's free twins Space Grotesk and DM Sans are quirkier). Mono → JetBrains Mono. On Apple platforms use **New York** (`.serif` design) and **SF Pro**. None of these cost anything.

### Type scale, measured
| Role | anthropic.com | claude.ai | Alibi target |
|---|---|---|---|
| Display | 80–96 / 700 sans, or 90 serif | 56 serif / ~330 | **44–56 Newsreader 300**, lh 1.08, −0.02em |
| H2 | 48 / 600 / 1.15 | — | **28 Newsreader 400**, lh 1.2 |
| H3 | 32 / 600 / 1.25 | — | **20 Inter 600**, lh 1.3 |
| Body | 18–20 / 1.4–1.5 | 16–17 / ~1.5 | **16 Inter 400, lh 1.55** (dashboard), 17pt iOS |
| Caption | 14 / 1.4 | — | **13 Inter 500**, lh 1.4 |
| Eyebrow | 13 / 500 / +0.04em, mono uppercase | — | **11–12 mono uppercase**, +0.06em |

The site's reading column is **720px** (prose width) inside a 1432px page, with gutters of `clamp(32px, 6vw, 80px)` and **88–160px** between sections ([webdesignhot](https://www.webdesignhot.com/design.md/anthropic/)). At 16–17px, 720px holds about 70 characters per line, inside the standard 45–75 character range for comfortable reading.

### Colour: how little is used
- Canvas `#faf9f5` (anthropic.com) or `#f5f4ed` (claude.ai parchment), ink `#141413`, soft text `#5e5d59` / `#87867f`, primary surface `#e8e6dc`, hairline borders `#f0eee6` ([opendesigner](https://opendesigner.io/design-systems/claude)).
- **One accent** (clay `#d97757` / terracotta `#c96442`). It appears on the logo spark, the send button and the odd link, and that is about all. An 8-colour earth palette exists but stays "dormant" and only appears on research pages ([abduzeedo on Geist's identity](https://www.abduzeedo.com/seamlessly-crafting-ai-branding-and-visual-identity-anthropic), [webdesignhot](https://www.webdesignhot.com/design.md/anthropic/)).
- Status colours are tinted backgrounds paired with dark text (success `#bcd1ca` bg / `#3d5a47` text), never saturated fills.
- **For Alibi:** NVIDIA green `#76B900` plays clay's part, and gets the same scarcity: under about 5% of pixels on any screen.

### Space, radii, depth
- 4px base: 4, 8, 12, 16, 24, 32, 48, 64, 96.
- Radii: inputs and buttons **8px**, cards **12–16px**, pills 9999.
- Depth comes from **ring shadows** (`0 0 0 1px` at about 10% ink) and hairlines, not drop shadows. Where shadows exist they are very faint: `0 1px 3px rgba(20,20,19,.04)`, elevated `0 12px 32px -8px rgba(20,20,19,.08)`.
- Motion tokens: 120 / 220 / 360ms with `cubic-bezier(0.2,0,0,1)` (emphasized) and `(0.4,0,0.2,1)` (standard) ([webdesignhot](https://www.webdesignhot.com/design.md/anthropic/)).

### The composer
A single large white rounded box (about 16–20px radius) floats on the warm canvas with a 1px hairline and a soft ambient shadow. It grows with the text, starting at about 1 line + toolbar and capped at about 40% of the viewport. Placeholder text is muted and conversational ("How can I help you today?"). Tools sit small and grey in the bottom-left, inside the box. The **send button** sits bottom-right as a ~32px rounded square in the accent colour with a white up-arrow. It is dimmed or hidden until there is text, and Enter sends it. Nothing else on screen competes with the box.

### Message layout
- User turns sit in a soft tinted bubble (the surface colour, no border).
- Assistant turns are **unboxed prose** in the reading column: no avatar chrome, just text at reading size. The serif/sans split tells the two voices apart without boxes.
- Actions (copy, retry) appear on hover in muted grey, 14–16px icons.

### Empty state
A centred greeting in the light display serif ("Good evening, Harrish") with the spark mark, the composer directly underneath, and 3–5 quiet suggestion chips. One sentence, no illustration clutter.

### Thinking indicator
The Claude **spark/asterisk** animates while the model works. In Claude Code it is a glyph cycle `· ✢ ✳ ✶ ✻ ✽ ✻ ✶ ✳ ✢` (ping-pong) next to a whimsical verb ("Sparkling…") with a moving colour **shimmer** sweep. A 3s delay comes before the "thinking" glow appears ([pi-claude-shimmer README](https://cdn.jsdelivr.net/npm/pi-claude-shimmer@1.0.5/README.md), [Medium: reverse-engineering the spinner](https://medium.com/@kyletmartinez/reverse-engineering-claudes-ascii-spinner-animation-eec2804626e0)). The ideas to borrow: **show a brand glyph that breathes, not a spinner; delay it; give it a human verb.**

```css
/* Alibi "watching" shimmer: drop-in */
.shimmer{background:linear-gradient(90deg,var(--muted) 0%,var(--muted) 40%,var(--accent-ink) 50%,var(--muted) 60%,var(--muted) 100%);
  background-size:300% 100%;-webkit-background-clip:text;background-clip:text;color:transparent;
  animation:sh 2.4s cubic-bezier(.4,0,.2,1) infinite}
@keyframes sh{from{background-position:100% 0}to{background-position:0 0}}
@media (prefers-reduced-motion:reduce){.shimmer{animation:none;color:var(--muted)}}
```

### Tone of voice
Sentence case everywhere. Plain words, first person, no exclamation marks, no emoji. Errors state what happened and what to do next ("Couldn't reach the camera. Check it's plugged in, then try again."). Warm but dry, which fits Alibi's "three dry sentences" report.

**Do:** one accent, serif for the voice, hairlines, 720px column, a delayed shimmer.
**Don't:** gradients on surfaces, coloured card backgrounds, bold serif, more than 2 weights per face, spinners, confetti on routine actions, ALL CAPS buttons.

---

## 2. Five more calm products: one steal each

1. **Linear: "structure should be felt, not seen."** The 2026 refresh dimmed the sidebar "a few notches" so content leads. It cut icon count and size, removed coloured icon backgrounds, softened the contrast of separators and used fewer of them, and moved from cool blue-grey to a **warmer, less saturated grey** ([Linear: behind the latest design refresh](https://linear.app/now/behind-the-latest-design-refresh)). Linear generates themes in **LCH** from three inputs: base, accent and contrast ([Linear: how we redesigned the UI](https://linear.app/blog/how-we-redesigned-the-linear-ui)).
   **Steal:** dashboard nav and Setup at 60% ink. Hairlines at `rgba(0,0,0,.06)` light / `rgba(255,255,255,.07)` dark. Delete every icon that sits next to a label that already says the same thing.

2. **Things 3: the completion ritual.** Completing a task runs about 500ms: the circle fills clockwise (200ms easeInOut), then a checkmark springs in (**response 0.3, damping 0.5**), the row slides away (150ms easeOut), and a soft "plink" plays with a light haptic. Rows are 12px vertical / 16px horizontal padding and the checkbox is 22×22 ([Things 3 design study](https://blakecrosley.com/guides/design/things); these are a third party's reconstructed values, so treat them as close, not exact). The Magic Plus button adds a bit of fun to the most frequent action ([Tools & Toys](https://toolsandtoys.net/things-3-for-ios-apple-watch-and-mac/)).
   **Steal:** use this exact sequence for the "done" verdict on the island, the dashboard and iOS, with a `.sensoryFeedback(.success)` haptic on iPhone.

3. **Raycast: speed is the calm.** Its principles are fast, simple and delightful. It treats about **50ms** as the perceptible-latency line, enlarged the search bar to signal importance, and shows **shortcuts inline** (⌘1, ⌘2) in a bottom action bar rather than in tooltips ([Raycast: a fresh look and feel](https://www.raycast.com/blog/a-fresh-look-and-feel), [Raycast design study](https://blakecrosley.com/guides/design/raycast)).
   **Steal:** the island composer opens with focus in under 50ms (no network before first paint). Hint chips read "↵ start · ⌥⌘A toggle · esc close" in 11px mono at 50% ink.

4. **Arc / Dia: delight lives at the edges.** The defaults are soft rounded corners and quiet transitions. The theatrical moment (the first-launch "black hole" with sound) happens **once**, at a threshold ([uxdesign.cc on Arc](https://uxdesign.cc/why-the-arc-browser-is-the-chrome-replacement-ive-been-waiting-for-1e0a05da9fc9), [Arc design study](https://blakecrosley.com/blog/design-study-arc)).
   **Steal:** save the "insane" animation for three moments only: onboarding finish, verdict = done, and the end-of-week reel. Everything else moves under 250ms.

5. **Apple Fitness: one glanceable ring.** The Activity rings have stayed unchanged since 2015, an "exercise of minimalistic restraint" ([iMore](https://www.imore.com/apple-watch-rings-should-get-refreshed-and-heres-how)). A ring answers "how am I doing" in under 1s, and closing it is the celebration.
   **Steal:** a single NVIDIA-green ring for session progress, used on all three surfaces (12pt stroke on iOS, 8px on web, 3pt in island wings), with round caps. When it closes, it overshoots to 102% and settles.

**Bonus: Notion Calendar.** One family covers 11px time labels through 64px display, and hierarchy comes from scale contrast (about 5:1) instead of colour. It is fully keyboard-driven: `T` today, `C` create ([Notion Calendar design study](https://blakecrosley.com/guides/design/notion-calendar), [Notion: introducing Notion Calendar](https://www.notion.com/blog/introducing-notion-calendar)). **Steal:** the Today plan uses the hour labels in 11px tabular mono, plus the `T`/`N` keys.

---

## 3. Calm recipe for Alibi (paste into the design brief)

1. **Two voices.** Newsreader / New York (weight 300–400, never bold, no italics in UI) for anything Alibi *says*: greeting, verdict sentence, nightly report, nudge text. Inter / SF Pro 400/500/600 for all controls and data. JetBrains Mono / SF Mono with `tabular-nums` for times and percentages.
2. **Six sizes only (web px / iOS pt).** 11 · 13 · 16 · 20 · 28 · 48. Body line-height 1.55, display 1.08 with −0.02em tracking, eyebrows uppercase mono +0.06em.
3. **Measure.** Prose max 64ch (`max-width:640px`). Dashboard content column 1120px, gutters `clamp(16px,5vw,64px)`.
4. **Canvas and cards.** Light: canvas `#F2F2F2`, cards `#FFF`, ink `#000` at 88% for body and 56% (`#5E5E5E`) for muted. Dark: canvas `#000`, cards `#1A1A1A`, raised `#262626`, body `#F2F2F2` at 90%.
5. **Green budget ≤5% of pixels.** `#76B900` fills only the primary button, the progress ring, the focus ring and the "done" state. Green text uses `#4E7A00` / `#8FD400`, and text on green is always `#000`.
6. **Bad news is never green, and never shouted.** Show warn `#E5484D` as a 6px dot plus ink text, or as a 10% tint background (`color-mix(in srgb,#E5484D 10%,transparent)`). Never use a full red card. Partial/idle `#F2A900` follows the same rule.
7. **Hairlines over shadows.** Borders are `1px rgba(0,0,0,.08)` (dark: `rgba(255,255,255,.08)`). One shadow token is allowed, for floating layers only: `0 12px 32px -8px rgba(0,0,0,.12), 0 0 0 1px rgba(0,0,0,.06)`.
8. **Radii ladder.** 6 (chips, inline), 10 (buttons, inputs), 16 (cards), 22 (composer, iOS sheets), 9999 (pills, send button). Nested radius = outer − padding.
9. **4pt rhythm.** Spacing steps are 4/8/12/16/24/32/48/72. Card padding is 24 (web) / 20 (iOS) / 16 (island). Sections are 72 apart.
10. **The composer is the hero.** 56px min-height, 22px radius, white on canvas, hairline plus ring shadow, Newsreader 20px placeholder ("What are you about to do?"). A **36px round green send button with a black arrow** sits at 30% opacity until text exists, then 100% with a 120ms scale from 0.9 to 1. Enter starts, Esc clears.
11. **Motion budget.** Micro 120ms, standard 220ms, panel 360ms. Easing is `cubic-bezier(.2,0,0,1)`. In SwiftUI, structure uses `.spring(response:0.35, dampingFraction:0.86)` (no bounce) and only *rewards* use `response:0.3, dampingFraction:0.5`. One element animates at a time, and stagger is 40ms max.
12. **Thinking = breathing mark + shimmer, delayed 600ms.** The mascot or spark scales 0.96↔1.04 over 1.6s ease-in-out alongside a shimmering verb ("Watching…", "Checking the alibi…"). Never use a spinner.
13. **Celebrate rarely, as a ritual.** "Done" plays ring close → check spring → mascot reaction → success haptic, about 600ms total. Confetti is reserved for streaks and the weekly reel. Partial and slacked get a 1-line dry sentence and a calm mascot pose, with no shake.
14. **Keyboard-first, shortcuts visible.** ⌥⌘A island, `N` new session, `T` today, `/` focus composer, `esc` close. Show them in 11px mono under the composer.
15. **Microcopy.** Sentence case, ≤12 words, no "!", no emoji, first person singular for Alibi ("I saw your phone for 3 minutes."), and every error names its fix. Respect `prefers-reduced-motion` and `accessibilityReduceMotion`: swap motion for 150ms opacity fades.

```css
:root{--canvas:#F2F2F2;--card:#FFF;--ink:#000;--ink-2:#5E5E5E;--rule:rgba(0,0,0,.08);
 --accent:#76B900;--accent-ink:#4E7A00;--warn:#E5484D;--warn-ink:#C4161C;--partial:#F2A900;
 --r-chip:6px;--r-btn:10px;--r-card:16px;--r-composer:22px;
 --e:cubic-bezier(.2,0,0,1);--t1:120ms;--t2:220ms;--t3:360ms}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--canvas:#000;--card:#1A1A1A;
 --ink:#F2F2F2;--ink-2:#A6A6A6;--rule:rgba(255,255,255,.08);--accent-ink:#8FD400;--warn-ink:#FF7A7E}}
```
