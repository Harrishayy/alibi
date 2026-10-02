// Pinch.swift: the SwiftUI port of Pinch, Alibi's green detective lobster. Shared by the macOS island, the iPhone app
// and the Live Activity, so it imports SwiftUI only and has no top-level statements.
//
// Source of truth is the web rig in docs/design/pinch: pinch.svg (art), rig.json (params, pivots), clips.json (moods,
// clips, blink, policy) and rig.js (param -> transform mapping). gen_swift.py compiles the first three into
// PinchData.swift; this file ports rig.js and the engine rules line for line, so a pose renders the same on both.
//
//   PinchFigure(pose:size:dark:)                     pure drawing, LOD by size (full / no legs / lod24 / 20 and 16 glyphs)
//   PinchView(mood:clip:clipID:size:dark:)           animated: mood loop + one-shot clips + blink + idle gaze
//   PinchView(..., ambient: true)                    + fidgets and no rest while visible (ambient Pinches only)
//   PinchView.pose(mood:clip:ms:)                    deterministic frame for renders and tests
//   PinchView.fidgetPose(_:ms:)                      a fidget's frame over the idle key pose (still renders)
//   PinchPose.still("sideeye")                       a mood's or clip's key frame by name (Live Activity content state)
import SwiftUI

// MARK: - Names

/// Held, looping states (the server's `pinch.mood`).
enum PinchMood: String, CaseIterable, Sendable {
    case idle, focused, listening, thinking, sleepy, reading
    var motion: PinchMotion { PinchMotions.mood(self) }
}

/// One-shot moments (the server's `pinch.event`).
enum PinchClip: String, CaseIterable, Sendable {
    case hello, sideeye, nudge, celebrate, partial, supportive, surprise, connected
    var motion: PinchMotion { PinchMotions.clip(self) }
    /// Higher pre-empts lower, even inside the cooldown (clips.json policy).
    var priority: Int { motion.priority }
}

/// Ambient life: short param tracks an ambient Pinch plays now and then in the idle mood, so a
/// Pinch with nothing to report still looks alive. Client-side like blink and gaze, not a mood. They sit under clips,
/// never touch the clip cooldown or priority, and never drive lensGlow (the lens glows only while the camera samples).
/// The keyframes mirror the web engine's (pinch.js); change both together.
enum PinchFidget: String, CaseIterable, Sendable {
    case inspect, perk, glance, click

    var motion: PinchMotion {
        switch self {
        case .inspect: return PinchFidget.data[0]
        case .perk: return PinchFidget.data[1]
        case .glance: return PinchFidget.data[2]
        case .click: return PinchFidget.data[3]
        }
    }

    /// The frame a still render shows: where the fidget reads best.
    var peak: Double {
        switch self {
        case .inspect: return 800
        case .perk: return 300
        case .glance: return 600
        case .click: return 410
        }
    }

    /// The first fidget comes this long after the view appears; then one every `every` (uniform, seeded per view).
    static let first: ClosedRange<Double> = 6000...10000
    static let every: ClosedRange<Double> = 14000...28000

    static let data: [PinchMotion] = [
        // inspect: the lens comes up to the eye, one glint sweeps the glass, a small lean toward it
        PinchMotion(loop: false, dur: 1600, key: 800, priority: 0, tracks: [
            PinchTrack(.lens, [(0, 0, .out), (420, 0.92, .out), (1150, 0.92, .out), (1600, 0, .inOut)]),
            PinchTrack(.glint, [(0, 0, .out), (520, 0, .out), (980, 1, .inOut), (981, 0, .step)]),
            PinchTrack(.lookX, [(0, 0, .out), (420, 0.2, .out), (1150, 0.2, .out), (1600, 0, .inOut)]),
        ]),
        // perk: antennae flick up, eyes widen, a small hop of the body
        PinchMotion(loop: false, dur: 700, key: 300, priority: 0, tracks: [
            PinchTrack(.antennaLift, [(0, 0, .out), (140, -3, .anticip), (300, 9, .overshoot), (700, 0, .settle)]),
            PinchTrack(.eyeOpen, [(0, 1, .out), (220, 1.1, .out), (600, 1, .out)]),
            PinchTrack(.bodySquash, [(0, 1, .out), (140, 0.97, .anticip), (300, 1.03, .overshoot), (600, 1, .settle)]),
        ]),
        // glance: a look left, then right, then back
        PinchMotion(loop: false, dur: 1800, key: 600, priority: 0, tracks: [
            PinchTrack(.lookX, [(0, 0, .out), (260, -0.55, .out), (760, -0.55, .out), (1060, 0.5, .inOut),
                                (1500, 0.5, .out), (1800, 0, .inOut)]),
            PinchTrack(.lookY, [(0, 0, .out), (260, -0.1, .out), (1500, -0.1, .out), (1800, 0, .inOut)]),
        ]),
        // click: the crusher comes up and clicks twice
        PinchMotion(loop: false, dur: 1100, key: 410, priority: 0, tracks: [
            PinchTrack(.clawL, [(0, 0, .out), (150, -6, .anticip), (320, 14, .overshoot), (800, 10, .out),
                                (1100, 0, .settle)]),
            PinchTrack(.pinchL, [(320, 0, .out), (410, 1, .out), (540, 0, .out), (630, 1, .out), (760, 0, .out)]),
        ]),
    ]
}

// MARK: - Motion data types (filled by PinchData.swift)

/// clips.json easing: cubic-bezier, SwiftUI-style spring(duration ms, bounce), linear or step.
enum PinchEase: Sendable, Equatable {
    case linear, step
    case bezier(Double, Double, Double, Double)
    case spring(Double, Double)

