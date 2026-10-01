// Apple Health → health.samples (one row per day, last 7 days) and health.heart (heart-rate samples since last sync).
// Daily rows are only re-sent when a day's numbers changed (hash cursor); heart rate uses a persisted HKQueryAnchor.
import CryptoKit
import Foundation
import HealthKit
import os

/// What a collector produced plus how to advance its cursor once the Mac has the rows.
struct Collected {
    let stream: String
    var rows: [Row]
    var commit: () -> Void = {}
}

final class Health {
    static let shared = Health()
    let store = HKHealthStore()
    var available: Bool { HKHealthStore.isHealthDataAvailable() }

    private let quantities: [(key: String, id: HKQuantityTypeIdentifier, unit: HKUnit, sum: Bool, places: Int)] = [
        ("steps", .stepCount, .count(), true, 0),
        ("distance_km", .distanceWalkingRunning, .meterUnit(with: .kilo), true, 2),
        ("flights", .flightsClimbed, .count(), true, 0),
        ("active_kcal", .activeEnergyBurned, .kilocalorie(), true, 0),
        ("exercise_min", .appleExerciseTime, .minute(), true, 0),
        ("daylight_min", .timeInDaylight, .minute(), true, 0),
        ("resting_hr", .restingHeartRate, HKUnit.count().unitDivided(by: .minute()), false, 0),
        ("hrv_ms", .heartRateVariabilitySDNN, .secondUnit(with: .milli), false, 0),
        ("resp_rate", .respiratoryRate, HKUnit.count().unitDivided(by: .minute()), false, 1),
        ("headphone_db", .headphoneAudioExposure, .decibelAWeightedSoundPressureLevel(), false, 0),
    ]
    static let bpm = HKUnit.count().unitDivided(by: .minute())

    var readTypes: Set<HKObjectType> {
        var s: Set<HKObjectType> = Set(quantities.map { HKQuantityType($0.id) })
        s.formUnion([HKQuantityType(.heartRate), HKQuantityType(.distanceCycling), HKQuantityType(.distanceSwimming),
                     HKCategoryType(.sleepAnalysis), HKCategoryType(.mindfulSession), HKCategoryType(.appleStandHour),
                     HKObjectType.workoutType()])
        if #available(iOS 18.0, *) { s.insert(HKObjectType.stateOfMindType()) }
        return s
    }

    /// Types that wake the app in the background when new samples land.
    var observedTypes: [HKSampleType] {
        [HKQuantityType(.heartRate), HKQuantityType(.stepCount), HKCategoryType(.sleepAnalysis),
         HKCategoryType(.mindfulSession), HKObjectType.workoutType()]
    }

    private static let log = Logger(subsystem: "app.theultras.alibi", category: "health")
    private let observerLock = NSLock()
    private var observersStarted = false
    /// Last background-delivery problem (nil when every observed type registered fine). Shown in the Streams list.
    static let bgErrorKey = "health.bg.error"

    /// Observer queries + immediate background delivery for `observedTypes`: new samples wake the app and trigger a
    /// sync (live heart rate during sessions). Runs once per process, and only after the Health sheet has been shown —
    /// before that HealthKit rejects both, so launch calls it when `asked()` is already true and requestHealth() calls
    /// it right after the user answers the sheet.
    func startObservers() {
        guard available else { return }
        observerLock.lock()
        if observersStarted { observerLock.unlock(); return }
        observersStarted = true
        observerLock.unlock()
        Store.set(nil, Self.bgErrorKey)
        for type in observedTypes {
            let q = HKObserverQuery(sampleType: type, predicate: nil) { _, done, err in
                if let err {
                    Self.log.error("observer \(type.identifier, privacy: .public) failed: \(err.localizedDescription, privacy: .public)")
                    done(); return
                }
                Task { @MainActor in
                    await SyncEngine.shared.runAuto(reason: "health")
                    done()
                }
            }
            store.execute(q)
            store.enableBackgroundDelivery(for: type, frequency: .immediate) { ok, err in
                guard !ok || err != nil else { return }
                let why = err?.localizedDescription ?? "unknown error"
                Self.log.error("background delivery for \(type.identifier, privacy: .public) failed: \(why, privacy: .public)")
                Store.set("Background updates off (\(why))", Self.bgErrorKey)
            }
        }
    }

    func authorize() async throws {
        guard available else { return }
        try await store.requestAuthorization(toShare: [], read: readTypes)
    }

    /// true once the permission sheet has been shown (HealthKit never reveals whether *read* access was granted).
    func asked() async -> Bool {
        guard available else { return false }
        return await withCheckedContinuation { c in
            store.getRequestStatusForAuthorization(toShare: [], read: readTypes) { s, _ in c.resume(returning: s == .unnecessary) }
        }
    }

