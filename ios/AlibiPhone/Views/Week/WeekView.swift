// Week: what you claimed this week against what Alibi saw, per habit (the Mac's `week`, Monday to now), then the
// last 7 days of exercise from this phone's Health totals. Without a `week` (Mac out of reach, or nothing claimed yet)
// the first card says when it fills in.
import Charts
import SwiftUI

struct WeekView: View {
    @ObservedObject var mirror: MirrorClient
    @StateObject private var snap = Snapshot.shared

    private static let dayFmt: DateFormatter = {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_GB"); f.dateFormat = "EEE d MMM"; return f
    }()

    var body: some View {
        let s = mirror.session
        // A week with nothing claimed yet reads the same as no week: nothing to compare.
        let week = s?.week.flatMap { $0.claimed > 0 || $0.seen > 0 ? $0 : nil }
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                ScreenHeader(title: "Week", subtitle: Text(range(from: week?.start))) {
                    if let streak = s?.streak_days, streak > 0 { StreakBadge(days: streak).padding(.bottom, 2) }
                }
                .rise(0)

                PinchLineRow(text: week.map(Self.headline)
                             ?? (s == nil ? "Nothing to compare until your Mac answers." : line(s)))
                    .padding(.top, 14).rise(1)

                Group {
                    if let week {
                        ClaimedSeen(week: week)
                    } else {
                        ClaimedSeenEmpty(text: s == nil ? "Minutes claimed and seen, per habit, from your Mac."
                                                        : "This fills in after your first session this week.")
                    }
                }
                .padding(.top, Alibi.Space.s4)
                .rise(2)

                ActivityCard(days: snap.days).padding(.top, Alibi.Space.s3).rise(3)
            }
            .padding(.horizontal, Alibi.Space.cardPhone)
            .padding(.top, Alibi.Space.s2)
            .padding(.bottom, Alibi.Space.s8)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .scrollIndicators(.hidden)
        #if DEBUG
        // Screenshots of the Health card: `-AlibiScroll bottom` opens the tab scrolled to the end.
        .defaultScrollAnchor(UserDefaults.standard.string(forKey: "AlibiScroll") == "bottom" ? .bottom : nil)
        #endif
        .background(Alibi.ui.bg.ignoresSafeArea())
    }

    /// The Mac's week (Monday to today) when it sent one, else the last 7 days the Health card covers.
    private func range(from start: Date?) -> String {
        let end = Date()
        let from = start ?? Calendar.current.date(byAdding: .day, value: -6, to: end) ?? end
        if Calendar.current.isDate(from, inSameDayAs: end) { return "Today, \(Self.dayFmt.string(from: end))" }
        return "\(Self.dayFmt.string(from: from)) to \(Self.dayFmt.string(from: end))"
    }

    /// Pinch's weekly line, facts first: "You claimed 5h 52m this week. I saw 4h 29m. Building carried the week."
    static func headline(_ w: PhoneSession.Week) -> String {
        let claimed = w.claimed, seen = w.seen
        var out = claimed > 0 ? "You claimed \(spoken(claimed)) this week. " : ""
        out += claimed > 0 && seen >= claimed ? "I saw all of it."
            : seen == 0 ? "I saw none of it."
            : claimed > 0 ? "I saw \(spoken(seen))." : "I saw \(spoken(seen)) this week."
        let seenHabits = (w.habits ?? []).filter { ($0.seen_min ?? 0) > 0 }
        if seenHabits.count > 1, let top = seenHabits.max(by: { ($0.seen_min ?? 0) < ($1.seen_min ?? 0) }) {
            out += " \(name(top)) carried the week."
        }
        return out
    }

    /// Pinch says minutes; totals of an hour or more read "2h 10m". No-break spaces keep a total on one line.
    static func spoken(_ m: Int) -> String {
        (m < 60 ? "\(m) \(m == 1 ? "minute" : "minutes")" : TodayFmt.total(Double(m)))
            .replacingOccurrences(of: " ", with: "\u{00A0}")
    }

    static func name(_ h: PhoneSession.Week.Habit) -> String { h.label ?? TodayFmt.habit(h.habit) }

    private func line(_ s: PhoneSession?) -> String {
        let streak = s?.streak_days ?? 0
        switch streak {
        case 0: return "Nothing to compare yet. Finish a session on your Mac."
        case 1: return "Day 1. Every streak starts here."
        case 2..<7: return "\(streak) days in a row. That's how it starts."
        case 7..<14: return "A week of alibis that checked out."
        default: return "\(streak) days. Showing up is starting to look like you."
        }
    }
}

