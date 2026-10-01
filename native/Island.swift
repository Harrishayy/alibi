// Alibi Island — a Dynamic-Island-style bar that lives in the MacBook notch.
// Collapsed: habit + live label dot on the left wing, countdown ring on the right.
// Hover: expands into a prompt ("What are you about to do?") with session detail.
// Nudges and verdicts expand it on their own. Talks to the daemon at http://127.0.0.1:8765.
import AppKit
import Carbon.HIToolbox
import SwiftUI

let API = ProcessInfo.processInfo.environment["ALIBI_API"] ?? "http://127.0.0.1:8765"

// MARK: - API models

struct LabelEv: Decodable, Hashable { let ts: Double; let label: String; let note: String }
struct Session: Decodable {
    let id: Int; let habit: String; let modality: String; let declared_min: Int
    let started_at: Double; let ends_at: Double
    let labels: [LabelEv]; let on_task_so_far: Double?; let last_frame_url: String?
}
struct AlertEv: Decodable, Equatable { let id: Int64; let kind: String; let text: String; let image_url: String? }
struct HabitRef: Decodable, Hashable { let key: String; let modality: String; let default_min: Int? }
struct StateResp: Decodable { let session: Session?; let alert: AlertEv?; let witness: String; let habits: [HabitRef]? }

