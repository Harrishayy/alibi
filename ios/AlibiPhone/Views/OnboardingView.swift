// First-launch walkthrough: one permission per page, in plain language, asked in sequence. Every step can be skipped.
import FamilyControls
import SwiftUI

struct OnboardingView: View {
    var done: () -> Void
    @State private var step = 0
    @State private var working = false
    @StateObject private var home = HomeLocation.shared
    @StateObject private var st = ScreenTimeShield.shared
    @State private var picking = false
    @State private var draft = FamilyActivitySelection()

    private enum Kind { case welcome, health, motion, screenTime, home, focus }
    private struct Page {
        let kind: Kind, icon: String, title: String, body: String, button: String, skippable: Bool
    }

    private var pages: [Page] { [
        Page(kind: .welcome, icon: "checkmark.seal", title: "I'm Pinch. You say what you'll do; I check.",
             body: "Your Mac watches your desk sessions. This phone fills in the rest: sleep, movement, and whether you picked it up mid-session. Everything goes only to Alibi on \(Config.macName).",
             button: "Set it up", skippable: false),
        Page(kind: .health, icon: "heart.text.square", title: "Health",
             body: "Steps, sleep (stages, bed and wake time), resting heart rate, HRV, breathing rate, mindful minutes, daylight, headphone volume, moods you log, workouts, and live heart rate from your Watch. Alibi only reads — it never writes to Health. On the next screen, tap \"Turn On All\".",
             button: "Allow Health", skippable: true),
        Page(kind: .motion, icon: "figure.walk", title: "Motion",
             body: "Whether you're still, walking, driving or cycling, and when you pick the phone up after it's been resting. That's how Alibi notices a \"quick check\" in the middle of a focus session.",
             button: "Allow Motion", skippable: true),
        Page(kind: .screenTime, icon: "hourglass", title: "Screen Time",
             body: "Pick the apps that pull you away — social, video, games. Alibi counts every 5 minutes you spend in them, and blocks them while a session is on (tapping one shows what you said you'd be doing). App names never leave this phone; your Mac only hears minutes. iOS will ask for Screen Time access — tap Continue.",
             button: st.auth == .approved ? (st.picked > 0 ? "Change my apps" : "Pick my apps") : "Allow Screen Time", skippable: true),
        Page(kind: .home, icon: "house", title: "Home, and only home",
             body: "Stand at home and Alibi saves a small circle around it on this phone. Your Mac only ever hears \"at home\" or \"away\" — never where you are. For this to work while Alibi is closed, iOS will ask for \"Always\"; choose \"Change to Always Allow\".",
             button: home.homeSet ? "Home is set" : "I'm home — set it", skippable: true),
        Page(kind: .focus, icon: "moon.circle", title: "Alibi Focus",
             body: "Make a Focus called \"Alibi\" (Settings → Focus → + → Custom → Alibi). Under Focus Filters, tap Add Filter → Alibi → Alibi session and turn on \"Block distracting apps\". Also turn on \"Share Across Devices\". When your Mac starts a session it switches this Focus on, and the phone starts syncing every couple of minutes.",
             button: "Done", skippable: true),
    ] }

    var body: some View {
        let p = pages[step]
        VStack(alignment: .leading, spacing: 20) {
            HStack(spacing: 6) {
                ForEach(pages.indices, id: \.self) { i in
                    Capsule().fill(i <= step ? Alibi.ui.accent : Alibi.ui.surface3).frame(height: 3)
                }
            }.padding(.top, 8)
            Spacer()
            Group {
                if p.kind == .welcome {
                    PinchView(mood: .idle, clip: .hello, clipID: 1, size: 160).accessibilityHidden(true)
                } else {
                    Image(systemName: p.icon).font(.system(size: 40)).foregroundStyle(Alibi.ui.ink)
                        .frame(width: 72, height: 72)
                        .background(RoundedRectangle(cornerRadius: Alibi.Radius.md, style: .continuous).fill(Alibi.ui.surface1))
                        .overlay(RoundedRectangle(cornerRadius: Alibi.Radius.md, style: .continuous)
                            .strokeBorder(Alibi.ui.hairline, lineWidth: 1))
                        .accessibilityHidden(true)
                }
            }
            .id(step)
            .transition(.opacity.combined(with: .scale(scale: 0.96)))
            Text(p.title).font(Alibi.Fonts.iosLargeTitle).foregroundStyle(Alibi.ui.ink)
                .fixedSize(horizontal: false, vertical: true)
            Text(p.body).font(Alibi.Fonts.iosBody).foregroundStyle(Alibi.ui.ink2).fixedSize(horizontal: false, vertical: true)
            if p.kind == .screenTime, let m = st.message { Text(m).font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink) }
            if p.kind == .home, let m = home.message { Text(m).font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink) }
            Spacer()
            Button { Task { await primary() } } label: { Text(working ? "One moment…" : p.button) }
                .buttonStyle(PrimaryButtonStyle()).disabled(working)
            if p.skippable {
                Button("Not now") { next() }.buttonStyle(QuietButtonStyle()).frame(maxWidth: .infinity)
            }
        }
        .padding(Alibi.Space.s6)
        .background(Alibi.ui.bg.ignoresSafeArea())
        .interactiveDismissDisabled(working)
        .familyActivityPicker(headerText: "Pick your distracting apps", isPresented: $picking, selection: $draft)
        .onChange(of: picking) { _, open in
            if open { draft = st.selection; return }
            if draft != st.selection { st.save(draft) }
            next()
        }
    }

    private func next() {
        if step + 1 < pages.count { withAnimation(Alibi.Motion.smooth) { step += 1 } } else { done() }
    }

    private func primary() async {
        working = true
        defer { working = false }
        switch pages[step].kind {
        case .health: await Permissions.shared.requestHealth()
        case .motion: await Permissions.shared.requestMotion()
        case .screenTime:
            if st.auth != .approved { await st.requestAuthorization() }
            if st.auth == .approved { picking = true; return }        // next() runs when the picker closes
        case .home:
            if !home.homeSet { await home.setHomeHere() } else if home.auth != .authorizedAlways { await home.requestAlways() }
            HomeLocation.shared.startListening()
        default: break
        }
        next()
    }
}
