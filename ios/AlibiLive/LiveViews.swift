// The Live Activity's views: Lock Screen banner, Dynamic Island (compact, minimal, expanded) and the end state.
// Plain SwiftUI with no WidgetKit types, so a macOS ImageRenderer harness (LivePNG.swift) can draw them to PNG.
// The system ignores animation here: the timer and the time bar tick by themselves (Text/ProgressView(timerInterval:)),
// Pinch is a still pose per status, and every other change lands as a system blur-replace when the app pushes an update.
import SwiftUI

private let P = Alibi.Palette.dark

/// The PNG harness sets this: ImageRenderer can't draw timer-driven progress views, so draw the fraction at render time.
private struct LiveSnapshotKey: EnvironmentKey { static let defaultValue = false }
extension EnvironmentValues {
    var liveSnapshot: Bool {
        get { self[LiveSnapshotKey.self] }
        set { self[LiveSnapshotKey.self] = newValue }
    }
}

// MARK: Status → look

/// Everything a status decides: ink, Pinch pose, glyph, verdict word, lines.
struct LiveLook {
    let state: AlibiLiveAttributes.ContentState
    var reduced = false                                  // Always-On (isLuminanceReduced): outlines, no glow
    var stale = false                                    // past the session end with no update from the app

    var status: String { state.status }
    var isVerdict: Bool { state.isVerdict }
    var onBreak: Bool { status == "break" }
    var drifting: Bool { status == "drift" }
    var away: Bool { drifting && state.cause == "absent" }

    /// What the big timer counts down to: the break's end while on a break, else the session's.
    var timerRange: ClosedRange<Date> {
        let end = onBreak ? (state.breakEnd ?? state.end) : state.end
        return state.start...max(state.start, end)
    }
    var sessionRange: ClosedRange<Date> { state.start...max(state.start.addingTimeInterval(1), state.end) }

    /// Ink for the big timer (or the verdict word).
    var timerInk: Color {
        switch status {
        case "break", "partial": return P.partialInk
        case "done": return P.accentInk
        case "slacked": return P.warnInk
        default: return P.ink
        }
    }
    /// Ink for the compact trailing value.
    var compactInk: Color {
        switch status {
        case "drift": return away ? P.absentInk : P.warnInk
        case "slacked": return P.warnInk
        case "break", "partial": return P.partialInk
        default: return P.accentInk
        }
    }
    /// Fill for the bars: the session keeps its green while drifting (the dot and the noun carry the drift).
    var barInk: Color {
        if reduced { return P.ink3 }
        switch status {
        case "break", "partial": return P.partial
        case "slacked": return P.slacked
        case "done": return P.done
        default: return P.accent
        }
    }
    /// The minimal ring: `accent` on task, `partial` on a break, `warn` while drifting.
    var ringInk: Color {
        switch status {
        case "break", "partial": return P.partial
        case "drift": return away ? P.absent : P.warn
        case "slacked": return P.warn
        default: return P.accent
        }
    }
    var ratio: Double { Double(max(0, min(100, state.onTask ?? 0))) / 100 }

    var verdictWord: String {
        switch status { case "done": return "Done"; case "partial": return "Partly"; case "slacked": return "Slacked"; default: return "" }
    }
    /// SF Symbol for the compact slot while it isn't counting down (nil → the timer, or the drawn half-disc for partly).
    var compactSymbol: String? {
        switch status {
        case "drift":
            switch state.cause {
            case "off_task": return "laptopcomputer"
            case "absent": return "figure.walk"
            default: return "iphone"
            }
        case "break": return "cup.and.saucer.fill"
        case "done": return "checkmark"
        case "slacked": return "xmark"
        default: return nil
        }
    }
    /// The status mark before the line while live: colour plus shape.
    var dot: LiveStatusDot.Kind {
        if onBreak { return .idle }
        guard drifting else { return .onTask }
        switch state.cause {
        case "off_task": return .offTask
        case "absent": return .absent
        case "idle": return .idle
        default: return .phone
        }
    }

