#!/usr/bin/env python3
"""Writes docs/design/tokens/Theme.swift from the same colour table as build_tokens.py."""
import os, re, runpy
HERE = os.path.dirname(os.path.abspath(__file__))
ns = runpy.run_path(f"{HERE}/build_tokens.py", run_name="tokens")  # rebuilds json/css too
C, resolve, parse = ns["C"], ns["resolve"], ns["parse"]
OUT = "/Users/harrishayyanar/Documents/nvidia_habits/docs/design/tokens/Theme.swift"

def camel(n): p = n.split("-"); return p[0] + "".join(x.capitalize() for x in p[1:])
def sw(v, theme):
    if v.startswith("{"): v = resolve(v[1:-1], theme)
    rgb, a = parse(v)
    hx = "0x" + "".join("%02X" % round(x * 255) for x in rgb)
    return f".init(hex: {hx})" if a == 1 else f".init(hex: {hx}, alpha: {a:g})"

GROUPS = [("Surfaces", 0, 6), ("Ink", 6, 10), ("Lines", 10, 12), ("Accent", 12, 19), ("Green ramp", 19, 26),
          ("Status (always paired with a shape)", 26, 41), ("Verdict aliases", 41, 44), ("Pinch", 44, 54), ("Bloom", 54, 55)]

decl = []
for title, a, b in GROUPS:
    names = [camel(r[0]) for r in C[a:b]]
    decl.append(f"        /// {title}")
    for i in range(0, len(names), 8):
        decl.append("        let " + ", ".join(names[i:i + 8]) + ": Color")

def inst(theme):
    out = []
    for title, a, b in GROUPS:
        args = [f"{camel(r[0])}: {sw(r[1] if theme == 'dark' else r[2], theme)}" for r in C[a:b]]
        for i in range(0, len(args), 4):
            out.append("            " + ", ".join(args[i:i + 4]) + ",")
    out[-1] = out[-1].rstrip(",")
    return out

