#!/usr/bin/env python3
"""Single source for the Alibi token layer.

Writes docs/design/system/project/tokens.json and docs/design/tokens/tokens.css,
build_swift.py and build_specimen.py import this table to write Theme.swift and specimen.html.
Every contrast ratio in a usage note is computed here (WCAG 2, sRGB relative
luminance; rgba() colours are composited over the ground first).
"""
import json, math, re, sys, os

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
OUT_JSON = f"{REPO}/docs/design/system/project/tokens.json"
OUT_CSS = f"{REPO}/docs/design/tokens/tokens.css"

# ---------------------------------------------------------------- colour maths
def parse(c):
    c = c.strip()
    if c.startswith("#"):
        h = c[1:]
        if len(h) == 3: h = "".join(x * 2 for x in h)
        return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], 1.0
    m = re.match(r"rgba?\(([^)]*)\)", c)
    p = [float(x) for x in m.group(1).replace("/", ",").split(",")]
    return [x / 255 for x in p[:3]], (p[3] if len(p) > 3 else 1.0)

def lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def lum(rgb): r, g, b = map(lin, rgb); return 0.2126 * r + 0.7152 * g + 0.0722 * b

def flat(fg, bg):
    """Composite fg (maybe translucent) over an opaque bg."""
    f, a = parse(fg); b, _ = parse(bg)
    return [a * x + (1 - a) * y for x, y in zip(f, b)]

def ratio(fg, bg):
    x, y = sorted([lum(flat(fg, bg)), lum(parse(bg)[0])], reverse=True)
    return (x + 0.05) / (y + 0.05)

# ---------------------------------------------------------------- the palette
THEMES = ["dark", "light"]
GROUND = {  # named grounds per theme
    "dark": {"bg": "#000000", "surface-1": "#1A1A1A", "surface-2": "#262626", "surface-3": "#333333",
             "island": "#000000", "accent-wash": "#1C2A06", "partial-wash": "#2E2203", "warn-wash": "#3A1414",
             "accent": "#76B900", "accent-hover": "#85C900", "accent-press": "#6AA800", "warn": "#E5484D",
             "partial": "#F2A900", "ink": "#F2F2F2", "pinch-body": "#76B900"},
    "light": {"bg": "#F2F2F2", "surface-1": "#FFFFFF", "surface-2": "#F7F7F7", "surface-3": "#EBEBEB",
              "island": "#000000", "accent-wash": "#EAF4D6", "partial-wash": "#FDF1D6", "warn-wash": "#FBE3E3",
              "accent": "#76B900", "accent-hover": "#6AA800", "accent-press": "#5E9900", "warn": "#E5484D",
              "partial": "#A17005", "ink": "#1A1A1A", "pinch-body": "#76B900"},
}
SURF = ["bg", "surface-1", "surface-2", "surface-3"]
SURF3 = ["bg", "surface-1", "surface-2"]

