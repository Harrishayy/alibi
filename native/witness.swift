// alibi-witness: on-device evidence from a JPEG using Apple's Vision framework. No network, no keys.
// usage: alibi-witness frame.jpg  ->  {"humans":1,"faces":1,"hands":2,"pitch":-0.2,"classes":{"pen":0.4,...}}
import Foundation
import Vision

import AVFoundation

guard CommandLine.arguments.count > 1 else { print("{}"); exit(0) }
if CommandLine.arguments[1] == "--camera-auth" {
    switch AVCaptureDevice.authorizationStatus(for: .video) {
    case .authorized: print("authorized")
    case .denied: print("denied")
    case .restricted: print("restricted")
    case .notDetermined: print("not_determined")
    @unknown default: print("unknown")
    }
    exit(0)
}
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let handler = VNImageRequestHandler(url: url, options: [:])

let humans = VNDetectHumanRectanglesRequest(); humans.upperBodyOnly = true
let faces = VNDetectFaceRectanglesRequest()
let hands = VNDetectHumanHandPoseRequest(); hands.maximumHandCount = 4
let classify = VNClassifyImageRequest()

var out: [String: Any] = ["humans": 0, "faces": 0, "hands": 0, "classes": [String: Double]()]
do {
    try handler.perform([humans, faces, hands, classify])
    out["humans"] = humans.results?.count ?? 0
    out["faces"] = faces.results?.count ?? 0
    out["hands"] = (hands.results ?? []).filter { $0.confidence > 0.3 }.count
    if let f = faces.results?.first {
        out["pitch"] = f.pitch?.doubleValue ?? 0
        out["yaw"] = f.yaw?.doubleValue ?? 0
    }
    var classes: [String: Double] = [:]
    for c in (classify.results ?? []).prefix(400) where c.confidence > 0.05 {
        classes[c.identifier] = Double(c.confidence)
    }
    out["classes"] = classes
} catch {
    out["error"] = "\(error)"
}
let data = try! JSONSerialization.data(withJSONObject: out, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
