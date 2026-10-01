#!/usr/bin/env python3
"""Generate PinchData.swift from Pinch's web sources so the SwiftUI rig and the web rig stay identical.

Inputs (all next to this file, plus the token sheet):
  pinch.svg          full art: part tree, paths, classes, clips, LOD classes
  pinch-lod16.svg    16 pt silhouette glyph
  pinch-lod20.svg    20 pt silhouette glyph
  rig.json           params (defaults, ranges) and rig geometry
  clips.json         moods, clips, blink, easings, policy
  ../tokens/tokens.css   pinch-* colours for the dark and light themes

Output: PinchData.swift (declarations only, SwiftUI + Foundation, no top-level statements).
Never hand-edit PinchData.swift; edit the sources (or build_pinch.py) and rerun:

    python3 docs/design/pinch/gen_swift.py

pinch-lod24.svg is not read: it is pinch.svg with the .lod-40 and .lod-96 elements removed, which the Swift
renderer reproduces from the LOD flags on the full tree (the generator checks that claim).
"""
import json
import math
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
SVG_NS = "{http://www.w3.org/2000/svg}"
OUT = HERE / "PinchData.swift"


# ---------------------------------------------------------------- helpers
def num(v):
    """Swift literal for a float: short, stable, no exponent."""
    v = float(v)
    if abs(v) < 5e-7:
        v = 0.0
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return s


def camel(name):
    parts = re.split(r"[-_]", name)
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def mat_mul(m, n):
    """SVG matrix product m·n ([a b c d e f]); n is applied first."""
    return [m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1], m[0] * n[2] + m[2] * n[3],
            m[1] * n[2] + m[3] * n[3], m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5]]


IDENT = [1, 0, 0, 1, 0, 0]


def parse_transform(s):
    if not s:
        return IDENT
    m = IDENT
    for fn, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s):
        a = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if fn == "translate":
            t = [1, 0, 0, 1, a[0], a[1] if len(a) > 1 else 0]
        elif fn == "scale":
            t = [a[0], 0, 0, a[1] if len(a) > 1 else a[0], 0, 0]
        elif fn == "rotate":
            r = math.radians(a[0])
            c, si = math.cos(r), math.sin(r)
            t = [c, si, -si, c, 0, 0]
            if len(a) == 3:
                t = mat_mul(mat_mul([1, 0, 0, 1, a[1], a[2]], t), [1, 0, 0, 1, -a[1], -a[2]])
        elif fn == "matrix":
            t = a
        else:
            raise SystemExit("unsupported transform " + fn)
        m = mat_mul(m, t)
    return m


# ---------------------------------------------------------------- path data -> absolute ops
TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def arc_to_cubics(x1, y1, rx, ry, phi, fa, fs, x2, y2):
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        return [("L", x2, y2)]
    rx, ry = abs(rx), abs(ry)
    p = math.radians(phi)
    cp, sp = math.cos(p), math.sin(p)
    dx2, dy2 = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx2 + sp * dy2, -sp * dx2 + cp * dy2
    lam = x1p * x1p / (rx * rx) + y1p * y1p / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    numr = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(0.0, numr / den)) if den else 0.0
    if fa == fs:
        coef = -coef
    cxp, cyp = coef * rx * y1p / ry, -coef * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a

    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not fs and dt > 0:
        dt -= 2 * math.pi
    elif fs and dt < 0:
        dt += 2 * math.pi
    n = max(1, int(math.ceil(abs(dt) / (math.pi / 2) - 1e-9)))
    d = dt / n
    k = 4 / 3 * math.tan(d / 4)
    out = []

    def pt(ux, uy):
        return cx + rx * cp * ux - ry * sp * uy, cy + rx * sp * ux + ry * cp * uy

    a = t1
    for i in range(n):
        b = a + d
        c1 = pt(math.cos(a) - k * math.sin(a), math.sin(a) + k * math.cos(a))
        c2 = pt(math.cos(b) + k * math.sin(b), math.sin(b) - k * math.cos(b))
        e = pt(math.cos(b), math.sin(b)) if i < n - 1 else (x2, y2)
        out.append(("C", c1[0], c1[1], c2[0], c2[1], e[0], e[1]))
        a = b
    return out