    // MARK: daily rows

    func dayRows(days: Int = 7) async -> [String: [String: Any]] {
        let cal = Calendar.current
        let today = cal.startOfDay(for: Date())
        let start = cal.date(byAdding: .day, value: -(days - 1), to: today)!
        var out: [String: [String: Any]] = [:]
        for i in 0..<days { let k = Fmt.day.string(from: cal.date(byAdding: .day, value: i, to: start)!); out[k] = ["date": k] }
        let key = { (d: Date) in Fmt.day.string(from: cal.startOfDay(for: d)) }

        for q in quantities {
            let desc = HKStatisticsCollectionQueryDescriptor(
                predicate: .quantitySample(type: HKQuantityType(q.id), predicate: HKQuery.predicateForSamples(withStart: start, end: nil)),
                options: q.sum ? .cumulativeSum : .discreteAverage, anchorDate: start, intervalComponents: DateComponents(day: 1))
            guard let coll = try? await desc.result(for: store) else { continue }
            coll.enumerateStatistics(from: start, to: Date()) { s, _ in
                let qty = q.sum ? s.sumQuantity() : s.averageQuantity()
                guard let v = qty?.doubleValue(for: q.unit) else { return }
                out[key(s.startDate)]?[q.key] = q.places == 0 ? v.rounded() : Fmt.r(v, q.places)
            }
        }

        // Stand hours: count of hours marked "stood".
        if let stands = try? await categorySamples(.appleStandHour, from: start) {
            for s in stands where s.value == HKCategoryValueAppleStandHour.stood.rawValue {
                let k = key(s.startDate)
                let cur = (out[k]?["stand_h"] as? Double) ?? 0
                out[k]?["stand_h"] = cur + 1
            }
        }

        await addSleep(into: &out, start: start)

        // Mindful minutes (overlapping sessions from several apps merged).
        if let ms = try? await categorySamples(.mindfulSession, from: start) {
            var perDay: [String: [(Date, Date)]] = [:]
            for s in ms { perDay[key(s.startDate), default: []].append((s.startDate, s.endDate)) }
            for (k, iv) in perDay where out[k] != nil { out[k]?["mindful_min"] = (Self.union(iv) / 60).rounded() }
        }

        await addWorkouts(into: &out, start: start)
        if #available(iOS 18.0, *) { await addMoods(into: &out, start: start) }
        return out
    }

    private func categorySamples(_ id: HKCategoryTypeIdentifier, from: Date) async throws -> [HKCategorySample] {
        try await HKSampleQueryDescriptor(predicates: [.categorySample(type: HKCategoryType(id),
            predicate: HKQuery.predicateForSamples(withStart: from, end: nil))], sortDescriptors: [SortDescriptor(\.startDate)]).result(for: store)
    }

    /// Total seconds covered by possibly-overlapping intervals.
    static func union(_ iv: [(Date, Date)]) -> Double { merge(iv).reduce(0) { $0 + $1.1.timeIntervalSince($1.0) } }
    static func merge(_ iv: [(Date, Date)]) -> [(Date, Date)] {
        var m: [(Date, Date)] = []
        for (a, b) in iv.sorted(by: { $0.0 < $1.0 }) {
            if let last = m.last, a <= last.1 { m[m.count - 1].1 = max(last.1, b) } else { m.append((a, b)) }
        }
        return m
    }

    /// Sleep is credited to the morning you woke up (a sample ending before 18:00 counts for that day).
    private func addSleep(into out: inout [String: [String: Any]], start: Date) async {
        let cal = Calendar.current
        guard let samples = try? await categorySamples(.sleepAnalysis, from: cal.date(byAdding: .hour, value: -6, to: start)!) else { return }
        typealias V = HKCategoryValueSleepAnalysis
        let asleep: Set<Int> = [V.asleepUnspecified.rawValue, V.asleepCore.rawValue, V.asleepDeep.rawValue, V.asleepREM.rawValue]
        var nights: [String: [HKCategorySample]] = [:]
        for s in samples { nights[Fmt.day.string(from: cal.startOfDay(for: s.endDate.addingTimeInterval(6 * 3600))), default: []].append(s) }
        for (k, ss) in nights where out[k] != nil {
            let iv = { (vals: Set<Int>) in ss.filter { vals.contains($0.value) }.map { ($0.startDate, $0.endDate) } }
            let total = Self.union(iv(asleep))
            guard total > 0 || !iv([V.inBed.rawValue]).isEmpty else { continue }
            if total > 0 { out[k]?["sleep_h"] = Fmt.r(total / 3600, 2) }
            var stages: [String: Any] = [
                "core_h": Fmt.r(Self.union(iv([V.asleepCore.rawValue, V.asleepUnspecified.rawValue])) / 3600, 2),
                "deep_h": Fmt.r(Self.union(iv([V.asleepDeep.rawValue])) / 3600, 2),
                "rem_h": Fmt.r(Self.union(iv([V.asleepREM.rawValue])) / 3600, 2),
                "awake_h": Fmt.r(Self.union(iv([V.awake.rawValue])) / 3600, 2),
            ]
            // Main sleep = the longest merged block (so an afternoon nap doesn't move bed/wake time).
            let blocks = Self.merge(iv(asleep.union([V.inBed.rawValue])))
            if let main = blocks.max(by: { $0.1.timeIntervalSince($0.0) < $1.1.timeIntervalSince($1.0) }) {
                stages["bed"] = Fmt.hm.string(from: main.0)
                stages["wake"] = Fmt.hm.string(from: main.1)
            }
            out[k]?["sleep"] = stages
        }
    }

