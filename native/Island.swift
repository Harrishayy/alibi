// Alibi Island — a Dynamic-Island-style bar that lives in the MacBook notch.
// Collapsed: habit + live state on the left wing, countdown ring on the right; idle shows a status dot + today's tally.
// Hover (after a short dwell) peeks the panel without stealing focus; click the field or press ⌥⌘A to type.
// Nudges and verdicts expand it on their own, with actions. Talks to the daemon at http://127.0.0.1:8765.
import AppKit
import Carbon.HIToolbox
import SwiftUI

let API = ProcessInfo.processInfo.environment["ALIBI_API"] ?? "http://127.0.0.1:8765"

// MARK: - API models (new fields optional so an older daemon still decodes)

struct LabelEv: Decodable, Hashable {
    let ts: Double; let label: String; let note: String
    let label_text: String?; let frame_url: String?
}
struct LastSeen: Decodable { let label: String; let label_text: String?; let note: String?; let source: String?; let ago_s: Double? }
struct Drifting: Decodable { let label: String; let label_text: String?; let since_s: Double?; let samples: Int? }
struct OnBreak: Decodable { let until: Double?; let left_s: Double? }
struct Session: Decodable {
    let id: Int; let habit: String; let label: String?; let modality: String; let declared_min: Int
    let started_at: Double; let ends_at: Double
    let labels: [LabelEv]; let on_task_so_far: Double?; let last_frame_url: String?
    let samples: Int?; let warming_up: Bool?; let recent: [String]?; let recent_on_task: Double?
    let last_seen: LastSeen?; let drifting: Drifting?; let on_break: OnBreak?
    let nudges: Int?; let strikes: Int?
    var name: String { label ?? displayName(habit) }
}
struct AlertAction: Decodable, Equatable, Hashable { let label: String; let say: String?; let url: String?; let dismiss: Bool? }
struct AlertEv: Decodable, Equatable {
    let id: Int64; let ts: Double?; let kind: String; let text: String; let image_url: String?
    let session_id: Int?; let habit: String?; let habit_label: String?; let verdict: String?; let ratio: Double?
    let actions: [AlertAction]?; let reel_url: String?
    init(id: Int64, kind: String, text: String, ts: Double? = nil, session_id: Int? = nil, habit_label: String? = nil,
         verdict: String? = nil, ratio: Double? = nil, actions: [AlertAction]? = nil) {
        self.id = id; self.ts = ts; self.kind = kind; self.text = text; image_url = nil; self.session_id = session_id
        habit = nil; self.habit_label = habit_label; self.verdict = verdict; self.ratio = ratio; self.actions = actions; reel_url = nil
    }
}
struct HabitRef: Codable, Hashable { let key: String; let label: String?; let modality: String; let default_min: Int?
    var name: String { label ?? displayName(key) }
}
struct Today: Decodable { let tally: String?; let habits_done: Int?; let habits_total: Int?; let verified_min: Int? }
struct Verdict: Decodable {
    let id: Int; let habit: String; let label: String?; let verdict: String?; let on_task_ratio: Double?
    let declared_min: Int; let elapsed_min: Int?; let labels: [LabelEv]; let summary: String?; let reel_url: String?
}
struct StateResp: Decodable {
    let now: Double?
    let session: Session?; let alert: AlertEv?; let witness: String; let witness_label: String?
    let habits: [HabitRef]?; let today: Today?; let recent_verdict: Verdict?; let status_text: String?
}

func displayName(_ key: String) -> String { key == "cpp" ? "C++" : key.prefix(1).uppercased() + key.dropFirst() }
let labelCopy = ["on_task": "On task", "phone": "On your phone", "absent": "Away from desk", "idle": "Idle", "off_task": "Off task"]
func human(_ l: String) -> String { labelCopy[l] ?? l.replacingOccurrences(of: "_", with: " ").capitalized }

let palette: [String: Color] = [
    "on_task": Color(hex: 0x6FA172), "phone": Color(hex: 0xE0644C), "off_task": Color(hex: 0xC9553B),
    "idle": Color(hex: 0xE3A548), "absent": Color(hex: 0x8F8A82),
]
let coral = Color(hex: 0xD97757)
let cream = Color(hex: 0xF4EFE6)
let green = Color(hex: 0x6FA172), amber = Color(hex: 0xE3A548), red = Color(hex: 0xE0644C)
func verdictColour(_ v: String?) -> Color { v == "done" ? green : v == "partial" ? amber : v == "slacked" ? red : coral }

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255)
    }
}

// MARK: - Model

enum Mode: Equatable { case collapsed, expanded, alert }

@MainActor
final class Island: ObservableObject {
    @Published var state: StateResp?
    @Published var online = false
    @Published var connecting = true          // first ~3 s after launch: don't flash "offline"
    @Published var mode: Mode = .collapsed
    @Published var alert: AlertEv?
    @Published var pending: AlertEv?          // alert queued while the user is typing / pinned
    @Published var reply: String?
    @Published var replyFailed = false
    @Published var draft = ""
    @Published var busy = false
    @Published var now = Date().timeIntervalSince1970
    @Published var pinned = false             // opened by hotkey/click: stays open until Esc / send / click elsewhere
    @Published var hovering = false
    @Published var measured: CGSize = .zero   // drawn size of the island (drives the hover hit-rect)
    @Published var thumbs: [String: NSImage] = [:]
    @Published var habits: [HabitRef] = []    // cached, so chips survive the daemon going away
    var lastAlertId: Int64?
    var alertTask: Task<Void, Never>?
    let launched = Date().timeIntervalSince1970
    var startingUntil: Double = 0             // [Start] pressed: show "Starting…" (Start disabled) until online or 20 s
    var starting: Bool { !online && now < startingUntil }
    var loading = Set<String>()

    init() {
        if let d = UserDefaults.standard.data(forKey: "alibi.habits"),
           let h = try? JSONDecoder().decode([HabitRef].self, from: d) { habits = h }
    }

    var session: Session? { state?.session }

    func poll() async {
        while true {
            await refresh()
            try? await Task.sleep(nanoseconds: 1_000_000_000)
        }
    }

