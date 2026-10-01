// The sync engine: collects every enabled stream from its cursor, sends one {batch:[...]} POST (≤ 400 rows each) to the
// best reachable Mac address, advances cursors only after the Mac said 200, and keeps event rows (location, focus,
// app) in a small on-disk outbox until they're delivered. Then it asks the Mac whether a session is running; if so it
// syncs every `sync_every_s` (~2 min) while iOS gives the app time (foreground, Focus filter, geofence, Health wakes,
// background tasks).
import BackgroundTasks
import Foundation
import HealthKit
import UIKit

struct SessionInfo: Equatable {
    var active: Bool
    var habit: String?
    var endsAt: Date?
    var shield: Bool
    var every: Double
}

@MainActor
final class SyncEngine: ObservableObject {
    static let shared = SyncEngine()
    nonisolated static let refreshID = "app.theultras.alibi.sync"
    nonisolated static let processingID = "app.theultras.alibi.live"
    static let maxBatch = 400

    @Published var busy = false
    @Published var status = "Not synced yet"
    @Published var ok: Bool?
    @Published var lastSync: Date? = { let t = Store.double("sync.last"); return t > 0 ? Date(timeIntervalSince1970: t) : nil }()
    @Published var lastSent = 0
    @Published var session: SessionInfo?
    @Published var pending = 0
    @Published var tick = 0                                       // bumps after each run so stream rows re-read cursors

    private var outbox: [[String: Any]] = []                      // [{stream, row}]
    private var failures = 0
    private var nextRetry = Date.distantPast
    private var lastRun = Date.distantPast
    private var liveTask: Task<Void, Never>?
    private var foreground = false
    private var goodEndpoint: String {
        get { Store.d.string(forKey: "sync.endpoint") ?? "" }
        set { Store.set(newValue, "sync.endpoint") }
    }
    private var outboxURL: URL { Store.appSupport.appendingPathComponent("outbox.json") }