swift = f'''// Alibi design tokens for SwiftUI: shared by the Mac notch island and the iPhone app.
// Mirrors docs/design/system/project/tokens.json (token names camelCased). SwiftUI only, so
// both targets can compile it. Dark is the primary theme; the island is always `Palette.dark`.
// Type is all sans: SF Pro for text, SF Pro Rounded + monospacedDigit for numerals.
import SwiftUI

enum Alibi {{
    // MARK: Colour
    struct Palette: Sendable {{
{chr(10).join(decl)}

        static let dark = Palette(
{chr(10).join(inst("dark"))}
        )
        static let light = Palette(
{chr(10).join(inst("light"))}
        )
        static func of(_ scheme: ColorScheme) -> Palette {{ scheme == .light ? light : dark }}
    }}

    // MARK: Type (pt). Pair the wordmark with `.tracking(Fonts.wordmarkTracking)`.
    enum Fonts {{
        static func sans(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {{
            .system(size: size, weight: weight)
        }}
        /// Numerals: SF Pro Rounded with tabular (monospaced) digits so timers never jitter.
        static func rounded(_ size: CGFloat, _ weight: Font.Weight = .semibold) -> Font {{
            .system(size: size, weight: weight, design: .rounded).monospacedDigit()
        }}
        /// Keycaps and IDs only.
        static func mono(_ size: CGFloat = 12, _ weight: Font.Weight = .medium) -> Font {{
            .system(size: size, weight: weight, design: .monospaced)
        }}

        // Mac island: fixed sizes (macOS has no Dynamic Type). Floor is 11 pt.
        static let islandWordmark = sans(12, .heavy)      // "ALIBI", tracking 1.6
        static let wordmarkTracking: CGFloat = 1.6
        static let islandWing = rounded(13)               // + .contentTransition(.numericText(countsDown: true))
        static let islandTimer = rounded(34)              // + .tracking(islandTimerTracking)
        static let islandTimerTracking: CGFloat = -0.5
        static let islandTitle = sans(17, .semibold)
        static let islandVoice = sans(15, .medium)        // Pinch's lines; only the noun in warnInk
        static let islandBody = sans(14)                  // + .lineSpacing(3)
        static let islandSecondary = sans(12)             // white at 60%
        static let islandFloor = sans(11, .medium)

        // iPhone: Dynamic Type styles, sentence case.
        static let iosLargeTitle = Font.largeTitle.weight(.semibold)
        static let iosTitle = Font.title2.weight(.semibold)
        static let iosTitle3 = Font.title3.weight(.semibold)
        static let iosHeadline = Font.headline
        static let iosBody = Font.body
        static let iosSubheadline = Font.subheadline
        static let iosFootnote = Font.footnote
        static let iosCaption = Font.caption.weight(.semibold)
        static let iosStat = Font.system(.title, design: .rounded, weight: .semibold).monospacedDigit()
        static let iosTimer = rounded(56)

        // Live Activity and Dynamic Island: sans only, fixed frames around timers.
        static let laTitle = sans(15, .semibold)
        static let laTimer = rounded(34)
        static let laCompact = rounded(14)                // fixed 40 pt frame
        static let laExpandedLeading = sans(13, .medium)
        static let laExpandedCenter = sans(17, .semibold)
        static let laExpandedTrailing = rounded(22)
    }}

    // MARK: Spacing (4 · 8 · 12 · 16 · 24 · 32 · 48 · 72)
    enum Space {{
        static let s1: CGFloat = 4, s2: CGFloat = 8, s3: CGFloat = 12, s4: CGFloat = 16
        static let s6: CGFloat = 24, s8: CGFloat = 32, s12: CGFloat = 48, s18: CGFloat = 72
        /// Card padding per surface: island 16, iPhone 20.
        static let cardIsland: CGFloat = 16, cardPhone: CGFloat = 20
    }}

    // MARK: Radius (concentric: inner = outer - padding). Use `style: .continuous`.
    enum Radius {{
        static let xs: CGFloat = 6, sm: CGFloat = 10, md: CGFloat = 16
        static let lg: CGFloat = 22, xl: CGFloat = 28, pill: CGFloat = 9999
    }}

    // MARK: Motion: the six shared springs (research/04).
    enum Motion {{
        static let micro = Animation.spring(duration: 0.25, bounce: 0)        // toggles, dot recolour
        static let snappy = Animation.spring(duration: 0.35, bounce: 0.15)    // wings, inner content, tickers
        static let smooth = Animation.spring(duration: 0.5, bounce: 0)        // every close, sheets, ring start
        static let island = Animation.spring(duration: 0.45, bounce: 0.2)     // notch to panel open
        static let bouncy = Animation.spring(duration: 0.5, bounce: 0.3)      // alert drop, verdict pill, streak
        static let celebrate = Animation.spring(duration: 0.6, bounce: 0.4)   // Pinch only
        /// What every animation becomes under Reduce Motion: a short fade-friendly ease.
        static let reduced = Animation.easeOut(duration: 0.15)

        static let durMicro = 0.12, durSmall = 0.18, durMedium = 0.26
        static let durDrawer = 0.42, durReveal = 0.9, durCelebrate = 1.6
        /// Exits run at 0.65x the enter duration, never with bounce.
        static let exitFactor = 0.65
        static let stagger = 0.04, islandStagger = 0.03

        static func easeOut(_ duration: Double) -> Animation {{ .timingCurve(0.23, 1, 0.32, 1, duration: duration) }}
        static func drawer(_ duration: Double = durDrawer) -> Animation {{ .timingCurve(0.32, 0.72, 0, 1, duration: duration) }}
        static func exit(_ enter: Double) -> Animation {{ easeOut(enter * exitFactor) }}
        static func adaptive(_ animation: Animation, reduceMotion: Bool) -> Animation {{
            reduceMotion ? reduced : animation
        }}
    }}

    /// Applies an Alibi animation that collapses to `Motion.reduced` under Reduce Motion.
    struct AnimationModifier<Value: Equatable>: ViewModifier {{
        @Environment(\\.accessibilityReduceMotion) private var reduceMotion
        let animation: Animation
        let value: Value
        func body(content: Content) -> some View {{
            content.animation(Motion.adaptive(animation, reduceMotion: reduceMotion), value: value)
        }}
    }}
}}

extension View {{
    /// `.alibiAnimation(Alibi.Motion.snappy, value: minutes)`: respects Reduce Motion.
    func alibiAnimation<Value: Equatable>(_ animation: Animation, value: Value) -> some View {{
        modifier(Alibi.AnimationModifier(animation: animation, value: value))
    }}
}}

extension Color {{
    /// `Color(hex: 0x76B900)` or `Color(hex: 0x000000, alpha: 0.64)`, in sRGB.
    init(hex: UInt32, alpha: Double = 1) {{
        self.init(.sRGB, red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255, opacity: alpha)
    }}
    /// "#76B900", "76B900" or "#00000066" (RRGGBBAA); nil when malformed.
    init?(hex string: String) {{
        let s = string.hasPrefix("#") ? String(string.dropFirst()) : string
        guard s.count == 6 || s.count == 8, let v = UInt32(s, radix: 16) else {{ return nil }}
        self = s.count == 8 ? Color(hex: v >> 8, alpha: Double(v & 0xFF) / 255) : Color(hex: v)
    }}
}}
'''
with open(OUT, "w") as f: f.write(swift)
print(OUT, swift.count("\n"), "lines")
