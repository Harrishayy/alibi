// Alibi's Live Activity: Lock Screen banner and Dynamic Island for a running session. Views live in LiveViews.swift;
// this file only maps them into the system's slots. Black background, accent keyline, sans only, no custom motion.
import SwiftUI
import WidgetKit
import ActivityKit

@main
struct AlibiLiveBundle: WidgetBundle {
    var body: some Widget { AlibiLiveWidget() }
}

struct AlibiLiveWidget: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: AlibiLiveAttributes.self) { context in
            LiveLockScreenView(habit: context.attributes.habit, state: context.state, stale: context.isStale)
                .activityBackgroundTint(.black)
                .activitySystemActionForegroundColor(Alibi.Palette.dark.ink)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) { LiveExpandedLeading(state: context.state, stale: context.isStale) }
                DynamicIslandExpandedRegion(.trailing) { LiveExpandedTrailing(state: context.state) }
                DynamicIslandExpandedRegion(.center) { LiveExpandedCenter(habit: context.attributes.habit, state: context.state) }
                DynamicIslandExpandedRegion(.bottom) { LiveExpandedBottom(state: context.state, stale: context.isStale) }
            } compactLeading: {
                LiveCompactLeading(state: context.state, stale: context.isStale)
            } compactTrailing: {
                LiveCompactTrailing(state: context.state)
            } minimal: {
                LiveMinimal(state: context.state)
            }
            .keylineTint(Alibi.Palette.dark.accent)
        }
    }
}

#if DEBUG
#Preview("Lock Screen", as: .content, using: AlibiLiveAttributes.preview) {
    AlibiLiveWidget()
} contentStates: {
    AlibiLiveAttributes.ContentState.sample("on")
    AlibiLiveAttributes.ContentState.sample("watching")
    AlibiLiveAttributes.ContentState.sample("drift")
    AlibiLiveAttributes.ContentState.sample("break")
    AlibiLiveAttributes.ContentState.sample("done")
    AlibiLiveAttributes.ContentState.sample("partial")
    AlibiLiveAttributes.ContentState.sample("slacked")
}

#Preview("Island compact", as: .dynamicIsland(.compact), using: AlibiLiveAttributes.preview) {
    AlibiLiveWidget()
} contentStates: {
    AlibiLiveAttributes.ContentState.sample("on")
    AlibiLiveAttributes.ContentState.sample("drift")
}

#Preview("Island expanded", as: .dynamicIsland(.expanded), using: AlibiLiveAttributes.preview) {
    AlibiLiveWidget()
} contentStates: {
    AlibiLiveAttributes.ContentState.sample("on")
    AlibiLiveAttributes.ContentState.sample("done")
}
#endif
