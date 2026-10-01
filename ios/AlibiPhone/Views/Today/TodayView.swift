// Today: a live mirror of the Mac. Four states, swapped in place with opacity and scale 0.96 → 1 on spring-smooth:
// live (160pt Pinch beside the ring, the drift line, on-task and done-today stats), verdict (Pinch's clip, the pill,
// the on-task meter), idle (the honesty line, what's next, how to start) and offline (plain chrome copy with a fix).
// Layout and copy follow docs/design/canvas/project/Phone-Today-*.dc.html and Phone-Verdict.dc.html.
import SwiftUI

struct TodayView: View {
    @ObservedObject var mirror: MirrorClient
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private enum Mode: Equatable { case loading, offline, live, verdict, idle }

    private var mode: Mode {
        if mirror.online == false && mirror.session == nil { return .offline }
        guard let s = mirror.session else { return mirror.online == false ? .offline : .loading }
        if s.live != nil { return .live }
        if let v = s.recent_verdict, let end = v.ended, Date().timeIntervalSince(end) < 600, VerdictKind(v.verdict) != nil {
            return .verdict
        }
        return .idle
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                switch mode {
                case .loading: LoadingToday()
                case .offline: OfflineToday(retry: { await mirror.refresh() })
                case .live: LiveToday(mirror: mirror)
                case .verdict: VerdictToday(mirror: mirror)
                case .idle: IdleToday(mirror: mirror)
                }
            }
            .id(mode)
            .transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.96, anchor: .top)))
            .padding(.horizontal, Alibi.Space.cardPhone)
            .padding(.top, Alibi.Space.s2)
            .padding(.bottom, Alibi.Space.s8)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .animation(Alibi.Motion.adaptive(Alibi.Motion.smooth, reduceMotion: reduceMotion), value: mode)
        .scrollIndicators(.hidden)
        .refreshable { await mirror.refresh() }
        .background(Alibi.ui.bg.ignoresSafeArea())
        .sensoryFeedback(.success, trigger: mirror.doneCount)
        .sensoryFeedback(.warning, trigger: mirror.nudgeCount)
    }
}

// MARK: Shared bits

enum TodayFmt {
    static let longDay: DateFormatter = {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_GB"); f.dateFormat = "EEEE d MMMM"; return f
    }()
    static func hm(_ d: Date?) -> String { d.map { Fmt.hm.string(from: $0) } ?? "--:--" }
    /// Chrome totals: "50 min", "2h 10m".
    static func total(_ minutes: Double) -> String {
        let m = Int(minutes.rounded())
        return m < 60 ? "\(m) min" : "\(m / 60)h \(String(format: "%02d", m % 60))m"
    }
    static func pct(_ r: Double?) -> String { r.map { "\(Int(($0 * 100).rounded()))%" } ?? "--" }
    static func habit(_ key: String?) -> String {
        guard let key, !key.isEmpty else { return "Your next habit" }
        let known = ["cpp": "C++", "internships": "Internship apps"]
        return known[key] ?? key.capitalized
    }
}

private func mood(_ raw: String?, fallback: PinchMood) -> PinchMood { raw.flatMap(PinchMood.init(rawValue:)) ?? fallback }

/// The 8pt on-task dot that breathes (opacity 1 ↔ 0.45, 2.4 s) while live; still under Reduce Motion.
private struct LiveDot: View {
    var label = "on_task"
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var dim = false
    var body: some View {
        StatusDot(label: label, size: 8)
            .opacity(dim ? 0.45 : 1)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) { dim = true }
            }
    }
}

// MARK: Live

private struct LiveToday: View {
    @ObservedObject var mirror: MirrorClient
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        let s = mirror.session
        let live = s?.live ?? PhoneSession.Live()
        let start = live.start ?? Date()
        let end = live.end ?? start.addingTimeInterval(Double((live.declared_min ?? 25) * 60))
        let onBreak = live.on_break == true
        let drifting = live.drifting != nil && !onBreak

        VStack(alignment: .leading, spacing: 0) {
            ScreenHeader(title: "Today", subtitle: nil)
            HStack(spacing: 6) {
                LiveDot(label: onBreak ? "idle" : drifting ? (live.drifting?.label ?? "phone") : "on_task")
                Text(onBreak ? "On a break · live from \(mirror.macName)" : "Live from \(mirror.macName)")
                    .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2).lineLimit(2)
            }
            .padding(.top, 2)
            .rise(0)