let palette: [String: Color] = [
    "on_task": Color(hex: 0x6FA172), "phone": Color(hex: 0xE0644C), "off_task": Color(hex: 0xC9553B),
    "idle": Color(hex: 0xE3A548), "absent": Color(hex: 0x8F8A82),
]
let coral = Color(hex: 0xD97757)
let cream = Color(hex: 0xF4EFE6)

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
    @Published var mode: Mode = .collapsed
    @Published var alert: AlertEv?
    @Published var reply: String?
    @Published var draft = ""
    @Published var busy = false
    @Published var now = Date().timeIntervalSince1970
    @Published var pinned = false          // opened by hotkey: stays open until Esc / send / click elsewhere
    var lastAlertId: Int64?
    var alertTask: Task<Void, Never>?

    func poll() async {
        while true {
            now = Date().timeIntervalSince1970
            if let s: StateResp = await get("/api/state") {
                online = true
                state = s
                if let a = s.alert, a.id != lastAlertId {
                    if lastAlertId != nil && a.kind != "info" { show(alert: a) }
                    lastAlertId = a.id
                }
            } else {
                online = false
            }
            try? await Task.sleep(nanoseconds: 1_000_000_000)
        }
    }

    func show(alert a: AlertEv) {
        alert = a
        withAnimation(.spring(response: 0.42, dampingFraction: 0.78)) { mode = .alert }
        NSSound(named: a.kind == "nudge" ? "Funk" : "Glass")?.play()
        alertTask?.cancel()
        alertTask = Task {
            try? await Task.sleep(nanoseconds: (a.kind == "verdict" ? 12 : 7) * 1_000_000_000)
            if !Task.isCancelled && mode == .alert {
                withAnimation(.spring(response: 0.4, dampingFraction: 0.85)) { mode = .collapsed }
            }
        }
    }

    func unpinSoon() {
        guard pinned else { return }
        Task {
            try? await Task.sleep(nanoseconds: 2_500_000_000)
            if pinned && draft.isEmpty { pinned = false; withAnimation { mode = .collapsed } }
        }
    }

    func send(_ text: String) async {
        let t = text.trimmingCharacters(in: .whitespaces)
        guard !t.isEmpty else { return }
        busy = true
        struct R: Decodable { let reply: String }
        let r: R? = await post("/api/say", ["text": t])
        reply = r?.reply ?? "Daemon isn't running — start it with python -m alibi.daemon"
        draft = ""
        busy = false
    }

    func end() async {
        struct R: Decodable { let reply: String }
        let r: R? = await post("/api/end", [:])
        reply = r?.reply
    }

    func get<T: Decodable>(_ path: String) async -> T? {
        guard let url = URL(string: API + path),
              let (d, _) = try? await URLSession.shared.data(from: url) else { return nil }
        return try? JSONDecoder().decode(T.self, from: d)
    }

    func post<T: Decodable>(_ path: String, _ body: [String: String]) async -> T? {
        var req = URLRequest(url: URL(string: API + path)!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
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

@MainActor func size(for mode: Mode, notch: Notch, island: Island) -> CGSize {
    switch mode {
    case .collapsed:
        if island.state?.session != nil { return CGSize(width: notch.width + 210, height: notch.height) }
        if island.reply != nil { return CGSize(width: notch.width + 120, height: notch.height) }
        return CGSize(width: notch.hasNotch ? notch.width : 150, height: notch.height)
    case .expanded:
        let base: CGFloat = island.state?.session != nil ? 150 : 102
        return CGSize(width: 500, height: notch.height + base + (island.reply != nil ? 24 : 0))
    case .alert:
        let img = island.alert?.image_url != nil
        let lines = CGFloat(min(3, max(1, ((island.alert?.text.count ?? 0) + 44) / 45)))
        return CGSize(width: img ? 560 : 500, height: notch.height + 34 + lines * 23 + (img ? 206 : 0))
    }
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

// MARK: - Views

func mmss(_ s: Double) -> String {
    let s = max(0, Int(s.rounded()))
    return s >= 3600 ? String(format: "%d:%02d:%02d", s / 3600, (s % 3600) / 60, s % 60)
                     : String(format: "%d:%02d", s / 60, s % 60)
}

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
    let colour: Color
    @State private var on = false
    var body: some View {
        Circle().fill(colour).frame(width: 7, height: 7)
            .background(Circle().fill(colour.opacity(0.45)).scaleEffect(on ? 2.4 : 1).opacity(on ? 0 : 1))
            .onAppear { withAnimation(.easeOut(duration: 1.6).repeatForever(autoreverses: false)) { on = true } }
    }
}

struct IslandView: View {
    @ObservedObject var m: Island
    let notch: Notch
    @FocusState private var focused: Bool

    var session: Session? { m.state?.session }
    var lastLabel: String { session?.labels.last?.label ?? "on_task" }
    var left: Double { max(0, (session?.ends_at ?? 0) - m.now) }
    var progress: Double {
        guard let s = session else { return 0 }
        return min(1, max(0, (m.now - s.started_at) / max(1, s.ends_at - s.started_at)))
    }

    var body: some View {
        let sz = size(for: m.mode, notch: notch, island: m)
        VStack(spacing: 0) {
            ZStack(alignment: .top) {
                NotchShape(top: m.mode == .collapsed ? 6 : 12, bottom: m.mode == .collapsed ? 12 : 30)
                    .fill(Color.black)
                    .shadow(color: .black.opacity(m.mode == .collapsed ? 0 : 0.35), radius: 18, y: 8)
                content.padding(.horizontal, m.mode == .collapsed ? 14 : 26)
                    .frame(width: sz.width, height: sz.height, alignment: .top)
                    .clipped()
            }
            .frame(width: sz.width, height: sz.height)
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .animation(.spring(response: 0.42, dampingFraction: 0.8), value: m.mode)
        .animation(.spring(response: 0.42, dampingFraction: 0.8), value: session?.id)
        .preferredColorScheme(.dark)
    }

    @ViewBuilder var content: some View {
        switch m.mode {
        case .collapsed: collapsed
        case .expanded: expanded.transition(.opacity.combined(with: .scale(scale: 0.96, anchor: .top)))
        case .alert: alertView.transition(.opacity.combined(with: .scale(scale: 0.96, anchor: .top)))
        }
    }

    // Wings either side of the physical notch.
    var collapsed: some View {
        HStack(spacing: 0) {
            if let s = session {
                HStack(spacing: 7) {
                    Pulse(colour: palette[lastLabel] ?? coral)
                    Text(s.habit.capitalized).font(.system(size: 12.5, weight: .semibold, design: .serif))
                        .foregroundStyle(cream).lineLimit(1)
                }
                Spacer(minLength: notch.width)
                HStack(spacing: 7) {
                    Text(mmss(left)).font(.system(size: 12, weight: .medium, design: .monospaced))
                        .foregroundStyle(cream.opacity(0.9)).contentTransition(.numericText())
                    Ring(progress: progress, colour: coral, width: 2.2).frame(width: 13, height: 13)
                }
            } else if let r = m.reply {
                Circle().fill(coral).frame(width: 6, height: 6)
                Spacer(minLength: notch.width)
                Text(r.count > 14 ? "noted" : r).font(.system(size: 11)).foregroundStyle(cream.opacity(0.7))
            } else if !notch.hasNotch {
                Spacer()
                Text("alibi").font(.system(size: 12, weight: .semibold, design: .serif)).foregroundStyle(cream.opacity(0.8))
                Circle().fill(m.online ? coral : .gray).frame(width: 5, height: 5).padding(.leading, 5)
                Spacer()
            }
        }
        .frame(height: notch.height)
    }

    var expanded: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Alibi").font(.system(size: 13, weight: .semibold, design: .serif)).foregroundStyle(coral)
                Spacer()
                Text(m.online ? "witness · \(m.state?.witness ?? "?")  ·  ⌥⌘A" : "daemon offline")
                    .font(.system(size: 10.5, design: .monospaced)).foregroundStyle(.white.opacity(0.4))
                Button { NSApp.terminate(nil) } label: {
                    Image(systemName: "power").font(.system(size: 10, weight: .semibold)).foregroundStyle(.white.opacity(0.4))
                }.buttonStyle(.plain).help("Quit Alibi (stops the daemon, camera off)").padding(.leading, 6)
            }
            .frame(height: notch.height - 6, alignment: .bottom)

            if let s = session { sessionCard(s) }

            HStack(spacing: 10) {
                Image(systemName: m.busy ? "ellipsis" : "eye").foregroundStyle(coral).frame(width: 16)
                TextField("", text: $m.draft, prompt: Text(session == nil ? "What are you about to do?" : "status · end · report")
                    .foregroundStyle(.white.opacity(0.35)))
                    .textFieldStyle(.plain).font(.system(size: 15, design: .serif)).foregroundStyle(cream)
                    .focused($focused)
                    .onSubmit { Task { await m.send(m.draft); m.unpinSoon() } }
                    .onExitCommand { m.pinned = false; m.draft = ""; m.mode = .collapsed }
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

            if let r = m.reply {
                Text(r).font(.system(size: 12.5, design: .serif)).foregroundStyle(cream.opacity(0.75)).lineLimit(2)
            } else if session == nil {
                chips
            }
        }
        .onAppear { DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { focused = true } }
    }

    var chips: some View {
        let hs = (m.state?.habits ?? []).filter { $0.modality != "strava" }.prefix(4)
        return HStack(spacing: 6) {
            ForEach(Array(hs), id: \.self) { h in
                Button { Task { await m.send("\(h.key) for \(h.default_min ?? 25) minutes") } } label: {
                    HStack(spacing: 4) {
                        Text(h.key.capitalized).font(.system(size: 11.5, weight: .medium, design: .serif))
                            .lineLimit(1).fixedSize()
                        Text("\(h.default_min ?? 25)m").font(.system(size: 10, design: .monospaced)).opacity(0.5)
                            .lineLimit(1).fixedSize()
                    }
                    .padding(.horizontal, 9).padding(.vertical, 5)
                    .background(Capsule().strokeBorder(Color.white.opacity(0.16)))
                }.buttonStyle(.plain).foregroundStyle(cream)
            }
            Button { Task { await m.send("report") } } label: {
                Text("report").font(.system(size: 11.5)).padding(.horizontal, 9).padding(.vertical, 5)
                    .background(Capsule().fill(coral.opacity(0.18)))
            }.buttonStyle(.plain).foregroundStyle(coral)
        }
    }

    func sessionCard(_ s: Session) -> some View {
        HStack(alignment: .center, spacing: 16) {
            ZStack {
                Ring(progress: progress, colour: coral, width: 4)
                Text(mmss(left)).font(.system(size: 12.5, weight: .semibold, design: .monospaced)).foregroundStyle(cream)
                    .contentTransition(.numericText())
            }.frame(width: 62, height: 62)
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(s.habit.capitalized).font(.system(size: 24, weight: .regular, design: .serif)).foregroundStyle(cream)
                    Text("\(s.declared_min) min · \(s.modality)").font(.system(size: 11)).foregroundStyle(.white.opacity(0.45))
                }
                HStack(spacing: 3) {
                    ForEach(Array(s.labels.suffix(30).enumerated()), id: \.offset) { _, l in
                        RoundedRectangle(cornerRadius: 2).fill(palette[l.label] ?? .gray).frame(width: 7, height: 12)
                    }
                    if s.labels.isEmpty {
                        Text("watching…").font(.system(size: 11)).foregroundStyle(.white.opacity(0.4))
                    }
                }
                if let n = s.labels.last {
                    Text("\(n.label.replacingOccurrences(of: "_", with: " ")) — \(n.note)")
                        .font(.system(size: 11)).foregroundStyle((palette[n.label] ?? .gray).opacity(0.95)).lineLimit(1)
                }
            }
            Spacer()
            if let r = s.on_task_so_far {
                VStack(alignment: .trailing, spacing: 0) {
                    Text("\(Int((r * 100).rounded()))%").font(.system(size: 26, weight: .light, design: .serif))
                        .foregroundStyle(r >= 0.7 ? palette["on_task"]! : r >= 0.4 ? palette["idle"]! : palette["phone"]!)
                    Text("on task").font(.system(size: 10)).foregroundStyle(.white.opacity(0.4))
                }
            }
        }
    }

    var alertView: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(m.alert?.kind == "nudge" ? "Caught you" : m.alert?.kind == "verdict" ? "Verdict" : "Alibi")
                    .font(.system(size: 13, weight: .semibold, design: .serif)).foregroundStyle(coral)
                Spacer()
            }.frame(height: notch.height - 6, alignment: .bottom)
            Text(m.alert?.text ?? "").font(.system(size: 17, design: .serif)).foregroundStyle(cream)
                .fixedSize(horizontal: false, vertical: true).lineLimit(3)
            if let u = m.alert?.image_url, let url = URL(string: API + u) {
                AsyncImage(url: url) { img in img.resizable().aspectRatio(contentMode: .fill) } placeholder: {
                    Color.white.opacity(0.05)
                }
                .frame(height: 190).frame(maxWidth: .infinity).clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
    }
}

