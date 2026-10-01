// Alibi for iPhone — reads daily Health totals (steps, sleep, mindful minutes, workouts) and sends them to the
// Alibi app on your Mac. Syncs when opened, on "Sync now", and in the background when iOS allows it.
// Mac address + key come from Generated/AlibiConfig.plist, written by ios/build_install.sh from data/secrets.json.
import BackgroundTasks
import HealthKit
import SwiftUI

let green = Color(red: 0x76 / 255, green: 0xB9 / 255, blue: 0)
let ink = Color(white: 0.65)
let bgTaskID = "app.theultras.alibi.sync"

struct DayTotals: Codable, Identifiable {
    var id: String { date }
    let date: String
    var steps: Double?
    var sleep_h: Double?
    var mindful_min: Double?
    var workout_min: Double?
    var workouts: [[String: String]]?
}

enum Config {
    static let dict: [String: Any] = {
        guard let url = Bundle.main.url(forResource: "AlibiConfig", withExtension: "plist"),
              let d = NSDictionary(contentsOf: url) as? [String: Any] else { return [:] }
        return d
    }()
    static var endpoints: [String] { dict["endpoints"] as? [String] ?? [] }   // full ingest URLs, best first
    static var key: String { dict["key"] as? String ?? "" }
    static var macName: String { dict["mac_name"] as? String ?? "your Mac" }
}

// MARK: - Health

final class Health {
    static let shared = Health()
    let store = HKHealthStore()
    let types: Set<HKObjectType> = [
        HKQuantityType(.stepCount), HKCategoryType(.sleepAnalysis), HKCategoryType(.mindfulSession), HKObjectType.workoutType(),
    ]

    func authorize() async throws {
        guard HKHealthStore.isHealthDataAvailable() else { return }
        try await store.requestAuthorization(toShare: [], read: types)
    }

    static let dayFmt: DateFormatter = {
        let f = DateFormatter(); f.calendar = Calendar(identifier: .gregorian); f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"; return f
    }()

    /// Totals for the last `days` days (today included). Sleep is credited to the morning you woke up.
    func totals(days: Int = 7) async -> [DayTotals] {
        let cal = Calendar.current
        let today = cal.startOfDay(for: Date())
        let start = cal.date(byAdding: .day, value: -(days - 1), to: today)!
        var out: [String: DayTotals] = [:]
        for i in 0..<days {
            let d = cal.date(byAdding: .day, value: i, to: start)!
            let k = Self.dayFmt.string(from: d)
            out[k] = DayTotals(date: k)
        }
        let key = { (d: Date) in Self.dayFmt.string(from: cal.startOfDay(for: d)) }

        // Steps: one statistics bucket per day (de-duplicates iPhone + Watch).
        let stepsQ = HKStatisticsCollectionQueryDescriptor(
            predicate: .quantitySample(type: HKQuantityType(.stepCount), predicate: HKQuery.predicateForSamples(withStart: start, end: nil)),
            options: .cumulativeSum, anchorDate: start, intervalComponents: DateComponents(day: 1))
        if let coll = try? await stepsQ.result(for: store) {
            coll.enumerateStatistics(from: start, to: Date()) { s, _ in
                if let v = s.sumQuantity()?.doubleValue(for: .count()) { out[key(s.startDate)]?.steps = v.rounded() }
            }
        }

        // Sleep: asleep intervals from 18:00 the evening before; overlapping sources merged.
        let asleep: Set<Int> = [HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue, HKCategoryValueSleepAnalysis.asleepCore.rawValue,
                                HKCategoryValueSleepAnalysis.asleepDeep.rawValue, HKCategoryValueSleepAnalysis.asleepREM.rawValue]
        let sleepFrom = cal.date(byAdding: .hour, value: -6, to: start)!
        let sleepQ = HKSampleQueryDescriptor(predicates: [.categorySample(type: HKCategoryType(.sleepAnalysis),
            predicate: HKQuery.predicateForSamples(withStart: sleepFrom, end: nil))], sortDescriptors: [SortDescriptor(\.startDate)])
        if let samples = try? await sleepQ.result(for: store) {
            var merged: [(Date, Date)] = []
            for s in samples where asleep.contains(s.value) {
                if let last = merged.last, s.startDate <= last.1 { merged[merged.count - 1].1 = max(last.1, s.endDate) }
                else { merged.append((s.startDate, s.endDate)) }
            }
            for (a, b) in merged {
                let wake = cal.date(byAdding: .hour, value: 6, to: b)!      // a nap at 15:00 and a night ending 07:00 both land "today"
                let k = key(wake)
                if var d = out[k] { d.sleep_h = (((d.sleep_h ?? 0) + b.timeIntervalSince(a) / 3600) * 100).rounded() / 100; out[k] = d }
            }
        }

        // Mindful minutes.
        let mindQ = HKSampleQueryDescriptor(predicates: [.categorySample(type: HKCategoryType(.mindfulSession),
            predicate: HKQuery.predicateForSamples(withStart: start, end: nil))], sortDescriptors: [])
        if let samples = try? await mindQ.result(for: store) {
            for s in samples {
                let k = key(s.startDate)
                guard var d = out[k] else { continue }
                d.mindful_min = ((d.mindful_min ?? 0) + s.endDate.timeIntervalSince(s.startDate) / 60).rounded()
                out[k] = d
            }
        }

        // Workouts.
        let woQ = HKSampleQueryDescriptor(predicates: [.workout(HKQuery.predicateForSamples(withStart: start, end: nil))], sortDescriptors: [])
        if let ws = try? await woQ.result(for: store) {
            for w in ws {
                let k = key(w.startDate)
                guard var d = out[k] else { continue }
                let mins = (w.duration / 60).rounded()
                d.workout_min = (d.workout_min ?? 0) + mins
                var item = ["type": w.workoutActivityType.name, "min": String(Int(mins))]
                if let km = w.statistics(for: HKQuantityType(.distanceWalkingRunning))?.sumQuantity()?.doubleValue(for: .meterUnit(with: .kilo)) {
                    item["km"] = String(format: "%.2f", km)
                }
                d.workouts = (d.workouts ?? []) + [item]
                out[k] = d
            }
        }
        return out.values.sorted { $0.date > $1.date }
    }
}

