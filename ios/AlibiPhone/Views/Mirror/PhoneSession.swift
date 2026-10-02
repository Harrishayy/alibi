// What `GET /api/phone/session` returns (alibi/integrations.py session_info), decoded leniently: every field is
// optional and a wrong type drops that one field rather than the reply, so older Macs (the flat coupling keys only)
// still decode. Read by Today, Week and the Live Activity controller (Views/Live).
import Foundation

struct PhoneSession: Decodable, Equatable {
    struct Live: Decodable, Equatable {
        var id: Int?; var habit: String?; var habit_label: String?; var modality: String?
        var started_at: Double?; var ends_at: Double?; var declared_min: Int?; var on_break: Bool?
        var on_task_ratio: Double?; var last_label: String?; var nudges: Int?
        /// When on a break, when it ends. The Mac sends `on_break` as `{until, left_s}` (older builds a Bool).
        var break_until: Double?
        /// Non-nil means drifting. The Mac sends `{label, since_s}` (older builds a Bool; `true` decodes to an empty one).
        var drifting: Drifting?

        private struct BreakInfo: Decodable { var until: Double?; var left_s: Double? }

        struct Drifting: Decodable, Equatable {
            var label: String?          // "phone", "off_task", "absent"
            var since_s: Double?        // seconds the drift has lasted
        }

        private enum K: String, CodingKey {
            case id, habit, habit_label, modality, started_at, ends_at, declared_min, on_break, on_task_ratio, last_label
            case nudges, drifting
        }

        init(id: Int? = nil, habit: String? = nil, habit_label: String? = nil, started_at: Double? = nil,
             ends_at: Double? = nil, declared_min: Int? = nil, on_break: Bool? = nil, on_task_ratio: Double? = nil,
             last_label: String? = nil, nudges: Int? = nil, drifting: Drifting? = nil) {
            self.id = id; self.habit = habit; self.habit_label = habit_label; self.started_at = started_at
            self.ends_at = ends_at; self.declared_min = declared_min; self.on_break = on_break
            self.on_task_ratio = on_task_ratio; self.last_label = last_label; self.nudges = nudges; self.drifting = drifting
        }

        init(from d: Decoder) throws {
            let c = try d.container(keyedBy: K.self)
            id = c.lenientInt(.id); habit = c.lenient(.habit); habit_label = c.lenient(.habit_label)
            modality = c.lenient(.modality); started_at = c.lenientDouble(.started_at); ends_at = c.lenientDouble(.ends_at)
            declared_min = c.lenientInt(.declared_min)
            if let b: Bool = c.lenient(.on_break) {
                on_break = b
            } else if let o: BreakInfo = c.lenient(.on_break) {
                on_break = true; break_until = o.until
            }
            on_task_ratio = c.lenientDouble(.on_task_ratio); last_label = c.lenient(.last_label); nudges = c.lenientInt(.nudges)
            if let o: Drifting = c.lenient(.drifting) {
                drifting = o
            } else if let b: Bool = c.lenient(.drifting), b {
                drifting = Drifting()
            }
        }

        /// Flat aliases for the drift wrapper (Views/Live reads these).
        var drift_label: String? { drifting?.label }
        var drift_since_s: Double? { drifting?.since_s }

        var start: Date? { started_at.map { Date(timeIntervalSince1970: $0) } }
        var end: Date? { ends_at.map { Date(timeIntervalSince1970: $0) } }
        var title: String { habit_label ?? habit?.capitalized ?? "Session" }
    }

    struct Pinch: Decodable, Equatable {
        var mood: String?; var event: String?; var seq: Int?; var age_s: Double?; var line: String?; var ref: String?
        private enum K: String, CodingKey { case mood, event, seq, age_s, line, ref }
        init(mood: String? = nil, event: String? = nil, seq: Int? = nil, age_s: Double? = nil, line: String? = nil) {
            self.mood = mood; self.event = event; self.seq = seq; self.age_s = age_s; self.line = line
        }
        init(from d: Decoder) throws {
            let c = try d.container(keyedBy: K.self)
            mood = c.lenient(.mood); event = c.lenient(.event); seq = c.lenientInt(.seq)
            age_s = c.lenientDouble(.age_s); line = c.lenient(.line); ref = c.lenient(.ref)
        }
    }

    struct Verdict: Decodable, Equatable {
        var id: Int?; var habit: String?; var habit_label: String?; var verdict: String?
        var on_task_ratio: Double?; var ended_at: Double?; var summary: String?
        private enum K: String, CodingKey { case id, habit, habit_label, verdict, on_task_ratio, ratio, ended_at, summary }
        init(from d: Decoder) throws {
            let c = try d.container(keyedBy: K.self)
            id = c.lenientInt(.id); habit = c.lenient(.habit); habit_label = c.lenient(.habit_label)
            verdict = c.lenient(.verdict); on_task_ratio = c.lenientDouble(.on_task_ratio) ?? c.lenientDouble(.ratio)
            ended_at = c.lenientDouble(.ended_at); summary = c.lenient(.summary)
        }
        var title: String { habit_label ?? habit?.capitalized ?? "Session" }
        var ended: Date? { ended_at.map { Date(timeIntervalSince1970: $0) } }
        /// The Mac calls it `ratio` here; both names read the same value.
        var ratio: Double? { on_task_ratio }
    }

    struct Today: Decodable, Equatable {
        var habits_done: Int?; var habits_total: Int?; var verified_min: Double?; var declared_min: Double?
        private enum K: String, CodingKey { case habits_done, habits_total, verified_min, declared_min }
        init(from d: Decoder) throws {
            let c = try d.container(keyedBy: K.self)
            habits_done = c.lenientInt(.habits_done); habits_total = c.lenientInt(.habits_total)
            verified_min = c.lenientDouble(.verified_min); declared_min = c.lenientDouble(.declared_min)
        }
    }