    /// rig.js `ease(name, t, segMs, elapsedMs)`.
    func value(_ t: Double, elapsedMs: Double) -> Double {
        switch self {
        case .linear: return t
        case .step: return t >= 1 ? 1 : 0
        case let .bezier(x1, y1, x2, y2): return PinchEase.solve(x1, y1, x2, y2, t)
        case let .spring(dur, bounce): return t >= 1 ? 1 : PinchEase.spring(dur, bounce, elapsedMs)
        }
    }

    /// Newton with a bisection fallback, exactly as rig.js does it.
    static func solve(_ x1: Double, _ y1: Double, _ x2: Double, _ y2: Double, _ x: Double) -> Double {
        if x <= 0 { return 0 }
        if x >= 1 { return 1 }
        func calc(_ t: Double, _ p1: Double, _ p2: Double) -> Double {
            ((((1 - 3 * p2 + 3 * p1) * t + (3 * p2 - 6 * p1)) * t) + 3 * p1) * t
        }
        func slope(_ t: Double, _ p1: Double, _ p2: Double) -> Double {
            3 * (1 - 3 * p2 + 3 * p1) * t * t + 2 * (3 * p2 - 6 * p1) * t + 3 * p1
        }
        var t = x
        for _ in 0..<8 {
            let s = slope(t, x1, x2)
            if abs(s) < 1e-6 { break }
            t -= (calc(t, x1, x2) - x) / s
        }
        if t < 0 || t > 1 {
            var lo = 0.0, hi = 1.0
            t = x
            for _ in 0..<30 {
                if calc(t, x1, x2) < x { lo = t } else { hi = t }
                t = (lo + hi) / 2
            }
        }
        return calc(t, y1, y2)
    }

    /// SwiftUI-compatible spring(duration, bounce) on real elapsed time: omega = 2pi/duration, damping = 1 - bounce.
    static func spring(_ durMs: Double, _ bounce: Double, _ elapsedMs: Double) -> Double {
        let t = max(0, elapsedMs) / 1000, w = 2 * Double.pi / (durMs / 1000), z = 1 - bounce
        if z >= 1 { return 1 - exp(-w * t) * (1 + w * t) }
        let wd = w * (1 - z * z).squareRoot()
        return 1 - exp(-z * w * t) * (cos(wd * t) + (z * w / wd) * sin(wd * t))
    }
}

struct PinchKey: Sendable {
    let t: Double
    let v: Double
    let ease: PinchEase
}

struct PinchTrack: Sendable {
    let param: PinchParam
    let keys: [PinchKey]
    init(_ param: PinchParam, _ keys: [(Double, Double, PinchEase)]) {
        self.param = param
        self.keys = keys.map { PinchKey(t: $0.0, v: $0.1, ease: $0.2) }
    }

    /// rig.js `sampleTrack`: hold before the first key, ease into each key, hold after the last; shapes step.
    func sample(_ ms: Double) -> Double {
        guard let first = keys.first else { return param.rest }
        if ms <= first.t { return first.v }
        for i in 1..<keys.count {
            let a = keys[i - 1], b = keys[i]
            if ms < b.t {
                if param == .mouth { return a.v }
                let seg = b.t - a.t == 0 ? 1 : b.t - a.t
                return a.v + (b.v - a.v) * b.ease.value((ms - a.t) / seg, elapsedMs: ms - a.t)
            }
        }
        return keys[keys.count - 1].v
    }
}

struct PinchMotion: Sendable {
    let loop: Bool
    let dur: Double
    let key: Double
    let priority: Int
    let tracks: [PinchTrack]

    func drives(_ p: PinchParam) -> Bool { tracks.contains { $0.param == p } }

    /// Writes every track at `ms` into `pose`, mixed by `weight` (the mouth snaps at 50 %).
    func apply(to pose: inout PinchPose, ms: Double, weight: Double = 1) {
        guard weight > 0 else { return }
        let t = loop ? (ms.truncatingRemainder(dividingBy: dur) + dur).truncatingRemainder(dividingBy: dur) : ms
        for tr in tracks {
            let v = tr.sample(t)
            if weight >= 1 {
                pose[tr.param] = v
            } else if tr.param == .mouth {
                if weight >= 0.5 { pose[tr.param] = v }
            } else {
                pose[tr.param] += (v - pose[tr.param]) * weight
            }
        }
    }
}

// MARK: - Art data types (filled by PinchData.swift)

enum PinchInk: UInt8, Sendable { case body, belly, shade, eye, shine, lens, lensGlow, spark, blush, glint, silhouette, bloom }

enum PinchOutline: UInt8, Sendable {
    case none
    case paintOrder   // .o: a 2*ow outline stroke under the fill
    case underlay     // .u: a stroke (base + 2*ow) under a same-path line
}

struct PinchShape: @unchecked Sendable {   // Path is an immutable value; the generated shapes are never mutated
    let path: Path
    let fill: PinchInk?
    let stroke: PinchInk?
    let width: CGFloat
    let outline: PinchOutline
    let outlineBase: CGFloat
    let cap: CGLineCap
    let join: CGLineJoin
    let evenOdd: Bool
    let strokeOpacity: Double
    let gradient: Bool
}

/// One SVG element. Children are the nodes `index + 1 ..< end`.
struct PinchNode: Sendable {
    let part: PinchPart?
    let lod: Int          // 40: hidden below 40 pt, 96: hidden below 96 pt
    let opacity: Double
    let transform: CGAffineTransform
    let clip: Int         // index into the tree's clips, or -1
    let shape: Int        // index into the tree's shapes, or -1 for a group
    let end: Int
}