            VStack(alignment: .leading, spacing: 2) {
                HStack(alignment: .firstTextBaseline, spacing: Alibi.Space.s3) {
                    Text(live.title).font(Alibi.Fonts.iosTitle).foregroundStyle(Alibi.ui.ink)
                    Spacer(minLength: 0)
                    if let m = live.declared_min {
                        Text("\(m) min").font(Alibi.Fonts.iosSubheadline).foregroundStyle(Alibi.ui.ink2).monospacedDigit()
                    }
                }
                Text("Started on your Mac at \(TodayFmt.hm(live.start))")
                    .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2).monospacedDigit()
            }
            .padding(.top, 20)
            .rise(1)

            let pinch = PinchView(mood: onBreak ? .sleepy : drifting ? .thinking : mood(s?.pinch?.mood, fallback: .focused),
                                  clip: mirror.clip, clipID: mirror.clipID, size: 160,
                                  camera: !onBreak && live.modality != "digital")    // the lens glows only while sampling
                .accessibilityHidden(true)
            let ring = RingTimer(start: start, end: end, size: 176,
                                 tint: onBreak ? Alibi.ui.partial : drifting ? Alibi.ui.warn : Alibi.ui.accent,
                                 caption: "left")
            Group {
                if typeSize >= .accessibility1 {
                    VStack(spacing: Alibi.Space.s4) { pinch; ring }.frame(maxWidth: .infinity)
                } else {
                    HStack(alignment: .center) { pinch.padding(.leading, Alibi.Space.s2); Spacer(minLength: 0); ring }
                }
            }
            .padding(.top, Alibi.Space.s3)
            .rise(2)

            line(live: live, end: end, onBreak: onBreak, drifting: drifting, said: s?.pinch?.line)
                .font(Alibi.Fonts.iosBody).foregroundStyle(Alibi.ui.ink)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, Alibi.Space.s3)
                .accessibilityAddTraits(.updatesFrequently)
                .rise(3)

            let cols = typeSize >= .accessibility1 ? [GridItem(.flexible())]
                : [GridItem(.flexible(), spacing: Alibi.Space.s3), GridItem(.flexible())]
            LazyVGrid(columns: cols, alignment: .leading, spacing: Alibi.Space.s3) {
                Card(padding: Alibi.Space.s4) {
                    Stat(label: "On task", value: TodayFmt.pct(live.on_task_ratio)) {
                        if let l = live.last_label {
                            ViewThatFits(in: .horizontal) {
                                HStack(spacing: 6) {
                                    Text("Latest look").foregroundStyle(Alibi.ui.ink3)
                                    StatusDot(label: l, size: 9, showWord: true)
                                }
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Latest look").foregroundStyle(Alibi.ui.ink3)
                                    StatusDot(label: l, size: 9, showWord: true)
                                }
                            }
                            .font(Alibi.Fonts.iosFootnote).lineLimit(1)
                        } else {
                            Text("No look yet").font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink3)
                        }
                    }
                }
                .frame(maxHeight: .infinity, alignment: .top)
                Card(padding: Alibi.Space.s4) {
                    let done = s?.today?.habits_done ?? 0, total = max(s?.today?.habits_total ?? 0, done)
                    Stat(label: "Done today", value: total > 0 ? "\(done) of \(total)" : "\(done)") {
                        if total > 0 { HabitSegments(done: done, total: total) }
                    }
                }
                .frame(maxHeight: .infinity, alignment: .top)
            }
            .padding(.top, 20)
            .rise(4)

            VStack(alignment: .leading, spacing: Alibi.Space.s3) {
                LiveActivityButton()
                Text("Break and Finish are on your Mac: ⌥⌘A opens the island.")
                    .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink3)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(.top, 20)
            .rise(5)
        }
    }

    private func line(live: PhoneSession.Live, end: Date, onBreak: Bool, drifting: Bool, said: String?) -> Text {
        let habit = live.title.lowercased()
        if onBreak {
            if let until = live.break_until { return Text("On a break. Back at \(TodayFmt.hm(Date(timeIntervalSince1970: until))).") }
            return Text("On a break. I've moved the finish to \(TodayFmt.hm(end)).")
        }
        if drifting {
            let mins = max(1, Int(((live.drifting?.since_s ?? 60) / 60).rounded()))
            let minutes = "\(mins) \(mins == 1 ? "minute" : "minutes")"
            switch live.drifting?.label ?? live.last_label {
            case "phone":
                return Text("You said \(habit). I've seen your ") + Text("phone").foregroundStyle(Alibi.ui.warnInk)
                    + Text(" for \(minutes).")
            case "absent":
                return Text("Your desk's been ") + Text("empty").foregroundStyle(Alibi.ui.warnInk)
                    + Text(" for \(minutes). Still \(habit)?")
            case "idle":
                return Text("You said \(habit). Nothing's ") + Text("moved").foregroundStyle(Alibi.ui.warnInk)
                    + Text(" in \(minutes).")
            default:
                return Text("You said \(habit). I've seen ") + Text("something else").foregroundStyle(Alibi.ui.warnInk)
                    + Text(" for \(minutes).")
            }
        }
        if let said, !said.isEmpty { return Text(said) }
        let mins = max(0, Int(Date().timeIntervalSince(live.start ?? Date()) / 60))
        return Text(mins < 1 ? "Just started. I'm watching." : "\(mins) \(mins == 1 ? "minute" : "minutes") in. Nothing to flag.")
    }
}

