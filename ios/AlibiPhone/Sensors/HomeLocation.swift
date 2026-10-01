// Home geofence → phone.location {at_home}. The user taps "Set this as home" once; only that circle is kept, on this
// phone. No coordinates ever leave the phone — the Mac only learns "at home: yes/no" when you cross the fence.
// CLMonitor relaunches the app in the background on enter/exit, which also triggers an immediate sync.
import CoreLocation
import Foundation
import UIKit

@MainActor
final class HomeLocation: NSObject, ObservableObject, CLLocationManagerDelegate {
    static let shared = HomeLocation()
    private let manager = CLLocationManager()
    private var monitor: CLMonitor?
    private var listening = false
    static let radius: CLLocationDistance = 150

    @Published var auth: CLAuthorizationStatus = .notDetermined
    @Published var atHome: Bool? = Store.d.object(forKey: "home.at") as? Bool
    @Published var homeSet: Bool = Store.d.object(forKey: "home.lat") != nil
    @Published var busy = false
    @Published var message: String?

    override init() {
        super.init()
        manager.delegate = self
        auth = manager.authorizationStatus
    }

    nonisolated func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        let s = m.authorizationStatus
        Task { @MainActor in
            self.auth = s
            self.authWaiters.forEach { $0.resume() }
            self.authWaiters.removeAll()
        }
    }

    private var authWaiters: [CheckedContinuation<Void, Never>] = []
    private func waitForAuthChange() async {
        await withCheckedContinuation { c in authWaiters.append(c) }
    }

    var permissionText: String {
        switch auth {
        case .authorizedAlways: homeSet ? "Always · home set" : "Always · home not set"
        case .authorizedWhenInUse: "Only while open — choose Always"
        case .denied, .restricted: "Off — allow in Settings"
        default: "Not asked yet"
        }
    }

    var tone: Tone {
        switch auth {
        case .authorizedAlways: homeSet ? .good : .partial
        case .authorizedWhenInUse: .partial
        case .denied, .restricted: .bad
        default: .neutral
        }
    }

    /// Step 1 of the polite ask: While Using (needed to read where "home" is).
    func requestWhenInUse() async {
        guard auth == .notDetermined else { return }
        manager.requestWhenInUseAuthorization()
        await waitForAuthChange()
    }

    /// Step 2: Always, so iOS can tell Alibi when you leave/arrive while the app is closed.
    func requestAlways() async {
        guard auth == .authorizedWhenInUse || auth == .notDetermined else { return }
        manager.requestAlwaysAuthorization()
        // iOS may answer later (provisional Always); don't hang the onboarding on it.
        let t = Task { await waitForAuthChange() }
        try? await Task.sleep(for: .seconds(4))
        t.cancel()
    }

    /// Reads one good fix and makes a 150 m circle around it the home fence.
    func setHomeHere() async {
        busy = true; message = nil
        defer { busy = false }
        if auth == .notDetermined { await requestWhenInUse() }
        guard auth == .authorizedWhenInUse || auth == .authorizedAlways else {
            message = "Location is off for Alibi. Settings → Alibi → Location → Always."
            return
        }
        var fix: CLLocation?
        do {
            let deadline = Date().addingTimeInterval(15)
            for try await u in CLLocationUpdate.liveUpdates() {
                if let l = u.location, l.horizontalAccuracy >= 0 {
                    fix = l
                    if l.horizontalAccuracy <= 50 || Date() > deadline { break }
                }
                if Date() > deadline { break }
            }
        } catch {}
        guard let fix else { message = "Couldn't get a location fix. Try again near a window."; return }
        Store.set(fix.coordinate.latitude, "home.lat")
        Store.set(fix.coordinate.longitude, "home.lon")
        homeSet = true
        let mon = await monitorInstance()
        await mon.remove("home")
        await mon.add(CLMonitor.CircularGeographicCondition(center: fix.coordinate, radius: Self.radius), identifier: "home", assuming: .satisfied)
        record(atHome: true)
        startListening()
        message = "Home saved (a \(Int(Self.radius)) m circle, kept only on this phone)."
        if auth != .authorizedAlways { await requestAlways() }
    }

    func clearHome() async {
        await monitorInstance().remove("home")
        Store.set(nil, "home.lat"); Store.set(nil, "home.lon"); Store.set(nil, "home.at")
        homeSet = false; atHome = nil
    }

    private func monitorInstance() async -> CLMonitor {
        if let monitor { return monitor }
        let m = await CLMonitor("AlibiHome")
        monitor = m
        return m
    }

    /// Call at every launch (including background relaunches for region events) to receive enter/exit events.
    func startListening() {
        guard !listening, homeSet else { return }
        listening = true
        Task {
            let mon = await monitorInstance()
            do {
                for try await ev in await mon.events where ev.identifier == "home" {
                    switch ev.state {
                    case .satisfied: record(atHome: true)
                    case .unsatisfied: record(atHome: false)
                    default: break
                    }
                }
            } catch {}
            listening = false
        }
    }

    private func record(atHome now: Bool) {
        guard atHome != now else { return }
        atHome = now
        Store.set(now, "home.at")
        guard Store.enabled("location") else { return }
        SyncEngine.shared.enqueue([row("phone", "location", ["at_home": now])], stream: "location")
        SyncEngine.shared.syncInBackground(reason: now ? "arrived home" : "left home")
    }
}