// MARK: - Pose helpers

extension PinchPose {
    /// a -> b by w for every numeric param; the mouth switches at 50 %.
    static func mix(_ a: PinchPose, _ b: PinchPose, _ w: Double) -> PinchPose {
        if w <= 0 { return a }
        if w >= 1 { return b }
        var out = a
        for p in PinchParam.allCases where p != .mouth { out[p] = a[p] + (b[p] - a[p]) * w }
        out.mouth = w >= 0.5 ? b.mouth : a.mouth
        return out
    }

    /// A mood or clip by name at `ms` (its key frame when nil) over the rest pose: the web `seek(name, ms)`.
    /// Unknown names give the idle key frame, so a stale Live Activity state still draws a calm Pinch.
    static func seek(_ name: String, ms: Double? = nil) -> PinchPose {
        var p = PinchPose()
        if let m = PinchMood(rawValue: name) {
            m.motion.apply(to: &p, ms: ms ?? m.motion.key)
        } else if let c = PinchClip(rawValue: name) {
            c.motion.apply(to: &p, ms: ms ?? c.motion.key)
        }
        return p
    }

    /// The key frame of a mood or clip by name, for still surfaces (Live Activity, widgets, app icon).
    static func still(_ name: String) -> PinchPose { seek(name) }

    /// The camera light as a switch (the placeholder API the island was built against): on means lensGlow 1.
    var lensLit: Bool {
        get { lensGlow >= 0.5 }
        set { lensGlow = newValue ? 1 : 0 }
    }

    /// Placeholder-API name for bodySquash.
    var squash: Double {
        get { bodySquash }
        set { bodySquash = newValue }
    }
}

// MARK: - Rig (rig.js `apply`)

private enum PinchAffine {
    static func mul(_ m: CGAffineTransform, _ n: CGAffineTransform) -> CGAffineTransform { n.concatenating(m) } // m·n, n first
    static func T(_ x: Double, _ y: Double) -> CGAffineTransform { CGAffineTransform(translationX: x, y: y) }
    static func R(_ deg: Double, _ c: CGPoint = .zero) -> CGAffineTransform {
        let r = deg * .pi / 180, cs = cos(r), sn = sin(r)
        let rot = CGAffineTransform(a: cs, b: sn, c: -sn, d: cs, tx: 0, ty: 0)
        return mul(mul(T(c.x, c.y), rot), T(-c.x, -c.y))
    }
    static func S(_ sx: Double, _ sy: Double, _ c: CGPoint) -> CGAffineTransform {
        mul(mul(T(c.x, c.y), CGAffineTransform(scaleX: sx, y: sy)), T(-c.x, -c.y))
    }
    static func clamp(_ v: Double, _ a: Double = 0, _ b: Double = 1) -> Double { max(a, min(b, v)) }
    static func smooth(_ a: Double, _ b: Double, _ v: Double) -> Double {
        let t = clamp((v - a) / (b - a))
        return t * t * (3 - 2 * t)
    }
}

/// Every part's transform and opacity for one pose.
struct PinchRigFrame {
    var xf: [CGAffineTransform] = PinchArt.restTransform
    var op: [Double] = PinchArt.restOpacity

    subscript(x part: PinchPart) -> CGAffineTransform {
        get { xf[part.rawValue] }
        set { xf[part.rawValue] = newValue }
    }
    subscript(o part: PinchPart) -> Double {
        get { op[part.rawValue] }
        set { op[part.rawValue] = PinchAffine.clamp(newValue) }
    }

    init(glyphLit: Bool) { self[o: .glyphGlow] = glyphLit ? 1 : 0 }

