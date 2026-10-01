import FamilyControls
import SwiftUI

struct HomeView: View {
    @StateObject private var sync = SyncEngine.shared
    @StateObject private var snap = Snapshot.shared
    @StateObject private var perms = Permissions.shared
    @StateObject private var home = HomeLocation.shared
    @StateObject private var focus = FocusState.shared
    @StateObject private var st = ScreenTimeShield.shared
    @State private var picking = false
    @State private var draft = FamilyActivitySelection()
    @Environment(\.scenePhase) private var phase
    @AppStorage("onboarded", store: Store.d) private var onboarded = false
    @State private var showOnboarding = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                header
                if let s = sync.session, s.active { sessionBanner(s) }
                statusCard
                Button { Task { await sync.run(reason: "manual", full: true) } } label: {
                    Text(sync.busy ? "Syncing…" : "Sync now")
                }.buttonStyle(PrimaryButtonStyle()).disabled(sync.busy)

                SectionLabel(text: "Streams").padding(.top, 6)
                streams
                SectionLabel(text: "Screen Time").padding(.top, 6)
                screenTimeCard
                SectionLabel(text: "Home").padding(.top, 6)
                homeCard
                if !snap.days.isEmpty {
                    SectionLabel(text: "Last 7 days").padding(.top, 6)
                    WeekCard(days: snap.days)
                }
                Text("Only what's listed above leaves this phone, and only to your own Mac. Home is a yes/no — your location never leaves the phone. Screen Time sends minutes only, never app names. No message text, no app contents. Alibi never writes to Health.")
                    .font(.caption).foregroundStyle(Palette.muted).padding(.top, 6)
                Button("Review permissions") { showOnboarding = true }
                    .font(.footnote.weight(.semibold)).foregroundStyle(Palette.accentInk)
            }
            .padding(20)
        }
        .background(Color.black.ignoresSafeArea())
        .familyActivityPicker(headerText: "Pick your distracting apps", isPresented: $picking,
                              selection: $draft)
        .onChange(of: picking) { _, open in
            if open { draft = st.selection } else if draft != st.selection { st.save(draft) }
        }
        .sheet(isPresented: $showOnboarding, onDismiss: { onboarded = true; Task { await perms.refresh(); await sync.run(reason: "onboarded") } }) {
            OnboardingView(done: { showOnboarding = false })
        }
        .task {
            await perms.refresh()
            st.ensureMonitoring()
            if !onboarded { showOnboarding = true } else { await sync.run(reason: "open") }
        }
        .onChange(of: phase) { _, p in
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

    private var header: some View {
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            Text("Alibi").font(.system(size: 34, weight: .semibold, design: .serif))
            Circle().fill(Palette.accent).frame(width: 8, height: 8)
            Spacer()
        }
    }

    private func sessionBanner(_ s: SessionInfo) -> some View {
        HStack(spacing: 10) {
            Dot(tone: .good, size: 10)
            VStack(alignment: .leading, spacing: 2) {
                Text("Session live\(s.habit.map { " · \($0)" } ?? "")").font(.subheadline.weight(.semibold))
                Text("Syncing every \(Int(s.every / 60)) min\(s.endsAt.map { " · ends \($0.formatted(date: .omitted, time: .shortened))" } ?? "")\(focus.on ? " · Focus on" : "")")
                    .font(.caption).foregroundStyle(Palette.muted)
            }
            Spacer()
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 14, style: .continuous).fill(Palette.accent.opacity(0.14)))
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(Palette.accent.opacity(0.5), lineWidth: 1))
    }

    private var statusCard: some View {
        Card {
            HStack(alignment: .top, spacing: 10) {
                Dot(tone: sync.ok == nil ? .neutral : sync.ok! ? .good : .bad, size: 10).padding(.top, 5)
                VStack(alignment: .leading, spacing: 4) {
                    Text(Config.macName).font(.system(.title3, design: .serif).weight(.semibold))
                    Text(sync.busy ? "Syncing…" : sync.status).font(.subheadline).foregroundStyle(sync.ok == false ? Palette.bad : .white)
                    HStack(spacing: 12) {
                        Text("Last sync \(Fmt.ago(sync.lastSync))")
                        if sync.pending > 0 { Text("\(sync.pending) waiting") }
                    }.font(.caption).foregroundStyle(Palette.muted)
                }
            }
        }
    }

    private var streams: some View {
        Card {
            StreamRow(id: "health", icon: "heart.text.square", title: "Health",
                      value: healthValue, perm: perms.healthText, tone: perms.healthTone)
            Divider().overlay(Palette.hairline)
            StreamRow(id: "heart", icon: "waveform.path.ecg", title: "Heart rate",
                      value: snap.heart.map { "\(Int($0.bpm)) bpm · \(Fmt.ago($0.at))" } ?? "No reading yet",
                      perm: perms.healthText, tone: perms.healthTone)
            Divider().overlay(Palette.hairline)
            StreamRow(id: "motion", icon: "figure.walk", title: "Motion & pickups",
                      value: motionValue, perm: perms.motionText, tone: perms.motionTone, also: ["pickup"])
            Divider().overlay(Palette.hairline)
            StreamRow(id: "location", icon: "house", title: "At home",
                      value: home.atHome.map { $0 ? "At home" : "Away" } ?? "Home not set",
                      perm: home.permissionText, tone: home.tone)
            Divider().overlay(Palette.hairline)
            StreamRow(id: "focus", icon: "moon.circle", title: "Alibi Focus",
                      value: focus.configured ? (focus.on ? "On" : "Off") : "Not added to a Focus yet",
                      perm: focus.configured ? "Filter added" : "Settings → Focus → Alibi → Add Filter",
                      tone: focus.configured ? .good : .neutral)
            Divider().overlay(Palette.hairline)
            StreamRow(id: "screentime", icon: "hourglass", title: st.name,
                      value: st.valueText, perm: st.permissionText, tone: st.tone, also: ["shield"])
        }
    }

    private var healthValue: String {
        var bits: [String] = []
        if let s = snap.stepsToday { bits.append("\(Int(s).formatted()) steps today") }
        if let h = snap.sleepLastNight { bits.append(String(format: "%.1f h sleep", h) + (snap.bedWake.map { " (\($0))" } ?? "")) }
        return bits.isEmpty ? "No data yet" : bits.joined(separator: " · ")
    }

    private var motionValue: String {
        var bits: [String] = []
        if let m = snap.motionNow { bits.append("\(m.state.capitalized) since \(m.since.formatted(date: .omitted, time: .shortened))") }
        bits.append("\(Motion.pickupsToday) pickups today")
        return bits.joined(separator: " · ")
    }

    private var screenTimeCard: some View {
        Card {
            Text(st.auth == .approved
                 ? "Alibi counts every 5 minutes you spend in your picked apps, and blocks them while a session is on — tapping a blocked app shows what you said you'd be doing."
                 : "Pick the apps that pull you away. Alibi counts the minutes you spend in them and blocks them while a session is on. App names never leave this phone — your Mac only hears minutes.")
                .font(.subheadline).foregroundStyle(Palette.muted)
            if let m = st.message { Text(m).font(.footnote).foregroundStyle(.white) }
            if st.auth != .approved {
                Button { Task { await st.requestAuthorization(); if st.auth == .approved { picking = true } } } label: {
                    Text("Allow Screen Time")
                }.buttonStyle(PrimaryButtonStyle())
            } else {
                Button { picking = true } label: {
                    Text(st.picked > 0 ? "Change distracting apps (\(st.picked))" : "Pick your distracting apps")
                }.buttonStyle(SecondaryButtonStyle())
                if st.picked > 0 {
                    Button { st.apply(on: !st.manualOn, source: "manual") } label: {
                        Text(st.manualOn ? "Stop test block" : st.shieldOn ? "Blocking for the session" : "Test the block now")
                    }.buttonStyle(SecondaryButtonStyle()).disabled(st.shieldOn && !st.manualOn)
                }
            }
        }
    }

    private var homeCard: some View {
        Card {
            Text(home.homeSet ? "Alibi knows when you leave or get home — handy for gym and walk habits, and to spot when you're away from your desk during a session."
                 : "Stand at home and tap below. Alibi saves a \(Int(HomeLocation.radius)) m circle on this phone and only ever tells your Mac \"at home: yes/no\".")
                .font(.subheadline).foregroundStyle(Palette.muted)
            if home.auth == .authorizedWhenInUse {
                Text("To notice arrivals while Alibi is closed, iOS needs Location set to **Always**: Settings → Alibi → Location → Always.")
                    .font(.footnote).foregroundStyle(Palette.partial)
            }
            if let m = home.message { Text(m).font(.footnote).foregroundStyle(.white) }
            Button { Task { await home.setHomeHere() } } label: {
                Text(home.busy ? "Finding you…" : home.homeSet ? "Move home to here" : "Set this as home")
            }.buttonStyle(SecondaryButtonStyle()).disabled(home.busy)
        }
    }
}

