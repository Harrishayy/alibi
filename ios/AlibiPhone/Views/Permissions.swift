// Permission states shown in the Streams list and requested in sequence by onboarding.
import CoreMotion
import Foundation

@MainActor
final class Permissions: ObservableObject {
    static let shared = Permissions()
    @Published var healthAsked = false
    @Published var bgError: String?
    @Published var motion: CMAuthorizationStatus = CMMotionActivityManager.authorizationStatus()

    func refresh() async {
        healthAsked = await Health.shared.asked()
        if healthAsked { Health.shared.startObservers() }   // idempotent; covers access granted from the Health app
        bgError = Store.d.string(forKey: Health.bgErrorKey)
        motion = Motion.shared.status
    }

    func requestHealth() async {
        do {
            try await Health.shared.authorize()
            Health.shared.startObservers()               // launch skipped them (no permission yet): register now
        } catch {
            Store.set("Health request failed: \(error.localizedDescription)", Health.bgErrorKey)
        }
        await refresh()
    }

    func requestMotion() async {
        await Motion.shared.authorize()
        await refresh()
    }

    var healthText: String {
        if !Health.shared.available { return "Not available on this device" }
        if let bgError { return bgError }
        return healthAsked ? "Asked · manage in Health → Sharing → Apps" : "Not asked yet"
    }
    var healthTone: Tone { !Health.shared.available ? .bad : bgError != nil ? .bad : healthAsked ? .good : .neutral }

    var motionText: String {
        if !Motion.shared.available { return "Not available on this device" }
        switch motion {
        case .authorized: return "Allowed"
        case .denied, .restricted: return "Off — Settings → Alibi → Motion & Fitness"
        default: return "Not asked yet"
        }
    }
    var motionTone: Tone {
        switch motion { case .authorized: .good; case .denied, .restricted: .bad; default: .neutral }
    }
}