# name, dark, light, kind, grounds (None = no contrast claim), usage
# kind: text (4.5:1) · mark (3:1: icons, rings, dots, focus, meaningful borders) · fill · ground · line · deco
C = [
    # surfaces
    ("bg", "#000000", "#F2F2F2", "ground", None,
     "Page canvas behind every card on the web dashboard and the iPhone app; the window behind the island menu bar. Dark-first: pure black, so the island and the page read as one object."),
    ("surface-1", "#1A1A1A", "#FFFFFF", "ground", None,
     "Cards on bg: the Now card, latest verdict, today timeline, week, sessions; iPhone grouped rows; the composer at rest. Separate it from bg with hairline, not a shadow."),
    ("surface-2", "#262626", "#F7F7F7", "ground", None,
     "Raised or nested layer inside a card: the composer while focused, popovers, the setup drawer, the correction popover, hover state of a row on surface-1."),
    ("surface-3", "#333333", "#EBEBEB", "ground", None,
     "Pressed rows, selected chips without colour, meter and ring tracks, the segmented-control thumb rail, keycap (Kbd) fill. Only ink and ink-2 may sit on it; never ink-3."),
    ("island", "#000000", "#000000", "ground", None,
     "The notch island fill on Mac (both themes: it must merge with the hardware notch) and the Live Activity / Dynamic Island backdrop. Solid, no glass, no gradient."),
    ("scrim", "rgba(0,0,0,0.64)", "rgba(0,0,0,0.32)", "deco", None,
     "Behind the setup drawer, the lightbox for contact-sheet frames and iPhone sheets. Fades in on dur-medium, out at 0.65x."),
    # ink
    ("ink", "#F2F2F2", "#1A1A1A", "text", SURF,
     "Primary text: headings, body, voice lines, stats, button labels on neutral fills. Reads on bg, surface-1, surface-2 and surface-3."),
    ("ink-2", "#A6A6A6", "#5E5E5E", "text", SURF,
     "Secondary text: meta lines, timestamps, captions under stats, inactive tab labels, icons beside labels. Reads on bg, surface-1, surface-2 and surface-3."),
    ("ink-3", "#8F8F8F", "#6E6E6E", "text", SURF3,
     "Faint text: composer placeholder, disabled labels, keyboard hints, chart axis labels. Reads on bg, surface-1 and surface-2 only (it fails on surface-3; use ink-2 there). Replaces the failing #767676 / #8C8C8C."),
    ("ink-inverse", "#000000", "#FFFFFF", "text", ["ink"],
     "Text on an ink fill: tooltips and the snackbar, which invert the theme. Never on green (use on-accent) or red (use on-warn)."),
    # lines
    ("hairline", "rgba(255,255,255,0.08)", "rgba(0,0,0,0.08)", "line", None,
     "Decorative 1px dividers and card edges: card borders on bg, list separators, the today-timeline rules. Depth comes from this, not from shadows. Not a component boundary (see hairline-strong)."),
    ("hairline-strong", "rgba(255,255,255,0.38)", "rgba(0,0,0,0.46)", "mark", SURF,
     "1px boundary of a control that has no fill of its own: unchecked checkbox and radio, the composer outline when it sits directly on bg, the unselected segmented control, the dashed absent ring outline. Meets 3:1 on bg, surface-1, surface-2 and surface-3."),
    # accent
    ("accent", "#76B900", "#76B900", "fill", None,
     "NVIDIA green, exact. Fill for the one primary button per view, the send button, the progress ring and meter on dark grounds, the selected tab indicator, the 2px now-line. At most 5% of chrome. Always paired with on-accent text. As a thin mark on light grounds it is only 2.41:1 on white, so light-theme rings and meters use on-task."),
    ("accent-hover", "#85C900", "#6AA800", "fill", None,
     "Hover fill of accent buttons (pointer: fine only). Lighter in dark, deeper in light; on-accent still reads on it."),
    ("accent-press", "#6AA800", "#5E9900", "fill", None,
     "Pressed fill of accent buttons, together with scale 0.97 on dur-micro."),
    ("on-accent", "#000000", "#000000", "text", ["accent", "accent-hover", "accent-press"],
     "Text and icons on any green fill: primary button label, send arrow, the Done verdict pill, the contact-sheet badge. Always black, never white."),
    ("accent-ink", "#8FD400", "#477200", "text", SURF + ["accent-wash"],
     "Green text: links, 'On task 92%' figures, the active chip label, the honesty line's 'seen' number. Reads on bg, surface-1, surface-2, surface-3 and accent-wash. Light uses #477200 (green-700) because #4E7A00 fails on the wash (4.48)."),
    ("accent-wash", "#1C2A06", "#EAF4D6", "ground", None,
     "Tinted ground for a selected chip, the on-task streak pill, ::selection, the focused composer's send-area halo. Text on it is accent-ink or ink."),
    ("focus-ring", "#76B900", "#588C05", "mark", SURF,
     "2px :focus-visible outline with 2px offset on every focusable element, web and iPhone. Light uses green-600 because #76B900 is only 2.15:1 on the light page. Meets 3:1 on bg, surface-1, surface-2 and surface-3."),
    # green ramp (mascot + data viz)
    ("green-100", "#D0FCA9", "#D0FCA9", "deco", None, "Lightest green: celebration particles on dark, the bloom's hot centre in the reel title card. Never text."),
    ("green-200", "#AAF059", "#AAF059", "deco", None, "Pinch sparkles on dark grounds, confetti highlight. Never text."),
    ("green-300", "#97DC42", "#97DC42", "deco", None, "Pinch belly and highlight. Never text."),
    ("green-500", "#76B900", "#76B900", "deco", None, "Ramp anchor, identical to accent: Pinch body, claimed-vs-seen 'seen' bars on dark."),
    ("green-600", "#588C05", "#588C05", "mark", SURF3,
     "Pinch shade; light-theme focus ring; 'seen' bars on light. A 3:1 mark on light grounds only."),
    ("green-700", "#477200", "#477200", "text", None, "Green text on light grounds and washes (same value as light accent-ink)."),
    ("green-800", "#365900", "#365900", "deco", None, "Pinch outline on light grounds; dark lines inside the mascot (mouth, antennae)."),
    # status (always paired with a shape)
    ("on-task", "#76B900", "#588C05", "mark", SURF,
     "Sample dot: filled circle. Also the session ring and meter fill, and 'seen' bars. Shape-coded: green and amber are identical under protanopia, so the circle shape carries the meaning."),
    ("on-task-ink", "#8FD400", "#477200", "text", SURF + ["accent-wash"],
     "Text naming on-task time: 'On task 92%', '1h 52m seen'. Reads on bg, surface-1, surface-2, surface-3 and accent-wash."),
    ("partial", "#F2A900", "#A17005", "mark", SURF,
     "Partial verdict mark: the half-filled circle glyph, meter fill between partAt and doneAt, amber ring for breaks. Light uses a deeper amber so the mark meets 3:1."),
    ("partial-ink", "#FFC233", "#8A5F00", "text", SURF + ["partial-wash"],
     "Text for partial, idle and break states: 'Partly', 'Idle 4 min', the break countdown label. Reads on bg, surface-1, surface-2, surface-3 and partial-wash."),
    ("partial-wash", "#2E2203", "#FDF1D6", "ground", None,
     "Tinted ground for the Partly verdict pill and the break banner. Text on it is partial-ink or ink."),
    ("warn", "#E5484D", "#E5484D", "mark", SURF,
     "Red mark: phone and off-task dots, slacked meter fill, error icons. Never the accent, never a full red card. Text on a red fill is on-warn."),
    ("warn-ink", "#FF7A7E", "#C4161C", "text", SURF + ["warn-wash"],
     "Red text: the noun in a nudge ('your phone'), error messages, 'Slacked'. Reads on bg, surface-1, surface-2, surface-3 and warn-wash."),
    ("warn-wash", "#3A1414", "#FBE3E3", "ground", None,
     "10% red tint behind the Slacked pill and an error row. Text on it is warn-ink or ink."),
    ("on-warn", "#000000", "#000000", "text", ["warn"],
     "Text on a solid red fill (destructive button, phone badge). Black, because white is 3.91:1."),
    ("idle", "#F2A900", "#A17005", "mark", SURF,
     "Idle sample: hollow amber ring (2px). Same hue as partial; the ring shape tells them apart."),
    ("idle-ink", "#FFC233", "#8A5F00", "text", SURF + ["partial-wash"],
     "Text for idle: 'Idle 3 min', 'On a break'. Same values as partial-ink."),
    ("phone", "#E5484D", "#E5484D", "mark", SURF,
     "Phone sample: filled red rounded square. Same red as warn; the square shape carries it."),
    ("off-task", "#E5484D", "#E5484D", "mark", SURF,
     "Off-task sample: red square with a 45 degree hatch (repeating-linear-gradient 2px/2px). Replaces the retired #C8362B, which was indistinguishable from phone red."),
    ("absent", "#A6A6A6", "#767676", "mark", SURF,
     "Absent sample: 1.5px dashed grey ring; island wing when nobody is at the desk. Must be #A6A6A6 in the island."),
    ("absent-ink", "#A6A6A6", "#5E5E5E", "text", SURF,
     "Text for absent: 'Away 6 min', 'No frames'. Reads on bg, surface-1, surface-2 and surface-3."),
    # verdict aliases
    ("done", "{on-task}", "{on-task}", "mark", SURF, "Verdict alias: Done. The pill reads '✓ Done' as on-accent on accent, or on-task-ink on accent-wash; the mark (meter, dot) uses this."),
    ("partly", "{partial}", "{partial}", "mark", SURF, "Verdict alias: Partly. Pill '◐ Partly' in partial-ink on partial-wash."),
    ("slacked", "{warn}", "{warn}", "mark", SURF, "Verdict alias: Slacked. Pill '✕ Slacked' in warn-ink on warn-wash. Pinch stays green and supportive."),
    # mascot (exempt from the 5% green budget)
    ("pinch-body", "#76B900", "#76B900", "deco", None, "Pinch's body and claws at every size from the 16pt wing to the 160pt celebration."),
    ("pinch-belly", "#97DC42", "#97DC42", "deco", None, "Belly patch and claw-tip highlight, 24pt and up."),
    ("pinch-shade", "#588C05", "#588C05", "deco", None, "Underside shade, inner claw, tail fan; 24pt and up."),
    ("pinch-outline", "#8FD400", "#365900", "mark", ["bg", "surface-1"],
     "1.5px outline at 24pt and up: a bright rim on dark grounds, a deep outline on light grounds. Off at 16pt (silhouette only)."),
    ("pinch-eye", "#000000", "#000000", "mark", ["pinch-body"], "Dot eyes and pupils (black on green body). One white highlight per eye in pinch-shine."),
    ("pinch-shine", "#FFFFFF", "#FFFFFF", "deco", None, "Eye highlight dot; lens glass glint."),
    ("pinch-blush", "rgba(242,169,0,0.4)", "rgba(242,169,0,0.4)", "deco", None, "Cheek blush on celebrate and hello. Amber at 40%, never red."),
    ("pinch-spark", "#AAF059", "#588C05", "deco", None, "Sparkles around Pinch on celebrate and connected; deeper on light so they stay visible on white."),
    ("pinch-lens", "#D7D7D7", "#5E5E5E", "mark", ["bg", "surface-1"], "Rim and handle of Pinch's detective magnifying lens."),
    ("pinch-lens-glow", "rgba(170,240,89,0.55)", "rgba(118,185,0,0.4)", "deco", None,
     "Lens glass while the camera is sampling (the lens is the camera-on indicator). Off = empty glass in the ground colour."),
    ("bloom", "rgba(118,185,0,0.35)", "rgba(118,185,0,0.28)", "deco", None,
     "Centre stop of the one allowed gradient, the celebration bloom: radial-gradient(closest-side, var(--bloom), transparent) at 1.6x Pinch's size, behind the verdict reveal and streak moments only."),
]