/// "3 of 5" as five 4pt capsules: filled `on-task` for done, a `hairline-strong` outline for to do.
private struct HabitSegments: View {
    let done: Int
    let total: Int
    var body: some View {
        HStack(spacing: Alibi.Space.s1) {
            ForEach(0..<min(total, 12), id: \.self) { i in
                if i < done {
                    Capsule().fill(Alibi.ui.onTask).frame(height: 4)
                } else {
                    Capsule().strokeBorder(Alibi.ui.hairlineStrong, lineWidth: 1).frame(height: 4)
                }
            }
        }
        .frame(height: 14)
        .accessibilityElement()
        .accessibilityLabel("\(done) of \(total) habits done")
    }
}

// MARK: Verdict

private struct VerdictToday: View {
    @ObservedObject var mirror: MirrorClient
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var shownPct = 0
    @State private var pillIn = false
    @State private var textIn = false

    var body: some View {
        let s = mirror.session
        let v = s?.recent_verdict
        let kind = VerdictKind(v?.verdict) ?? .done
        let ratio = v?.on_task_ratio ?? 0
        let target = Int((ratio * 100).rounded())

        VStack(alignment: .leading, spacing: 0) {
            ScreenHeader(title: "Today",
                         subtitle: Text("\(v?.title ?? "Session") · ended \(TodayFmt.hm(v?.ended)) · \(Fmt.ago(v?.ended))"))

            VStack(spacing: 0) {
                PinchView(mood: mood(s?.pinch?.mood, fallback: .idle), clip: mirror.clip ?? kind.clip,
                          clipID: mirror.clipID, size: 160, force: true)
                    .accessibilityHidden(true)
                HStack(spacing: Alibi.Space.s2) {
                    VerdictPill(verdict: kind)
                    if let streak = s?.streak_days, streak > 0 { StreakBadge(days: streak) }
                }
                .padding(.top, Alibi.Space.s2)
                .scaleEffect(pillIn || reduceMotion ? 1 : 0.94)
                .opacity(pillIn ? 1 : 0)
                Text(headline(kind, ratio: ratio))
                    .font(Alibi.Fonts.iosTitle).foregroundStyle(Alibi.ui.ink).monospacedDigit()
                    .multilineTextAlignment(.center)
                    .padding(.top, 14)
                    .opacity(textIn ? 1 : 0).offset(y: textIn || reduceMotion ? 0 : 4)
                Text(s?.pinch?.line ?? Self.fallbackLine(kind))
                    .font(Alibi.Fonts.iosBody).foregroundStyle(Alibi.ui.ink2).monospacedDigit()
                    .multilineTextAlignment(.center).frame(maxWidth: 320)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, Alibi.Space.s1)
                    .opacity(textIn ? 1 : 0).offset(y: textIn || reduceMotion ? 0 : 4)
            }
            .frame(maxWidth: .infinity)
            .padding(.top, Alibi.Space.s4)

            HStack(alignment: .center, spacing: Alibi.Space.s4) {
                Meter(value: ratio)
                VStack(alignment: .trailing, spacing: 0) {
                    Text("\(shownPct)%")
                        .font(Alibi.Fonts.rounded(28)).foregroundStyle(Alibi.ui.ink)
                        .contentTransition(.numericText(value: Double(shownPct)))
                        .frame(minWidth: 64, alignment: .trailing)
                    Text("on task").font(Alibi.Fonts.iosCaption).foregroundStyle(Alibi.ui.ink2)
                }
                .accessibilityElement(children: .combine)
            }
            .padding(.top, Alibi.Space.s4)
            .rise(2)

            Card(padding: Alibi.Space.s4, spacing: Alibi.Space.s2) {
                SectionTitle(text: "What I saw")
                Text("The proof is on your Mac: every frame, and a way to fix a moment.")
                    .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(.top, Alibi.Space.s4)
            .rise(3)
        }
        .onAppear { reveal(target) }
    }

