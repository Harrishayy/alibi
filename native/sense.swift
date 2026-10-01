// alibi-sense: one cheap look at "is the person at this Mac, and what is it doing?" — JSON out, never prompts.
//
//   alibi-sense                  -> {"idle_s","locked","display_asleep","displays","on_battery","battery_pct",
//                                    "camera","camera_devices":[..],"mic","mic_apps":[..],"meeting_apps":[..],
//                                    "media":[{app,id,playing,title?,status}],"focus":{on,mode?,status}}
//   alibi-sense --ask-media      -> same, but may show the one-time "Alibi wants to control Music/Spotify" prompt
//   alibi-sense --installed ID…  -> {"ID": "App Name" | null}   (is this bundle id an app on this Mac?)
//
// Every read here is permission-free: HIDIdleTime, CGSession, CoreMediaIO / CoreAudio "is running somewhere"
// queries and NSWorkspace never trigger a TCC prompt. Music/Spotify are only asked when they are running AND
// Automation was already allowed (unless --ask-media). Focus needs Full Disk Access; without it we say so.
import Foundation
import AppKit
import IOKit
import IOKit.ps
import CoreGraphics
import CoreMediaIO
import CoreAudio

func out(_ obj: Any) {
    if let d = try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys]),
       let s = String(data: d, encoding: .utf8) { print(s) } else { print("{\"error\":\"encode\"}") }
}

// --- presence ------------------------------------------------------------------------------------------------------

func idleSeconds() -> Double? {
    let svc = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IOHIDSystem"))
    guard svc != 0 else { return nil }
    defer { IOObjectRelease(svc) }
    guard let v = IORegistryEntryCreateCFProperty(svc, "HIDIdleTime" as CFString, kCFAllocatorDefault, 0)?
            .takeRetainedValue() as? NSNumber else { return nil }
    return (v.doubleValue / 1_000_000_000 * 10).rounded() / 10
}

func sessionInfo() -> (locked: Bool, onConsole: Bool) {
    guard let d = CGSessionCopyCurrentDictionary() as? [String: Any] else { return (false, true) }
    let locked = (d["CGSSessionScreenIsLocked"] as? Bool) ?? ((d["CGSSessionScreenIsLocked"] as? Int) ?? 0 != 0)
    let onConsole = (d[kCGSessionOnConsoleKey as String] as? Bool) ?? true
    return (locked, onConsole)
}

func displays() -> (count: Int, asleep: Bool) {
    var n: UInt32 = 0
    CGGetOnlineDisplayList(0, nil, &n)
    return (Int(n), CGDisplayIsAsleep(CGMainDisplayID()) != 0)
}

func power() -> (onBattery: Bool?, pct: Int?) {
    guard let blob = IOPSCopyPowerSourcesInfo()?.takeRetainedValue(),
          let list = IOPSCopyPowerSourcesList(blob)?.takeRetainedValue() as? [CFTypeRef] else { return (nil, nil) }
    for ps in list {
        guard let d = IOPSGetPowerSourceDescription(blob, ps)?.takeUnretainedValue() as? [String: Any] else { continue }
        if (d[kIOPSTypeKey] as? String) != kIOPSInternalBatteryType { continue }
        let state = d[kIOPSPowerSourceStateKey] as? String
        var pct: Int? = nil
        if let cur = d[kIOPSCurrentCapacityKey] as? Int, let mx = d[kIOPSMaxCapacityKey] as? Int, mx > 0 {
            pct = cur * 100 / mx
        }
        return (state == kIOPSBatteryPowerValue, pct)
    }
    return (false, nil)  // desktop Mac: always on AC
}

// --- camera (CoreMediaIO) ------------------------------------------------------------------------------------------

func cmioAddr(_ sel: Int) -> CMIOObjectPropertyAddress {
    CMIOObjectPropertyAddress(mSelector: CMIOObjectPropertySelector(sel),
                              mScope: CMIOObjectPropertyScope(kCMIOObjectPropertyScopeGlobal),
                              mElement: CMIOObjectPropertyElement(kCMIOObjectPropertyElementMain))
}

func cameraInUse() -> (on: Bool, devices: [String]) {
    var addr = cmioAddr(Int(kCMIOHardwarePropertyDevices))
    var size: UInt32 = 0
    let sys = CMIOObjectID(kCMIOObjectSystemObject)
    guard CMIOObjectGetPropertyDataSize(sys, &addr, 0, nil, &size) == 0, size > 0 else { return (false, []) }
    var ids = [CMIOObjectID](repeating: 0, count: Int(size) / MemoryLayout<CMIOObjectID>.size)
    var used: UInt32 = 0
    guard CMIOObjectGetPropertyData(sys, &addr, 0, nil, size, &used, &ids) == 0 else { return (false, []) }
    var names: [String] = []
    for id in ids {
        var a = cmioAddr(Int(kCMIODevicePropertyDeviceIsRunningSomewhere))
        var running: UInt32 = 0
        var got: UInt32 = 0
        if CMIOObjectGetPropertyData(id, &a, 0, nil, UInt32(MemoryLayout<UInt32>.size), &got, &running) == 0, running != 0 {
            var na = cmioAddr(Int(kCMIOObjectPropertyName))
            var name: Unmanaged<CFString>? = nil
            var g2: UInt32 = 0
            let ok = CMIOObjectGetPropertyData(id, &na, 0, nil, UInt32(MemoryLayout<Unmanaged<CFString>?>.size), &g2, &name)
            names.append(ok == 0 ? (name?.takeRetainedValue() as String? ?? "camera") : "camera")
        }
    }
    return (!names.isEmpty, names)
}