    /// Pinch's still pose: a resting mood, or a clip's key frame (clips.json `key`, in ms).
    var pinchPose: PinchPose {
        var pose: PinchPose
        switch state.pose {
        case "sideeye": pose = PinchView.pose(mood: .focused, clip: .sideeye, ms: 720)
        case "sleepy": pose = PinchView.pose(mood: .sleepy, clip: nil, ms: 0)
        case "celebrate": pose = PinchView.pose(mood: .idle, clip: .celebrate, ms: 760)
        case "partial": pose = PinchView.pose(mood: .idle, clip: .partial, ms: 380)
        case "supportive": pose = PinchView.pose(mood: .idle, clip: .supportive, ms: 460)
        case "idle": pose = PinchView.pose(mood: .idle, clip: nil, ms: 0)
        default: pose = PinchView.pose(mood: .focused, clip: nil, ms: 0)
        }
        // The lens tells the truth: it glows only while the camera samples, so never after the session or when dimmed.
        if reduced || isVerdict || stale { pose.lensLit = false }
        return pose
    }

    /// The line under the bar. Drifting names its cause first ("Phone · 3 min"); that noun alone takes the status ink.
    var line: String { stale && !isVerdict ? "Time's up · open Alibi for the verdict" : state.line }
    var lineNoun: String? {
        guard drifting, !stale, let r = state.line.range(of: " · ") else { return nil }
        return String(state.line[..<r.lowerBound])
    }
    var lineRest: String {
        guard lineNoun != nil, let r = state.line.range(of: " · ") else { return line }
        return String(state.line[r.lowerBound...])
    }
    var nounInk: Color { away ? P.absentInk : P.warnInk }
    /// Expanded bottom line: the centre already says "On task 92%", so keep only "Last seen 18:04".
    var expandedLine: String {
        guard !stale, status == "on", let r = state.line.range(of: " · last seen ") else { return line }
        return "Last seen " + state.line[r.upperBound...]
    }
    /// Expanded centre line.
    var centerLine: String {
        if onBreak { return "On a break" }
        guard let p = state.onTask else { return "First look soon" }
        return "On task \(p)%"
    }

    var accessibility: String {
        if isVerdict { return "\(verdictWord), \(state.line)" }
        if drifting { return state.line }
        if onBreak { return "on a break" }
        return state.onTask.map { "on task \($0) percent" } ?? "watching"
    }
}

// MARK: Small parts

/// Status is colour plus shape: ● on task, ○ idle, ■ phone, ▨ off task, ◌ absent.
struct LiveStatusDot: View {
    enum Kind { case onTask, idle, phone, offTask, absent }
    var kind: Kind
    var size: CGFloat = 8
    var body: some View {
        Group {
            switch kind {
            case .onTask: Circle().fill(P.onTask)
            case .idle: Circle().strokeBorder(P.idle, lineWidth: 2)
            case .phone: RoundedRectangle(cornerRadius: size * 0.25, style: .continuous).fill(P.phone)
            case .offTask:
                ZStack {
                    LiveHatch(gap: size / 3).stroke(P.offTask, lineWidth: 1).clipShape(Circle())
                    Circle().strokeBorder(P.offTask, lineWidth: 1.5)
                }
            case .absent: Circle().strokeBorder(P.absent, style: StrokeStyle(lineWidth: 1.5, dash: [2, 1.5]))
            }
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }
}

/// 45° hatch lines for the off-task mark.
struct LiveHatch: Shape {
    var gap: CGFloat
    func path(in r: CGRect) -> Path {
        var p = Path()
        var x = r.minX - r.height
        while x < r.maxX {
            p.move(to: CGPoint(x: x, y: r.maxY)); p.addLine(to: CGPoint(x: x + r.height, y: r.minY))
            x += max(1.5, gap)
        }
        return p
    }
}

/// ◐ for "Partly": a ring with its left half filled.
struct LiveHalfDisc: View {
    var size: CGFloat
    var line: CGFloat = 2
    var body: some View {
        ZStack {
            Circle().strokeBorder(lineWidth: line)
            Circle().trim(from: 0.25, to: 0.75).fill()   // trim starts at 3 o'clock, clockwise: 0.25…0.75 is the left half
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }
}

/// The verdict glyph at a given type size, in the current foreground colour.
struct LiveVerdictGlyph: View {
    var status: String
    var size: CGFloat
    var body: some View {
        if status == "partial" {
            LiveHalfDisc(size: (size * 0.75).rounded(), line: max(1.5, (size / 11).rounded()))
        } else {
            Image(systemName: status == "done" ? "checkmark" : "xmark")
                .font(.system(size: (size * 0.8).rounded(), weight: .bold))
        }
    }
}

/// A 6 pt bar on `surface-2`, radius 3. `fraction` nil → the session's time, ticking by itself.
struct LiveBar: View {
    var look: LiveLook
    var fraction: Double?
    @Environment(\.liveSnapshot) private var snapshot

