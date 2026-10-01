// Shared between the Alibi app and its Screen Time extensions (DeviceActivity monitor, shield configuration, shield
// action). Extensions can't network reliably, so they only write small rows into the App Group; the app ships them to
// the Mac as phone.screentime / phone.shield on its next sync (docs/SIGNALS.md).
import DeviceActivity
import FamilyControls
import Foundation
import ManagedSettings

enum AlibiShared {
    static let group = "group.app.theultras.alibi"
    static var defaults: UserDefaults { UserDefaults(suiteName: group) ?? .standard }

    static let queueKey = "st.queue"                  // [{source, kind, ts, payload}] waiting for the app to ship
    static let selectionKey = "st.selection"          // JSON-encoded FamilyActivitySelection
    static let todayDayKey = "st.today.day"           // "yyyy-MM-dd" the minutes below belong to
    static let todayMinKey = "st.today.min"           // cumulative minutes on picked apps today
    static let todayTsKey = "st.today.ts"
    static let shieldOnKey = "shield.on"
    static let shieldAppsKey = "shield.apps"
    static let shieldSourcesKey = "shield.sources"    // why blocking is on: session / focus / manual
    static let habitKey = "session.habit"             // shown on the shield ("Alibi says: you said drawing")

    /// Threshold events: every 5 min of the picked apps, up to 2 h a day.
    static let stepMin = 5
    static let maxMin = 120
    static let pickedLabel = "Picked apps"

    static func today(_ d: Date = Date()) -> String {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"
        return f.string(from: d)
    }

    // MARK: queue (extension → app)

    static func push(kind: String, payload: [String: Any], ts: Double = Date().timeIntervalSince1970) {
        let d = defaults
        var q = d.array(forKey: queueKey) as? [[String: Any]] ?? []
        q.append(["source": "phone", "kind": kind, "ts": ts, "payload": payload])
        if q.count > 500 { q.removeFirst(q.count - 500) }
        d.set(q, forKey: queueKey)
    }

    /// Takes everything queued so far. Rows an extension adds while this runs stay queued for next time.
    static func drain() -> [[String: Any]] {
        let d = defaults
        let q = d.array(forKey: queueKey) as? [[String: Any]] ?? []
        guard !q.isEmpty else { return [] }
        let now = d.array(forKey: queueKey) as? [[String: Any]] ?? []
        d.set(Array(now.dropFirst(min(q.count, now.count))), forKey: queueKey)
        return q
    }

    // MARK: usage (written by the monitor extension)

    /// Records "picked apps reached `minutes` today". Duplicate or lower thresholds the same day are ignored, so a
    /// monitor restart that replays past thresholds doesn't double count. Returns whether a row was queued.
    @discardableResult
    static func recordUsage(minutes: Int, at ts: Double = Date().timeIntervalSince1970) -> Bool {
        let d = defaults
        let day = today(Date(timeIntervalSince1970: ts))
        let prev = d.string(forKey: todayDayKey) == day ? d.integer(forKey: todayMinKey) : 0
        guard minutes > prev else { return false }
        d.set(day, forKey: todayDayKey)
        d.set(minutes, forKey: todayMinKey)
        d.set(ts, forKey: todayTsKey)
        push(kind: "screentime", payload: ["app": pickedLabel, "minutes": minutes, "threshold_min": stepMin], ts: ts)
        return true
    }

    /// Starts a new day's count — only when the stored minutes belong to an earlier day. A mid-day monitoring restart
    /// (re-picking apps) also fires intervalDidStart and then replays every threshold already reached today; keeping
    /// today's floor makes recordUsage() ignore those replays instead of queueing them as fresh minutes stamped "now".
    /// Returns whether it reset.
    @discardableResult
    static func resetDay(now: Date = Date()) -> Bool {
        let d = defaults
        guard d.string(forKey: todayDayKey) != today(now) else { return false }
        d.set(today(now), forKey: todayDayKey)
        d.set(0, forKey: todayMinKey)
        return true
    }

    static var minutesToday: Int {
        let d = defaults
        return d.string(forKey: todayDayKey) == today() ? d.integer(forKey: todayMinKey) : 0
    }

    // MARK: selection

    static func loadSelection() -> FamilyActivitySelection {
        guard let data = defaults.data(forKey: selectionKey),
              let s = try? JSONDecoder().decode(FamilyActivitySelection.self, from: data) else { return FamilyActivitySelection() }
        return s
    }

    static func saveSelection(_ s: FamilyActivitySelection) {
        if let data = try? JSONEncoder().encode(s) { defaults.set(data, forKey: selectionKey) }
    }

    static func count(_ s: FamilyActivitySelection) -> Int {
        s.applicationTokens.count + s.categoryTokens.count + s.webDomainTokens.count
    }

    // MARK: shield

    /// Removes blocking and records phone.shield {on: false} if it was on. Used by the app and by the monitor's
    /// failsafe (so a missed "session ended" never leaves apps blocked).
    static func clearShield() {
        ManagedSettingsStore(named: .alibi).clearAllSettings()
        let d = defaults
        d.set([String](), forKey: shieldSourcesKey)
        guard d.bool(forKey: shieldOnKey) else { return }
        d.set(false, forKey: shieldOnKey)
        push(kind: "shield", payload: ["on": false, "apps": 0])
    }
}

extension ManagedSettingsStore.Name {
    static let alibi = Self("alibi")
}

extension DeviceActivityName {
    /// 00:00–23:59 every day; carries the 5-minute threshold events.
    static let alibiDaily = Self("alibi.daily")
    /// One-off window that ends shortly after the session; its end clears the shield if the app never got to.
    static let alibiShieldFailsafe = Self("alibi.shield")
}

extension DeviceActivityEvent.Name {
    static func picked(_ minutes: Int) -> Self { Self("picked.\(minutes)") }
    /// Minutes encoded in a "picked.N" event name.
    var pickedMinutes: Int? {
        let s = rawValue
        guard s.hasPrefix("picked.") else { return nil }
        return Int(s.dropFirst("picked.".count))
    }
}
