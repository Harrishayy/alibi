// Alibi Island — a Dynamic-Island-style bar that lives in the MacBook notch.
// Collapsed: the session on the left wing and a countdown ring on the right. When idle it shows the next planned
// block ("Drawing 18:00", or "▶ Drawing · now") on the left and a segmented "today" ring on the right.
// Hover (after a short, still dwell) peeks the panel without stealing focus; click the field or press ⌥⌘A to type.
// Nudges, planned blocks, synced runs and verdicts expand it on their own, with buttons. Talks to http://127.0.0.1:8765.
import AppKit
import Carbon.HIToolbox
import SwiftUI

let API = ProcessInfo.processInfo.environment["ALIBI_API"] ?? "http://127.0.0.1:8765"

// MARK: - API models (new fields optional so an older daemon still decodes)

/// A JSON scalar, so alert action bodies ({key, min}) round-trip without a schema.
enum JSONValue: Decodable, Hashable {
    case num(Double), bool(Bool), str(String), null
    init(from d: Decoder) throws {
        let c = try d.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let n = try? c.decode(Double.self) { self = .num(n) }
        else if let b = try? c.decode(Bool.self) { self = .bool(b) }
        else if let s = try? c.decode(String.self) { self = .str(s) }
        else { self = .null }
    }
    var any: Any {
        switch self {
        case .num(let n): return n == n.rounded() && abs(n) < 1e15 ? Int(n) as Any : n
        case .bool(let b): return b
        case .str(let s): return s
        case .null: return NSNull()
        }
    }
}

struct LabelEv: Decodable, Hashable {
    let ts: Double; let label: String; let note: String
    let label_text: String?; let frame_url: String?
}
struct LastSeen: Decodable { let label: String; let label_text: String?; let note: String?; let source: String?; let ago_s: Double? }
struct Drifting: Decodable { let label: String; let label_text: String?; let since_s: Double?; let samples: Int? }
struct OnBreak: Decodable { let until: Double?; let left_s: Double? }
/// Screen-tracked habits: share of checks per window ("ChatGPT", 0.67, off_task). Titles go through placeName.
struct WindowShare: Decodable, Hashable { let title: String; let share: Double; let label: String }
/// Merge windows into plain places ("Slack — Arun (DM) - HyBird - Slack" -> "Slack"), biggest first.
func places(_ ws: [WindowShare]) -> [(name: String, share: Double, label: String)] {
    var order: [String] = []; var share: [String: Double] = [:]; var on: [String: Double] = [:]
    for w in ws {
        let n = placeName(w.title)
        if share[n] == nil { order.append(n) }
        share[n, default: 0] += w.share
        if w.label == "on_task" { on[n, default: 0] += w.share }
    }
    return order.map { n in (n, share[n]!, (on[n] ?? 0) * 2 >= share[n]! ? "on_task" : "off_task") }
        .sorted { $0.share > $1.share }
}
/// "Mostly on ChatGPT (67%), then Slack (33%)" — never a raw tab title.
func placesLine(_ ws: [WindowShare]) -> String? {
    let ps = places(ws)
    guard let a = ps.first else { return nil }
    let pct = { (x: Double) in "\(Int((x * 100).rounded()))%" }
    if ps.count == 1 || a.share >= 0.95 { return "All on \(a.name)" }
    let b = ps[1]
    return "Mostly on \(a.name) (\(pct(a.share))), then \(b.name) (\(pct(b.share)))"
}
/// Screen-only evidence: one segment per place, as wide as its share of the checks (on-task places first).
struct PlaceStrip: View {
    let ws: [WindowShare]; var height: CGFloat = 8; var rest: Double = 0
    var body: some View {
        let ps = places(ws).sorted { ($0.label == "on_task" ? 0 : 1, -$0.share) < ($1.label == "on_task" ? 0 : 1, -$1.share) }
        let total = max(0.0001, ps.map(\.share).reduce(0, +))
        GeometryReader { g in
            let w = max(4, g.size.width * (1 - rest))
            HStack(spacing: 1.5) {
                HStack(spacing: 1.5) {
                    ForEach(Array(ps.enumerated()), id: \.offset) { i, p in
                        Rectangle().fill((palette[p.label] ?? .gray).opacity(i % 2 == 0 ? 1 : 0.7))
                            .frame(width: max(2, (w - 1.5 * CGFloat(ps.count - 1)) * p.share / total))
                    }
                }.frame(width: w, alignment: .leading)
                if rest > 0.01 { Rectangle().fill(Color.white.opacity(0.12)) }
            }
            .frame(width: g.size.width, height: height)
            .clipShape(RoundedRectangle(cornerRadius: height / 2))
        }.frame(height: height)
    }
}
struct Session: Decodable {
    let id: Int; let habit: String; let label: String?; let modality: String; let declared_min: Int
    let started_at: Double; let ends_at: Double
    let labels: [LabelEv]; let on_task_so_far: Double?; let last_frame_url: String?
    let samples: Int?; let warming_up: Bool?; let recent: [String]?; let recent_on_task: Double?
    let last_seen: LastSeen?; let drifting: Drifting?; let on_break: OnBreak?
    let nudges: Int?; let strikes: Int?; let windows: [WindowShare]?
    var name: String { label ?? displayName(habit) }
}
struct AlertAction: Decodable, Equatable, Hashable {
    let label: String; let say: String?; let url: String?; let dismiss: Bool?
    let post: String?; let body: [String: JSONValue]?
    init(_ label: String, say: String? = nil, url: String? = nil, post: String? = nil,
         body: [String: JSONValue]? = nil, dismiss: Bool? = nil) {
        self.label = label; self.say = say; self.url = url; self.post = post; self.body = body; self.dismiss = dismiss
    }
}
struct AlertEv: Decodable, Equatable {
    let id: Int64; let ts: Double?; let kind: String; let text: String; let image_url: String?
    let session_id: Int?; let habit: String?; let habit_label: String?; let verdict: String?; let ratio: Double?
    let actions: [AlertAction]?; let reel_url: String?
    // planned (calendar auto-start)
    let minutes: Int?; let block_key: String?; let start: Double?; let end: Double?; let at: String?
    let late: Bool?; let check: String?
    // verdict / nudge / synced extras
    let ended_early: Bool?; let label: String?; let title: String?; let detail: String?; let progress: String?
    init(id: Int64, kind: String, text: String, ts: Double? = nil, session_id: Int? = nil, habit: String? = nil,
         habit_label: String? = nil, verdict: String? = nil, ratio: Double? = nil, actions: [AlertAction]? = nil,
         minutes: Int? = nil, block_key: String? = nil, start: Double? = nil, end: Double? = nil, at: String? = nil,
         check: String? = nil, label: String? = nil, title: String? = nil, detail: String? = nil, progress: String? = nil) {
        self.id = id; self.ts = ts; self.kind = kind; self.text = text; image_url = nil; self.session_id = session_id
        self.habit = habit; self.habit_label = habit_label; self.verdict = verdict; self.ratio = ratio
        self.actions = actions; reel_url = nil
        self.minutes = minutes; self.block_key = block_key; self.start = start; self.end = end; self.at = at
        late = nil; self.check = check; ended_early = nil; self.label = label; self.title = title
        self.detail = detail; self.progress = progress
    }
}
struct HabitRef: Codable, Hashable { let key: String; let label: String?; let modality: String; let default_min: Int?
    var name: String { label ?? displayName(key) }
}
struct Today: Decodable { let tally: String?; let habits_done: Int?; let habits_total: Int?; let verified_min: Int? }
struct Verdict: Decodable {
    let id: Int; let habit: String; let label: String?; let verdict: String?; let on_task_ratio: Double?
    let declared_min: Int; let elapsed_min: Int?; let labels: [LabelEv]; let summary: String?; let reel_url: String?
    let coverage: Double?; let windows: [WindowShare]?; let modality: String?
}
struct StateResp: Decodable {
    let now: Double?
    let session: Session?; let alert: AlertEv?; let witness: String; let witness_label: String?
    let habits: [HabitRef]?; let today: Today?; let recent_verdict: Verdict?; let status_text: String?
}
/// /api/calendar/plan?days=1 — today's planned blocks (from habits.yaml schedules, calendar connected or not).
struct PlanBlock: Decodable, Hashable {
    let key: String; let habit: String; let label: String?; let at: String; let min: Int
    let start: Double; let end: Double; let check: String?; let state: String; let state_text: String?
    var name: String { label ?? displayName(habit) }
    var startable: Bool { !["strava", "health"].contains(check ?? "") }
}
struct PlanResp: Decodable { let now: Double?; let blocks: [PlanBlock]; let next: PlanBlock?; let live: PlanBlock? }
struct OnboardingResp: Decodable { let needs_onboarding: Bool?; let onboarded: Bool? }

func displayName(_ key: String) -> String { key == "cpp" ? "C++" : key.prefix(1).uppercased() + key.dropFirst() }
let labelCopy = ["on_task": "On task", "phone": "On your phone", "absent": "Away from desk", "idle": "Idle", "off_task": "Off task"]
func human(_ l: String) -> String { labelCopy[l] ?? l.replacingOccurrences(of: "_", with: " ").capitalized }