    init(pose p: PinchPose, ms: Double) {
        typealias A = PinchAffine
        typealias G = PinchGeom
        // root: squash about the feet with volume kept, then tilt (+ gaze lean), then bodyY
        let sy = p.bodySquash, sx = 1 / sy.squareRoot()
        self[x: .pinchRoot] = A.mul(A.mul(A.T(0, p.bodyY), A.R(p.tilt + G.lookLean * p.lookX, G.feet)), A.S(sx, sy, G.feet))

        // antennae: lift is mirrored, sway is same-direction (the right one at 0.85)
        self[x: .antennaL] = A.R(p.antennaLift + p.antennaSway, G.antennaL)
        self[x: .antennaR] = A.R(-p.antennaLift + 0.85 * p.antennaSway, G.antennaR)

        // eyes: gaze translate, >1 eyeOpen scales up, joy crossfades to ^ ^
        let cEye = A.clamp(1 - p.eyeOpen), es = max(1, p.eyeOpen)
        var eyeR = CGAffineTransform.identity
        for left in [true, false] {
            let c = left ? G.eyeL : G.eyeR
            let m = A.mul(A.T(p.lookX * G.look.width, p.lookY * G.look.height), A.S(es, es, c))
            let lid = left ? p.lidL : p.lidR, brow = left ? -p.browL : p.browR
            let cov = A.clamp(1 - (1 - cEye) * (1 - lid))
            let lidT = A.mul(A.T(0, cov * G.lidSpan), A.R(brow, CGPoint(x: c.x, y: left ? G.lidEdgeL : G.lidEdgeR)))
            if left {
                self[x: .eyeL] = m; self[x: .lidL] = lidT; self[o: .lidLLash] = cov / 0.06
                self[o: .eyeLOpen] = 1 - p.joy; self[o: .eyeLJoy] = p.joy
            } else {
                eyeR = m
                self[x: .eyeR] = m; self[x: .lidR] = lidT; self[o: .lidRLash] = cov / 0.06
                self[o: .eyeROpen] = 1 - p.joy; self[o: .eyeRJoy] = p.joy
                self[x: .lensLid] = lidT; self[o: .lensLidLash] = cov / 0.06; self[o: .lensEyeROpen] = 1 - p.joy
            }
        }

        // mouth: one of four shapes; smile height scales with mouthCurve (never below -0.2: no frowns)
        self[o: .mouthSmile] = p.mouth == .smile ? 1 : 0
        self[o: .mouthFlat] = p.mouth == .flat ? 1 : 0
        self[o: .mouthOpen] = p.mouth == .open ? 1 : 0
        self[o: .mouthO] = p.mouth == .o ? 1 : 0
        let mc = A.clamp(p.mouthCurve, -0.2, 1.4)
        self[x: .mouthSmile] = A.mul(A.T(0, G.smileY * (1 - mc)), CGAffineTransform(scaleX: 1, y: mc))
        self[x: .mouth] = A.R(p.mouthTilt, G.mouth)
        self[o: .blush] = p.blush

        // arms and claws: + raises on both sides; the lens macro adds its IK angles to the right side
        let L = A.clamp(p.lens)
        let armL = p.clawL, armR = -p.clawR + L * G.lensRaiseArm
        let clawL = G.clawFollow * p.clawL + p.wristL, clawR = -G.clawFollow * p.clawR - p.wristR + L * G.lensRaiseClaw
        self[x: .armL] = A.R(armL, G.shoulderL)
        self[x: .armR] = A.R(armR, G.shoulderR)
        self[x: .clawL] = A.R(clawL, G.wristL)
        self[x: .clawR] = A.R(clawR, G.wristR)
        for left in [true, false] {
            let v = A.clamp(p.pinch + (left ? p.pinchL : p.pinchR), -1, 1)
            let top = v >= 0 ? v * G.jawTopClose : -v * G.jawTopOpen
            let bot = v >= 0 ? v * G.jawBottomClose : -v * G.jawBottomOpen
            self[x: left ? .jawLTop : .jawRTop] = A.R(top, G.jawTop)
            self[x: left ? .jawLBottom : .jawRBottom] = A.R(bot, G.jawBottom)
        }

        // lens: slide along the handle, zoom about the glass, tuck away about the grip
        let out = A.clamp(p.lensOut), tuck = 1 - 0.35 * out
        let lensM = A.mul(A.mul(A.T(L * G.lensRaiseSlide.width, L * G.lensRaiseSlide.height), A.S(p.lensZoom, p.lensZoom, G.glass)),
                          A.S(tuck, tuck, G.grip))
        self[x: .lens] = lensM
        self[o: .lens] = 1 - out
        self[o: .lensRing] = p.lensGlow
        self[o: .lensWash] = p.lensGlow
        let gl = A.clamp(p.glint), sw = (2 * gl - 1) * 1.25 * G.glassR * 0.7071
        self[x: .lensSweep] = A.T(-sw, sw)
        self[o: .lensSweep] = sin(.pi * gl)
        // the magnified eye behind the glass: what is behind the lens, scaled about the glass centre
        let view = A.smooth(0.72, 0.96, L)
        self[o: .lensView] = view
        if view > 0 {
            let W = A.mul(A.mul(A.R(armR, G.shoulderR), A.R(clawR, G.wristR)), lensM)
            let gw = G.glass.applying(W)
            self[x: .lensEye] = A.mul(A.mul(W.inverted(), A.S(G.lensMag, G.lensMag, gw)), eyeR)
        }
        self[o: .paper] = p.paper

        // effects
        self[o: .sweat] = p.sweat
        self[x: .sweat] = A.T(0, 3.5 * (A.clamp(p.sweat) - 1))
        let spk = A.clamp(p.sparkle)
        self[o: .sparkle] = spk * 1.6
        self[x: .sparkle] = A.S(0.72 + 0.34 * spk, 0.72 + 0.34 * spk, G.sparkleC)
        self[o: .bloom] = p.bloom
        self[x: .bloom] = A.S(0.8 + 0.2 * p.bloom, 0.8 + 0.2 * p.bloom, G.bloom)
        self[o: .zzz] = p.zzz
        let ph = (max(0, ms).truncatingRemainder(dividingBy: G.zzzPeriod)) / G.zzzPeriod
        let zs: [PinchPart] = [.z0, .z1, .z2]
        for i in 0..<3 {
            let q = (ph + Double(i) / 3).truncatingRemainder(dividingBy: 1)
            self[x: zs[i]] = A.T(5 * q, -11 * q)
            self[o: zs[i]] = sin(.pi * q)
        }
    }
}

// MARK: - Renderer

private struct PinchInks {
    let palette: PinchPalette
    let dark: Bool
    let rim: Bool
    let tint: Color?

    var outline: Color? { dark ? (rim ? palette.outline : nil) : palette.outline }

    func color(_ ink: PinchInk) -> Color {
        switch ink {
        case .body: return palette.body
        case .belly: return palette.belly
        case .shade: return palette.shade
        case .eye: return palette.eye
        case .shine: return palette.shine
        case .lens: return palette.lens
        case .lensGlow: return palette.lensGlow
        case .spark: return palette.spark
        case .blush: return palette.blush
        case .glint: return dark ? palette.shine : palette.shade
        case .silhouette: return tint ?? palette.body
        case .bloom: return palette.bloom
        }
    }
}

private struct PinchTree {
    let nodes: [PinchNode]
    let shapes: [PinchShape]
    let clips: [Path]
    let viewBox: CGFloat

