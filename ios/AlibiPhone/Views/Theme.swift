// NVIDIA palette on a Claude-style layout: black surfaces, #1A1A1A cards with a hairline, #76B900 accent with black
// text on green, #E5484D for bad, #F2A900 for partial. Serif (New York) for headings, sans for UI.
import SwiftUI

enum Palette {
    static let accent = Color(red: 0x76 / 255, green: 0xB9 / 255, blue: 0)
    static let accentInk = Color(red: 0x8F / 255, green: 0xD4 / 255, blue: 0)
    static let bad = Color(red: 0xE5 / 255, green: 0x48 / 255, blue: 0x4D / 255)
    static let partial = Color(red: 0xF2 / 255, green: 0xA9 / 255, blue: 0)
    static let card = Color(red: 0x1A / 255, green: 0x1A / 255, blue: 0x1A / 255)
    static let muted = Color(red: 0xA6 / 255, green: 0xA6 / 255, blue: 0xA6 / 255)
    static let dim = Color(red: 0x5E / 255, green: 0x5E / 255, blue: 0x5E / 255)
    static let hairline = Color.white.opacity(0.09)
}

enum Tone { case good, partial, bad, neutral
    var color: Color {
        switch self { case .good: Palette.accent; case .partial: Palette.partial; case .bad: Palette.bad; case .neutral: Palette.dim }
    }
}

struct Card<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 12) { content }
            .padding(16).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Palette.card))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(Palette.hairline, lineWidth: 1))
    }
}

struct SectionLabel: View {
    let text: String
    var body: some View {
        Text(text.uppercased()).font(.caption.weight(.semibold)).tracking(0.6).foregroundStyle(Palette.muted)
    }
}

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(.headline).foregroundStyle(.black)
            .frame(maxWidth: .infinity).padding(.vertical, 14)
            .background(RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Palette.accent))
            .scaleEffect(configuration.isPressed ? 0.97 : 1).opacity(configuration.isPressed ? 0.9 : 1)
    }
}

struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(.subheadline.weight(.semibold)).foregroundStyle(.white)
            .frame(maxWidth: .infinity).padding(.vertical, 12)
            .background(RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Color.white.opacity(configuration.isPressed ? 0.14 : 0.08)))
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
    }
}

struct Dot: View {
    let tone: Tone
    var size: CGFloat = 8
    var body: some View { Circle().fill(tone.color).frame(width: size, height: size) }
}