// --- microphone (CoreAudio) -----------------------------------------------------------------------------------------

func audioAddr(_ sel: AudioObjectPropertySelector, _ scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal)
    -> AudioObjectPropertyAddress {
    AudioObjectPropertyAddress(mSelector: sel, mScope: scope, mElement: kAudioObjectPropertyElementMain)
}

func audioIDs(_ obj: AudioObjectID, _ sel: AudioObjectPropertySelector) -> [AudioObjectID] {
    var a = audioAddr(sel)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(obj, &a, 0, nil, &size) == noErr, size > 0 else { return [] }
    var ids = [AudioObjectID](repeating: 0, count: Int(size) / MemoryLayout<AudioObjectID>.size)
    guard AudioObjectGetPropertyData(obj, &a, 0, nil, &size, &ids) == noErr else { return [] }
    return ids
}

func audioU32(_ obj: AudioObjectID, _ sel: AudioObjectPropertySelector) -> UInt32? {
    var a = audioAddr(sel)
    var v: UInt32 = 0
    var size = UInt32(MemoryLayout<UInt32>.size)
    return AudioObjectGetPropertyData(obj, &a, 0, nil, &size, &v) == noErr ? v : nil
}

func audioString(_ obj: AudioObjectID, _ sel: AudioObjectPropertySelector) -> String? {
    var a = audioAddr(sel)
    var v: Unmanaged<CFString>? = nil
    var size = UInt32(MemoryLayout<Unmanaged<CFString>?>.size)
    guard AudioObjectGetPropertyData(obj, &a, 0, nil, &size, &v) == noErr else { return nil }
    return v?.takeRetainedValue() as String?
}

/// Which apps are recording from a microphone right now (macOS 14.2+ process objects), else: is any input-only
/// device running? Neither asks for microphone permission.
func micInUse() -> (on: Bool, apps: [String]) {
    let sys = AudioObjectID(kAudioObjectSystemObject)
    if #available(macOS 14.2, *) {
        let procs = audioIDs(sys, kAudioHardwarePropertyProcessObjectList)
        if !procs.isEmpty {
            var apps: [String] = []
            for p in procs where audioU32(p, kAudioProcessPropertyIsRunningInput) ?? 0 != 0 {
                apps.append(audioString(p, kAudioProcessPropertyBundleID) ?? "unknown")
            }
            return (!apps.isEmpty, apps)
        }
    }
    for d in audioIDs(sys, kAudioHardwarePropertyDevices) {
        var ia = audioAddr(kAudioDevicePropertyStreams, kAudioObjectPropertyScopeInput)
        var oa = audioAddr(kAudioDevicePropertyStreams, kAudioObjectPropertyScopeOutput)
        var isz: UInt32 = 0, osz: UInt32 = 0
        AudioObjectGetPropertyDataSize(d, &ia, 0, nil, &isz)
        AudioObjectGetPropertyDataSize(d, &oa, 0, nil, &osz)
        // A headset that also plays music would look "running", so only input-only devices count here.
        if isz > 0 && osz == 0 && (audioU32(d, kAudioDevicePropertyDeviceIsRunningSomewhere) ?? 0) != 0 {
            return (true, [])
        }
    }
    return (false, [])
}

// --- apps ----------------------------------------------------------------------------------------------------------

let MEETING_APPS = ["us.zoom.xos": "Zoom", "com.microsoft.teams2": "Teams", "com.microsoft.teams": "Teams",
                    "com.apple.FaceTime": "FaceTime", "com.cisco.webexmeetingsapp": "Webex",
                    "com.webex.meetingmanager": "Webex", "com.tinyspeck.slackmacgap": "Slack",
                    "com.hnc.Discord": "Discord", "com.google.Chrome.app.kjgfgldnnfoeklkmfkjfagphfepbbdan": "Google Meet"]

func runningIDs() -> Set<String> {
    Set(NSWorkspace.shared.runningApplications.compactMap { $0.bundleIdentifier })
}

// --- now playing (Music, Spotify) ----------------------------------------------------------------------------------

let PLAYERS: [(id: String, name: String, script: String)] = [
    ("com.spotify.client", "Spotify",
     "tell application id \"com.spotify.client\"\nif player state is playing then\nreturn \"1||\" & (name of current track) & \" — \" & (artist of current track)\nelse\nreturn \"0||\"\nend if\nend tell"),
    ("com.apple.Music", "Music",
     "tell application id \"com.apple.Music\"\nif player state is playing then\nreturn \"1||\" & (name of current track) & \" — \" & (artist of current track)\nelse\nreturn \"0||\"\nend if\nend tell"),
]