/// Pinch's 20pt avatar beside one line in Pinch's voice (`Alibi.PinchLine`, mood `reading`).
private struct PinchLineRow: View {
    let text: String
    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            PinchView(mood: .reading, size: 20).accessibilityHidden(true).padding(.top, 2)
            Text(text).font(Alibi.Fonts.iosBody.weight(.medium)).foregroundStyle(Alibi.ui.ink).monospacedDigit()
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

/// A card title: 15pt semibold.
private struct CardTitle: View {
    let text: String
    var body: some View {
        Text(text).font(Alibi.Fonts.iosSubheadline.weight(.semibold)).foregroundStyle(Alibi.ui.ink)
            .accessibilityAddTraits(.isHeader)
    }
}

// MARK: Claimed vs seen

private struct ClaimedSeen: View {
    let week: PhoneSession.Week

    private struct Row { let name: String; let claimed: Int; let seen: Int; let status: String? }

    var body: some View {
        let all = week.habits ?? []
        var rows = all.filter { ($0.claimed_min ?? 0) > 0 || ($0.seen_min ?? 0) > 0 }
            .map { Row(name: WeekView.name($0), claimed: $0.claimed_min ?? 0, seen: $0.seen_min ?? 0, status: $0.status) }
        // An older Mac with totals only: one row for the whole week.
        if rows.isEmpty { rows = [Row(name: "All habits", claimed: week.claimed, seen: week.seen, status: nil)] }
        let quiet = all.filter { ($0.claimed_min ?? 0) == 0 && ($0.seen_min ?? 0) == 0 }.map(WeekView.name)
        let scale = max(1, rows.map { max($0.claimed, $0.seen) }.max() ?? 1)
        let statuses = Set(rows.compactMap { PaceMark.Kind($0.status) })

        return Card(padding: Alibi.Space.s4, spacing: 10) {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .center, spacing: Alibi.Space.s3) {
                    CardTitle(text: "Claimed vs seen")
                    Spacer(minLength: 0)
                    BarLegend()
                }
                VStack(alignment: .leading, spacing: Alibi.Space.s1) {
                    CardTitle(text: "Claimed vs seen")
                    BarLegend()
                }
            }
            ForEach(Array(rows.enumerated()), id: \.offset) { i, r in
                HabitBars(name: r.name, claimed: r.claimed, seen: r.seen, status: PaceMark.Kind(r.status),
                          scale: scale, index: i)
            }
            if !quiet.isEmpty {
                Text("Nothing claimed yet for \(ListFormatter.localizedString(byJoining: quiet)).")
                    .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if !statuses.isEmpty {
                PaceLegend(kinds: PaceMark.Kind.allCases.filter(statuses.contains))
                    .padding(.top, 2)
            }
        }
    }
}

/// One habit: its name and pace mark, "seen of claimed", then the claimed bar (neutral outline) over the seen bar
/// (accent). Both share one scale so lengths compare across habits; they grow from the left on appear.
private struct HabitBars: View {
    let name: String
    let claimed: Int
    let seen: Int
    let status: PaceMark.Kind?
    let scale: Int
    let index: Int