    func refresh() async {
        now = Date().timeIntervalSince1970
        if let s: StateResp = await get("/api/state?client=island") {
            online = true; connecting = false; startingUntil = 0
            state = s
            if let h = s.habits, h != habits {
                habits = h
                if let d = try? JSONEncoder().encode(h) { UserDefaults.standard.set(d, forKey: "alibi.habits") }
            }
            if let a = s.alert, a.id != lastAlertId {
                // Fresh = raised after launch (minus a little slack); stale alerts from before launch are skipped.
                let fresh = a.ts.map { $0 > launched - 5 } ?? (lastAlertId != nil)
                if fresh && a.kind != "info" { show(alert: a) }
                lastAlertId = a.id
            }
        } else {
            online = false
            if now - launched > 3 { connecting = false }
            // The child we spawned died before answering: stop pretending it's booting.
            if startingUntil > 0 && DaemonOwner.shared.exited { startingUntil = 0; reply = "The daemon exited — see Open logs."; replyFailed = true }
            if startingUntil > 0 && now >= startingUntil { startingUntil = 0; reply = "Still not answering after 20 s — see Open logs."; replyFailed = true }
        }
    }

    func show(alert a: AlertEv) {
        // Don't yank the island out from under someone typing: queue it as a pulsing edge instead.
        if (pinned || !draft.isEmpty) && mode == .expanded {
            pending = a
            return
        }
        pending = nil
        alert = a
        withAnimation(.spring(response: 0.42, dampingFraction: 0.78)) { mode = .alert }
        NSSound(named: a.kind == "nudge" ? "Funk" : "Glass")?.play()
        if hovering { alertTask?.cancel() } else { scheduleDismiss(after: a.kind == "verdict" ? 12 : 8) }
    }

    func scheduleDismiss(after s: Double) {
        alertTask?.cancel()
        alertTask = Task {
            try? await Task.sleep(nanoseconds: UInt64(s * 1_000_000_000))
            if !Task.isCancelled && mode == .alert { dismissAlert() }
        }
    }

    func dismissAlert() {
        alertTask?.cancel()
        withAnimation(.spring(response: 0.4, dampingFraction: 0.85)) { mode = .collapsed }
    }

    func act(_ a: AlertAction) {
        if let say = a.say { Task { await send(say, quiet: true) } }
        if let u = a.url {
            let full = u.hasPrefix("/") ? API + u : u
            if let url = URL(string: full) { NSWorkspace.shared.open(url) }
        }
        dismissAlert()
    }

    func unpinSoon() {
        guard pinned else { return }
        Task {
            try? await Task.sleep(nanoseconds: 2_500_000_000)
            if pinned && draft.isEmpty { pinned = false; withAnimation { mode = .collapsed } }
        }
    }

    func send(_ text: String, quiet: Bool = false) async {
        let t = text.trimmingCharacters(in: .whitespaces)
        guard !t.isEmpty else { return }
        busy = true
        struct R: Decodable { let reply: String }
        let r: R? = await post("/api/say", ["text": t])
        replyFailed = r == nil
        reply = r?.reply ?? "Alibi isn't running, so nothing was recorded."
        draft = ""
        busy = false
        await refresh()                     // optimistic: show the new session wings at once
        if quiet && r != nil { reply = nil }
    }

    func end() async {
        struct R: Decodable { let reply: String }
        let r: R? = await post("/api/end", [:])
        reply = r?.reply
        await refresh()
    }

    func thumb(_ path: String) -> NSImage? {
        if let i = thumbs[path] { return i }
        if !loading.contains(path) {
            loading.insert(path)
            Task { await loadThumb(path) }
        }
        return nil
    }

    func loadThumb(_ path: String) async {
        guard let url = URL(string: API + path), let (d, _) = try? await URLSession.shared.data(from: url),
              let img = NSImage(data: d) else { return }
        thumbs[path] = img
    }

    func get<T: Decodable>(_ path: String) async -> T? {
        guard let url = URL(string: API + path) else { return nil }
        var req = URLRequest(url: url, timeoutInterval: 3)
        req.setValue("island", forHTTPHeaderField: "X-Alibi-Client")
        guard let (d, _) = try? await URLSession.shared.data(for: req) else { return nil }
        return try? JSONDecoder().decode(T.self, from: d)
    }

    func post<T: Decodable>(_ path: String, _ body: [String: String]) async -> T? {
        var req = URLRequest(url: URL(string: API + path)!, timeoutInterval: 10)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("island", forHTTPHeaderField: "X-Alibi-Client")
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        guard let (d, _) = try? await URLSession.shared.data(for: req) else { return nil }
        return try? JSONDecoder().decode(T.self, from: d)
    }
}

// MARK: - Geometry

struct Notch {
    let screen: NSScreen
    var hasNotch: Bool { screen.safeAreaInsets.top > 0 }
    var height: CGFloat { hasNotch ? screen.safeAreaInsets.top : 30 }
    var width: CGFloat {
        guard hasNotch, let l = screen.auxiliaryTopLeftArea, let r = screen.auxiliaryTopRightArea else { return 150 }
        return screen.frame.width - l.width - r.width
    }
}

// Only the width is per mode; the height comes from the measured content.
@MainActor func width(for mode: Mode, notch: Notch, island: Island) -> CGFloat {
    switch mode {
    case .collapsed:
        if island.session != nil { return notch.width + 230 }
        if island.reply != nil { return notch.width + 64 }
        return notch.hasNotch ? notch.width + 56 : 150
    case .expanded: return 520
    case .alert: return island.alert?.kind == "verdict" ? 540 : 500
    }
}

struct SizeKey: PreferenceKey {
    static var defaultValue: CGSize = .zero
    static func reduce(value: inout CGSize, nextValue: () -> CGSize) { value = nextValue() }
}

// MARK: - Shape

struct NotchShape: Shape {
    var top: CGFloat = 8, bottom: CGFloat = 22
    var animatableData: AnimatablePair<CGFloat, CGFloat> {
        get { AnimatablePair(top, bottom) }
        set { top = newValue.first; bottom = newValue.second }
    }
    func path(in r: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: r.minX, y: r.minY))
        p.addQuadCurve(to: CGPoint(x: r.minX + top, y: r.minY + top), control: CGPoint(x: r.minX + top, y: r.minY))
        p.addLine(to: CGPoint(x: r.minX + top, y: r.maxY - bottom))
        p.addQuadCurve(to: CGPoint(x: r.minX + top + bottom, y: r.maxY), control: CGPoint(x: r.minX + top, y: r.maxY))
        p.addLine(to: CGPoint(x: r.maxX - top - bottom, y: r.maxY))
        p.addQuadCurve(to: CGPoint(x: r.maxX - top, y: r.maxY - bottom), control: CGPoint(x: r.maxX - top, y: r.maxY))
        p.addLine(to: CGPoint(x: r.maxX - top, y: r.minY + top))
        p.addQuadCurve(to: CGPoint(x: r.maxX, y: r.minY), control: CGPoint(x: r.maxX - top, y: r.minY))
        p.closeSubpath()
        return p
    }
}

// MARK: - Small views