def resolve(name, theme):
    for n, d, l, *_ in C:
        if n == name:
            v = d if theme == "dark" else l
            return resolve(v[1:-1], theme) if v.startswith("{") else v
    return GROUND[theme][name]

def ground_val(g, theme):
    return resolve(g, theme) if any(n == g for n, *_ in C) else GROUND[theme][g]

failures = []
report = []
def contrast_note(name, kind, grounds):
    if not grounds: return ""
    need = 4.5 if kind == "text" else 3.0
    parts = []
    for t in THEMES:
        fg = resolve(name, t)
        rs = []
        for g in grounds:
            r = ratio(fg, ground_val(g, t))
            rs.append(f"{r:.2f} on {g}")
            report.append((t, name, g, round(r, 2), need))
            if r < need - 1e-9: failures.append((t, name, g, round(r, 2), need))
        parts.append(f"{t.capitalize()} " + ", ".join(rs))
    label = "text, needs 4.5:1" if kind == "text" else "mark, needs 3:1"
    return f" Contrast ({label}): " + "; ".join(parts) + "."

def jsonhex(v):  # the Design System page stores hex lowercased; write it that way so a round trip is a no-op
    return v.lower() if v.startswith("#") else v

color_tokens = []
for n, d, l, kind, grounds, usage in C:
    value = {"dark": jsonhex(d), "light": jsonhex(l)} if d != l else jsonhex(d)
    color_tokens.append({"name": n, "value": value, "usage": usage + contrast_note(n, kind, grounds)})