    @ScaledMetric(relativeTo: .subheadline) private var mark: CGFloat = 9
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var claimedIn = false
    @State private var seenIn = false

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .firstTextBaseline, spacing: Alibi.Space.s3) {
                    title
                    Spacer(minLength: 0)
                    numbers
                }
                VStack(alignment: .leading, spacing: 2) {
                    title
                    numbers
                }
            }
            GeometryReader { g in
                VStack(alignment: .leading, spacing: 3) {
                    RoundedRectangle(cornerRadius: 3, style: .continuous)
                        .strokeBorder(Alibi.ui.hairlineStrong, lineWidth: 1.5)
                        .frame(width: width(claimed, in: g.size.width), height: 7)
                        .scaleEffect(x: claimedIn ? 1 : 0.001, y: 1, anchor: .leading)
                    RoundedRectangle(cornerRadius: 3, style: .continuous)
                        .fill(Alibi.ui.accent)
                        .frame(width: width(seen, in: g.size.width), height: 7)
                        .scaleEffect(x: seenIn ? 1 : 0.001, y: 1, anchor: .leading)
                }
            }
            .frame(height: 17)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(a11y)
        .onAppear(perform: grow)
    }

    private var title: some View {
        HStack(alignment: .center, spacing: 6) {
            Text(name).font(Alibi.Fonts.iosSubheadline).foregroundStyle(Alibi.ui.ink).lineLimit(1)
            if let status { PaceMark(kind: status).frame(width: mark, height: mark) }
        }
    }

    private var numbers: some View {
        let seenText = Text(TodayFmt.total(Double(seen))).foregroundStyle(Alibi.ui.ink).fontWeight(.semibold)
        return Text("\(seenText) of \(TodayFmt.total(Double(claimed)))")
            .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2).monospacedDigit()
            .lineLimit(1)
    }

    private func width(_ m: Int, in w: CGFloat) -> CGFloat {
        guard m > 0 else { return 0 }
        return max(6, w * CGFloat(m) / CGFloat(scale))
    }

    private var a11y: String {
        let pace = status.map { ", \($0.word.lowercased())" } ?? ""
        return "\(name)\(pace). Seen \(TodayFmt.total(Double(seen))) of \(TodayFmt.total(Double(claimed))) claimed."
    }

    /// The bars grow in: claimed at 200 ms, seen 60 ms later, 40 ms per row after that.
    private func grow() {
        if reduceMotion { claimedIn = true; seenIn = true; return }
        let delay = 0.2 + Double(min(index, 5)) * Alibi.Motion.stagger
        withAnimation(Alibi.Motion.easeOut(Alibi.Motion.durReveal).delay(delay)) { claimedIn = true }
        withAnimation(Alibi.Motion.easeOut(Alibi.Motion.durReveal).delay(delay + 0.06)) { seenIn = true }
    }
}

/// Weekly pace from the Mac's report: ● on pace (green), ◐ behind pace (amber). Always shape plus colour.
private struct PaceMark: View {
    enum Kind: CaseIterable {
        case onPace, behind
        init?(_ raw: String?) {
            switch raw {
            case "aligned": self = .onPace
            case "behind": self = .behind
            default: return nil
            }
        }
        var word: String { switch self { case .onPace: "On pace"; case .behind: "Behind pace" } }
    }

    let kind: Kind
    var body: some View {
        switch kind {
        case .onPace:
            Circle().fill(Alibi.ui.onTask).accessibilityHidden(true)
        case .behind:
            GeometryReader { g in
                let s = min(g.size.width, g.size.height)
                ZStack {
                    Circle().strokeBorder(Alibi.ui.partial, lineWidth: max(1.5, s * 0.16))
                    Rectangle().fill(Alibi.ui.partial).frame(width: s / 2, height: s).offset(x: -s / 4)
                }
                .frame(width: s, height: s)
                .clipShape(Circle())
            }
            .accessibilityHidden(true)
        }
    }
}

/// Claimed (outline) and Seen (accent) swatches.
private struct BarLegend: View {
    var body: some View {
        HStack(spacing: Alibi.Space.s3) {
            HStack(spacing: 5) {
                RoundedRectangle(cornerRadius: 2, style: .continuous)
                    .strokeBorder(Alibi.ui.hairlineStrong, lineWidth: 1.5).frame(width: 12, height: 6)
                Text("Claimed")
            }
            HStack(spacing: 5) {
                RoundedRectangle(cornerRadius: 2, style: .continuous).fill(Alibi.ui.accent).frame(width: 12, height: 6)
                Text("Seen")
            }
        }
        .font(Alibi.Fonts.iosCaption.weight(.regular)).foregroundStyle(Alibi.ui.ink2)
        .lineLimit(1)
        .accessibilityHidden(true)
    }
}