/// "Google Chrome — Lo-fi beats - YouTube - Google Chrome" -> "YouTube". Never shows a raw tab title.
let knownPlaces: [(String, String)] = [
    ("youtube", "YouTube"), ("instagram", "Instagram"), ("tiktok", "TikTok"), ("reddit", "Reddit"),
    ("netflix", "Netflix"), ("twitter", "X"), ("x.com", "X"), ("facebook", "Facebook"), ("whatsapp", "WhatsApp"),
    ("messages", "Messages"), ("discord", "Discord"), ("slack", "Slack"), ("twitch", "Twitch"),
    ("linkedin", "LinkedIn"), ("spotify", "Spotify"), ("amazon", "Amazon"), ("prime video", "Prime Video"),
]
let browserNames: Set<String> = ["google chrome", "chrome", "safari", "arc", "firefox", "brave", "brave browser",
                                 "microsoft edge", "opera", "vivaldi"]
func placeName(_ title: String) -> String {
    let low = title.lowercased()
    for (k, v) in knownPlaces where low.contains(k) { return v }
    let parts = title.components(separatedBy: CharacterSet(charactersIn: "—–|"))
        .flatMap { $0.components(separatedBy: " - ") }
        .map { $0.trimmingCharacters(in: .whitespaces) }
        .filter { !$0.isEmpty && !browserNames.contains($0.lowercased()) }
    let p = parts.last ?? title
    return p.count > 16 ? String(p.prefix(15)) + "…" : p
}