    private func headline(_ k: VerdictKind, ratio: Double) -> String {
        "\(Int((ratio * 100).rounded()))% of the session on task."
    }

    static func fallbackLine(_ k: VerdictKind) -> String {
        switch k {
        case .done: "Every look checked out."
        case .partial: "Over 60%, so the streak holds."
        case .slacked: "Tap any frame on your Mac if I got it wrong."
        }
    }

    /// Verdict reveal (Motion.md §1): pill pops at 270 ms, the % counts up from 420 ms, the sentence lands at 1000 ms.
    private func reveal(_ target: Int) {
        if reduceMotion {
            withAnimation(Alibi.Motion.reduced) { pillIn = true; textIn = true; shownPct = target }
            return
        }
        withAnimation(Alibi.Motion.bouncy.delay(0.27)) { pillIn = true }
        withAnimation(Alibi.Motion.easeOut(Alibi.Motion.durReveal).delay(0.42)) { shownPct = target }
        withAnimation(Alibi.Motion.easeOut(Alibi.Motion.durMedium).delay(1.0)) { textIn = true }
    }
}

// MARK: Idle

private struct IdleToday: View {
    @ObservedObject var mirror: MirrorClient
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        let s = mirror.session
        let today = s?.today
        let done = today?.habits_done ?? 0
        let total = max(today?.habits_total ?? 0, done)

        VStack(alignment: .leading, spacing: 0) {
            ScreenHeader(title: "Today", subtitle: Text("\(TodayFmt.longDay.string(from: Date())) · nothing running"))
                .rise(0)

            let pinch = PinchView(mood: mood(s?.pinch?.mood, fallback: .idle), clip: mirror.clip, clipID: mirror.clipID, size: 160)
                .accessibilityHidden(true)
            let words = VStack(alignment: .leading, spacing: 10) {
                Text(honesty(today)).font(Alibi.Fonts.iosTitle).foregroundStyle(Alibi.ui.ink).monospacedDigit()
                    .fixedSize(horizontal: false, vertical: true)
                if let next = s?.plan_next, let at = next.starts_at {
                    Label {
                        Text("\(TodayFmt.habit(next.habit)) next, \(TodayFmt.hm(at))").monospacedDigit()
                    } icon: {
                        Image(systemName: "calendar")
                    }
                    .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2)
                }
            }
            Group {
                if typeSize >= .accessibility1 {
                    VStack(alignment: .leading, spacing: Alibi.Space.s3) { pinch; words }
                } else {
                    HStack(alignment: .center, spacing: Alibi.Space.s3) { pinch; words; Spacer(minLength: 0) }
                }
            }
            .padding(.top, Alibi.Space.s2)
            .rise(1)

            VStack(alignment: .leading, spacing: Alibi.Space.s2) {
                SectionLabel(text: "Start on your Mac")
                HStack(alignment: .firstTextBaseline, spacing: Alibi.Space.s2) {
                    Kbd(keys: "⌥⌘A")
                    Text("opens the island. Say what you're about to do.")
                        .font(Alibi.Fonts.iosSubheadline).foregroundStyle(Alibi.ui.ink)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(.horizontal, Alibi.Space.s4).padding(.vertical, Alibi.Space.s3)
                .frame(maxWidth: .infinity, minHeight: 52, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: Alibi.Radius.md, style: .continuous).fill(Alibi.ui.surface1))
                .overlay(RoundedRectangle(cornerRadius: Alibi.Radius.md, style: .continuous)
                    .strokeBorder(Alibi.ui.hairline, lineWidth: 1))
            }
            .padding(.top, Alibi.Space.s3)
            .rise(2)

