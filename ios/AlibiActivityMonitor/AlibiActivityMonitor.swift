// DeviceActivity monitor extension. iOS runs this (not the app) when the picked apps cross another 5 minutes today,
// and when a monitored window starts or ends. It only writes to the App Group; the app ships rows on its next sync.
import DeviceActivity
import Foundation
import ManagedSettings

final class AlibiActivityMonitor: DeviceActivityMonitor {
    override func intervalDidStart(for activity: DeviceActivityName) {
        super.intervalDidStart(for: activity)
        if activity == .alibiDaily { AlibiShared.resetDay() }
    }

    override func intervalDidEnd(for activity: DeviceActivityName) {
        super.intervalDidEnd(for: activity)
        // The session window passed without the app turning blocking off (it was asleep or killed): unblock now.
        if activity == .alibiShieldFailsafe { AlibiShared.clearShield() }
    }

    override func eventDidReachThreshold(_ event: DeviceActivityEvent.Name, activity: DeviceActivityName) {
        super.eventDidReachThreshold(event, activity: activity)
        guard activity == .alibiDaily, let m = event.pickedMinutes else { return }
        AlibiShared.recordUsage(minutes: m)
    }
}
