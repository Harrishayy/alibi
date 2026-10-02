// The last two names of the old phone theme, kept only because files outside Views/ still use them:
// AlibiPhoneApp.swift tints with `Palette.accent`; Permissions, ScreenTimeShield and HomeLocation report a `Tone`.
// Both resolve to the shared Alibi tokens. Delete this file once those files read `Alibi.ui` and StatusDot labels.
import SwiftUI

enum Palette {
    static let accent = Alibi.ui.accent
}

enum Tone { case good, partial, bad, neutral
    /// The evidence label whose shape this tone borrows (status is colour plus shape).
    var label: String {
        switch self { case .good: "on_task"; case .partial: "idle"; case .bad: "phone"; case .neutral: "absent" }
    }
    var color: Color {
        switch self { case .good: Alibi.ui.onTask; case .partial: Alibi.ui.partial; case .bad: Alibi.ui.warn; case .neutral: Alibi.ui.absent }
    }
}
