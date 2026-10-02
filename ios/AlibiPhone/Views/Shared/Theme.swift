// Alibi design tokens for SwiftUI: shared by the Mac notch island and the iPhone app.
// Mirrors docs/design/system/project/tokens.json (token names camelCased). SwiftUI only, so
// both targets can compile it. Dark is the primary theme; the island is always `Palette.dark`.
// Type is all sans: SF Pro for text, SF Pro Rounded + monospacedDigit for numerals.
import SwiftUI

enum Alibi {
    // MARK: Colour
    struct Palette: Sendable {
        /// Surfaces
        let bg, surface1, surface2, surface3, island, scrim: Color
        /// Ink
        let ink, ink2, ink3, inkInverse: Color
        /// Lines
        let hairline, hairlineStrong: Color
        /// Accent
        let accent, accentHover, accentPress, onAccent, accentInk, accentWash, focusRing: Color
        /// Green ramp
        let green100, green200, green300, green500, green600, green700, green800: Color
        /// Status (always paired with a shape)
        let onTask, onTaskInk, partial, partialInk, partialWash, warn, warnInk, warnWash: Color
        let onWarn, idle, idleInk, phone, offTask, absent, absentInk: Color
        /// Verdict aliases
        let done, partly, slacked: Color
        /// Pinch
        let pinchBody, pinchBelly, pinchShade, pinchOutline, pinchEye, pinchShine, pinchBlush, pinchSpark: Color
        let pinchLens, pinchLensGlow: Color
        /// Bloom
        let bloom: Color