def parse_d(d):
    toks = TOKEN.findall(d)
    i, cmd = 0, None
    x = y = sx = sy = 0.0
    last_c = last_q = None
    ops = []

    def nxt():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                ops.append(("Z",))
                x, y = sx, sy
                last_c = last_q = None
                continue
        rel = cmd.islower()
        C = cmd.upper()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if C == "M":
            x, y = ox + nxt(), oy + nxt()
            sx, sy = x, y
            ops.append(("M", x, y))
            cmd = "l" if rel else "L"
            last_c = last_q = None
        elif C == "L":
            x, y = ox + nxt(), oy + nxt()
            ops.append(("L", x, y))
            last_c = last_q = None
        elif C == "H":
            x = ox + nxt()
            ops.append(("L", x, y))
            last_c = last_q = None
        elif C == "V":
            y = oy + nxt()
            ops.append(("L", x, y))
            last_c = last_q = None
        elif C == "C":
            c1x, c1y, c2x, c2y, ex, ey = (ox + nxt(), oy + nxt(), ox + nxt(), oy + nxt(), ox + nxt(), oy + nxt())
            ops.append(("C", c1x, c1y, c2x, c2y, ex, ey))
            x, y, last_c, last_q = ex, ey, (c2x, c2y), None
        elif C == "S":
            c1x, c1y = (2 * x - last_c[0], 2 * y - last_c[1]) if last_c else (x, y)
            c2x, c2y, ex, ey = ox + nxt(), oy + nxt(), ox + nxt(), oy + nxt()
            ops.append(("C", c1x, c1y, c2x, c2y, ex, ey))
            x, y, last_c, last_q = ex, ey, (c2x, c2y), None
        elif C == "Q":
            qx, qy, ex, ey = ox + nxt(), oy + nxt(), ox + nxt(), oy + nxt()
            ops.append(("Q", qx, qy, ex, ey))
            x, y, last_q, last_c = ex, ey, (qx, qy), None
        elif C == "T":
            qx, qy = (2 * x - last_q[0], 2 * y - last_q[1]) if last_q else (x, y)
            ex, ey = ox + nxt(), oy + nxt()
            ops.append(("Q", qx, qy, ex, ey))
            x, y, last_q, last_c = ex, ey, (qx, qy), None
        elif C == "A":
            rx, ry, phi, fa, fs = nxt(), nxt(), nxt(), nxt(), nxt()
            ex, ey = ox + nxt(), oy + nxt()
            ops.extend(arc_to_cubics(x, y, rx, ry, phi, int(fa), int(fs), ex, ey))
            x, y = ex, ey
            last_c = last_q = None
        else:
            raise SystemExit("unsupported path command " + cmd)
    return ops


def swift_path_body(ops):
    lines = []
    for op in ops:
        k = op[0]
        if k == "M":
            lines.append("p.move(to: .init(x: %s, y: %s))" % (num(op[1]), num(op[2])))
        elif k == "L":
            lines.append("p.addLine(to: .init(x: %s, y: %s))" % (num(op[1]), num(op[2])))
        elif k == "Q":
            lines.append("p.addQuadCurve(to: .init(x: %s, y: %s), control: .init(x: %s, y: %s))"
                         % (num(op[3]), num(op[4]), num(op[1]), num(op[2])))
        elif k == "C":
            lines.append("p.addCurve(to: .init(x: %s, y: %s), control1: .init(x: %s, y: %s), control2: .init(x: %s, y: %s))"
                         % (num(op[5]), num(op[6]), num(op[1]), num(op[2]), num(op[3]), num(op[4])))
        elif k == "Z":
            lines.append("p.closeSubpath()")
    return lines