    var body: some View {
        Group {
            if let f = fraction ?? (snapshot ? Self.elapsed(look.sessionRange) : nil) {
                GeometryReader { g in
                    ZStack(alignment: .leading) {
                        Capsule().fill(P.surface2)
                        if f > 0 {
                            let w = max(6, g.size.width * min(1, f))
                            if look.reduced { Capsule().strokeBorder(look.barInk, lineWidth: 1).frame(width: w) }
                            else { Capsule().fill(look.barInk).frame(width: w) }
                        }
                    }
                }
                .frame(height: 6)
            } else {
                // The system's linear bar is 4 pt; scale it to the 6 pt spec. It advances every second with no updates.
                ProgressView(timerInterval: look.sessionRange, countsDown: false) { EmptyView() } currentValueLabel: { EmptyView() }
                    .progressViewStyle(.linear)
                    .tint(look.barInk)
                    .scaleEffect(x: 1, y: 1.5, anchor: .center)
                    .frame(height: 6)
            }
        }
        .accessibilityHidden(true)
    }

    static func elapsed(_ r: ClosedRange<Date>) -> Double {
        let total = r.upperBound.timeIntervalSince(r.lowerBound)
        return total > 0 ? max(0, min(1, Date().timeIntervalSince(r.lowerBound) / total)) : 1
    }
}

/// The line under the bar: dot + "On task 92% · last seen 18:04", or "Phone · 3 min" with only the noun in status ink.
struct LiveLine: View {
    var look: LiveLook
    var expanded = false
    var body: some View {
        HStack(spacing: 6) {
            if !look.isVerdict && !look.stale { LiveStatusDot(kind: look.dot) }
            Group {
                if let noun = look.lineNoun {
                    Text(noun).foregroundStyle(look.nounInk).fontWeight(.semibold) + Text(look.lineRest)
                } else {
                    Text(expanded ? look.expandedLine : look.line)
                }
            }
            .font(Alibi.Fonts.sans(13))
            .monospacedDigit()
            .foregroundStyle(P.ink2)
            .contentTransition(.numericText())
            .lineLimit(1)
        }
        .frame(minHeight: 18)
    }
}

/// Countdown that ticks on its own, in a fixed frame so "0:00:00" never reflows the row.
struct LiveTimer: View {
    var look: LiveLook
    var font: Font
    var width: CGFloat
    var body: some View {
        Text(timerInterval: look.timerRange, countsDown: true)
            .font(font)
            .monospacedDigit()
            .foregroundStyle(look.timerInk)
            .multilineTextAlignment(.trailing)
            .lineLimit(1)
            .minimumScaleFactor(0.7)
            .frame(width: width, alignment: .trailing)
    }
}

/// The verdict word with its glyph, in place of the timer at the end.
struct LiveVerdictWord: View {
    var look: LiveLook
    var size: CGFloat
    var body: some View {
        HStack(spacing: size >= 20 ? 6 : 4) {
            LiveVerdictGlyph(status: look.status, size: size)
            Text(look.verdictWord).font(Alibi.Fonts.rounded(size))
        }
        .foregroundStyle(look.timerInk)
        .lineLimit(1)
        .fixedSize()
    }
}

// MARK: Lock Screen

/// Row 1 (44 pt): Pinch 32 · "Alibi" over the habit · the timer. Row 2: the time bar. Row 3: dot + line.
struct LiveLockScreenView: View {
    var habit: String
    var state: AlibiLiveAttributes.ContentState
    var stale = false
    @Environment(\.isLuminanceReduced) private var reduced

