// Alibi Island — a Dynamic-Island-style bar that lives in the MacBook notch.
// Idle it is exactly the notch. A live session adds two 46 pt wings: a still 16 pt Pinch on the left, the time left on
// the right. Hover (after a short, still dwell) blooms it into a 400 pt panel without stealing focus; click the field
// or press ⌥⌘A to type. Nudges (400 pt, 56 pt Pinch) and verdicts (440 pt, 64 pt Pinch) drop down on their own; a sync
// only glints the wings. Look and motion come from native/shared/Theme.swift. Talks to http://127.0.0.1:8765.
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
                        Rectangle().fill((palette[p.label] ?? P.absent).opacity(i % 2 == 0 ? 1 : 0.7))
                            .frame(width: max(2, (w - 1.5 * CGFloat(ps.count - 1)) * p.share / total))
                    }
                }.frame(width: w, alignment: .leading)
                if rest > 0.01 { Rectangle().fill(P.surface3) }
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
    let coverage: Double?; let windows: [WindowShare]?; let modality: String?; let verified_min: Int?
}
struct StateResp: Decodable {
    let now: Double?
    let session: Session?; let alert: AlertEv?; let witness: String; let witness_label: String?
    let habits: [HabitRef]?; let today: Today?; let recent_verdict: Verdict?; let status_text: String?
    let pinch: PinchState?
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

func displayName(_ key: String) -> String { key == "cpp" ? "C++" : key.prefix(1).uppercased() + key.dropFirst() }  // lint-ok: sentence-cases a habit key, not an eyebrow
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

// MARK: - Tokens

// Colour, type, spacing and motion all come from native/shared/Theme.swift (`Alibi.*`). The island is always dark.
let P = Alibi.Palette.dark
typealias F = Alibi.Fonts
/// Status marks (fills) and status text (inks), by label. Status always travels with a shape: see StatusDot.
let palette: [String: Color] = ["on_task": P.onTask, "phone": P.phone, "off_task": P.offTask, "idle": P.idle, "absent": P.absent]
let statusInk: [String: Color] = ["on_task": P.onTaskInk, "phone": P.warnInk, "off_task": P.warnInk, "idle": P.idleInk,
                                  "absent": P.absentInk]
func verdictInk(_ v: String?) -> Color {
    v == "done" ? P.accentInk : v == "partial" ? P.partialInk : v == "slacked" ? P.warnInk : P.ink2
}
func verdictWash(_ v: String?) -> Color {
    v == "done" ? P.accentWash : v == "partial" ? P.partialWash : v == "slacked" ? P.warnWash : P.surface2
}
/// Snapshots render a single frame: entrances start at rest and the composer is drawn as plain text.
nonisolated(unsafe) var snapshotting = false

// MARK: - Model

enum Mode: Equatable { case collapsed, expanded, alert }
/// How the island opened. The hotkey moves the shape only: no blur, no stagger (Motion.md, recipe 3).
enum Via { case hover, key, alert }

/// The server's Pinch rulebook for this moment (`/api/state` → `pinch`; LANES.md). Optional so an older daemon decodes.
struct PinchState: Decodable, Equatable {
    let mood: String?; let event: String?; let seq: Double?; let age_s: Double?; let line: String?
}

@MainActor
final class Island: ObservableObject {
    @Published var state: StateResp?
    @Published var online = false
    @Published var connecting = true          // first ~3 s after launch: don't flash "offline"
    @Published var mode: Mode = .collapsed
    @Published var via: Via = .hover
    @Published var leaving = false            // closing: the content fades out before the shape folds
    @Published var alert: AlertEv?
    @Published var pending: AlertEv?          // alert queued while the user is typing / pinned
    @Published var reply: String?
    @Published var replyFailed = false
    @Published var draft = "" { didSet { lastInteraction = Date().timeIntervalSince1970 } }
    @Published var busy = false
    @Published var now = Date().timeIntervalSince1970
    @Published var pinned = false             // opened by hotkey/click: stays open until Esc / send / click elsewhere
    @Published var hovering = false
    @Published var composing = false          // the composer has focus: Pinch listens
    @Published var measured: CGSize = .zero   // drawn size of the island (drives the hover hit-rect)
    @Published var thumbs: [String: NSImage] = [:]
    @Published var habits: [HabitRef] = []    // cached, so chips survive the daemon going away
    @Published var plan: PlanResp?            // today's planned blocks
    @Published var needsSetup = false         // first run: no habits / onboarding not finished
    var setupPath = "/"                       // the dashboard opens its wizard by itself while onboarding is unfinished
    @Published var confirmFinish = false      // [Finish] tapped with time still to go: inline confirm
    @Published var seenNudges = 0             // nudges the person has seen this session
    // Pinch: one clip at a time, keyed by the server's seq exactly like the web (play only when seq grows).
    @Published var pinchClip: PinchClip?      // the one-shot playing now; nil = the resting mood
    @Published var pinchClipID = 0
    var pinchForce = false
    @Published var glintUntil: Double = 0     // a quiet "synced": the wings glint and Pinch connects, no panel
    @Published var glintIcon = "heart.fill"
    @Published var shakeID = 0                // a phone nudge shakes the shape once
    @Published var peeking = false            // the pointer rests in the notch, before the 0.35 s dwell opens it
    @Published var peekSide: Double = 0       // -1 pointer left of centre, 1 right: the wing Pinch tilts toward it
    var lastSeq: Double?                      // nil until the first state arrives: record it without playing
    var lastClipAt: Double = 0
    var clipTask: Task<Void, Never>?
    var closeTask: Task<Void, Never>?
    var closedAt: Double = 0
    var lastInteraction = Date().timeIntervalSince1970
    var seenNudgeSession: Int?
    var lastAlertId: Int64?
    var alertTask: Task<Void, Never>?
    var alertShownAt: Double = 0
    var lastExtras: Double = 0
    let launched = Date().timeIntervalSince1970
    var startingUntil: Double = 0             // [Turn on] pressed: show "Starting…" until online or 20 s
    var starting: Bool { !online && now < startingUntil }
    var glinting: Bool { now < glintUntil }
    var reduceMotion: Bool { !snapshotting && NSWorkspace.shared.accessibilityDisplayShouldReduceMotion }
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
    /// The next block that hasn't started yet (shown in the footer, live or not).
    var nextLater: PlanBlock? {
        (plan?.blocks ?? []).filter { $0.state == "planned" && $0.start > now }.min { $0.start < $1.start }
    }
    func markNudgesSeen() {
        guard let s = session else { return }
        seenNudgeSession = s.id; seenNudges = s.nudges ?? 0
    }

    // MARK: Shape changes (every open and close goes through here, so they all use the Theme springs)

    func setMode(_ new: Mode, via v: Via = .hover) {
        lastInteraction = Date().timeIntervalSince1970
        let reduce = reduceMotion
        if new == .collapsed {
            guard mode != .collapsed else { return }
            composing = false
            // Content leaves first (opacity + blur 4, 100 ms ease-out), then the shape folds on `smooth`: no bounce
            // into the hardware notch.
            withAnimation(Alibi.Motion.adaptive(Alibi.Motion.exit(0.15), reduceMotion: reduce)) { leaving = true }
            closeTask?.cancel()
            closeTask = Task { @MainActor in
                try? await Task.sleep(nanoseconds: 100_000_000)
                guard !Task.isCancelled else { return }
                closedAt = Date().timeIntervalSince1970
                withAnimation(Alibi.Motion.adaptive(Alibi.Motion.smooth, reduceMotion: reduce)) { mode = .collapsed; leaving = false }
            }
            return
        }
        closeTask?.cancel()
        leaving = false
        via = v
        let a = v == .key ? Alibi.Motion.key : new == .alert ? Alibi.Motion.bouncy : Alibi.Motion.island
        withAnimation(Alibi.Motion.adaptive(a, reduceMotion: reduce)) { mode = new }
    }

    // MARK: Pinch

    static let clipLength: [PinchClip: Double] = [.hello: 1.4, .connected: 1.0, .surprise: 0.7, .sideeye: 1.3, .nudge: 0.9,
                                                  .celebrate: 1.6, .partial: 1.0, .supportive: 1.4]
    static let verdictClip: [String: PinchClip] = ["done": .celebrate, "partial": .partial, "slacked": .supportive]

    /// Same rule as the web: play `event` once when `seq` grows and the moment is under 15 s old; on the first state
    /// only record `seq`, so a relaunch never replays an old event.
    func pinchFrom(_ p: PinchState?) {
        guard let p, let seq = p.seq else { return }
        defer { lastSeq = max(lastSeq ?? 0, seq) }
        guard let last = lastSeq, seq > last, (p.age_s ?? 0) < 15,
              let e = p.event, let clip = PinchClip(rawValue: e) else { return }
        switch clip {
        case .sideeye, .nudge: play(.sideeye, force: true)     // one one-shot: the rig chains side-eye into nudge
        case .celebrate, .partial, .supportive: play(clip, force: true, after: 0.3)   // after the shape has dropped
        default: play(clip)
        }
    }

    /// Hover peek (Motion.md recipe 3): the closed shape grows 12 pt wider and 4 pt taller on `snappy`.
    func setPeek(_ on: Bool, side: Double) {
        guard on != peeking || (on && side != peekSide) else { return }
        withAnimation(Alibi.Motion.adaptive(Alibi.Motion.snappy, reduceMotion: reduceMotion)) { peeking = on; peekSide = side }
    }

