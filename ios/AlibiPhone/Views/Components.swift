// The iPhone's building blocks on the shared Alibi tokens (Views/Shared/Theme.swift): cards, labels, buttons, status
// marks, the verdict pill, the streak badge, the ring timer and the meter. The phone is dark, so every view
// reads `Alibi.ui` (the dark palette). Status is always colour plus shape plus word.
import SwiftUI

extension Alibi {
    /// The phone's palette. Dark is the reference design.
    static let ui = Palette.dark
}

// MARK: Surfaces

/// A `surface-1` card: 20pt padding (the iPhone inset), `radius-md`, a hairline edge and no shadow.
struct Card<Content: View>: View {
    var padding: CGFloat = Alibi.Space.cardPhone
    var spacing: CGFloat = Alibi.Space.s3
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: spacing) { content }
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: Alibi.Radius.md, style: .continuous).fill(Alibi.ui.surface1))
            .overlay(RoundedRectangle(cornerRadius: Alibi.Radius.md, style: .continuous)
                .strokeBorder(Alibi.ui.hairline, lineWidth: 1))
    }
}

/// A small sentence-case label above a group ("Start on your Mac"). Never uppercase.
struct SectionLabel: View {
    let text: String
    var body: some View {
        Text(text).font(Alibi.Fonts.iosCaption).foregroundStyle(Alibi.ui.ink2)
            .accessibilityAddTraits(.isHeader)
    }
}

/// A section title in `ios-headline` ("Last 7 days").
struct SectionTitle: View {
    let text: String
    var body: some View {
        Text(text).font(Alibi.Fonts.iosHeadline).foregroundStyle(Alibi.ui.ink)
            .accessibilityAddTraits(.isHeader)
    }
}

/// The large title plus its one-line subtitle, as on every phone board.
struct ScreenHeader<Trailing: View>: View {
    let title: String
    var subtitle: Text? = nil
    @ViewBuilder var trailing: Trailing
    var body: some View {
        HStack(alignment: .bottom, spacing: Alibi.Space.s3) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(Alibi.Fonts.iosLargeTitle).foregroundStyle(Alibi.ui.ink)
                    .accessibilityAddTraits(.isHeader)
                if let subtitle {
                    subtitle.font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2).monospacedDigit()
                }
            }
            Spacer(minLength: 0)
            trailing
        }
    }
}

extension ScreenHeader where Trailing == EmptyView {
    init(title: String, subtitle: Text? = nil) {
        self.init(title: title, subtitle: subtitle) { EmptyView() }
    }
}

// MARK: Buttons (10pt radius, 50pt tall, press scale 0.97 on spring-micro)

struct PrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var enabled
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Alibi.Fonts.iosHeadline).foregroundStyle(Alibi.ui.onAccent)
            .frame(maxWidth: .infinity, minHeight: 50).padding(.horizontal, Alibi.Space.s4)
            .background(RoundedRectangle(cornerRadius: Alibi.Radius.sm, style: .continuous)
                .fill(configuration.isPressed ? Alibi.ui.accentPress : Alibi.ui.accent))
            .opacity(enabled ? 1 : 0.4)
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .alibiAnimation(Alibi.Motion.micro, value: configuration.isPressed)
    }
}

struct SecondaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var enabled
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Alibi.Fonts.iosHeadline).foregroundStyle(Alibi.ui.ink)
            .frame(maxWidth: .infinity, minHeight: 50).padding(.horizontal, Alibi.Space.s4)
            .background(RoundedRectangle(cornerRadius: Alibi.Radius.sm, style: .continuous)
                .fill(configuration.isPressed ? Alibi.ui.surface3 : Alibi.ui.surface2))
            .overlay(RoundedRectangle(cornerRadius: Alibi.Radius.sm, style: .continuous)
                .strokeBorder(Alibi.ui.hairline, lineWidth: 1))
            .opacity(enabled ? 1 : 0.4)
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .alibiAnimation(Alibi.Motion.micro, value: configuration.isPressed)
    }
}

/// Text-only action ("Review permissions"): `ink-2`, at least 44pt tall.
struct QuietButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Alibi.Fonts.iosSubheadline.weight(.semibold)).foregroundStyle(Alibi.ui.ink2)
            .frame(minHeight: 44).contentShape(Rectangle())
            .opacity(configuration.isPressed ? 0.6 : 1)
            .alibiAnimation(Alibi.Motion.micro, value: configuration.isPressed)
    }
}

// MARK: Status marks

/// One of the five evidence labels, drawn as its shape: ● on task, ○ idle, ■ phone, hatched ● off task, dashed ○ away.
struct StatusDot: View {
    let label: String
    var size: CGFloat = 10
    var showWord = false