func automationStatus(_ bid: String, ask: Bool) -> String {
    let target = NSAppleEventDescriptor(bundleIdentifier: bid)
    guard let desc = target.aeDesc else { return "unknown" }
    let st = AEDeterminePermissionToAutomateTarget(desc, typeWildCard, typeWildCard, ask)
    switch st {
    case noErr: return "allowed"
    case OSStatus(errAEEventWouldRequireUserConsent): return "needs_permission"
    case OSStatus(errAEEventNotPermitted): return "denied"
    case OSStatus(procNotFound): return "not_running"
    default: return "unknown"
    }
}

func media(running: Set<String>, ask: Bool) -> [[String: Any]] {
    var res: [[String: Any]] = []
    for p in PLAYERS where running.contains(p.id) {
        var row: [String: Any] = ["app": p.name, "id": p.id, "playing": NSNull()]
        let st = automationStatus(p.id, ask: ask)
        row["status"] = st
        if st == "allowed" {
            var err: NSDictionary?
            if let r = NSAppleScript(source: p.script)?.executeAndReturnError(&err).stringValue {
                let parts = r.components(separatedBy: "||")
                row["playing"] = parts.first == "1"
                if parts.first == "1", parts.count > 1, !parts[1].isEmpty { row["title"] = String(parts[1].prefix(120)) }
            } else {
                row["status"] = "script_failed"
            }
        }
        res.append(row)
    }
    return res
}

// --- Focus (needs Full Disk Access) --------------------------------------------------------------------------------

func focus() -> [String: Any] {
    let dir = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/DoNotDisturb/DB")
    let assertions: Data
    do {
        assertions = try Data(contentsOf: dir.appendingPathComponent("Assertions.json"))
    } catch {
        let ns = error as NSError
        let missing = ns.code == NSFileReadNoSuchFileError
        return ["on": NSNull(), "status": missing ? "unknown (no Focus data on this Mac)" : "unknown (needs Full Disk Access)"]
    }
    guard let root = try? JSONSerialization.jsonObject(with: assertions) as? [String: Any] else {
        return ["on": NSNull(), "status": "unknown (unreadable Focus data)"]
    }
    var modeID: String? = nil
    var on = false
    for entry in (root["data"] as? [[String: Any]]) ?? [] {
        for rec in (entry["storeAssertionRecords"] as? [[String: Any]]) ?? [] {
            on = true
            if let det = rec["assertionDetails"] as? [String: Any] {
                modeID = (det["assertionDetailsModeIdentifier"] as? String) ?? modeID
            }
        }
    }
    var res: [String: Any] = ["on": on, "status": "ok"]
    if on, let mid = modeID {
        var name = mid.components(separatedBy: ".").last ?? mid
        if let cd = try? Data(contentsOf: dir.appendingPathComponent("ModeConfigurations.json")),
           let cr = try? JSONSerialization.jsonObject(with: cd) as? [String: Any],
           let first = (cr["data"] as? [[String: Any]])?.first,
           let confs = first["modeConfigurations"] as? [String: Any],
           let conf = confs[mid] as? [String: Any],
           let mode = conf["mode"] as? [String: Any], let n = mode["name"] as? String {
            name = n
        }
        res["mode"] = name
    }
    return res
}

// --- main ----------------------------------------------------------------------------------------------------------

let args = Array(CommandLine.arguments.dropFirst())
if args.first == "--installed" {
    var res: [String: Any] = [:]
    for bid in args.dropFirst() {
        if let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: bid) {
            res[bid] = FileManager.default.displayName(atPath: url.path).replacingOccurrences(of: ".app", with: "")
        } else {
            res[bid] = NSNull()
        }
    }
    out(res)
    exit(0)
}
if args.first == "--help" || args.first == "-h" {
    print("usage: alibi-sense [--ask-media] | --installed BUNDLE_ID ...")
    exit(0)
}

let ask = args.contains("--ask-media")
let running = runningIDs()
let s = sessionInfo()
let disp = displays()
let pw = power()
let cam = cameraInUse()
let mic = micInUse()
var res: [String: Any] = [
    "idle_s": idleSeconds() ?? NSNull(),
    "locked": s.locked || !s.onConsole,
    "display_asleep": disp.asleep,
    "displays": disp.count,
    "on_battery": pw.onBattery ?? NSNull(),
    "battery_pct": pw.pct ?? NSNull(),
    "camera": cam.on, "camera_devices": cam.devices,
    "mic": mic.on, "mic_apps": mic.apps,
    "meeting_apps": MEETING_APPS.filter { running.contains($0.key) }.map { $0.value }.sorted(),
    "media": media(running: running, ask: ask),
    "focus": focus(),
    "ts": Date().timeIntervalSince1970,
]
if let front = NSWorkspace.shared.frontmostApplication { res["front_app"] = front.localizedName ?? NSNull() }
out(res)