/// Drop command hints and session numbers from replies ("Say "change to 40" to adjust.", "Session 8: ").
func plainReply(_ r: String) -> String {
    var t = r.replacingOccurrences(of: #"^Session \d+:\s*"#, with: "", options: .regularExpression)
    let sentences = t.split(separator: ".", omittingEmptySubsequences: false).map(String.init)
    if sentences.count > 1 {
        let keep = sentences.filter { s in
            let l = s.lowercased()
            return !(l.contains("say \"") || l.contains("say '") || l.contains("say “") || l.contains("your word is worth"))
        }
        t = keep.joined(separator: ".").trimmingCharacters(in: .whitespaces)
        if !t.isEmpty && !t.hasSuffix(".") && !t.hasSuffix("!") && !t.hasSuffix("?") && !t.hasSuffix("…") { t += "." }
    }
    return t.replacingOccurrences(of: "..", with: ".")
}

let checkCopy = ["camera": "Alibi checks with the camera", "screen": "Alibi checks your screen",
                 "both": "Alibi checks the camera and your screen", "strava": "Strava confirms the run",
                 "health": "Apple Health confirms it tonight"]

let hhmm: DateFormatter = { let f = DateFormatter(); f.dateFormat = "HH:mm"; return f }()
func clock(_ t: Double) -> String { hhmm.string(from: Date(timeIntervalSince1970: t)) }

// Colours are NVIDIA (CLAUDE.md "Design system"): green #76B900 on black; text on green is black. Layout and type are Claude-style.
let palette: [String: Color] = [
    "on_task": Color(hex: 0x76B900), "phone": Color(hex: 0xE5484D), "off_task": Color(hex: 0xC8362B),
    "idle": Color(hex: 0xF2A900), "absent": Color(hex: 0x8C8C8C),
]
let accent = Color(hex: 0x76B900)
let cream = Color(hex: 0xEEEEEE)
let surface = Color(hex: 0x1A1A1A)          // cards and the composer, on the black island
let hairline = Color.white.opacity(0.09)
let green = Color(hex: 0x76B900), amber = Color(hex: 0xF2A900), red = Color(hex: 0xE5484D)
func verdictColour(_ v: String?) -> Color { v == "done" ? green : v == "partial" ? amber : v == "slacked" ? red : accent }

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
    @Published var plan: PlanResp?            // today's planned blocks
    @Published var needsSetup = false         // first run: no habits / onboarding not finished
    var setupPath = "/"                       // the dashboard opens its wizard by itself while onboarding is unfinished
    @Published var confirmFinish = false      // [Finish] tapped with time still to go: inline confirm
    @Published var seenNudges = 0             // nudges the person has seen this session (badge = nudges - seen)
    var seenNudgeSession: Int?
    var lastAlertId: Int64?
    var alertTask: Task<Void, Never>?
    var alertShownAt: Double = 0
    var lastExtras: Double = 0
    let launched = Date().timeIntervalSince1970
    var startingUntil: Double = 0             // [Turn on] pressed: show "Starting…" until online or 20 s
    var starting: Bool { !online && now < startingUntil }
    var loading = Set<String>()

    init() {
        if let d = UserDefaults.standard.data(forKey: "alibi.habits"),
           let h = try? JSONDecoder().decode([HabitRef].self, from: d) { habits = h }
    }

    var session: Session? { state?.session }

    /// The block the idle island should talk about: happening now, else the next one later today.
    var upNext: PlanBlock? {
        guard session == nil, let p = plan else { return nil }
        if let l = p.live, l.state == "now" { return l }
        if let n = p.next, ["now", "planned"].contains(n.state) { return n }
        return p.blocks.first { ["now", "planned"].contains($0.state) && $0.end > now }
    }
    var unseenNudges: Int {
        guard let s = session else { return 0 }
        return seenNudgeSession == s.id ? max(0, (s.nudges ?? 0) - seenNudges) : (s.nudges ?? 0)
    }
    func markNudgesSeen() {
        guard let s = session else { return }
        seenNudgeSession = s.id; seenNudges = s.nudges ?? 0
    }

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
            let hadSession = state?.session?.id
            state = s
            if let h = s.habits, h != habits {
                habits = h
                if let d = try? JSONEncoder().encode(h) { UserDefaults.standard.set(d, forKey: "alibi.habits") }
            }
            if s.session?.id != hadSession { confirmFinish = false; await refreshExtras() }
            else if now - lastExtras > 15 { await refreshExtras() }
            if let a = s.alert, a.id != lastAlertId {
                // Fresh = raised after launch (minus a little slack); stale alerts from before launch are skipped.
                let fresh = a.ts.map { $0 > launched - 5 } ?? (lastAlertId != nil)
                if fresh && shouldShow(a) { show(alert: a) }
                lastAlertId = a.id
            }
            settleAlert()
        } else {
            online = false
            if now - launched > 3 { connecting = false }
            // The child we spawned died before answering: stop pretending it's booting.
            if startingUntil > 0 && DaemonOwner.shared.exited {
                startingUntil = 0; reply = "Alibi couldn't start. Tap “Show details” to see why."; replyFailed = true
            }
            if startingUntil > 0 && now >= startingUntil {
                startingUntil = 0; reply = "Alibi still isn't answering. Tap “Show details” to see why."; replyFailed = true
            }
        }
    }

    func refreshExtras() async {
        lastExtras = now
        plan = await get("/api/calendar/plan?days=1")
        if let o: OnboardingResp = await get("/api/onboarding") { needsSetup = o.needs_onboarding ?? false }
        else { needsSetup = false }
        setupPath = "/"
        if !needsSetup && (state?.habits ?? habits).isEmpty && online { needsSetup = true; setupPath = "/#setup" }
    }

    /// Which alerts deserve the island. Plain "info" (daemon up, etc.) stays in the log; a synced run or an info with
    /// buttons (e.g. "Reconnect Strava") is shown.
    func shouldShow(_ a: AlertEv) -> Bool {
        if a.kind != "info" { return true }
        return isSynced(a) || !(a.actions ?? []).isEmpty
    }
    func isSynced(_ a: AlertEv) -> Bool {
        a.kind == "synced" || (a.kind == "info" && a.text.hasPrefix("Strava:") && !a.text.contains("stopped"))
    }

    /// Alerts that should outlive a timer: a nudge stays while you're still off task; a planned block stays until
    /// you answer, it's 10 min past its start, or a session starts.
    func settleAlert() {
        guard mode == .alert, let a = alert else { return }
        if a.kind == "nudge" {
            let brk = (session?.on_break?.until ?? 0) > now
            if session == nil || brk || (session?.drifting == nil && now - alertShownAt > 4) { dismissAlert() }
        } else if a.kind == "planned" {
            if session != nil || now > (a.start ?? alertShownAt) + 600 { dismissAlert() }
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
        alertShownAt = Date().timeIntervalSince1970
        if a.kind == "nudge" { markNudgesSeen() }
        withAnimation(.spring(response: 0.42, dampingFraction: 0.78)) { mode = .alert }
        let sound: String? = switch a.kind {
            case "nudge": "Funk"; case "planned": "Purr"; case "verdict": "Glass"
            default: isSynced(a) ? nil : "Tink" }
        if let sound { NSSound(named: sound)?.play() }
        alertTask?.cancel()
        if !hovering, let s = dismissAfter(a) { scheduleDismiss(after: s) }
    }

    /// nil = stays until answered (see settleAlert).
    func dismissAfter(_ a: AlertEv) -> Double? {
        switch a.kind {
        case "nudge", "planned": return nil
        case "verdict": return 15
        default: return isSynced(a) ? 6 : 10
        }
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
        if let p = a.post {
            let body = (a.body ?? [:]).mapValues(\.any)
            Task {
                struct R: Decodable { let reply: String?; let ok: Bool? }
                let r: R? = await post(p, body)
                if let t = r?.reply { reply = plainReply(t); replyFailed = false; clearReplySoon() }
                await refreshExtras()
            }
        }
        if let u = a.url { open(u) }
        dismissAlert()
    }

    /// "/api/reel?…" answers JSON {url}; open the video itself, not the JSON.
    func open(_ u: String) {
        if u.hasPrefix("/api/reel") {
            Task {
                struct R: Decodable { let url: String? }
                if let r: R = await get(u, timeout: 60), let v = r.url, let url = URL(string: v.hasPrefix("/") ? API + v : v) {
                    NSWorkspace.shared.open(url)
                } else if let url = URL(string: API + "/") { NSWorkspace.shared.open(url) }
            }
            return
        }
        if let url = URL(string: u.hasPrefix("/") ? API + u : u) { NSWorkspace.shared.open(url) }
    }

    func clearReplySoon() {
        Task {
            try? await Task.sleep(nanoseconds: 5_000_000_000)
            if mode == .collapsed { reply = nil }
        }
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
        reply = r.map { plainReply($0.reply) } ?? "Alibi is off, so nothing was recorded."
        draft = ""
        busy = false
        await refresh()                     // optimistic: show the new session wings at once
        if quiet && r != nil { reply = nil }
    }

    func start(_ habit: String, _ minutes: Int) async { await send("\(habit) for \(minutes) minutes", quiet: true) }

    func end() async {
        struct R: Decodable { let reply: String }
        confirmFinish = false
        let r: R? = await post("/api/end", [:])
        reply = r.map { plainReply($0.reply) }
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

    func get<T: Decodable>(_ path: String, timeout: Double = 3) async -> T? {
        guard let url = URL(string: API + path) else { return nil }
        var req = URLRequest(url: url, timeoutInterval: timeout)
        req.setValue("island", forHTTPHeaderField: "X-Alibi-Client")
        guard let (d, r) = try? await URLSession.shared.data(for: req),
              ((r as? HTTPURLResponse)?.statusCode ?? 200) < 400 else { return nil }
        return try? JSONDecoder().decode(T.self, from: d)
    }

    func post<T: Decodable>(_ path: String, _ body: [String: Any]) async -> T? {
        guard let url = URL(string: API + path) else { return nil }
        var req = URLRequest(url: url, timeoutInterval: 10)
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
    var height: CGFloat { hasNotch ? screen.safeAreaInsets.top : 24 }
    var width: CGFloat {
        guard hasNotch, let l = screen.auxiliaryTopLeftArea, let r = screen.auxiliaryTopRightArea else { return 64 }
        return screen.frame.width - l.width - r.width
    }
}

// Only the width is per mode; the height comes from the measured content.
// Closed, the island is the camera housing itself: idle it is exactly the notch, so nothing shows. A live session
// (or a planned-now block / fresh reply) adds two compact wings, like an iPhone Live Activity.
let wing: CGFloat = 46
@MainActor func hasWings(_ island: Island) -> Bool {
    island.session != nil || island.reply != nil || (island.online && island.upNext?.state == "now")
}
@MainActor func width(for mode: Mode, notch: Notch, island: Island) -> CGFloat {
    switch mode {
    case .collapsed: return notch.width + (hasWings(island) ? 2 * wing : 0)
    case .expanded: return 400
    case .alert: return island.alert?.kind == "verdict" ? 440 : 400
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

/// Apple-Activity-style segmented ring: one segment per habit, green when it counted today.
struct TodayRing: View {
    let done: Int; let total: Int; var width: CGFloat = 2.5
    var body: some View {
        let n = max(1, total)
        let gap = n > 1 ? 0.035 : 0
        ZStack {
            ForEach(0..<n, id: \.self) { i in
                Circle().trim(from: Double(i) / Double(n) + gap / 2, to: Double(i + 1) / Double(n) - gap / 2)
                    .stroke(i < done ? green : Color.white.opacity(0.18), style: StrokeStyle(lineWidth: width, lineCap: .butt))
                    .rotationEffect(.degrees(-90))
            }
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

struct Glow: View {   // slow pulsing inner edge: drifting (red), a queued alert or a planned block (accent)
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

/// Every pressable thing: a hover wash and a 0.97 press, so clicks feel heard.
struct Pressable: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .opacity(configuration.isPressed ? 0.85 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

/// Claude-style button: soft rounded rectangle. Primary is NVIDIA green with black text; secondary is a quiet fill.
struct PillButton: View {
    let title: String; var primary = false; var tint: Color = accent; var icon: String? = nil; var small = false
    let action: () -> Void
    @State private var hover = false
    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                if let icon { Image(systemName: icon).font(.system(size: small ? 10 : 11, weight: .semibold)) }
                Text(title).font(.system(size: small ? 12 : 12.5, weight: .medium)).lineLimit(1).fixedSize()
            }
            .padding(.horizontal, small ? 10 : 12).frame(height: small ? 28 : 32)
            .background(RoundedRectangle(cornerRadius: 9, style: .continuous)
                .fill(primary ? tint.opacity(hover ? 0.88 : 1) : Color.white.opacity(hover ? 0.12 : 0.07)))
            .overlay(RoundedRectangle(cornerRadius: 9, style: .continuous).strokeBorder(primary ? .clear : hairline))
            .foregroundStyle(primary ? Color.black : cream.opacity(0.92))
            .contentShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
        }
        .buttonStyle(Pressable())
        .onHover { hover = $0 }
    }
}

/// Small square icon button (header, dismiss).
struct IconButton: View {
    let icon: String; var help = ""; let action: () -> Void
    @State private var hover = false
    var body: some View {
        Button(action: action) {
            Image(systemName: icon).font(.system(size: 11, weight: .semibold))
                .foregroundStyle(cream.opacity(hover ? 0.9 : 0.5))
                .frame(width: 26, height: 26)
                .background(RoundedRectangle(cornerRadius: 7, style: .continuous).fill(Color.white.opacity(hover ? 0.1 : 0)))
                .contentShape(Rectangle())
        }
        .buttonStyle(Pressable()).onHover { hover = $0 }.help(help)
    }
}

/// Hover wash + press for suggestion chips.
struct Chip: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View { ChipBody(configuration: configuration) }
    struct ChipBody: View {
        let configuration: Configuration
        @State private var hover = false
        var body: some View {
            configuration.label
                .background(RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Color.white.opacity(hover ? 0.07 : 0)))
                .scaleEffect(configuration.isPressed ? 0.97 : 1)
                .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
                .onHover { hover = $0 }
        }
    }
}

extension View {
    /// The one card surface: #1A1A1A, hairline border, 16 pt continuous corners. `highlight` = green edge.
    func card(highlight: Bool = false) -> some View {
        background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(surface))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous)
                .strokeBorder(highlight ? accent.opacity(0.45) : hairline, lineWidth: 1))
    }
}

// Proportional segmented strip: always fills its width, however many samples there are. `rest` greys out the
// part of the planned time that never happened (a session stopped early).
struct Strip: View {
    let labels: [String]; var height: CGFloat = 8; var rest: Double = 0
    var body: some View {
        GeometryReader { g in
            HStack(spacing: 1.5) {
                HStack(spacing: labels.count > 40 ? 0.5 : 1.5) {
                    ForEach(Array(labels.enumerated()), id: \.offset) { _, l in
                        Rectangle().fill(palette[l] ?? .gray)
                    }
                }.frame(width: max(4, g.size.width * (1 - rest)))
                if rest > 0.01 { Rectangle().fill(Color.white.opacity(0.12)) }
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
    /// A break is never a failure: while one runs, drifting is ignored everywhere (wing, glow, status line, nudges).
    var drifting: Drifting? { onBreak ? nil : session?.drifting }
    /// Seconds since the state was fetched (keeps drift/break timers ticking between polls).
    var drift: Double { max(0, m.now - (m.state?.now ?? m.now)) }
    var breakUntil: Double? {
        guard let u = session?.on_break?.until, u > m.now else { return nil }
        return u
    }
    var onBreak: Bool { breakUntil != nil }
    /// Work time left. A break pauses it (the backend moves ends_at out by the break), so it never shows break time.
    var sessionLeft: Double {
        guard let s = session else { return 0 }
        return max(0, s.ends_at - (breakUntil ?? m.now))
    }
    var breakLeft: Double { max(0, (breakUntil ?? m.now) - m.now) }
    var progress: Double {
        guard let s = session else { return 0 }
        return min(1, max(0, 1 - sessionLeft / Double(max(60, s.declared_min * 60))))
    }
    var showNote: Bool { (m.state?.witness ?? "") == "nvidia" }   // on-device/mock notes are internals, not copy
    var corner: (CGFloat, CGFloat) { m.mode == .collapsed ? (6, 10) : (10, 24) }
    var plannedNow: PlanBlock? { m.upNext.flatMap { $0.state == "now" ? $0 : nil } }

    var body: some View {
        let w = width(for: m.mode, notch: notch, island: m)
        VStack(spacing: 0) {
            content
                .padding(.horizontal, m.mode == .collapsed ? 6 + corner.0 : 16 + corner.0)
                .padding(.bottom, m.mode == .collapsed ? 0 : 16)
                .frame(width: w, alignment: .top)
                .fixedSize(horizontal: false, vertical: true)
                .background(alignment: .top) {
                    NotchShape(top: corner.0, bottom: corner.1)
                        .fill(Color.black)
                        .shadow(color: .black.opacity(m.mode == .collapsed ? 0 : 0.4), radius: 24, y: 10)
                }
                .overlay {
                    if drifting != nil && m.mode == .collapsed && hasWings(m) {
                        Glow(colour: red, top: corner.0, bottom: corner.1)
                    } else if m.pending != nil && m.mode == .collapsed {
                        Glow(colour: accent, top: corner.0, bottom: corner.1)
                    }
                }
                .background(GeometryReader { g in Color.clear.preference(key: SizeKey.self, value: g.size) })
                .onPreferenceChange(SizeKey.self) { s in MainActor.assumeIsolated { m.measured = s } }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .animation(.spring(response: 0.38, dampingFraction: 0.86), value: m.mode)
        .animation(.spring(response: 0.42, dampingFraction: 0.8), value: session?.id)
        .animation(.spring(response: 0.42, dampingFraction: 0.8), value: drifting?.label)
        .animation(.spring(response: 0.35, dampingFraction: 0.85), value: m.confirmFinish)
        .preferredColorScheme(.dark)
    }

    @ViewBuilder var content: some View {
        switch m.mode {
        case .collapsed: collapsed
        case .expanded: expanded.transition(.opacity.combined(with: .scale(scale: 0.96, anchor: .top)))
        case .alert:
            Group {
                if m.alert?.kind == "verdict" { verdictView }
                else if m.alert?.kind == "planned" { plannedView }
                else if let a = m.alert, m.isSynced(a) { syncedView }
                else { alertView }
            }.transition(.opacity.combined(with: .scale(scale: 0.96, anchor: .top)))
        }
    }

    // MARK: Collapsed — the camera housing, plus compact leading/trailing wings while something is live.

    var collapsed: some View {
        HStack(spacing: 0) {
            if hasWings(m) {
                compactLeading.frame(width: wing - 6, alignment: .leading)
                Color.clear.frame(maxWidth: .infinity)
                compactTrailing.frame(width: wing - 6, alignment: .trailing)
            } else {
                Color.clear.frame(maxWidth: .infinity)
            }
        }
        .frame(height: notch.height)
    }

    /// Leading wing: one glyph that says how it's going.
    @ViewBuilder var compactLeading: some View {
        if session != nil {
            if m.unseenNudges > 0 {
                Text("\(m.unseenNudges)").font(rounded(10, .bold)).foregroundStyle(.black)
                    .frame(minWidth: 16, minHeight: 16).background(Circle().fill(red))
            } else if drifting != nil { Pulse(colour: red, size: 7) }
            else if onBreak { Image(systemName: "cup.and.saucer.fill").font(.system(size: 11)).foregroundStyle(amber) }
            else { Pulse(colour: palette[current] ?? accent, size: 7) }
        } else if m.reply != nil {
            Image(systemName: m.replyFailed ? "exclamationmark" : "checkmark")
                .font(.system(size: 11, weight: .bold)).foregroundStyle(m.replyFailed ? red : accent)
        } else if plannedNow != nil {
            Image(systemName: "play.fill").font(.system(size: 10, weight: .bold)).foregroundStyle(accent)
        }
    }

    /// Trailing wing: the one number that matters (time left, break left, or "now").
    @ViewBuilder var compactTrailing: some View {
        if session != nil {
            let tint: Color = drifting != nil ? red : onBreak ? amber : cream
            Text(short(onBreak ? breakLeft : sessionLeft)).font(rounded(12, .semibold)).monospacedDigit()
                .foregroundStyle(tint).contentTransition(.numericText()).lineLimit(1).fixedSize()
        } else if m.reply == nil, plannedNow != nil {
            Text("now").font(rounded(12, .semibold)).foregroundStyle(accent).fixedSize()
        }
    }

    /// 24m · 45s · 1h05 — fits a 40 pt wing.
    func short(_ s: Double) -> String {
        let s = Int(max(0, s).rounded())
        if s >= 3600 { return String(format: "%dh%02d", s / 3600, (s % 3600) / 60) }
        return s >= 60 ? "\(Int((Double(s) / 60).rounded(.up)))m" : "\(s)s"
    }

    func shortDrift(_ d: Drifting) -> String {
        switch d.label { case "phone": return "Phone"; case "absent": return "Away"; case "idle": return "Idle"
        default: return d.label_text.map(placeName) ?? "Off task" }
    }

    // MARK: Expanded

    var expanded: some View {
        VStack(alignment: .leading, spacing: 12) {
            header
            if !m.online && !m.connecting {
                offlineCard
            } else if m.needsSetup && session == nil {
                welcomeCard
            } else {
                if let s = session { sessionCard(s); sessionControls(s) }
                else if let b = m.upNext { upNextCard(b) }
                composer
            }
            if let r = m.reply {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    if m.replyFailed { Image(systemName: "exclamationmark.circle.fill").foregroundStyle(red).font(.system(size: 11)) }
                    Text(r).font(.system(size: 13, design: .serif)).foregroundStyle(cream.opacity(0.8))
                        .lineLimit(3).fixedSize(horizontal: false, vertical: true)
                }.padding(.horizontal, 4)
            }
            if session == nil && !m.needsSetup && !m.habits.isEmpty { chips.opacity(m.online ? 1 : 0.45) }
            footer
        }
        .onAppear {
            m.markNudgesSeen()
            if m.pinned { DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { focused = true } }
        }
        .onChange(of: m.pinned) { _, p in if p { focused = true } }
    }

    var statusText: String {
        guard m.online else { return "Off" }
        guard let s = session else { return "Ready" }
        if onBreak { return "On a break" }
        switch s.modality {
        case "digital": return "Watching your screen"
        case "hybrid": return "Watching desk + screen"
        default: return "Watching your desk"
        }
    }

    /// The notch row: only the far edges are visible beside the camera, so it holds just the name and two icons.
    var header: some View {
        HStack(spacing: 2) {
            Text("Alibi").font(.system(size: 14, weight: .medium, design: .serif)).foregroundStyle(cream)
            Circle().fill(accent).frame(width: 4, height: 4).offset(y: 3)
            Spacer(minLength: notch.width)
            IconButton(icon: "arrow.up.right", help: "Open Alibi in the browser") { m.open("/") }
            IconButton(icon: "power", help: "Quit Alibi (stops watching)") { NSApp.terminate(nil) }
        }
        .frame(height: notch.height - 2, alignment: .center)
    }

    /// Quiet status line under everything: what Alibi is doing, today's tally, the hotkey.
    var footer: some View {
        HStack(spacing: 6) {
            if (m.connecting || m.starting) && !m.online {
                ProgressView().controlSize(.mini).tint(.white)
                Text(m.starting ? "Starting…" : "Connecting…")
            } else {
                Circle().fill(m.online ? (session != nil ? accent : Color.white.opacity(0.35)) : amber).frame(width: 6, height: 6)
                Text(statusText).lineLimit(1)
                    .help(m.online ? "Checked by: \(m.state?.witness_label ?? m.state?.witness ?? "—")" : "")
                if m.online, let t = m.state?.today, let total = t.habits_total, total > 0 {
                    Text("·").opacity(0.5)
                    TodayRing(done: t.habits_done ?? 0, total: total, width: 2).frame(width: 10, height: 10)
                    Text("\(t.habits_done ?? 0) of \(total) today").lineLimit(1).fixedSize()
                }
            }
            Spacer()
            Keycap(text: "⌥⌘A")
        }
        .font(.system(size: 11)).foregroundStyle(.white.opacity(0.45))
        .padding(.horizontal, 4).padding(.top, 2)
    }

    /// Claude-style composer: a soft box with the field on top and a round send button bottom-right.
    var composer: some View {
        let canSend = !m.draft.trimmingCharacters(in: .whitespaces).isEmpty && !m.busy
        return VStack(alignment: .leading, spacing: 8) {
            TextField("", text: $m.draft, prompt: Text(session == nil ? "What are you about to do?" : "Add a note…")
                .foregroundStyle(.white.opacity(0.38)))
                .textFieldStyle(.plain).font(.system(size: 14)).foregroundStyle(cream)
                .focused($focused)
                .onSubmit { Task { await m.send(m.draft); m.unpinSoon() } }
                .onExitCommand { Controller.shared?.collapse() }
            HStack {
                Text(session == nil ? "Try “draw for 25 min”" : "Notes go on the session record")
                    .font(.system(size: 11)).foregroundStyle(.white.opacity(0.32)).lineLimit(1)
                Spacer()
                Button { Task { await m.send(m.draft); m.unpinSoon() } } label: {
                    Image(systemName: m.busy ? "ellipsis" : "arrow.up").font(.system(size: 12, weight: .bold))
                        .foregroundStyle(canSend ? Color.black : .white.opacity(0.35))
                        .frame(width: 28, height: 28)
                        .background(Circle().fill(canSend ? accent : Color.white.opacity(0.08)))
                }
                .buttonStyle(Pressable()).disabled(!canSend).help("Send (Return)")
            }
        }
        .padding(.leading, 14).padding(.trailing, 10).padding(.top, 13).padding(.bottom, 10)
        .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(surface))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous)
            .strokeBorder(focused ? accent.opacity(0.55) : hairline, lineWidth: 1))
        .animation(.easeOut(duration: 0.15), value: focused)
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
            VStack(alignment: .leading, spacing: 3) {
                Text(m.starting ? "Turning on…" : "Alibi is off").font(.system(size: 15, design: .serif)).foregroundStyle(cream)
                Text(m.starting ? "Usually a few seconds." : "Nothing is being recorded.")
                    .font(.system(size: 11.5)).foregroundStyle(.white.opacity(0.5))
                if !m.starting && repoRoot != nil {
                    Button { Controller.openLogs() } label: {
                        Text("Show details").font(.system(size: 11)).underline().foregroundStyle(.white.opacity(0.4))
                    }.buttonStyle(.plain)
                }
            }
            Spacer()
            PillButton(title: "Turn on", primary: true) {
                guard !m.starting else { return }
                m.reply = nil; m.replyFailed = false
                m.startingUntil = Date().timeIntervalSince1970 + 20; m.now = Date().timeIntervalSince1970
                Controller.startDaemon()
            }
            .disabled(m.starting).opacity(m.starting ? 0.5 : 1)
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .card()
    }

    /// First run: nothing to track yet, so the only useful thing is the setup wizard.
    var welcomeCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Welcome to Alibi").font(.system(size: 19, design: .serif)).foregroundStyle(cream)
            Text("Pick a habit or two, say when you'll do them, and Alibi quietly checks you actually did. It takes about two minutes.")
                .font(.system(size: 12.5)).foregroundStyle(cream.opacity(0.7)).fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 8) {
                PillButton(title: "Set up my habits", primary: true, icon: "sparkles") { m.open(m.setupPath) }
                Text("Opens in your browser").font(.system(size: 11)).foregroundStyle(.white.opacity(0.4))
            }.padding(.top, 2)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
    }

    /// Idle: what's planned. Now -> a big card with Start; later today -> one quiet line.
    @ViewBuilder func upNextCard(_ b: PlanBlock) -> some View {
        if b.state == "now" {
            HStack(spacing: 14) {
                Image(systemName: "calendar.badge.clock").font(.system(size: 15)).foregroundStyle(accent)
                    .frame(width: 34, height: 34).background(RoundedRectangle(cornerRadius: 10, style: .continuous).fill(accent.opacity(0.14)))
                VStack(alignment: .leading, spacing: 3) {
                    Text(b.name).font(.system(size: 16, design: .serif)).foregroundStyle(cream).lineLimit(1)
                    Text("Planned now · \(clock(b.start))–\(clock(b.end))").font(.system(size: 11.5, weight: .medium))
                        .foregroundStyle(accent.opacity(0.9)).lineLimit(1)
                }.layoutPriority(1)
                Spacer(minLength: 8)
                if b.startable {
                    PillButton(title: "Start", primary: true, icon: "play.fill", small: true) { Task { await m.start(b.habit, b.min) } }
                }
                PillButton(title: "Skip", small: true) { skip(b) }.help("Skip \(b.name) for today")
            }
            .padding(12)
            .card(highlight: true)
        } else {
            HStack(spacing: 8) {
                Image(systemName: "calendar").font(.system(size: 11)).foregroundStyle(.white.opacity(0.45))
                Text("Next up").font(.system(size: 11.5, weight: .semibold)).foregroundStyle(.white.opacity(0.45))
                Text("\(b.name) at \(b.at) · \(b.min) min").font(.system(size: 12.5, weight: .medium))
                    .foregroundStyle(cream.opacity(0.9)).lineLimit(1).truncationMode(.tail)
                Spacer(minLength: 6)
                if b.startable {
                    PillButton(title: "Start now", small: true) { Task { await m.start(b.habit, b.min) } }
                } else {
                    Text(checkCopy[b.check ?? ""] ?? "").font(.system(size: 11)).foregroundStyle(.white.opacity(0.4))
                        .lineLimit(1).fixedSize()
                }
            }.padding(.horizontal, 4)
        }
    }

    func skip(_ b: PlanBlock) {
        m.act(AlertAction("Skip today", post: "/api/calendar/plan/skip", body: ["key": .str(b.key)]))
    }

    /// Habits as one-tap chips: today's planned ones first (the one planned now highlighted), then the rest.
    var chips: some View {
        let planned = (m.plan?.blocks ?? []).filter { ["now", "planned"].contains($0.state) }
        let order = Dictionary(planned.enumerated().map { ($1.habit, $0) }, uniquingKeysWith: { a, _ in a })
        let all = m.habits.filter { $0.modality != "strava" && $0.modality != "health" }
            .enumerated().sorted { (order[$0.element.key] ?? 100 + $0.offset) < (order[$1.element.key] ?? 100 + $1.offset) }
            .map(\.element)
        let nowKey = plannedNow?.habit
        let hs = m.upNext?.state == "now" ? all.filter { $0.key != nowKey } : all   // the card above already offers it
        return Flow(spacing: 6) {
            ForEach(Array(hs.enumerated()), id: \.element) { i, h in
                let block = planned.first { $0.habit == h.key }
                let mins = block?.min ?? h.default_min ?? 25
                let isNow = h.key == nowKey
                let doneToday = (m.plan?.blocks ?? []).contains { $0.habit == h.key && ["done", "partial"].contains($0.state) }
                Button { Task { await m.send("\(h.key) for \(mins) minutes") } } label: {
                    HStack(spacing: 6) {
                        if isNow { Image(systemName: "play.fill").font(.system(size: 8, weight: .bold)).foregroundStyle(accent) }
                        else if doneToday { Image(systemName: "checkmark").font(.system(size: 9, weight: .bold)).foregroundStyle(accent) }
                        Text(h.name).font(.system(size: 12.5)).lineLimit(1).fixedSize()
                        Text(block.map { isNow ? "now" : "\($0.at)" } ?? "\(mins)m")
                            .font(.system(size: 11)).monospacedDigit().foregroundStyle(.white.opacity(0.4)).lineLimit(1).fixedSize()
                    }
                    .padding(.horizontal, 11).frame(height: 30)
                    .background(RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Color.white.opacity(0.03)))
                    .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous).strokeBorder(isNow ? accent.opacity(0.6) : hairline))
                    .contentShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                }
                .buttonStyle(Chip()).foregroundStyle(cream.opacity(0.88))
                .keyboardShortcut(KeyEquivalent(Character("\(min(i + 1, 9))")), modifiers: .command)
                .help("Start \(h.name) for \(mins) min (⌘\(i + 1)) · right-click for another length")
                .contextMenu {
                    ForEach([15, 25, 45, 60], id: \.self) { n in
                        Button("\(h.name) for \(n) min") { Task { await m.send("\(h.key) for \(n) minutes") } }
                    }
                }
            }
            Button { Task { await m.send("how am I doing") } } label: {
                HStack(spacing: 6) {
                    Image(systemName: "chart.bar").font(.system(size: 10, weight: .semibold)).foregroundStyle(.white.opacity(0.45))
                    Text("How am I doing?").font(.system(size: 12.5))
                }
                .padding(.horizontal, 11).frame(height: 30)
                .background(RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Color.white.opacity(0.03)))
                .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous).strokeBorder(hairline))
                .contentShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            }.buttonStyle(Chip()).foregroundStyle(cream.opacity(0.88))
        }
    }

    func sessionCard(_ s: Session) -> some View {
        let warming = s.warming_up ?? ((s.samples ?? s.labels.count) < 6)
        let recentR = s.recent_on_task ?? s.on_task_so_far ?? 1
        let heroColour = recentR >= 0.67 ? green : recentR >= 0.34 ? amber : red
        return HStack(alignment: .center, spacing: 14) {
            ZStack {
                Ring(progress: progress, colour: onBreak ? amber : (palette[current] ?? accent), width: 3.5)
                Image(systemName: onBreak ? "cup.and.saucer.fill" : s.modality == "digital" ? "macwindow" : "camera.fill")
                    .font(.system(size: 13)).foregroundStyle(.white.opacity(0.55))
            }.frame(width: 44, height: 44)
            VStack(alignment: .leading, spacing: 5) {
                Text(s.name).font(.system(size: 18, design: .serif)).foregroundStyle(cream)
                    .lineLimit(1).truncationMode(.tail)
                Text(onBreak ? "Paused · \(mmss(sessionLeft)) left of \(s.declared_min) min"
                             : "\(mmss(sessionLeft)) left of \(s.declared_min) min")
                    .font(rounded(11.5, .medium)).monospacedDigit()
                    .foregroundStyle(.white.opacity(0.5)).lineLimit(1)
                let live = s.labels.isEmpty ? (s.recent ?? []) : s.labels.suffix(60).map(\.label)
                if !live.isEmpty && !onBreak {
                    Strip(labels: live, height: 6)
                        .frame(maxWidth: 150, alignment: .leading)
                        .padding(.top, 1)
                }
                statusLine(s)
            }.layoutPriority(1)
            Spacer(minLength: 0)
            VStack(alignment: .trailing, spacing: 1) {
                if warming || s.on_task_so_far == nil {
                    Text("—").font(rounded(24, .semibold)).foregroundStyle(.white.opacity(0.4))
                    Text("getting a read").font(.system(size: 10.5)).foregroundStyle(.white.opacity(0.4))
                } else if let r = s.on_task_so_far {
                    Text("\(Int((r * 100).rounded()))%").font(rounded(24, .semibold)).monospacedDigit()
                        .foregroundStyle(heroColour).contentTransition(.numericText())
                    Text("focused").font(.system(size: 10.5)).foregroundStyle(.white.opacity(0.4))
                }
            }.fixedSize()
        }
        .padding(14)
        .card()
    }

    /// One-tap controls (no typed commands needed): break / +10 / finish, and an inline confirm before ending early.
    @ViewBuilder func sessionControls(_ s: Session) -> some View {
        if m.confirmFinish {
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 1) {
                    Text("End \(s.name) now?").font(.system(size: 12.5, weight: .semibold)).foregroundStyle(cream)
                    Text("\(max(1, Int(sessionLeft / 60))) min to go. It'll be judged on what Alibi saw.")
                        .font(.system(size: 11)).foregroundStyle(.white.opacity(0.5)).lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                }.layoutPriority(1)
                Spacer(minLength: 6)
                PillButton(title: "Keep going", small: true) { m.confirmFinish = false }
                PillButton(title: "End now", primary: true, tint: amber, small: true) { Task { await m.end() } }
            }
            .padding(.horizontal, 12).padding(.vertical, 10)
            .card()
        } else {
            HStack(spacing: 8) {
                if onBreak {
                    PillButton(title: "I'm back", primary: true, tint: amber, icon: "arrow.uturn.backward") {
                        Task { await m.send("back", quiet: true) }
                    }
                } else {
                    PillButton(title: "Break", icon: "cup.and.saucer", small: true) {
                        Task { await m.send("break 5", quiet: true) }
                    }
                    .contextMenu {
                        ForEach([2, 5, 10, 15], id: \.self) { n in
                            Button("Break for \(n) min") { Task { await m.send("break \(n)", quiet: true) } }
                        }
                    }
                    .help("5-minute break · right-click for another length")
                }
                PillButton(title: "+10 min", icon: "plus", small: true) {
                    Task { await m.send("change to \(s.declared_min + 10)", quiet: true) }
                }.help("Make this session 10 minutes longer")
                Spacer()
                PillButton(title: "Finish", icon: "flag.checkered", small: true) {
                    if sessionLeft > 60 { m.confirmFinish = true } else { Task { await m.end() } }
                }
            }
        }
    }

    @ViewBuilder func statusLine(_ s: Session) -> some View {
        if let d = drifting {
            let place = d.label == "phone" ? "on your phone" : d.label == "absent" ? "away from the desk"
                : d.label == "idle" ? "idle" : "on \(shortDrift(d))"
            Text("You've been \(place) for \(mmss((d.since_s ?? 0) + drift))").font(.system(size: 11.5, weight: .medium))
                .foregroundStyle(red).lineLimit(1)
        } else if onBreak {
            HStack(spacing: 5) {
                Image(systemName: "cup.and.saucer.fill").font(.system(size: 9))
                Text("Break · back in \(mmss(breakLeft))").font(rounded(11.5, .semibold)).monospacedDigit()
            }
            .foregroundStyle(Color.black.opacity(0.85))
            .padding(.horizontal, 8).frame(height: 20).background(Capsule().fill(amber))
        } else if let l = s.last_seen {
            let ago = l.ago_s.map { $0 < 5 ? "just now" : "\(Int($0)) s ago" } ?? ""
            let note = showNote ? (l.note.map { " · \($0)" } ?? "") : ""
            Text("\(l.label_text ?? human(l.label)) · checked \(ago)\(note)").font(.system(size: 11.5))
                .foregroundStyle((palette[l.label] ?? .gray).opacity(0.95)).lineLimit(1)
        } else if let n = s.labels.last {
            Text(n.label_text ?? human(n.label)).font(.system(size: 11.5)).foregroundStyle(palette[n.label] ?? .gray).lineLimit(1)
        } else {
            Text("First check in a few seconds…").font(.system(size: 11)).foregroundStyle(.white.opacity(0.4))
        }
    }

    // MARK: Alerts

    /// Server actions, with the island's plainer labels for the known ones.
    func actions(for a: AlertEv) -> [AlertAction] {
        var xs = a.actions ?? []
        if xs.isEmpty {
            switch a.kind {
            case "nudge": xs = [AlertAction("Back to it", say: "back"), AlertAction("This counts", say: "it's on task"),
                                AlertAction("Quiet 5 min", say: "snooze 5")]
            case "verdict":
                if let id = a.session_id {
                    xs = [AlertAction("Watch replay", url: "/api/reel?session=\(id)"), AlertAction("Something's wrong?", url: "/#session-\(id)")]
                } else { xs = [AlertAction("OK", dismiss: true)] }
            default: xs = [AlertAction("OK", dismiss: true)]
            }
        }
        return xs.map { x in
            let l: String = switch (x.say ?? "", x.label) {
                case ("back", _): "Back to it"
                case ("it's on task", _): "This counts"
                case (let s, _) where s.hasPrefix("snooze"): "Quiet \(s.split(separator: " ").last.map(String.init) ?? "5") min"
                case (_, "Watch reel"): "Watch replay"
                case (_, "Fix samples"): "Something's wrong?"
                case (_, "Not now"): "Not now"
                case (_, let t) where t.hasSuffix("m") && t.hasPrefix("Start "): t.dropLast() + " min"
                case (_, let t) where t.hasPrefix("Again ") && t.hasSuffix("m"): "Again · " + t.dropFirst(6).dropLast() + " min"
                default: x.label
            }
            return AlertAction(l, say: x.say, url: x.url, post: x.post, body: x.body, dismiss: x.dismiss)
        }
    }

    func actionRow(_ a: AlertEv, tint: Color, extra: [AlertAction] = []) -> some View {
        HStack(spacing: 8) {
            ForEach(Array((extra + actions(for: a)).prefix(3).enumerated()), id: \.offset) { i, x in
                PillButton(title: x.label, primary: i == 0, tint: tint) { m.act(x) }
            }
            Spacer()
            IconButton(icon: "xmark", help: "Dismiss (Esc)") { m.dismissAlert() }
        }
    }

    /// Notch row (only its edges are visible): wordmark left, context right. The title sits below the camera.
    func alertHeader(icon: String, title: String, tint: Color, trailing: String?) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 2) {
                Text("Alibi").font(.system(size: 14, weight: .medium, design: .serif)).foregroundStyle(cream)
                Circle().fill(accent).frame(width: 4, height: 4).offset(y: 3)
                Spacer(minLength: notch.width)
                if let t = trailing {
                    Text(t).font(.system(size: 11)).monospacedDigit().foregroundStyle(.white.opacity(0.45)).lineLimit(1)
                }
            }.frame(height: notch.height - 2)
            HStack(spacing: 7) {
                Image(systemName: icon).font(.system(size: 11, weight: .semibold)).foregroundStyle(tint)
                Text(title).font(.system(size: 12.5, weight: .semibold)).foregroundStyle(tint)
            }
        }
    }

    var alertView: some View {
        let a = m.alert ?? AlertEv(id: 0, kind: "info", text: "")
        let tint: Color = a.kind == "nudge" ? red : a.kind == "pace" ? amber : accent
        let habitName = a.habit_label ?? a.habit.map(displayName) ?? session?.name
        let title: String = switch a.kind {
            case "nudge": "Still \((session?.habit ?? a.habit).map(spokenHabit) ?? "on it")?"
            case "pace": "Behind this week"; case "recap": "Today's replay"; case "report": "Tonight's report"
            default: "Alibi" }
        let icon = a.kind == "nudge" ? "eye.fill" : a.kind == "pace" ? "chart.line.downtrend.xyaxis"
            : a.kind == "recap" ? "film" : a.kind == "report" ? "doc.text" : "bell.fill"
        let text = a.kind == "pace" ? paceCopy(a) : a.text
        return VStack(alignment: .leading, spacing: 12) {
            alertHeader(icon: icon, title: title, tint: tint, trailing: a.kind == "nudge" ? nil : habitName)
            Text(text).font(.system(size: 15, design: .serif)).foregroundStyle(cream)
                .lineLimit(4).fixedSize(horizontal: false, vertical: true)
            if a.kind == "nudge", let d = drifting {
                Text("Seen for \(mmss((d.since_s ?? 0) + drift)) · \(mmss(sessionLeft)) left of your \(session?.declared_min ?? 0) min")
                    .font(rounded(11, .medium)).monospacedDigit().foregroundStyle(.white.opacity(0.45))
            }
            actionRow(a, tint: tint)
        }
    }

    /// "Drawing: 40 min behind pace. 25 min now closes 62% of it. Say 'yes'." ->
    /// "You're 40 min short on Drawing this week. 25 min now gets you more than halfway back."
    func paceCopy(_ a: AlertEv) -> String {
        let t = a.text
        guard let r = t.range(of: #"(\d+) min behind pace"#, options: .regularExpression),
              let behind = Int(t[r].split(separator: " ").first ?? "") else { return plainReply(t) }
        let name = a.habit_label ?? a.habit.map(displayName) ?? String(t.split(separator: ":").first ?? "")
        let mins = a.minutes ?? 25
        let how = mins >= behind ? "gets you back on track" : mins * 2 >= behind ? "gets you more than halfway back"
            : "makes a start on it"
        return "You're \(behind) min short on \(name) this week. \(mins) min now \(how)."
    }

    /// "drawing" -> "drawing"; "cpp" -> "on C++"; "internships" -> "on Internships".
    func spokenHabit(_ k: String) -> String {
        let verbs = ["drawing", "building", "reading", "running", "coding", "studying", "writing", "practising",
                     "practicing", "meditating", "sketching", "painting", "journaling", "stretching"]
        let label = m.habits.first { $0.key == k }?.name ?? displayName(k)
        return verbs.contains(label.lowercased()) ? label.lowercased() : "on \(label)"
    }

    /// Calendar auto-start: "Drawing is planned now — start?" [Start 25 min] [In 10 min] [Skip today].
    var plannedView: some View {
        let a = m.alert ?? AlertEv(id: 0, kind: "planned", text: "")
        let range = (a.start.map(clock) ?? a.at ?? "") + (a.end.map { "–" + clock($0) } ?? "")
        let late = a.late ?? false
        return VStack(alignment: .leading, spacing: 12) {
            alertHeader(icon: "calendar.badge.clock", title: late ? "Planned for \(a.at ?? "earlier")" : "Planned now",
                        tint: accent, trailing: range)
            HStack(alignment: .center, spacing: 14) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(a.text).font(.system(size: 16, design: .serif)).foregroundStyle(cream)
                        .lineLimit(2).fixedSize(horizontal: false, vertical: true)
                    Text([a.minutes.map { "\($0) min" }, checkCopy[a.check ?? ""]].compactMap { $0 }.joined(separator: " · "))
                        .font(.system(size: 11.5)).foregroundStyle(.white.opacity(0.5)).lineLimit(1)
                }.layoutPriority(1)
                Spacer(minLength: 0)
            }
            actionRow(a, tint: accent)
        }
    }

    /// A run (or a Health target) came in from the phone: quiet, celebratory, gone in 6 s.
    var syncedView: some View {
        let a = m.alert ?? AlertEv(id: 0, kind: "synced", text: "")
        let (title, detail) = syncedCopy(a)
        return VStack(alignment: .leading, spacing: 12) {
            alertHeader(icon: "figure.run", title: a.title ?? title, tint: green, trailing: a.habit_label)
            HStack(spacing: 14) {
                ZStack {
                    Ring(progress: 1, colour: green, width: 3.5)
                    Image(systemName: "checkmark").font(.system(size: 15, weight: .bold)).foregroundStyle(green)
                }.frame(width: 40, height: 40)
                VStack(alignment: .leading, spacing: 3) {
                    Text(a.detail ?? detail).font(.system(size: 15, design: .serif)).foregroundStyle(cream).lineLimit(2)
                    if let p = a.progress {
                        Text(p).font(.system(size: 11.5)).foregroundStyle(.white.opacity(0.5))
                    }
                }
                Spacer(minLength: 0)
            }
            if a.actions?.isEmpty == false { actionRow(a, tint: green) }
        }
    }

    /// "Strava: Morning Run, 5.2 km — logged." -> ("Run logged from Strava", "Morning Run · 5.2 km")
    func syncedCopy(_ a: AlertEv) -> (String, String) {
        guard a.text.hasPrefix("Strava:") else { return ("Synced", a.text) }
        var t = String(a.text.dropFirst(7)).trimmingCharacters(in: .whitespaces)
        let updated = t.contains("— updated")
        if let r = t.range(of: " — ") { t = String(t[..<r.lowerBound]) }
        t = t.replacingOccurrences(of: ", ", with: " · ")
        return (updated ? "Run updated from Strava" : "Run logged from Strava", t)
    }

    var verdictView: some View {
        let a = m.alert ?? AlertEv(id: 0, kind: "verdict", text: "")
        let rv = m.state?.recent_verdict.flatMap { v in (a.session_id == nil || v.id == a.session_id) ? v : nil }
        let v = a.verdict ?? rv?.verdict
        let labels = rv?.labels ?? []
        let wins = labels.isEmpty ? (rv?.windows ?? []) : []      // screen-only habit: the windows are the evidence
        let screenShare: Double? = wins.isEmpty ? nil : wins.filter { $0.label == "on_task" }.map(\.share).reduce(0, +)
        let declared = rv?.declared_min ?? 0
        let elapsed = rv?.elapsed_min ?? declared
        let early = (a.ended_early ?? false) || (declared > 0 && Double(elapsed) < Double(declared) * 0.9)
        let tint = early ? amber : verdictColour(v)
        let ratio = a.ratio ?? rv?.on_task_ratio
        let onShare = labels.isEmpty ? screenShare : Double(labels.filter { $0.label == "on_task" }.count) / Double(labels.count)
        let counts = Dictionary(grouping: labels, by: \.label).mapValues(\.count)
        let offBits = ["phone": "on the phone", "absent": "away", "idle": "idle", "off_task": "on something else"]
            .compactMap { k, t in counts[k].map { (k, "\(t) \($0 == 1 ? "once" : $0 == 2 ? "twice" : "\($0)×")") } }
            .sorted { $0.0 < $1.0 }.map(\.1)
        let detail = wins.isEmpty ? (["Checked \(labels.count) time\(labels.count == 1 ? "" : "s")"] + offBits).joined(separator: " · ")
            : (placesLine(wins) ?? "")
        let name = a.habit_label ?? rv?.label ?? a.habit.map(displayName) ?? "Session"
        let badge = early ? "STOPPED EARLY" : v == "done" ? "DONE" : v == "partial" ? "PARTLY DONE" : v == "slacked" ? "DIDN'T COUNT" : "ENDED"
        let enoughLooks = labels.count >= 6 || !wins.isEmpty
        let checkedWhat = wins.isEmpty ? "Alibi checked" : "Alibi checked your screen"
        let focusLine: String? = onShare.map { r in
            r >= 0.99 ? "Focused the whole time \(checkedWhat)." : r <= 0.01 ? "Not on it any time \(checkedWhat)."
                : "Focused \(Int((r * 100).rounded()))% of the time \(checkedWhat)." }
        let counted = v == "done" ? " Still counts for today." : v == "partial" ? " Counts as partly done."
            : " Too short to count for today."
        let line = early ? ((focusLine ?? "") + counted).trimmingCharacters(in: .whitespaces) : plainReply(a.text)
        var extra: [AlertAction] = []
        if early, let h = a.habit ?? rv?.habit, declared - elapsed >= 2 {
            extra = [AlertAction("Keep going · \(declared - elapsed) min", say: "\(h) for \(declared - elapsed) minutes")]
        }
        return VStack(alignment: .leading, spacing: 12) {
            alertHeader(icon: "checkmark.seal.fill", title: "Verdict", tint: accent,
                        trailing: rv.map { _ in early ? nil : "\(elapsed) of \(declared) min" } ?? nil)
            HStack(alignment: .center, spacing: 12) {
                Text(badge).font(.system(size: 10.5, weight: .bold)).tracking(0.8)
                    .foregroundStyle(Color.black).lineLimit(1).fixedSize()
                    .padding(.horizontal, 8).frame(height: 22).background(RoundedRectangle(cornerRadius: 6, style: .continuous).fill(tint))
                Text(name).font(.system(size: 19, design: .serif)).foregroundStyle(cream)
                    .lineLimit(1).truncationMode(.tail).layoutPriority(1)
                Spacer(minLength: 8)
                VStack(alignment: .trailing, spacing: 0) {
                    if early && rv != nil {
                        Text("\(elapsed) of \(declared)").font(rounded(24, .semibold)).monospacedDigit().foregroundStyle(tint)
                        Text("minutes").font(.system(size: 10.5)).foregroundStyle(.white.opacity(0.45))
                    } else if let r = ratio, enoughLooks || rv == nil {
                        Text("\(Int((r * 100).rounded()))%").font(rounded(26, .semibold)).monospacedDigit().foregroundStyle(tint)
                        Text("focused").font(.system(size: 10.5)).foregroundStyle(.white.opacity(0.45))
                    }
                }.fixedSize()
            }
            if !labels.isEmpty || !wins.isEmpty {
                let rest = early && declared > 0 ? min(0.7, max(0, 1 - Double(elapsed) / Double(declared))) : 0  // keep the evidence readable
                VStack(alignment: .leading, spacing: 6) {
                    if wins.isEmpty { Strip(labels: labels.map(\.label), height: 8, rest: rest) }
                    else { PlaceStrip(ws: wins, height: 8, rest: rest) }
                    HStack {
                        Text(detail).font(rounded(11, .medium)).foregroundStyle(.white.opacity(0.5)).lineLimit(1)
                        Spacer()
                        if early { Text("not done").font(rounded(11, .medium)).foregroundStyle(.white.opacity(0.35)) }
                    }
                }
            }
            if !line.isEmpty {
                Text(line).font(.system(size: 13.5, design: .serif))
                    .foregroundStyle(cream.opacity(0.8)).lineLimit(3).fixedSize(horizontal: false, vertical: true)
            }
            if !labels.isEmpty { thumbRow(labels) }
            actionRow(a, tint: tint, extra: extra)
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

/// Alibi is never the frontmost app, so every click on the island is a "first click" into an inactive window.
/// Without this, SwiftUI swallows it and buttons do nothing.
final class FirstClickHostingView<Content: View>: NSHostingView<Content> {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

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
    var lastMouse: NSPoint = .zero

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
        panel.contentView = FirstClickHostingView(rootView: IslandView(m: island, notch: notch))
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
        // A click anywhere on the open island pins it: it stays until Esc, a send, or a click elsewhere.
        NSEvent.addLocalMonitorForEvents(matching: [.leftMouseDown]) { e in
            MainActor.assumeIsolated {
                if e.window === self.panel && self.island.mode == .expanded { self.island.pinned = true }
            }
            return e
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
        island.confirmFinish = false
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

    // Hover (a still pointer for 0.35 s) -> peek, no focus. Leaving only folds it after the pointer has been out of a
    // generous margin around the island for 0.8 s, so reaching for a button never collapses it; a click inside pins it.
    // Sweeping across the menu bar never opens it. Clicks pass through everywhere else.
    func track() {
        let p = NSEvent.mouseLocation
        let speed = hypot(p.x - lastMouse.x, p.y - lastMouse.y) * 30   // pt/s at the 30 Hz tick
        lastMouse = p
        let f = notch.screen.frame
        let sz = CGSize(width: max(island.measured.width, width(for: island.mode, notch: notch, island: island)),
                        height: max(island.measured.height, notch.height))
        let hit = NSRect(x: f.midX - sz.width / 2, y: f.maxY - sz.height, width: sz.width, height: sz.height)
        let onIsland = hit.insetBy(dx: -4, dy: -4).contains(p)
        panel.ignoresMouseEvents = !onIsland
        // Open: stay open anywhere in a wide margin (sideways 32 pt, 48 pt below). Collapsed: the island itself.
        let inside = island.mode == .collapsed ? onIsland
            : NSRect(x: hit.minX - 32, y: hit.minY - 48, width: hit.width + 64, height: hit.height + 48).contains(p)
        island.hovering = inside
        defer { wasInside = inside }

        // A queued alert surfaces as soon as the user is done typing.
        if let a = island.pending, island.mode == .collapsed { island.show(alert: a) }

        if inside {
            collapseAt = nil
            if !wasInside { enteredAt = Date() }
            if speed > 200 { enteredAt = Date() }   // still moving: restart the dwell
            if island.mode == .alert {
                island.alertTask?.cancel()          // pause auto-dismiss while the pointer is on it
            } else if island.mode == .collapsed, let t = enteredAt, Date().timeIntervalSince(t) > 0.35 {
                withAnimation(.spring(response: 0.42, dampingFraction: 0.8)) { island.mode = .expanded }
            }
        } else {
            enteredAt = nil
            // Seen it and moved away: a timed alert goes in 3 s; nudges/planned blocks fold into the wing.
            if wasInside && island.mode == .alert { island.scheduleDismiss(after: 3) }
            if island.mode == .expanded && island.draft.isEmpty && !island.busy && !island.pinned {
                if collapseAt == nil { collapseAt = Date().addingTimeInterval(0.8) }
                if let c = collapseAt, Date() > c {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.85)) { island.mode = .collapsed }
                    collapseAt = nil
                    island.confirmFinish = false
                    giveBackFocus()
                    if island.reply != nil {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 4) { self.island.reply = nil }
                    }
                }
            }
        }
    }
}