        static let dark = Palette(
            bg: .init(hex: 0x000000), surface1: .init(hex: 0x1A1A1A), surface2: .init(hex: 0x262626), surface3: .init(hex: 0x333333),
            island: .init(hex: 0x000000), scrim: .init(hex: 0x000000, alpha: 0.64),
            ink: .init(hex: 0xF2F2F2), ink2: .init(hex: 0xA6A6A6), ink3: .init(hex: 0x8F8F8F), inkInverse: .init(hex: 0x000000),
            hairline: .init(hex: 0xFFFFFF, alpha: 0.08), hairlineStrong: .init(hex: 0xFFFFFF, alpha: 0.38),
            accent: .init(hex: 0x76B900), accentHover: .init(hex: 0x85C900), accentPress: .init(hex: 0x6AA800), onAccent: .init(hex: 0x000000),
            accentInk: .init(hex: 0x8FD400), accentWash: .init(hex: 0x1C2A06), focusRing: .init(hex: 0x76B900),
            green100: .init(hex: 0xD0FCA9), green200: .init(hex: 0xAAF059), green300: .init(hex: 0x97DC42), green500: .init(hex: 0x76B900),
            green600: .init(hex: 0x588C05), green700: .init(hex: 0x477200), green800: .init(hex: 0x365900),
            onTask: .init(hex: 0x76B900), onTaskInk: .init(hex: 0x8FD400), partial: .init(hex: 0xF2A900), partialInk: .init(hex: 0xFFC233),
            partialWash: .init(hex: 0x2E2203), warn: .init(hex: 0xE5484D), warnInk: .init(hex: 0xFF7A7E), warnWash: .init(hex: 0x3A1414),
            onWarn: .init(hex: 0x000000), idle: .init(hex: 0xF2A900), idleInk: .init(hex: 0xFFC233), phone: .init(hex: 0xE5484D),
            offTask: .init(hex: 0xE5484D), absent: .init(hex: 0xA6A6A6), absentInk: .init(hex: 0xA6A6A6),
            done: .init(hex: 0x76B900), partly: .init(hex: 0xF2A900), slacked: .init(hex: 0xE5484D),
            pinchBody: .init(hex: 0x76B900), pinchBelly: .init(hex: 0x97DC42), pinchShade: .init(hex: 0x588C05), pinchOutline: .init(hex: 0x8FD400),
            pinchEye: .init(hex: 0x000000), pinchShine: .init(hex: 0xFFFFFF), pinchBlush: .init(hex: 0xF2A900, alpha: 0.4), pinchSpark: .init(hex: 0xAAF059),
            pinchLens: .init(hex: 0xD7D7D7), pinchLensGlow: .init(hex: 0xAAF059, alpha: 0.55),
            bloom: .init(hex: 0x76B900, alpha: 0.35)
        )
        static let light = Palette(
            bg: .init(hex: 0xF2F2F2), surface1: .init(hex: 0xFFFFFF), surface2: .init(hex: 0xF7F7F7), surface3: .init(hex: 0xEBEBEB),
            island: .init(hex: 0x000000), scrim: .init(hex: 0x000000, alpha: 0.32),
            ink: .init(hex: 0x1A1A1A), ink2: .init(hex: 0x5E5E5E), ink3: .init(hex: 0x6E6E6E), inkInverse: .init(hex: 0xFFFFFF),
            hairline: .init(hex: 0x000000, alpha: 0.08), hairlineStrong: .init(hex: 0x000000, alpha: 0.46),
            accent: .init(hex: 0x76B900), accentHover: .init(hex: 0x6AA800), accentPress: .init(hex: 0x5E9900), onAccent: .init(hex: 0x000000),
            accentInk: .init(hex: 0x477200), accentWash: .init(hex: 0xEAF4D6), focusRing: .init(hex: 0x588C05),
            green100: .init(hex: 0xD0FCA9), green200: .init(hex: 0xAAF059), green300: .init(hex: 0x97DC42), green500: .init(hex: 0x76B900),
            green600: .init(hex: 0x588C05), green700: .init(hex: 0x477200), green800: .init(hex: 0x365900),
            onTask: .init(hex: 0x588C05), onTaskInk: .init(hex: 0x477200), partial: .init(hex: 0xA17005), partialInk: .init(hex: 0x8A5F00),
            partialWash: .init(hex: 0xFDF1D6), warn: .init(hex: 0xE5484D), warnInk: .init(hex: 0xC4161C), warnWash: .init(hex: 0xFBE3E3),
            onWarn: .init(hex: 0x000000), idle: .init(hex: 0xA17005), idleInk: .init(hex: 0x8A5F00), phone: .init(hex: 0xE5484D),
            offTask: .init(hex: 0xE5484D), absent: .init(hex: 0x767676), absentInk: .init(hex: 0x5E5E5E),
            done: .init(hex: 0x588C05), partly: .init(hex: 0xA17005), slacked: .init(hex: 0xE5484D),
            pinchBody: .init(hex: 0x76B900), pinchBelly: .init(hex: 0x97DC42), pinchShade: .init(hex: 0x588C05), pinchOutline: .init(hex: 0x365900),
            pinchEye: .init(hex: 0x000000), pinchShine: .init(hex: 0xFFFFFF), pinchBlush: .init(hex: 0xF2A900, alpha: 0.4), pinchSpark: .init(hex: 0x588C05),
            pinchLens: .init(hex: 0x5E5E5E), pinchLensGlow: .init(hex: 0x76B900, alpha: 0.4),
            bloom: .init(hex: 0x76B900, alpha: 0.28)
        )
        static func of(_ scheme: ColorScheme) -> Palette { scheme == .light ? light : dark }
    }

    // MARK: Type (pt). Pair the wordmark with `.tracking(Fonts.wordmarkTracking)`.
    enum Fonts {
        static func sans(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
            .system(size: size, weight: weight)
        }
        /// Numerals: SF Pro Rounded with tabular (monospaced) digits so timers never jitter.
        static func rounded(_ size: CGFloat, _ weight: Font.Weight = .semibold) -> Font {
            .system(size: size, weight: weight, design: .rounded).monospacedDigit()
        }
        /// Keycaps and IDs only.
        static func mono(_ size: CGFloat = 12, _ weight: Font.Weight = .medium) -> Font {
            .system(size: size, weight: weight, design: .monospaced)
        }

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
    }

