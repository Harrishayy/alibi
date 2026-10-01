// Drives the Live Activity from the live mirror. MirrorClient hands every `/api/phone/session` reply to `sync(_:)`:
//  · a live session and no activity, app in the foreground → start one (once per session; the button restarts it)
//  · the session changed → update, at most every 15 s unless the status (on / drift / break) changed
//  · the session ended → end with the verdict word, dismissed after 30 minutes
// No APNs: mid-session updates only land while the app is open, so nothing here promises real-time drift alerts.
import ActivityKit
import SwiftUI
import UIKit

@MainActor
final class LiveActivityController: ObservableObject {
    static let shared = LiveActivityController()
    static let throttle: TimeInterval = 15
    static let dismissAfter: TimeInterval = 30 * 60

    /// A session is live on the Mac right now.
    @Published private(set) var sessionLive = false
    /// Our activity is on the Lock Screen / Dynamic Island.
    @Published private(set) var running = false
    /// When the running activity's session ends ("On your Lock Screen until 18:25").
    @Published private(set) var until: Date?

    var enabled: Bool { ActivityAuthorizationInfo().areActivitiesEnabled }

    private typealias State = AlibiLiveAttributes.ContentState
    private var activity: Activity<AlibiLiveAttributes>?
    private var sessionKey: String?          // the session the activity (or the auto-start) belongs to
    private var autoStarted: Set<String> = []
    private var lastPushed: State?
    private var lastPushAt: Date = .distantPast
    private var latest: (habit: String, state: State)?
    private var lastDeclaredMin: Int?
    private var watch: Task<Void, Never>?

    private init() {
        // Re-adopt an activity left running by a previous launch.
        if let a = Activity<AlibiLiveAttributes>.activities.first(where: { $0.activityState == .active }) {
            adopt(a)
            lastPushed = a.content.state
        }
    }

    // MARK: Sync

    func sync(_ s: PhoneSession?) {
        guard let s else { return }                      // offline: keep whatever is showing
        if let live = s.live, live.ends_at != nil || live.started_at != nil {
            let key = live.id.map(String.init) ?? live.started_at.map { String(Int($0)) } ?? live.title
            let state = Self.state(for: live)
            latest = (live.title, state)
            lastDeclaredMin = live.declared_min ?? lastDeclaredMin
            sessionLive = true
            if sessionKey != nil, sessionKey != key { endNow() }     // a different session took over
            if activity == nil {
                if !autoStarted.contains(key), UIApplication.shared.applicationState == .active {
                    autoStarted.insert(key)
                    start(habit: live.title, state: state, key: key)
                }
            } else {
                push(state)
            }
        } else {
            sessionLive = false
            latest = nil
            guard activity != nil else { return }
            end(with: s.recent_verdict.map { Self.verdictState(for: $0, declaredMin: lastDeclaredMin, last: lastPushed) })
        }
    }

    /// "Show on Lock Screen": start (or restart) the activity for the live session.
    func startNow() {
        guard activity == nil, let latest, let key = latestKey() else { return }
        start(habit: latest.habit, state: latest.state, key: key)
    }

    private func latestKey() -> String? {
        guard let s = MirrorClient.shared.session?.live else { return sessionKey ?? "manual" }
        return s.id.map(String.init) ?? s.started_at.map { String(Int($0)) } ?? s.title
    }

    // MARK: ActivityKit

    private func start(habit: String, state: State, key: String) {
        guard enabled else { return }
        do {
            let a = try Activity.request(attributes: AlibiLiveAttributes(habit: String(habit.prefix(18))),
                                         content: .init(state: state, staleDate: state.end), pushType: nil)
            sessionKey = key
            lastPushed = state
            lastPushAt = Date()
            adopt(a)
        } catch {
            running = false
        }
    }

    private func push(_ state: State) {
        guard let a = activity, state != lastPushed else { return }
        let statusChanged = state.status != lastPushed?.status
        guard statusChanged || Date().timeIntervalSince(lastPushAt) >= Self.throttle else { return }
        lastPushed = state
        lastPushAt = Date()
        until = state.end
        Task { await a.update(.init(state: state, staleDate: state.end)) }
    }

    private func end(with verdict: State?) {
        guard let a = activity else { return }
        activity = nil; sessionKey = nil; running = false; until = nil
        let final = verdict ?? lastPushed
        Task {
            if let final {
                await a.end(.init(state: final, staleDate: nil), dismissalPolicy: .after(Date().addingTimeInterval(Self.dismissAfter)))
            } else {
                await a.end(nil, dismissalPolicy: .immediate)
            }
        }
    }

    private func endNow() {
        guard let a = activity else { return }
        activity = nil; sessionKey = nil; running = false; until = nil
        Task { await a.end(nil, dismissalPolicy: .immediate) }
    }