// MARK: - Snapshots

/// Extra keys a --state fixture may carry (all optional): "_plan" (/api/calendar/plan), "_needs_setup",
/// "_alerts" [{name, alert}] rendered in alert mode, "_only" [render names] to limit output, "_confirm_finish".
struct SnapNamedAlert: Decodable { let name: String; let alert: AlertEv }
struct SnapExtras: Decodable {
    let _plan: PlanResp?; let _needs_setup: Bool?; let _alerts: [SnapNamedAlert]?; let _only: [String]?
    let _confirm_finish: Bool?
}

// --snapshot DIR [--state FILE.json] [--prefix P]: render every mode offscreen to PNGs
// (visual check without screen-recording permission). --state renders a saved /api/state payload (+ extras above).
@MainActor func snapshot(to dir: String, stateFile: String?, prefix: String) async {
    let m = Island()
    var extras: SnapExtras?
    if let f = stateFile, let d = FileManager.default.contents(atPath: f) {
        do { m.state = try JSONDecoder().decode(StateResp.self, from: d) } catch { print("state decode failed: \(error)") }
        do { extras = try JSONDecoder().decode(SnapExtras.self, from: d) } catch { print("extras decode failed: \(error)") }
        m.plan = extras?._plan
        m.needsSetup = extras?._needs_setup ?? false
    } else {
        m.state = await m.get("/api/state")
        m.online = m.state != nil
        if m.online { await m.refreshExtras() }
    }
    m.online = m.state != nil; m.connecting = false
    if stateFile != nil, let n = m.state?.now { m.now = n }
    if let h = m.state?.habits { m.habits = h }
    m.confirmFinish = extras?._confirm_finish ?? false
    let screen = NSScreen.screens.first { $0.safeAreaInsets.top > 0 } ?? NSScreen.main!
    let notch = Notch(screen: screen)
    // Preload every frame the verdict view might show (ImageRenderer can't wait on network).
    for l in m.state?.recent_verdict?.labels ?? [] { if let u = l.frame_url { await m.loadThumb(u) } }

    let nudge = m.state?.alert?.kind == "nudge" ? m.state!.alert! :
        AlertEv(id: 1, kind: "nudge", text: "You said drawing. I've seen your phone for 30 seconds.", habit: "drawing",
                habit_label: "Drawing", actions: [AlertAction("I'm back", say: "back"), AlertAction("It's on task", say: "it's on task"),
                                                  AlertAction("Snooze 5m", say: "snooze 5")])
    var renders: [(String, Mode, AlertEv?, Bool)] = [
        ("collapsed", .collapsed, nil, true), ("expanded", .expanded, nil, true), ("alert", .alert, nudge, true),
        ("offline_collapsed", .collapsed, nil, false), ("offline_expanded", .expanded, nil, false),
        ("offline_starting", .expanded, nil, false),
    ]
    if let a = m.state?.alert, a.kind != "nudge", a.kind != "verdict", m.shouldShow(a) {
        renders.append(("alert_\(a.kind)", .alert, a, true))
    }
    if let rv = m.state?.recent_verdict {
        let a = m.state?.alert?.kind == "verdict" ? m.state!.alert! :
            AlertEv(id: 2, kind: "verdict", text: rv.summary ?? "", session_id: rv.id, habit: rv.habit, habit_label: rv.label,
                    verdict: rv.verdict, ratio: rv.on_task_ratio)
        renders.append(("verdict", .alert, a, true))
    } else if let a = m.state?.alert, a.kind == "verdict" {
        renders.append(("verdict", .alert, a, true))   // e.g. a Strava claim settled: no session behind it
    }
    for x in extras?._alerts ?? [] { renders.append((x.name, .alert, x.alert, true)) }
    if let only = extras?._only { renders = renders.filter { only.contains($0.0) } }
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
    print("notch \(notch.width)x\(notch.height) hasNotch=\(notch.hasNotch) online=\(saved != nil) renders=\(renders.count)")
}

