// Screen Time / Opal-style blocking. `Shields.current` is the real ScreenTimeShield (ScreenTimeShield.swift), set at
// launch. Callers say *why* they want blocking (`source`): the Mac's session ("session"), the Alibi Focus filter
// ("focus") or the in-app test button ("manual"). Apps stay blocked while any source wants it; the controller posts
// phone.shield {on, apps} itself when blocking actually changes.
import Foundation

@MainActor
protocol ShieldController: AnyObject {
    /// Human name for the Streams list ("Screen Time").
    var name: String { get }
    /// Whether the user has granted Screen Time access and picked apps.
    var isReady: Bool { get }
    /// Turn Opal-style blocking of the picked apps on or off for one reason.
    func apply(on: Bool, source: String)
}

extension ShieldController {
    func apply(on: Bool) { apply(on: on, source: "manual") }
}

/// Does nothing (used before launch wiring, or on devices without Screen Time).
final class NoShield: ShieldController {
    let name = "Screen Time"
    var isReady: Bool { false }
    func apply(on: Bool, source: String) {}
}

@MainActor
enum Shields {
    static var current: ShieldController = NoShield()
}