func mmss(_ s: Double) -> String {
    let s = max(0, Int(s.rounded()))
    return s >= 3600 ? String(format: "%d:%02d:%02d", s / 3600, (s % 3600) / 60, s % 60)
                     : String(format: "%d:%02d", s / 60, s % 60)
}

func rounded(_ size: CGFloat, _ w: Font.Weight = .semibold) -> Font { .system(size: size, weight: w, design: .rounded) }

struct Ring: View {
    let progress: Double; let colour: Color; var width: CGFloat = 2.5
    var body: some View {
        ZStack {
            Circle().stroke(Color.white.opacity(0.14), lineWidth: width)
            Circle().trim(from: 0, to: progress).stroke(colour, style: StrokeStyle(lineWidth: width, lineCap: .round))
                .rotationEffect(.degrees(-90))
        }
    }
}

struct Pulse: View {
    let colour: Color; var size: CGFloat = 7
    @State private var on = false
    var body: some View {
        Circle().fill(colour).frame(width: size, height: size)
            .background(Circle().fill(colour.opacity(0.45)).scaleEffect(on ? 2.4 : 1).opacity(on ? 0 : 1))
            .onAppear { withAnimation(.easeOut(duration: 1.6).repeatForever(autoreverses: false)) { on = true } }
    }
}

struct Glow: View {   // slow pulsing inner edge: drifting (red) or a queued alert (coral)
    let colour: Color; let top: CGFloat; let bottom: CGFloat
    @State private var on = false
    var body: some View {
        NotchShape(top: top, bottom: bottom).stroke(colour.opacity(on ? 0.85 : 0.3), lineWidth: 1.2)
            .onAppear { withAnimation(.easeInOut(duration: 1.1).repeatForever(autoreverses: true)) { on = true } }
    }
}

struct Keycap: View {
    let text: String
    var body: some View {
        Text(text).font(.system(size: 10, weight: .medium)).foregroundStyle(.white.opacity(0.55))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(RoundedRectangle(cornerRadius: 5).fill(Color.white.opacity(0.08)))
            .overlay(RoundedRectangle(cornerRadius: 5).strokeBorder(Color.white.opacity(0.14), lineWidth: 0.5))
    }
}

struct PillButton: View {
    let title: String; var primary = false; var tint: Color = coral; let action: () -> Void
    var body: some View {
        Button(action: action) {
            Text(title).font(.system(size: 12, weight: .semibold)).lineLimit(1).fixedSize()
                .padding(.horizontal, 13).frame(height: 28)
                .background(Capsule().fill(primary ? tint : Color.white.opacity(0.1)))
                .foregroundStyle(primary ? Color.black.opacity(0.85) : cream)
        }.buttonStyle(.plain)
    }
}

// Proportional segmented strip: always fills its width, however many samples there are.
struct Strip: View {
    let labels: [String]; var height: CGFloat = 8
    var body: some View {
        GeometryReader { g in
            HStack(spacing: labels.count > 40 ? 0.5 : 1.5) {
                ForEach(Array(labels.enumerated()), id: \.offset) { _, l in
                    Rectangle().fill(palette[l] ?? .gray)
                }
            }
            .frame(width: g.size.width, height: height)
            .clipShape(RoundedRectangle(cornerRadius: height / 2))
        }.frame(height: height)
    }
}

// Wrapping row: every habit stays reachable (no prefix(4) cut-off), the panel grows a line if needed.
struct Flow: Layout {
    var spacing: CGFloat = 6
    func rows(_ w: CGFloat, _ subs: Subviews) -> [[(Int, CGSize)]] {
        var rows: [[(Int, CGSize)]] = [[]]; var x: CGFloat = 0
        for (i, v) in subs.enumerated() {
            let s = v.sizeThatFits(.unspecified)
            if x + s.width > w && !rows[rows.count - 1].isEmpty { rows.append([]); x = 0 }
            rows[rows.count - 1].append((i, s)); x += s.width + spacing
        }
        return rows
    }
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let w = proposal.width ?? 480
        let r = rows(w, subviews)
        let h = r.map { $0.map(\.1.height).max() ?? 0 }.reduce(0, +) + spacing * CGFloat(max(0, r.count - 1))
        return CGSize(width: w, height: h)
    }
    func placeSubviews(in b: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var y = b.minY
        for row in rows(b.width, subviews) {
            var x = b.minX; let h = row.map(\.1.height).max() ?? 0
            for (i, s) in row { subviews[i].place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s)); x += s.width + spacing }
            y += h + spacing
        }
    }
}

// MARK: - Island view

struct IslandView: View {
    @ObservedObject var m: Island
    let notch: Notch
    @FocusState private var focused: Bool

    var session: Session? { m.session }
    var current: String { session?.recent?.last ?? session?.labels.last?.label ?? "on_task" }
    var drifting: Drifting? { session?.drifting }
    var left: Double {
        guard let s = session else { return 0 }
        if let b = s.on_break, let u = b.until { return max(0, u - m.now) }
        return max(0, s.ends_at - m.now)
    }
    var progress: Double {
        guard let s = session else { return 0 }
        return min(1, max(0, (m.now - s.started_at) / max(1, s.ends_at - s.started_at)))
    }
    var showNote: Bool { (m.state?.witness ?? "") == "nvidia" }   // on-device/mock notes are internals, not copy
    var corner: (CGFloat, CGFloat) { m.mode == .collapsed ? (6, 12) : (12, 30) }