// MARK: - Daemon ownership (Alibi.app)

final class DaemonOwner {
    static let shared = DaemonOwner()
    var proc: Process?

    func start(root: String) {
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
        try? FileManager.default.createDirectory(atPath: root + "/data/logs", withIntermediateDirectories: true)
        FileManager.default.createFile(atPath: root + "/data/logs/daemon.log", contents: nil)
        if let log = FileHandle(forWritingAtPath: root + "/data/logs/daemon.log") {
            log.seekToEndOfFile(); p.standardOutput = log; p.standardError = log
        }
        try? p.run()
        proc = p
        for sig in [SIGTERM, SIGINT] {
            signal(sig) { _ in DaemonOwner.shared.stop(); exit(0) }
        }
        atexit { DaemonOwner.shared.stop() }
    }

    func stop() { proc?.terminate(); proc = nil }
}

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

    func start() {
        let screen = NSScreen.screens.first { $0.safeAreaInsets.top > 0 } ?? NSScreen.main!
        notch = Notch(screen: screen)
        let W: CGFloat = 640, H: CGFloat = 420
        let f = screen.frame
        panel = Panel(contentRect: NSRect(x: f.midX - W / 2, y: f.maxY - H, width: W, height: H),
                      styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.level = NSWindow.Level(rawValue: NSWindow.Level.statusBar.rawValue + 8)
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary, .ignoresCycle]
        panel.isMovable = false
        panel.contentView = NSHostingView(rootView: IslandView(m: island, notch: notch))
        panel.orderFrontRegardless()
        panel.ignoresMouseEvents = true

        Task { await island.poll() }
        Controller.shared = self
        registerHotkey()
        NSEvent.addGlobalMonitorForEvents(matching: [.leftMouseDown]) { _ in
            MainActor.assumeIsolated {
                if self.island.pinned { self.island.pinned = false; self.island.mode = .collapsed }
            }
        }
        Timer.scheduledTimer(withTimeInterval: 1 / 30, repeats: true) { _ in
            MainActor.assumeIsolated { self.track() }
        }
    }

    static var shared: Controller?

    func summon() {
        if island.mode != .collapsed && island.pinned {
            island.pinned = false
            island.mode = .collapsed
            return
        }
        island.pinned = true
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

    // Hover in -> expand; out (and nothing typed) -> collapse. Clicks pass through everywhere else.
    func track() {
        let p = NSEvent.mouseLocation
        let f = notch.screen.frame
        let sz = size(for: island.mode, notch: notch, island: island)
        let hit = NSRect(x: f.midX - sz.width / 2, y: f.maxY - sz.height, width: sz.width, height: sz.height)
        let inside = hit.insetBy(dx: -6, dy: -6).contains(p)
        panel.ignoresMouseEvents = !inside
        if inside {
            collapseAt = nil
            if island.mode == .collapsed {
                island.mode = .expanded
                panel.makeKey()
            }
        } else if island.mode == .expanded && island.draft.isEmpty && !island.busy && !island.pinned {
            if collapseAt == nil { collapseAt = Date().addingTimeInterval(0.35) }
            if let c = collapseAt, Date() > c {
                island.mode = .collapsed
                collapseAt = nil
                if island.reply != nil {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 4) { self.island.reply = nil }
                }
            }
        }
    }
}