    var body: some View {
        let look = LiveLook(state: state, reduced: reduced, stale: stale)
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                PinchFigure(pose: look.pinchPose, size: 32)
                VStack(alignment: .leading, spacing: 0) {
                    Text("Alibi").font(Alibi.Fonts.sans(11, .semibold)).foregroundStyle(P.ink3)
                    Text(habit).font(Alibi.Fonts.laTitle).foregroundStyle(P.ink).lineLimit(1)
                }
                Spacer(minLength: 8)
                if look.isVerdict {
                    LiveVerdictWord(look: look, size: 22)
                } else {
                    LiveTimer(look: look, font: Alibi.Fonts.laTimer, width: 104)
                }
            }
            .frame(height: 44)
            LiveBar(look: look, fraction: look.isVerdict ? look.ratio : nil)
            LiveLine(look: look)
        }
        .padding(.leading, 14)
        .padding(.trailing, 16)
        .padding(.vertical, 14)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Alibi: \(habit), \(look.accessibility)")
    }
}

// MARK: Dynamic Island

/// Compact leading: the 20 pt Pinch silhouette.
struct LiveCompactLeading: View {
    var state: AlibiLiveAttributes.ContentState
    var stale = false
    @Environment(\.isLuminanceReduced) private var reduced
    var body: some View {
        PinchFigure(pose: LiveLook(state: state, reduced: reduced, stale: stale).pinchPose, size: 20)
            .accessibilityLabel("Alibi")
    }
}

/// Compact trailing: the countdown in a fixed 40 pt frame; a glyph and a short value while drifting or on a break.
struct LiveCompactTrailing: View {
    var state: AlibiLiveAttributes.ContentState
    var body: some View {
        let look = LiveLook(state: state)
        Group {
            if look.isVerdict {
                Group {
                    if look.status == "partial" { LiveHalfDisc(size: 12, line: 1.5) }
                    else { Image(systemName: look.compactSymbol ?? "checkmark").font(.system(size: 13, weight: .bold)) }
                }
                .accessibilityLabel(look.verdictWord)
            } else if let sym = look.compactSymbol, let badge = state.badge {
                HStack(spacing: 2) {
                    Image(systemName: sym).font(.system(size: 12, weight: .semibold))
                    Text(badge).font(Alibi.Fonts.laCompact)
                }
                .lineLimit(1)
                .minimumScaleFactor(0.8)
            } else {
                Text(timerInterval: look.timerRange, countsDown: true)
                    .font(Alibi.Fonts.laCompact)
                    .multilineTextAlignment(.trailing)
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)
            }
        }
        .foregroundStyle(look.compactInk)
        .frame(width: 40, alignment: .trailing)
    }
}

/// Minimal: a ring that runs out by itself, with a 10 pt Pinch head inside.
struct LiveMinimal: View {
    var state: AlibiLiveAttributes.ContentState
    @Environment(\.isLuminanceReduced) private var reduced
    @Environment(\.liveSnapshot) private var snapshot
    var body: some View {
        let look = LiveLook(state: state, reduced: reduced)
        Group {
            if look.isVerdict {
                LiveVerdictGlyph(status: look.status, size: 16).foregroundStyle(look.timerInk)
            } else if snapshot {
                ZStack {
                    Circle().stroke(P.surface2, lineWidth: 2.5)
                    Circle().trim(from: 0, to: 1 - LiveBar.elapsed(look.sessionRange))
                        .stroke(look.ringInk, style: StrokeStyle(lineWidth: 2.5, lineCap: .round))
                        .rotationEffect(.degrees(-90))
                    PinchFigure(pose: look.pinchPose, size: 10)
                }
                .padding(5)
            } else {
                ProgressView(timerInterval: look.sessionRange, countsDown: true) {
                    EmptyView()
                } currentValueLabel: {
                    PinchFigure(pose: look.pinchPose, size: 10)
                }
                .progressViewStyle(.circular)
                .tint(look.ringInk)
            }
        }
        .accessibilityLabel("Alibi, \(look.accessibility)")
    }
}

