// Screen Time via Apple's Family Controls (individual authorization — you manage your own phone):
//   • FamilyActivityPicker → "your distracting apps", saved in the App Group so the extensions can see it.
//   • DeviceActivity daily schedule with an event every 5 min of those apps (5…120). The monitor extension
//     (AlibiActivityMonitor) writes {minutes, ts} to the App Group; drainExtension() ships them as phone.screentime.
//   • ManagedSettingsStore shields while an Alibi session (or the Alibi Focus) is on; phone.shield {on, apps}.
//   • A one-off DeviceActivity window that ends a little after the session: if the app never hears "session over",
//     the monitor extension unblocks at that point.
import DeviceActivity
import FamilyControls
import Foundation
import ManagedSettings
import SwiftUI

@MainActor
final class ScreenTimeShield: ObservableObject, ShieldController {
    static let shared = ScreenTimeShield()

    let name = "Screen Time"
    @Published private(set) var auth: AuthorizationStatus = AuthorizationCenter.shared.authorizationStatus
    @Published private(set) var selection: FamilyActivitySelection = AlibiShared.loadSelection()
    @Published private(set) var shieldOn: Bool = AlibiShared.defaults.bool(forKey: AlibiShared.shieldOnKey)
    @Published private(set) var minutesToday: Int = AlibiShared.minutesToday
    @Published var message: String?

    @Published private(set) var sources: Set<String> = Set(AlibiShared.defaults.stringArray(forKey: AlibiShared.shieldSourcesKey) ?? [])
    private var failsafeEnd: Date?
    private let store = ManagedSettingsStore(named: .alibi)
    private let center = DeviceActivityCenter()

    var picked: Int { AlibiShared.count(selection) }
    var isReady: Bool { auth == .approved && picked > 0 }
    var manualOn: Bool { sources.contains("manual") }

    // MARK: status

    func refresh() {
        auth = AuthorizationCenter.shared.authorizationStatus
        shieldOn = AlibiShared.defaults.bool(forKey: AlibiShared.shieldOnKey)
        sources = Set(AlibiShared.defaults.stringArray(forKey: AlibiShared.shieldSourcesKey) ?? [])
        minutesToday = AlibiShared.minutesToday
    }

    var permissionText: String {
        switch auth {
        case .approved: return picked > 0 ? "Allowed · \(picked) picked" : "Allowed · pick your apps below"
        case .denied: return "Off — Settings → Screen Time → Apps with Screen Time Access → Alibi"
        default: return "Not asked yet"
        }
    }
    var tone: Tone { auth == .approved ? (picked > 0 ? .good : .partial) : auth == .denied ? .bad : .neutral }

    var valueText: String {
        guard auth == .approved else { return "Not set up" }
        guard picked > 0 else { return "No apps picked yet" }
        let used = "\(minutesToday) min on picked apps today"
        return shieldOn ? "Blocking now · \(used)" : used
    }

    // MARK: setup

    func requestAuthorization() async {
        do {
            try await AuthorizationCenter.shared.requestAuthorization(for: .individual)
            message = nil
        } catch {
            message = "Screen Time access wasn't granted (\(error.localizedDescription)). You can try again any time."
        }
        refresh()
        if isReady { startMonitoring() }
    }

    func save(_ s: FamilyActivitySelection) {
        selection = s
        AlibiShared.saveSelection(s)
        startMonitoring(restart: true)
        if shieldOn { blockPicked() }                                       // keep blocking in step with the new pick
        message = picked > 0 ? "Watching \(picked) pick\(picked == 1 ? "" : "s"). Alibi counts every 5 minutes you spend in them." : nil
    }

    /// Called at launch: make sure the daily schedule exists (iOS keeps it across launches, but not across a reinstall).
    func ensureMonitoring() {
        refresh()
        guard isReady else { return }
        if !center.activities.contains(.alibiDaily) { startMonitoring() }
    }

    func startMonitoring(restart: Bool = false) {
        guard isReady else { center.stopMonitoring([.alibiDaily]); return }
        if restart { center.stopMonitoring([.alibiDaily]) }
        var events: [DeviceActivityEvent.Name: DeviceActivityEvent] = [:]
        for m in stride(from: AlibiShared.stepMin, through: AlibiShared.maxMin, by: AlibiShared.stepMin) {
            events[.picked(m)] = event(minutes: m)
        }
        let schedule = DeviceActivitySchedule(intervalStart: DateComponents(hour: 0, minute: 0, second: 0),
                                              intervalEnd: DateComponents(hour: 23, minute: 59, second: 59), repeats: true)
        do {
            try center.startMonitoring(.alibiDaily, during: schedule, events: events)
        } catch {
            message = "Couldn't start Screen Time tracking: \(error.localizedDescription)"
        }
    }

