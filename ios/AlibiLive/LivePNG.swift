// macOS-only PNG harness for the Live Activity views (compiles to nothing in the iOS extension).
// Draws every status into stand-ins for the system containers: the Lock Screen banner, the compact and minimal
// Dynamic Island, and the expanded island, so the layouts can be checked without a device. Run:
//   swiftc -parse-as-library -target arm64-apple-macos14.0 ios/AlibiLive/LivePNG.swift ios/AlibiLive/LiveViews.swift \
//     ios/AlibiPhone/Views/Live/AlibiLiveAttributes.swift ios/AlibiPhone/Views/Shared/{Theme,Pinch}.swift -o /tmp/livepng
//   /tmp/livepng OUT_DIR
#if os(macOS)
import AppKit
import SwiftUI

private let P = Alibi.Palette.dark

/// The system's island capsule around the compact slots (52 pt slots either side of the camera).
private struct CompactIsland: View {
    var state: AlibiLiveAttributes.ContentState
    var body: some View {
        HStack(spacing: 0) {
            LiveCompactLeading(state: state).frame(width: 52, alignment: .center)
            Spacer(minLength: 0)
            LiveCompactTrailing(state: state).frame(width: 52, alignment: .center)
        }
        .padding(.horizontal, 6)
        .frame(width: 250, height: 37)
        .background(Capsule().fill(P.island))
    }
}

private struct ExpandedIsland: View {
    var habit: String
    var state: AlibiLiveAttributes.ContentState
    var body: some View {
        VStack(spacing: 4) {
            HStack(alignment: .top) {
                LiveExpandedLeading(state: state)
                Spacer()
                LiveExpandedTrailing(state: state)
            }
            .overlay(alignment: .bottom) { LiveExpandedCenter(habit: habit, state: state).offset(y: 18) }
            .frame(height: 52)
            Spacer(minLength: 0)
            LiveExpandedBottom(state: state)
        }
        .padding(.horizontal, 18)
        .padding(.top, 14)
        .padding(.bottom, 16)
        .frame(width: 368, height: 160)
        .background(RoundedRectangle(cornerRadius: 44, style: .continuous).fill(P.island))
        .overlay(RoundedRectangle(cornerRadius: 44, style: .continuous).strokeBorder(P.accentWash, lineWidth: 1))
    }
}

private struct Board: View {
    var status: String
    var reduced = false
    var body: some View {
        let s = AlibiLiveAttributes.ContentState.sample(status, now: Date())
        VStack(alignment: .leading, spacing: 24) {
            Text("\(status)\(reduced ? " · always-on" : "")").font(Alibi.Fonts.sans(13, .semibold)).foregroundStyle(P.ink2)
            LiveLockScreenView(habit: "Drawing", state: s)
                .frame(width: 362)
                .background(RoundedRectangle(cornerRadius: Alibi.Radius.lg, style: .continuous).fill(P.island))
                .overlay(RoundedRectangle(cornerRadius: Alibi.Radius.lg, style: .continuous).strokeBorder(P.hairline))
            HStack(spacing: 16) {
                CompactIsland(state: s)
                LiveMinimal(state: s).frame(width: 37, height: 37).padding(0)
                    .background(Circle().fill(P.island))
            }
            ExpandedIsland(habit: "Drawing", state: s)
        }
        .padding(24)
        .frame(width: 410, alignment: .leading)
        .background(P.surface1)
        .environment(\.isLuminanceReduced, reduced)
        .environment(\.liveSnapshot, true)
        .environment(\.colorScheme, .dark)
    }
}

@main
struct LivePNG {
    @MainActor static func main() {
        let out = CommandLine.arguments.dropFirst().first ?? "/tmp/p20"
        try? FileManager.default.createDirectory(atPath: out, withIntermediateDirectories: true)
        let boards: [(String, Bool)] = [("on", false), ("watching", false), ("drift", false), ("break", false),
                                        ("done", false), ("partial", false), ("slacked", false), ("on", true)]
        for (status, reduced) in boards {
            let r = ImageRenderer(content: Board(status: status, reduced: reduced))
            r.scale = 3
            guard let cg = r.cgImage else { print("render failed \(status)"); continue }
            let rep = NSBitmapImageRep(cgImage: cg)
            let name = "\(out)/live_\(status)\(reduced ? "_aod" : "").png"
            try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: name))
            print("wrote \(name)")
        }
    }
}
#endif