    static let full = PinchTree(nodes: PinchArt.fullNodes, shapes: PinchArt.fullShapes, clips: PinchArt.fullClips,
                                viewBox: PinchArt.fullViewBox)
    static let glyph16 = PinchTree(nodes: PinchArt.glyph16Nodes, shapes: PinchArt.glyph16Shapes,
                                   clips: PinchArt.glyph16Clips, viewBox: PinchArt.glyph16ViewBox)
    static let glyph20 = PinchTree(nodes: PinchArt.glyph20Nodes, shapes: PinchArt.glyph20Shapes,
                                   clips: PinchArt.glyph20Clips, viewBox: PinchArt.glyph20ViewBox)
}

/// Level of detail by rendered size (SPEC.md): full art at 96+, no legs and outline 3.6 at 40–95, the lod24 cut
/// (no tail, blush or belly lines, outline 5.5) at 24–39, and the static silhouette glyphs below 24.
enum PinchLOD: Equatable, Sendable {
    case full, noLegs, lod24, glyph20, glyph16

    init(size: CGFloat) {
        switch size {
        case 96...: self = .full
        case 40..<96: self = .noLegs
        case 24..<40: self = .lod24
        case 20..<24: self = .glyph20
        default: self = .glyph16
        }
    }

    var isGlyph: Bool { self == .glyph16 || self == .glyph20 }
    fileprivate var outlineWidth: CGFloat { self == .full ? 3 : (self == .noLegs ? 3.6 : 5.5) }
    fileprivate func hides(_ lod: Int) -> Bool {
        switch self {
        case .full: return false
        case .noLegs: return lod == 96
        default: return lod != 0
        }
    }
}

private enum PinchRenderer {
    static func draw(_ tree: PinchTree, frame: PinchRigFrame, lod: PinchLOD, inks: PinchInks, in ctx: GraphicsContext) {
        draw(tree, 0..<tree.nodes.count, frame, lod, inks, ctx)
    }

    private static func draw(_ tree: PinchTree, _ range: Range<Int>, _ f: PinchRigFrame, _ lod: PinchLOD,
                             _ inks: PinchInks, _ ctx: GraphicsContext) {
        var i = range.lowerBound
        while i < range.upperBound {
            let n = tree.nodes[i]
            defer { i = n.end }
            if n.lod != 0 && lod.hides(n.lod) { continue }
            var o = n.opacity, xf = n.transform
            if let part = n.part {
                o *= f.op[part.rawValue]
                xf = f.xf[part.rawValue]
            }
            if o <= 0.002 { continue }
            var c = ctx
            if !xf.isIdentity { c.concatenate(xf) }
            if n.clip >= 0 { c.clip(to: tree.clips[n.clip]) }
            if n.shape >= 0 {
                if o < 1 { c.opacity *= o }
                drawShape(tree.shapes[n.shape], lod, inks, &c)
            } else if o < 0.998 {
                // SVG group opacity composites the group once, so overlapping children don't double up
                c.opacity *= o
                c.drawLayer { layer in draw(tree, (i + 1)..<n.end, f, lod, inks, layer) }
            } else {
                draw(tree, (i + 1)..<n.end, f, lod, inks, c)
            }
        }
    }

    private static func drawShape(_ s: PinchShape, _ lod: PinchLOD, _ inks: PinchInks, _ c: inout GraphicsContext) {
        if s.outline != .none, let ol = inks.outline {
            let ow = lod.outlineWidth
            if s.outline == .paintOrder {
                c.stroke(s.path, with: .color(ol), style: StrokeStyle(lineWidth: 2 * ow, lineCap: .butt, lineJoin: .round))
            } else {
                c.stroke(s.path, with: .color(ol), style: StrokeStyle(lineWidth: s.outlineBase + 2 * ow, lineCap: s.cap,
                                                                      lineJoin: .miter, miterLimit: 4))
            }
        }
        if let fill = s.fill {
            if s.gradient {
                let r = s.path.boundingRect
                let col = inks.color(fill)
                c.fill(s.path, with: .radialGradient(Gradient(colors: [col, col.opacity(0)]),
                                                     center: CGPoint(x: r.midX, y: r.midY), startRadius: 0,
                                                     endRadius: r.width / 2),
                       style: FillStyle(eoFill: s.evenOdd))
            } else {
                c.fill(s.path, with: .color(inks.color(fill)), style: FillStyle(eoFill: s.evenOdd))
            }
        }
        if let stroke = s.stroke {
            let col = inks.color(stroke)
            c.stroke(s.path, with: .color(s.strokeOpacity < 1 ? col.opacity(s.strokeOpacity) : col),
                     style: StrokeStyle(lineWidth: s.width, lineCap: s.cap, lineJoin: s.join))
        }
    }
}

// MARK: - PinchFigure

/// Pinch drawn in one pose inside a `size` × `size` box. Pure drawing: no state, no timers.
/// Hops and raised claws may draw up to 15 % outside the box (the SVG is overflow: visible); layout stays `size`.
struct PinchFigure: View {
    var pose: PinchPose
    var size: CGFloat
    var dark: Bool = true
    /// Recolours the silhouette glyph (below 24 pt) by state: on task, idle, phone, absent. The lens keeps its colour.
    var tint: Color? = nil
    /// Dark theme only: draw the #8FD400 rim instead of no outline.
    var rim: Bool = false
    /// Engine time in ms; only the zzz drift reads it.
    var time: Double = 0

    static let overscan: CGFloat = 0.15

