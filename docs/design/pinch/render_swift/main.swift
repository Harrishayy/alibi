// Offscreen renders of the SwiftUI Pinch, for side-by-side checks against the web rig (compare.py).
// The only file in the rig with top-level code. Build and run from docs/design/pinch/render_swift:
//
//   swiftc -O main.swift ../Pinch.swift ../PinchData.swift -o /tmp/pinch-render && /tmp/pinch-render
//
// Reads cases.json (written by compare.py; a default set is used when it is missing) and writes
// ../swift-renders/<id>.png at 2x: each case is a (size + 2 × round(0.15 size)) square on its theme's ground, Pinch centred.
import Foundation
import ImageIO
import SwiftUI
import UniformTypeIdentifiers

struct RenderCase: Decodable {
    let id: String
    let mood: String
    let clip: String?
    let ms: Double
    let size: Double
    let theme: String
}

let here = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
let outDir = here.deletingLastPathComponent().appendingPathComponent("swift-renders")
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

let defaults: [RenderCase] = {
    var out: [RenderCase] = []
    for theme in ["dark", "light"] {
        out.append(RenderCase(id: "idle-160-\(theme)", mood: "idle", clip: nil, ms: 0, size: 160, theme: theme))
        out.append(RenderCase(id: "celebrate380-160-\(theme)", mood: "idle", clip: "celebrate", ms: 380, size: 160, theme: theme))
        out.append(RenderCase(id: "sideeye600-160-\(theme)", mood: "idle", clip: "sideeye", ms: 600, size: 160, theme: theme))
        out.append(RenderCase(id: "supportive700-160-\(theme)", mood: "idle", clip: "supportive", ms: 700, size: 160, theme: theme))
        out.append(RenderCase(id: "idle-16-\(theme)", mood: "idle", clip: nil, ms: 0, size: 16, theme: theme))
    }
    return out
}()

let casesURL = here.appendingPathComponent("cases.json")
let cases: [RenderCase] = (try? JSONDecoder().decode([RenderCase].self, from: Data(contentsOf: casesURL))) ?? defaults

func writePNG(_ image: CGImage, to url: URL) -> Bool {
    guard let dest = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil) else { return false }
    CGImageDestinationAddImage(dest, image, nil)
    return CGImageDestinationFinalize(dest)
}

MainActor.assumeIsolated {
    var failures = 0
    for c in cases {
        let mood = PinchMood(rawValue: c.mood) ?? .idle
        let clip = c.clip.flatMap(PinchClip.init(rawValue:))
        let pose = PinchView.pose(mood: mood, clip: clip, ms: c.ms)
        let dark = c.theme == "dark"
        let size = CGFloat(c.size)
        let box = size + 2 * (size * 0.15).rounded()
        let view = ZStack {
            (dark ? Color.black : Color.white)
            PinchFigure(pose: pose, size: size, dark: dark, time: c.ms)
        }
        .frame(width: box, height: box)
        .environment(\.colorScheme, dark ? .dark : .light)
        let r = ImageRenderer(content: view)
        r.scale = 2
        guard let img = r.cgImage, writePNG(img, to: outDir.appendingPathComponent("\(c.id).png")) else {
            print("FAIL \(c.id)")
            failures += 1
            continue
        }
        print("wrote swift-renders/\(c.id).png")
    }
    if failures > 0 { exit(1) }
}