    private func event(minutes m: Int) -> DeviceActivityEvent {
        let threshold = DateComponents(minute: m)
        if #available(iOS 17.4, *) {
            // Count today's earlier use too, so a restart mid-day doesn't reset the clock (duplicates are ignored).
            return DeviceActivityEvent(applications: selection.applicationTokens, categories: selection.categoryTokens,
                                       webDomains: selection.webDomainTokens, threshold: threshold, includesPastActivity: true)
        }
        return DeviceActivityEvent(applications: selection.applicationTokens, categories: selection.categoryTokens,
                                   webDomains: selection.webDomainTokens, threshold: threshold)
    }

    // MARK: shipping extension rows

    /// Moves rows the extensions wrote (screentime thresholds, failsafe unblocks) into the sync outbox.
    func drainExtension() {
        let rows = AlibiShared.drain()
        refresh()
        let st = rows.filter { ($0["kind"] as? String) == "screentime" }
        let sh = rows.filter { ($0["kind"] as? String) == "shield" }
        if !st.isEmpty, Store.enabled("screentime") { SyncEngine.shared.enqueue(st, stream: "screentime") }
        if !sh.isEmpty, Store.enabled("shield") { SyncEngine.shared.enqueue(sh, stream: "shield") }
    }

    // MARK: blocking

    func apply(on: Bool, source: String) {
        if on { sources.insert(source) } else { sources.remove(source) }
        AlibiShared.defaults.set(Array(sources), forKey: AlibiShared.shieldSourcesKey)
        let want = !sources.isEmpty
        if want {
            guard isReady else {
                if source == "manual" { message = "Allow Screen Time and pick your apps first." }
                return
            }
            if !shieldOn { blockPicked(); post(on: true); failsafeEnd = nil; armFailsafe() }
            else if on && source == "session" { armFailsafe() }        // the session's end time may have moved
        } else if shieldOn {
            store.clearAllSettings()
            center.stopMonitoring([.alibiShieldFailsafe])
            failsafeEnd = nil
            setOn(false)
            post(on: false)
        }
    }

    private func blockPicked() {
        store.shield.applications = selection.applicationTokens.isEmpty ? nil : selection.applicationTokens
        store.shield.applicationCategories = selection.categoryTokens.isEmpty ? nil : .specific(selection.categoryTokens)
        store.shield.webDomains = selection.webDomainTokens.isEmpty ? nil : selection.webDomainTokens
        store.shield.webDomainCategories = selection.categoryTokens.isEmpty ? nil : .specific(selection.categoryTokens)
        setOn(true)
    }

    private func setOn(_ on: Bool) {
        shieldOn = on
        AlibiShared.defaults.set(on, forKey: AlibiShared.shieldOnKey)
        AlibiShared.defaults.set(on ? picked : 0, forKey: AlibiShared.shieldAppsKey)
    }

    private func post(on: Bool) {
        guard Store.enabled("shield") else { return }
        SyncEngine.shared.enqueue([row("phone", "shield", ["on": on, "apps": on ? picked : 0])], stream: "shield")
        SyncEngine.shared.syncInBackground(reason: on ? "shield on" : "shield off")
    }

    /// One-off window ending ~10 min after the session's end (or in 4 h for Focus/manual blocking with no end time).
    /// DeviceActivity windows must be ≥ 15 min, so short sessions get a 16-min window.
    private func armFailsafe() {
        let now = Date()
        let endsAt = SyncEngine.shared.session?.endsAt
        var end = endsAt.map { $0.addingTimeInterval(10 * 60) } ?? now.addingTimeInterval(4 * 3600)
        end = max(end, now.addingTimeInterval(16 * 60))
        if let f = failsafeEnd, endsAt == nil || abs(f.timeIntervalSince(end)) < 60 { return }
        let cal = Calendar.current
        let parts: Set<Calendar.Component> = [.year, .month, .day, .hour, .minute, .second]
        let schedule = DeviceActivitySchedule(intervalStart: cal.dateComponents(parts, from: now),
                                              intervalEnd: cal.dateComponents(parts, from: end), repeats: false)
        do {
            try center.startMonitoring(.alibiShieldFailsafe, during: schedule)
            failsafeEnd = end
        } catch {
            failsafeEnd = nil                                            // blocking still works; just no auto-unblock
        }
    }
}
