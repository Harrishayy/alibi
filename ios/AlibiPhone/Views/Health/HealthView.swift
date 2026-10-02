// Health: what this phone sends to the Mac. The sync card (Mac, connection dot, "Synced 2 min ago", Sync now), the
// last 7 days of daily totals, then the streams, Screen Time and Home settings that used to be the whole app.
// After a manual sync works, Pinch (20pt, beside the status) plays `connected` once.
import FamilyControls
import SwiftUI

struct HealthView: View {
    @ObservedObject var mirror: MirrorClient
    @Binding var showOnboarding: Bool
    @StateObject private var sync = SyncEngine.shared
    @StateObject private var snap = Snapshot.shared
    @StateObject private var perms = Permissions.shared
    @StateObject private var home = HomeLocation.shared
    @StateObject private var focus = FocusState.shared
    @StateObject private var st = ScreenTimeShield.shared
    @State private var picking = false
    @State private var draft = FamilyActivitySelection()
    @State private var connectedID = 0
    @State private var demoSynced: Date?
    @State private var demoBusy = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                ScreenHeader(title: "Health", subtitle: Text("Daily totals from this iPhone, sent to your Mac"))
                    .rise(0)
                syncCard.padding(.top, Alibi.Space.s4).rise(1)

                SectionTitle(text: "Last 7 days").padding(.top, Alibi.Space.s6).rise(2)
                DaysTable(days: snap.days).padding(.top, Alibi.Space.s2).rise(2)
                Text("Sleep in hours, mindful and exercise in minutes. Only these totals leave this phone, and they go to your Mac. Alibi never writes to Health.")
                    .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 10)
                    .rise(3)

                SectionTitle(text: "Streams").padding(.top, Alibi.Space.s8)
                streams.padding(.top, Alibi.Space.s2)
                SectionTitle(text: "Screen Time").padding(.top, Alibi.Space.s6)
                screenTimeCard.padding(.top, Alibi.Space.s2)
                SectionTitle(text: "Home").padding(.top, Alibi.Space.s6)
                homeCard.padding(.top, Alibi.Space.s2)
                Text("Home is a yes or no; your location never leaves the phone. Screen Time sends minutes only, never app names. No message text, no app contents.")
                    .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, Alibi.Space.s4)
                Button("Review permissions") { showOnboarding = true }
                    .buttonStyle(QuietButtonStyle())
                    .padding(.top, Alibi.Space.s1)
            }
            .padding(.horizontal, Alibi.Space.cardPhone)
            .padding(.top, Alibi.Space.s2)
            .padding(.bottom, Alibi.Space.s8)
        }
        .scrollIndicators(.hidden)
        .background(Alibi.ui.bg.ignoresSafeArea())
        .familyActivityPicker(headerText: "Pick your distracting apps", isPresented: $picking, selection: $draft)
        .onChange(of: picking) { _, open in
            if open { draft = st.selection } else if draft != st.selection { st.save(draft) }
        }
        .sensoryFeedback(.success, trigger: connectedID)
    }

    // MARK: Sync card

    private var reachable: Bool? { MirrorClient.demo ? mirror.online : (sync.ok ?? mirror.online) }
    private var lastSync: Date? { MirrorClient.demo ? (demoSynced ?? Date().addingTimeInterval(-120)) : sync.lastSync }
    private var busy: Bool { MirrorClient.demo ? demoBusy : sync.busy }

    private var syncCard: some View {
        Card(padding: Alibi.Space.s4, spacing: 14) {
            HStack(spacing: Alibi.Space.s3) {
                Image(systemName: "laptopcomputer").font(.title3).foregroundStyle(Alibi.ui.ink)
                    .frame(width: 44, height: 44)
                    .background(RoundedRectangle(cornerRadius: Alibi.Radius.sm, style: .continuous).fill(Alibi.ui.surface2))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text(mirror.macName).font(Alibi.Fonts.iosHeadline).foregroundStyle(Alibi.ui.ink).lineLimit(2)
                    HStack(spacing: 6) {
                        StatusDot(label: reachable == true ? "on_task" : reachable == false ? "phone" : "absent", size: 8)
                        Text(reachable == true ? "Connected" : reachable == false ? "Can't reach it right now" : "Not synced yet")
                            .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2)
                    }
                }
                Spacer(minLength: 0)
            }
            Divider().overlay(Alibi.ui.hairline)
            HStack(spacing: Alibi.Space.s2) {
                if connectedID > 0 {
                    PinchView(mood: .idle, clip: .connected, clipID: connectedID, size: 20)
                        .accessibilityHidden(true)
                        .transition(.opacity.combined(with: .scale(scale: 0.94)))
                }
                Text(busy ? "Sending…" : lastSync == nil ? "Not synced yet" : "Synced \(Fmt.ago(lastSync))")
                    .font(Alibi.Fonts.iosSubheadline.weight(.semibold)).foregroundStyle(Alibi.ui.ink).monospacedDigit()
                    .contentTransition(.opacity)
                Spacer(minLength: 0)
                if !MirrorClient.demo, sync.pending > 0 {
                    Text("\(sync.pending) waiting").font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink3).monospacedDigit()
                }
            }
            .frame(minHeight: 24)
            .accessibilityElement(children: .combine)
            if !MirrorClient.demo, sync.ok == false {
                Text(sync.status).font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Button { Task { await syncNow() } } label: {
                Label(busy ? "Syncing…" : "Sync now", systemImage: "arrow.up")
            }
            .buttonStyle(SecondaryButtonStyle()).disabled(busy)
            .sensoryFeedback(.selection, trigger: busy)
        }
        .alibiAnimation(Alibi.Motion.smooth, value: connectedID)
    }

    private func syncNow() async {
        if MirrorClient.demo {                       // demo: never touch the network
            demoBusy = true
            try? await Task.sleep(for: .milliseconds(900))
            demoBusy = false; demoSynced = Date(); connectedID += 1
            return
        }
        await sync.run(reason: "manual", full: true)
        if sync.ok == true { connectedID += 1 }
    }

    // MARK: Streams, Screen Time, Home (the old Home screen, on tokens)

    private var streams: some View {
        Card(padding: Alibi.Space.s4) {
            StreamRow(id: "health", icon: "heart", title: "Health",
                      value: healthValue, perm: perms.healthText, tone: perms.healthTone)
            Divider().overlay(Alibi.ui.hairline)
            StreamRow(id: "heart", icon: "waveform.path.ecg", title: "Heart rate",
                      value: snap.heart.map { "\(Int($0.bpm)) bpm · \(Fmt.ago($0.at))" } ?? "No reading yet",
                      perm: perms.healthText, tone: perms.healthTone)
            Divider().overlay(Alibi.ui.hairline)
            StreamRow(id: "motion", icon: "figure.walk", title: "Motion and pickups",
                      value: motionValue, perm: perms.motionText, tone: perms.motionTone, also: ["pickup"])
            Divider().overlay(Alibi.ui.hairline)
            StreamRow(id: "location", icon: "house", title: "At home",
                      value: home.atHome.map { $0 ? "At home" : "Away" } ?? "Home not set",
                      perm: home.permissionText, tone: home.tone)
            Divider().overlay(Alibi.ui.hairline)
            StreamRow(id: "focus", icon: "moon", title: "Alibi Focus",
                      value: focus.configured ? (focus.on ? "On" : "Off") : "Not added to a Focus yet",
                      perm: focus.configured ? "Filter added" : "Settings › Focus › Alibi › Add Filter",
                      tone: focus.configured ? .good : .neutral)
            Divider().overlay(Alibi.ui.hairline)
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
        if let m = snap.motionNow { bits.append("\(m.state.capitalized) since \(Fmt.hm.string(from: m.since))") }
        bits.append("\(Motion.pickupsToday) pickups today")
        return bits.joined(separator: " · ")
    }

    private var screenTimeCard: some View {
        Card(padding: Alibi.Space.s4) {
            Text(st.auth == .approved
                 ? "Alibi counts every 5 minutes you spend in your picked apps, and blocks them while a session is on. Tapping a blocked app shows what you said you'd be doing."
                 : "Pick the apps that pull you away. Alibi counts the minutes you spend in them and blocks them while a session is on. App names never leave this phone; your Mac only hears minutes.")
                .font(Alibi.Fonts.iosSubheadline).foregroundStyle(Alibi.ui.ink2)
                .fixedSize(horizontal: false, vertical: true)
            if let m = st.message { Text(m).font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink) }
            if st.auth != .approved {
                Button { Task { await st.requestAuthorization(); if st.auth == .approved { picking = true } } } label: {
                    Text("Allow Screen Time")
                }.buttonStyle(SecondaryButtonStyle())
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
        Card(padding: Alibi.Space.s4) {
            Text(home.homeSet ? "Alibi knows when you leave or get home, for gym and walk habits and to spot when you're away from your desk during a session."
                 : "Stand at home and tap below. Alibi saves a \(Int(HomeLocation.radius)) m circle on this phone and only ever tells your Mac \"at home: yes or no\".")
                .font(Alibi.Fonts.iosSubheadline).foregroundStyle(Alibi.ui.ink2)
                .fixedSize(horizontal: false, vertical: true)
            if home.auth == .authorizedWhenInUse {
                Text("To notice arrivals while Alibi is closed, set Location to Always: Settings › Alibi › Location › Always.")
                    .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.partialInk)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let m = home.message { Text(m).font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink) }
            Button { Task { await home.setHomeHere() } } label: {
                Text(home.busy ? "Finding you…" : home.homeSet ? "Move home to here" : "Set this as home")
            }.buttonStyle(SecondaryButtonStyle()).disabled(home.busy)
        }
    }
}

