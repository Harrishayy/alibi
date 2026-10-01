// Core Motion activity history → phone.motion segments, and a best-effort pickup detector → phone.pickup.
// iOS keeps 7 days of activity history, so nothing is lost while the app is asleep: each sync reads from the cursor.
import CoreMotion
import Foundation

final class Motion {
    static let shared = Motion()
    private let manager = CMMotionActivityManager()
    private static let cursorKey = "motion.cursor"

    var available: Bool { CMMotionActivityManager.isActivityAvailable() }
    var status: CMAuthorizationStatus { CMMotionActivityManager.authorizationStatus() }

    /// Shows the Motion & Fitness prompt (a tiny history query is the only way to trigger it).
    func authorize() async {
        guard available, status == .notDetermined else { return }
        _ = await activities(from: Date().addingTimeInterval(-60), to: Date())
    }

    private func activities(from: Date, to: Date) async -> [CMMotionActivity] {
        await withCheckedContinuation { c in
            manager.queryActivityStarting(from: from, to: to, to: .main) { acts, _ in c.resume(returning: acts ?? []) }
        }
    }

    struct Segment { var start: Date; var end: Date; var state: String; var confidence: String }

    static func state(_ a: CMMotionActivity) -> String {
        if a.automotive { return "automotive" }
        if a.cycling { return "cycling" }
        if a.running { return "running" }
        if a.walking { return "walking" }
        if a.stationary { return "stationary" }
        return "unknown"
    }

    static func confidence(_ a: CMMotionActivity) -> String {
        switch a.confidence { case .high: "high"; case .medium: "medium"; default: "low" }
    }

    /// Collapse consecutive activities with the same state into segments; the last one is still open.
    static func segments(_ acts: [CMMotionActivity], until now: Date) -> [Segment] {
        var segs: [Segment] = []
        for a in acts {
            let st = state(a)
            if var last = segs.last, last.state == st {
                if a.confidence.rawValue > (["low": 0, "medium": 1, "high": 2][last.confidence] ?? 0) { last.confidence = confidence(a) }
                segs[segs.count - 1] = last
                continue
            }
            if !segs.isEmpty { segs[segs.count - 1].end = a.startDate }
            segs.append(Segment(start: a.startDate, end: now, state: st, confidence: confidence(a)))
        }
        return segs
    }

    /// Phone moved after resting ≥ 2 min = it was probably picked up.
    static func pickups(_ segs: [Segment]) -> [Date] {
        guard segs.count > 1 else { return [] }
        var out: [Date] = []
        for i in 1..<segs.count where segs[i - 1].state == "stationary" && segs[i].state != "stationary"
            && segs[i - 1].end.timeIntervalSince(segs[i - 1].start) >= 120 {
            out.append(segs[i].start)
        }
        return out
    }

    /// phone.motion rows for every closed segment since the cursor, plus phone.pickup rows. The query starts at the last
    /// already-sent segment so the stationary→moving transition at the boundary isn't missed; rows are de-duplicated by cursors.
    func collect() async -> (motion: Collected, pickups: Collected) {
        let empty = (Collected(stream: "motion", rows: []), Collected(stream: "pickup", rows: []))
        guard available, status == .authorized else { return empty }
        let now = Date()
        let cursor = Store.double(Self.cursorKey)                   // start of the segment that was still open last time
        let prev = Store.double("motion.prev")                       // start of the last segment already sent
        let pickCursor = Store.double("pickup.cursor")
        let floor = now.addingTimeInterval(-7 * 86400)
        let from = max(prev > 0 ? Date(timeIntervalSince1970: prev) : cursor > 0 ? Date(timeIntervalSince1970: cursor)
                       : now.addingTimeInterval(-24 * 3600), floor)
        let segs = Self.segments(await activities(from: from, to: now), until: now)
        if let open = segs.last { await MainActor.run { Snapshot.shared.motionNow = (open.state, open.start) } }
        guard segs.count > 1 else { return empty }
        let closed = segs.dropLast().filter { $0.start.timeIntervalSince1970 >= cursor - 0.5 }
        let rows: [Row] = closed.map {
            row("phone", "motion", ts: $0.start.timeIntervalSince1970, ["start": Fmt.r($0.start.timeIntervalSince1970, 0),
                "end": Fmt.r($0.end.timeIntervalSince1970, 0), "state": $0.state, "confidence": $0.confidence])
        }
        let picks = Self.pickups(segs).filter { $0.timeIntervalSince1970 > pickCursor + 0.5 }
        let pickRows: [Row] = picks.map { row("phone", "pickup", ts: $0.timeIntervalSince1970, ["ts": Fmt.r($0.timeIntervalSince1970, 0)]) }
        let newCursor = segs.last!.start.timeIntervalSince1970
        let newPrev = segs[segs.count - 2].start.timeIntervalSince1970
        let newPick = picks.last?.timeIntervalSince1970 ?? pickCursor
        return (Collected(stream: "motion", rows: rows) { Store.set(newCursor, Self.cursorKey); Store.set(newPrev, "motion.prev") },
                Collected(stream: "pickup", rows: pickRows) {
                    Store.set(newPick, "pickup.cursor")
                    let today = Fmt.day.string(from: Date())
                    let n = (Store.d.string(forKey: "pickup.day") == today ? Store.d.integer(forKey: "pickup.count") : 0)
                        + picks.filter { Calendar.current.isDateInToday($0) }.count
                    Store.set(today, "pickup.day"); Store.set(n, "pickup.count")
                })
    }

    /// Pickups delivered today (for the UI).
    static var pickupsToday: Int {
        Store.d.string(forKey: "pickup.day") == Fmt.day.string(from: Date()) ? Store.d.integer(forKey: "pickup.count") : 0
    }
}
