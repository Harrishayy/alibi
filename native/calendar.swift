// alibi-calendar: the only thing in Alibi that touches Apple Calendar (EventKit). JSON in on stdin, JSON out.
// It only ever reads or writes events inside the calendar called "Alibi" (created on first connect).
//
//   alibi-calendar status            -> {"auth":"full|write_only|denied|restricted|not_determined","calendar":{...}|null}
//   alibi-calendar request           -> asks macOS for full calendar access (shows the system prompt once)
//   alibi-calendar ensure            stdin {"title":"Alibi"} -> {"id","title","source","created"}
//   alibi-calendar list              stdin {"calendar_id","from","to"} -> {"events":[{id,title,start,end,notes,url}]}
//   alibi-calendar apply             stdin {"calendar_id","ops":[{"op":"upsert","ref","id"?,"title","start","end",
//                                    "notes"?,"url"?}, {"op":"delete","ref","id"}]} -> {"results":[{ref,id,ok,error?}]}
// Times are Unix seconds. Never prompts except on `request`. Exit 0 with {"error": ...} on a soft failure.
import Foundation
import EventKit

let store = EKEventStore()

func out(_ obj: Any) {
    if let d = try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys]),
       let s = String(data: d, encoding: .utf8) { print(s) } else { print("{\"error\":\"encode\"}") }
}

func fail(_ msg: String, code: Int32 = 0) -> Never { out(["error": msg]); exit(code) }

func authString() -> String {
    let st = EKEventStore.authorizationStatus(for: .event)
    if #available(macOS 14.0, *) {
        switch st {
        case .fullAccess: return "full"
        case .writeOnly: return "write_only"
        case .denied: return "denied"
        case .restricted: return "restricted"
        case .notDetermined: return "not_determined"
        default: return "unknown"
        }
    }
    switch st {
    case .authorized: return "full"
    case .denied: return "denied"
    case .restricted: return "restricted"
    case .notDetermined: return "not_determined"
    default: return "unknown"
    }
}

func readInput() -> [String: Any] {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    if data.isEmpty { return [:] }
    guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { fail("stdin is not a JSON object", code: 2) }
    return obj
}

func calJSON(_ c: EKCalendar) -> [String: Any] {
    ["id": c.calendarIdentifier, "title": c.title, "source": c.source?.title ?? ""]
}

func findCalendar(id: String?, title: String) -> EKCalendar? {
    if let id = id, !id.isEmpty, let c = store.calendar(withIdentifier: id) { return c }
    return store.calendars(for: .event).first { $0.title == title && $0.allowsContentModifications }
}

func requireFull() {
    if authString() != "full" { fail("no_access") }
}

let args = CommandLine.arguments
let cmd = args.count > 1 ? args[1] : "status"

switch cmd {
case "status":
    let auth = authString()
    var cal: Any = NSNull()
    if auth == "full", let c = findCalendar(id: nil, title: "Alibi") { cal = calJSON(c) }
    out(["auth": auth, "calendar": cal])

case "request":
    let sem = DispatchSemaphore(value: 0)
    var granted = false
    var err: String? = nil
    let done: (Bool, Error?) -> Void = { g, e in granted = g; err = e?.localizedDescription; sem.signal() }
    if #available(macOS 14.0, *) {
        store.requestFullAccessToEvents(completion: done)
    } else {
        store.requestAccess(to: .event, completion: done)
    }
    if sem.wait(timeout: .now() + 180) == .timedOut { fail("timed out waiting for the permission prompt") }
    var o: [String: Any] = ["auth": authString(), "granted": granted]
    if let e = err { o["error"] = e }
    out(o)

case "ensure":
    requireFull()
    let input = readInput()
    let title = (input["title"] as? String) ?? "Alibi"
    if let c = findCalendar(id: input["id"] as? String, title: title) {
        var j = calJSON(c); j["created"] = false; out(j); exit(0)
    }
    // Prefer where the person's own events go (usually iCloud, so it shows on their iPhone), then any CalDAV, then local.
    var sources: [EKSource] = []
    if let s = store.defaultCalendarForNewEvents?.source { sources.append(s) }
    sources += store.sources.filter { $0.sourceType == .calDAV && $0.title.lowercased().contains("icloud") }
    sources += store.sources.filter { $0.sourceType == .local }
    sources += store.sources.filter { $0.sourceType == .calDAV }
    var lastErr = "no calendar account found"
    var tried = Set<String>()
    for s in sources where !tried.contains(s.sourceIdentifier) {
        tried.insert(s.sourceIdentifier)
        let c = EKCalendar(for: .event, eventStore: store)
        c.title = title
        c.source = s
        c.cgColor = CGColor(red: 0.96, green: 0.55, blue: 0.16, alpha: 1)
        do {
            try store.saveCalendar(c, commit: true)
            var j = calJSON(c); j["created"] = true; out(j); exit(0)
        } catch { lastErr = error.localizedDescription }
    }
    fail(lastErr)

case "list":
    requireFull()
    let input = readInput()
    guard let c = findCalendar(id: input["calendar_id"] as? String, title: "Alibi") else { fail("no_calendar") }
    let from = Date(timeIntervalSince1970: (input["from"] as? Double) ?? Date().timeIntervalSince1970)
    let to = Date(timeIntervalSince1970: (input["to"] as? Double) ?? Date().timeIntervalSince1970 + 14 * 86400)
    let pred = store.predicateForEvents(withStart: from, end: to, calendars: [c])
    let evs = store.events(matching: pred).map { e -> [String: Any] in
        ["id": e.eventIdentifier ?? "", "title": e.title ?? "", "start": e.startDate.timeIntervalSince1970,
         "end": e.endDate.timeIntervalSince1970, "notes": e.notes ?? "", "url": e.url?.absoluteString ?? ""]
    }
    out(["calendar_id": c.calendarIdentifier, "events": evs])

case "apply":
    requireFull()
    let input = readInput()
    guard let c = findCalendar(id: input["calendar_id"] as? String, title: "Alibi") else { fail("no_calendar") }
    var results: [[String: Any]] = []
    for op in (input["ops"] as? [[String: Any]]) ?? [] {
        let ref = op["ref"] as? String ?? ""
        let id = op["id"] as? String
        do {
            if op["op"] as? String == "delete" {
                if let id = id, let e = store.event(withIdentifier: id), e.calendar.calendarIdentifier == c.calendarIdentifier {
                    try store.remove(e, span: .thisEvent, commit: true)
                }
                results.append(["ref": ref, "id": id ?? "", "ok": true])
                continue
            }
            var e: EKEvent
            if let id = id, let old = store.event(withIdentifier: id), old.calendar.calendarIdentifier == c.calendarIdentifier {
                e = old
            } else {
                e = EKEvent(eventStore: store); e.calendar = c
            }
            if let t = op["title"] as? String { e.title = t }
            if let s = op["start"] as? Double { e.startDate = Date(timeIntervalSince1970: s) }
            if let en = op["end"] as? Double { e.endDate = Date(timeIntervalSince1970: en) }
            if let n = op["notes"] as? String { e.notes = n }
            if let u = op["url"] as? String { e.url = URL(string: u) }
            try store.save(e, span: .thisEvent, commit: true)   // commit per event: new ids are final
            results.append(["ref": ref, "id": e.eventIdentifier ?? "", "ok": true])
        } catch {
            results.append(["ref": ref, "id": id ?? "", "ok": false, "error": error.localizedDescription])
        }
    }
    out(["results": results])

default:
    fail("unknown command \(cmd)", code: 2)
}