    init() {
        if let data = try? Data(contentsOf: outboxURL), let arr = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] {
            outbox = arr
        }
        pending = outbox.count
    }

    // MARK: outbox

    /// Queue event rows (location/focus/shield/screentime/app). They're sent with the next sync and survive relaunches.
    func enqueue(_ rows: [Row], stream: String) {
        outbox += rows.map { ["stream": stream, "row": $0] }
        if outbox.count > 2000 { outbox.removeFirst(outbox.count - 2000) }
        saveOutbox()
    }

    private func saveOutbox() {
        pending = outbox.count
        if let data = try? JSONSerialization.data(withJSONObject: outbox) { try? data.write(to: outboxURL, options: .atomic) }
    }

    // MARK: run

    /// Automatic triggers respect backoff and a 20 s debounce; "Sync now" doesn't.
    func runAuto(reason: String) async {
        guard Date() >= nextRetry, Date().timeIntervalSince(lastRun) > 20 else { return }
        await run(reason: reason)
    }

    func run(reason: String = "manual", full: Bool = false) async {
        guard !busy else { return }
        busy = true
        lastRun = Date()
        sessionFromReply = nil
        defer { busy = false; tick += 1 }
        guard Config.configured else { status = "Missing Mac address — rebuild the app from the Mac"; ok = false; return }

        var collected: [Collected] = []
        if Health.shared.available {
            if Store.enabled("health") { collected.append(await Health.shared.collectDays(full: full)) }
            if Store.enabled("heart") { collected.append(await Health.shared.collectHeart()) }
            if let h = await Health.shared.latestHeart() { Snapshot.shared.noteHeart(bpm: h.0, at: h.1) }
        }
        if Store.enabled("motion") {
            let m = await Motion.shared.collect()
            collected += [m.motion, m.pickups]
        }
        ScreenTimeShield.shared.drainExtension()                       // Screen Time rows the extensions left in the App Group
        let queued = outbox
        let rows = queued.compactMap { $0["row"] as? Row } + collected.flatMap(\.rows)

        do {
            var sent = 0
            var i = 0
            repeat {
                let chunk = Array(rows[i..<min(i + Self.maxBatch, rows.count)])
                if !chunk.isEmpty { try await deliver(chunk) }
                sent += chunk.count
                i += Self.maxBatch
            } while i < rows.count
            // Delivered: drop what was queued (new events may have arrived meanwhile), advance cursors.
            outbox.removeFirst(min(queued.count, outbox.count))
            saveOutbox()
            collected.forEach { $0.commit() }
            let now = Date()
            Set(collected.map(\.stream) + queued.compactMap { $0["stream"] as? String }).forEach { Store.markSent($0, at: now) }
            failures = 0; nextRetry = .distantPast
            lastSync = now; Store.set(now.timeIntervalSince1970, "sync.last")
            lastSent = sent
            ok = true
            status = sent == 0 ? "Up to date with \(Config.macName)" : "Sent \(sent) update\(sent == 1 ? "" : "s") to \(Config.macName)"
        } catch let e as SyncError {
            failures += 1
            nextRetry = Date().addingTimeInterval(min(pow(2, Double(failures)) * 15, 1800))
            ok = false
            status = e.message
            return
        } catch {
            ok = false; status = error.localizedDescription; return
        }
        await pollSession()
    }

    enum SyncError: Error {
        case unauthorized, unreachable(String)
        var message: String {
            switch self {
            case .unauthorized: "The key doesn't match — rebuild the app from the Mac."
            case .unreachable(let why): "Couldn't reach \(Config.macName). Is Alibi running with iPhone sync on, and are you on the same Wi-Fi (or Tailscale)? \(why)"
            }
        }
    }

    private var endpointOrder: [String] {
        (NSOrderedSet(array: ([goodEndpoint] + Config.endpoints).filter { !$0.isEmpty }).array as? [String]) ?? Config.endpoints
    }

    /// Tries each address until one answers; remembers the winner.
    private func deliver(_ rows: [Row]) async throws {
        var lastErr = ""
        for ep in endpointOrder {
            do {
                try await postBatch(rows, to: ep)
                goodEndpoint = ep
                return
            } catch SyncError.unauthorized {
                throw SyncError.unauthorized
            } catch {
                lastErr = (error as? SyncError).map { if case .unreachable(let w) = $0 { w } else { "" } } ?? error.localizedDescription
            }
        }
        throw SyncError.unreachable(lastErr)
    }

    private func request(_ url: URL, body: Any?) -> URLRequest {
        var req = URLRequest(url: url, timeoutInterval: 10)
        req.setValue(Config.key, forHTTPHeaderField: "X-Alibi-Secret")
        if let body {
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        }
        return req
    }

    private func send(_ req: URLRequest) async throws -> (Int, Data) {
        do {
            let (data, resp) = try await URLSession.shared.data(for: req)
            return ((resp as? HTTPURLResponse)?.statusCode ?? 0, data)
        } catch {
            throw SyncError.unreachable(error.localizedDescription)
        }
    }

    private func postBatch(_ rows: [Row], to ep: String) async throws {
        guard let url = URL(string: ep) else { throw SyncError.unreachable("bad address \(ep)") }
        let (code, data) = try await send(request(url, body: ["batch": rows]))
        switch code {
        case 200:
            // Only trust an endpoint that answers like Alibi ({"saved": n, ...}); a captive portal or some other server
            // on that port also says 200, and trusting it would drop the rows and advance every cursor.
            guard let d = try? JSONSerialization.jsonObject(with: data) as? [String: Any], d["saved"] != nil else {
                throw SyncError.unreachable("\(url.host ?? ep) answered, but not like Alibi")
            }
            if let sess = d["session"] as? [String: Any] { sessionFromReply = sess }
            return
        case 401, 403: throw SyncError.unauthorized
        case 400, 422:
            // An older Mac build without batch support: send rows one by one. A row the Mac rejects (400/422) is
            // dropped, not retried; anything else (404/405/5xx/no answer/not Alibi) fails the whole delivery so the
            // next address is tried and no cursor moves.
            for r in rows {
                let (c, body) = try await send(request(url, body: r))
                switch c {
                case 200:
                    guard (try? JSONSerialization.jsonObject(with: body)) is [String: Any] else {
                        throw SyncError.unreachable("\(url.host ?? ep) answered, but not like Alibi")
                    }
                case 400, 422: continue
                case 401, 403: throw SyncError.unauthorized
                default: throw SyncError.unreachable("HTTP \(c)")
                }
            }
        default:
            // 404/405 included: wrong port, stale `tailscale serve` config or a proxy — not an Alibi /ingest.
            throw SyncError.unreachable("HTTP \(code) \(String(data: data, encoding: .utf8)?.prefix(80) ?? "")")
        }
    }

    // MARK: session (near-live)

    /// Session info from the last batch reply (the Mac includes it), so the extra GET is skipped.
    private var sessionFromReply: [String: Any]?

    func pollSession() async {
        if let d = sessionFromReply { sessionFromReply = nil; applySession(d); return }
        guard let ep = endpointOrder.first, let url = Config.sibling(of: ep, path: "/api/phone/session") else { return }
        guard let (code, data) = try? await send(request(url, body: nil)), code == 200,
              let d = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return                                                     // older Mac build: no session endpoint yet
        }
        applySession(d)
    }

    private func applySession(_ d: [String: Any]) {
        let new = SessionInfo(active: d["active"] as? Bool ?? false, habit: (d["label"] as? String) ?? (d["habit"] as? String),
                              endsAt: (d["ends_at"] as? Double).map { Date(timeIntervalSince1970: $0) },
                              shield: d["shield"] as? Bool ?? false, every: max(60, d["sync_every_s"] as? Double ?? 120))
        session = new
        Store.set(new.active, "session.active")
        Store.set(new.every, "session.every")
        Store.set(new.active ? new.habit : nil, AlibiShared.habitKey)        // shown on the shield screen
        Shields.current.apply(on: new.active && new.shield, source: "session")   // idempotent; also re-arms after a relaunch
        if new.active { startLive(); Self.scheduleBackground(after: new.every) } else { liveTask?.cancel(); liveTask = nil }
    }

    /// While a session runs: sync every `every` seconds for as long as iOS keeps us running.
    func startLive() {
        guard liveTask == nil else { return }
        liveTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self, let s = self.session, s.active else { break }
                try? await Task.sleep(for: .seconds(s.every))
                if Task.isCancelled { break }
                let bgLeft = UIApplication.shared.backgroundTimeRemaining
                if !self.foreground && bgLeft < 20 { break }
                await self.run(reason: "live")
            }
            self?.liveTask = nil
        }
    }

    func setForeground(_ on: Bool) {
        foreground = on
        if on, session?.active == true { startLive() }
    }

    /// For wakes (geofence, Focus filter, Health observer): ask iOS for ~30 s, sync, hand the time back.
    func syncInBackground(reason: String) {
        var id = UIBackgroundTaskIdentifier.invalid
        id = UIApplication.shared.beginBackgroundTask(withName: "alibi-sync") {
            UIApplication.shared.endBackgroundTask(id); id = .invalid
        }
        Task {
            await self.run(reason: reason)
            if id != .invalid { UIApplication.shared.endBackgroundTask(id) }
        }
    }

    // MARK: background registration

    nonisolated static func registerBackground() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: refreshID, using: nil) { task in
            handle(task)
        }
        BGTaskScheduler.shared.register(forTaskWithIdentifier: processingID, using: nil) { task in
            handle(task)
        }
        // Health observers + background delivery need the permission sheet to have been shown first; on a fresh install
        // they're started from Permissions.requestHealth() instead.
        Task { if await Health.shared.asked() { Health.shared.startObservers() } }
    }

    nonisolated private static func handle(_ task: BGTask) {
        let t = Task { @MainActor in
            await SyncEngine.shared.run(reason: "bgtask")
            let s = SyncEngine.shared.session
            scheduleBackground(after: s?.active == true ? s!.every : 3 * 3600)
            task.setTaskCompleted(success: SyncEngine.shared.ok == true)
        }
        task.expirationHandler = { t.cancel() }
    }

    /// iOS decides the real time; during a session we ask for ~2 min, otherwise every few hours.
    nonisolated static func scheduleBackground(after seconds: Double = 3 * 3600) {
        let r = BGAppRefreshTaskRequest(identifier: refreshID)
        r.earliestBeginDate = Date(timeIntervalSinceNow: seconds)
        try? BGTaskScheduler.shared.submit(r)
        let p = BGProcessingTaskRequest(identifier: processingID)
        p.requiresNetworkConnectivity = true
        p.earliestBeginDate = Date(timeIntervalSinceNow: max(seconds, 15 * 60))
        try? BGTaskScheduler.shared.submit(p)
    }
}