    var body: some View {
        let w = width(for: m.mode, notch: notch, island: m)
        VStack(spacing: 0) {
            content
                .padding(.horizontal, m.mode == .collapsed ? (session == nil ? 12 : 16) : 28)
                .padding(.bottom, m.mode == .collapsed ? 0 : 20)
                .frame(width: w, alignment: .top)
                .fixedSize(horizontal: false, vertical: true)
                .background(alignment: .top) {
                    NotchShape(top: corner.0, bottom: corner.1)
                        .fill(Color.black)
                        .shadow(color: .black.opacity(m.mode == .collapsed ? 0 : 0.35), radius: 18, y: 8)
                }
                .overlay {
                    if drifting != nil && m.mode == .collapsed {
                        Glow(colour: red, top: corner.0, bottom: corner.1)
                    } else if m.pending != nil {
                        Glow(colour: coral, top: corner.0, bottom: corner.1)
                    }
                }
                .background(GeometryReader { g in Color.clear.preference(key: SizeKey.self, value: g.size) })
                .onPreferenceChange(SizeKey.self) { s in MainActor.assumeIsolated { m.measured = s } }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .animation(.spring(response: 0.42, dampingFraction: 0.8), value: m.mode)
        .animation(.spring(response: 0.42, dampingFraction: 0.8), value: session?.id)
        .animation(.spring(response: 0.42, dampingFraction: 0.8), value: drifting?.label)
        .preferredColorScheme(.dark)
    }

    @ViewBuilder var content: some View {
        switch m.mode {
        case .collapsed: collapsed
        case .expanded: expanded.transition(.opacity.combined(with: .scale(scale: 0.96, anchor: .top)))
        case .alert:
            Group {
                if m.alert?.kind == "verdict" { verdictView } else { alertView }
            }.transition(.opacity.combined(with: .scale(scale: 0.96, anchor: .top)))
        }
    }

    // MARK: Collapsed — wings either side of the physical notch.

    var collapsed: some View {
        HStack(spacing: 0) {
            if let s = session {
                liveLeftWing(s).frame(maxWidth: .infinity, alignment: .leading)
                Color.clear.frame(width: notch.width)
                HStack(spacing: 7) {
                    let tint: Color = s.on_break != nil ? amber : current == "on_task" ? cream.opacity(0.92) : (palette[current] ?? cream)
                    Text(mmss(left)).font(rounded(12.5, .semibold)).monospacedDigit()
                        .foregroundStyle(tint).contentTransition(.numericText())
                    Ring(progress: progress, colour: s.on_break != nil ? amber : (palette[current] ?? coral), width: 2.5)
                        .frame(width: 16, height: 16)
                }.frame(maxWidth: .infinity, alignment: .trailing)
            } else if m.reply != nil {
                Image(systemName: m.replyFailed ? "exclamationmark" : "checkmark")
                    .font(.system(size: 10, weight: .bold)).foregroundStyle(m.replyFailed ? red : green)
                    .frame(maxWidth: .infinity, alignment: .leading)
                Color.clear.frame(width: notch.width)
                Text(m.replyFailed ? "Offline" : "Noted").font(rounded(11, .medium)).foregroundStyle(.white.opacity(0.55))
                    .lineLimit(1).fixedSize().frame(maxWidth: .infinity, alignment: .trailing)
            } else if notch.hasNotch {
                statusDot.frame(maxWidth: .infinity, alignment: .leading)
                Color.clear.frame(width: notch.width)
                Text(m.state?.today?.tally ?? "").font(rounded(11, .semibold)).monospacedDigit()
                    .foregroundStyle(.white.opacity(0.5)).lineLimit(1).fixedSize()
                    .frame(maxWidth: .infinity, alignment: .trailing)
            } else {
                Spacer()
                Text("Alibi").font(.system(size: 12, weight: .semibold, design: .serif)).foregroundStyle(cream.opacity(0.85))
                statusDot.padding(.leading, 6)
                if let t = m.state?.today?.tally {
                    Text(t).font(rounded(11, .semibold)).monospacedDigit().foregroundStyle(.white.opacity(0.5)).padding(.leading, 6)
                }
                Spacer()
            }
        }
        .frame(height: notch.height)
    }

    @ViewBuilder func liveLeftWing(_ s: Session) -> some View {
        if let d = drifting {
            HStack(spacing: 6) {
                Pulse(colour: red, size: 6)
                Text(d.label == "phone" ? "On phone" : shortDrift(d)).font(rounded(12, .semibold))
                    .foregroundStyle(red).lineLimit(1)
            }
        } else if s.on_break != nil {
            HStack(spacing: 6) {
                Image(systemName: "cup.and.saucer.fill").font(.system(size: 10)).foregroundStyle(amber)
                Text("Break").font(rounded(12, .semibold)).foregroundStyle(amber).lineLimit(1)
            }
        } else {
            HStack(spacing: 7) {
                Pulse(colour: palette[current] ?? coral)
                Text(s.name).font(.system(size: 12.5, weight: .semibold)).foregroundStyle(cream).lineLimit(1)
            }
        }
    }

    func shortDrift(_ d: Drifting) -> String {
        switch d.label { case "phone": return "Phone"; case "absent": return "Away"; case "idle": return "Idle"
        default: return d.label_text.map { String($0.prefix(14)) } ?? "Off task" }
    }

    var statusDot: some View {
        Circle().fill(m.online ? green : (m.connecting || m.starting) ? Color.gray : amber).frame(width: 6, height: 6)
    }

    // MARK: Expanded

    var expanded: some View {
        VStack(alignment: .leading, spacing: 12) {
            header
            if !m.online && !m.connecting {
                offlineCard
            } else {
                if let s = session { sessionCard(s) }
                promptBar
            }
            if let r = m.reply {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    if m.replyFailed { Image(systemName: "exclamationmark.circle.fill").foregroundStyle(red).font(.system(size: 11)) }
                    Text(r).font(.system(size: 12.5)).foregroundStyle(cream.opacity(0.75))
                        .lineLimit(3).fixedSize(horizontal: false, vertical: true)
                }
            }
            if session == nil && !m.habits.isEmpty { chips.opacity(m.online ? 1 : 0.45) }
        }
        .onAppear { if m.pinned { DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { focused = true } } }
        .onChange(of: m.pinned) { _, p in if p { focused = true } }
    }

    var header: some View {
        HStack(spacing: 7) {
            Text("Alibi").font(.system(size: 13, weight: .semibold, design: .serif)).foregroundStyle(coral)
            Spacer()
            if (m.connecting || m.starting) && !m.online {
                ProgressView().controlSize(.mini).tint(.white)
                Text(m.starting ? "Starting…" : "Connecting…").font(.system(size: 11)).foregroundStyle(.white.opacity(0.45))
            } else {
                statusDot
                Text(m.online ? (session != nil ? "Watching · \(m.state?.witness_label ?? m.state?.witness ?? "")"
                                               : "Ready · \(m.state?.witness_label ?? "")")
                              : "Not watching")
                    .font(.system(size: 11, weight: .medium)).foregroundStyle(.white.opacity(0.5)).lineLimit(1)
            }
            if session == nil { Keycap(text: "⌥⌘A").padding(.leading, 4) }
            Button { NSApp.terminate(nil) } label: {
                Image(systemName: "power").font(.system(size: 10, weight: .semibold)).foregroundStyle(.white.opacity(0.4))
            }.buttonStyle(.plain).help("Quit Alibi (stops the daemon, camera off)").padding(.leading, 4)
        }
        .frame(height: notch.height - 4, alignment: .bottom)
    }