# ---------------------------------------------------------------- type
SANS = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Onest", system-ui, sans-serif'
ROUNDED = 'ui-rounded, -apple-system, "SF Pro Rounded", "Onest", system-ui, sans-serif'
MONO = 'ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace'

WEB = [  # name, family, size, lh, weight, tracking, tnum, sample, usage
    ("display", "rounded", 56, 1.0, 600, "-0.025em", True, "24:07",
     "The live session timer in the Now card and the verdict reveal's count-up. Rounded numerals, tabular."),
    ("h1", "sans", 32, 1.15, 600, "-0.02em", False, "Claimed 2h 10m. Seen 1h 52m.",
     "One per page: the dashboard honesty line in the hero strip, onboarding titles."),
    ("h2", "sans", 22, 1.25, 600, "-0.015em", False, "Latest verdict",
     "Section titles in sentence case: Now, Latest verdict, Today, This week, Sessions."),
    ("h3", "sans", 17, 1.35, 600, "-0.01em", False, "Drawing · 25 min",
     "Card and row titles: the session name, a plan block, a setup group."),
    ("voice", "sans", 20, 1.45, 500, "-0.01em", False, "You said drawing. I've seen your phone for 3 minutes.",
     "Alibi's voice: Pinch's lines, the verdict sentence, the nightly report sentences. Same family as the UI; weight and size make it the voice."),
    ("body", "sans", 16, 1.55, 400, "0em", False, "Twenty-five minutes at the desk, camera on, laptop on Procreate the whole time.",
     "Default reading text. In dark: line-height 1.6 and +0.01em tracking (tokens.css swaps --body-lh / --body-ls). Prose capped at 62ch."),
    ("small", "sans", 13, 1.45, 400, "0em", False, "Sampled every 30 s · last frame 14:32",
     "Meta lines, timestamps, captions under stats, helper text. Usually in ink-2."),
    ("label", "sans", 12, 1.3, 600, "0.01em", False, "On task",
     "Chips, field labels, pill text, tab labels. Sentence case only, never uppercase eyebrows. The web floor."),
    ("stat", "rounded", 32, 1.0, 600, "-0.02em", True, "92%",
     "Single stats: on-task %, seen minutes, streak days. Rounded, tabular."),
    ("mono", "mono", 12, 1.4, 500, "0em", True, "⌥⌘A",
     "Keycaps (Kbd) and IDs only: session ids, file paths in setup. Never for labels or eyebrows."),
]
ISLAND = [
    ("island-wordmark", "sans", 12, 1.0, 800, "1.6px", False, "ALIBI", "The island wordmark: SF Pro Heavy 12pt, tracking 1.6. The only uppercase text in the system."),
    ("island-wing", "rounded", 13, 1.2, 600, "0px", True, "24m", "Right wing countdown in live wings: SF Pro Rounded semibold, monospacedDigit, numericText(countsDown: true)."),
    ("island-timer", "rounded", 34, 1.0, 600, "-0.5px", True, "24:07", "Expanded island session timer: Rounded semibold, monospacedDigit, tracking -0.5."),
    ("island-title", "sans", 17, 1.3, 600, "0px", False, "Drawing", "Session title and alert headline in the expanded island, nudge and verdict alerts."),
    ("island-voice", "sans", 15, 1.4, 500, "0px", False, "You said drawing. I've seen your phone for 3 minutes.", "Pinch's line in nudge and verdict alerts and the drift line; the noun alone in warn-ink."),
    ("island-body", "sans", 14, 1.4, 400, "0px", False, "What are you about to do?", "Composer text and body copy in the expanded island; lineSpacing 3."),
    ("island-secondary", "sans", 12, 1.35, 400, "0px", False, "Next up · Run at 18:00", "Secondary island text at 60% white. The island floor is 11pt (badge digits only below that)."),
]
IOS = [
    ("ios-largetitle", "sans", 34, 1.2, 600, "0px", False, "Today", "iPhone screen titles: .largeTitle semibold (34/41 at the Large setting). Dynamic Type."),
    ("ios-title", "sans", 22, 1.27, 600, "0px", False, "This week", "Section headers: .title2 semibold (22/28); .title3 semibold (20/25) for subsections."),
    ("ios-headline", "sans", 17, 1.29, 600, "0px", False, "Drawing · 25 min", "Row titles: .headline (17/22)."),
    ("ios-body", "sans", 17, 1.29, 400, "0px", False, "Synced from your Mac 2 min ago.", "Body: .body (17/22); .subheadline (15/20) for dense rows."),
    ("ios-footnote", "sans", 13, 1.38, 400, "0px", False, "Steps from Apple Health · updated 09:41", "Meta lines: .footnote (13/18)."),
    ("ios-caption", "sans", 12, 1.33, 600, "0px", False, "Last 7 days", "Labels and chip text: .caption semibold (12/16), sentence case."),
    ("ios-stat", "rounded", 28, 1.21, 600, "0px", True, "1h 52m", "Stats: .title rounded semibold, monospacedDigit (28/34)."),
    ("ios-timer", "rounded", 56, 1.0, 600, "0px", True, "18:42", "Today hero timer: 56pt rounded semibold, monospacedDigit, Text(timerInterval:)."),
]
LA = [
    ("la-title", "sans", 15, 1.3, 600, "0px", False, "Drawing", "Lock Screen Live Activity habit title: 15pt semibold."),
    ("la-timer", "rounded", 34, 1.0, 600, "0px", True, "18:42", "Lock Screen countdown: 34pt rounded semibold, monospacedDigit, Text(timerInterval:countsDown:)."),
    ("la-compact", "rounded", 14, 1.0, 600, "0px", True, "18:42", "Dynamic Island compact trailing timer: 14pt rounded semibold in a fixed 40pt frame."),
    ("la-expanded-center", "sans", 17, 1.3, 600, "0px", False, "On task 92%", "Dynamic Island expanded centre line: 17pt semibold."),
]