def shape_path(el):
    """Swift statements that build the element's geometry into `p`."""
    tag = el.tag.replace(SVG_NS, "")
    g = lambda k, d=0.0: float(el.get(k, d))
    if tag == "path":
        return swift_path_body(parse_d(el.get("d")))
    if tag == "circle":
        r = g("r")
        return ["p.addEllipse(in: CGRect(x: %s, y: %s, width: %s, height: %s))"
                % (num(g("cx") - r), num(g("cy") - r), num(2 * r), num(2 * r))]
    if tag == "ellipse":
        rx, ry = g("rx"), g("ry")
        return ["p.addEllipse(in: CGRect(x: %s, y: %s, width: %s, height: %s))"
                % (num(g("cx") - rx), num(g("cy") - ry), num(2 * rx), num(2 * ry))]
    if tag == "rect":
        rx = g("rx")
        return ["p.addRoundedRect(in: CGRect(x: %s, y: %s, width: %s, height: %s), cornerSize: CGSize(width: %s, height: %s))"
                % (num(g("x")), num(g("y")), num(g("width")), num(g("height")), num(rx), num(rx))]
    raise SystemExit("unsupported shape " + tag)


# ---------------------------------------------------------------- styles
INK_BY_VAR = {
    "--pinch-body": "body", "--pinch-belly": "belly", "--pinch-shade": "shade", "--pinch-eye": "eye",
    "--pinch-shine": "shine", "--pinch-lens": "lens", "--pinch-lens-glow": "lensGlow", "--pinch-spark": "spark",
    "--pinch-blush": "blush", "--p-glint": "glint", "--pinch-silhouette": "silhouette",
}
FILL_CLASS = {"fb": "body", "fy": "belly", "fs": "shade", "fe": "eye", "fw": "shine", "fl": "lens",
              # glyph classes
              "ps": "silhouette", "pl": "lens", "pe": "eye", "pw": "shine", "pg": "spark"}
STROKE_CLASS = {"sb": "body", "ss": "shade", "se": "eye", "sy": "belly", "sl": "lens"}


def style_map(el):
    out = {}
    for decl in (el.get("style") or "").split(";"):
        if ":" in decl:
            k, v = decl.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def ink_of(value):
    m = re.match(r"var\((--[\w-]+)", value or "")
    if not m or m.group(1) not in INK_BY_VAR:
        raise SystemExit("unknown colour " + str(value))
    return INK_BY_VAR[m.group(1)]


# ---------------------------------------------------------------- svg -> node list
class Tree:
    def __init__(self, name, part_attr):
        self.name = name
        self.part_attr = part_attr       # callable(el) -> part name or None
        self.nodes = []                  # dicts, pre-order
        self.shapes = []                 # list of (statements, style dict)
        self.clips = {}                  # id -> statements
        self.clip_order = []
        self.parts = {}                  # part -> {"opacity": rest, "transform": rest}


def collect_clips(root, tree):
    for cp in root.iter(SVG_NS + "clipPath"):
        body = []
        for ch in cp:
            body += shape_path(ch)
        tree.clips[cp.get("id")] = body
        tree.clip_order.append(cp.get("id"))