    var promptBar: some View {
        HStack(spacing: 10) {
            Image(systemName: m.busy ? "ellipsis" : "eye").foregroundStyle(coral).frame(width: 16)
            TextField("", text: $m.draft, prompt: Text(session == nil ? "What are you about to do?" : "Add a note, or type end")
                .foregroundStyle(.white.opacity(0.35)))
                .textFieldStyle(.plain).font(.system(size: 15)).foregroundStyle(cream)
                .focused($focused)
                .onSubmit { Task { await m.send(m.draft); m.unpinSoon() } }
                .onExitCommand { Controller.shared?.collapse() }
            if !focused && m.draft.isEmpty && !m.pinned {
                Text("Click to type").font(.system(size: 10.5)).foregroundStyle(.white.opacity(0.3)).fixedSize()
            }
            if session != nil {
                Button { Task { await m.end() } } label: {
                    Text("End").font(.system(size: 11.5, weight: .semibold)).padding(.horizontal, 10).padding(.vertical, 4)
                        .background(Capsule().fill(Color.white.opacity(0.1)))
                }.buttonStyle(.plain).foregroundStyle(cream)
            }
            Button { NSWorkspace.shared.open(URL(string: API)!) } label: {
                Image(systemName: "arrow.up.right").font(.system(size: 11, weight: .semibold))
                    .padding(6).background(Circle().fill(Color.white.opacity(0.1)))
            }.buttonStyle(.plain).foregroundStyle(cream).help("Open dashboard")
        }
        .padding(.horizontal, 14).padding(.vertical, 11)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color.white.opacity(0.07)))
        .contentShape(Rectangle())
        .simultaneousGesture(TapGesture().onEnded { Controller.shared?.focusPanel(); focused = true })
    }

    var offlineCard: some View {
        HStack(spacing: 12) {
            if m.starting {
                ProgressView().controlSize(.small).tint(cream).frame(width: 8, height: 8)
            } else {
                Circle().fill(amber).frame(width: 8, height: 8)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(m.starting ? "Starting Alibi…" : "Alibi isn't watching").font(.system(size: 14, weight: .semibold)).foregroundStyle(cream)
                Text(m.starting ? "Usually a few seconds."
                                : "Nothing is recorded until it runs.").font(.system(size: 11.5)).foregroundStyle(.white.opacity(0.5))
            }
            Spacer()
            PillButton(title: "Open logs") { Controller.openLogs() }
            PillButton(title: "Start", primary: true) {
                guard !m.starting else { return }
                m.reply = nil; m.replyFailed = false
                m.startingUntil = Date().timeIntervalSince1970 + 20; m.now = Date().timeIntervalSince1970
                Controller.startDaemon()
            }
            .disabled(m.starting).opacity(m.starting ? 0.5 : 1)
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color.white.opacity(0.07)))
    }

    var chips: some View {
        let hs = m.habits.filter { $0.modality != "strava" }
        return Flow(spacing: 6) {
                ForEach(Array(hs.enumerated()), id: \.element) { i, h in
                    let mins = h.default_min ?? 25
                    Button { Task { await m.send("\(h.key) for \(mins) minutes") } } label: {
                        HStack(spacing: 5) {
                            if i < 9 { Text("\(i + 1)").font(rounded(9.5, .bold)).foregroundStyle(.white.opacity(0.3)) }
                            Text(h.name).font(.system(size: 12, weight: .medium)).lineLimit(1).fixedSize()
                            Text("\(mins)m").font(rounded(10.5, .medium)).monospacedDigit().opacity(0.45).lineLimit(1).fixedSize()
                        }
                        .padding(.horizontal, 10).frame(height: 26)
                        .background(Capsule().strokeBorder(Color.white.opacity(0.16)))
                        .contentShape(Capsule())
                    }
                    .buttonStyle(.plain).foregroundStyle(cream)
                    .keyboardShortcut(KeyEquivalent(Character("\(min(i + 1, 9))")), modifiers: .command)
                    .help("⌘\(i + 1) · right-click for another length")
                    .contextMenu {
                        ForEach([15, 25, 45, 60], id: \.self) { n in
                            Button("\(h.name) for \(n) min") { Task { await m.send("\(h.key) for \(n) minutes") } }
                        }
                    }
                }
                Button { Task { await m.send("report") } } label: {
                    Text("Report").font(.system(size: 12, weight: .medium)).padding(.horizontal, 10).frame(height: 26)
                        .background(Capsule().fill(coral.opacity(0.18)))
                }.buttonStyle(.plain).foregroundStyle(coral)
        }
    }

    func sessionCard(_ s: Session) -> some View {
        let warming = s.warming_up ?? ((s.samples ?? s.labels.count) < 6)
        let recentR = s.recent_on_task ?? s.on_task_so_far ?? 1
        let heroColour = recentR >= 0.67 ? green : recentR >= 0.34 ? amber : red
        return HStack(alignment: .center, spacing: 16) {
            ZStack {
                Ring(progress: progress, colour: s.on_break != nil ? amber : (palette[current] ?? coral), width: 3.5)
                Image(systemName: s.on_break != nil ? "cup.and.saucer.fill" : s.modality == "digital" ? "macwindow" : "camera.fill")
                    .font(.system(size: 13)).foregroundStyle(.white.opacity(0.55))
            }.frame(width: 44, height: 44)
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(s.name).font(.system(size: 22, weight: .regular, design: .serif)).foregroundStyle(cream)
                        .lineLimit(1).fixedSize()
                    Text("\(mmss(left)) left · \(s.declared_min) min").font(rounded(11.5, .medium)).monospacedDigit()
                        .foregroundStyle(.white.opacity(0.45)).lineLimit(1).fixedSize()
                }
                if s.labels.isEmpty {
                    Text("First look in a few seconds…").font(.system(size: 11)).foregroundStyle(.white.opacity(0.4))
                } else {
                    Strip(labels: s.labels.suffix(60).map(\.label), height: 7)
                        .frame(width: min(220, CGFloat(min(60, s.labels.count)) * 14), alignment: .leading)
                }
                statusLine(s)
            }
            Spacer(minLength: 0)
            VStack(alignment: .trailing, spacing: 1) {
                if warming || s.on_task_so_far == nil {
                    Text("—").font(rounded(26, .semibold)).foregroundStyle(.white.opacity(0.4))
                    Text("warming up").font(.system(size: 10.5)).foregroundStyle(.white.opacity(0.4))
                } else if let r = s.on_task_so_far {
                    Text("\(Int((r * 100).rounded()))%").font(rounded(26, .semibold)).monospacedDigit()
                        .foregroundStyle(heroColour).contentTransition(.numericText())
                    Text(drifting != nil ? "on task · drifting" : "on task").font(.system(size: 10.5))
                        .foregroundStyle(drifting != nil ? red.opacity(0.9) : .white.opacity(0.4))
                }
            }.fixedSize()
        }
    }

    @ViewBuilder func statusLine(_ s: Session) -> some View {
        if let d = s.drifting {
            Text("\(d.label_text ?? human(d.label)) for \(mmss(d.since_s ?? 0))").font(.system(size: 11.5, weight: .medium))
                .foregroundStyle(red).lineLimit(1)
        } else if let b = s.on_break {
            Text("On a break · back in \(mmss(b.left_s ?? left))").font(.system(size: 11.5, weight: .medium)).foregroundStyle(amber)
        } else if let l = s.last_seen {
            let ago = l.ago_s.map { $0 < 5 ? "just now" : "\(Int($0)) s ago" } ?? ""
            let note = showNote ? (l.note.map { " · \($0)" } ?? "") : ""
            Text("\(l.label_text ?? human(l.label)) · \(ago)\(note)").font(.system(size: 11.5))
                .foregroundStyle((palette[l.label] ?? .gray).opacity(0.95)).lineLimit(1)
        } else if let n = s.labels.last {
            Text(n.label_text ?? human(n.label)).font(.system(size: 11.5)).foregroundStyle(palette[n.label] ?? .gray).lineLimit(1)
        }
    }

    // MARK: Alerts

    func actions(for a: AlertEv) -> [AlertAction] {
        if let x = a.actions, !x.isEmpty { return x }
        switch a.kind {
        case "nudge": return [AlertAction(label: "I'm back", say: "back", url: nil, dismiss: nil),
                              AlertAction(label: "It's on task", say: "it's on task", url: nil, dismiss: nil),
                              AlertAction(label: "Snooze 5m", say: "snooze 5", url: nil, dismiss: nil)]
        case "verdict":
            let id = a.session_id.map(String.init) ?? ""
            return [AlertAction(label: "Watch reel", say: nil, url: "/api/reel?session=\(id)", dismiss: nil),
                    AlertAction(label: "Fix samples", say: nil, url: "/#session-\(id)", dismiss: nil)]
        default: return [AlertAction(label: "OK", say: nil, url: nil, dismiss: true)]
        }
    }

    func actionRow(_ a: AlertEv, tint: Color) -> some View {
        HStack(spacing: 8) {
            ForEach(Array(actions(for: a).enumerated()), id: \.offset) { i, x in
                PillButton(title: x.label, primary: i == 0, tint: tint) { m.act(x) }
            }
            Spacer()
            Button { m.dismissAlert() } label: {
                Image(systemName: "xmark").font(.system(size: 10, weight: .bold)).foregroundStyle(.white.opacity(0.4))
                    .frame(width: 24, height: 24).background(Circle().fill(Color.white.opacity(0.07)))
            }.buttonStyle(.plain).help("Dismiss (Esc)")
        }
    }

    var alertView: some View {
        let a = m.alert ?? AlertEv(id: 0, kind: "info", text: "")
        let tint: Color = a.kind == "nudge" ? red : coral
        let title: String = switch a.kind {
            case "nudge": "Caught you"; case "pace": "Behind pace"; case "recap": "Today's reel"; case "report": "Report"
            default: "Alibi" }
        return VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 7) {
                Image(systemName: a.kind == "nudge" ? "eye.fill" : a.kind == "pace" ? "clock.fill" : "sparkles")
                    .font(.system(size: 11, weight: .semibold)).foregroundStyle(tint)
                Text(title).font(.system(size: 12.5, weight: .semibold)).foregroundStyle(tint)
                Spacer()
                if let h = a.habit_label ?? session?.name {
                    Text(h).font(.system(size: 11, weight: .medium)).foregroundStyle(.white.opacity(0.45))
                }
            }.frame(height: notch.height - 4, alignment: .bottom)
            Text(a.text).font(.system(size: 16, weight: .regular, design: .serif)).foregroundStyle(cream)
                .lineLimit(4).fixedSize(horizontal: false, vertical: true)
            actionRow(a, tint: tint)
        }
    }

    var verdictView: some View {
        let a = m.alert ?? AlertEv(id: 0, kind: "verdict", text: "")
        let rv = m.state?.recent_verdict.flatMap { v in (a.session_id == nil || v.id == a.session_id) ? v : nil }
        let v = a.verdict ?? rv?.verdict
        let tint = verdictColour(v)
        let ratio = a.ratio ?? rv?.on_task_ratio
        let labels = rv?.labels ?? []
        let counts = Dictionary(grouping: labels, by: \.label).mapValues(\.count)
        let detail = (["\(labels.count) looks"] + ["phone", "absent", "idle", "off_task"].compactMap { k in
            counts[k].map { "\(human(k).lowercased()) ×\($0)" } }).joined(separator: " · ")
        let name = a.habit_label ?? rv?.label ?? a.habit.map(displayName) ?? "Session"
        return VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 7) {
                Text("Verdict").font(.system(size: 12.5, weight: .semibold)).foregroundStyle(coral)
                Spacer()
                if let rv { Text("\(rv.elapsed_min ?? rv.declared_min) of \(rv.declared_min) min")
                    .font(rounded(11, .medium)).monospacedDigit().foregroundStyle(.white.opacity(0.45)) }
            }.frame(height: notch.height - 4, alignment: .bottom)
            HStack(alignment: .center, spacing: 12) {
                Text((v ?? "ended").uppercased()).font(.system(size: 13, weight: .heavy, design: .rounded)).tracking(1.2)
                    .foregroundStyle(Color.black.opacity(0.85))
                    .padding(.horizontal, 11).frame(height: 26).background(Capsule().fill(tint))
                Text(name).font(.system(size: 24, design: .serif)).foregroundStyle(cream).lineLimit(1)
                Spacer(minLength: 8)
                if let r = ratio {
                    VStack(alignment: .trailing, spacing: 0) {
                        Text("\(Int((r * 100).rounded()))%").font(rounded(30, .bold)).monospacedDigit().foregroundStyle(tint)
                        Text("on task").font(.system(size: 10.5)).foregroundStyle(.white.opacity(0.45))
                    }.fixedSize()
                }
            }
            if !labels.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Strip(labels: labels.map(\.label), height: 8)
                    Text(detail).font(rounded(11, .medium)).foregroundStyle(.white.opacity(0.5)).lineLimit(1)
                }
            }
            Text(rv?.summary.map { _ in a.text } ?? a.text).font(.system(size: 13.5, design: .serif))
                .foregroundStyle(cream.opacity(0.8)).lineLimit(3).fixedSize(horizontal: false, vertical: true)
            if !labels.isEmpty { thumbRow(labels) }
            actionRow(a, tint: tint)
        }
    }

    // 5 frames: every off-task look first (that's the evidence), padded with evenly spaced on-task ones, in time order.
    func thumbRow(_ labels: [LabelEv]) -> some View {
        let withFrames = labels.filter { $0.frame_url != nil }
        var pick = Array(withFrames.filter { $0.label != "on_task" }.prefix(3))
        let on = withFrames.filter { $0.label == "on_task" }
        let need = max(0, 5 - pick.count)
        if need > 0 && !on.isEmpty {
            for i in 0..<min(need, on.count) { pick.append(on[i * on.count / min(need, on.count)]) }
        }
        pick.sort { $0.ts < $1.ts }
        return HStack(spacing: 8) {
            ForEach(pick, id: \.self) { l in
                ZStack(alignment: .bottom) {
                    Group {
                        if let u = l.frame_url, let img = m.thumb(u) {
                            Image(nsImage: img).resizable().aspectRatio(contentMode: .fill)
                        } else {
                            Color.white.opacity(0.06)
                        }
                    }
                    .frame(maxWidth: .infinity).frame(height: 62).clipped()
                    Rectangle().fill(palette[l.label] ?? .gray).frame(height: 3)
                }
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Color.white.opacity(0.08), lineWidth: 0.5))
            }
        }
    }
}