    private func addWorkouts(into out: inout [String: [String: Any]], start: Date) async {
        let desc = HKSampleQueryDescriptor(predicates: [.workout(HKQuery.predicateForSamples(withStart: start, end: nil))],
                                           sortDescriptors: [SortDescriptor(\.startDate)])
        guard let ws = try? await desc.result(for: store) else { return }
        for w in ws {
            let k = Fmt.day.string(from: Calendar.current.startOfDay(for: w.startDate))
            guard out[k] != nil else { continue }
            let mins = (w.duration / 60).rounded()
            var item: [String: Any] = ["type": w.workoutActivityType.name, "start": Fmt.hm.string(from: w.startDate), "min": mins]
            for d in [HKQuantityType(.distanceWalkingRunning), HKQuantityType(.distanceCycling), HKQuantityType(.distanceSwimming)] {
                if let km = w.statistics(for: d)?.sumQuantity()?.doubleValue(for: .meterUnit(with: .kilo)), km > 0 {
                    item["km"] = Fmt.r(km, 2); break
                }
            }
            if let hr = w.statistics(for: HKQuantityType(.heartRate))?.averageQuantity()?.doubleValue(for: Self.bpm) { item["avg_hr"] = hr.rounded() }
            if let kc = w.statistics(for: HKQuantityType(.activeEnergyBurned))?.sumQuantity()?.doubleValue(for: .kilocalorie()) { item["kcal"] = kc.rounded() }
            let curMin = (out[k]?["workout_min"] as? Double) ?? 0
            let curList = (out[k]?["workouts"] as? [[String: Any]]) ?? []
            out[k]?["workout_min"] = curMin + mins
            out[k]?["workouts"] = curList + [item]
        }
    }

    @available(iOS 18.0, *)
    private func addMoods(into out: inout [String: [String: Any]], start: Date) async {
        let desc = HKSampleQueryDescriptor(predicates: [.stateOfMind(HKQuery.predicateForSamples(withStart: start, end: nil))],
                                           sortDescriptors: [SortDescriptor(\.startDate)])
        guard let ms = try? await desc.result(for: store) else { return }
        for m in ms {
            let k = Fmt.day.string(from: Calendar.current.startOfDay(for: m.startDate))
            guard out[k] != nil else { continue }
            let item: [String: Any] = ["ts": m.startDate.timeIntervalSince1970.rounded(), "valence": Fmt.r(m.valence, 2),
                                       "labels": m.labels.map(\.name)]
            let cur = (out[k]?["moods"] as? [[String: Any]]) ?? []
            out[k]?["moods"] = cur + [item]
        }
    }

    /// health.samples rows for days whose numbers changed since they were last delivered (all of them when `full`).
    func collectDays(full: Bool) async -> Collected {
        let days = await dayRows()
        var hashes = Store.d.dictionary(forKey: "health.dayhash") as? [String: String] ?? [:]
        var rows: [Row] = []
        var newHashes: [String: String] = [:]
        for (k, p) in days where p.count > 1 {                              // skip days with only {"date"}
            let data = (try? JSONSerialization.data(withJSONObject: p, options: [.sortedKeys])) ?? Data()
            let h = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
            if !full && hashes[k] == h { continue }
            newHashes[k] = h
            let noon = Calendar.current.date(bySettingHour: 12, minute: 0, second: 0, of: Fmt.day.date(from: k) ?? Date()) ?? Date()
            rows.append(row("health", "samples", ts: min(noon, Date()).timeIntervalSince1970, p))
        }
        await MainActor.run { Snapshot.shared.absorb(days: days) }
        return Collected(stream: "health", rows: rows) {
            hashes.merge(newHashes) { $1 }
            let keep = Set(days.keys)
            Store.set(hashes.filter { keep.contains($0.key) }, "health.dayhash")
        }
    }

    // MARK: heart rate

    private static let anchorKey = "health.heart.anchor"