def style(row):
    n, fam, size, lh, w, ls, tnum, sample, usage = row
    s = {"name": n, "family": fam, "fontSize": f"{size}px", "lineHeight": lh, "fontWeight": w,
         "letterSpacing": ls, "sample": sample, "usage": usage + (" Tabular figures." if tnum and "abular" not in usage else "")}
    return s

type_block = {
    "fonts": [],
    "families": {"sans": SANS, "rounded": ROUNDED, "mono": MONO},
    "groups": [
        {"name": "Web", "family": "sans", "styles": [style(r) for r in WEB]},
        {"name": "Mac island", "family": "sans", "styles": [style(r) for r in ISLAND]},
        {"name": "iPhone", "family": "sans", "styles": [style(r) for r in IOS]},
        {"name": "Live Activity", "family": "sans", "styles": [style(r) for r in LA]},
    ],
}

SPACE = [("space-1", 4, "Icon-to-label gap, dot-to-word gap, the tightest inline gap."),
         ("space-2", 8, "Chip gap, gap between a stat and its caption, button icon gap."),
         ("space-3", 12, "Island panel inner padding (12, so 16-radius inner cards stay concentric in the 28 shape); row vertical padding."),
         ("space-4", 16, "Island card padding; button horizontal padding; gaps inside a card."),
         ("space-6", 24, "Web card padding; gap between dashboard cards; iPhone card padding is 20 (space-4 + space-1)."),
         ("space-8", 32, "Gap between a card's header block and its body; hero strip padding."),
         ("space-12", 48, "Gap between dashboard sections (minimum)."),
         ("space-18", 72, "Gap between dashboard sections (maximum); top of page above the hero strip.")]
RADIUS = [("radius-xs", 6, "Chips, inline tags, keycaps, sample dots that are squares (phone)."),
          ("radius-sm", 10, "Buttons, inputs, popover items, contact-sheet frames at thumbnail size."),
          ("radius-md", 16, "Cards on the web and inside the island; the correction popover."),
          ("radius-lg", 22, "The composer, iPhone sheets, toasts."),
          ("radius-xl", 28, "The island's open shape (with space-3 padding, inner 16 cards stay concentric)."),
          ("radius-pill", 9999, "Pills, verdict pills, streak badge, the round send button, status capsules.")]
