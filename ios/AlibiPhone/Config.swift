// Shared configuration, storage and small helpers for the Alibi iPhone companion.
// Mac address + key come from Generated/AlibiConfig.plist, written by ios/build_install.sh from data/secrets.json.
import Foundation
import SwiftUI

/// One events row as the Mac expects it: {source, kind, ts, payload}. See docs/SIGNALS.md.
typealias Row = [String: Any]

func row(_ source: String, _ kind: String, ts: Double = Date().timeIntervalSince1970, _ payload: [String: Any]) -> Row {
    ["source": source, "kind": kind, "ts": ts, "payload": payload]
}

enum Config {
    static let appGroup = "group.app.theultras.alibi"
    static let dict: [String: Any] = {
        guard let url = Bundle.main.url(forResource: "AlibiConfig", withExtension: "plist"),
              let d = NSDictionary(contentsOf: url) as? [String: Any] else { return [:] }
        return d
    }()
    /// Full ingest URLs (…/ingest), best first.
    static var endpoints: [String] { dict["endpoints"] as? [String] ?? [] }
    static var key: String { dict["key"] as? String ?? "" }
    static var macName: String { dict["mac_name"] as? String ?? "your Mac" }
    static var configured: Bool { !key.isEmpty && !endpoints.isEmpty }

    /// Same host as an ingest URL, different path (e.g. /api/phone/session).
    static func sibling(of ingest: String, path: String) -> URL? {
        guard var c = URLComponents(string: ingest) else { return nil }
        var p = c.path
        if p.hasSuffix("/ingest") { p.removeLast("/ingest".count) }
        c.path = p + path
        c.query = nil
        return c.url
    }
}

/// UserDefaults shared with the (future) Screen Time extensions through the App Group; falls back to standard.
enum Store {
    static let d: UserDefaults = UserDefaults(suiteName: Config.appGroup) ?? .standard

    static func double(_ k: String) -> Double { d.double(forKey: k) }
    static func set(_ v: Any?, _ k: String) { d.set(v, forKey: k) }

    /// Per-stream toggles (default on).
    static func enabled(_ stream: String) -> Bool { d.object(forKey: "stream.\(stream).on") as? Bool ?? true }
    static func setEnabled(_ stream: String, _ on: Bool) { d.set(on, forKey: "stream.\(stream).on") }

    /// When this stream last delivered rows to the Mac.
    static func lastSent(_ stream: String) -> Date? {
        let t = d.double(forKey: "stream.\(stream).sent")
        return t > 0 ? Date(timeIntervalSince1970: t) : nil
    }
    static func markSent(_ stream: String, at: Date = Date()) { d.set(at.timeIntervalSince1970, forKey: "stream.\(stream).sent") }

    static var appSupport: URL {
        let base = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: Config.appGroup)
            ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base
    }
}

enum Fmt {
    static let day: DateFormatter = {
        let f = DateFormatter(); f.calendar = Calendar(identifier: .gregorian); f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"; return f
    }()
    static let hm: DateFormatter = {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "HH:mm"; return f
    }()
    static func ago(_ d: Date?) -> String {
        guard let d else { return "never" }
        let s = Date().timeIntervalSince(d)
        if s < 60 { return "just now" }
        if s < 3600 { return "\(Int(s / 60)) min ago" }
        if Calendar.current.isDateInToday(d) { return "at " + d.formatted(date: .omitted, time: .shortened) }
        return d.formatted(.dateTime.weekday(.abbreviated).hour().minute())
    }
    static func r(_ v: Double, _ places: Int = 1) -> Double {
        let m = pow(10, Double(places)); return (v * m).rounded() / m
    }
}