// MARK: - Daemon ownership (Alibi.app)

final class DaemonOwner {
    static let shared = DaemonOwner()
    var proc: Process?
    private var hooked = false
    private var spawning = false
    private let lock = NSLock()
    /// True when we spawned a daemon and it has already exited.
    var exited: Bool { lock.lock(); defer { lock.unlock() }; return proc.map { !$0.isRunning } ?? false }

    static func logPath(root: String) -> String {
        let env = ProcessInfo.processInfo.environment["ALIBI_DATA_DIR"].flatMap { $0.isEmpty ? nil : $0 }
        return (env ?? root + "/data") + "/logs/daemon.log"
    }

    func start(root: String) {
        // Already booting/running: never spawn a second daemon (the first would be orphaned).
        lock.lock()
        if spawning || proc?.isRunning == true { lock.unlock(); return }
        spawning = true; proc = nil; lock.unlock()   // drop a dead previous child so `exited` doesn't misfire
        defer { lock.lock(); spawning = false; lock.unlock() }
        let sem = DispatchSemaphore(value: 0)
        var up = false
        URLSession.shared.dataTask(with: URL(string: API + "/api/state")!) { _, r, _ in
            up = (r as? HTTPURLResponse)?.statusCode == 200; sem.signal()
        }.resume()
        _ = sem.wait(timeout: .now() + 1.5)
        if up { return }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: root + "/.venv/bin/python")
        p.arguments = ["-m", "alibi.daemon"]
        p.currentDirectoryURL = URL(fileURLWithPath: root)
        let logPath = DaemonOwner.logPath(root: root)
        try? FileManager.default.createDirectory(atPath: (logPath as NSString).deletingLastPathComponent, withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: logPath) { FileManager.default.createFile(atPath: logPath, contents: nil) }
        if let log = FileHandle(forWritingAtPath: logPath) {
            log.seekToEndOfFile(); p.standardOutput = log; p.standardError = log
        }
        do { try p.run() } catch { return }
        lock.lock(); proc = p; lock.unlock()
        if !hooked {
            hooked = true
            for sig in [SIGTERM, SIGINT] {
                signal(sig) { _ in DaemonOwner.shared.stop(); exit(0) }
            }
            atexit { DaemonOwner.shared.stop() }
        }
    }

    func stop() { proc?.terminate(); proc = nil }
}