SHADOW = [("shadow-float", {"dark": "0 12px 32px -8px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.08)",
                            "light": "0 12px 32px -8px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.06)"},
           "The only web shadow: floating layers only (popovers, the correction popover, toasts, the drawer, the lightbox). Cards use hairline instead."),
          ("shadow-island", {"dark": "0 2px 6px rgba(0,0,0,0.5), 0 12px 24px rgba(0,0,0,0.35)",
                             "light": "0 2px 6px rgba(0,0,0,0.5), 0 12px 24px rgba(0,0,0,0.35)"},
           "The open island and its alerts (SwiftUI: black .5 r6 y2 plus black .35 r24 y12). None when collapsed; the web NotchIsland preview uses the same value.")]
DUR = [("dur-micro", "120ms", "Press scale, toggles, colour changes, focus ring."),
       ("dur-small", "180ms", "Tooltips, popovers, chip select, hover lift."),
       ("dur-medium", "260ms", "Toasts, card expand, content blur-in, stagger items (40ms apart, max 6)."),
       ("dur-drawer", "420ms", "Setup drawer and sheets (with ease-drawer); exit at 0.65x."),
       ("dur-reveal", "900ms", "Verdict count-up and meter fill (scaleX) in the verdict reveal."),
       ("dur-celebrate", "1600ms", "Pinch's celebrate clip and the claw confetti burst; the whole moment is skippable and capped at 2.6s.")]
EASE = [("ease-out", "cubic-bezier(0.23,1,0.32,1)", "Default for every enter and exit: fades, popovers, blur-ins. Never use ease-in on UI."),
        ("ease-drawer", "cubic-bezier(0.32,0.72,0,1)", "Drawer and sheet slides."),
        ("ease-in-out", "cubic-bezier(0.65,0,0.35,1)", "Things moving while on screen (FLIP of a section, ring arc start without a spring).")]
# The six shared springs (Motion.md), simulated from SwiftUI spring(duration, bounce) physics
SPRING = [
    ("micro", 0.25, 0.0, 376, "linear(0,.086,.252,.419,.569,.688,.777,.844,.891,.925,.949,.965,.977,.984,.989,.993,.995,.997,.998,.999,1)",
     "Toggles, chip select, sample dot recolour."),
    ("snappy", 0.35, 0.15, 484, "linear(0,.077,.234,.413,.573,.705,.808,.882,.932,.966,.986,.997,1.003,1.005,1.006,1.005,1.004,1.003,1.002,1.002,1)",
     "Popovers, island wings, inner island content, composer send, digit tickers."),
    ("smooth", 0.5, 0.0, 686, "linear(0,.072,.217,.373,.517,.637,.731,.805,.86,.899,.929,.95,.965,.976,.983,.988,.992,.994,.996,.997,1)",
     "Every close and collapse, sheets, ring start. No bounce into the notch."),
    ("island", 0.45, 0.2, 619, "linear(0,.076,.237,.419,.588,.727,.832,.908,.957,.988,1.005,1.012,1.015,1.014,1.012,1.009,1.006,1.004,1.003,1.001,1)",
     "Notch to panel open (island bloom)."),
    ("bouncy", 0.5, 0.3, 720, "linear(0,.047,.155,.296,.443,.584,.707,.81,.892,.952,.995,1.022,1.038,1.044,1.045,1.042,1.036,1.029,1.023,1.017,1.011,1.007,1.004,1.001,1,.999,.998,.998,1)",
     "Nudge alert drop, verdict pill, streak bump, sample dot pop."),
    ("celebrate", 0.6, 0.4, 1003, "linear(0,.062,.207,.387,.572,.738,.871,.972,1.039,1.077,1.093,1.092,1.082,1.066,1.048,1.032,1.017,1.007,.999,.994,.992,.991,.992,.993,.995,.996,.998,.999,1)",
     "Pinch only (hop, clap). Never on UI structure."),
]
spring_tokens = []
for n, d, b, ms, lin_s, use in SPRING:
    assert len(lin_s) <= 200, n
    spring_tokens.append({"name": f"spring-{n}", "value": lin_s,
                          "usage": f"{use} SwiftUI .spring(duration: {d}, bounce: {b}). CSS: transition: transform var(--spring-{n}-dur) var(--spring-{n}); falls back to ease-out where linear() is unsupported, and to ease under reduced motion."})
    spring_tokens.append({"name": f"spring-{n}-dur", "value": f"{ms}ms",
                          "usage": f"Settle time of spring-{n} ({ms}ms, longer than the perceived {int(d*1000)}ms). Pair it with spring-{n}; 150ms under reduced motion."})