/// --act LABEL: press a button on the current alert exactly as a click would (say / post+body / url), print the reply.
@MainActor func actOnce(_ label: String) async {
    let m = Island()
    await m.refresh()
    guard let a = m.state?.alert else { print("no alert"); return }
    let screen = NSScreen.main!
    let v = IslandView(m: m, notch: Notch(screen: screen))
    let xs = v.actions(for: a)
    guard let x = xs.first(where: { $0.label == label }) else {
        print("no button “\(label)” on \(a.kind) alert; buttons: \(xs.map(\.label))"); return
    }
    if x.url != nil { print("would open \(x.url!)"); return }
    m.act(x)
    for _ in 0..<30 where m.reply == nil && m.busy == false && x.post != nil {
        try? await Task.sleep(nanoseconds: 100_000_000)
    }
    try? await Task.sleep(nanoseconds: 500_000_000)
    print("pressed “\(x.label)” on \(a.kind): reply=\(m.reply ?? "-") session=\(m.session?.name ?? "none")")
}

let args = CommandLine.arguments
func arg(_ k: String) -> String? { args.firstIndex(of: k).flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil } }
if let label = arg("--act") {
    Task { @MainActor in await actOnce(label); exit(0) }
    RunLoop.main.run()
} else if let dir = arg("--snapshot") {
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