// Repo root: Alibi.app carries it in root.txt; bin/alibi-island lives one level down from it.
let repoRoot: String? = {
    if let r = Bundle.main.url(forResource: "root", withExtension: "txt")
        .flatMap({ try? String(contentsOf: $0, encoding: .utf8) })?.trimmingCharacters(in: .whitespacesAndNewlines) { return r }
    let exe = URL(fileURLWithPath: CommandLine.arguments[0]).resolvingSymlinksInPath()
    let up = exe.deletingLastPathComponent().deletingLastPathComponent().path
    return FileManager.default.fileExists(atPath: up + "/alibi/daemon.py") ? up : nil
}()

// MARK: - Window

final class Panel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

@MainActor
final class Controller {
    let island = Island()
    var panel: Panel!
    var notch: Notch!
    var collapseAt: Date?
    var enteredAt: Date?
    var wasInside = false
    var previousApp: NSRunningApplication?

    func start() {
        let screen = NSScreen.screens.first { $0.safeAreaInsets.top > 0 } ?? NSScreen.main!
        notch = Notch(screen: screen)
        let W: CGFloat = 640, H: CGFloat = 460
        let f = screen.frame
        panel = Panel(contentRect: NSRect(x: f.midX - W / 2, y: f.maxY - H, width: W, height: H),
                      styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.level = NSWindow.Level(rawValue: NSWindow.Level.statusBar.rawValue + 8)
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary, .ignoresCycle]
        panel.isMovable = false
        panel.becomesKeyOnlyIfNeeded = true
        panel.contentView = NSHostingView(rootView: IslandView(m: island, notch: notch))
        panel.orderFrontRegardless()
        panel.ignoresMouseEvents = true

        Task { await island.poll() }
        Controller.shared = self
        registerHotkey()
        NSEvent.addGlobalMonitorForEvents(matching: [.leftMouseDown]) { _ in
            MainActor.assumeIsolated {
                if self.island.pinned && self.island.mode == .expanded { self.collapse() }
            }
        }
        // Esc collapses in every mode (not only when the text field has focus).
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { e in
            if e.keyCode == 53 {
                MainActor.assumeIsolated { Controller.shared?.collapse() }
                return nil
            }
            return e
        }
        Timer.scheduledTimer(withTimeInterval: 1 / 30, repeats: true) { _ in
            MainActor.assumeIsolated { self.track() }
        }
    }

    static var shared: Controller?

    static func startDaemon() {
        guard let root = repoRoot else { return }
        DispatchQueue.global().async { DaemonOwner.shared.start(root: root) }
    }