tokens = {
    "name": "Alibi",
    "version": 1,
    "meta": {"source": "docs/design"},
    "color": {"themes": [{"id": "dark", "name": "Dark"}, {"id": "light", "name": "Light"}], "tokens": color_tokens},
    "type": type_block,
    "spacing": {"note": "4-based ladder. Card padding 24 web, 20 iPhone, 16 island; sections 48-72 apart; dashboard column max 880px, prose 62ch.",
                "tokens": [{"name": n, "value": f"{v}px", "usage": u} for n, v, u in SPACE]},
    "radius": {"note": "One concentric ladder: inner radius = outer radius minus padding.",
               "tokens": [{"name": n, "value": f"{v}px", "usage": u} for n, v, u in RADIUS]},
    "shadow": {"note": "Hairlines over shadows. Two shadows exist, both for floating layers.",
               "tokens": [{"name": n, "value": v, "usage": u} for n, v, u in SHADOW]},
    "duration": {"note": "Exits run at 0.65x the enter duration with no bounce. Frequent actions get the shortest values.",
                 "tokens": [{"name": n, "value": v, "usage": u} for n, v, u in DUR]},
    "easing": {"note": "ease-out for enter/exit, ease-in-out for on-screen movement, linear only for time.",
               "tokens": [{"name": n, "value": v, "usage": u} for n, v, u in EASE]},
    "spring": {"note": "Six springs shared by web, island and iPhone (Motion.md). CSS values are linear() simulations of the SwiftUI springs; -dur is the settle time.",
               "tokens": spring_tokens},
}

# ---------------------------------------------------------------- validation
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
seen = set()
for fam, blk in tokens.items():
    if fam in ("name", "version", "meta", "type"): continue
    for t in blk["tokens"]:
        assert NAME.match(t["name"]), t["name"]
        assert t["name"] not in seen, t["name"]; seen.add(t["name"])
        assert len(t["usage"]) <= 1000, (t["name"], len(t["usage"]))
        if fam not in ("color", "shadow"):
            assert re.fullmatch(r"[A-Za-z0-9 #%(),./+_-]{1,200}", t["value"]), t["name"]
for g in type_block["groups"]:
    for s in g["styles"]:
        assert NAME.match(s["name"]) and len(s["sample"]) <= 200
for fam in type_block["families"].values():
    assert len(fam) <= 200 and not re.search(r"[;{}<>\\()]", fam)
CVAL = re.compile(r"^(#[0-9A-Fa-f]{6}|rgba\(\d+,\d+,\d+,[0-9.]+\)|\{[a-z0-9-]+\})$")
for n, d, l, *_ in C:
    assert CVAL.match(d) and CVAL.match(l), n

# ---------------------------------------------------------------- tokens.json
os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
with open(OUT_JSON, "w") as f:
    json.dump(tokens, f, indent=2, ensure_ascii=False); f.write("\n")

# ---------------------------------------------------------------- tokens.css
def cssval(v):
    return f"var(--{v[1:-1]})" if v.startswith("{") else v

def color_block(theme, indent="  "):
    lines = []
    groups = [("Surfaces", 0, 6), ("Ink", 6, 10), ("Lines", 10, 12), ("Accent", 12, 19), ("Green ramp (mascot, data)", 19, 26),
              ("Status: always paired with a shape", 26, 41), ("Verdict aliases", 41, 44), ("Pinch (exempt from the 5% green budget)", 44, 54), ("Celebration bloom", 54, 55)]
    for title, a, b in groups:
        lines.append(f"{indent}/* {title} */")
        for n, d, l, *_ in C[a:b]:
            v = d if theme == "dark" else l
            lines.append(f"{indent}--{n}: {cssval(v)};")
    return lines
assert C[54][0] == "bloom" and C[41][0] == "done" and C[26][0] == "on-task" and C[19][0] == "green-100"

def shadow_lines(theme, indent="  "):
    return [f"{indent}--{n}: {v[theme]};" for n, v, _ in SHADOW]

TYPEDOC = {r[0]: r for r in WEB}
css = []
css.append('@import url("https://fonts.googleapis.com/css2?family=Onest:wght@400..700&display=swap");')
css.append("""
/* Alibi tokens · docs/design
   Same names as docs/design/system/project/tokens.json. Dark is the primary theme.
   Theme switch: <html data-theme="dark|light">; with no attribute, dark unless the OS prefers light.
   Type: all sans. SF Pro on Apple, Onest for everyone else; Rounded for big numerals; mono for keycaps/IDs only.
   Colour: #76B900 is the accent (<=5% of chrome); text on any green or red fill is #000; status colours always ship with a shape. */
""")
css.append(':root,\n[data-theme="dark"] {\n  color-scheme: dark;')
css += color_block("dark")
css += ["  /* Depth */"] + shadow_lines("dark")
css += ["  /* Dark text gets air: +0.05 line-height, +0.01em tracking */", "  --body-lh: 1.6;", "  --body-ls: 0.01em;", "}"]
css.append('\n[data-theme="light"] {\n  color-scheme: light;')
light_lines = color_block("light") + ["  /* Depth */"] + shadow_lines("light") + ["  --body-lh: 1.55;", "  --body-ls: 0em;"]
css += light_lines + ["}"]
css.append('\n@media (prefers-color-scheme: light) {\n  :root:not([data-theme="dark"]) {\n    color-scheme: light;')
css += ["  " + x for x in light_lines] + ["  }", "}"]