extension HKWorkoutActivityType {
    var name: String {
        switch self {
        case .running: "Run"; case .walking: "Walk"; case .cycling: "Ride"; case .yoga: "Yoga"; case .swimming: "Swim"
        case .traditionalStrengthTraining, .functionalStrengthTraining: "Strength"; case .hiking: "Hike"
        case .highIntensityIntervalTraining: "HIIT"; case .mindAndBody: "Mind & body"
        default: "Workout"
        }
    }
}

// MARK: - Sync

@MainActor
final class Sync: ObservableObject {
    static let shared = Sync()
    @Published var days: [DayTotals] = []
    @Published var status = "Not synced yet"
    @Published var ok: Bool? = nil
    @Published var busy = false
    @AppStorage("lastSync") var lastSync: Double = 0
    @AppStorage("goodEndpoint") var goodEndpoint: String = ""

    func run(reason: String = "manual") async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do { try await Health.shared.authorize() } catch { status = "Health access wasn't granted"; ok = false; return }
        days = await Health.shared.totals()
        guard !Config.key.isEmpty, !Config.endpoints.isEmpty else { status = "Missing Mac address — rebuild from the Mac"; ok = false; return }
        var sent = 0
        var lastErr = ""
        let order = ([goodEndpoint] + Config.endpoints).filter { !$0.isEmpty }
        endpoints: for ep in NSOrderedSet(array: order).array as! [String] {
            sent = 0
            for d in days {
                do { try await post(d, to: ep); sent += 1 } catch { lastErr = error.localizedDescription; continue endpoints }
            }
            goodEndpoint = ep
            break
        }
        if sent == days.count && sent > 0 {
            lastSync = Date().timeIntervalSince1970
            ok = true
            status = "Sent \(sent) days to \(Config.macName)"
        } else {
            ok = false
            status = "Couldn't reach \(Config.macName). Is Alibi running and are you on the same Wi-Fi (or Tailscale)? \(lastErr)"
        }
    }

    func post(_ d: DayTotals, to ep: String) async throws {
        var req = URLRequest(url: URL(string: ep)!, timeoutInterval: 8)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue(Config.key, forHTTPHeaderField: "X-Alibi-Secret")
        req.httpBody = try JSONSerialization.data(withJSONObject: [
            "source": "health", "kind": "samples", "payload": try JSONSerialization.jsonObject(with: JSONEncoder().encode(d)),
        ])
        let (data, resp) = try await URLSession.shared.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard code == 200 else {
            throw NSError(domain: "Alibi", code: code, userInfo: [NSLocalizedDescriptionKey:
                code == 401 ? "The key doesn't match — rebuild the app from the Mac." : "HTTP \(code) \(String(data: data, encoding: .utf8)?.prefix(80) ?? "")"])
        }
    }

    // Background: Health wakes us when new steps/sleep land; BGTask as a fallback every few hours.
    nonisolated static func registerBackground() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: bgTaskID, using: nil) { task in
            scheduleRefresh()
            let t = Task { await Sync.shared.run(reason: "bgtask"); task.setTaskCompleted(success: true) }
            task.expirationHandler = { t.cancel() }
        }
        let store = Health.shared.store
        for type in [HKQuantityType(.stepCount), HKCategoryType(.sleepAnalysis)] as [HKSampleType] {
            let q = HKObserverQuery(sampleType: type, predicate: nil) { _, done, _ in
                Task { await Sync.shared.run(reason: "observer"); done() }
            }
            store.execute(q)
            store.enableBackgroundDelivery(for: type, frequency: .hourly) { _, _ in }
        }
    }

    nonisolated static func scheduleRefresh() {
        let r = BGAppRefreshTaskRequest(identifier: bgTaskID)
        r.earliestBeginDate = Date(timeIntervalSinceNow: 3 * 3600)
        try? BGTaskScheduler.shared.submit(r)
    }
}