// --snapshot DIR: render every mode offscreen to PNGs (visual check without screen-recording permission).
@MainActor func snapshot(to dir: String) async {
    let m = Island()
    m.state = await m.get("/api/state")
    m.online = m.state != nil
    let screen = NSScreen.screens.first { $0.safeAreaInsets.top > 0 } ?? NSScreen.main!
    let notch = Notch(screen: screen)
    let fake = AlertEv(id: 1, kind: "nudge", text: "You said drawing. I've seen your phone for 3 minutes.", image_url: nil)
    for (name, mode) in [("collapsed", Mode.collapsed), ("expanded", .expanded), ("alert", .alert)] {
        m.mode = mode
        m.alert = mode == .alert ? (m.state?.alert?.kind == "verdict" ? m.state?.alert : fake) : nil
        let v = ZStack(alignment: .top) {
            Color(white: 0.82)   // stand-in for the menu bar / wallpaper
            IslandView(m: m, notch: notch)
        }.frame(width: 640, height: 420)
        let r = ImageRenderer(content: v)
        r.scale = 2
        if let img = r.nsImage, let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
           let png = rep.representation(using: .png, properties: [:]) {
            try? png.write(to: URL(fileURLWithPath: "\(dir)/island_\(name).png"))
        }
    }
    print("notch \(notch.width)x\(notch.height) hasNotch=\(notch.hasNotch) online=\(m.online)")
}

let args = CommandLine.arguments
if let i = args.firstIndex(of: "--snapshot"), i + 1 < args.count {
    let dir = args[i + 1]
    Task { @MainActor in await snapshot(to: dir); exit(0) }
    RunLoop.main.run()
} else {
    // Inside Alibi.app: own the daemon's lifetime (start it if nothing answers, stop it when we quit).
    if let root = Bundle.main.url(forResource: "root", withExtension: "txt")
        .flatMap({ try? String(contentsOf: $0, encoding: .utf8) })?.trimmingCharacters(in: .whitespacesAndNewlines) {
        DaemonOwner.shared.start(root: root)
    }
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    let controller = MainActor.assumeIsolated { Controller() }
    MainActor.assumeIsolated { controller.start() }
    app.run()
}