    /// health.heart rows: every heart-rate sample added since the last delivered anchor (first run: last 6 hours).
    func collectHeart() async -> Collected {
        var anchor: HKQueryAnchor?
        if let data = Store.d.data(forKey: Self.anchorKey) {
            anchor = try? NSKeyedUnarchiver.unarchivedObject(ofClass: HKQueryAnchor.self, from: data)
        }
        let since = Date().addingTimeInterval(anchor == nil ? -6 * 3600 : -3 * 86400)
        let desc = HKAnchoredObjectQueryDescriptor(
            predicates: [.quantitySample(type: HKQuantityType(.heartRate), predicate: HKQuery.predicateForSamples(withStart: since, end: nil))],
            anchor: anchor, limit: 5000)
        guard let res = try? await desc.result(for: store) else { return Collected(stream: "heart", rows: []) }
        let samples = res.addedSamples.sorted { $0.startDate < $1.startDate }
            .map { [Fmt.r($0.startDate.timeIntervalSince1970, 0), $0.quantity.doubleValue(for: Self.bpm).rounded()] }
        if let last = res.addedSamples.max(by: { $0.startDate < $1.startDate }) {
            let bpm = last.quantity.doubleValue(for: Self.bpm)
            await MainActor.run { Snapshot.shared.noteHeart(bpm: bpm, at: last.startDate) }
        }
        var rows: [Row] = []
        var i = 0
        while i < samples.count {
            let chunk = Array(samples[i..<min(i + 1000, samples.count)])
            rows.append(row("health", "heart", ts: chunk.last?[0] ?? Date().timeIntervalSince1970, ["samples": chunk]))
            i += 1000
        }
        let newAnchor = res.newAnchor
        return Collected(stream: "heart", rows: rows) {
            if let data = try? NSKeyedArchiver.archivedData(withRootObject: newAnchor, requiringSecureCoding: true) {
                Store.set(data, Self.anchorKey)
            }
        }
    }

    /// Most recent heart rate for the UI (works even when nothing new needs sending).
    func latestHeart() async -> (Double, Date)? {
        let desc = HKSampleQueryDescriptor(predicates: [.quantitySample(type: HKQuantityType(.heartRate))],
                                           sortDescriptors: [SortDescriptor(\.startDate, order: .reverse)], limit: 1)
        guard let s = try? await desc.result(for: store).first else { return nil }
        return (s.quantity.doubleValue(for: Self.bpm), s.startDate)
    }
}

extension HKWorkoutActivityType {
    var name: String {
        switch self {
        case .running: "Run"; case .walking: "Walk"; case .cycling: "Ride"; case .yoga: "Yoga"; case .swimming: "Swim"
        case .traditionalStrengthTraining, .functionalStrengthTraining: "Strength"; case .hiking: "Hike"
        case .highIntensityIntervalTraining: "HIIT"; case .mindAndBody: "Mind & body"; case .rowing: "Row"
        case .elliptical: "Elliptical"; case .stairClimbing, .stairs: "Stairs"; case .coreTraining: "Core"
        case .pilates: "Pilates"; case .dance, .socialDance, .cardioDance: "Dance"; case .cooldown: "Cooldown"
        case .tennis: "Tennis"; case .soccer: "Football"; case .basketball: "Basketball"; case .badminton: "Badminton"
        case .crossTraining: "Cross training"; case .mixedCardio: "Cardio"
        default: "Workout"
        }
    }
}

@available(iOS 18.0, *)
extension HKStateOfMind.Label {
    var name: String {
        switch self {
        case .amazed: "amazed"; case .amused: "amused"; case .angry: "angry"; case .anxious: "anxious"; case .ashamed: "ashamed"
        case .brave: "brave"; case .calm: "calm"; case .content: "content"; case .disappointed: "disappointed"
        case .discouraged: "discouraged"; case .disgusted: "disgusted"; case .embarrassed: "embarrassed"; case .excited: "excited"
        case .frustrated: "frustrated"; case .grateful: "grateful"; case .guilty: "guilty"; case .happy: "happy"
        case .hopeless: "hopeless"; case .irritated: "irritated"; case .jealous: "jealous"; case .joyful: "joyful"
        case .lonely: "lonely"; case .passionate: "passionate"; case .peaceful: "peaceful"; case .proud: "proud"
        case .relieved: "relieved"; case .sad: "sad"; case .scared: "scared"; case .stressed: "stressed"
        case .surprised: "surprised"; case .worried: "worried"; case .annoyed: "annoyed"; case .confident: "confident"
        case .drained: "drained"; case .hopeful: "hopeful"; case .indifferent: "indifferent"; case .overwhelmed: "overwhelmed"
        case .satisfied: "satisfied"
        @unknown default: "other"
        }
    }
}