/// The words for the pace marks in use, under a hairline (the day-grid legend).
private struct PaceLegend: View {
    let kinds: [PaceMark.Kind]
    @ScaledMetric(relativeTo: .caption) private var mark: CGFloat = 9
    var body: some View {
        HStack(spacing: 14) {
            ForEach(kinds, id: \.self) { k in
                HStack(spacing: 5) {
                    PaceMark(kind: k).frame(width: mark, height: mark)
                    Text(k.word)
                }
            }
        }
        .font(Alibi.Fonts.iosCaption.weight(.regular)).foregroundStyle(Alibi.ui.ink2)
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, 10)
        .overlay(alignment: .top) { Rectangle().fill(Alibi.ui.hairline).frame(height: 1) }
        .accessibilityHidden(true)
    }
}

/// Nothing to compare yet: the card keeps its place and says when it fills in.
private struct ClaimedSeenEmpty: View {
    let text: String
    var body: some View {
        Card(padding: Alibi.Space.s4, spacing: Alibi.Space.s2) {
            CardTitle(text: "Claimed vs seen")
            Text(text).font(Alibi.Fonts.iosSubheadline).foregroundStyle(Alibi.ui.ink2)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

// MARK: This phone's activity

/// Exercise minutes per day from Health, as bars, with today in green. Above Large type the day labels shrink to
/// one letter so seven of them still fit.
private struct ActivityCard: View {
    let days: [[String: Any]]
    @Environment(\.dynamicTypeSize) private var typeSize

    private struct Row: Identifiable {
        let id: String; let label: String; let letter: String; let move: Int; let steps: Int?
    }

    private static let letterFmt: DateFormatter = {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_GB"); f.dateFormat = "EEEEE"; return f
    }()

    private var rows: [Row] {
        days.prefix(7).reversed().map { d in
            let iso = d["date"] as? String ?? ""
            let label = DaysTable.label(iso)
            return Row(id: iso, label: label, letter: Fmt.day.date(from: iso).map(Self.letterFmt.string(from:)) ?? label,
                       move: DaysTable.num(d["exercise_min"] ?? d["workout_min"]) ?? 0, steps: DaysTable.num(d["steps"]))
        }
    }

    private func axisLabel(_ id: String?) -> String {
        guard let r = rows.first(where: { $0.id == id }) else { return "" }
        return typeSize > .large ? r.letter : r.label
    }

    var body: some View {
        Card(padding: Alibi.Space.s4) {
            HStack(alignment: .firstTextBaseline) {
                CardTitle(text: "Moving, last 7 days")
                Spacer()
                Text("from Health").font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2)
            }
            if rows.isEmpty {
                Text("No Health data yet. Allow Health, then Sync now on the Health tab.")
                    .font(Alibi.Fonts.iosSubheadline).foregroundStyle(Alibi.ui.ink2)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                Chart(rows) { r in
                    BarMark(x: .value("Day", r.id), y: .value("Exercise", r.move), width: .ratio(0.55))
                        .foregroundStyle(r.id == rows.last?.id ? Alibi.ui.accent : Alibi.ui.surface3)
                        .clipShape(RoundedRectangle(cornerRadius: 3, style: .continuous))
                        .annotation(position: .top, spacing: 4) {
                            Text("\(r.move)").font(Alibi.Fonts.iosCaption).foregroundStyle(Alibi.ui.ink2).monospacedDigit()
                        }
                }
                .chartYAxis(.hidden)
                .chartXAxis {
                    AxisMarks { v in
                        AxisValueLabel { Text(axisLabel(v.as(String.self))) }
                            .font(Alibi.Fonts.iosCaption).foregroundStyle(Alibi.ui.ink2)
                    }
                }
                .frame(height: 150)
                .accessibilityElement()
                .accessibilityLabel("Exercise minutes per day: " + rows.map { "\($0.label) \($0.move)" }.joined(separator: ", "))
                Text("Minutes of exercise per day. Today is in green.")
                    .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2)
            }
        }
    }
}