def walk(el, tree, inherited_fill, depth=0):
    tag = el.tag.replace(SVG_NS, "")
    if tag in ("style", "defs", "clipPath", "title", "desc", "radialGradient", "linearGradient"):
        return
    cls = (el.get("class") or "").split()
    st = style_map(el)
    part = tree.part_attr(el)
    lod = 96 if "lod-96" in cls else (40 if "lod-40" in cls else 0)
    opacity = float(el.get("opacity", 1))
    xf = parse_transform(el.get("transform"))
    clip = None
    if el.get("clip-path"):
        clip = re.match(r"url\(#([^)]+)\)", el.get("clip-path")).group(1)
    node = {"part": part, "lod": lod, "opacity": opacity, "transform": xf, "clip": clip, "shape": None}
    if part:
        if part in tree.parts:
            raise SystemExit("duplicate part " + part)
        tree.parts[part] = {"opacity": opacity, "transform": xf}
        node["opacity"], node["transform"] = 1.0, IDENT   # the rig owns a part's transform and opacity
    fill = inherited_fill
    if "fill" in st:
        fill = ink_of(st["fill"])
    idx = len(tree.nodes)
    tree.nodes.append(node)
    if tag == "g" or tag == "svg":
        for ch in el:
            walk(ch, tree, fill, depth + 1)
    else:
        s = {"fill": None, "stroke": None, "width": float(el.get("stroke-width", 1)), "outline": "none",
             "outlineBase": 0.0, "cap": "butt", "join": "miter", "evenOdd": el.get("fill-rule") == "evenodd",
             "fillOpacity": 1.0, "strokeOpacity": float(el.get("stroke-opacity", 1)), "gradient": False}
        # fill: explicit class > style > inherited; .k and .u remove it
        f = None
        for c in cls:
            if c in FILL_CLASS:
                f = FILL_CLASS[c]
        if f is None and "fill" in st:
            f = ink_of(st["fill"])
        if f is None and el.get("fill", "").startswith("url("):
            s["gradient"] = True
            f = "bloom"
        if f is None:
            f = fill
        if "k" in cls or "u" in cls:
            f = None
        s["fill"] = f
        if "k" in cls:
            s["cap"], s["join"] = "round", "round"
            for c in cls:
                if c in STROKE_CLASS:
                    s["stroke"] = STROKE_CLASS[c]
            if "stroke" in st:
                s["stroke"] = ink_of(st["stroke"])
            if s["stroke"] is None:
                raise SystemExit("stroke class without colour in " + tree.name)
        if "u" in cls:
            s["outline"] = "underlay"
            s["cap"] = "round"
            m = re.match(r"calc\(([\d.]+)\s*\+\s*2\*var\(--pinch-ow", st.get("stroke-width", ""))
            if not m:
                raise SystemExit("u without calc stroke-width")
            s["outlineBase"] = float(m.group(1))
        if "o" in cls:
            s["outline"] = "paintOrder"
        if st.get("stroke-linecap"):
            s["cap"] = st["stroke-linecap"]
        tree.shapes.append((shape_path(el), s))
        node["shape"] = len(tree.shapes) - 1
    node["end"] = len(tree.nodes)
    tree.nodes[idx] = node


def load_tree(path, name, part_attr):
    root = ET.parse(path).getroot()
    tree = Tree(name, part_attr)
    collect_clips(root, tree)
    for ch in root:
        walk(ch, tree, None)
    return tree


# ---------------------------------------------------------------- tokens
def theme_block(css, theme):
    m = re.search(r'\[data-theme="%s"\]\s*\{(.*?)\n\}' % theme, css, re.S)
    if not m:
        raise SystemExit("no %s block in tokens.css" % theme)
    vals = dict(re.findall(r"--([\w-]+):\s*([^;]+);", m.group(1)))
    return vals


def swift_color(v):
    v = v.strip()
    m = re.match(r"#([0-9a-fA-F]{6})$", v)
    if m:
        h = m.group(1)
        r, g, b, a = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0
    else:
        m = re.match(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)", v)
        if not m:
            raise SystemExit("unsupported colour " + v)
        r, g, b, a = int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))
    return "Color(.sRGB, red: %s, green: %s, blue: %s, opacity: %s)" % (
        num(r / 255), num(g / 255), num(b / 255), num(a))


PALETTE_KEYS = [("body", "pinch-body"), ("belly", "pinch-belly"), ("shade", "pinch-shade"),
                ("outline", "pinch-outline"), ("eye", "pinch-eye"), ("shine", "pinch-shine"),
                ("blush", "pinch-blush"), ("spark", "pinch-spark"), ("lens", "pinch-lens"),
                ("lensGlow", "pinch-lens-glow"), ("bloom", "bloom")]