// MARK: - UI

@main
struct AlibiPhoneApp: App {
    init() { Sync.registerBackground(); Sync.scheduleRefresh() }
    var body: some Scene { WindowGroup { HomeView().preferredColorScheme(.dark) } }
}

struct HomeView: View {
    @StateObject var sync = Sync.shared
    @Environment(\.scenePhase) var phase

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack(spacing: 8) {
                    Text("Alibi").font(.system(size: 34, weight: .bold))
                    Circle().fill(green).frame(width: 9, height: 9).offset(y: 9)
                    Spacer()
                }
                Text("Sends your daily Health totals to Alibi on \(Config.macName), so it can check your steps, sleep and meditation habits.")
                    .font(.subheadline).foregroundStyle(ink)

                HStack(alignment: .top, spacing: 10) {
                    Circle().fill(sync.ok == nil ? ink : sync.ok! ? green : Color(red: 0.9, green: 0.28, blue: 0.3))
                        .frame(width: 10, height: 10).padding(.top, 5)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(sync.busy ? "Syncing…" : sync.status).font(.headline)
                        if sync.lastSync > 0 {
                            Text("Last sync \(Date(timeIntervalSince1970: sync.lastSync).formatted(date: .omitted, time: .shortened))")
                                .font(.caption).foregroundStyle(ink)
                        }
                    }
                }
                .padding(16).frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 16).fill(Color(white: 0.1)))

                Button { Task { await sync.run() } } label: {
                    Text(sync.busy ? "Syncing…" : "Sync now").font(.headline).foregroundStyle(.black)
                        .frame(maxWidth: .infinity).padding(.vertical, 15)
                        .background(RoundedRectangle(cornerRadius: 14).fill(green))
                }.disabled(sync.busy)

                if !sync.days.isEmpty {
                    Text("LAST 7 DAYS").font(.caption.weight(.semibold)).foregroundStyle(ink).padding(.top, 6)
                    VStack(spacing: 0) {
                        ForEach(sync.days) { d in
                            HStack {
                                Text(label(d.date)).font(.subheadline.weight(.medium)).frame(width: 70, alignment: .leading)
                                stat(d.steps.map { "\(Int($0).formatted())" }, "steps")
                                stat(d.sleep_h.map { String(format: "%.1f", $0) }, "h sleep")
                                stat(d.mindful_min.map { "\(Int($0))" }, "min calm")
                                stat(d.workout_min.map { "\(Int($0))" }, "min move")
                            }
                            .padding(.vertical, 11)
                            Divider().background(Color(white: 0.2))
                        }
                    }
                }
                Text("Only daily totals leave this phone, and only to your own Mac. Alibi never writes to Health.")
                    .font(.caption).foregroundStyle(ink).padding(.top, 8)
            }
            .padding(22)
        }
        .background(Color.black.ignoresSafeArea())
        .task { await sync.run(reason: "open") }
        .onChange(of: phase) { _, p in if p == .active { Task { await sync.run(reason: "foreground") } } }
    }

    func label(_ iso: String) -> String {
        guard let d = Health.dayFmt.date(from: iso) else { return iso }
        if Calendar.current.isDateInToday(d) { return "Today" }
        if Calendar.current.isDateInYesterday(d) { return "Yesterday" }
        return d.formatted(.dateTime.weekday(.abbreviated).day())
    }

    func stat(_ v: String?, _ unit: String) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(v ?? "—").font(.subheadline.monospacedDigit()).foregroundStyle(v == nil ? ink : .white)
            Text(unit).font(.caption2).foregroundStyle(ink)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}