/// Expanded leading: the 44 pt Pinch.
struct LiveExpandedLeading: View {
    var state: AlibiLiveAttributes.ContentState
    var stale = false
    @Environment(\.isLuminanceReduced) private var reduced
    var body: some View {
        PinchFigure(pose: LiveLook(state: state, reduced: reduced, stale: stale).pinchPose, size: 44)
            .padding(.leading, 4)
    }
}

/// Expanded trailing: the countdown (22 pt rounded), or the verdict word.
struct LiveExpandedTrailing: View {
    var state: AlibiLiveAttributes.ContentState
    var body: some View {
        let look = LiveLook(state: state)
        Group {
            if look.isVerdict { LiveVerdictWord(look: look, size: 17) }
            else { LiveTimer(look: look, font: Alibi.Fonts.laExpandedTrailing, width: 72) }
        }
        .frame(height: 30)
        .padding(.trailing, 4)
    }
}

/// Expanded centre: the habit over "On task 92%".
struct LiveExpandedCenter: View {
    var habit: String
    var state: AlibiLiveAttributes.ContentState
    var body: some View {
        let look = LiveLook(state: state)
        VStack(spacing: 0) {
            Text(habit).font(Alibi.Fonts.laExpandedCenter).foregroundStyle(P.ink).lineLimit(1)
            Text(look.centerLine).font(Alibi.Fonts.sans(13, .medium)).monospacedDigit()
                .foregroundStyle(P.ink2).lineLimit(1)
                .contentTransition(.numericText())
        }
    }
}

/// Expanded bottom: the on-task bar (fills to the on-task %), then the drift or last-seen line.
struct LiveExpandedBottom: View {
    var state: AlibiLiveAttributes.ContentState
    var stale = false
    @Environment(\.isLuminanceReduced) private var reduced
    var body: some View {
        let look = LiveLook(state: state, reduced: reduced, stale: stale)
        VStack(alignment: .leading, spacing: 10) {
            LiveBar(look: look, fraction: look.ratio)
            LiveLine(look: look, expanded: true)
        }
        .padding(.horizontal, 8)
        .padding(.top, 8)
    }
}

// MARK: Samples (previews and the PNG harness)

extension AlibiLiveAttributes {
    static let preview = AlibiLiveAttributes(habit: "Drawing")
}

extension AlibiLiveAttributes.ContentState {
    /// One state per status, as the controller builds it. `now` anchors a 25-minute session that started 6 min ago.
    static func sample(_ status: String, now: Date = Date()) -> Self {
        let start = now.addingTimeInterval(-6 * 60 - 18), end = start.addingTimeInterval(25 * 60)
        switch status {
        case "drift":
            return .init(start: start, end: end, onTask: 84, status: "drift", line: "Phone · 3 min", pose: "sideeye",
                         badge: "3m", cause: "phone")
        case "break":
            return .init(start: start, end: end, onTask: 92, status: "break", line: "On a break · back 19:31",
                         pose: "sleepy", badge: "5m", breakEnd: now.addingTimeInterval(252))
        case "watching":
            return .init(start: now.addingTimeInterval(-20), end: now.addingTimeInterval(25 * 60 - 20), onTask: nil,
                         status: "on", line: "Watching since 19:20", pose: "focused")
        case "done":
            return .init(start: start, end: end, onTask: 92, status: "done", line: "23 of 25 min on task", pose: "celebrate")
        case "partial":
            return .init(start: start, end: end, onTask: 68, status: "partial", line: "17 of 25 min on task", pose: "partial")
        case "slacked":
            return .init(start: start, end: end, onTask: 24, status: "slacked", line: "6 of 25 min on task", pose: "supportive")
        default:
            return .init(start: start, end: end, onTask: 92, status: "on", line: "On task 92% · last seen 19:26", pose: "focused")
        }
    }
}
