// The Live Activity's data contract, shared by the app (which starts/updates/ends it) and the AlibiLive widget
// extension (which draws it). Keep the payload tiny: the system caps it at 4 KB.
// The ActivityKit conformance is iOS-only so the macOS PNG harness (docs/design/fixtures/live/) can compile the views.
import Foundation
#if os(iOS)
import ActivityKit
#endif

struct AlibiLiveAttributes {
    struct ContentState: Codable, Hashable {
        var start: Date; var end: Date
        var onTask: Int?                // 0–100; nil until the first sample ("Watching")
        var status: String              // "on" | "drift" | "break" | "done" | "partial" | "slacked"
        var line: String                // "On task 92% · last seen 18:04" (≤ 40 chars)
        var pose: String                // Pinch still pose: focused | sideeye | sleepy | celebrate | partial | supportive
        var badge: String? = nil        // short compact value while drifting/on a break ("3m"); nil → the timer
        var cause: String? = nil        // what the drift is: phone | off_task | absent | idle
        var breakEnd: Date? = nil       // on a break: the timer counts down to this instead of `end`
    }
    var habit: String                   // "Drawing"
}

#if os(iOS)
extension AlibiLiveAttributes: ActivityAttributes {}
#endif

extension AlibiLiveAttributes.ContentState {
    var isVerdict: Bool { ["done", "partial", "slacked"].contains(status) }
}