    var body: some View {
        let lod = PinchLOD(size: size)
        let pad = lod.isGlyph ? 0 : (size * Self.overscan).rounded(.up)
        let pose = pose, time = time
        let inks = PinchInks(palette: dark ? .dark : .light, dark: dark, rim: rim, tint: tint)
        Canvas { ctx, _ in
            let tree: PinchTree
            let frame: PinchRigFrame
            switch lod {
            case .glyph16: tree = .glyph16; frame = PinchRigFrame(glyphLit: pose.lensGlow >= 0.5)
            case .glyph20: tree = .glyph20; frame = PinchRigFrame(glyphLit: pose.lensGlow >= 0.5)
            default: tree = .full; frame = PinchRigFrame(pose: pose, ms: time)
            }
            var c = ctx
            c.translateBy(x: pad, y: pad)
            c.scaleBy(x: size / tree.viewBox, y: size / tree.viewBox)
            PinchRenderer.draw(tree, frame: frame, lod: lod, inks: inks, in: c)
        }
        .frame(width: size + 2 * pad, height: size + 2 * pad)
        .frame(width: size, height: size)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text("Pinch"))
        .accessibilityAddTraits(.isImage)
    }
}

// MARK: - PinchView

/// Pinch for a mood, with one-shot clips on top (bump `clipID` to replay the same clip).
///
/// Layers, as in the web engine: the mood loops on engine time, a clip blends in over 120 ms and out over 240 ms, blink
/// multiplies eyeOpen every 3–6 s (skipped while a clip drives the eyes), idle glances drift the gaze. The lens glow is
/// max(camera, motion), so the lens never says the camera is off while it samples. A clip is dropped inside the 90 s
/// cooldown unless it outranks the last one or `force` is set; sideeye chains into nudge.
/// The TimelineView only exists while Pinch is visible, moving and not resting (2 min without news); reduced motion,
/// `still` and sizes under 24 pt draw key frames and crossfade between them instead.
/// `ambient` (off by default) is for a Pinch that sits in view with nothing to report (the island's Today panel): it
/// never rests while visible and, in the idle mood at 40 pt and up, plays a fidget now and then (PinchFidget).
struct PinchView: View {
    var mood: PinchMood = .idle
    var clip: PinchClip? = nil
    var clipID: Int = 0
    var size: CGFloat = 96
    var dark: Bool = true
    /// The host's camera state: lights the lens.
    var camera: Bool = false
    /// Bypass the cooldown (verdict clips).
    var force: Bool = false
    /// Key frames only, no loop, breath or blink.
    var still: Bool = false
    /// Extra gaze, -1…1 on both axes (the web `lookAt`).
    var look: CGSize = .zero
    var tint: Color? = nil
    var rim: Bool = false
    /// Ambient life: no 2-minute rest while visible, and idle fidgets (sizes 40 and up). Off keeps the old behaviour.
    var ambient: Bool = false

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var engine = PinchEngine()
    @State private var visible = false

    private struct ClipKey: Equatable { let clip: PinchClip?; let id: Int }

    var body: some View {
        Group {
            if animating {
                TimelineView(.animation) { tl in
                    let ms = engine.ms(at: tl.date)
                    PinchFigure(pose: compose(at: tl.date), size: size, dark: dark, tint: tint, rim: rim, time: ms)
                }
                .transition(.opacity)
            } else {
                ZStack {
                    PinchFigure(pose: stillPose, size: size, dark: dark, tint: tint, rim: rim)
                        .id(stillKey)
                        .transition(.opacity)
                }
                .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.2), value: stillKey)
        .animation(.easeInOut(duration: 0.2), value: animating)
        .frame(width: size, height: size)
        .accessibilityLabel(Text("Pinch, \(engine.play?.clip.rawValue ?? mood.rawValue)"))
        .onAppear {
            visible = true
            engine.wake()
            if let clip { start(clip, force: force) }
        }
        .onDisappear { visible = false }
        .onChange(of: ClipKey(clip: clip, id: clipID)) { _, key in
            if let c = key.clip { start(c, force: force) }
        }
        .onChange(of: mood) { old, _ in
            engine.moodFrom = old
            engine.moodChanged = Date()
            engine.wake()
        }
        .onChange(of: look) { old, _ in      // a new host gaze eases in like a glance, from wherever the eyes are
            engine.lookFrom = engine.look(at: Date(), to: old)
            engine.lookChanged = Date()
        }
        .task(id: engine.token) {
            guard let play = engine.play else { return }
            let left = play.clip.motion.dur + PinchMotions.blendOut - Date().timeIntervalSince(play.start) * 1000
            if left > 0 { try? await Task.sleep(nanoseconds: UInt64(left * 1_000_000)) }
            guard !Task.isCancelled, engine.play?.start == play.start else { return }
            engine.play = nil
            engine.fading = nil
            if let next = PinchMotions.chain(after: play.clip) { start(next, force: true) }
        }
        .task(id: engine.activity) {
            try? await Task.sleep(nanoseconds: UInt64(PinchMotions.restAfter * 1_000_000))
            if !Task.isCancelled && !ambient { engine.resting = true }   // an ambient Pinch never rests while visible
        }
    }

    private var animating: Bool {
        visible && !reduceMotion && !still && !engine.resting && !PinchLOD(size: size).isGlyph
    }

    private var stillKey: String {
        "\(engine.play?.clip.rawValue ?? mood.rawValue)|\(camera)"
    }

    /// Key frame of the playing clip, else of the mood (reduced motion, still, resting, glyph sizes).
    private var stillPose: PinchPose {
        var p = Self.pose(mood: mood, clip: engine.play?.clip, ms: engine.play?.clip.motion.key ?? mood.motion.key)
        if camera { p.lensGlow = max(p.lensGlow, 1) }
        return p
    }