    static func openLogs() {
        guard let root = repoRoot else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: DaemonOwner.logPath(root: root)))
    }

    func collapse() {
        island.pinned = false
        island.draft = ""
        island.alertTask?.cancel()
        withAnimation(.spring(response: 0.4, dampingFraction: 0.85)) { island.mode = .collapsed }
        giveBackFocus()
    }

    func giveBackFocus() {
        if panel.isKeyWindow { panel.resignKey() }
        if NSApp.isActive, let p = previousApp, p != NSRunningApplication.current { p.activate() }
        previousApp = nil
    }

    // Only an explicit click on the field or the hotkey makes the panel key.
    func focusPanel() {
        if previousApp == nil { previousApp = NSWorkspace.shared.frontmostApplication }
        island.pinned = true
        panel.makeKey()
    }

    func summon() {
        if island.mode != .collapsed && island.pinned { collapse(); return }
        previousApp = NSWorkspace.shared.frontmostApplication
        island.pinned = true
        island.pending = nil
        island.mode = .expanded
        NSApp.activate(ignoringOtherApps: true)
        panel.makeKeyAndOrderFront(nil)
    }

    func registerHotkey() {
        var ref: EventHotKeyRef?
        let id = EventHotKeyID(signature: OSType(0x414C_4249), id: 1)   // 'ALBI'
        let status = RegisterEventHotKey(UInt32(kVK_ANSI_A), UInt32(cmdKey | optionKey), id,
                                         GetApplicationEventTarget(), 0, &ref)
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
            DispatchQueue.main.async { MainActor.assumeIsolated { Controller.shared?.summon() } }
            return noErr
        }, 1, &spec, nil, nil)
        print(status == noErr ? "hotkey ⌥⌘A registered" : "hotkey failed: \(status)")
        fflush(stdout)
    }

    // Hover (after a dwell) -> peek, no focus; out (and nothing typed) -> collapse. Clicks pass through elsewhere.
    func track() {
        let p = NSEvent.mouseLocation
        let f = notch.screen.frame
        var sz = island.measured
        if sz.width < 10 { sz = CGSize(width: width(for: island.mode, notch: notch, island: island), height: notch.height) }
        let hit = NSRect(x: f.midX - sz.width / 2, y: f.maxY - sz.height, width: sz.width, height: sz.height)
        let inside = hit.insetBy(dx: -4, dy: -4).contains(p)
        panel.ignoresMouseEvents = !inside
        island.hovering = inside
        defer { wasInside = inside }

        // A queued alert surfaces as soon as the user is done typing.
        if let a = island.pending, island.mode == .collapsed { island.show(alert: a) }

        if inside {
            collapseAt = nil
            if !wasInside { enteredAt = Date() }
            if island.mode == .alert {
                island.alertTask?.cancel()          // pause auto-dismiss while the pointer is on it
            } else if island.mode == .collapsed, let t = enteredAt, Date().timeIntervalSince(t) > 0.18 {
                NSHapticFeedbackManager.defaultPerformer.perform(.alignment, performanceTime: .now)
                withAnimation(.spring(response: 0.42, dampingFraction: 0.8)) { island.mode = .expanded }
            }
        } else {
            enteredAt = nil
            if wasInside && island.mode == .alert { island.scheduleDismiss(after: 3) }
            if island.mode == .expanded && island.draft.isEmpty && !island.busy && !island.pinned {
                if collapseAt == nil { collapseAt = Date().addingTimeInterval(0.35) }
                if let c = collapseAt, Date() > c {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.85)) { island.mode = .collapsed }
                    collapseAt = nil
                    giveBackFocus()
                    if island.reply != nil {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 4) { self.island.reply = nil }
                    }
                }
            }
        }
    }
}

// --snapshot DIR [--state FILE.json] [--prefix P]: render every mode offscreen to PNGs
// (visual check without screen-recording permission). --state renders a saved /api/state payload.
@MainActor func snapshot(to dir: String, stateFile: String?, prefix: String) async {
    let m = Island()
    if let f = stateFile, let d = FileManager.default.contents(atPath: f) {
        m.state = try? JSONDecoder().decode(StateResp.self, from: d)
    } else {
        m.state = await m.get("/api/state")
    }
    m.online = m.state != nil; m.connecting = false
    if stateFile != nil, let n = m.state?.now { m.now = n }
    if let h = m.state?.habits { m.habits = h }
    let screen = NSScreen.screens.first { $0.safeAreaInsets.top > 0 } ?? NSScreen.main!
    let notch = Notch(screen: screen)
    // Preload every frame the verdict view might show (ImageRenderer can't wait on network).
    for l in m.state?.recent_verdict?.labels ?? [] { if let u = l.frame_url { await m.loadThumb(u) } }

    let nudge = m.state?.alert?.kind == "nudge" ? m.state!.alert! :
        AlertEv(id: 1, kind: "nudge", text: "You said drawing. I've seen your phone for 30 seconds.", habit_label: "Drawing")
    var renders: [(String, Mode, AlertEv?, Bool)] = [
        ("collapsed", .collapsed, nil, true), ("expanded", .expanded, nil, true), ("alert", .alert, nudge, true),
        ("offline_collapsed", .collapsed, nil, false), ("offline_expanded", .expanded, nil, false),
        ("offline_starting", .expanded, nil, false),
    ]
    if let rv = m.state?.recent_verdict {
        let a = m.state?.alert?.kind == "verdict" ? m.state!.alert! :
            AlertEv(id: 2, kind: "verdict", text: rv.summary ?? "", session_id: rv.id, habit_label: rv.label,
                    verdict: rv.verdict, ratio: rv.on_task_ratio)
        renders.append(("verdict", .alert, a, true))
    }
    let saved = m.state
    for (name, mode, alert, online) in renders {
        m.online = online
        m.state = online ? saved : nil
        m.mode = mode
        m.alert = alert
        m.startingUntil = name == "offline_starting" ? m.now + 20 : 0
        let v = ZStack(alignment: .top) {
            Color(white: 0.82)   // stand-in for the menu bar / wallpaper
            IslandView(m: m, notch: notch)
        }.frame(width: 640, height: 460)
        let r = ImageRenderer(content: v)
        r.scale = 2
        if let img = r.nsImage, let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
           let png = rep.representation(using: .png, properties: [:]) {
            try? png.write(to: URL(fileURLWithPath: "\(dir)/\(prefix)island_\(name).png"))
        }
    }
    print("notch \(notch.width)x\(notch.height) hasNotch=\(notch.hasNotch) online=\(saved != nil)")
}

let args = CommandLine.arguments
func arg(_ k: String) -> String? { args.firstIndex(of: k).flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil } }
if let dir = arg("--snapshot") {
    Task { @MainActor in await snapshot(to: dir, stateFile: arg("--state"), prefix: arg("--prefix") ?? ""); exit(0) }
    RunLoop.main.run()
} else {
    // Inside Alibi.app: own the daemon's lifetime (start it if nothing answers, stop it when we quit).
    if Bundle.main.url(forResource: "root", withExtension: "txt") != nil, let root = repoRoot {
        DaemonOwner.shared.start(root: root)
    }
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    let controller = MainActor.assumeIsolated { Controller() }
    MainActor.assumeIsolated { controller.start() }
    app.run()
}