    /// Hands a one-shot to the rig (which keeps the 90 s cooldown and chains side-eye into nudge). `force` is for
    /// verdicts and nudges, which ride the server's own cooldowns. `pinchClip` stays set while the clip plays, so the
    /// bloom can follow it.
    func play(_ clip: PinchClip, force: Bool = false, after delay: Double = 0) {
        let t = Date().timeIntervalSince1970
        if !force && t - lastClipAt < 90 { return }
        lastClipAt = t
        if clip == .connected { glintUntil = t + 3 }
        clipTask?.cancel()
        clipTask = Task { @MainActor in
            if delay > 0 { try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000)) }
            guard !Task.isCancelled else { return }
            pinchForce = force; pinchClip = clip; pinchClipID += 1
            let len = (Island.clipLength[clip] ?? 1) + (clip == .sideeye ? Island.clipLength[.nudge] ?? 0 : 0)
            try? await Task.sleep(nanoseconds: UInt64(len * 1_000_000_000))
            if !Task.isCancelled { pinchClip = nil }
        }
    }

    // MARK: Polling

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
            pinchFrom(s.pinch)
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
        // A sync is good news that needs nothing from you: a wing glint and Pinch `connected`, never a panel.
        if isSynced(a) && (a.actions ?? []).isEmpty {
            glintIcon = a.text.hasPrefix("Strava") || a.title?.contains("Strava") == true ? "figure.run" : "heart.fill"
            glintUntil = Date().timeIntervalSince1970 + 3
            if state?.pinch == nil { play(.connected) }
            return
        }
        // Don't yank the island out from under someone typing: queue it as an edge line instead.
        if (pinned || !draft.isEmpty) && mode == .expanded {
            pending = a
            return
        }
        pending = nil
        alert = a
        alertShownAt = Date().timeIntervalSince1970
        if a.kind == "nudge" { markNudgesSeen() }
        setMode(.alert, via: .alert)
        if state?.pinch == nil {      // an older daemon: pick the clip from the alert itself
            if a.kind == "nudge" { play(.sideeye, force: true) }
            else if a.kind == "verdict", let c = Island.verdictClip[a.verdict ?? ""] { play(c, force: true, after: 0.3) }
        }
        // A phone nudge shakes once at +680 ms; soft drift never does.
        if a.kind == "nudge" && (a.label ?? session?.drifting?.label) == "phone" && !reduceMotion {
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 680_000_000)
                if mode == .alert { shakeID += 1 }
            }
        }
        // The Mac is silent by default (Mascot.md). Opt-in: `defaults write <app> alibi.sound -bool YES`, wins only.
        if a.kind == "verdict" && a.verdict == "done" && UserDefaults.standard.bool(forKey: "alibi.sound") {
            let pop = NSSound(named: "Pop"); pop?.volume = 0.3; pop?.play()
        }
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
        setMode(.collapsed)
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
            if pinned && draft.isEmpty { pinned = false; setMode(.collapsed) }
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

// MARK: - Alert buttons

/// A button on an alert: the island's label for it, plus the server's action (posted unchanged).
struct AlertButton { let title: String; let action: AlertAction; var icon: String? = nil }

