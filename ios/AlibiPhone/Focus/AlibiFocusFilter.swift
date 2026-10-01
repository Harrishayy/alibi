// Focus filter "Alibi session". Add it to an "Alibi" Focus (Settings → Focus → Alibi → Focus Filters → Alibi).
// The Mac turns that Focus on at session start (shared across devices), iOS runs perform() here, and the app:
//   • posts phone.focus {on, name}
//   • asks the Screen Time shield (ScreenTime/ShieldController.swift) to block / unblock
//   • syncs right away and keeps syncing every ~2 min while it has time.
// iOS calls perform() again with every parameter reset to its default when the Focus turns off, so the optional
// "Block distracting apps" parameter doubles as the on/off signal: set (on or off) = Focus active, nil = Focus ended.
import AppIntents
import Foundation

struct AlibiFocusFilter: SetFocusFilterIntent {
    static var title: LocalizedStringResource = "Alibi session"
    static var description: IntentDescription? = IntentDescription(
        "While this Focus is on, Alibi tells your Mac you're in a session, blocks your picked apps, and syncs every few minutes.")

    @Parameter(title: "Block distracting apps")
    var block: Bool?

    var displayRepresentation: DisplayRepresentation {
        switch block {
        case .some(true): DisplayRepresentation(title: "Alibi session", subtitle: "Blocks picked apps · syncs every 2 min")
        case .some(false): DisplayRepresentation(title: "Alibi session", subtitle: "Syncs every 2 min")
        case .none: DisplayRepresentation(title: "Alibi session", subtitle: "Choose whether to block apps")
        }
    }

    func perform() async throws -> some IntentResult {
        await FocusState.shared.apply(on: block != nil, block: block ?? false)
        return .result()
    }
}

@MainActor
final class FocusState: ObservableObject {
    static let shared = FocusState()
    @Published var on: Bool = Store.d.bool(forKey: "focus.on")
    @Published var configured: Bool = Store.d.bool(forKey: "focus.seen")

    func apply(on new: Bool, block: Bool) {
        configured = true
        Store.set(true, "focus.seen")
        let changed = new != on
        on = new
        Store.set(new, "focus.on")
        Shields.current.apply(on: new && block, source: "focus")
        guard changed else { return }
        if Store.enabled("focus") {
            SyncEngine.shared.enqueue([row("phone", "focus", ["on": new, "name": "Alibi"])], stream: "focus")
        }
        SyncEngine.shared.syncInBackground(reason: new ? "focus on" : "focus off")
        if new { SyncEngine.shared.startLive() }
    }
}
