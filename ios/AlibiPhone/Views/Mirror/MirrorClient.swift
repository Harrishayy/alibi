// The live mirror: while the app is in the foreground, ask the Mac's phone listener for `/api/phone/session` every 3 s
// (same address list and key as SyncEngine), publish what came back, turn new `pinch.seq` events into one-shot clips,
// and hand every update to the Live Activity. Never polls in the background.
//
// DEBUG demo mode for deterministic screenshots: launch with `-AlibiDemo <name>` and the mirror loads the bundled
// fixture Views/DemoFixtures/<name>.json instead of polling (`offline` fakes an unreachable Mac). Fixture times are
// rebased so "now" in the fixture is now on the device, so timers tick from the same place every launch.
import Foundation
import SwiftUI

@MainActor
final class MirrorClient: ObservableObject {
    static let shared = MirrorClient()
    static let every: Duration = .seconds(3)

    @Published private(set) var session: PhoneSession?
    /// nil until the first answer (or failure); then whether the last poll reached the Mac.
    @Published private(set) var online: Bool?
    @Published private(set) var lastOK: Date?
    /// The one-shot Pinch should play; `clipID` bumps to replay it.
    @Published private(set) var clip: PinchClip?
    @Published private(set) var clipID = 0
    /// Haptic triggers: bump when a done verdict lands / when the nudge count rises.
    @Published private(set) var doneCount = 0
    @Published private(set) var nudgeCount = 0

    private var lastSeq: Int?
    private var lastVerdictEnd: Double?
    private var lastNudges: Int?
    private var loop: Task<Void, Never>?
    private var good: String?

    // MARK: demo mode

    #if DEBUG
    static let demoName: String? = UserDefaults.standard.string(forKey: "AlibiDemo")
    #else
    static let demoName: String? = nil
    #endif
    static var demo: Bool { demoName != nil }
    /// The Mac's name, or the fixture's in demo mode.
    @Published private(set) var macName = Config.macName

    // MARK: lifecycle

    /// Poll while active; stop when the app leaves the foreground.
    func setActive(_ on: Bool) {
        loop?.cancel(); loop = nil
        guard on else { return }
        loop = Task { [weak self] in
            while !Task.isCancelled {
                await self?.refresh()
                try? await Task.sleep(for: Self.every)
            }
        }
    }

    func refresh() async {
        if Self.demo { loadDemo(); return }
        guard Config.configured else { fail(); return }
        let order = ([good, Store.d.string(forKey: "sync.endpoint")].compactMap { $0 } + Config.endpoints)
            .reduce(into: [String]()) { if !$0.contains($1) && !$1.isEmpty { $0.append($1) } }
        for ep in order {
            guard let url = Config.sibling(of: ep, path: "/api/phone/session") else { continue }
            var req = URLRequest(url: url, timeoutInterval: 2.5)
            req.setValue(Config.key, forHTTPHeaderField: "X-Alibi-Secret")
            guard let (data, resp) = try? await URLSession.shared.data(for: req),
                  (resp as? HTTPURLResponse)?.statusCode == 200,
                  let s = PhoneSession.decode(data) else { continue }
            good = ep
            apply(s)
            return
        }
        fail()
    }

    private func fail() {
        online = false
        LiveActivityController.shared.sync(nil)
    }

    private func apply(_ s: PhoneSession, firstPlays: Bool = false) {
        let first = online == nil || session == nil
        // Pinch: record the first seq without playing (unless a demo asks), then play each newer, fresh event once.
        if let p = s.pinch, let seq = p.seq, seq > 0 {
            let fresh = (p.age_s ?? 0) < 15
            if (first ? firstPlays : seq > (lastSeq ?? 0)) && fresh, let ev = p.event.flatMap(PinchClip.init(rawValue:)) {
                clip = ev; clipID += 1
            }
            lastSeq = max(seq, lastSeq ?? 0)
        }
        // Haptics: a new done verdict; a rising nudge count.
        if let v = s.recent_verdict, let end = v.ended_at, end != lastVerdictEnd {
            if (!first || firstPlays) && v.verdict == "done" { doneCount += 1 }
            lastVerdictEnd = end
        }
        let n = s.live?.nudges ?? 0
        if let last = lastNudges, n > last { nudgeCount += 1 }
        lastNudges = s.live == nil ? nil : n

        withAnimation(Alibi.Motion.smooth) {
            session = s
            online = true
        }
        lastOK = Date()
        LiveActivityController.shared.sync(s)
    }

    private var demoLoaded = false

    private func loadDemo() {
        guard !demoLoaded, let name = Self.demoName else { return }
        demoLoaded = true
        if name == "offline" { online = false; return }
        let url = Bundle.main.url(forResource: name, withExtension: "json")
            ?? Bundle.main.url(forResource: name, withExtension: "json", subdirectory: "DemoFixtures")
        guard let url, let data = try? Data(contentsOf: url),
              var obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { fail(); return }
        let offset = Date().timeIntervalSince1970 - ((obj["demo_now"] as? Double) ?? Date().timeIntervalSince1970)
        obj = Self.rebase(obj, by: offset) as? [String: Any] ?? obj
        if let mac = obj["demo_mac"] as? String { macName = mac }
        if let days = obj["demo_health_days"] as? [[String: Any]] {
            var byDate: [String: [String: Any]] = [:]
            for d in days {
                let ago = (d["days_ago"] as? Int) ?? 0
                let date = Fmt.day.string(from: Calendar.current.date(byAdding: .day, value: -ago, to: Date()) ?? Date())
                var row = d; row["date"] = date; row.removeValue(forKey: "days_ago")
                byDate[date] = row
            }
            Snapshot.shared.absorb(days: byDate)
        }
        guard let clean = try? JSONSerialization.data(withJSONObject: obj), let s = PhoneSession.decode(clean) else { fail(); return }
        apply(s, firstPlays: true)
    }

    /// Shift every timestamp key by `offset` seconds, recursively.
    private static func rebase(_ v: Any, by offset: Double) -> Any {
        if let d = v as? [String: Any] {
            var out = d
            for (k, x) in d {
                if ["started_at", "ends_at", "ended_at", "starts_at", "until", "week_start", "demo_now"].contains(k), let t = x as? Double {
                    out[k] = t + offset
                } else if k == "line", let s = x as? String {
                    out[k] = shiftClock(s, by: offset)
                } else {
                    out[k] = rebase(x, by: offset)
                }
            }
            return out
        }
        if let a = v as? [Any] { return a.map { rebase($0, by: offset) } }
        return v
    }

    /// Fixture lines were written against the fixture's own clock ("Back at 18:20."), which no longer matches the
    /// rebased timers; drop those so Today composes the line from the (rebased) numbers instead.
    private static func shiftClock(_ s: String, by offset: Double) -> Any {
        s.range(of: #"\b\d{1,2}:\d{2}\b"#, options: .regularExpression) == nil ? s : NSNull()
    }
}