    private func start(_ c: PinchClip, force: Bool) {
        let now = Date()
        let pri = c.priority
        if !force, let last = engine.lastClipAt, now.timeIntervalSince(last) * 1000 < PinchMotions.cooldown,
           pri <= engine.lastPriority {
            return   // equal or lower inside the cooldown: dropped, not queued
        }
        if let cur = engine.play, now.timeIntervalSince(cur.start) * 1000 < cur.clip.motion.dur + PinchMotions.blendOut {
            engine.fading = cur
            engine.fadeStart = now
        }
        engine.play = PinchPlay(clip: c, start: now)
        engine.lastPlay = engine.play
        engine.lastClipAt = now
        engine.lastPriority = pri
        engine.token &+= 1
        engine.wake()
    }

    /// Mood (crossfaded on change) + idle gaze + clip layers + blink + camera, at `date`.
    private func compose(at date: Date) -> PinchPose {
        let t = engine.ms(at: date)
        var p = PinchPose()
        mood.motion.apply(to: &p, ms: t)
        var moodW = 1.0
        if let from = engine.moodFrom, from != mood {
            let k = date.timeIntervalSince(engine.moodChanged) * 1000 / 260
            if k < 1 {
                moodW = PinchEase.out.value(k, elapsedMs: 0)
                var a = PinchPose()
                from.motion.apply(to: &a, ms: t)
                p = PinchPose.mix(a, p, moodW)
            }
        }
        if PinchMotions.gazeMoods.contains(mood) {
            let g = engine.gaze(t)
            p.lookX += g.width * moodW
            p.lookY += g.height * moodW
        }
        let lk = engine.look(at: date, to: look)
        p.lookX = max(-1, min(1, p.lookX + lk.width))
        p.lookY = max(-1, min(1, p.lookY + lk.height))

        var eyesDriven = false
        // Ambient fidget: absolute values under any clip, in the idle mood only (it fades with the mood crossfade).
        if ambient && size >= 40, let f = engine.fidget(t) {
            let idleW = mood == .idle ? moodW : (engine.moodFrom == .idle ? 1 - moodW : 0)
            let w = fidgetWeight(f.fidget, start: f.start, at: t) * idleW
            if w > 0 {
                f.fidget.motion.apply(to: &p, ms: min(t - f.start, f.fidget.motion.dur), weight: w)
                if f.fidget.motion.drives(.eyeOpen) { eyesDriven = true }   // no blink through a perk
            }
        }
        for (play, fade) in [(engine.fading, true), (engine.play, false)] {
            guard let play else { continue }
            let m = play.clip.motion
            let e = date.timeIntervalSince(play.start) * 1000
            var w = min(1, max(0, e / PinchMotions.blendIn))
            if e > m.dur { w *= max(0, 1 - (e - m.dur) / PinchMotions.blendOut) }
            if fade { w *= max(0, 1 - date.timeIntervalSince(engine.fadeStart) * 1000 / PinchMotions.blendOut) }
            guard w > 0 else { continue }
            m.apply(to: &p, ms: min(e, m.dur), weight: w)
            if m.drives(.eyeOpen) || m.drives(.joy) { eyesDriven = true }
        }
        if !eyesDriven { p.eyeOpen *= engine.blink(t) }
        if camera { p.lensGlow = max(p.lensGlow, 1) }
        return p
    }

    /// A fidget's mix at engine time `t`: in over 120 ms, out over 240 ms after its last key. A clip pre-empts it: one
    /// that starts during the fidget fades it out over 120 ms, and one still playing when the fidget is due skips it.
    private func fidgetWeight(_ f: PinchFidget, start s: Double, at t: Double) -> Double {
        let e = t - s, dur = f.motion.dur
        var w = min(1, max(0, e / PinchMotions.blendIn))
        if e > dur { w *= max(0, 1 - (e - dur) / PinchMotions.blendOut) }
        if let c = engine.lastPlay {
            let cs = engine.ms(at: c.start)
            if cs >= s { w *= min(1, max(0, 1 - (t - cs) / PinchMotions.blendIn)) }
            else if cs + c.clip.motion.dur + PinchMotions.blendOut > s { w = 0 }
        }
        return w
    }

    /// A fidget at `ms` over the idle key pose, for still renders and checks (unknown names give the idle key pose).
    static func fidgetPose(_ name: String, ms: Double) -> PinchPose {
        var p = pose(mood: .idle, clip: nil, ms: PinchMood.idle.motion.key)
        PinchFidget(rawValue: name)?.motion.apply(to: &p, ms: ms)
        return p
    }

    /// The pose at `ms` into `clip` over the mood's key frame, or the mood itself at `ms` (loop time) when `clip`
    /// is nil. Deterministic: no blink, gaze or blend, so it matches the web `seek` for the idle mood.
    static func pose(mood: PinchMood, clip: PinchClip?, ms: Double) -> PinchPose {
        var p = PinchPose()
        if let clip {
            mood.motion.apply(to: &p, ms: mood.motion.key)
            clip.motion.apply(to: &p, ms: ms)
        } else {
            mood.motion.apply(to: &p, ms: ms)
        }
        return p
    }
}

private struct PinchPlay: Equatable {
    let clip: PinchClip
    let start: Date
}