css.append("\n:root {\n  /* Type families */")
css += [f"  --font-sans: {SANS};", f"  --font-rounded: {ROUNDED};", f"  --font-mono: {MONO};"]
css.append("  /* Spacing: 4 · 8 · 12 · 16 · 24 · 32 · 48 · 72 */")
css += [f"  --{n}: {v}px;" for n, v, _ in SPACE]
css.append("  /* Radius: one concentric ladder */")
css += [f"  --{n}: {v}px;" for n, v, _ in RADIUS]
css.append("  /* Durations (exit = 0.65 x enter) */")
css += [f"  --{n}: {v};" for n, v, _ in DUR]
css.append("  /* Easing */")
css += [f"  --{n}: {v};" for n, v, _ in EASE]
css.append("  /* Springs: ease-out until linear() is known to work (gated below; a var() would hide an invalid linear()) */")
for n, d, b, ms, *_ in SPRING:
    css.append(f"  --spring-{n}: var(--ease-out);")
    css.append(f"  --spring-{n}-dur: {ms}ms; /* SwiftUI .spring(duration: {d}, bounce: {b}) */")
css.append("}")
css.append("\n/* Springs (Motion.md), simulated from the same physics as the SwiftUI springs. */")
css.append("@supports (animation-timing-function: linear(0, 1)) {\n  :root {")
for n, *_r in SPRING:
    css.append(f"    --spring-{n}: {_r[3]};")
css.append("  }\n}")

css.append("\n/* Web type styles (.t-<style>). Sizes in px; sentence case everywhere. */")
for n, fam, size, lh, w, ls, tnum, sample, usage in WEB:
    lhv = "var(--body-lh)" if n == "body" else f"{lh}"
    lsv = "var(--body-ls)" if n == "body" else ls
    rule = [f".t-{n} {{", f"  font-family: var(--font-{fam});", f"  font-size: {size}px;", f"  line-height: {lhv};",
            f"  font-weight: {w};", f"  letter-spacing: {lsv};"]
    if tnum: rule.append("  font-variant-numeric: tabular-nums lining-nums;")
    if n in ("h1", "h2", "h3"): rule.append("  text-wrap: balance;")
    if n in ("voice", "body"): rule.append("  text-wrap: pretty;")
    rule.append("}")
    css.append("\n".join(rule))

css.append("""
/* Base */
body {
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: var(--body-lh);
  letter-spacing: var(--body-ls);
  font-kerning: normal;
  font-optical-sizing: auto;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}
h1, h2, h3 { text-wrap: balance; }
p, li, blockquote, figcaption { text-wrap: pretty; }
[data-num], .num, time { font-variant-numeric: tabular-nums lining-nums; }
:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
}
::selection {
  background: var(--accent-wash);
  color: var(--ink);
}

/* Reduced motion: fewer and gentler, not zero (Motion.md).
   Opacity and colour feedback stay (150ms); transforms, bounces and decorative loops go. */
@media (prefers-reduced-motion: reduce) {
  :root {
    --spring-micro: ease;
    --spring-snappy: ease;
    --spring-smooth: ease;
    --spring-island: ease;
    --spring-bouncy: ease;
    --spring-celebrate: ease;
    --spring-micro-dur: 150ms;
    --spring-snappy-dur: 150ms;
    --spring-smooth-dur: 150ms;
    --spring-island-dur: 150ms;
    --spring-bouncy-dur: 150ms;
    --spring-celebrate-dur: 150ms;
    --dur-drawer: 260ms;
    --dur-reveal: 150ms;
    --dur-celebrate: 150ms;
  }
  *, *::before, *::after {
    animation-duration: 1ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
  }
  .moves, [data-moves] { transform: none !important; }
  .confetti, .al-confetti, .shake, .al-shake { display: none !important; }
}
""")
os.makedirs(os.path.dirname(OUT_CSS), exist_ok=True)
with open(OUT_CSS, "w") as f:
    f.write("\n".join(css))

print(f"wrote {OUT_JSON} ({len(color_tokens)} colours) and {OUT_CSS}")
print(f"{len(report)} contrast pairs checked; failures: {len(failures)}")
for x in failures: print("  FAIL", x)
mins = {}
for t, n, g, r, need in report:
    k = (t, n); mins[k] = min(mins.get(k, (99, ""))[0], r), need
for (t, n), (r, need) in sorted(mins.items(), key=lambda x: x[1][0] - x[1][1])[:12]:
    print(f"  tightest {t:5} {n:16} {r:.2f} (needs {need})")