/// One stream: icon, title, its latest value, permission state (as a shaped dot) and when it last reached the Mac.
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
        HStack(alignment: .top, spacing: Alibi.Space.s3) {
            Image(systemName: icon).font(.body).foregroundStyle(Alibi.ui.ink2).frame(width: 24).padding(.top, 2)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(Alibi.Fonts.iosSubheadline.weight(.semibold)).foregroundStyle(Alibi.ui.ink)
                Text(value).font(Alibi.Fonts.iosSubheadline).monospacedDigit().foregroundStyle(Alibi.ui.ink)
                HStack(spacing: 6) {
                    Dot(tone: tone, size: 7)
                    Text(perm).lineLimit(2)
                }
                .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink2)
                Text("Sent \(Fmt.ago(([id] + also).compactMap(Store.lastSent).max()))")
                    .font(Alibi.Fonts.iosFootnote).foregroundStyle(Alibi.ui.ink3).monospacedDigit()
            }
            Spacer(minLength: Alibi.Space.s1)
            Toggle(title, isOn: $on).labelsHidden().tint(Alibi.ui.accent)
                .onChange(of: on) { _, v in ([id] + also).forEach { Store.setEnabled($0, v) } }
        }
        .onAppear { on = Store.enabled(id) }
    }
}

/// Day · Steps · Sleep · Mindful · Exercise, newest first. Short sleep (< 7 h) gets the half-disc mark and partial ink.
struct DaysTable: View {
    let days: [[String: Any]]
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        VStack(spacing: 0) {
            if days.isEmpty {
                Text("No Health data yet. Allow Health in Review permissions, then Sync now.")
                    .font(Alibi.Fonts.iosSubheadline).foregroundStyle(Alibi.ui.ink2)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, Alibi.Space.s4)
            } else {
                Grid(alignment: .trailing, horizontalSpacing: 6, verticalSpacing: 0) {
                    GridRow {
                        Text("Day").gridColumnAlignment(.leading).frame(maxWidth: .infinity, alignment: .leading)
                        Text("Steps"); Text("Sleep"); Text("Mindful"); Text("Exercise")
                    }
                    .font(Alibi.Fonts.iosCaption).foregroundStyle(Alibi.ui.ink2)
                    .lineLimit(1).minimumScaleFactor(0.8)
                    .padding(.top, 10).padding(.bottom, Alibi.Space.s2)
                    ForEach(Array(days.prefix(7).enumerated()), id: \.offset) { i, d in
                        Divider().overlay(Alibi.ui.hairline).gridCellUnsizedAxes(.horizontal)
                        GridRow {
                            Text(Self.label(d["date"] as? String ?? "")).fontWeight(i == 0 ? .semibold : .regular)
                                .foregroundStyle(Alibi.ui.ink).frame(maxWidth: .infinity, alignment: .leading)
                            Text(Self.num(d["steps"]).map { $0.formatted(.number.grouping(.automatic).locale(Locale(identifier: "en_GB"))) } ?? "–")
                            sleep(d["sleep_h"])
                            Text(Self.num(d["mindful_min"]).map(String.init) ?? "–")
                            Text(Self.num(d["exercise_min"] ?? d["workout_min"]).map(String.init) ?? "–")
                        }
                        .font(Alibi.Fonts.iosSubheadline).monospacedDigit().foregroundStyle(Alibi.ui.ink)
                        .lineLimit(1).minimumScaleFactor(0.75)
                        .frame(minHeight: typeSize >= .xxLarge ? 36 : 30)
                    }
                }
                .padding(.bottom, 6)
            }
        }
        .padding(.horizontal, Alibi.Space.s4)
        .background(RoundedRectangle(cornerRadius: Alibi.Radius.md, style: .continuous).fill(Alibi.ui.surface1))
        .overlay(RoundedRectangle(cornerRadius: Alibi.Radius.md, style: .continuous).strokeBorder(Alibi.ui.hairline, lineWidth: 1))
    }

    @ViewBuilder private func sleep(_ v: Any?) -> some View {
        if let h = v as? Double {
            HStack(spacing: 5) {
                if h < 7 { StatusDot(label: "idle", size: 8).accessibilityLabel("Under 7 hours") }
                Text(String(format: "%.1f", h)).foregroundStyle(h < 7 ? Alibi.ui.partialInk : Alibi.ui.ink)
            }
        } else {
            Text("–")
        }
    }

    static func num(_ v: Any?) -> Int? { (v as? Double).map { Int($0.rounded()) } ?? (v as? Int) }

    static func label(_ iso: String) -> String {
        guard let d = Fmt.day.date(from: iso) else { return iso }
        if Calendar.current.isDateInToday(d) { return "Today" }
        let f = DateFormatter(); f.locale = Locale(identifier: "en_GB"); f.dateFormat = "EEE d"
        return f.string(from: d)
    }
}