struct StreamRow: View {
    let id: String
    let icon: String
    let title: String
    let value: String
    let perm: String
    let tone: Tone
    var also: [String] = []
    @State private var on = true

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon).font(.system(size: 18)).foregroundStyle(Palette.accent).frame(width: 26).padding(.top, 2)
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(.subheadline.weight(.semibold))
                Text(value).font(.subheadline.monospacedDigit()).foregroundStyle(.white.opacity(0.9))
                HStack(spacing: 6) {
                    Dot(tone: tone, size: 6)
                    Text(perm).lineLimit(1)
                    Text("· sent \(Fmt.ago(([id] + also).compactMap(Store.lastSent).max()))").lineLimit(1)
                }.font(.caption).foregroundStyle(Palette.muted)
            }
            Spacer(minLength: 4)
            Toggle("", isOn: $on).labelsHidden().tint(Palette.accent)
                .onChange(of: on) { _, v in ([id] + also).forEach { Store.setEnabled($0, v) } }
        }
        .onAppear { on = Store.enabled(id) }
    }
}

struct WeekCard: View {
    let days: [[String: Any]]
    var body: some View {
        Card {
            ForEach(days.indices, id: \.self) { i in
                let d = days[i]
                HStack {
                    Text(label(d["date"] as? String ?? "")).font(.subheadline.weight(.medium)).frame(width: 74, alignment: .leading)
                    stat((d["steps"] as? Double).map { Int($0).formatted() }, "steps")
                    stat((d["sleep_h"] as? Double).map { String(format: "%.1f", $0) }, "h sleep")
                    stat((d["resting_hr"] as? Double).map { "\(Int($0))" }, "rest bpm")
                    stat((d["workout_min"] as? Double).map { "\(Int($0))" }, "min move")
                }
            }
        }
    }

    func label(_ iso: String) -> String {
        guard let d = Fmt.day.date(from: iso) else { return iso }
        if Calendar.current.isDateInToday(d) { return "Today" }
        if Calendar.current.isDateInYesterday(d) { return "Yesterday" }
        return d.formatted(.dateTime.weekday(.abbreviated).day())
    }

    func stat(_ v: String?, _ unit: String) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(v ?? "—").font(.subheadline.monospacedDigit()).foregroundStyle(v == nil ? Palette.dim : .white)
            Text(unit).font(.caption2).foregroundStyle(Palette.muted)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}
