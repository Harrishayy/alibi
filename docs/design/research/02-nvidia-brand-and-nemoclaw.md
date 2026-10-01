# 02 · NVIDIA brand, NemoClaw/OpenClaw, and the Alibi mascot

The short version: NVIDIA's own rules forbid third parties from imitating NVIDIA's visual style, so Alibi's current approach (calm Claude-like layout with NVIDIA green as a signal colour) is both the safer choice and the better-looking one. Keep `#76B900` for small, meaningful things: action, progress, "on task" and the mascot. Never use the logo, the eye mark or NVIDIA Sans.

## 1. What NVIDIA actually does (and what we borrow)

**Usage on nvidia.com** ([design analysis](https://cdn.jsdelivr.net/npm/oh-my-opencode@4.18.2/dist/skills/frontend/references/design/nvidia.md), [getdesign.md](https://getdesign.md/design-md/nvidia/preview)):
- The base is black `#000` and white `#FFF`, with sections alternating dark and light. `#1A1A1A` is used for dark cards and `#5E5E5E` for borders. Alibi already uses both.
- **Green is a signal, not a surface.** It shows up as `2px solid #76B900` borders, 2px link underlines, CTA outlines and active indicators. It is "never a background or large surface area" on main content.
- Corners are 2px, there is one ambient shadow (`0 0 5px rgba(0,0,0,.3)`), type is bold 700 almost everywhere, and the stated rule is "no glassmorphism, blur, or complex gradients".
- Extended colours: green-light `#BFF230`, success green `#3F8500`, red `#E52020`, orange `#DF6500` and purple `#4D1368` (used for AI/premium gradient ends).
- Font: NVIDIA-EMEA / NVIDIA Sans, with Arial as the fallback.

**What Alibi borrows:** green as signal, black and `#1A1A1A` surfaces, `#5E5E5E` hairlines, and the 2px green underline for links on light backgrounds.
**What Alibi deliberately does not borrow:** 2px corners, bold-everything type and uppercase nav. The user already rejected that look, and NVIDIA's guidelines discourage imitating it anyway (see §2).

**Proportion budget per screen:** neutrals at least 85% of pixels, green at most 8–10% (primary button, ring, progress, mascot), status colours at most 5%. A full green fill is allowed only on the primary button, the "done" celebration burst and the mascot. Text on a green fill is always `#000` (8.71:1).

**Gradients:** none in the UI chrome. One flourish is allowed, for the celebration moment and video title cards: a green bloom on black, `radial-gradient(closest-side, rgba(118,185,0,.35), rgba(118,185,0,0))`, sized about 1.6× the mascot. It reads as GTC-style rendered light without copying any NVIDIA artwork. *I could not find a published GTC 2026 visual-identity spec, so treat the "GTC look" here as observation, not a rule.*

**Photography/illustration:** NVIDIA's marketing is dark, product-render, rendered-light imagery. Alibi has no photography beyond the user's own camera frames, so: frames in contact sheets get a `#262626` 1px keyline with 12px radius and no filters, and the mascot is the only illustration.

## 2. Brand rules for a third-party entry (do / don't)

Source: [NVIDIA Logo and Brand Guidelines](https://nvidia.com/en-us/about-nvidia/legal-info/logo-brand-usage).

| Do | Don't |
|---|---|
| Name NVIDIA tech in **plain text**, e.g. "Runs on NVIDIA Nemotron via build.nvidia.com" | Use the NVIDIA logo or eye mark anywhere in app chrome, the icon, the mascot or the reel |
| Write "Entry for the NVIDIA London Claw Agent Challenge" as plain text on the title card | Imply "affiliation, endorsement, or sponsorship that isn't approved" |
| Use a logo only if organisers supply one for entrants, unmodified, with clear space equal to the "n" height | Recreate, recolour, stylise or crop the logo; use retired marks |
| Make an original mascot | Use fan art of NVIDIA marks, or "imitate or appropriate NVIDIA visual style" |
| Use Inter (already in use) | Use **NVIDIA Sans**: its EULA grants use "in connection with NVIDIA's products and services only" ([EULA](https://raytracing-docs.nvidia.com/iray/ext/fonts/nvidia-sans/NVIDIA_Sans_EULA_20220602_FINAL.pdf); [summary](https://madegooddesigns.com/?p=12212)) |

**Type substitutes:** Inter is the closest licence-clean neutral and Jost is closest for a geometric wordmark ([alternatives](https://fontalternatives.com/alternatives/google-sans/with/tech/)). Recommendation: keep Inter 400/600 for UI and Newsreader / New York for display, as the design direction already says. For the "ALIBI" wordmark, use Inter 800, `letter-spacing: .14em`. Don't add a third family.

## 3. NemoClaw, OpenClaw and the lobsters

- **NemoClaw** was announced by Jensen Huang at GTC on 16 March 2026. It is an Apache-2.0 stack that installs the **OpenShell** sandboxed runtime (part of the Agent Toolkit) and **Nemotron** models around OpenClaw in one command ([docs.nvidia.com/nemoclaw](https://docs.nvidia.com/nemoclaw/), [Barchart](https://business.minstercommunitypost.com/minstercommunitypost/article/barchart-2026-3-17-nvidia-just-announced-nemoclaw-to-make-openclaw-safer-as-lobster-ai-agent-craze-raises-security-alarms), [classmethod GTC report](https://dev.classmethod.jp/articles/gtc2026-nemoclaw-preview/)). The press calls it NVIDIA's "green lobster" ([INSIDE](https://www.inside.com.tw/article/40811-nvidia-green-lobster-nemoclaw-is-rumored-to-debut-at-gtc-2026)). I found **no official NemoClaw mascot artwork**: the GitHub README and docs show none. NVIDIA's site reportedly ran an AI cartoon of Jensen sewing a lobster doll ([36kr](https://eu.36kr.com/en/p/3717904404936072)). So "green lobster" is a nickname, not a protected character. That makes room for an original one, but don't call ours "NemoClaw" or "Nemo-anything", because Nemo/Nemotron are NVIDIA marks.
- **OpenClaw** is Peter Steinberger's self-hosted agent. Its mascot went Clawd (a "space lobster", Nov 2025) → Moltbot → **Molty** (27 Jan 2026, after Anthropic's trademark email). Personality: enthusiastic, chaotic and pun-heavy ("EXFOLIATE!", "The claw is the law", "New shell, same lobster soul"), pronouns they/them ([OpenClaw lore](https://docs.openclaw.ai/start/lore)). The look is a **red-orange pixel/8-bit lobster** with two raised claws, small black dot eyes and a compact symmetric silhouette ([merch listings](https://www.teepublic.com/pins/openclaw-ai)). The homepage uses ASCII-art lobsters and 🦞 everywhere ([openclaw.ai](https://openclaw.ai)).
- **Event branding:** there is no public "Claw Agent Challenge London" branding. Related events: NVIDIA "Build-a-Claw" workshops ([Seoul](https://www.invenglobal.com/articles/20954/build-your-own-ai-agent-nvidias-build-a-claw-comes-to-seoul), [Tokyo](https://dev.classmethod.jp/en/articles/nvidia-build-a-claw-tokyo-report/)), [Sheffield, 11 Jul 2026](https://rse.sheffield.ac.uk/events/workshop-2026-07-11-building-practical-ai-agents-using-claw.html) and the community [ClawClub London hack night](https://luma.com/zztvmfnl). Don't invent an event logo.

**Where our mascot sits:** OpenClaw = red, pixel, chaotic. Ours = **green, smooth flat vector, calm, observant**. It's a cousin in species and colour, and different in rendering and temperament. That fits Alibi: a witness, not a gremlin.

## 4. Colour system extension

All ratios below are WCAG 2.x, computed in a script (sRGB relative luminance). AA = 4.5 for body text, 3.0 for large text or UI glyphs.

**Green ramp** (OKLCH hue 130.8°, `#76B900` = L 0.713 C 0.194; steps hold the hue):

| Step | Hex | on #FFF | on #000 | on #1A1A1A | Use |
|---|---|---|---|---|---|
| 50 | `#E6FFD1` | 1.07 | 19.6 | 16.2 | lightest wash |
| 100 | `#D0FCA9` | 1.16 | 18.2 | 15.1 | selected chip bg (light) |
| 200 | `#AAF059` | 1.37 | 15.3 | 12.7 | confetti, highlight |
| 300 | `#97DC42` | 1.66 | 12.6 | 10.5 | mascot belly/highlight |
| **500** | **`#76B900`** | 2.41 ✗ | **8.71** | **7.22** | hero fill; text on dark |
| 600 | `#588C05` | 4.06 | 5.17 | 4.28 | mascot shade, large text on white |
| 700 | `#477200` | **5.71** | 3.67 | 3.05 | green text on washes |
| 800 | `#365900` | 8.12 | — | — | mascot outline/eyes on light |
| 900 | `#264100` | 11.4 | — | — | — |

Amber and red ramps use the same method: amber 600 `#A17005` (4.34 on #FFF), 700 `#845A01` (6.10); red 600 `#D53740`, 700 `#B81228` (6.66).

**Semantic tokens** (light / dark), checked against the current `:root` in `alibi/web/index.html`:

| Token | Fill (light/dark) | Text ink light → ratio on #FFF / #F2F2F2 | Text ink dark → ratio on #1A1A1A / #262626 |
|---|---|---|---|
| on_task / done | `#76B900` | `#4E7A00` → 5.11 / 4.57 | `#8FD400` → 9.60 / 8.35 |
| idle / partial | `#F2A900` | `#8A5F00` → 5.65 / 5.05 | `#FFC233` → 10.79 |
| phone / slacked | `#E5484D` | `#C4161C` → 6.04 / 5.39 | `#FF7A7E` → 6.91 / 6.01 |
| off_task | `#C8362B` + **hatch** | `#C4161C` | `#FF7A7E` |
| absent | `#A6A6A6` / `#767676` dashed ring | `#5E5E5E` → 6.48 / 5.79 | `#A6A6A6` → 7.15 / 6.22 |
| on-fill text | `#000` on green 8.71, on amber 10.45, on red 5.37 | never `#FFF` on red (3.91 ✗) | |

**Fixes found in the current tokens:**
1. `--accent-ink #4E7A00` on `--accent-wash #EAF4D6` is **4.48, just under AA**. Use `#477200` on washes (5.01).
2. `--faint #8C8C8C` on `#FFF` is 3.36. Use it only for ≥18px text or icons, or change it to `#6E6E6E` (5.10 / 4.55 on #F2F2F2).
3. Dark `--faint #767676` on `#1A1A1A` is 3.83. Change it to `#8C8C8C` (5.18; 4.50 on #262626).
4. `--phone #E5484D` vs `--off_task #C8362B` is ΔE_ok 7.4 and 1.34:1, so they're **indistinguishable** in a 10px sample dot. Either merge them visually and distinguish by shape, or (an open question) give off_task its own hue.

**Colour-blind check** (Machado simulation): **green vs amber under protanopia ΔE 0.6, i.e. identical**. Green vs red under deuteranopia is ΔE 9.1 (weak). So redundant encoding is required, not optional:
- on_task: filled circle
- idle: 2px amber **ring** (hollow)
- phone: filled red **rounded square**
- off_task: red with 45° hatch (`repeating-linear-gradient(45deg, var(--c) 0 2px, transparent 2px 4px)`)
- absent: 1.5px **dashed** grey ring
- Verdict pills always carry a glyph and a word: `✓ Done`, `◐ Partly`, `✕ Slacked`.

## 5. Mascot: an original green cousin

**Concept:** a small green lobster **witness**. Calm, curious, a little dry, never mean. Its role is "I saw what I saw", and the Duo-style emotional range comes from the eyes and claws, not from words.

**Silhouette options** (pick one; A is recommended):
- **A. "Bean with mitts"** (recommended). Rounded bean body, width:height 1 : 1.15. Two oversized claws, each about 45% of body width, held up beside the face. Two short eye-stalks with large round eyes (eye diameter about 22% of body width; 2 px pupils at 16 px). No legs or tail below 48 px. The raised claws make the "V" that reads as *lobster* even as a blob.
- **B. "Detective"**: A plus one claw holding a magnifying lens. The lens **doubles as the camera-on indicator** (glows green while sampling, empty ring when the camera is off), which turns a privacy cue into character.
- **C. "Pincer glyph"**: for 12–16 px only, a single claw whose closing pincer forms a check mark on "done". Use it as the favicon/app-icon fallback.

**Level of detail (LOD) by size:**

| Size | Parts | Rules |
|---|---|---|
| 16 px / pt (notch wing, favicon) | body + 2 claws + 2 eyes = **5 shapes**, solid fills | `#76B900` on black (8.71:1); smallest feature 2 px; no outline; snap to whole pixels |
| 24–48 px (alerts, chips) | + eye-stalks, eyelid shape, belly tint `#97DC42` | 1.5 px `#365900` outline on light bg only |
| 120–160 px (celebration, onboarding) | + antennae (2 curved strokes), 3 tiny leg pairs, tail fan, cheek highlight, optional lens | shade `#588C05`, highlight `#AAF059`; still flat, no 3D or pixel style |

**Expression set** (eyes + claws carry everything):

| Event | Pose | Motion (web ms / SwiftUI) |
|---|---|---|
| idle | half-lid blink every 4–7 s (random), breathe scale 1→1.02 | 3200 ms ease-in-out loop |
| watching / on-task | eyes open, slow look left/right, small nod every ~20 s | translate ±1.5 px, 600 ms |
| drift / phone | eyes narrow (lid 40%), one claw taps twice, "ahem" | 2× 140 ms taps; `.spring(response: 0.25, dampingFraction: 0.5)` |
| partial | shrug: both claws up 15°, one eye squint | 420 ms `cubic-bezier(.34,1.56,.64,1)` |
| slacked | claws drop, eyes look down, 6% squash; stays green (shame is not red) | 500 ms ease-out, no bounce |
| done | jump 18% of height + claw clack + green/white confetti + bloom | `.spring(response: 0.35, dampingFraction: 0.55)`; web 520 ms overshoot |

Under `prefers-reduced-motion` / `accessibilityReduceMotion`, swap poses with a 150 ms cross-fade and no jump or confetti.

**Build:** code only, no image assets. Web: inline SVG with named groups, toggled by a state class. macOS/iOS: the same geometry as SwiftUI `Shape`s (`Ellipse`, `Capsule`, `Path`) in a `ZStack`, so springs are native.

```html
<svg class="mascot is-idle" viewBox="0 0 64 64" aria-hidden="true">
  <g class="claw L" style="transform-origin:18px 34px"><path d="M8 30c-6-8 0-18 8-14 3 2 3 6 1 8l4 4-5 6z" fill="#76B900"/></g>
  <g class="claw R" style="transform-origin:46px 34px"><path d="M56 30c6-8 0-18-8-14-3 2-3 6-1 8l-4 4 5 6z" fill="#76B900"/></g>
  <ellipse class="body" cx="32" cy="40" rx="15" ry="17" fill="#76B900"/>
  <g class="eyes"><circle cx="26" cy="30" r="4.5" fill="#fff"/><circle cx="38" cy="30" r="4.5" fill="#fff"/>
    <circle class="pupil" cx="26.5" cy="31" r="2" fill="#000"/><circle class="pupil" cx="38.5" cy="31" r="2" fill="#000"/></g>
</svg>
```

**Name ideas:**
1. **Pinch** (recommended): one syllable, fits a notch alert, and the copy writes itself ("Pinch saw your phone for 3 minutes"). It means "caught you" without menace.
2. **Bailey**: after the Old Bailey, London's criminal court. It fits the alibi theme, nods to the London event, and sounds like a friendly pet name.
3. **Copper**: British slang for police officer, with a London nod. Gentle irony for a green lobster.
4. **Gumshoe**, nickname "Gummy": old detective slang. Playful, and it suits silhouette B.
5. **Alby**: short for Alibi. Zero learning cost, and the brand and mascot reinforce each other.

Avoid Molty, Clawd, anything Nemo-, and "Claw" as the whole name: they belong to someone else or confuse the lineage.
