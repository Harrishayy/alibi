// Alibi Island — entry point. Swift only allows top-level code in main.swift, so the island's argument parsing
// (--act, --snapshot) and the app run loop live here; everything else is in Island.swift and native/shared/.
import AppKit

let args = CommandLine.arguments
func arg(_ k: String) -> String? { args.firstIndex(of: k).flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil } }
if let label = arg("--act") {
    Task { @MainActor in await actOnce(label); exit(0) }
    RunLoop.main.run()
} else if let dir = arg("--snapshot") {
    Task { @MainActor in await snapshot(to: dir, stateFile: arg("--state"), prefix: arg("--prefix") ?? ""); exit(0) }
    RunLoop.main.run()
} else {
    // Inside Alibi.app: own the daemon's lifetime (start it if nothing answers, stop it when we quit).
    if Bundle.main.url(forResource: "root", withExtension: "txt") != nil, let root = repoRoot {
        DaemonOwner.shared.start(root: root)
    }
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    let controller = MainActor.assumeIsolated { Controller() }
    MainActor.assumeIsolated { controller.start() }
    app.run()
}