            VStack(alignment: .leading, spacing: Alibi.Space.s2) {
                HStack(alignment: .center, spacing: Alibi.Space.s3) {
                    (Text("Habits ") + Text(total > 0 ? "  \(done) of \(total) done" : "").font(Alibi.Fonts.iosHeadline.weight(.regular))
                        .foregroundStyle(Alibi.ui.ink2))
                        .font(Alibi.Fonts.iosHeadline).foregroundStyle(Alibi.ui.ink).monospacedDigit()
                        .accessibilityAddTraits(.isHeader)
                    Spacer(minLength: 0)
                    if let streak = s?.streak_days, streak > 0 { StreakBadge(days: streak) }
                }
                if let v = s?.recent_verdict, let kind = VerdictKind(v.verdict) {
                    Card(padding: Alibi.Space.s4) {
                        HStack(spacing: Alibi.Space.s3) {
                            Image(systemName: "camera").font(Alibi.Fonts.iosSubheadline).foregroundStyle(Alibi.ui.ink2)
                                .frame(width: 32, height: 32)
                                .background(Circle().fill(Alibi.ui.surface2))
                                .accessibilityHidden(true)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(v.title).font(Alibi.Fonts.iosHeadline).foregroundStyle(Alibi.ui.ink)
                                Text("\(TodayFmt.pct(v.on_task_ratio)) on task · \(TodayFmt.hm(v.ended))")
                                    .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2).monospacedDigit()
                            }
                            Spacer(minLength: 0)
                            VerdictPill(verdict: kind)
                        }
                    }
                } else if done == 0 {
                    Text("Nothing claimed yet. What are you about to do?")
                        .font(Alibi.Fonts.iosBody).foregroundStyle(Alibi.ui.ink2)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if total > 0 { HabitSegments(done: done, total: total).padding(.top, Alibi.Space.s1) }
            }
            .padding(.top, Alibi.Space.s6)
            .rise(3)
        }
    }

    private func honesty(_ t: PhoneSession.Today?) -> String {
        let seen = t?.verified_min ?? 0
        if let claimed = t?.declared_min, claimed > 0 {
            return "Claimed \(TodayFmt.total(claimed)). Seen \(TodayFmt.total(seen))."
        }
        return seen > 0 ? "Seen \(TodayFmt.total(seen)) on task today." : "Nothing claimed yet today."
    }
}

// MARK: Offline and loading

private struct OfflineToday: View {
    var retry: () async -> Void
    @State private var busy = false
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ScreenHeader(title: "Today", subtitle: Text("Not connected"))
            Card(spacing: Alibi.Space.s4) {
                HStack(alignment: .top, spacing: Alibi.Space.s3) {
                    Image(systemName: "laptopcomputer").font(.title3).foregroundStyle(Alibi.ui.ink)
                        .frame(width: 44, height: 44)
                        .background(RoundedRectangle(cornerRadius: Alibi.Radius.sm, style: .continuous).fill(Alibi.ui.surface2))
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: Alibi.Space.s1) {
                        Text("Can't reach your Mac.").font(Alibi.Fonts.iosHeadline).foregroundStyle(Alibi.ui.ink)
                        Text("Check you're both on Tailscale or the same Wi-Fi, then pull to refresh.")
                            .font(Alibi.Fonts.iosSubheadline).foregroundStyle(Alibi.ui.ink2)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                Button {
                    busy = true
                    Task { await retry(); busy = false }
                } label: { Text(busy ? "Trying…" : "Retry") }
                    .buttonStyle(SecondaryButtonStyle()).disabled(busy)
            }
            .padding(.top, 20)
            .rise(1)
        }
    }
}

private struct LoadingToday: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ScreenHeader(title: "Today", subtitle: Text("Looking for your Mac…"))
            PinchView(mood: .listening, size: 160).accessibilityHidden(true).padding(.top, Alibi.Space.s2)
        }
    }
}
