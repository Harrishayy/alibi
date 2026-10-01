# 07 — Typography

**Bottom line:** Use Pairing A. On the web that means **Source Serif 4** for display and **Figtree** for UI. On the island and iPhone it means **New York + SF Pro + SF Pro Rounded**, which costs zero bytes. This keeps Claude's calm editorial feel, which the user asked to keep, and drops Inter, the one font the impeccable hook flags today. Every timer and stat uses tabular lining figures. NVIDIA shows through colour, not type.

## 1. What Claude uses (and the free stand-ins)

- Claude pairs a Tiempos/Copernicus-style serif (Klim, descended from Galaxie Copernicus) for display with **Styrene B** (Commercial Type, a geometric sans) for UI. Sources: [type.today on Styrene at Anthropic](https://type.today/en/journal/anthropic) and the [shadcn Claude DESIGN.md](https://www.shadcn.io/design/claude).
- Other details from those notes: display weight is 400–500 with negative tracking (-0.3 to -1.5px), the scale runs 12→64px, and code is set in JetBrains Mono.
- Both faces are commercial. The free stand-ins most often suggested for Styrene are Space Grotesk, Work Sans and DM Sans ([fontalternatives](https://fontalternatives.com/alternatives/styrene/)). Space Grotesk and DM Sans are both on impeccable's reject list, so they're out.
- The idea worth borrowing: **serif = the AI's considered voice (verdicts, reports); geometric sans = the human's controls.** That maps directly onto Alibi.

## 2. The impeccable rules we have to pass (read from plugin v3.7.1 source)

**Hook `overused-font`** (`scripts/detector/shared/constants.mjs`) flags these families:
- inter, roboto, open sans, lato, montserrat, arial, helvetica
- fraunces, instrument sans, instrument serif
- geist, geist mono, mona sans
- plus jakarta sans, space grotesk, recoleta

**Today `index.html` loads Inter, so it trips this rule.** Inter Tight isn't on the list, but it's a dodge.

**Brand reflex-reject list** (`reference/brand.md`) adds Newsreader, Lora, Crimson/Crimson Pro, IBM Plex (all of it), DM Sans/DM Serif, Outfit and Space Mono. This list applies to new choices. Newsreader is our current serif, so we're allowed to keep it, but it reads as "2026 default".

**Other typography rules the detector enforces (exact thresholds):**

| Rule | Fires when | What we do |
|---|---|---|
| `italic-serif-display` | Big italic serif headline. Source Serif 4, Newsreader and Spectral are in `KNOWN_SERIF_FONTS` | **Set display roman only.** Italic is allowed only inline, at ≤20px. |
| `tight-leading` | Line-height < 1.3× on text over 50 characters (headings excluded) | Body 1.5–1.6 |
| `tiny-text` | Text < 12px and > 20 characters, outside chip/label/badge/meta classes | 12px is the floor; under 13px only for labels |
| `wide-tracking` | Letter-spacing > 0.05em on lowercase text | Lowercase max +0.02em |
| `extreme-negative-tracking` | Letter-spacing ≤ -0.05em | Display min -0.025em (SKILL.md floor is -0.04em) |
| `flat-type-hierarchy` | Largest size / smallest size < 2.0 | Our 12→56px scale = 4.7× |
| `single-font` | Only one family on the page | Pairing B still ships a second face (mono) |
| `hero-eyebrow-chip` / `repeated-section-kickers` | Tiny uppercase tracked label above every section | **Sentence-case section labels**; no "NOW / THIS WEEK" kickers |
| `oversized-h1` | h1 ≥ 72px with ≥ 40 characters | Our h1 is 36px |
| `numbered-section-markers`, `gradient-text` | — | Banned outright |

Guidance from SKILL.md and typeset.md:
- Product register: a fixed rem scale with a 1.125–1.2 step ratio.
- Light text on dark needs about +0.05 line-height and +0.01em tracking.
- At most 3 families and 3–4 weights.
- `text-wrap: balance` on h1–h3; `pretty` on prose.

## 3. Candidates: measured, not guessed

I downloaded each regular weight from Google Fonts and read it with fontTools. In the table, "xh" is x-height divided by em size; bigger means more legible at 13–15px. The axes listed are the ranges the GF API accepted.

| Face | xh | tnum | Axes | Latin woff2 | Verdict |
|---|---|---|---|---|---|
| **Source Serif 4** | .475 | ✓ | opsz 8–60, wght 200–900 | 119KB (opsz+wght 400–600) | **A display.** Display cut at opsz 60 is crisp and Tiempos-like. Higher x-height than Newsreader. Not flagged. |
| Newsreader (current) | .426 | ✓ | opsz 6–72, wght 200–800 | — | Lovely but small x-height. On the reject list. Fallback only. |
| Literata | .503 | ✓ | opsz 7–72, wght 200–900 | — | Warm and bookish. Good runner-up for display. |
| Young Serif | .500 | ✓ | single 400 | — | Most Copernicus-like slab, but only one weight. |
| Spectral / Gelasio / Lora / Crimson Pro / EB Garamond | .42–.50 | ✓ | — | — | Small x-height or flagged. No. |
| **Figtree** | .500 | ✓ | wght 300–900 | **19KB** | **A UI.** Geometric-humanist with open apertures, the friendly stand-in for Styrene. Not flagged. Tiny file. |
| **Schibsted Grotesk** | .527 | ✓ | wght 400–900 | 45KB | **B UI + display.** News-grotesk character fits the "verdict/evidence" voice. Not flagged. |
| Onest | .527 | ✓ | wght 100–900 | — | Neutral, Inter-like. A safe backup. |
| Manrope / Public Sans | .54 / .52 | ✓ | — | — | Fine, but generic. |
| Hanken Grotesk, DM Sans | .49 / .50 | **✗ no tnum** | — | — | Rejected because timers would jitter. |
| Inter, Geist, Mona Sans, Instrument Sans, Plus Jakarta | .51–.55 | ✓ | — | — | Hook-flagged. |
| JetBrains Mono | .550 | (mono) | wght 100–800 | 30KB | Keep only if we need code/IDs; Claude uses it too. |
| Geist Mono / IBM Plex Mono | — | — | — | — | Flagged. Commit Mono isn't on GF (would need self-hosting). |
| SF Pro (system) | .508 | ✓ | opsz auto, cv01–06 | 0 | Apple surfaces. |

**NVIDIA bridge:**
- NVIDIA Sans is a commissioned face under its own [EULA](https://raytracing-docs.nvidia.com/iray/ext/fonts/nvidia-sans/NVIDIA_Sans_EULA_20220602_FINAL.pdf). **Don't embed it.**
- The free "NVIDIA look" suggestions (Rajdhani, Eurostile) are squared and techno ([madegooddesigns](https://madegooddesigns.com/?p=6811)). They fight the calm brief, and the user already rejected an NVIDIA-ish type direction.
- The bridge is #76B900 plus the heavy, tracked "ALIBI" wordmark in SF Pro Heavy. No third family.

## 4. Pairing A (recommended): Source Serif 4 + Figtree; New York + SF on Apple

**Roles:**
- Serif is for *words the agent says*: greeting, section titles, verdict line, the three-sentence report, alert headlines. It's always roman, weight 400–500, with `font-optical-sizing:auto`.
- Sans is for everything you touch and every number.

### Dashboard (px; root 16px; light ink #000/#1A1A1A on #FFF/#F2F2F2; dark #F2F2F2 on #000/#1A1A1A)

| Token | Face | Size / LH | Weight | Tracking | Use |
|---|---|---|---|---|---|
| `--t-display` | Figtree tnum | 56 / 1.0 | 500 | -0.025em | Now-ring timer "24:07" |
| `--t-h1` | Source Serif 4 | 36 / 1.15 | 400 | -0.015em | "Good evening." / onboarding |
| `--t-h2` | Source Serif 4 | 24 / 1.25 | 450 | -0.01em | Now, This week, Sessions |
| `--t-h3` | Figtree | 17 / 1.35 | 600 | 0 | Card titles, session name |
| `--t-quote` | Source Serif 4 | 20 / 1.45 | 400 | 0 | Report sentences, verdict line, drift line |
| `--t-body` | Figtree | 15 / 1.55 (dark 1.6) | 400 (dark 450) | 0 (dark +0.01em) | Default |
| `--t-small` | Figtree | 13 / 1.45 | 400 | +0.005em | Meta, timestamps; #5E5E5E / #A6A6A6 |
| `--t-label` | Figtree | 12 / 1.3 | 600 | +0.01em | Chip text, field labels; sentence case |
| `--t-stat` | Figtree tnum | 32 / 1.0 | 600 | -0.02em | "82%" on-task, pace |
| `--t-num` | Figtree tnum | inherit | 500 | 0 | Any inline number |
| `--t-code` | ui-monospace | 13 / 1.45 | 400 | 0 | Raw IDs/paths (SF Mono on Mac, so no download) |

A typography detail worth doing: use 13px `--t-label` for chips and buttons.

### Island (pt; dark only; macOS has no Dynamic Type)

| Role | Font | Size | Weight | Notes |
|---|---|---|---|---|
| Wordmark | SF Pro | 12 | .heavy | `.tracking(1.6)`, "ALIBI" |
| Compact wing value | SF Pro Rounded | 13 | .semibold | `.monospacedDigit()` + `.contentTransition(.numericText(countsDown:true))` |
| Expanded timer | SF Pro Rounded | 34 | .semibold | Same as above; `.tracking(-0.5)` |
| Session title / alert headline | New York | 19 / 17 | .regular | e.g. "Drawing", "You said drawing." |
| Body / composer | SF Pro | 14 | .regular | `.lineSpacing(3)` |
| Secondary | SF Pro | 12 | .regular | White at 0.6 opacity |
| Caption floor | SF Pro | 11 | .medium | Nothing smaller except 10pt badge digits |

**Fix today's 10pt text run** at `native/Island.swift:603`. It should be 11pt minimum. The 10pt badge digits at line 829 are fine.

### iPhone (Dynamic Type relative styles; sizes at the default "Large" setting, per the [HIG](https://developer.apple.com/design/human-interface-guidelines/typography))

| Role | Style |
|---|---|
| Screen title | `.largeTitle` (34/41), `design: .serif`, `.regular` |
| Section | `.title3` (20/25), serif |
| Row title | `.headline` (17/22), SF |
| Body | `.body` (17/22) |
| Meta | `.subheadline` (15/20) and `.footnote` (13/18) |
| Stat | `.title` (28/34), `.rounded`, `.semibold`, `.monospacedDigit()` |
| Labels | `.caption` (12/16), `.semibold`. **Sentence case.** Replace "LAST 7 DAYS" with "Last 7 days". |

### Live Activity / Dynamic Island

**Sans only.** No serif at these sizes and in this system context.

| Slot | Font |
|---|---|
| Lock screen title | 15pt semibold |
| Lock screen timer | `Text(timerInterval:countsDown:)` at 34pt rounded semibold, `.monospacedDigit()` |
| Compact trailing | 14pt rounded semibold |
| Expanded leading | 13pt medium |
| Expanded center | 17pt semibold |
| Expanded trailing | 22pt rounded semibold |
| Minimal | Glyph only |

## 5. Pairing B: all-sans precision

- **Web:** Schibsted Grotesk for everything, plus `ui-monospace` for code.
  - Display and h1 at 600, -0.02em; h2 at 600, 24px; body at 400, 15/1.55; stats at 700, tnum.
  - Same sizes as A, but serif roles become Schibsted 500 with **no** negative tracking under 20px.
- **Apple:** SF Pro everywhere, with SF Pro Rounded for numbers.
- **Trade-off:** it's more "instrument", reads closer to NVIDIA, and saves 74KB. But it loses the Claude calm the user explicitly asked to keep.

## 6. Why A

1. It matches the user's stated taste (Claude calm) without copying Claude's fonts.
2. It removes the only overused-font finding (Inter) and stays off both impeccable lists.
3. The serif-voice / sans-control split gives the mascot and verdict copy a distinct "agent voice" that viewers can read in a demo.
4. Every numeral face has tnum, so timers don't jitter.
5. Apple surfaces cost nothing. New York and Source Serif 4 are both transitional serifs with optical sizes, so the island and the dashboard feel like one family.

## 7. Web font loading (drop-in)

To swap fonts, edit lines 7–9 and 20–22 of `alibi/web/index.html`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Figtree:wght@400..700&family=Source+Serif+4:opsz,wght@8..60,400..600&display=swap">
```

```css
/* metric-matched fallbacks (computed with fontTools from GF 400 vs Arial/Georgia) */
@font-face{font-family:"Figtree Fallback";src:local("Arial");size-adjust:100%;ascent-override:95%;descent-override:25%;line-gap-override:0%}
@font-face{font-family:"Source Serif Fallback";src:local("Georgia");size-adjust:104.6%;ascent-override:99%;descent-override:32%;line-gap-override:0%}
:root{
  --serif:"Source Serif 4","Source Serif Fallback","New York",Georgia,serif;
  --sans:"Figtree","Figtree Fallback",-apple-system,system-ui,sans-serif;
  --mono:ui-monospace,"SF Mono",Menlo,monospace;
}
body{font:400 15px/1.55 var(--sans);font-kerning:normal;font-optical-sizing:auto;
     -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
h1,h2,.serif{font-family:var(--serif);font-style:normal;text-wrap:balance}
.num,.mono,time,[data-num]{font-variant-numeric:tabular-nums lining-nums}
.prose{text-wrap:pretty;max-width:62ch}
```

**What Google Fonts already handles:**
- Subsetting by `unicode-range`, so the latin slice is all that downloads: Figtree 19KB, Source Serif 4 119KB.
- `font-display:swap`.

**For an offline demo, self-host.** Run `curl` with a Chrome User-Agent against the same css2 URL, save the two `/* latin */` woff2 files into `alibi/web/fonts/`, and point the `@font-face` blocks at `/web/fonts/…`. The `/web` folder is already mounted at `alibi/api.py:395`. Add `<link rel=preload as=font type=font/woff2 crossorigin>` for **Figtree only**.

## 8. SwiftUI helpers (island and iPhone)

```swift
extension Font {
    static func voice(_ s: CGFloat, _ w: Weight = .regular) -> Font { .system(size: s, weight: w, design: .serif) }   // New York
    static func ui(_ s: CGFloat, _ w: Weight = .regular) -> Font { .system(size: s, weight: w) }                        // SF Pro
    static func num(_ s: CGFloat, _ w: Weight = .semibold) -> Font { .system(size: s, weight: w, design: .rounded).monospacedDigit() }
    // iPhone: Dynamic-Type aware
    static let voiceTitle = Font.system(.largeTitle, design: .serif)
    static let stat = Font.system(.title, design: .rounded).weight(.semibold).monospacedDigit()
}
// Animated numerals (iOS 17 / macOS 14+):
Text(left, format: .number).font(.num(34))
    .contentTransition(.numericText(countsDown: true))
    .animation(.snappy(duration: 0.35), value: left)
```

The existing `rounded(_:_:)` helper at `Island.swift:552` becomes `Font.num`.

## 9. Do / don't

**Do:**
- Keep serif roman, weight 400–500.
- Put tnum on every number.
- Use sentence-case labels.
- Floors: 12px web, 11pt Apple.
- Display tracking between -0.01 and -0.025em.
- Body line-height ≥1.5, plus 0.05 on dark backgrounds.
- Use at most 3 weights per face (400/500/600).
- Rely on system tracking on Apple; tracking only the wordmark.

**Don't:**
- Use italic serif headlines (the impeccable `italic-serif-display` rule).
- Use uppercase eyebrows above every section.
- Ship Inter, Geist, or anything else in `OVERUSED_FONTS`.
- Set tracking beyond ±0.05em.
- Add a NVIDIA-ish third face.
- Use serif inside Live Activities.
- Load italics we don't use (the current URL loads the Newsreader italic axis for nothing).

**Housekeeping:** CLAUDE.md's "Design system" section still says "sans only (Inter…), no serif". Update it to Pairing A once the user confirms, or the next agent will undo this change.