    // MARK: Spacing (4 · 8 · 12 · 16 · 24 · 32 · 48 · 72)
    enum Space {
        static let s1: CGFloat = 4, s2: CGFloat = 8, s3: CGFloat = 12, s4: CGFloat = 16
        static let s6: CGFloat = 24, s8: CGFloat = 32, s12: CGFloat = 48, s18: CGFloat = 72
        /// Card padding per surface: island 16, iPhone 20.
        static let cardIsland: CGFloat = 16, cardPhone: CGFloat = 20
    }

    // MARK: Radius (concentric: inner = outer - padding). Use `style: .continuous`.
    enum Radius {
        static let xs: CGFloat = 6, sm: CGFloat = 10, md: CGFloat = 16
        static let lg: CGFloat = 22, xl: CGFloat = 28, pill: CGFloat = 9999
    }

    // MARK: Motion: the six shared springs.
    enum Motion {
        static let micro = Animation.spring(duration: 0.25, bounce: 0)        // toggles, dot recolour
        static let snappy = Animation.spring(duration: 0.35, bounce: 0.15)    // wings, inner content, tickers
        static let smooth = Animation.spring(duration: 0.5, bounce: 0)        // every close, sheets, ring start
        static let island = Animation.spring(duration: 0.45, bounce: 0.2)     // notch to panel open
        static let bouncy = Animation.spring(duration: 0.5, bounce: 0.3)      // alert drop, verdict pill, streak
        static let celebrate = Animation.spring(duration: 0.6, bounce: 0.4)   // Pinch only
        /// The island opened from the keyboard (⌥⌘A): the shape only, a touch quicker than `island`.
        static let key = Animation.spring(duration: 0.3, bounce: 0.2)
        /// What every animation becomes under Reduce Motion: a short fade-friendly ease.
        static let reduced = Animation.easeOut(duration: 0.15)

        static let durMicro = 0.12, durSmall = 0.18, durMedium = 0.26
        static let durDrawer = 0.42, durReveal = 0.9, durCelebrate = 1.6
        /// Exits run at 0.65x the enter duration, never with bounce.
        static let exitFactor = 0.65
        static let stagger = 0.04, islandStagger = 0.03

        static func easeOut(_ duration: Double) -> Animation { .timingCurve(0.23, 1, 0.32, 1, duration: duration) }
        static func drawer(_ duration: Double = durDrawer) -> Animation { .timingCurve(0.32, 0.72, 0, 1, duration: duration) }
        static func exit(_ enter: Double) -> Animation { easeOut(enter * exitFactor) }
        static func adaptive(_ animation: Animation, reduceMotion: Bool) -> Animation {
            reduceMotion ? reduced : animation
        }
    }

    /// Applies an Alibi animation that collapses to `Motion.reduced` under Reduce Motion.
    struct AnimationModifier<Value: Equatable>: ViewModifier {
        @Environment(\.accessibilityReduceMotion) private var reduceMotion
        let animation: Animation
        let value: Value
        func body(content: Content) -> some View {
            content.animation(Motion.adaptive(animation, reduceMotion: reduceMotion), value: value)
        }
    }
}

extension View {
    /// `.alibiAnimation(Alibi.Motion.snappy, value: minutes)`: respects Reduce Motion.
    func alibiAnimation<Value: Equatable>(_ animation: Animation, value: Value) -> some View {
        modifier(Alibi.AnimationModifier(animation: animation, value: value))
    }
}

extension Color {
    /// `Color(hex: 0x76B900)` or `Color(hex: 0x000000, alpha: 0.64)`, in sRGB.
    init(hex: UInt32, alpha: Double = 1) {
        self.init(.sRGB, red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255, opacity: alpha)
    }
    /// "#76B900", "76B900" or "#00000066" (RRGGBBAA); nil when malformed.
    init?(hex string: String) {
        let s = string.hasPrefix("#") ? String(string.dropFirst()) : string
        guard s.count == 6 || s.count == 8, let v = UInt32(s, radix: 16) else { return nil }
        self = s.count == 8 ? Color(hex: v >> 8, alpha: Double(v & 0xFF) / 255) : Color(hex: v)
    }
}
