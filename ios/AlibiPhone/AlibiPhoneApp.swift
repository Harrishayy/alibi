// Alibi for iPhone — streams Health, heart rate, motion/pickups, home geofence and Focus state to Alibi on your Mac so
// it can check whether you're really doing the work. Files:
//   Config.swift            addresses/key (Generated/AlibiConfig.plist), App Group defaults, formatters
//   Sensors/                Health, Motion, HomeLocation collectors
//   Sync/                   SyncEngine (cursors, outbox, batch POST, backoff, session polling, background), Snapshot
//   Focus/                  "Alibi session" Focus filter
//   ScreenTime/             Screen Time: picked apps, usage thresholds, Opal-style blocking (+ ../Shared, extensions)
//   Views/                  Home, onboarding, theme
import SwiftUI

@main
struct AlibiPhoneApp: App {
    init() {
        Shields.current = ScreenTimeShield.shared               // Opal-style blocking during sessions
        ScreenTimeShield.shared.ensureMonitoring()               // daily 5-min usage thresholds for picked apps
        SyncEngine.registerBackground()
        SyncEngine.scheduleBackground()
        HomeLocation.shared.startListening()                    // geofence events relaunch us in the background
    }

    var body: some Scene {
        WindowGroup { HomeView().preferredColorScheme(.dark).tint(Palette.accent) }
    }
}
