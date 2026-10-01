// What a blocked app looks like during an Alibi session: black, NVIDIA green, and a reminder of what you said you'd do.
import ManagedSettings
import ManagedSettingsUI
import UIKit

final class AlibiShieldConfig: ShieldConfigurationDataSource {
    private let green = UIColor(red: 0x76 / 255, green: 0xB9 / 255, blue: 0, alpha: 1)
    private let muted = UIColor(red: 0xA6 / 255, green: 0xA6 / 255, blue: 0xA6 / 255, alpha: 1)

    override func configuration(shielding application: Application) -> ShieldConfiguration {
        make(application.localizedDisplayName)
    }

    override func configuration(shielding application: Application, in category: ActivityCategory) -> ShieldConfiguration {
        make(application.localizedDisplayName)
    }

    override func configuration(shielding webDomain: WebDomain) -> ShieldConfiguration {
        make(webDomain.domain)
    }

    override func configuration(shielding webDomain: WebDomain, in category: ActivityCategory) -> ShieldConfiguration {
        make(webDomain.domain)
    }

    private func make(_ name: String?) -> ShieldConfiguration {
        let habit = AlibiShared.defaults.string(forKey: AlibiShared.habitKey)?.trimmingCharacters(in: .whitespaces)
        let title = (habit?.isEmpty == false) ? "Alibi says: you said \(habit!.lowercased())" : "Alibi says: you're in a session"
        let icon = UIImage(systemName: "checkmark.seal.fill")?.withTintColor(green, renderingMode: .alwaysOriginal)
        return ShieldConfiguration(
            backgroundBlurStyle: .systemUltraThinMaterialDark,
            backgroundColor: .black,
            icon: icon,
            title: .init(text: title, color: .white),
            subtitle: .init(text: "\(name ?? "This app") is blocked until your session ends. Your Mac is keeping the receipts.",
                            color: muted),
            primaryButtonLabel: .init(text: "Back to it", color: .black),
            primaryButtonBackgroundColor: green,
            secondaryButtonLabel: nil)
    }
}