    /// Track the activity so a swipe-away on the Lock Screen brings the button back.
    private func adopt(_ a: Activity<AlibiLiveAttributes>) {
        activity = a
        running = true
        until = a.content.state.end
        watch?.cancel()
        watch = Task { [weak self] in
            for await st in a.activityStateUpdates where st != .active {
                await MainActor.run {
                    guard let self, self.activity?.id == a.id else { return }
                    self.activity = nil; self.running = false; self.until = nil
                }
                break
            }
        }
    }

    // MARK: Session → content (strings per Voice.md "Live Activity strings")

    private static let hm: DateFormatter = {
        let f = DateFormatter(); f.dateFormat = "HH:mm"; return f
    }()

    static func state(for s: PhoneSession.Live, now: Date = Date()) -> AlibiLiveAttributes.ContentState {
        let declared = TimeInterval((s.declared_min ?? 25) * 60)
        let start = s.start ?? s.end.map { $0.addingTimeInterval(-declared) } ?? now
        let end = s.end ?? start.addingTimeInterval(declared)
        let pct = s.on_task_ratio.map { Int(($0 * 100).rounded()) }
        let onTask = pct.map { max(0, min(100, $0)) }   // nil until the first sample: the views say "Watching"
        if let d = s.drifting {
            let mins = max(1, Int(((d.since_s ?? 60) / 60).rounded()))
            return .init(start: start, end: end, onTask: onTask, status: "drift",
                         line: "\(noun(d.label ?? s.last_label)) · \(mins) min", pose: "sideeye", badge: "\(mins)m",
                         cause: d.label ?? s.last_label ?? "phone")
        }
        if s.on_break == true {
            return .init(start: start, end: end, onTask: onTask, status: "break", line: "On a break", pose: "sleepy")
        }
        let line: String
        if let pct {
            line = s.last_label == "on_task" ? "On task \(pct)% · last seen \(hm.string(from: now))" : "On task \(pct)%"
        } else {
            line = "Watching since \(hm.string(from: start))"
        }
        return .init(start: start, end: end, onTask: onTask, status: "on", line: line, pose: "focused")
    }

    static func verdictState(for v: PhoneSession.Verdict, declaredMin: Int?, last: AlibiLiveAttributes.ContentState?)
        -> AlibiLiveAttributes.ContentState {
        let status: String
        switch v.verdict {
        case "done": status = "done"
        case "partial", "partly": status = "partial"
        default: status = "slacked"
        }
        let ratio = max(0, min(1, v.on_task_ratio ?? Double(last?.onTask ?? 0) / 100))
        let declared = declaredMin ?? last.map { max(1, Int(($0.end.timeIntervalSince($0.start) / 60).rounded())) }
        let line = declared.map { "\(Int((ratio * Double($0)).rounded())) of \($0) min on task" }
            ?? "On task \(Int((ratio * 100).rounded()))%"
        let pose = ["done": "celebrate", "partial": "partial", "slacked": "supportive"][status] ?? "supportive"
        let now = Date()
        return .init(start: last?.start ?? now, end: last?.end ?? now, onTask: Int((ratio * 100).rounded()),
                     status: status, line: line, pose: pose)
    }

    /// The drift's cause as a noun: "Phone", "Away", "Off task".
    private static func noun(_ label: String?) -> String {
        switch label {
        case "phone": return "Phone"
        case "absent": return "Away"
        case "idle": return "Idle"
        case "off_task": return "Off task"
        default: return label.map { $0.replacingOccurrences(of: "_", with: " ").capitalized } ?? "Off task"
        }
    }
}

// MARK: Button

/// "Show on Lock Screen": visible while a session is live, Live Activities are on and none is showing.
/// Once it's up, a quiet status line says until when.
struct LiveActivityButton: View {
    @ObservedObject private var live = LiveActivityController.shared
    private let p = Alibi.Palette.dark

    var body: some View {
        Group {
            if live.running, let until = live.until {
                Label {
                    Text("On your Lock Screen until \(until, format: .dateTime.hour().minute())")
                } icon: {
                    Image(systemName: "lock")
                }
                .font(Alibi.Fonts.iosFootnote)
                .monospacedDigit()
                .foregroundStyle(p.ink2)
                .transition(.opacity)
            } else if live.sessionLive && live.enabled {
                Button {
                    live.startNow()
                } label: {
                    Label("Show on Lock Screen", systemImage: "lock")
                        .font(Alibi.Fonts.iosSubheadline.weight(.semibold))
                        .foregroundStyle(p.ink)
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .background(RoundedRectangle(cornerRadius: Alibi.Radius.sm, style: .continuous).fill(p.surface2))
                        .overlay(RoundedRectangle(cornerRadius: Alibi.Radius.sm, style: .continuous).strokeBorder(p.hairline))
                }
                .buttonStyle(.plain)
                .sensoryFeedback(.selection, trigger: live.running)
                .transition(.opacity)
            }
        }
        .alibiAnimation(Alibi.Motion.smooth, value: live.running)
    }
}