    static func word(_ label: String) -> String {
        switch label {
        case "on_task": "On task"
        case "idle": "Idle"
        case "phone": "Phone"
        case "off_task": "Off task"
        case "absent": "Away"
        default: label.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    static func ink(_ label: String) -> Color {
        switch label {
        case "on_task": Alibi.ui.onTaskInk
        case "idle": Alibi.ui.idleInk
        case "phone", "off_task": Alibi.ui.warnInk
        default: Alibi.ui.absentInk
        }
    }

    var body: some View {
        HStack(spacing: Alibi.Space.s2) {
            mark.frame(width: size, height: size)
            if showWord {
                Text(Self.word(label)).font(Alibi.Fonts.iosFootnote.weight(.medium)).foregroundStyle(Alibi.ui.ink2)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Self.word(label))
    }

    @ViewBuilder private var mark: some View {
        switch label {
        case "on_task": Circle().fill(Alibi.ui.onTask)
        case "idle": Circle().strokeBorder(Alibi.ui.idle, lineWidth: 2)
        case "phone": RoundedRectangle(cornerRadius: size * 0.22, style: .continuous).fill(Alibi.ui.phone)
        case "off_task":
            Circle().fill(Alibi.ui.offTask)
                .overlay(Hatch().stroke(Alibi.ui.bg.opacity(0.7), lineWidth: max(1, size / 8)).clipShape(Circle()))
        default: Circle().strokeBorder(Alibi.ui.absent, style: StrokeStyle(lineWidth: 1.5, dash: [2, 2]))
        }
    }
}

/// 45° hatch lines for the off-task mark.
private struct Hatch: Shape {
    func path(in r: CGRect) -> Path {
        var p = Path()
        let step = r.width / 3
        var x = -r.height
        while x < r.width {
            p.move(to: CGPoint(x: r.minX + x, y: r.maxY))
            p.addLine(to: CGPoint(x: r.minX + x + r.height, y: r.minY))
            x += step
        }
        return p
    }
}

/// The legacy 3-tone dot used by the Streams list (Permissions, Screen Time, Home report a `Tone`).
struct Dot: View {
    let tone: Tone
    var size: CGFloat = 8
    var body: some View {
        StatusDot(label: tone.label, size: size)
    }
}

// MARK: Verdict pill

enum VerdictKind: String {
    case done, partial, slacked

    init?(_ raw: String?) {
        switch raw {
        case "done": self = .done
        case "partial", "partly": self = .partial
        case "slacked": self = .slacked
        default: return nil
        }
    }
    var word: String { switch self { case .done: "Done"; case .partial: "Partly"; case .slacked: "Slacked" } }
    var ink: Color { switch self { case .done: Alibi.ui.accentInk; case .partial: Alibi.ui.partialInk; case .slacked: Alibi.ui.warnInk } }
    var wash: Color { switch self { case .done: Alibi.ui.accentWash; case .partial: Alibi.ui.partialWash; case .slacked: Alibi.ui.warnWash } }
    var fill: Color { switch self { case .done: Alibi.ui.done; case .partial: Alibi.ui.partly; case .slacked: Alibi.ui.slacked } }
    var clip: PinchClip { switch self { case .done: .celebrate; case .partial: .partial; case .slacked: .supportive } }
}

/// ✓ Done · ◐ Partly · ✕ Slacked, on its 10% wash. 28pt tall, pill radius.
struct VerdictPill: View {
    let verdict: VerdictKind
    var ratio: Double? = nil
    var body: some View {
        HStack(spacing: Alibi.Space.s1) {
            VerdictGlyph(verdict: verdict).frame(width: 14, height: 14)
            Text(verdict.word)
            if let ratio {
                Text("· \(Int((ratio * 100).rounded()))%").fontWeight(.medium)
            }
        }
        .font(Alibi.Fonts.iosFootnote.weight(.semibold)).monospacedDigit()
        .foregroundStyle(verdict.ink)
        .padding(.leading, Alibi.Space.s2).padding(.trailing, Alibi.Space.s3)
        .frame(minHeight: 28)
        .background(Capsule().fill(verdict.wash))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Verdict: \(verdict.word.lowercased())\(ratio.map { ", \(Int(($0 * 100).rounded()))%" } ?? "")")
    }
}

/// The verdict's own glyph: a tick, a half-filled disc, or a cross.
struct VerdictGlyph: View {
    let verdict: VerdictKind
    var body: some View {
        GeometryReader { g in
            let s = min(g.size.width, g.size.height)
            switch verdict {
            case .done:
                Path { p in
                    p.move(to: CGPoint(x: s * 0.2, y: s * 0.52))
                    p.addLine(to: CGPoint(x: s * 0.42, y: s * 0.74))
                    p.addLine(to: CGPoint(x: s * 0.82, y: s * 0.3))
                }.stroke(verdict.ink, style: StrokeStyle(lineWidth: s * 0.15, lineCap: .round, lineJoin: .round))
            case .partial:
                ZStack {
                    Circle().strokeBorder(verdict.ink, lineWidth: s * 0.12)
                    Rectangle().fill(verdict.ink).frame(width: s / 2, height: s).offset(x: -s / 4).clipShape(Circle())
                }.frame(width: s * 0.8, height: s * 0.8).position(x: s / 2, y: s / 2)
            case .slacked:
                Path { p in
                    p.move(to: CGPoint(x: s * 0.25, y: s * 0.25)); p.addLine(to: CGPoint(x: s * 0.75, y: s * 0.75))
                    p.move(to: CGPoint(x: s * 0.75, y: s * 0.25)); p.addLine(to: CGPoint(x: s * 0.25, y: s * 0.75))
                }.stroke(verdict.ink, style: StrokeStyle(lineWidth: s * 0.15, lineCap: .round))
            }
        }
        .accessibilityHidden(true)
    }
}

// MARK: Streak badge (claw glyph, never a flame)

struct ClawGlyph: Shape {
    // Alibi.Icon "claw", drawn on its 24 grid.
    func path(in r: CGRect) -> Path {
        let k = min(r.width, r.height) / 24
        func pt(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: r.minX + x * k, y: r.minY + y * k) }
        var p = Path()
        p.move(to: pt(7.5, 20.5))
        p.addCurve(to: pt(6.9, 9.6), control1: pt(4.8, 17.8), control2: pt(4.6, 13.2))
        p.addCurve(to: pt(14.2, 3.5), control1: pt(8.6, 7), control2: pt(11.1, 4.9))
        p.addCurve(to: pt(12.5, 10.7), control1: pt(14.4, 6.1), control2: pt(13.8, 8.6))
        p.addCurve(to: pt(20.8, 10.4), control1: pt(15.0, 9.7), control2: pt(17.9, 9.6))
        p.addCurve(to: pt(12.8, 16.9), control1: pt(19.5, 13.9), control2: pt(16.4, 16.3))
        p.addCurve(to: pt(10.1, 20.5), control1: pt(11.4, 17.2), control2: pt(10.4, 18.5))
        p.closeSubpath()
        return p
    }
}

struct StreakBadge: View {
    let days: Int
    var freezes: Int? = nil
    var body: some View {
        HStack(spacing: Alibi.Space.s2) {
            ClawGlyph().stroke(Alibi.ui.accentInk, style: StrokeStyle(lineWidth: 1.5, lineCap: .round, lineJoin: .round))
                .frame(width: 16, height: 16)
            Text("\(days) \(days == 1 ? "day" : "days")").contentTransition(.numericText())
            if let freezes, freezes > 0 {
                Text("·").foregroundStyle(Alibi.ui.ink3)
                Text("\(freezes) \(freezes == 1 ? "freeze" : "freezes") left").fontWeight(.medium).foregroundStyle(Alibi.ui.ink2)
            }
        }
        .font(Alibi.Fonts.iosFootnote.weight(.semibold)).monospacedDigit().foregroundStyle(Alibi.ui.ink)
        .lineLimit(1)
        .padding(.leading, 10).padding(.trailing, Alibi.Space.s3)
        .frame(minHeight: 32)
        .background(Capsule().fill(Alibi.ui.surface2))
        .overlay(Capsule().strokeBorder(Alibi.ui.hairline, lineWidth: 1))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Streak: \(days) \(days == 1 ? "day" : "days")")
    }
}

// MARK: Stat

/// Label over a big rounded number over a sub line: "On task / 92% / Last seen 19:26".
struct Stat<Sub: View>: View {
    let label: String
    let value: String
    @ViewBuilder var sub: Sub
    var body: some View {
        VStack(alignment: .leading, spacing: Alibi.Space.s2) {
            Text(label).font(Alibi.Fonts.iosCaption).foregroundStyle(Alibi.ui.ink2)
            Text(value).font(Alibi.Fonts.iosStat).foregroundStyle(Alibi.ui.ink)
                .contentTransition(.numericText()).lineLimit(1).minimumScaleFactor(0.7)
            sub
        }
        .accessibilityElement(children: .combine)
    }
}

// MARK: Ring timer

/// The live ring: `accent` arc on a 12% ink track with round caps, ticking once a second between `start` and `end`.
/// The countdown inside is `Text(timerInterval:countsDown:)`, so it ticks with zero updates.
struct RingTimer: View {
    let start: Date
    let end: Date
    var size: CGFloat = 176
    var tint: Color = Alibi.ui.accent
    var caption = "left"
    @ScaledMetric(relativeTo: .largeTitle) private var valueSize: CGFloat = 42
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var drawn = false

    var body: some View {
        let stroke = max(3, (size / 16).rounded())
        ZStack {
            Circle().stroke(Alibi.ui.ink.opacity(0.12), lineWidth: stroke)
            TimelineView(.periodic(from: .now, by: 1)) { ctx in
                Circle()
                    .trim(from: 0, to: drawn ? progress(at: ctx.date) : 0)
                    .stroke(tint, style: StrokeStyle(lineWidth: stroke, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .alibiAnimation(Alibi.Motion.smooth, value: drawn)
            }
            VStack(spacing: Alibi.Space.s1) {
                Text(timerInterval: start...max(start, end), countsDown: true)
                    .font(.system(size: min(valueSize, size * 0.3), weight: .semibold, design: .rounded).monospacedDigit())
                    .foregroundStyle(Alibi.ui.ink)
                    .multilineTextAlignment(.center)
                    .lineLimit(1).minimumScaleFactor(0.5)
                Text(caption).font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2).lineLimit(1)
            }
            .padding(.horizontal, stroke * 2)
        }
        .frame(width: size, height: size)
        .onAppear { if reduceMotion { drawn = true } else { DispatchQueue.main.async { drawn = true } } }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Time left")
    }

    private func progress(at now: Date) -> CGFloat {
        let total = end.timeIntervalSince(start)
        guard total > 0 else { return 1 }
        return CGFloat(min(1, max(0, now.timeIntervalSince(start) / total)))
    }
}

// MARK: Meter

/// On-task meter: 8pt track, fill grows with scaleX (never width), ticks at 0.4 and 0.7. Tone follows the ratio.
struct Meter: View {
    let value: Double
    var reveal = true
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var shown = false

    private var fill: Color { value >= 0.7 ? Alibi.ui.done : value >= 0.4 ? Alibi.ui.partly : Alibi.ui.slacked }

    var body: some View {
        GeometryReader { g in
            ZStack(alignment: .leading) {
                Capsule().fill(Alibi.ui.ink.opacity(0.12))
                Capsule().fill(fill)
                    .scaleEffect(x: shown ? max(0.001, min(1, value)) : 0.001, y: 1, anchor: .leading)
                ForEach([0.4, 0.7], id: \.self) { t in
                    Rectangle().fill(Alibi.ui.bg.opacity(0.8)).frame(width: 2).offset(x: g.size.width * t - 1)
                }
            }
        }
        .frame(height: 8)
        .clipShape(Capsule())
        .onAppear {
            guard reveal, !reduceMotion else { shown = true; return }
            withAnimation(Alibi.Motion.easeOut(Alibi.Motion.durReveal).delay(0.42)) { shown = true }
        }
        .accessibilityElement()
        .accessibilityLabel("On task \(Int((value * 100).rounded()))%")
    }
}

// MARK: Keycap

struct Kbd: View {
    let keys: String
    var body: some View {
        Text(keys).font(Alibi.Fonts.mono(13)).foregroundStyle(Alibi.ui.ink)
            .padding(.horizontal, 6).frame(minHeight: 22)
            .background(RoundedRectangle(cornerRadius: Alibi.Radius.xs, style: .continuous).fill(Alibi.ui.surface2))
            .overlay(RoundedRectangle(cornerRadius: Alibi.Radius.xs, style: .continuous)
                .strokeBorder(Alibi.ui.hairlineStrong, lineWidth: 1))
    }
}

// MARK: Entrance

/// "Content in" for a screen's sections: opacity plus 8 → 0pt rise, 40ms stagger, capped at 6. Reduced motion: fade.
struct Rise: ViewModifier {
    let index: Int
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var shown = false
    func body(content: Content) -> some View {
        content
            .opacity(shown ? 1 : 0)
            .offset(y: shown || reduceMotion ? 0 : 8)
            .onAppear {
                let anim = reduceMotion ? Alibi.Motion.reduced
                    : Alibi.Motion.easeOut(Alibi.Motion.durMedium).delay(Double(min(index, 5)) * Alibi.Motion.stagger)
                withAnimation(anim) { shown = true }
            }
    }
}

extension View {
    func rise(_ index: Int) -> some View { modifier(Rise(index: index)) }
}