/// Per-view engine state. Blink and gaze are pure functions of engine time and a per-view seed, so they need no timers.
private struct PinchEngine {
    var born = Date()
    var seed = UInt64.random(in: 1...UInt64.max)
    var moodFrom: PinchMood?
    var moodChanged = Date.distantPast
    var play: PinchPlay?
    var fading: PinchPlay?
    var fadeStart = Date.distantPast
    var lastClipAt: Date?
    var lastPlay: PinchPlay?   // the last clip started, kept after it ends (a fidget it overlapped stays skipped)
    var lookFrom = CGSize.zero
    var lookChanged = Date.distantPast
    var lastPriority = 0
    var token = 0
    var activity = 0
    var resting = false

    func ms(at date: Date) -> Double { date.timeIntervalSince(born) * 1000 }

    mutating func wake() {
        activity &+= 1
        resting = false
    }

    /// 0..<1 from (seed, slot, salt): splitmix64.
    private func rand(_ slot: Int, _ salt: UInt64) -> Double {
        var z = seed &+ UInt64(bitPattern: Int64(slot)) &* 0x9E37_79B9_7F4A_7C15 &+ salt &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        z ^= z >> 31
        return Double(z >> 11) / Double(1 << 53)
    }

    /// eyeOpen multiplier: one blink per slot, spaced 3–6 s apart, 15 % of them doubled.
    func blink(_ t: Double) -> Double {
        let every = PinchMotions.blinkEvery
        let slot = (every.lowerBound + every.upperBound) / 2, jitter = (every.upperBound - every.lowerBound) / 4
        let b = PinchMotions.blink, k = Int((t / slot).rounded(.down))
        var f = 1.0
        for j in [k - 1, k, k + 1] where j > 0 {
            let s = Double(j) * slot + (rand(j, 1) * 2 - 1) * jitter
            var local = t - s
            if local >= 0 && local < b.dur {
                var q = PinchPose(); b.apply(to: &q, ms: local); f = min(f, q.eyeOpen)
            }
            local -= b.dur + PinchMotions.blinkDoubleGap
            if rand(j, 2) < PinchMotions.blinkDoubleChance && local >= 0 && local < b.dur {
                var q = PinchPose(); b.apply(to: &q, ms: local); f = min(f, q.eyeOpen)
            }
        }
        return f
    }

    /// The host gaze (`look`) at `date`: eases from `lookFrom` to `target` over a glance's 420 ms after a change, and
    /// is exactly `target` otherwise.
    func look(at date: Date, to target: CGSize) -> CGSize {
        let k = date.timeIntervalSince(lookChanged) * 1000 / PinchMotions.gazeDur
        if k >= 1 { return target }
        let e = PinchMotions.gazeEase.value(max(0, k), elapsedMs: 0)
        return CGSize(width: lookFrom.width + (target.width - lookFrom.width) * e,
                      height: lookFrom.height + (target.height - lookFrom.height) * e)
    }

    /// The fidget due at engine time `t` (still playing or fading out) and its start, else nil. A pure function of the
    /// seed, like blink and gaze: the first 6–10 s in, then one every 14–28 s, in a seeded shuffle of the four with no
    /// repeat back to back.
    func fidget(_ t: Double) -> (fidget: PinchFidget, start: Double)? {
        let a = PinchFidget.first, b = PinchFidget.every
        var s = a.lowerBound + rand(0, 6) * (a.upperBound - a.lowerBound)
        var k = 0
        while s <= t && k < 100_000 {
            let f = fidgetOrder(k)
            if t < s + f.motion.dur + PinchMotions.blendOut { return (f, s) }
            k += 1
            s += b.lowerBound + rand(k, 7) * (b.upperBound - b.lowerBound)
        }
        return nil
    }

    /// The k-th fidget: cycles of four in a seeded order; a cycle never starts with the one the last cycle ended on.
    private func fidgetOrder(_ k: Int) -> PinchFidget {
        let c = k / 4
        var order = fidgetCycle(c)
        if c > 0 && order[0] == fidgetCycle(c - 1)[3] { order.swapAt(0, 1) }
        return PinchFidget.allCases[order[k % 4]]
    }

    private func fidgetCycle(_ c: Int) -> [Int] {
        var a = [0, 1, 2, 3]
        for i in stride(from: 3, to: 0, by: -1) {
            a.swapAt(i, min(i, Int(rand(c, UInt64(20 + i)) * Double(i + 1))))
        }
        return a
    }

    /// Idle glance: every 4–8 s the gaze eases to a new point in the clips.json ranges and holds there.
    func gaze(_ t: Double) -> CGSize {
        let every = PinchMotions.gazeEvery
        let slot = (every.lowerBound + every.upperBound) / 2, jitter = (every.upperBound - every.lowerBound) / 4
        func at(_ j: Int) -> Double { j <= 0 ? Double(j) * slot : Double(j) * slot + (rand(j, 3) * 2 - 1) * jitter }
        func target(_ j: Int) -> CGSize {
            guard j > 0 else { return .zero }
            let x = PinchMotions.gazeX, y = PinchMotions.gazeY
            return CGSize(width: x.lowerBound + rand(j, 4) * (x.upperBound - x.lowerBound),
                          height: y.lowerBound + rand(j, 5) * (y.upperBound - y.lowerBound))
        }
        let k = Int((t / slot).rounded(.down))
        guard let j = [k + 1, k, k - 1].first(where: { at($0) <= t }) else { return .zero }
        let a = target(j - 1), b = target(j)
        let e = PinchMotions.gazeEase.value(min(1, (t - at(j)) / PinchMotions.gazeDur), elapsedMs: t - at(j))
        return CGSize(width: a.width + (b.width - a.width) * e, height: a.height + (b.height - a.height) * e)
    }
}