# ---------------------------------------------------------------- emit
def emit():
    rig = json.loads((HERE / "rig.json").read_text())
    clips = json.loads((HERE / "clips.json").read_text())
    css = (HERE.parent / "tokens" / "tokens.css").read_text()

    full = load_tree(HERE / "pinch.svg", "full", lambda el: el.get("data-part"))
    glyph_part = lambda el: "glyph-glow" if el.get("id") == "lens-glow" else None
    g16 = load_tree(HERE / "pinch-lod16.svg", "glyph16", glyph_part)
    g20 = load_tree(HERE / "pinch-lod20.svg", "glyph20", glyph_part)

    # lod24 check: every data-part in pinch-lod24.svg exists in the full tree, and the full tree only adds LOD-flagged ones
    lod24 = ET.parse(HERE / "pinch-lod24.svg").getroot()
    p24 = {el.get("data-part") for el in lod24.iter() if el.get("data-part")}
    lod_parts = {n["part"] for n in full.nodes if n["part"] and n["lod"]}
    missing = set(full.parts) - p24 - lod_parts
    extra = p24 - set(full.parts)
    if missing or extra:
        raise SystemExit("pinch-lod24.svg drifted from pinch.svg + LOD flags: missing %s extra %s" % (missing, extra))

    parts = list(full.parts) + ["glyph-glow"]
    part_index = {p: i for i, p in enumerate(parts)}

    params = rig["params"]
    pnames = [p["name"] for p in params]
    mouth_shapes = ["smile", "flat", "open", "o"]

    L = []
    w = L.append
    w("// PinchData.swift: GENERATED by docs/design/pinch/gen_swift.py from pinch.svg, pinch-lod16.svg,")
    w("// pinch-lod20.svg, rig.json, clips.json and tokens/tokens.css. Do not edit by hand: change the sources and rerun")
    w("//     python3 docs/design/pinch/gen_swift.py")
    w("// Pinch.swift holds the rig, the renderer and the views; this file is only data. SwiftUI only (macOS 14, iOS 17).")
    w("import SwiftUI")
    w("")

    # ---- params + pose
    w("/// Every rig parameter, in rig.json order. `mouth` is the one shape (step) parameter.")
    w("enum PinchParam: Int, CaseIterable, Sendable {")
    w("    case " + ", ".join(pnames))
    w("    /// rig.json default (mouth: index into PinchMouth).")
    w("    var rest: Double {")
    w("        switch self {")
    for p in params:
        d = p["default"]
        w("        case .%s: return %s" % (p["name"], num(mouth_shapes.index(d)) if isinstance(d, str) else num(d)))
    w("        }")
    w("    }")
    w("    /// rig.json range (for sliders and clamps; mouth spans the shape indices).")
    w("    var range: ClosedRange<Double> {")
    w("        switch self {")
    for p in params:
        if p["min"] is None:
            w("        case .%s: return 0...%d" % (p["name"], len(mouth_shapes) - 1))
        else:
            w("        case .%s: return %s...%s" % (p["name"], num(p["min"]), num(p["max"])))
    w("        }")
    w("    }")
    w("}")
    w("")
    w("/// The mouth is the rig's only shape swap.")
    w("enum PinchMouth: Int, CaseIterable, Sendable { case " + ", ".join("`o`" if m == "o" else m for m in mouth_shapes) + " }")
    w("")
    w("/// One frame of Pinch: every rig.json param at its value. `PinchPose()` is the rest pose.")
    w("struct PinchPose: Equatable, Sendable {")
    for p in params:
        doc = p["drives"].replace("\n", " ")
        if p["name"] == "mouth":
            w("    /// %s" % doc)
            w("    var mouth: PinchMouth = .%s" % p["default"])
        else:
            w("    /// %s (%s, %s…%s)" % (doc, p["unit"], num(p["min"]), num(p["max"])))
            w("    var %s: Double = %s" % (p["name"], num(p["default"])))
    w("")
    w("    init() {}")
    w("")
    w("    /// Read or write any param by key (mouth as its PinchMouth raw value).")
    w("    subscript(_ k: PinchParam) -> Double {")
    w("        get {")
    w("            switch k {")
    for n in pnames:
        w("            case .%s: return %s" % (n, "Double(mouth.rawValue)" if n == "mouth" else n))
    w("            }")
    w("        }")
    w("        set {")
    w("            switch k {")
    for n in pnames:
        if n == "mouth":
            w("            case .mouth: mouth = PinchMouth(rawValue: Int(newValue.rounded())) ?? .smile")
        else:
            w("            case .%s: %s = newValue" % (n, n))
    w("            }")
    w("        }")
    w("    }")
    w("}")
    w("")

    # ---- motion data
    easings = clips["easings"]

    def ease_swift(name):
        if name in easings and easings[name] not in ("linear", "step"):
            return "." + camel(name)
        return ease_spec_swift(name)

    def ease_spec_swift(name):
        spec = easings.get(name, name)
        if spec == "linear":
            return ".linear"
        if spec == "step":
            return ".step"
        m = re.match(r"cubic-bezier\(([^)]+)\)", spec)
        if m:
            v = [num(x) for x in m.group(1).split(",")]
            return ".bezier(%s, %s, %s, %s)" % tuple(v)
        m = re.match(r"spring\(([^,]+),([^)]+)\)", spec)
        if m:
            return ".spring(%s, %s)" % (num(m.group(1)), num(m.group(2)))
        raise SystemExit("unknown easing " + name)

    def track_swift(name, keys):
        out = []
        for k in keys:
            v = k[1]
            v = num(mouth_shapes.index(v)) if isinstance(v, str) else num(v)
            e = ease_swift(k[2] if len(k) > 2 else "out")   # rig.js: b[2] || 'out'
            out.append("(%s, %s, %s)" % (num(k[0]), v, e))
        return "PinchTrack(.%s, [%s])" % (name, ", ".join(out))

    def motion_swift(d, indent):
        lines = ["PinchMotion(loop: %s, dur: %s, key: %s, priority: %d, tracks: [" % (
            "true" if d.get("loop") else "false", num(d["dur"]), num(d.get("key", 0)), d.get("priority", 0))]
        for k, keys in d["tracks"].items():
            if k not in pnames:
                raise SystemExit("track for unknown param " + k)
            lines.append(indent + "    " + track_swift(k, keys) + ",")
        lines.append(indent + "])")
        return "\n".join(lines)

    w("/// clips.json easings by name (rig.js resolves a keyframe's easing name through this table).")
    w("extension PinchEase {")
    for k in easings:
        if easings[k] in ("linear", "step"):
            continue
        w("    static let %s = PinchEase%s" % (camel(k), ease_spec_swift(k)))
    w("}")
    w("")
    w("/// clips.json, compiled. Keyframes are (ms, value, easing into this key); mouth values are PinchMouth indices.")
    w("enum PinchMotions {")
    w("    static func mood(_ m: PinchMood) -> PinchMotion {")
    w("        switch m {")
    for name in clips["moods"]:
        w("        case .%s: return %s" % (name, "moodData[%d]" % list(clips["moods"]).index(name)))
    w("        }")
    w("    }")
    w("    static func clip(_ c: PinchClip) -> PinchMotion {")
    w("        switch c {")
    for name in clips["clips"]:
        w("        case .%s: return %s" % (name, "clipData[%d]" % list(clips["clips"]).index(name)))
    w("        }")
    w("    }")
    w("    static let moodData: [PinchMotion] = [")
    for name, d in clips["moods"].items():
        w("        // %s" % name)
        w("        " + motion_swift(d, "        ") + ",")
    w("    ]")
    w("    static let clipData: [PinchMotion] = [")
    for name, d in clips["clips"].items():
        w("        // %s" % name)
        w("        " + motion_swift(d, "        ") + ",")
    w("    ]")
    b = clips["blink"]
    w("    static let blink = " + motion_swift({"dur": b["dur"], "tracks": b["tracks"]}, "    "))
    w("    static let blinkEvery: ClosedRange<Double> = %s...%s" % (num(b["every_ms"][0]), num(b["every_ms"][1])))
    w("    static let blinkDoubleChance = %s" % num(b["double_chance"]))
    w("    static let blinkDoubleGap: Double = %s" % num(b["double_gap_ms"]))
    pol = clips["policy"]
    w("    static let cooldown: Double = %s" % num(pol["cooldown_ms"]))
    w("    static let blendIn: Double = %s" % num(pol["blend_in_ms"]))
    w("    static let blendOut: Double = %s" % num(pol["blend_out_ms"]))
    w("    static let restAfter: Double = %s" % num(pol["rest_after_ms"]))
    gz = pol["idle_gaze"]
    w("    static let gazeEvery: ClosedRange<Double> = %s...%s" % (num(gz["every_ms"][0]), num(gz["every_ms"][1])))
    w("    static let gazeX: ClosedRange<Double> = %s...%s" % (num(gz["lookX"][0]), num(gz["lookX"][1])))
    w("    static let gazeY: ClosedRange<Double> = %s...%s" % (num(gz["lookY"][0]), num(gz["lookY"][1])))
    w("    static let gazeDur: Double = %s" % num(gz["dur_ms"]))
    w("    static let gazeEase: PinchEase = %s" % ease_swift(gz["ease"]))
    w("    static let gazeMoods: [PinchMood] = [%s]" % ", ".join("." + m for m in gz["moods"]))
    chain = pol["chain"]
    w("    /// policy.chain: the clip that follows another one, forced.")
    w("    static func chain(after c: PinchClip) -> PinchClip? {")
    w("        switch c {")
    for k, v in chain.items():
        w("        case .%s: return .%s" % (k, v))
    w("        default: return nil")
    w("        }")
    w("    }")
    w("}")
    w("")

    # ---- geometry
    G = rig["geom"]

    def pt(v):
        return "CGPoint(x: %s, y: %s)" % (num(v[0]), num(v[1]))

    w("/// rig.json geometry (viewBox units, 160 × 160).")
    w("enum PinchGeom {")
    w("    static let feet = %s" % pt(rig["feet"]))
    w("    static let eyeL = %s, eyeR = %s" % (pt(G["eyes"]["l"]), pt(G["eyes"]["r"])))
    w("    static let look = CGSize(width: %s, height: %s)" % (num(G["look"][0]), num(G["look"][1])))
    w("    static let lookLean: Double = %s" % num(G["lookLean"]))
    w("    static let lidSpan: Double = %s" % num(G["lidSpan"]))
    w("    static let lidEdgeL: Double = %s, lidEdgeR: Double = %s" % (num(G["lidEdge"]["l"]), num(G["lidEdge"]["r"])))
    w("    static let mouth = %s" % pt(G["mouth"]))
    w("    static let smileY: Double = %s" % num(G["smileY"]))
    w("    static let antennaL = %s, antennaR = %s" % (pt(G["antenna"]["l"]), pt(G["antenna"]["r"])))
    w("    static let shoulderL = %s, shoulderR = %s" % (pt(G["shoulder"]["l"]), pt(G["shoulder"]["r"])))
    w("    static let wristL = %s, wristR = %s" % (pt(G["wrist"]["l"]), pt(G["wrist"]["r"])))
    w("    static let clawFollow: Double = %s" % num(G["clawFollow"]))
    J = G["jaws"]
    w("    static let jawTop = %s, jawBottom = %s" % (pt(J["top"]["local"]), pt(J["bottom"]["local"])))
    w("    static let jawTopClose: Double = %s, jawTopOpen: Double = %s" % (num(J["top"]["close_deg"]), num(J["top"]["open_deg"])))
    w("    static let jawBottomClose: Double = %s, jawBottomOpen: Double = %s" % (
        num(J["bottom"]["close_deg"]), num(J["bottom"]["open_deg"])))
    w("    static let glass = %s" % pt(G["glass"]))
    w("    static let glassR: Double = %s" % num(G["glassR"]))
    w("    static let grip = %s" % pt(G["grip"]))
    w("    static let lensMag: Double = %s" % num(G["lensMag"]))
    LR = G["lensRaise"]
    w("    static let lensRaiseArm: Double = %s, lensRaiseClaw: Double = %s" % (num(LR["arm"]), num(LR["claw"])))
    w("    static let lensRaiseSlide = CGSize(width: %s, height: %s)" % (num(LR["slide"][0]), num(LR["slide"][1])))
    w("    static let sparkleC = %s" % pt(G["sparkleC"]))
    w("    static let bloom = %s" % pt(G["bloom"]))
    w("    static let zzzPeriod: Double = %s" % num(G["zzzPeriod"]))
    w("}")
    w("")

    # ---- palette
    dark, light = theme_block(css, "dark"), theme_block(css, "light")
    w("/// pinch-* tokens from tokens/tokens.css. In the dark theme the outline is transparent unless `rim` is on.")
    w("struct PinchPalette: Sendable {")
    w("    let " + ", ".join(k for k, _ in PALETTE_KEYS) + ": Color")
    for nm, vals in (("dark", dark), ("light", light)):
        args = ", ".join("%s: %s" % (k, swift_color(vals[t])) for k, t in PALETTE_KEYS)
        w("    static let %s = PinchPalette(%s)" % (nm, args))
    w("}")
    w("")

    # ---- parts + art
    w("/// Every animated part (data-part in pinch.svg), plus the glyph's lens light.")
    w("enum PinchPart: Int, CaseIterable, Sendable {")
    w("    case " + ", ".join(camel(p) for p in parts))
    w("}")
    w("")

    def mat(m):
        if m == IDENT:
            return ".identity"
        return "CGAffineTransform(a: %s, b: %s, c: %s, d: %s, tx: %s, ty: %s)" % tuple(num(x) for x in m)

    def emit_tree(tree, label):
        clip_ids = tree.clip_order
        out = []
        out.append("    // %s: %d nodes, %d shapes" % (label, len(tree.nodes), len(tree.shapes)))
        out.append("    static let %sClips: [Path] = [" % label)
        for cid in clip_ids:
            out.append("        { var p = Path(); %s; return p }(), // %s" % ("; ".join(tree.clips[cid]), cid))
        out.append("    ]")
        out.append("    static let %sShapes: [PinchShape] = [" % label)
        for stmts, s in tree.shapes:
            body = "\n".join("            " + x for x in stmts)
            ink = lambda v: ("." + v) if v else "nil"
            out.append("        PinchShape(path: { var p = Path()\n%s\n            return p }()," % body)
            out.append("                   fill: %s, stroke: %s, width: %s, outline: .%s, outlineBase: %s, cap: .%s, join: .%s, evenOdd: %s, strokeOpacity: %s, gradient: %s),"
                       % (ink(s["fill"]), ink(s["stroke"]), num(s["width"]), s["outline"], num(s["outlineBase"]),
                          s["cap"], s["join"], "true" if s["evenOdd"] else "false", num(s["strokeOpacity"]),
                          "true" if s["gradient"] else "false"))
        out.append("    ]")
        out.append("    static let %sNodes: [PinchNode] = [" % label)
        for i, n in enumerate(tree.nodes):
            out.append("        PinchNode(part: %s, lod: %d, opacity: %s, transform: %s, clip: %d, shape: %d, end: %d), // %d"
                       % ("." + camel(n["part"]) if n["part"] else "nil", n["lod"], num(n["opacity"]), mat(n["transform"]),
                          clip_ids.index(n["clip"]) if n["clip"] else -1, n["shape"] if n["shape"] is not None else -1,
                          n["end"], i))
        out.append("    ]")
        return out

    w("/// The art as flat pre-order node lists (a node's subtree is `index + 1 ..< end`) over shared shapes and clips.")
    w("enum PinchArt {")
    w("    /// Rest transform and opacity of every part (the SVG's own attributes before the rig writes them).")
    w("    static let restTransform: [CGAffineTransform] = [")
    for p in parts:
        info = full.parts.get(p) or g16.parts.get(p)
        w("        %s, // %s" % (mat(info["transform"]), p))
    w("    ]")
    w("    static let restOpacity: [Double] = [")
    for p in parts:
        info = full.parts.get(p) or g16.parts.get(p)
        w("        %s, // %s" % (num(info["opacity"]), p))
    w("    ]")
    for tree, label, vb in ((full, "full", 160), (g16, "glyph16", 16), (g20, "glyph20", 20)):
        for line in emit_tree(tree, label):
            w(line)
        w("    static let %sViewBox: CGFloat = %d" % (label, vb))
    w("}")
    w("")
    OUT.write_text("\n".join(L) + "\n")
    print("wrote %s (%d parts, %d shapes full, %d+%d glyph shapes, %d moods, %d clips)" % (
        OUT.relative_to(HERE.parent.parent.parent), len(parts), len(full.shapes), len(g16.shapes), len(g20.shapes),
        len(clips["moods"]), len(clips["clips"])))


if __name__ == "__main__":
    emit()
