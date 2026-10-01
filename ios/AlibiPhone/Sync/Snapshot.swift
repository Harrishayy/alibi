// Latest values for the Streams list ("steps today", "sleep last night", "HR now", "motion now").
import Foundation

@MainActor
final class Snapshot: ObservableObject {
    static let shared = Snapshot()
    @Published var stepsToday: Double?
    @Published var sleepLastNight: Double?
    @Published var bedWake: String?
    @Published var heart: (bpm: Double, at: Date)?
    @Published var motionNow: (state: String, since: Date)?
    @Published var days: [[String: Any]] = []

    func absorb(days: [String: [String: Any]]) {
        let today = Fmt.day.string(from: Date())
        stepsToday = days[today]?["steps"] as? Double
        sleepLastNight = days[today]?["sleep_h"] as? Double
        if let s = days[today]?["sleep"] as? [String: Any], let b = s["bed"] as? String, let w = s["wake"] as? String { bedWake = "\(b)–\(w)" }
        self.days = days.values.sorted { ($0["date"] as? String ?? "") > ($1["date"] as? String ?? "") }
    }

    func noteHeart(bpm: Double, at: Date) {
        if heart == nil || at > heart!.at { heart = (bpm, at) }
    }
}