    struct PlanNext: Decodable, Equatable {
        var habit: String?; var starts_at: Date?
        private enum K: String, CodingKey { case habit, starts_at }
        init(from d: Decoder) throws {
            let c = try d.container(keyedBy: K.self)
            habit = c.lenient(.habit)
            if let t = c.lenientDouble(.starts_at) { starts_at = Date(timeIntervalSince1970: t) }
            else if let s: String = c.lenient(.starts_at) { starts_at = ISO8601DateFormatter().date(from: s) }
        }
    }

    /// This week (Monday to now) per habit: minutes claimed, minutes Alibi saw, the weekly target and whether it's on
    /// pace (`status` "aligned" or "behind"). From the Mac's weekly report (alibi/report.py build_json rows).
    struct Week: Decodable, Equatable {
        struct Habit: Decodable, Equatable {
            var habit: String?; var label: String?; var claimed_min: Int?; var seen_min: Int?; var target_min: Int?
            var status: String?
            private enum K: String, CodingKey { case habit, label, claimed_min, seen_min, target_min, status }
            init(from d: Decoder) throws {
                let c = try d.container(keyedBy: K.self)
                habit = c.lenient(.habit); label = c.lenient(.label); claimed_min = c.lenientInt(.claimed_min)
                seen_min = c.lenientInt(.seen_min); target_min = c.lenientInt(.target_min); status = c.lenient(.status)
            }
        }
        var week_start: Double?; var claimed_min: Int?; var seen_min: Int?; var habits: [Habit]?
        private enum K: String, CodingKey { case week_start, claimed_min, seen_min, habits }

        /// One malformed habit drops that habit, not the week.
        private struct Maybe: Decodable {
            let value: Habit?
            init(from d: Decoder) throws { value = try? Habit(from: d) }
        }

        init(from d: Decoder) throws {
            let c = try d.container(keyedBy: K.self)
            week_start = c.lenientDouble(.week_start); claimed_min = c.lenientInt(.claimed_min)
            seen_min = c.lenientInt(.seen_min)
            habits = (c.lenient(.habits) as [Maybe]?)?.compactMap(\.value)
        }

        var start: Date? { week_start.map { Date(timeIntervalSince1970: $0) } }
        /// Totals: the Mac's, or summed from the habits when an older Mac sends only those.
        var claimed: Int { claimed_min ?? (habits ?? []).reduce(0) { $0 + ($1.claimed_min ?? 0) } }
        var seen: Int { seen_min ?? (habits ?? []).reduce(0) { $0 + ($1.seen_min ?? 0) } }
    }

    // Flat coupling keys (SyncEngine reads these too).
    var active: Bool?; var label: String?; var ends_at: Double?; var on_break: Bool?
    var session: Live?
    var today: Today?
    var recent_verdict: Verdict?
    var streak_days: Int?
    var plan_next: PlanNext?
    var week: Week?
    var pinch: Pinch?

    private enum K: String, CodingKey {
        case active, label, ends_at, on_break, session, today, recent_verdict, streak_days, plan_next, week, pinch
    }

    init(active: Bool? = nil, session: Live? = nil, pinch: Pinch? = nil) {
        self.active = active; self.session = session; self.pinch = pinch
    }

    init(from d: Decoder) throws {
        let c = try d.container(keyedBy: K.self)
        active = c.lenient(.active); label = c.lenient(.label); ends_at = c.lenientDouble(.ends_at); on_break = c.lenient(.on_break)
        session = c.lenient(.session); today = c.lenient(.today); recent_verdict = c.lenient(.recent_verdict)
        streak_days = c.lenientInt(.streak_days); plan_next = c.lenient(.plan_next); week = c.lenient(.week)
        pinch = c.lenient(.pinch)
    }

    /// The live session, also when only the flat keys came back (older Mac): enough for the habit and the end time.
    var live: Live? {
        if let session { return session }
        guard active == true else { return nil }
        return Live(habit_label: label, ends_at: ends_at, on_break: on_break)
    }

    static func decode(_ data: Data) -> PhoneSession? { try? JSONDecoder().decode(PhoneSession.self, from: data) }
}

extension Optional where Wrapped == PhoneSession.Live.Drifting {
    /// `live.drifting == true` reads as "is drifting": a non-nil wrapper means true.
    static func == (lhs: Self, rhs: Bool) -> Bool { (lhs != nil) == rhs }
}

/// A number or a string (the Mac sends some fields either way).
enum JSONNumberOrString: Decodable, Equatable {
    case number(Double), string(String)
    init(from d: Decoder) throws {
        let c = try d.singleValueContainer()
        if let v = try? c.decode(Double.self) { self = .number(v) } else { self = .string(try c.decode(String.self)) }
    }
    var double: Double? { if case .number(let v) = self { v } else { Double(stringValue) } }
    var stringValue: String { switch self { case .number(let v): String(v); case .string(let s): s } }
}

extension KeyedDecodingContainer {
    /// Decode one key or nil: a missing key, a null or a wrong type all give nil instead of failing the reply.
    func lenient<T: Decodable>(_ k: Key) -> T? { (try? decodeIfPresent(T.self, forKey: k)) ?? nil }
    func lenientDouble(_ k: Key) -> Double? {
        if let v: Double = lenient(k) { return v }
        if let s: String = lenient(k) { return Double(s) }
        return nil
    }
    func lenientInt(_ k: Key) -> Int? {
        if let v: Int = lenient(k) { return v }
        return lenientDouble(k).flatMap { $0.isFinite ? Int($0) : nil }
    }
}
