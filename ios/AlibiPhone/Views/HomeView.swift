// The app root (AlibiPhoneApp instantiates `HomeView`): three tabs on the system tab bar (its default glass, nothing
// custom): Today (the live mirror), Week and Health. The root also owns the onboarding sheet, the foreground
// `phone.app` rows, and when the mirror polls (foreground only).
import SwiftUI

struct HomeView: View {
    @StateObject private var sync = SyncEngine.shared
    @StateObject private var perms = Permissions.shared
    @StateObject private var st = ScreenTimeShield.shared
    @StateObject private var mirror = MirrorClient.shared
    @Environment(\.scenePhase) private var phase
    @AppStorage("onboarded", store: Store.d) private var onboarded = false
    @State private var showOnboarding = false
    @State private var tab = Tab.today

    enum Tab: Hashable { case today, week, health }

    var body: some View {
        TabView(selection: $tab) {
            TodayView(mirror: mirror)
                .tabItem { Label("Today", systemImage: "clock") }
                .tag(Tab.today)
            WeekView(mirror: mirror)
                .tabItem { Label("Week", systemImage: "calendar") }
                .tag(Tab.week)
            HealthView(mirror: mirror, showOnboarding: $showOnboarding)
                .tabItem { Label("Health", systemImage: "heart") }
                .tag(Tab.health)
        }
        .tint(Alibi.ui.accentInk)
        .sensoryFeedback(.selection, trigger: tab)
        .sheet(isPresented: $showOnboarding, onDismiss: {
            onboarded = true
            Task { await perms.refresh(); if !MirrorClient.demo { await sync.run(reason: "onboarded") } }
        }) {
            OnboardingView(done: { showOnboarding = false })
        }
        .task {
            #if DEBUG
            if let t = UserDefaults.standard.string(forKey: "AlibiTab") { tab = t == "week" ? .week : t == "health" ? .health : .today }
            #endif
            mirror.setActive(phase == .active)
            if MirrorClient.demo { return }                 // demo screenshots never touch the Mac or the permission sheet
            await perms.refresh()
            st.ensureMonitoring()
            if !onboarded { showOnboarding = true } else { await sync.run(reason: "open") }
        }
        .onChange(of: phase) { _, p in
            mirror.setActive(p == .active)
            if MirrorClient.demo { return }
            sync.setForeground(p == .active)
            if p == .active {
                if Store.enabled("app") { SyncEngine.shared.enqueue([row("phone", "app", ["opened": true, "reason": "foreground"])], stream: "app") }
                st.refresh()
                Task { await perms.refresh(); await sync.runAuto(reason: "foreground") }
            } else if p == .background, Store.enabled("app") {
                SyncEngine.shared.enqueue([row("phone", "app", ["opened": false, "reason": "background"])], stream: "app")
            }
        }
    }
}