/// Server actions with the island's plainer labels. The payload never changes, only the words on the button.
func alertButtons(_ a: AlertEv) -> [AlertButton] {
    var xs = a.actions ?? []
    if xs.isEmpty {
        switch a.kind {
        case "nudge": xs = [AlertAction("Back to it", say: "back"), AlertAction("This counts", say: "it's on task"),
                            AlertAction("Quiet 5 min", say: "snooze 5")]
        case "verdict":
            if let id = a.session_id {
                xs = [AlertAction("See proof", url: "/#session-\(id)"), AlertAction("Fix a moment", url: "/#session-\(id)")]
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
            case (_, "Fix samples"), (_, "Something's wrong?"): "Fix a moment"
            case (_, let t) where t.hasSuffix("m") && t.hasPrefix("Start "): t.dropLast() + " min"
            case (_, let t) where t.hasPrefix("Again ") && t.hasSuffix("m"): "Again · " + t.dropFirst(6).dropLast() + " min"
            default: x.label
        }
        return AlertButton(title: l, action: x, icon: l == "See proof" ? "eye" : l == "Watch replay" ? "film" : nil)
    }
}

/// Every name `--act` accepts for a button: the label on screen, the server's label, and the pre-redesign label.
func actLabels(_ b: AlertButton) -> [String] {
    var names = [b.title, b.action.label]
    let say = b.action.say ?? ""
    if say == "back" { names.append("I'm back") }
    if say == "it's on task" { names.append("It's on task") }
    if say.hasPrefix("snooze") { names.append("Snooze \(say.split(separator: " ").last.map(String.init) ?? "5")m") }
    return names
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
// (or a planned-now block / fresh reply / a quiet sync glint) adds two 46 pt wings, like an iPhone Live Activity.
let wing: CGFloat = 46
@MainActor func hasWings(_ island: Island) -> Bool {
    island.session != nil || island.reply != nil || island.glinting || (island.online && island.upNext?.state == "now")
}
/// Top flare and bottom radius (Surfaces.md): idle hugs the hardware (6/10), wings 6/12, open 12/radius-xl.
@MainActor func corners(_ mode: Mode, _ island: Island) -> (flare: CGFloat, bottom: CGFloat) {
    mode == .collapsed ? (6, island.peeking ? 14 : hasWings(island) ? 12 : 10) : (12, Alibi.Radius.xl)
}
@MainActor func width(for mode: Mode, notch: Notch, island: Island) -> CGFloat {
    switch mode {
    case .collapsed:   // wings: a notch + 92 body plus 6 pt flares; a peek adds 12
        return notch.width + (hasWings(island) ? 2 * (wing + 6) : 0) + (island.peeking ? 12 : 0)
    case .expanded: return 400 + 24                                        // a 400 pt body plus two 12 pt flares
    case .alert: return (island.alert?.kind == "verdict" ? 440 : 400) + 24
    }
}

struct SizeKey: PreferenceKey {
    static var defaultValue: CGSize = .zero
    static func reduce(value: inout CGSize, nextValue: () -> CGSize) { value = nextValue() }
}

// MARK: - Shape

/// One shape whose size and radii animate (never two crossfading shapes). The top corners flare out into the menu bar.
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

// MARK: - Motion modifiers

/// Content in (Motion.md): opacity, blur 8 → 0 and scale 0.96 from the top, 30 ms per tier (three tiers at most),
/// starting 60 ms after the shape. The hotkey path is a 120 ms fade with no blur or stagger; reduced motion fades only.
struct Tier: ViewModifier {
    let index: Int; var lift = false; var plain = false
    @Environment(\.accessibilityReduceMotion) private var reduce
    @State private var shown = snapshotting
    func body(content: Content) -> some View {
        let rest = shown || reduce || plain
        content
            .opacity(shown ? 1 : 0)
            .blur(radius: rest ? 0 : 8)
            .scaleEffect(rest ? 1 : 0.96, anchor: .top)
            .offset(y: rest || !lift ? 0 : 6)
            .onAppear {
                guard !shown else { return }
                let a = plain ? Alibi.Motion.easeOut(Alibi.Motion.durMicro)
                    : Alibi.Motion.snappy.delay(0.06 + Alibi.Motion.islandStagger * Double(min(index, 2)))
                withAnimation(Alibi.Motion.adaptive(a, reduceMotion: reduce)) { shown = true }
            }
    }
}

/// Wings slide out from the camera: x ±24 → 0 with opacity on `snappy`; the right wing follows 60 ms later.
struct WingIn: ViewModifier {
    let dx: CGFloat; let delay: Double
    @Environment(\.accessibilityReduceMotion) private var reduce
    @State private var shown = snapshotting
    func body(content: Content) -> some View {
        content
            .opacity(shown ? 1 : 0)
            .offset(x: shown || reduce ? 0 : dx)
            .onAppear {
                guard !shown else { return }
                withAnimation(Alibi.Motion.adaptive(Alibi.Motion.snappy.delay(delay), reduceMotion: reduce)) { shown = true }
            }
    }
}

/// One 360 ms shake for a phone nudge: 0, −6, 5, −3, 2, 0 pt (ease-out keyframes).
struct Shake: ViewModifier {
    let trigger: Int
    func body(content: Content) -> some View {
        content.keyframeAnimator(initialValue: CGFloat(0), trigger: trigger) { view, x in
            view.offset(x: x)
        } keyframes: { _ in
            KeyframeTrack {
                CubicKeyframe(-6, duration: 0.072)
                CubicKeyframe(5, duration: 0.072)
                CubicKeyframe(-3, duration: 0.072)
                CubicKeyframe(2, duration: 0.072)
                CubicKeyframe(0, duration: 0.072)
            }
        }
    }
}

extension View {
    func tier(_ i: Int, lift: Bool = false, plain: Bool = false) -> some View { modifier(Tier(index: i, lift: lift, plain: plain)) }
}

extension AnyTransition {
    /// Content leaves fast (120 ms, ease-out, no bounce); the shape has its own spring.
    static var exitFade: AnyTransition {
        .asymmetric(insertion: .identity, removal: .opacity.animation(Alibi.Motion.easeOut(Alibi.Motion.durMicro)))
    }
}

// MARK: - Small views

func mmss(_ s: Double) -> String {
    let s = max(0, Int(s.rounded()))
    return s >= 3600 ? String(format: "%d:%02d:%02d", s / 3600, (s % 3600) / 60, s % 60)
                     : String(format: "%d:%02d", s / 60, s % 60)
}

struct Ring: View {
    let progress: Double; let colour: Color; var width: CGFloat = 4
    var body: some View {
        ZStack {
            Circle().stroke(P.surface3, lineWidth: width)
            Circle().trim(from: 0, to: progress).stroke(colour, style: StrokeStyle(lineWidth: width, lineCap: .round))
                .rotationEffect(.degrees(-90))
        }
    }
}

/// The system spinner; snapshots draw a still ring (ImageRenderer can't draw ProgressView).
struct Spinner: View {
    var size: CGFloat = 12
    var body: some View {
        if snapshotting {
            Circle().trim(from: 0, to: 0.7).stroke(P.ink2, style: StrokeStyle(lineWidth: 1.5, lineCap: .round))
                .frame(width: size, height: size)
        } else {
            ProgressView().controlSize(.mini).tint(P.ink2).frame(width: size, height: size)
        }
    }
}

/// Status is colour plus shape: ● on task, ○ idle, ■ phone, ▨ off task, ◌ absent (README "Colour").
struct StatusDot: View {
    let label: String; var size: CGFloat = 8
    var body: some View {
        let c = palette[label] ?? P.absent
        Group {
            switch label {
            case "on_task": Circle().fill(c)
            case "idle": Circle().strokeBorder(c, lineWidth: 2)
            case "phone": RoundedRectangle(cornerRadius: size * 0.25, style: .continuous).fill(c)
            case "off_task": Circle().fill(c).overlay(Hatch().stroke(P.island, lineWidth: max(1, size / 8))).clipShape(Circle())
            default: Circle().strokeBorder(c, style: StrokeStyle(lineWidth: 1.5, dash: [2, 1.6]))
            }
        }
        .frame(width: size, height: size)
        .accessibilityLabel(human(label))
    }
}

struct Hatch: Shape {
    func path(in r: CGRect) -> Path {
        var p = Path()
        for i in stride(from: -r.height, through: r.width, by: max(2, r.width / 2.5)) {
            p.move(to: CGPoint(x: r.minX + i, y: r.maxY)); p.addLine(to: CGPoint(x: r.minX + i + r.height, y: r.minY))
        }
        return p
    }
}

/// ✓ Done, ◐ Partly, ✕ Slacked on a 10% wash: a glyph and a word, never a slab (VerdictPill).
struct VerdictPill: View {
    let verdict: String?; var ratio: Double? = nil
    var body: some View {
        let (glyph, word): (String, String) = switch verdict {
            case "done": ("checkmark", "Done"); case "partial": ("circle.lefthalf.filled", "Partly")
            case "slacked": ("xmark", "Slacked"); default: ("circle.dashed", "Ended") }
        HStack(spacing: Alibi.Space.s1) {
            Image(systemName: glyph).font(F.sans(11, .bold))
            Text(word).font(F.sans(13, .semibold))
            if let r = ratio {
                Text("·").font(F.sans(13, .medium)).opacity(0.7)
                Text("\(Int((r * 100).rounded()))%").font(F.sans(13, .medium)).monospacedDigit()
            }
        }
        .foregroundStyle(verdictInk(verdict))
        .padding(.leading, Alibi.Space.s2).padding(.trailing, Alibi.Space.s3).frame(height: 28)
        .background(Capsule().fill(verdictWash(verdict)))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Verdict: \(word.lowercased())\(ratio.map { ", \(Int(($0 * 100).rounded()))%" } ?? "")")
    }
}

struct Keycap: View {
    let text: String
    var body: some View {
        Text(text).font(F.mono(11)).foregroundStyle(P.ink2)
            .padding(.horizontal, 6).frame(height: 20)
            .background(RoundedRectangle(cornerRadius: Alibi.Radius.xs, style: .continuous).fill(P.surface2))
            .overlay(RoundedRectangle(cornerRadius: Alibi.Radius.xs, style: .continuous).strokeBorder(P.hairlineStrong, lineWidth: 0.5))
    }
}

/// Every pressable thing: a 0.97 press, so clicks feel heard. Reduced motion keeps the click and drops the scale.
struct Pressable: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View { PressBody(configuration: configuration) }
    struct PressBody: View {
        let configuration: Configuration
        @Environment(\.accessibilityReduceMotion) private var reduce
        var body: some View {
            configuration.label
                .scaleEffect(configuration.isPressed && !reduce ? 0.97 : 1)
                .animation(Alibi.Motion.easeOut(Alibi.Motion.durMicro), value: configuration.isPressed)
        }
    }
}

/// The island's buttons (Alibi.Button): primary is green with black text (one per view), secondary a raised surface
/// with a hairline, quiet a bare label that lifts on hover.
struct IslandButton: View {
    enum Variant { case primary, secondary, quiet }
    let title: String; var variant: Variant = .secondary; var icon: String? = nil; var small = false
    let action: () -> Void
    @State private var hover = false
    var body: some View {
        let shape = RoundedRectangle(cornerRadius: Alibi.Radius.sm, style: .continuous)
        Button(action: action) {
            HStack(spacing: Alibi.Space.s2) {
                if let icon { Image(systemName: icon).font(F.sans(12, .semibold)) }
                Text(title).font(F.sans(small ? 12 : 14, variant == .primary ? .semibold : .medium)).lineLimit(1).fixedSize()
            }
            .padding(.horizontal, small ? Alibi.Space.s3 : Alibi.Space.s4).frame(height: small ? 28 : 36)
            .foregroundStyle(foreground)
            .background(shape.fill(background))
            .overlay(shape.strokeBorder(variant == .secondary ? P.hairline : .clear, lineWidth: 1))
            .contentShape(shape)
        }
        .buttonStyle(Pressable())
        .onHover { hover = $0 }
    }
    var background: Color {
        switch variant {
        case .primary: return hover ? P.accentHover : P.accent
        case .secondary: return hover ? P.surface3 : P.surface2
        case .quiet: return hover ? P.surface2 : .clear
        }
    }
    var foreground: Color {
        switch variant {
        case .primary: return P.onAccent
        case .secondary: return P.ink
        case .quiet: return hover ? P.ink : P.ink2
        }
    }
}

/// Small square icon button (header): 28 pt target, radius-xs.
struct IconButton: View {
    let icon: String; var help = ""; let action: () -> Void
    @State private var hover = false
    var body: some View {
        Button(action: action) {
            Image(systemName: icon).font(F.sans(12, .medium))
                .foregroundStyle(hover ? P.ink : P.ink2)
                .frame(width: 28, height: 28)
                .background(RoundedRectangle(cornerRadius: Alibi.Radius.xs, style: .continuous).fill(hover ? P.surface2 : .clear))
                .contentShape(Rectangle())
        }
        .buttonStyle(Pressable()).onHover { hover = $0 }.help(help).accessibilityLabel(help)
    }
}

/// Suggestion chips (Chip spec: 32 pt, radius-xs): a quiet surface-1 at rest, surface-2 on hover, a press. `quiet`
/// rests bare (slim rows such as "Finish setup"). The content shape makes the whole chip take the click, not its text.
struct Chip: ButtonStyle {
    var quiet = false
    func makeBody(configuration: Configuration) -> some View { ChipBody(configuration: configuration, quiet: quiet) }
    struct ChipBody: View {
        let configuration: Configuration
        let quiet: Bool
        @Environment(\.accessibilityReduceMotion) private var reduce
        @State private var hover = false
        var body: some View {
            let shape = RoundedRectangle(cornerRadius: quiet ? Alibi.Radius.sm : Alibi.Radius.xs, style: .continuous)
            configuration.label
                .background(shape.fill(hover ? P.surface2 : quiet ? .clear : P.surface1))
                .contentShape(shape)
                .scaleEffect(configuration.isPressed && !reduce ? 0.97 : 1)
                .animation(Alibi.Motion.easeOut(Alibi.Motion.durMicro), value: configuration.isPressed)
                .animation(Alibi.Motion.adaptive(Alibi.Motion.micro, reduceMotion: reduce), value: hover)
                .onHover { hover = $0 }
        }
    }
}

extension View {
    /// The one card surface: surface-1, a hairline edge, radius-md 16 (concentric inside the 28 pt island at a 12 inset).
    func card(highlight: Bool = false) -> some View {
        background(RoundedRectangle(cornerRadius: Alibi.Radius.md, style: .continuous).fill(P.surface1))
            .overlay(RoundedRectangle(cornerRadius: Alibi.Radius.md, style: .continuous)
                .strokeBorder(highlight ? P.accent.opacity(0.45) : P.hairline, lineWidth: 1))
    }
}

/// The last few samples as status marks, newest on the right (SampleStrip).
struct SampleDots: View {
    let labels: [String]
    var body: some View {
        HStack(spacing: Alibi.Space.s1) {
            ForEach(Array(labels.enumerated()), id: \.offset) { _, l in StatusDot(label: l, size: 8) }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Last \(labels.count) checks: \(labels.filter { $0 == "on_task" }.count) on task")
    }
}

/// A verdict frame: 96 × 54, radius-xs, a strong hairline, its status mark and the time it was taken.
struct FrameThumb: View {
    let label: LabelEv; let image: NSImage?
    var body: some View {
        let shape = RoundedRectangle(cornerRadius: Alibi.Radius.xs, style: .continuous)
        ZStack {
            P.surface2
            if let image { Image(nsImage: image).resizable().aspectRatio(contentMode: .fill) }
            else { Image(systemName: "camera").font(F.sans(13)).foregroundStyle(P.ink3) }
        }
        .frame(width: 96, height: 54).clipShape(shape)
        .overlay(shape.strokeBorder(P.hairlineStrong, lineWidth: 1))
        .overlay(alignment: .topTrailing) {
            StatusDot(label: label.label, size: 8).padding(2).background(Circle().fill(P.island)).padding(3)
        }
        .overlay(alignment: .bottomLeading) {
            Text(clock(label.ts)).font(F.islandFloor).monospacedDigit().foregroundStyle(P.ink)
                .padding(.horizontal, Alibi.Space.s1).padding(.vertical, 1)
                .background(RoundedRectangle(cornerRadius: 4, style: .continuous).fill(P.surface1))
                .padding(Alibi.Space.s1)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Frame at \(clock(label.ts)), \(human(label.label).lowercased())")
    }
}

// Wrapping row: every chip stays reachable, the panel grows a line if needed.
struct Flow: Layout {
    var spacing: CGFloat = 8
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
    @Environment(\.accessibilityReduceMotion) private var reduce

    var session: Session? { m.session }
    var current: String { session?.recent?.last ?? session?.labels.last?.label ?? "on_task" }
    /// A break is never a failure: while one runs, drifting is ignored everywhere (wing, edge, status line, nudges).
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
    var plannedNow: PlanBlock? { m.upNext.flatMap { $0.state == "now" ? $0 : nil } }
    var open: Bool { m.mode != .collapsed }
    var plain: Bool { m.via == .key }
    /// The lens tells the truth: it glows only while the camera is sampling.
    var cameraSampling: Bool {
        guard let s = session, !onBreak else { return false }
        return s.modality == "physical" || s.modality == "hybrid"
    }

    var body: some View {
        let w = width(for: m.mode, notch: notch, island: m)
        let c = corners(m.mode, m)
        VStack(spacing: 0) {
            content
                .opacity(m.leaving ? 0 : 1)
                .blur(radius: m.leaving && !reduce ? 4 : 0)
                .padding(.horizontal, open ? c.flare + Alibi.Space.s3 : c.flare)
                .padding(.bottom, open ? Alibi.Space.s3 : 0)
                .frame(width: w, alignment: .top)
                .fixedSize(horizontal: false, vertical: true)
                .background(alignment: .top) {
                    // shadow-island when open; none when closed (it would outline the hardware notch).
                    NotchShape(top: c.flare, bottom: c.bottom)
                        .fill(P.island)
                        .shadow(color: .black.opacity(open ? 0.5 : 0), radius: 6, y: 2)
                        .shadow(color: .black.opacity(open ? 0.35 : 0), radius: 24, y: 12)
                }
                .overlay { edge(c) }
                .background(GeometryReader { g in Color.clear.preference(key: SizeKey.self, value: g.size) })
                .onPreferenceChange(SizeKey.self) { s in MainActor.assumeIsolated { m.measured = s } }
                .modifier(Shake(trigger: m.shakeID))
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .animation(Alibi.Motion.adaptive(Alibi.Motion.snappy, reduceMotion: reduce), value: hasWings(m))
        .animation(Alibi.Motion.adaptive(Alibi.Motion.snappy, reduceMotion: reduce), value: session?.id)
        .animation(Alibi.Motion.adaptive(Alibi.Motion.smooth, reduceMotion: reduce), value: m.confirmFinish)
        .preferredColorScheme(.dark)
    }

    /// First run with nothing to track: the panel is the welcome. Once habits exist, setup never hides the composer.
    var welcoming: Bool {
        m.needsSetup && session == nil && m.habits.isEmpty && (m.state?.habits ?? []).isEmpty && (m.online || m.connecting)
    }

    /// A still hairline on the closed shape: warn while drifting, accent while an alert waits. No loops in the wings.
    @ViewBuilder func edge(_ c: (flare: CGFloat, bottom: CGFloat)) -> some View {
        if m.mode == .collapsed && hasWings(m) && drifting != nil {
            NotchShape(top: c.flare, bottom: c.bottom).stroke(P.warn.opacity(0.6), lineWidth: 1)
        } else if m.pending != nil && m.mode == .collapsed {
            NotchShape(top: c.flare, bottom: c.bottom).stroke(P.accent.opacity(0.6), lineWidth: 1)
        }
    }

    @ViewBuilder var content: some View {
        switch m.mode {
        case .collapsed: collapsed
        case .expanded: expanded.transition(.exitFade)
        case .alert:
            Group {
                if m.alert?.kind == "verdict" { verdictView } else { alertView }
            }
            .id(m.alert?.id ?? 0)
            .transition(.exitFade)
        }
    }

    // MARK: Pinch

    /// Pinch at a rung of the size ladder, playing the current one-shot. The rig rests after 2 minutes without news,
    /// lights the lens only while the camera samples, and draws key frames under reduced motion. Snapshots draw the
    /// clip's key frame (one still image can't wait for a timeline).
    @ViewBuilder func pinch(_ mood: PinchMood, size: CGFloat) -> some View {
        if snapshotting {
            let c = m.pinchClip
            var p = PinchView.pose(mood: mood, clip: c, ms: c?.motion.key ?? mood.motion.key)
            let _ = (p.lensLit = p.lensLit || cameraSampling)
            PinchFigure(pose: p, size: size).accessibilityHidden(true)
        } else {
            PinchView(mood: mood, clip: m.pinchClip, clipID: m.pinchClipID, size: size, camera: cameraSampling,
                      force: m.pinchForce)
                .accessibilityHidden(true)
        }
    }

    /// The 16 pt wing Pinch is always still: focused, a side-eye while drifting, sleepy on a break, connected on a sync.
    var wingPose: PinchPose {
        var p: PinchPose
        if m.glinting { p = PinchView.pose(mood: .idle, clip: .connected, ms: PinchClip.connected.motion.key) }
        else if onBreak { p = PinchView.pose(mood: .sleepy, clip: nil, ms: PinchMood.sleepy.motion.key) }
        else if drifting != nil { p = PinchView.pose(mood: .focused, clip: .sideeye, ms: PinchClip.sideeye.motion.key) }
        else if session != nil { p = PinchView.pose(mood: .focused, clip: nil, ms: PinchMood.focused.motion.key) }
        else { p = PinchView.pose(mood: .idle, clip: nil, ms: PinchMood.idle.motion.key) }
        p.lensLit = m.glinting || cameraSampling
        return p
    }

    // MARK: Collapsed: the camera housing, plus compact leading/trailing wings while something is live.

    var collapsed: some View {
        HStack(spacing: 0) {
            if hasWings(m) {
                wingLeading.frame(width: wing).modifier(WingIn(dx: 24, delay: 0.1))
                Color.clear.frame(maxWidth: .infinity)
                wingTrailing.frame(width: wing).modifier(WingIn(dx: -24, delay: 0.16))
            } else {
                Color.clear.frame(maxWidth: .infinity)
            }
        }
        .frame(height: notch.height + (m.peeking ? 4 : 0))
    }

    /// Leading wing: Pinch (a reply glyph when Alibi just answered and nothing is live).
    @ViewBuilder var wingLeading: some View {
        if session == nil && m.reply != nil && !m.glinting {
            Image(systemName: m.replyFailed ? "exclamationmark" : "checkmark")
                .font(F.sans(12, .bold)).foregroundStyle(m.replyFailed ? P.warnInk : P.accentInk)
        } else {
            PinchFigure(pose: wingPose, size: 16)
                .rotationEffect(.degrees(m.peeking && !reduce ? 8 * m.peekSide : 0), anchor: .bottom)
                .accessibilityHidden(true)
        }
    }

    /// Trailing wing: the one value that matters (Voice.md "Island wing values").
    @ViewBuilder var wingTrailing: some View {
        if session != nil {
            if onBreak {
                HStack(spacing: 3) {
                    Image(systemName: "cup.and.saucer.fill").font(F.sans(11, .semibold))
                    Text(short(breakLeft)).font(F.islandWing)
                }
                .foregroundStyle(P.partialInk).fixedSize()
            } else if let d = drifting {
                // The mark says what (■ phone, ▨ off task, ◌ away, ○ idle); the value says for how long. "phone" itself
                // doesn't fit 40 pt beside its mark.
                HStack(spacing: 3) {
                    StatusDot(label: d.label, size: 8)
                    Text(short((d.since_s ?? 0) + drift)).font(F.islandWing).foregroundStyle(statusInk[d.label] ?? P.warnInk)
                }
                .fixedSize()
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(wingWord(d)), \(short((d.since_s ?? 0) + drift))")
            } else {
                Text(short(sessionLeft)).font(F.islandWing).foregroundStyle(P.accentInk)
                    .contentTransition(.numericText(countsDown: true)).lineLimit(1).fixedSize()
            }
        } else if m.glinting {
            Image(systemName: m.glintIcon).font(F.sans(12, .semibold)).foregroundStyle(P.accentInk)
        } else if m.reply == nil, plannedNow != nil {
            Text("now").font(F.islandWing).foregroundStyle(P.ink).fixedSize()
        }
    }

    /// 24m · 45s · 1h 5m: fits a 46 pt wing.
    func short(_ s: Double) -> String {
        let s = Int(max(0, s).rounded())
        if s >= 3600 { return "\(s / 3600)h \((s % 3600) / 60)m" }
        return s >= 60 ? "\(Int((Double(s) / 60).rounded(.up)))m" : "\(s)s"
    }

    func wingWord(_ d: Drifting) -> String {
        switch d.label {
        case "phone": return "phone"
        case "absent": return "away"
        case "idle": return "idle"
        default:
            let p = d.label_text.map(placeName) ?? ""
            return !p.isEmpty && p.count <= 6 ? p : "off"
        }
    }

    // MARK: Expanded

    var expanded: some View {
        VStack(alignment: .leading, spacing: 0) {
            header.tier(0, plain: plain)
            Group {
                if !m.online && !m.connecting {
                    offlineCard
                } else if welcoming {
                    welcomeCard
                } else if let s = session {
                    VStack(alignment: .leading, spacing: Alibi.Space.s3) { sessionCard(s); sessionControls(s) }
                } else {
                    VStack(alignment: .leading, spacing: Alibi.Space.s3) {
                        if let b = plannedNow { upNextCard(b) }
                        composer
                    }
                }
            }
            .padding(.top, Alibi.Space.s2)
            .tier(1, plain: plain)
            if let r = m.reply { replyLine(r).padding(.top, Alibi.Space.s3).tier(1, plain: plain) }
            if !welcoming {
                VStack(alignment: .leading, spacing: Alibi.Space.s3) {
                    if session == nil && !m.habits.isEmpty && (m.online || m.connecting) {
                        chips.opacity(m.online ? 1 : 0.45)
                    }
                    if session == nil && m.needsSetup && m.online { finishSetupRow }
                    Rectangle().fill(P.hairline).frame(height: 1).padding(.horizontal, Alibi.Space.s1)
                    footer
                }
                .padding(.top, Alibi.Space.s3)
                .tier(2, lift: true, plain: plain)
            }
        }
        .onAppear {
            m.markNudgesSeen()
            if m.pinned { DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { focused = true } }
        }
        .onChange(of: m.pinned) { _, p in if p { focused = true } }
        .onChange(of: focused) { _, f in m.composing = f }
    }

    var statusText: String {
        guard m.online else { return "Off" }
        guard let s = session else { return "Ready" }
        if onBreak { return "On a break" }
        switch s.modality {
        case "digital": return "Watching your screen"
        case "hybrid": return "Watching desk and screen"
        default: return "Watching your desk"
        }
    }

    /// The notch row: only the far edges are visible beside the camera. Pinch, the wordmark and the online dot on the
    /// left; open-dashboard and quit on the right.
    var header: some View {
        let mood: PinchMood = m.composing ? .listening : onBreak ? .sleepy : session != nil ? .focused : .idle
        return HStack(spacing: Alibi.Space.s2) {
            // No Pinch on system errors (Mascot.md); one Pinch per view, so the welcome's 56 pt Pinch replaces this one.
            if (m.online || m.connecting) && !welcoming { pinch(mood, size: 28) }
            Text("ALIBI").font(F.islandWordmark).tracking(F.wordmarkTracking).foregroundStyle(P.ink)
            Circle().fill(m.online ? P.accent : P.partial).frame(width: 6, height: 6)
                .accessibilityLabel(m.online ? "Online" : "Offline")
            Spacer(minLength: notch.width)
            IconButton(icon: "arrow.up.right", help: "Open the dashboard") { m.open("/") }
            IconButton(icon: "power", help: "Quit Alibi (stops watching)") { NSApp.terminate(nil) }
        }
        .padding(.horizontal, Alibi.Space.s1)
        .frame(height: notch.height, alignment: .center)
    }

    /// Quiet line under everything: today's habits as marks, then what's next (or the hotkey).
    var footer: some View {
        HStack(spacing: Alibi.Space.s2) {
            if (m.connecting || m.starting) && !m.online {
                Spinner(size: 12)
                Text(m.starting ? "Starting…" : "Connecting…")
            } else if m.online, let t = m.state?.today, let total = t.habits_total, total > 0 {
                HStack(spacing: Alibi.Space.s1) {
                    ForEach(0..<min(total, 8), id: \.self) { i in
                        StatusDot(label: i < (t.habits_done ?? 0) ? "on_task" : "absent", size: 8)
                    }
                }
                .accessibilityHidden(true)
                Text("\(t.habits_done ?? 0) of \(total) today").monospacedDigit().fixedSize()
                    .accessibilityLabel("\(t.habits_done ?? 0) of \(total) habits done today")
            } else {
                Text(statusText)
            }
            Spacer(minLength: Alibi.Space.s2)
            if let b = m.nextLater, plannedNow == nil {
                Text("Next up: \(b.name) at \(b.at)").monospacedDigit().truncationMode(.tail)
            } else {
                Keycap(text: "⌥⌘A")
            }
        }
        .font(F.islandSecondary).foregroundStyle(P.ink2).lineLimit(1)
        .padding(.horizontal, Alibi.Space.s1)
        .help(m.online ? "Checked by: \(m.state?.witness_label ?? m.state?.witness ?? "—")" : "")
    }

    /// Habits exist but the wizard isn't finished: one slim, quiet row that reopens it. It never blocks the composer.
    var finishSetupRow: some View {
        Button { m.open(m.setupPath) } label: {
            HStack(spacing: Alibi.Space.s2) {
                Image(systemName: "checklist").font(F.sans(12, .medium)).foregroundStyle(P.ink3)
                Text("Setup isn't finished").foregroundStyle(P.ink2)
                Spacer(minLength: Alibi.Space.s2)
                Text("Finish setup").fontWeight(.medium).foregroundStyle(P.ink)
                Image(systemName: "arrow.up.right").font(F.sans(10, .semibold)).foregroundStyle(P.ink3)
            }
            .font(F.islandSecondary).lineLimit(1)
            .padding(.horizontal, Alibi.Space.s2).frame(height: 32)
        }
        .buttonStyle(Chip(quiet: true))
        // Content lines up with the footer and divider (s1 in); the hover wash keeps s2 of air around it.
        .padding(.horizontal, -Alibi.Space.s1)
        .help("Opens the setup in your browser")
    }

    func replyLine(_ r: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: Alibi.Space.s2) {
            if m.replyFailed {
                Image(systemName: "exclamationmark.circle.fill").font(F.sans(12)).foregroundStyle(P.warnInk)
            }
            Text(r).font(F.islandVoice).foregroundStyle(P.ink)
                .lineLimit(3).fixedSize(horizontal: false, vertical: true)
        }
        .padding(.horizontal, Alibi.Space.s1)
    }

    /// The composer: one field on surface-2 with a strong hairline, the round green send button on the right.
    var composer: some View {
        let canSend = !m.draft.trimmingCharacters(in: .whitespaces).isEmpty && !m.busy
        let shape = RoundedRectangle(cornerRadius: Alibi.Radius.md, style: .continuous)
        return HStack(spacing: Alibi.Space.s2) {
            Group {
                if snapshotting {
                    Text(m.draft.isEmpty ? "What are you about to do?" : m.draft)
                        .foregroundStyle(m.draft.isEmpty ? P.ink3 : P.ink)
                        .frame(maxWidth: .infinity, alignment: .leading)
                } else {
                    TextField("", text: $m.draft, prompt: Text("What are you about to do?").foregroundStyle(P.ink3))
                        .textFieldStyle(.plain).foregroundStyle(P.ink)
                        .focused($focused)
                        .onSubmit { Task { await m.send(m.draft); m.unpinSoon() } }
                        .onExitCommand { Controller.shared?.collapse() }
                }
            }
            .font(F.islandVoice)
            Button { Task { await m.send(m.draft); m.unpinSoon() } } label: {
                Image(systemName: m.busy ? "ellipsis" : "arrow.up").font(F.sans(13, .bold))
                    .foregroundStyle(canSend ? P.onAccent : P.ink3)
                    .frame(width: 32, height: 32)
                    .background(Circle().fill(canSend ? P.accent : P.surface3))
            }
            .buttonStyle(Pressable()).disabled(!canSend).help("Send (Return)").accessibilityLabel("Send")
        }
        .padding(.leading, Alibi.Space.s4).padding(.trailing, Alibi.Space.s2).frame(minHeight: 48)
        .background(shape.fill(P.surface2))
        .overlay(shape.strokeBorder(focused ? P.focusRing : P.hairlineStrong, lineWidth: focused ? 2 : 1))
        .animation(Alibi.Motion.adaptive(Alibi.Motion.micro, reduceMotion: reduce), value: focused)
        .contentShape(Rectangle())
        .simultaneousGesture(TapGesture().onEnded { Controller.shared?.focusPanel(); focused = true })
    }

    var offlineCard: some View {
        HStack(spacing: Alibi.Space.s3) {
            if m.starting {
                Spinner(size: 12)
            } else {
                StatusDot(label: "idle", size: 8)
            }
            VStack(alignment: .leading, spacing: Alibi.Space.s1) {
                Text(m.starting ? "Turning on…" : "Alibi is off").font(F.islandTitle).foregroundStyle(P.ink)
                Text(m.starting ? "Usually a few seconds." : "Nothing is being recorded.")
                    .font(F.islandSecondary).foregroundStyle(P.ink2)
                if !m.starting && repoRoot != nil {
                    Button { Controller.openLogs() } label: {
                        Text("Show details").font(F.islandSecondary).underline().foregroundStyle(P.ink3)
                    }.buttonStyle(.plain)
                }
            }
            Spacer()
            IslandButton(title: "Turn on", variant: .primary) {
                guard !m.starting else { return }
                m.reply = nil; m.replyFailed = false
                m.startingUntil = Date().timeIntervalSince1970 + 20; m.now = Date().timeIntervalSince1970
                Controller.startDaemon()
            }
            .disabled(m.starting).opacity(m.starting ? 0.4 : 1)
        }
        .padding(Alibi.Space.cardIsland)
        .card()
    }

    /// First run, no habits yet (matches the dashboard's welcome step): Pinch says hello at 56 pt beside one headline
    /// and its line, the three steps ahead on one card, then one primary button and a quiet way out.
    var welcomeCard: some View {
        VStack(alignment: .leading, spacing: Alibi.Space.s4) {
            HStack(alignment: .center, spacing: Alibi.Space.s3) {
                helloPinch(size: 56)
                VStack(alignment: .leading, spacing: Alibi.Space.s1) {
                    Text("Welcome to Alibi").font(F.islandTitle).foregroundStyle(P.ink)
                    // Body size keeps the line on one row beside the 56 pt Pinch (island-voice wraps "I check." alone).
                    Text("I'm Pinch. You say what you'll do; I check.").font(F.islandBody).foregroundStyle(P.ink2)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, Alibi.Space.s1)
            VStack(alignment: .leading, spacing: Alibi.Space.s3) {
                setupStep(1, "Pick a habit or two", current: true)
                setupStep(2, "Say when you'll do them", current: false)
                setupStep(3, "Try a short practice run", current: false)
            }
            .padding(Alibi.Space.cardIsland)
            .frame(maxWidth: .infinity, alignment: .leading)
            .card()
            HStack(spacing: Alibi.Space.s2) {
                IslandButton(title: "Set up my habits", variant: .primary) { m.open(m.setupPath) }
                    .help("Opens the setup in your browser")
                IslandButton(title: "Not now", variant: .quiet) { Controller.shared?.collapse() }
                Spacer(minLength: Alibi.Space.s2)
                Text("About two minutes").font(F.islandSecondary).foregroundStyle(P.ink3).lineLimit(1).fixedSize()
            }
        }
        .padding(.top, Alibi.Space.s2)
    }

    /// One setup step: a numbered mark (the current one raised) and its line.
    func setupStep(_ n: Int, _ text: String, current: Bool) -> some View {
        HStack(spacing: Alibi.Space.s3) {
            Text("\(n)").font(F.sans(11, .semibold)).monospacedDigit()
                .foregroundStyle(current ? P.ink : P.ink3)
                .frame(width: 20, height: 20)
                .background(Circle().fill(current ? P.surface3 : P.surface2))
                .overlay(Circle().strokeBorder(current ? P.accent : .clear, lineWidth: 1.5))
            Text(text).font(F.islandBody).foregroundStyle(current ? P.ink : P.ink2).lineLimit(1)
            Spacer(minLength: 0)
        }
        .accessibilityElement(children: .combine)
    }

    /// Pinch waving hello (Mascot.md `hello`): plays once when the welcome appears; snapshots draw its key frame.
    @ViewBuilder func helloPinch(size: CGFloat) -> some View {
        if snapshotting {
            PinchFigure(pose: PinchView.pose(mood: .idle, clip: .hello, ms: PinchClip.hello.motion.key), size: size)
                .accessibilityHidden(true)
        } else {
            PinchView(mood: .idle, clip: .hello, clipID: 1, size: size, camera: false, force: m.pinchForce)
                .accessibilityHidden(true)
        }
    }

    /// A block planned for now: a card with Start (primary) and Skip.
    func upNextCard(_ b: PlanBlock) -> some View {
        HStack(spacing: Alibi.Space.s3) {
            Image(systemName: "calendar").font(F.sans(14)).foregroundStyle(P.ink2)
                .frame(width: 32, height: 32)
                .background(RoundedRectangle(cornerRadius: Alibi.Radius.sm, style: .continuous).fill(P.surface2))
            VStack(alignment: .leading, spacing: 2) {
                Text(b.name).font(F.islandTitle).foregroundStyle(P.ink).lineLimit(1)
                Text("Now · \(clock(b.start))–\(clock(b.end))").font(F.islandSecondary).monospacedDigit()
                    .foregroundStyle(P.accentInk).lineLimit(1)
            }
            .layoutPriority(1)
            Spacer(minLength: Alibi.Space.s2)
            if b.startable {
                IslandButton(title: "Start", variant: .primary, icon: "play.fill", small: true) { Task { await m.start(b.habit, b.min) } }
            }
            IslandButton(title: "Skip", variant: .quiet, small: true) { skip(b) }.help("Skip \(b.name) for today")
        }
        .padding(Alibi.Space.s3)
        .card()
    }

    func skip(_ b: PlanBlock) {
        m.act(AlertAction("Skip today", post: "/api/calendar/plan/skip", body: ["key": .str(b.key)]))
    }

    /// Up to four habits as one-tap chips (⌘1–⌘4): today's planned ones first, then the rest. Right-click for a length.
    var chips: some View {
        let planned = (m.plan?.blocks ?? []).filter { ["now", "planned"].contains($0.state) }
        let order = Dictionary(planned.enumerated().map { ($1.habit, $0) }, uniquingKeysWith: { a, _ in a })
        let all = m.habits.filter { $0.modality != "strava" && $0.modality != "health" }
            .enumerated().sorted { (order[$0.element.key] ?? 100 + $0.offset) < (order[$1.element.key] ?? 100 + $1.offset) }
            .map(\.element)
        let nowKey = plannedNow?.habit
        let hs = Array((plannedNow != nil ? all.filter { $0.key != nowKey } : all).prefix(4))   // the card offers it
        return Flow(spacing: Alibi.Space.s2) {
            ForEach(Array(hs.enumerated()), id: \.element) { i, h in
                let block = planned.first { $0.habit == h.key }
                let mins = block?.min ?? h.default_min ?? 25
                let doneToday = (m.plan?.blocks ?? []).contains { $0.habit == h.key && ["done", "partial"].contains($0.state) }
                Button { Task { await m.send("\(h.key) for \(mins) minutes") } } label: {
                    chipLabel(h.name, detail: block.map(\.at) ?? "\(mins) min", done: doneToday)
                }
                .buttonStyle(Chip())
                .keyboardShortcut(KeyEquivalent(Character("\(i + 1)")), modifiers: .command)
                .help("Start \(h.name) for \(mins) min (⌘\(i + 1)) · right-click for another length")
                .contextMenu {
                    ForEach([15, 25, 45, 60], id: \.self) { n in
                        Button("\(h.name) for \(n) min") { Task { await m.send("\(h.key) for \(n) minutes") } }
                    }
                }
            }
            Button { Task { await m.send("how am I doing") } } label: {
                chipLabel("How am I doing?", detail: nil, done: false)
            }.buttonStyle(Chip())
        }
    }

    func chipLabel(_ name: String, detail: String?, done: Bool) -> some View {
        let shape = RoundedRectangle(cornerRadius: Alibi.Radius.xs, style: .continuous)
        return HStack(spacing: Alibi.Space.s2) {
            if done { StatusDot(label: "on_task", size: 6) }
            Text(name).font(F.sans(13, .medium)).foregroundStyle(detail == nil ? P.ink2 : P.ink).lineLimit(1).fixedSize()
            if let detail {
                Text(detail).font(F.islandSecondary).monospacedDigit().foregroundStyle(P.ink3).lineLimit(1).fixedSize()
            }
        }
        .padding(.horizontal, Alibi.Space.s3).frame(height: 32)
        .overlay(shape.strokeBorder(P.hairline, lineWidth: 1))
        .contentShape(shape)
    }

    /// The live session (canvas Island-Expanded): name and plan, ring + big timer + on-task %, the last checks,
    /// and one line in Pinch's voice.
    func sessionCard(_ s: Session) -> some View {
        let warming = s.warming_up ?? ((s.samples ?? s.labels.count) < 6)
        let recent = s.labels.isEmpty ? (s.recent ?? []) : s.labels.suffix(12).map(\.label)
        let lastTs = s.labels.last?.ts ?? s.last_seen?.ago_s.map { (m.state?.now ?? m.now) - $0 }
        return VStack(alignment: .leading, spacing: Alibi.Space.s3) {
            HStack(alignment: .firstTextBaseline, spacing: Alibi.Space.s3) {
                Text(s.name).font(F.islandTitle).foregroundStyle(P.ink).lineLimit(1).truncationMode(.tail)
                Spacer(minLength: Alibi.Space.s2)
                Text("\(s.declared_min) min · started \(clock(s.started_at))").font(F.islandSecondary).monospacedDigit()
                    .foregroundStyle(P.ink2).lineLimit(1).fixedSize()
            }
            HStack(spacing: Alibi.Space.s3) {
                ZStack {
                    Ring(progress: progress, colour: onBreak ? P.partial : P.accent)
                    Image(systemName: onBreak ? "cup.and.saucer.fill" : s.modality == "digital" ? "laptopcomputer" : "camera")
                        .font(F.sans(12)).foregroundStyle(P.ink2)
                }
                .frame(width: 44, height: 44)
                VStack(alignment: .leading, spacing: Alibi.Space.s1) {
                    Text(mmss(onBreak ? breakLeft : sessionLeft)).font(F.islandTimer).tracking(F.islandTimerTracking)
                        .foregroundStyle(onBreak ? P.partialInk : P.ink)
                        .contentTransition(.numericText(countsDown: true)).lineLimit(1).fixedSize()
                    Text(onBreak ? "break · \(mmss(sessionLeft)) of work left" : "left of \(s.declared_min) min")
                        .font(F.islandSecondary).monospacedDigit().foregroundStyle(P.ink2).lineLimit(1)
                }
                Spacer(minLength: Alibi.Space.s2)
                VStack(alignment: .trailing, spacing: Alibi.Space.s1) {
                    if warming || s.on_task_so_far == nil {
                        Text("—").font(F.rounded(17)).foregroundStyle(P.ink3)
                        Text("getting a read").font(F.islandSecondary).foregroundStyle(P.ink2)
                    } else if let r = s.on_task_so_far {
                        Text("\(Int((r * 100).rounded()))%").font(F.rounded(17)).foregroundStyle(P.ink)
                            .contentTransition(.numericText())
                        Text("on task").font(F.islandSecondary).foregroundStyle(P.ink2)
                    }
                }
                .fixedSize()
            }
            if !recent.isEmpty || lastTs != nil {
                HStack(spacing: Alibi.Space.s3) {
                    SampleDots(labels: recent)
                    Spacer(minLength: Alibi.Space.s2)
                    if let t = lastTs {
                        Text("Last seen \(clock(t))").font(F.islandSecondary).monospacedDigit().foregroundStyle(P.ink2)
                    }
                }
            }
            liveLine(s).font(F.islandVoice).foregroundStyle(P.ink).lineSpacing(2)
                .lineLimit(2).fixedSize(horizontal: false, vertical: true)
        }
        .padding(Alibi.Space.cardIsland)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
    }

    /// Pinch's line for the live card: the drift (only the noun in warn-ink), the break, or what it last saw.
    func liveLine(_ s: Session) -> Text {
        if let d = drifting {
            let secs = (d.since_s ?? 0) + drift
            let span = secs < 60 ? "\(Int(secs)) seconds" : "\(Int((secs / 60).rounded())) minute\(Int((secs / 60).rounded()) == 1 ? "" : "s")"
            switch d.label {
            case "phone": return Text("I've seen your \(Text("phone").foregroundStyle(P.warnInk)) for \(span).")
            case "absent": return Text("Your desk's been empty for \(span).")
            case "idle": return Text("Nothing's moved for \(span).")
            default:
                let place = d.label_text.map(placeName) ?? "something else"
                return Text("That's been \(Text(place).foregroundStyle(P.warnInk)) for \(span).")
            }
        }
        if let u = breakUntil { return Text("On a break. Back at \(clock(u)).") }
        if showNote, let n = s.last_seen?.note, !n.isEmpty { return Text(n) }
        if let l = m.state?.pinch?.line, !l.isEmpty { return Text(l) }
        if let l = s.last_seen { return Text(l.label_text ?? human(l.label)) }
        return Text("First check in a few seconds.")
    }

    /// One-tap controls (no typed commands needed): break / +10 / finish, and an inline confirm before ending early.
    @ViewBuilder func sessionControls(_ s: Session) -> some View {
        if m.confirmFinish {
            HStack(spacing: Alibi.Space.s2) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("End \(s.name) now?").font(F.islandBody).fontWeight(.semibold).foregroundStyle(P.ink)
                    Text("\(max(1, Int(sessionLeft / 60))) min to go. It's judged on what Alibi saw.")
                        .font(F.islandSecondary).foregroundStyle(P.ink2).lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .layoutPriority(1)
                Spacer(minLength: 6)
                IslandButton(title: "Keep going", variant: .primary, small: true) { m.confirmFinish = false }
                IslandButton(title: "End now", variant: .secondary, small: true) { Task { await m.end() } }
            }
            .padding(Alibi.Space.s3)
            .card()
        } else {
            HStack(spacing: Alibi.Space.s2) {
                if onBreak {
                    IslandButton(title: "I'm back", variant: .primary, icon: "arrow.uturn.backward") {
                        Task { await m.send("back", quiet: true) }
                    }
                } else {
                    IslandButton(title: "Break", icon: "cup.and.saucer") { Task { await m.send("break 5", quiet: true) } }
                        .contextMenu {
                            ForEach([2, 5, 10, 15], id: \.self) { n in
                                Button("Break for \(n) min") { Task { await m.send("break \(n)", quiet: true) } }
                            }
                        }
                        .help("5-minute break · right-click for another length")
                }
                IslandButton(title: "10 min", icon: "plus") {
                    Task { await m.send("change to \(s.declared_min + 10)", quiet: true) }
                }
                .help("Make this session 10 minutes longer")
                IslandButton(title: "Finish", icon: "stop.fill") {
                    if sessionLeft > 60 { m.confirmFinish = true } else { Task { await m.end() } }
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, Alibi.Space.s1)
        }
    }

    // MARK: Alerts

    func alertHeader(_ trailing: String?) -> some View {
        HStack(spacing: Alibi.Space.s2) {
            Text("ALIBI").font(F.islandWordmark).tracking(F.wordmarkTracking).foregroundStyle(P.ink)
            Spacer(minLength: notch.width)
            if let t = trailing {
                Text(t).font(F.islandSecondary).monospacedDigit().foregroundStyle(P.ink2).lineLimit(1)
            }
        }
        .padding(.horizontal, Alibi.Space.s1)
        .frame(height: notch.height)
    }

    /// Buttons: primary, secondary, quiet on nudges and plans; the verdict leads with secondary (See proof).
    func actionRow(_ a: AlertEv, extra: [AlertButton] = []) -> some View {
        let verdict = a.kind == "verdict"
        let xs = Array((extra + alertButtons(a)).prefix(verdict ? 2 + extra.count : 3))
        return HStack(spacing: Alibi.Space.s2) {
            ForEach(Array(xs.enumerated()), id: \.offset) { i, x in
                let isExtra = i < extra.count
                let v: IslandButton.Variant = isExtra ? .primary
                    : verdict ? (i == extra.count ? .secondary : .quiet)
                    : i == 0 ? .primary : i == 1 ? .secondary : .quiet
                IslandButton(title: x.title, variant: v, icon: x.icon) { m.act(x.action) }
            }
            Spacer(minLength: 0)
        }
    }

    /// Nudges, plans, pace, recap, report and info share the 400 pt frame: a 56 pt Pinch beside one line in its voice,
    /// then the buttons. Only a nudge's noun takes warn-ink.
    var alertView: some View {
        let a = m.alert ?? AlertEv(id: 0, kind: "info", text: "")
        let habitName = a.habit_label ?? a.habit.map(displayName) ?? session?.name
        let trailing: String = switch a.kind {
            case "planned": (a.start.map(clock) ?? a.at ?? "") + (a.end.map { "–" + clock($0) } ?? "")
            default: [habitName, clock(a.ts ?? m.now)].compactMap { $0 }.joined(separator: " · ")
        }
        return VStack(alignment: .leading, spacing: 0) {
            alertHeader(trailing).tier(0)
            HStack(alignment: .center, spacing: Alibi.Space.s3) {
                pinch(a.kind == "nudge" ? .focused : .idle, size: 56)
                alertLine(a).font(F.islandVoice).foregroundStyle(P.ink).lineSpacing(2)
                    .lineLimit(4).fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
            }
            .padding(.top, Alibi.Space.s1).padding(.horizontal, Alibi.Space.s1)
            .tier(0)
            actionRow(a).padding(.top, Alibi.Space.s3).padding(.horizontal, Alibi.Space.s1).tier(1, lift: true)
        }
    }

    func alertLine(_ a: AlertEv) -> Text {
        switch a.kind {
        case "nudge": return nudgeLine(a)
        case "pace": return Text(paceCopy(a))
        case "planned":
            let name = a.habit_label ?? a.habit.map(displayName) ?? "A block"
            if a.late == true { return Text("\(name) was planned for \(a.at ?? "earlier"). Start now?") }
            return Text("\(name) is planned now. Start?")
        default: return Text(plainReply(a.text))
        }
    }

    /// "You said drawing. I've seen your phone for 3 minutes." Composed like the web (M3): from the habit, the label
    /// and how long the drift has run; a server line already in Pinch's voice is used as it is.
    func nudgeLine(_ a: AlertEv) -> Text {
        let d = session?.drifting
        let label = a.label ?? d?.label ?? ""
        var noun: String? = label == "phone" ? "phone" : label == "off_task" ? d?.label_text.map(placeName) : nil
        var line = a.text
        if !(a.text.hasPrefix("You said") || a.text.hasPrefix("Your desk")), let d, let h = a.habit.map(spokenHabit) {
            let mins = max(1, Int((((d.since_s ?? 0) + drift) / 60).rounded()))
            let span = "\(mins) minute\(mins == 1 ? "" : "s")"
            switch label {
            case "phone": line = "You said \(h). I've seen your phone for \(span)."
            case "off_task" where noun != nil: line = "You said \(h). That's been \(noun!) for \(span)."
            case "absent": line = "Your desk's been empty for \(span). Still \(h)?"
            case "idle": line = "You said \(h). Nothing's moved in \(span)."
            default: break
            }
        }
        if noun.map({ !line.contains($0) }) ?? true { noun = (["phone"] + knownPlaces.map(\.1)).first { line.contains($0) } }
        guard let n = noun, let r = line.range(of: n) else { return Text(line) }
        let before = String(line[..<r.lowerBound]), cause = String(line[r]), after = String(line[r.upperBound...])
        return Text("\(before)\(Text(cause).foregroundStyle(P.warnInk))\(after)")
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

    /// "drawing" -> "drawing"; "cpp" -> "C++"; "internships" -> "Internships".
    func spokenHabit(_ k: String) -> String {
        let verbs = ["drawing", "building", "reading", "running", "coding", "studying", "writing", "practising",
                     "practicing", "meditating", "sketching", "painting", "journaling", "stretching"]
        let label = m.habits.first { $0.key == k }?.name ?? displayName(k)
        return verbs.contains(label.lowercased()) ? label.lowercased() : label
    }

    /// Drop the verdict word the pill already says ("Done. 23 of 25…" -> "23 of 25…"). A server line that isn't in
    /// Pinch's voice ("Time's up. Drawing: slacked. 15% on task…") is rebuilt from the numbers instead.
    func verdictSentence(_ t: String, rv: Verdict?, verdict: String?) -> String {
        let s = plainReply(t)
        let words = ["done", "done early", "partly", "slacked", "slacked, by my count", "not this time"]
        if let r = s.range(of: ". "), words.contains(s[..<r.lowerBound].lowercased()) { return String(s[r.upperBound...]) }
        guard let rv, rv.declared_min > 0 else { return s }
        let elapsed = rv.elapsed_min ?? rv.declared_min
        let seen = rv.verified_min ?? Int(((rv.on_task_ratio ?? 0) * Double(elapsed)).rounded())
        let line = "\(seen) of \(rv.declared_min) minutes on task."
        return verdict == "slacked" ? line + " Tap any frame if I got it wrong." : line
    }

    /// The verdict (canvas Island-Verdict, 440 wide): Pinch 64 plays its clip (a bloom behind it on done), the pill and
    /// the sentence, three frames of proof, then See proof and Fix a moment. Pinch stays green whatever the verdict.
    var verdictView: some View {
        let a = m.alert ?? AlertEv(id: 0, kind: "verdict", text: "")
        let rv = m.state?.recent_verdict.flatMap { v in (a.session_id == nil || v.id == a.session_id) ? v : nil }
        let v = a.verdict ?? rv?.verdict
        let labels = rv?.labels ?? []
        let wins = labels.isEmpty ? (rv?.windows ?? []) : []      // screen-only habit: the windows are the evidence
        let declared = rv?.declared_min ?? 0
        let elapsed = rv?.elapsed_min ?? declared
        let early = (a.ended_early ?? false) || (declared > 0 && Double(elapsed) < Double(declared) * 0.9)
        let ratio = a.ratio ?? rv?.on_task_ratio
        let onShare: Double? = labels.isEmpty
            ? (wins.isEmpty ? nil : wins.filter { $0.label == "on_task" }.map(\.share).reduce(0, +))
            : Double(labels.filter { $0.label == "on_task" }.count) / Double(labels.count)
        let name = a.habit_label ?? rv?.label ?? a.habit.map(displayName) ?? "Session"
        let enoughLooks = labels.count >= 6 || !wins.isEmpty || rv == nil
        let counted = v == "done" ? "Still counts for today." : v == "partial" ? "Counts as partly done." : "Too short to count today."
        let sentence = early
            ? ([onShare.map { "\(elapsed) of \(declared) minutes, \(Int(($0 * 100).rounded()))% on task." }, counted]
                .compactMap { $0 }.joined(separator: " "))
            : verdictSentence(a.text, rv: rv, verdict: v)
        var extra: [AlertButton] = []
        if early, let h = a.habit ?? rv?.habit, declared - elapsed >= 2 {
            let x = AlertAction("Keep going · \(declared - elapsed) min", say: "\(h) for \(declared - elapsed) minutes")
            extra = [AlertButton(title: x.label, action: x)]
        }
        let trailing = [name, early && rv != nil ? "\(elapsed) of \(declared) min" : clock(a.ts ?? m.now)].joined(separator: " · ")
        return VStack(alignment: .leading, spacing: 0) {
            alertHeader(trailing).tier(0)
            HStack(alignment: .top, spacing: Alibi.Space.s3) {
                verdictPinch(v).tier(0)
                VStack(alignment: .leading, spacing: Alibi.Space.s2) {
                    VStack(alignment: .leading, spacing: Alibi.Space.s2) {
                        VerdictPill(verdict: v, ratio: enoughLooks ? ratio : nil)
                        if !sentence.isEmpty {
                            Text(sentence).font(F.islandVoice).foregroundStyle(P.ink).lineSpacing(2).monospacedDigit()
                                .lineLimit(3).fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .tier(0)
                    evidence(labels: labels, wins: wins, verdict: v).padding(.top, Alibi.Space.s1).tier(1, lift: true)
                }
                Spacer(minLength: 0)
            }
            .padding(.top, Alibi.Space.s1).padding(.horizontal, Alibi.Space.s1)
            actionRow(a, extra: extra)
                .padding(.top, Alibi.Space.s3).padding(.leading, Alibi.Space.s1 + 64 + Alibi.Space.s3)
                .padding(.trailing, Alibi.Space.s1)
                .tier(2, lift: true)
        }
    }

    /// The bloom is the product's one gradient: closest-side, 1.6x Pinch, only on done, only while the clip plays.
    func verdictPinch(_ v: String?) -> some View {
        ZStack {
            if v == "done" && m.pinchClip == .celebrate && !reduce {
                RadialGradient(colors: [P.bloom, P.bloom.opacity(0)], center: .center, startRadius: 0, endRadius: 51) // bloom
                    .frame(width: 102, height: 102)
                    .transition(.opacity.animation(Alibi.Motion.easeOut(Alibi.Motion.durMedium)))
                    .allowsHitTesting(false)
            }
            pinch(.idle, size: 64)
        }
        .frame(width: 64, height: 64)
    }

    /// Three frames in time order. Partial / slacked: the off-task looks first (they're the evidence), padded with evenly
    /// spaced on-task ones. Done: an even sample of the session with at most one off-task look, so a pass never reads as
    /// an accusation. Screen-only habits show where the time went instead.
    @ViewBuilder func evidence(labels: [LabelEv], wins: [WindowShare], verdict: String?) -> some View {
        if !wins.isEmpty {
            VStack(alignment: .leading, spacing: Alibi.Space.s2) {
                PlaceStrip(ws: wins, height: 8)
                if let l = placesLine(wins) { Text(l).font(F.islandSecondary).foregroundStyle(P.ink2).lineLimit(1) }
            }
        } else if !labels.isEmpty {
            let withFrames = labels.filter { $0.frame_url != nil }
            let pool = withFrames.isEmpty ? labels : withFrames
            let pick: [LabelEv] = {
                func spread(_ a: [LabelEv], _ n: Int) -> [LabelEv] {
                    let k = min(n, a.count)
                    return k > 0 ? (0..<k).map { a[(2 * $0 + 1) * a.count / (2 * k)] } : []
                }
                let on = pool.filter { $0.label == "on_task" }
                let off = pool.filter { $0.label != "on_task" }
                var p: [LabelEv]
                if verdict == "done" {
                    p = spread(pool, 3)
                    let drift = p.filter { $0.label != "on_task" }
                    if drift.count > 1 {
                        p = Array(drift.prefix(1)) + spread(on, 2)
                        for l in off where p.count < 3 && !p.contains(l) { p.append(l) }
                    }
                } else {
                    p = Array(off.prefix(2))
                    p += spread(on, 3 - p.count)
                }
                return p.sorted { $0.ts < $1.ts }
            }()
            HStack(spacing: Alibi.Space.s2) {
                ForEach(pick, id: \.self) { l in FrameThumb(label: l, image: l.frame_url.flatMap { m.thumb($0) }) }
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
        island.setMode(.collapsed)
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
        island.setMode(.expanded, via: .key)      // keyboard: the shape only, no blur or stagger
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
        // Peek while the pointer rests in the closed notch, until the dwell opens it.
        island.setPeek(inside && island.mode == .collapsed && !island.leaving, side: p.x < f.midX ? -1 : 1)

        // A queued alert surfaces as soon as the user is done typing.
        if let a = island.pending, island.mode == .collapsed { island.show(alert: a) }

        if inside {
            collapseAt = nil
            if !wasInside { enteredAt = Date() }
            if speed > 200 { enteredAt = Date() }   // still moving: restart the dwell
            if island.mode == .alert {
                island.alertTask?.cancel()          // pause auto-dismiss while the pointer is on it
            } else if island.mode == .collapsed, let t = enteredAt, Date().timeIntervalSince(t) > 0.35,
                      Date().timeIntervalSince1970 - island.closedAt > 0.15 {   // ignore re-entries just after a close
                island.setMode(.expanded, via: .hover)
            }
        } else {
            enteredAt = nil
            // Seen it and moved away: a timed alert goes in 3 s; nudges/planned blocks fold into the wing.
            if wasInside && island.mode == .alert { island.scheduleDismiss(after: 3) }
            if island.mode == .expanded && island.draft.isEmpty && !island.busy && !island.pinned {
                if collapseAt == nil { collapseAt = Date().addingTimeInterval(0.8) }
                if let c = collapseAt, Date() > c {
                    island.setMode(.collapsed)
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
/// "_alerts" [{name, alert}] rendered in alert mode, "_only" [render names] to limit output, "_confirm_finish",
/// "_draft" (composer text).
struct SnapNamedAlert: Decodable { let name: String; let alert: AlertEv }
struct SnapExtras: Decodable {
    let _plan: PlanResp?; let _needs_setup: Bool?; let _alerts: [SnapNamedAlert]?; let _only: [String]?
    let _confirm_finish: Bool?; let _draft: String?
}

// --snapshot DIR [--state FILE.json] [--prefix P]: render every mode offscreen to PNGs
// (visual check without screen-recording permission). --state renders a saved /api/state payload (+ extras above).
// Each render is one still frame at rest: alerts show the key pose of the clip Pinch would play.
@MainActor func snapshot(to dir: String, stateFile: String?, prefix: String) async {
    snapshotting = true
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
    m.draft = extras?._draft ?? ""
    let screen = NSScreen.screens.first { $0.safeAreaInsets.top > 0 } ?? NSScreen.main!
    let notch = Notch(screen: screen)
    // Preload every frame the verdict view might show (ImageRenderer can't wait on network).
    for l in m.state?.recent_verdict?.labels ?? [] { if let u = l.frame_url { await m.loadThumb(u) } }

    let nudge = m.state?.alert?.kind == "nudge" ? m.state!.alert! :
        AlertEv(id: 1, kind: "nudge", text: "You said drawing. I've seen your phone for 3 minutes.", habit: "drawing",
                habit_label: "Drawing", actions: [AlertAction("Back to it", say: "back"), AlertAction("This counts", say: "it's on task"),
                                                  AlertAction("Quiet 5 min", say: "snooze 5")], label: "phone")
    var renders: [(String, Mode, AlertEv?, Bool)] = [
        ("collapsed", .collapsed, nil, true), ("peek", .collapsed, nil, true), ("expanded", .expanded, nil, true),
        ("alert", .alert, nudge, true),
        ("offline_collapsed", .collapsed, nil, false), ("offline_expanded", .expanded, nil, false),
        ("offline_starting", .expanded, nil, false),
    ]
    if let a = m.state?.alert, a.kind != "nudge", a.kind != "verdict", m.shouldShow(a) {
        // A quiet sync never opens a panel: render the glinting wings instead.
        renders.append(m.isSynced(a) && (a.actions ?? []).isEmpty ? ("synced", .collapsed, a, true) : ("alert_\(a.kind)", .alert, a, true))
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
        m.alert = mode == .alert ? alert : nil
        m.glintUntil = name == "synced" ? m.now + 3 : 0
        m.peeking = name == "peek"; m.peekSide = 1
        m.glintIcon = alert.map { $0.text.hasPrefix("Strava") ? "figure.run" : "heart.fill" } ?? "heart.fill"
        m.pinchClip = mode != .alert ? nil
            : alert?.kind == "nudge" ? .sideeye
            : alert?.kind == "verdict" ? Island.verdictClip[alert?.verdict ?? ""] : nil
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
/// LABEL may be the island's label ("Back to it"), the server's, or the pre-redesign one ("I'm back").
@MainActor func actOnce(_ label: String) async {
    let m = Island()
    await m.refresh()
    guard let a = m.state?.alert else { print("no alert"); return }
    let xs = alertButtons(a)
    guard let b = xs.first(where: { actLabels($0).contains(label) }) else {
        print("no button “\(label)” on \(a.kind) alert; buttons: \(xs.map(\.title))"); return
    }
    let x = b.action
    if x.url != nil { print("would open \(x.url!)"); return }
    m.act(x)
    for _ in 0..<30 where m.reply == nil && m.busy == false && x.post != nil {
        try? await Task.sleep(nanoseconds: 100_000_000)
    }
    try? await Task.sleep(nanoseconds: 500_000_000)
    print("pressed “\(label)” on \(a.kind): reply=\(m.reply ?? "-") session=\(m.session?.name ?? "none")")
}
