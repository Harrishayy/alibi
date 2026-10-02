#!/usr/bin/env python3
"""Pinch: the canonical generator.

One parametric drawing, rebuilt from variant B ("Inspector with lens") with C's construction
method: every curve sits on a circle or capsule grid defined below, so a polish pass is an edit to
a number here, never a hand-edited path.  Writes, next to this file:

  pinch.svg         master rig, idle pose (viewBox 0 0 160 160)
  pinch-lod24.svg   24-39 px rung: no legs, tail or blush
  pinch-lod20.svg   20 px silhouette master (PinchLine avatar, Live Activity compact leading)
  pinch-lod16.svg   16 px silhouette master (island wings)
  rig.json          parts, pivots, transforms, params
  clips.json        moods, clips, blink, easings, policy
  pose-sheet.html   every mood and clip at its key frame, sizes, notch, toast, rig stress

Run:  python3 docs/design/pinch/build_pinch.py
"""
import json
import math
import pathlib
import re

OUT = pathlib.Path(__file__).resolve().parent

# --------------------------------------------------------------------------------------------
# number formatting and tiny 2D affine helpers
# --------------------------------------------------------------------------------------------


def f(v, nd=2):
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "", "-") else s


def P(x, y):
    return f"{f(x)} {f(y)}"


class M:
    """2D affine matrix [a c e; b d f]."""

    def __init__(self, a=1, b=0, c=0, d=1, e=0, f_=0):
        self.m = (a, b, c, d, e, f_)

    def __matmul__(self, o):
        a, b, c, d, e, f_ = self.m
        A, B, C, D, E, F = o.m
        return M(a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D, a * E + c * F + e, b * E + d * F + f_)

    def ap(self, p):
        a, b, c, d, e, f_ = self.m
        return (a * p[0] + c * p[1] + e, b * p[0] + d * p[1] + f_)

    @staticmethod
    def T(x, y):
        return M(1, 0, 0, 1, x, y)

    @staticmethod
    def R(deg, cx=0, cy=0):
        r = math.radians(deg)
        co, si = math.cos(r), math.sin(r)
        return M.T(cx, cy) @ M(co, si, -si, co, 0, 0) @ M.T(-cx, -cy)

    @staticmethod
    def S(sx, sy=None, cx=0, cy=0):
        return M.T(cx, cy) @ M(sx, 0, 0, sx if sy is None else sy, 0, 0) @ M.T(-cx, -cy)


def pol(c, r, deg):
    a = math.radians(deg)
    return (c[0] + r * math.cos(a), c[1] + r * math.sin(a))


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def star(cx, cy, s):
    """4-point sparkle on a circle grid: tips at radius s, waist at s*0.2."""
    k = s * 0.2
    return (f"M{P(cx, cy - s)}Q{P(cx + k, cy - k)} {P(cx + s, cy)}Q{P(cx + k, cy + k)} {P(cx, cy + s)}"
            f"Q{P(cx - k, cy + k)} {P(cx - s, cy)}Q{P(cx - k, cy - k)} {P(cx, cy - s)}Z")


# --------------------------------------------------------------------------------------------
# THE GRID: every number that shapes Pinch lives here
# --------------------------------------------------------------------------------------------

FEET = (80, 148)                    # squash / tilt origin

# Body: a teardrop hull of three circles, flanks are arcs of a large circle (convex, not conical).
HEAD_C, HEAD_R = (80, 59), 26       # crown circle -> top at y 33
BASE_R = 26                         # two base-corner circles
BASE_L, BASE_R_C = (64.5, 117.5), (95.5, 117.5)   # base width 83 (B's 78 widened ~6%)
FLANK_R = 150                       # flank arc radius

EYE_RX, EYE_RY = 9.4, 11.2          # ~23% of body width each (A's scale)
EYES = {"l": (66, 80), "r": (94, 80)}
SHINE = (-3.1, -4.4, 2.9)           # dx, dy, r
LID_REST = 0.0                      # idle lid coverage (directive: <= 12%; idle is fully open and curious)
LOOK = (3.5, 2.5)                   # px at lookX/lookY = 1

MOUTH_C = (80, 97)
BLUSH = {"l": (52.5, 94.5), "r": (107.5, 94.5)}
BLUSH_R = (6, 3.6)

BELLY_C, BELLY_R = (80, 122.5), (23, 18)
BELLY_LINES = [118, 129.5]          # two carapace lines at most
GLOSS_R, GLOSS_A = 16.5, (198, 246)  # highlight arc on the crown circle (deg)

ANT = {
    "l": ((74.5, 38), "C72.6 26 65 16.6 54.2 12.6C46.6 9.8 39.6 11.6 38.4 17"),
    "r": ((85.5, 38), "C87.4 26 95 16.6 105.8 12.6C113.4 9.8 120.4 11.6 121.6 17"),
}
ANT_W = 3.4

SHOULDER = {"l": (51.5, 104.5), "r": (108, 105)}
WRIST = {"l": (31.5, 89), "r": (125.5, 115)}
ARM_W = 9

# Claw frame: wrist at 0,0, claw pointing up (-y).  The palm is a circle; each finger is a crescent
# between an outer and an inner circle arc, with a round tip.  jaw-*-bottom = fixed finger (+x),
# jaw-*-top = dactyl (-x), hinged at HINGE.  The right claw is mirrored, so one signed angle closes both.
CLAW = {
    #        angle  scale  mirror
    "l": dict(a=-24, s=1.12, mirror=False),   # crusher: bigger, raised beside the face
    "r": dict(a=14, s=0.86, mirror=True),     # cutter: holds the lens
}
PALM_C, PALM_R = (0, -14), 13
FINGER = dict(base_out=(12.6, -17.5), tip=(5.2, -45.5), tip_r=2.6, base_in=(3.2, -25.5), bulge_out=16.5, bulge_in=7.2)
HINGE_TOP = (-7.5, -22)             # dactyl hinge (local)
HINGE_BOT = (7.5, -22)              # fixed-finger hinge (local)
OPEN_TOP, OPEN_BOT = -16, 5         # wide-open angles (deg)

# Lens: held in claw-r's bite, glass above.
LENS_R, RIM_W = 12.5, 4
HANDLE_W = 5
LENS_GRIP_LOCAL = (0, -24)          # grip point in claw-r frame (bite bottom)
LENS_HANDLE = 35                    # grip -> glass centre
LENS_TILT = 3                       # extra tilt of the lens vs the claw axis (deg)

LEGS = [((63.5, 136), (60, 147)), ((73, 139.5), (71.5, 149)), ((87, 139.5), (88.5, 149)), ((96.5, 136), (100, 147))]
LEG_W = 7

TAIL_BASE = (48, 133)                # tail segment: capsule from here to the fan root
TAIL_FAN_C = (35, 138)
TAIL_BLADES = [(-46, 13, 5.4), (-8, 15, 6.2), (30, 13, 5.4)]   # angle from pointing left (+ = down), length, half-width

SWEAT = (60.5, 57)                  # A's placement: on the left temple, clear of the lens
BLOOM_C, BLOOM_R = (80, 86), 76

# --------------------------------------------------------------------------------------------
# derived geometry
# --------------------------------------------------------------------------------------------


def flank(h, hr, b, br, side):
    """Arc of a circle of radius FLANK_R internally tangent to circles h and b. side -1 left, +1 right."""
    R = FLANK_R
    mx, my = (h[0] + b[0]) / 2, (h[1] + b[1]) / 2
    dx, dy = b[0] - h[0], b[1] - h[1]
    L = math.hypot(dx, dy)
    # unit perpendicular pointing inward (toward the body centre line)
    nx, ny = -dy / L, dx / L
    if (nx * side) > 0:
        nx, ny = -nx, -ny
    # both circles have the same radius here (24), so the centre is on the perpendicular bisector
    assert abs(hr - br) < 1e-6
    off = math.sqrt((R - hr) ** 2 - (L / 2) ** 2)
    F = (mx + nx * off, my + ny * off)
    th = (h[0] + (h[0] - F[0]) / (R - hr) * hr, h[1] + (h[1] - F[1]) / (R - hr) * hr)
    tb = (b[0] + (b[0] - F[0]) / (R - br) * br, b[1] + (b[1] - F[1]) / (R - br) * br)
    return th, tb


def body_d():
    tl_h, tl_b = flank(HEAD_C, HEAD_R, BASE_L, BASE_R, -1)
    tr_h, tr_b = flank(HEAD_C, HEAD_R, BASE_R_C, BASE_R, +1)
    top = (HEAD_C[0], HEAD_C[1] - HEAD_R)
    bl = (BASE_L[0], BASE_L[1] + BASE_R)
    br = (BASE_R_C[0], BASE_R_C[1] + BASE_R)
    R = FLANK_R
    return (f"M{P(*top)}A{f(HEAD_R)} {f(HEAD_R)} 0 0 0 {P(*tl_h)}A{R} {R} 0 0 0 {P(*tl_b)}"
            f"A{f(BASE_R)} {f(BASE_R)} 0 0 0 {P(*bl)}H{f(br[0])}A{f(BASE_R)} {f(BASE_R)} 0 0 0 {P(*tr_b)}"
            f"A{R} {R} 0 0 0 {P(*tr_h)}A{f(HEAD_R)} {f(HEAD_R)} 0 0 0 {P(*top)}Z")


def claw_frame(side):
    c = CLAW[side]
    w = WRIST[side]
    m = M.T(*w) @ M.R(c["a"]) @ M.S(c["s"])
    if c["mirror"]:
        m = m @ M.S(-1, 1)
    return m


def claw_frame_attr(side):
    c = CLAW[side]
    w = WRIST[side]
    t = f"translate({P(*w)}) rotate({f(c['a'])}) scale({f(-c['s']) if c['mirror'] else f(c['s'])} {f(c['s'])})"
    return t


def finger_d(sign):
    """Crescent finger on the +x side (sign=1) or mirrored to -x (sign=-1), local claw frame."""
    F = FINGER
    bo = (F["base_out"][0] * sign, F["base_out"][1])
    bi = (F["base_in"][0] * sign, F["base_in"][1])
    tip = (F["tip"][0] * sign, F["tip"][1])
    tr = F["tip_r"]
    # tip circle centre: tip point is the outermost end; inner and outer edges leave it tangentially.
    tc = (tip[0], tip[1] + tr)
    to = (tc[0] + tr * 0.94 * sign, tc[1] - tr * 0.34)   # outer side of the tip
    ti = (tc[0] - tr * 0.96 * sign, tc[1] + tr * 0.28)   # inner side of the tip
    sw = 0 if sign > 0 else 1
    ro, ri = F["bulge_out"] * 2.2, F["bulge_in"] * 3.2
    return (f"M{P(*bo)}A{f(ro)} {f(ro)} 0 0 {sw} {P(*to)}A{f(tr)} {f(tr)} 0 0 {sw} {P(*ti)}"
            f"A{f(ri)} {f(ri)} 0 0 {1 - sw} {P(*bi)}L{P(sign * 1.5, PALM_C[1] - 4)}Z")


def tip_centre(sign):
    F = FINGER
    return (F["tip"][0] * sign, F["tip"][1] + F["tip_r"])


def solve_close():
    """Angles at which the dactyl (top) tip meets the fixed finger (bottom) tip, overlapping 0.6."""
    bot_close = 3.0
    tb = M.R(-bot_close, *HINGE_BOT).ap(tip_centre(1))
    lo, hi = 0.0, 40.0
    target = 2 * FINGER["tip_r"] - 0.6
    for _ in range(60):
        mid = (lo + hi) / 2
        tt = M.R(mid, *HINGE_TOP).ap(tip_centre(-1))
        if dist(tt, tb) > target:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 1), -bot_close


CLOSE_TOP, CLOSE_BOT = solve_close()


def lens_rest_local():
    """Lens geometry in claw-r's *world-rest* frame (the lens is not mirrored)."""
    fr = claw_frame("r")
    grip = fr.ap(LENS_GRIP_LOCAL)
    axis_tip = fr.ap((LENS_GRIP_LOCAL[0], LENS_GRIP_LOCAL[1] - 10))
    ang = math.degrees(math.atan2(axis_tip[1] - grip[1], axis_tip[0] - grip[0])) + LENS_TILT
    gc = (grip[0] + LENS_HANDLE * math.cos(math.radians(ang)), grip[1] + LENS_HANDLE * math.sin(math.radians(ang)))
    return grip, gc, ang


GRIP, GLASS_C, LENS_ANG = lens_rest_local()


LENS_TARGET = (EYES["r"][0] + 0.4, EYES["r"][1] - 0.4)   # glass centre when lens = 1
LENS_SLIDE = -7.0                                       # handle slides down through the grip (along the handle)


def solve_lens(target, slide_len, pick=0, point="glass"):
    """Two-joint IK: arm-r about the shoulder, claw-r about the wrist, so the glass centre (or the grip)
    lands on target.  The handle may also slide slide_len along itself through the grip."""
    u = ((GLASS_C[0] - GRIP[0]) / LENS_HANDLE, (GLASS_C[1] - GRIP[1]) / LENS_HANDLE)
    slide = (u[0] * slide_len, u[1] * slide_len)
    G = (GLASS_C[0] + slide[0], GLASS_C[1] + slide[1]) if point == "glass" else GRIP
    S, W, T = SHOULDER["r"], WRIST["r"], target
    rw, dsw, D = dist(G, W), dist(W, S), dist(T, S)
    cosd = (rw * rw + dsw * dsw - D * D) / (2 * rw * dsw)
    assert -1 <= cosd <= 1, ("lens target unreachable", target, cosd)
    delta = math.degrees(math.acos(cosd))
    psi = math.degrees(math.atan2(S[1] - W[1], S[0] - W[0]))
    phi0 = math.degrees(math.atan2(G[1] - W[1], G[0] - W[0]))
    sols = []
    for sg in (1, -1):
        qa = psi + sg * delta
        ac = (qa - phi0 + 180) % 360 - 180
        Q = M.R(ac, *W).ap(G)
        aa = math.degrees(math.atan2(T[1] - S[1], T[0] - S[0]) - math.atan2(Q[1] - S[1], Q[0] - S[0]))
        aa = (aa + 180) % 360 - 180
        sols.append((round(aa, 2), round(ac, 2)))
    aa, ac = sols[pick]
    return dict(arm=aa, claw=ac, slide=[round(slide[0], 3), round(slide[1], 3)], target=[round(target[0], 2), round(target[1], 2)], all=sols)


def solve_lens_raise():
    return solve_lens(LENS_TARGET, LENS_SLIDE)


LENS_RAISE = solve_lens_raise()

# --------------------------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------------------------

STYLE = """<style>
[data-theme=dark]{--pinch-ol-auto:transparent;--pinch-glint-auto:var(--pinch-shine,#FFF)}
[data-theme=light]{--pinch-ol-auto:var(--pinch-outline,#365900);--pinch-glint-auto:var(--pinch-shade,#588C05)}
@media (prefers-color-scheme:dark){:root:not([data-theme]){--pinch-ol-auto:transparent;--pinch-glint-auto:var(--pinch-shine,#FFF)}}
.pinch{--p-ol:var(--pinch-ol-auto,var(--pinch-outline,#365900));--p-glint:var(--pinch-glint-auto,var(--pinch-shade,#588C05));overflow:visible}
.pinch.on-dark{--p-ol:transparent;--p-glint:var(--pinch-shine,#FFF)}
.pinch.on-light{--p-ol:var(--pinch-outline,#365900);--p-glint:var(--pinch-shade,#588C05)}
.pinch.rim{--p-ol:var(--pinch-outline,#8FD400)}
.pinch .o{stroke:var(--p-ol);stroke-width:calc(2*var(--pinch-ow,3));paint-order:stroke;stroke-linejoin:round}
.pinch .u{fill:none;stroke:var(--p-ol);stroke-linecap:round}
.pinch .k{fill:none;stroke-linecap:round;stroke-linejoin:round}
.pinch .fb{fill:var(--pinch-body,#76B900)}.pinch .fy{fill:var(--pinch-belly,#97DC42)}.pinch .fs{fill:var(--pinch-shade,#588C05)}
.pinch .fe{fill:var(--pinch-eye,#000)}.pinch .fw{fill:var(--pinch-shine,#FFF)}
.pinch .sb{stroke:var(--pinch-body,#76B900)}.pinch .ss{stroke:var(--pinch-shade,#588C05)}.pinch .se{stroke:var(--pinch-eye,#000)}
.pinch .sy{stroke:var(--pinch-belly,#97DC42)}
.pinch .fl{fill:var(--pinch-lens,#D7D7D7)}.pinch .sl{stroke:var(--pinch-lens,#D7D7D7)}
@container pinch (max-width:79px){.pinch{--pinch-ow:3.6}}
@container pinch (max-width:39px){.pinch{--pinch-ow:5.5}}
@container pinch (max-width:95px){.pinch .lod-96{display:none}}
@container pinch (max-width:39px){.pinch .lod-40{display:none}}
@media (max-width:79px){.pinch:root{--pinch-ow:3.6}}
@media (max-width:39px){.pinch:root{--pinch-ow:5.5}}
@media (max-width:95px){.pinch:root .lod-96{display:none}}
@media (max-width:39px){.pinch:root .lod-40{display:none}}
.pinch[data-lod="56"]{--pinch-ow:3.6}.pinch[data-lod="28"]{--pinch-ow:5.5}
.pinch[data-lod="56"] .lod-96,.pinch[data-lod="28"] .lod-96,.pinch[data-lod="28"] .lod-40{display:none}
</style>"""


def g(id_, inner, extra="", transform=""):
    t = f' transform="{transform}"' if transform else ""
    return f'<g id="{id_}" data-part="{id_}"{t}{extra}>{inner}</g>'


def stroke_part(d, w, cls_fill, cls_extra=""):
    """Capsule-stroke part with an outline underlay (outline is transparent on dark)."""
    return (f'<path class="u{cls_extra}" d="{d}" style="stroke-width:calc({f(w)} + 2*var(--pinch-ow,3))"/>'
            f'<path class="k {cls_fill}{cls_extra}" d="{d}" stroke-width="{f(w)}"/>')


LID_SAG = 1.6
LID_SPAN = 2 * EYE_RY + LID_SAG + 2.4    # lid travel from open (0) to shut (1)


def lid_edge_y(side):
    """y of the lid edge corners when coverage is 0 (just clear of the eye top)."""
    return EYES[side][1] - EYE_RY - LID_SAG - 1.2


def eye_art(side, magnified=False):
    cx, cy = EYES[side]
    sx, sy, sr = SHINE
    e = lid_edge_y(side)
    clip = f"pinch-eye-clip-{side}" if not magnified else "pinch-lens-eye-clip"
    lid_d = (f"M{P(cx - EYE_RX - 3, e - 18)}H{f(cx + EYE_RX + 3)}V{f(e)}"
             f"Q{P(cx, e + 2 * LID_SAG)} {P(cx - EYE_RX - 3, e)}Z")
    lash_d = f"M{P(cx - EYE_RX - 1.5, e + 0.3)}Q{P(cx, e + 2 * LID_SAG + 0.3)} {P(cx + EYE_RX + 1.5, e + 0.3)}"
    lid_id = f"lid-{side}" if not magnified else "lens-lid"
    happy = (f"M{P(cx - 7.2, cy + 2.6)}Q{P(cx, cy - 9.4)} {P(cx + 7.2, cy + 2.6)}")
    return (f'<clipPath id="{clip}"><ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(EYE_RX + 0.8)}" ry="{f(EYE_RY + 0.8)}"/></clipPath>'
            f'<g data-part="{"eye" if not magnified else "lens-eye"}-{side}-open">'
            f'<ellipse class="fe" cx="{f(cx)}" cy="{f(cy)}" rx="{f(EYE_RX)}" ry="{f(EYE_RY)}"/>'
            f'<circle class="fw" cx="{f(cx + sx)}" cy="{f(cy + sy)}" r="{f(sr)}"/>'
            f'<g clip-path="url(#{clip})">'
            + g(lid_id, f'<path class="fb" d="{lid_d}"/><path class="k ss" data-part="{lid_id}-lash" d="{lash_d}" stroke-width="2" opacity="0"/>')
            + "</g></g>"
            + (f'<path class="k se" data-part="eye-{side}-joy" d="{happy}" stroke-width="4" opacity="0"/>' if not magnified else ""))


def build_svg(lod="full"):
    """lod: full | 24 (no legs, tail, blush, belly lines, gloss)."""
    keep96 = lod == "full"
    keep40 = lod == "full"
    o = []
    o.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" class="pinch theme-auto" '
             'role="img" aria-label="Pinch, a green detective lobster holding a magnifying lens">')
    o.append(STYLE)
    # bloom: the system's one allowed gradient (celebrate only)
    o.append('<defs><radialGradient id="pinch-bloom"><stop offset="0" style="stop-color:var(--bloom,rgba(118,185,0,.35))"/>'
             '<stop offset="1" style="stop-color:var(--bloom,rgba(118,185,0,.35));stop-opacity:0"/></radialGradient>'
             f'<clipPath id="pinch-body-clip"><path d="{body_d()}"/></clipPath></defs>')
    o.append(f'<circle id="bloom" data-part="bloom" cx="{f(BLOOM_C[0])}" cy="{f(BLOOM_C[1])}" r="{BLOOM_R}" fill="url(#pinch-bloom)" opacity="0"/>')
    root = []

    # tail (behind the body, fan to the left)
    if keep40:
        blades = []
        for ang, ln, hw in TAIL_BLADES:
            a = 180 - ang
            tip = pol(TAIL_FAN_C, ln, a)
            # blade: capsule-ish leaf from the fan centre
            n = (math.cos(math.radians(a + 90)) * hw, math.sin(math.radians(a + 90)) * hw)
            mid = pol(TAIL_FAN_C, ln * 0.55, a)
            blades.append(f'<path class="o fs" d="M{P(*TAIL_FAN_C)}Q{P(mid[0] + n[0] * 1.6, mid[1] + n[1] * 1.6)} {P(*tip)}'
                          f'Q{P(mid[0] - n[0] * 1.6, mid[1] - n[1] * 1.6)} {P(*TAIL_FAN_C)}Z"/>')
        seg = f"M{P(*TAIL_BASE)}L{P(TAIL_FAN_C[0] + 3, TAIL_FAN_C[1])}"
        tail = ("".join(blades) + stroke_part(seg, 11, "ss")
                + f'<path class="k sb lod-96" d="M{P(TAIL_BASE[0] - 6.5, TAIL_BASE[1] - 4.8)}q-1.2 5 0 10.2" stroke-width="1.8" opacity=".55"/>')
        root.append(g("tail", tail, ' class="lod-40"'))

    # legs: four stubby capsules
    if keep96:
        legs = "".join(stroke_part(f"M{P(*a)}L{P(*b)}", LEG_W, "ss") for a, b in LEGS)
        root.append(g("legs", legs, ' class="lod-96"'))

    # body group
    body = []
    for s in "lr":
        base, rest = ANT[s]
        body.append(g(f"antenna-{s}", stroke_part(f"M{P(*base)}{rest}", ANT_W, "sb")))
    bd = body_d()
    body.append(f'<path class="o fb" d="{bd}"/>')
    # form shade: everything of the body outside an offset circle, clipped to the body
    body.append('<g clip-path="url(#pinch-body-clip)">'
                f'<path class="fs" fill-rule="evenodd" d="M20 20H140V160H20ZM{P(73 - 62, 84)}a62 62 0 1 0 124 0a62 62 0 1 0 -124 0Z"/></g>')
    if keep40:
        a0, a1 = GLOSS_A
        p0, p1 = pol(HEAD_C, GLOSS_R, a0), pol(HEAD_C, GLOSS_R, a1)
        body.append(f'<path class="k sy lod-40" d="M{P(*p0)}A{f(GLOSS_R)} {f(GLOSS_R)} 0 0 1 {P(*p1)}" stroke-width="4.4"/>')
    belly = f'<ellipse class="fy" cx="{f(BELLY_C[0])}" cy="{f(BELLY_C[1])}" rx="{f(BELLY_R[0])}" ry="{f(BELLY_R[1])}"/>'
    if keep40:
        for y in BELLY_LINES:
            dy = y - BELLY_C[1]
            hw = BELLY_R[0] * math.sqrt(max(0, 1 - (dy / BELLY_R[1]) ** 2)) - 3.2
            belly += f'<path class="k ss lod-40" d="M{P(80 - hw, y)}Q{P(80, y + 3.6)} {P(80 + hw, y)}" stroke-width="2.2"/>'
    body.append(g("belly", belly))
    if keep40:
        bl = "".join(f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(BLUSH_R[0])}" ry="{f(BLUSH_R[1])}"/>' for x, y in BLUSH.values())
        body.append(g("blush", bl, ' class="lod-40" style="fill:var(--pinch-blush,rgba(242,169,0,.35))" opacity="0"'))
    for s in "lr":
        body.append(g(f"eye-{s}", eye_art(s)))
    mx, my = MOUTH_C
    mouth = (f'<path class="k se" data-part="mouth-smile" d="M{P(mx - 5.6, my - 1.6)}Q{P(mx, my + 4.2)} {P(mx + 5.6, my - 1.6)}" stroke-width="2.6"/>'
             f'<path class="k se" data-part="mouth-flat" d="M{P(mx - 4.6, my)}H{f(mx + 4.6)}" stroke-width="2.6" opacity="0"/>'
             f'<path class="fe" data-part="mouth-open" d="M{P(mx - 6.8, my - 2.4)}H{f(mx + 6.8)}Q{P(mx + 6.8, my + 8)} {P(mx, my + 8)}Q{P(mx - 6.8, my + 8)} {P(mx - 6.8, my - 2.4)}Z" opacity="0"/>'
             f'<ellipse class="fe" data-part="mouth-o" cx="{f(mx)}" cy="{f(my + 1)}" rx="3.2" ry="3.9" opacity="0"/>')
    body.append(g("mouth", mouth))
    root.append(g("body", "".join(body)))

    # arms and claws
    for s in "lr":
        sh, wr = SHOULDER[s], WRIST[s]
        arm = stroke_part(f"M{P(*sh)}L{P(*wr)}", ARM_W, "ss")
        fr = claw_frame_attr(s)
        top = g(f"jaw-{s}-top", f'<path class="o fb" d="{finger_d(-1)}"/>')
        bot = g(f"jaw-{s}-bottom", f'<path class="o fb" d="{finger_d(1)}"/>')
        palm = (f'<circle class="o fb" cx="{f(PALM_C[0])}" cy="{f(PALM_C[1])}" r="{f(PALM_R)}"/>'
                f'<path class="fs lod-40" d="M{P(-PALM_R + 0.6, PALM_C[1] + 3)}A{f(PALM_R)} {f(PALM_R)} 0 0 0 {P(PALM_R - 0.6, PALM_C[1] + 3)}'
                f'A{f(PALM_R * 1.5)} {f(PALM_R * 1.5)} 0 0 1 {P(-PALM_R + 0.6, PALM_C[1] + 3)}Z"/>')
        if s == "r":   # the handle runs between the fingers: fixed finger, lens, dactyl, palm
            inner = f'<g transform="{fr}">{bot}</g>{lens_svg()}<g transform="{fr}">{top}{palm}</g>'
        else:          # the crusher pinches the paper slip (reading only)
            inner = f'<g transform="{fr}">{bot}{top}{palm}</g>{paper_svg()}'

        claw = g(f"claw-{s}", inner)
        root.append(g(f"arm-{s}", arm + claw))

    # effects
    root.append(g("sweat", f'<path style="fill:var(--pinch-lens,#D7D7D7)" d="M{P(SWEAT[0], SWEAT[1] - 7)}'
                           f'C{P(SWEAT[0] + 2.4, SWEAT[1] - 3)} {P(SWEAT[0] + 4.4, SWEAT[1] - 1.2)} {P(SWEAT[0] + 4.4, SWEAT[1] + 1.4)}'
                           f'A4.4 4.4 0 0 1 {P(SWEAT[0] - 4.4, SWEAT[1] + 1.4)}C{P(SWEAT[0] - 4.4, SWEAT[1] - 1.2)} {P(SWEAT[0] - 2.4, SWEAT[1] - 3)} {P(SWEAT[0], SWEAT[1] - 7)}Z"/>'
                           f'<path class="k" style="stroke:var(--pinch-shine,#FFF)" d="M{P(SWEAT[0] - 2.2, SWEAT[1] + 1)}a2.4 2.4 0 0 0 1.8 2.2" stroke-width="1.3"/>',
                  ' opacity="0"'))
    root.append(g("zzz", zzz_svg(), ' opacity="0"'))
    o.append(g("pinch-root", "".join(root)))
    o.append(g("sparkle", sparkle_svg(), ' opacity="0"'))
    o.append("</svg>")
    return "".join(o) + "\n"


def lens_svg():
    gx, gy = GLASS_C
    gr = GRIP
    # handle: capsule from inside the grip to the glass rim
    hd0 = (gr[0] - (gx - gr[0]) * 0.32, gr[1] - (gy - gr[1]) * 0.32)
    hd1 = (gx - (gx - gr[0]) / LENS_HANDLE * (LENS_R + HANDLE_W / 2 + 0.6), gy - (gy - gr[1]) / LENS_HANDLE * (LENS_R + HANDLE_W / 2 + 0.6))
    handle = (f'<path class="u" d="M{P(*hd0)}L{P(*hd1)}" style="stroke-width:calc({HANDLE_W} + 2*var(--pinch-ow,3))"/>'
              f'<path class="k sl" d="M{P(*hd0)}L{P(*hd1)}" stroke-width="{HANDLE_W}"/>'
              f'<path class="k se" d="M{P(*hd0)}L{P(*hd1)}" stroke-width="{HANDLE_W}" opacity=".42"/>')
    # ferrule where the handle meets the rim
    fe0 = (gx - (gx - gr[0]) / LENS_HANDLE * (LENS_R + 1.2), gy - (gy - gr[1]) / LENS_HANDLE * (LENS_R + 1.2))
    fe1 = (gx - (gx - gr[0]) / LENS_HANDLE * (LENS_R + 4.6), gy - (gy - gr[1]) / LENS_HANDLE * (LENS_R + 4.6))
    ferrule = f'<path class="k sl" d="M{P(*fe0)}L{P(*fe1)}" stroke-width="{HANDLE_W + 2.4}" style="stroke-linecap:butt"/>'
    glow_ring = f'<circle class="k sb" data-part="lens-ring" cx="{f(gx)}" cy="{f(gy)}" r="{f(LENS_R + RIM_W / 2 + 2.6)}" stroke-width="2.6" opacity="0"/>'
    wash = f'<circle data-part="lens-wash" cx="{f(gx)}" cy="{f(gy)}" r="{f(LENS_R)}" style="fill:var(--pinch-lens-glow,rgba(170,240,89,.55))" opacity="0"/>'
    view = (f'<clipPath id="pinch-glass-clip"><circle cx="{f(gx)}" cy="{f(gy)}" r="{f(LENS_R - 0.4)}"/></clipPath>'
            f'<g clip-path="url(#pinch-glass-clip)">'
            + g("lens-view", f'<circle class="fb" cx="{f(gx)}" cy="{f(gy)}" r="{f(LENS_R + 1)}"/>'
                + g("lens-eye", eye_art("r", magnified=True)), ' opacity="0"')
            + "</g>")
    # outline underlay: full outline outside the rim, a hairline (ow - 1.8) inside it
    rim = (f'<circle class="u" cx="{f(gx)}" cy="{f(gy)}" r="{f(LENS_R + 0.9)}" style="stroke-width:calc({f(RIM_W - 1.8)} + 2*var(--pinch-ow,3))"/>'
           f'<circle class="k sl" cx="{f(gx)}" cy="{f(gy)}" r="{f(LENS_R)}" stroke-width="{RIM_W}"/>')
    # specular glints at 10 and 2 o'clock (camera off: two strokes; both stay when lit, the ring is the shape cue)
    gl_r = LENS_R - 4.6
    a1, a2 = pol((gx, gy), gl_r, 196), pol((gx, gy), gl_r, 238)
    b1, b2 = pol((gx, gy), gl_r, 292), pol((gx, gy), gl_r, 306)
    glint = g("lens-glint",
              f'<path class="k" style="stroke:var(--p-glint)" d="M{P(*a1)}A{f(gl_r)} {f(gl_r)} 0 0 1 {P(*a2)}" stroke-width="2.4" stroke-opacity=".7"/>'
              f'<path class="k" style="stroke:var(--p-glint)" d="M{P(*b1)}A{f(gl_r)} {f(gl_r)} 0 0 1 {P(*b2)}" stroke-width="2.4" stroke-opacity=".7"/>')
    glow = g("lens-glow", glow_ring + wash)
    k = LENS_R * 0.9
    sweep = (f'<g clip-path="url(#pinch-glass-clip)">'
             + g("lens-sweep", f'<path class="k" style="stroke:var(--pinch-spark,#AAF059)" d="M{P(gx - k, gy - k)}L{P(gx + k, gy + k)}" stroke-width="5"/>',
                 ' opacity="0"') + "</g>")
    return g("lens", handle + ferrule + glow + view + sweep + rim + glint)


def paper_svg():
    """A small slip of paper, held in the crusher for 'reading' (hidden otherwise)."""
    fr = claw_frame("l")
    c = fr.ap((0, -40))
    w, h = 26, 19
    ang = CLAW["l"]["a"] + 64
    t = f"rotate({f(ang)} {P(*c)})"
    lines = "".join(f'<path class="k ss" d="M{P(c[0] - w / 2 + 4.5, c[1] - h / 2 + y)}h{f(ln)}" stroke-width="1.8"/>'
                    for y, ln in [(5.5, 15), (9.8, 17), (14.1, 10)])
    return g("paper", f'<g transform="{t}"><rect class="o fw" x="{f(c[0] - w / 2)}" y="{f(c[1] - h / 2)}" width="{w}" height="{h}" rx="2.6"/>{lines}</g>',
             ' opacity="0"')


def zzz_svg():
    out = []
    for i, (x, y, s) in enumerate([(112, 36, 5), (121, 25, 6.5), (131, 12, 8)]):
        out.append(f'<path data-part="z{i}" class="k ss" d="M{P(x, y)}h{f(s)}l{f(-s)} {f(s)}h{f(s)}" stroke-width="{f(1.6 + i * 0.35)}"/>')
    return "".join(out)


def sparkle_svg():
    # placed from the claw tips in the celebrate pose (computed in build_sparkles)
    return "".join(f'<path data-part="spark{i}" style="fill:var(--pinch-spark,#AAF059)" d="{star(x, y, s)}"/>' for i, (x, y, s) in enumerate(SPARKS))


SPARKS = [(14, 30, 7), (146, 30, 7), (27, 13, 4.2), (133, 12, 4.2), (6, 58, 3.6), (154, 58, 3.6)]
SPARKLE_C = (80, 64)


# --------------------------------------------------------------------------------------------
# Silhouette masters (16 and 20 px). Hand-placed on their own pixel grids, never scaled from 160.
# Five shapes: body, crusher V, lens ring with stem, two flat-top eyes (+ the lit-lens dot).
# Body + crusher share var(--pinch-silhouette, var(--pinch-body)) so the wing can tint them by state;
# the lens is its own colour and its lit dot is its own shape, so camera-on never collides with a tint.
# --------------------------------------------------------------------------------------------

SIL = {
    16: dict(
        body="M8.5 5.4C10.5 5.4 11.6 7.4 12.1 9.4L12.8 12.5C13.2 14.2 12.1 15.5 10.5 15.5H6.5C4.9 15.5 3.8 14.2 4.2 12.5L4.9 9.4C5.4 7.4 6.5 5.4 8.5 5.4Z",
        claw="M2.6 8.3C1.1 8 0.3 6.6 0.5 5L1.1 1.6C1.2 1 2.1 1 2.2 1.6L2.25 3.8C2.3 4.3 3.3 4.3 3.35 3.8L3.4 1.6C3.5 1 4.4 1 4.5 1.6L5.1 5C5.3 6.6 4.6 7.9 3.4 8.3Z",
        claw_t="translate(1.5 1.2) rotate(-16 2.8 8.3)",
        lens_c=(13, 4.1), lens_r=2.7, hole_r=1.1, stem="M10.9 6.2L12 7L10.6 9.4L9.5 8.7Z",
        eyes=[(5.9, 9.7), (9.1, 9.7)], eye_w=2, eye_h=2.5, shine=None),
    20: dict(
        body="M10.6 6.6C13.1 6.6 14.5 9.1 15.1 11.6L16 15.6C16.5 17.7 15.1 19.4 13.1 19.4H8.1C6.1 19.4 4.7 17.7 5.2 15.6L6.1 11.6C6.7 9.1 8.1 6.6 10.6 6.6Z",
        claw="M3.2 10.3C1.3 9.9 0.4 8.2 0.6 6.2L1.3 2C1.45 1.25 2.55 1.25 2.7 2L2.8 4.7C2.85 5.3 4.05 5.3 4.1 4.7L4.2 2C4.35 1.25 5.45 1.25 5.6 2L6.3 6.2C6.6 8.2 5.7 9.8 4.2 10.3Z",
        claw_t="translate(1.9 1.5) rotate(-16 3.5 10.3)",
        lens_c=(16.3, 5), lens_r=3.4, hole_r=1.4, stem="M13.7 7.6L15.1 8.6L13.3 11.7L11.9 10.8Z",
        eyes=[(7.35, 12.1), (11.35, 12.1)], eye_w=2.5, eye_h=3.1, shine=0.55),
}


def build_silhouette(n):
    d = SIL[n]
    cx, cy = d["lens_c"]
    ring = (f"M{P(cx, cy - d['lens_r'])}a{f(d['lens_r'])} {f(d['lens_r'])} 0 1 1 0 {f(2 * d['lens_r'])}a{f(d['lens_r'])} {f(d['lens_r'])} 0 1 1 0 {f(-2 * d['lens_r'])}Z"
            f"M{P(cx, cy - d['hole_r'])}a{f(d['hole_r'])} {f(d['hole_r'])} 0 1 0 0 {f(2 * d['hole_r'])}a{f(d['hole_r'])} {f(d['hole_r'])} 0 1 0 0 {f(-2 * d['hole_r'])}Z")
    eyes = []
    for i, (x, y) in enumerate(d["eyes"]):
        w, h = d["eye_w"], d["eye_h"]
        r = w / 2
        eye = f'<path id="eye-{"lr"[i]}" class="pe" d="M{P(x, y)}H{f(x + w)}V{f(y + h - r)}A{f(r)} {f(r)} 0 0 1 {P(x, y + h - r)}Z"/>'
        if d["shine"]:
            eye += f'<circle class="pw" cx="{f(x + w * 0.32)}" cy="{f(y + 0.75)}" r="{f(d["shine"])}"/>'
        eyes.append(eye)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="{n}" height="{n}" class="pinch-glyph" role="img" aria-label="Pinch">'
            "<style>.pinch-glyph .ps{fill:var(--pinch-silhouette,var(--pinch-body,#76B900))}"
            ".pinch-glyph .pl{fill:var(--pinch-lens,#D7D7D7)}.pinch-glyph .pe{fill:var(--pinch-eye,#000)}"
            ".pinch-glyph .pw{fill:var(--pinch-shine,#FFF)}.pinch-glyph .pg{fill:var(--pinch-spark,#AAF059)}"
            ".pinch-glyph.lit #lens-glow{opacity:1}</style>"
            '<g id="pinch-root">'
            f'<path id="body" class="ps" d="{d["body"]}"/>'
            f'<path id="claw-l" class="ps" transform="{d["claw_t"]}" d="{d["claw"]}"/>'
            f'<g id="lens"><path class="pl" fill-rule="evenodd" d="{ring}{d["stem"]}"/>'
            f'<circle id="lens-glow" class="pg" cx="{f(cx)}" cy="{f(cy)}" r="{f(d["hole_r"] + 0.05)}" opacity="0"/></g>'
            + "".join(eyes) + "</g></svg>\n")


# --------------------------------------------------------------------------------------------
# rig.json
# --------------------------------------------------------------------------------------------

CLAW_FOLLOW = -0.8      # the claw counter-rotates against its arm, so a raised claw still points up (net 0.2x)
LENS_MAG = 1.5
LOOK_LEAN = 2           # deg of body lean at lookX = 1
ZZZ_PERIOD = 2400

PARAMS = [
    # name, default, min, max, unit, drives
    ("bodySquash", 1, 0.85, 1.15, "scaleY", "pinch-root scale about the feet [80,148]; scaleX = 1/sqrt(scaleY)"),
    ("bodyY", 0, -24, 8, "px", "pinch-root translateY (hops: ease-out up, ease-in down)"),
    ("tilt", 0, -12, 12, "deg", "pinch-root rotate about the feet; lookX adds a 2 deg lean"),
    ("clawL", 0, -40, 45, "deg", "arm-l rotate about the shoulder (+ raises); claw-l counter-rotates -0.8x so it stays upright"),
    ("clawR", 0, -40, 86, "deg", "arm-r rotate about the shoulder (+ raises, mirrored sign); claw-r counter-rotates -0.8x"),
    ("wristL", 0, -60, 140, "deg", "extra claw-l rotate about the wrist (+ turns the crusher in toward the face: thinking, clap)"),
    ("wristR", 0, -60, 140, "deg", "extra claw-r rotate about the wrist, mirrored sense"),
    ("pinch", 0, -1, 1, "0..1", "both claws: -1 wide open, 0 rest gap, 1 jaws meet (close_deg)"),
    ("pinchL", 0, -1, 1, "0..1", "crusher only, added to pinch and clamped"),
    ("pinchR", 0, -1, 1, "0..1", "cutter only (grips the lens handle), added to pinch and clamped"),
    ("eyeOpen", 1, 0, 1.3, "0..1.3", "both lids: coverage = 1 - eyeOpen; above 1 the eyes scale up (surprise 1.15)"),
    ("lidL", 0, 0, 1, "0..1", "extra lid coverage on eye-l, combined 1-(1-a)(1-b) with eyeOpen (sideeye dry lid 0.4)"),
    ("lidR", 0, 0, 1, "0..1", "extra lid coverage on eye-r"),
    ("browL", 0, -8, 14, "deg", "lid-l tilt: + kind (outer corner down), - dry; never a frown"),
    ("browR", 0, -8, 14, "deg", "lid-r tilt, same sense mirrored"),
    ("joy", 0, 0, 1, "0..1", "crossfade the eyes to happy closed ^ ^ arcs (celebrate)"),
    ("lookX", 0, -1, 1, "-1..1", "eye-l/eye-r translateX +-3.5 (lids ride along), body lean 2 deg"),
    ("lookY", 0, -1, 1, "-1..1", "eye-l/eye-r translateY +-2.5"),
    ("mouth", "smile", None, None, "shape", "the only shape swap: smile | flat | open | o (step)"),
    ("mouthCurve", 1, -0.2, 1.4, "scaleY", "smile height (0 = flat line, 1 = rest smile); clamped at -0.2, never a frown"),
    ("mouthTilt", 0, -14, 14, "deg", "mouth rotate about its centre (half smile)"),
    ("blush", 0, 0, 1, "0..1", "blush opacity (pinch-blush already carries its alpha)"),
    ("antennaSway", 0, -16, 16, "deg", "both antennae rotate the same way (right one x0.85)"),
    ("antennaLift", 0, -16, 24, "deg", "antennae perk up (+) or droop (-), mirrored"),
    ("sparkle", 0, 0, 1, "0..1", "sparkle opacity and burst scale 0.72 -> 1.06"),
    ("sweat", 0, 0, 1, "0..1", "sweat drop opacity, slides 3.5 px down as it appears"),
    ("zzz", 0, 0, 1, "0..1", "z opacity; the three z's drift on a 2400 ms cycle of engine time"),
    ("lens", 0, 0, 1, "0..1", "0 lowered in the cutter -> 1 glass on eye-r (IK macro on arm-r, claw-r, lens); lens-view shows the magnified eye from 0.72"),
    ("lensGlow", 0, 0, 1, "0..1", "camera light: green wash in the glass + a ring outside the rim. Carries information: never animate it for decoration"),
    ("lensZoom", 1, 0.8, 1.4, "scale", "lens scale about the glass centre (the tap toward the viewer)"),
    ("lensOut", 0, 0, 1, "0..1", "lens tucked away (opacity 0, scale 0.65 about the grip) so both claws can clap"),
    ("glint", 0, 0, 1, "0..1", "one green glint sweeps across the glass, opacity sin(pi*glint) (connected)"),
    ("paper", 0, 0, 1, "0..1", "paper slip in the crusher (reading)"),
    ("bloom", 0, 0, 1, "0..1", "the one allowed gradient, behind Pinch, celebrate only"),
]


def jaw_spec():
    out = {}
    for s in "lr":
        fr = claw_frame(s)
        out[s] = {
            "top": {"local": list(HINGE_TOP), "world": [round(v, 1) for v in fr.ap(HINGE_TOP)], "close_deg": CLOSE_TOP, "open_deg": OPEN_TOP},
            "bottom": {"local": list(HINGE_BOT), "world": [round(v, 1) for v in fr.ap(HINGE_BOT)], "close_deg": CLOSE_BOT, "open_deg": OPEN_BOT},
        }
    return out


def r1(p):
    return [round(p[0], 2), round(p[1], 2)]


def build_rig():
    J = jaw_spec()
    parts = {
        "pinch-root": dict(pivot=list(FEET), parent=None, transforms="translate(0,bodyY) rotate(tilt + 2*lookX, feet) scale(1/sqrt(bodySquash), bodySquash, feet)"),
        "bloom": dict(pivot=list(BLOOM_C), parent=None, transforms="opacity bloom; scale 0.8+0.2*bloom"),
        "tail": dict(pivot=list(TAIL_BASE), parent="pinch-root", transforms="static (LOD: hidden below 40 px)"),
        "legs": dict(pivot=[80, 140], parent="pinch-root", transforms="static (LOD: hidden below 96 px)"),
        "body": dict(pivot=[80, 144], parent="pinch-root", transforms="static carrier for face parts"),
        "antenna-l": dict(pivot=list(ANT["l"][0]), parent="body", transforms="rotate(antennaLift + antennaSway)"),
        "antenna-r": dict(pivot=list(ANT["r"][0]), parent="body", transforms="rotate(-antennaLift + 0.85*antennaSway)"),
        "belly": dict(pivot=list(BELLY_C), parent="body", transforms="static"),
        "blush": dict(pivot=[80, BLUSH["l"][1]], parent="body", transforms="opacity blush"),
        "eye-l": dict(pivot=list(EYES["l"]), parent="body", transforms="translate(lookX*3.5, lookY*2.5) scale(max(1,eyeOpen))"),
        "eye-r": dict(pivot=list(EYES["r"]), parent="body", transforms="translate(lookX*3.5, lookY*2.5) scale(max(1,eyeOpen))"),
        "lid-l": dict(pivot=[EYES["l"][0], round(lid_edge_y("l"), 2)], parent="eye-l", transforms="translate(0, coverage*lidSpan) rotate(-browL, lid edge); clipped to the eye"),
        "lid-r": dict(pivot=[EYES["r"][0], round(lid_edge_y("r"), 2)], parent="eye-r", transforms="translate(0, coverage*lidSpan) rotate(browR, lid edge)"),
        "mouth": dict(pivot=list(MOUTH_C), parent="body", transforms="rotate(mouthTilt); child shape by mouth; smile scaleY(mouthCurve) about its corners"),
        "arm-l": dict(pivot=list(SHOULDER["l"]), parent="pinch-root", transforms="rotate(clawL)"),
        "claw-l": dict(pivot=list(WRIST["l"]), parent="arm-l", transforms="rotate(-0.8*clawL + wristL)"),
        "jaw-l-top": dict(pivot=J["l"]["top"]["world"], parent="claw-l", transforms="rotate(jaw angle) about jaws.top.local (dactyl)"),
        "jaw-l-bottom": dict(pivot=J["l"]["bottom"]["world"], parent="claw-l", transforms="rotate(jaw angle) about jaws.bottom.local (fixed finger)"),
        "paper": dict(pivot=list(WRIST["l"]), parent="claw-l", transforms="opacity paper"),
        "arm-r": dict(pivot=list(SHOULDER["r"]), parent="pinch-root", transforms="rotate(-clawR + lens*lensRaise.arm)"),
        "claw-r": dict(pivot=list(WRIST["r"]), parent="arm-r", transforms="rotate(0.8*clawR - wristR + lens*lensRaise.claw)"),
        "jaw-r-top": dict(pivot=J["r"]["top"]["world"], parent="claw-r", transforms="as jaw-l-top (the claw frame is mirrored, same signed angle closes)"),
        "jaw-r-bottom": dict(pivot=J["r"]["bottom"]["world"], parent="claw-r", transforms="as jaw-l-bottom"),
        "lens": dict(pivot=r1(GRIP), parent="claw-r", transforms="translate(lens*lensRaise.slide) scale(lensZoom, glass) scale(1-0.35*lensOut, grip); opacity 1-lensOut"),
        "lens-glow": dict(pivot=r1(GLASS_C), parent="lens", transforms="children lens-ring, lens-wash: opacity lensGlow"),
        "lens-glint": dict(pivot=r1(GLASS_C), parent="lens", transforms="static specular arcs at 10 and 2 o'clock"),
        "lens-sweep": dict(pivot=r1(GLASS_C), parent="lens", transforms="translate along the 45 deg diagonal (-1.25..1.25)*r by glint; opacity sin(pi*glint); clipped to the glass"),
        "lens-view": dict(pivot=r1(GLASS_C), parent="lens", transforms="opacity smoothstep(0.72,0.96,lens); clipped to the glass"),
        "lens-eye": dict(pivot=list(EYES["r"]), parent="lens-view", transforms="matrix = inverse(world(lens)) * scale(1.5 about the glass centre in world) * world(eye-r)"),
        "sweat": dict(pivot=list(SWEAT), parent="pinch-root", transforms="opacity sweat; translateY 3.5*(sweat-1)"),
        "zzz": dict(pivot=[121, 25], parent="pinch-root", transforms="opacity zzz; z0..z2 drift (5,-11)*phase on a 2400 ms cycle"),
        "sparkle": dict(pivot=list(SPARKLE_C), parent=None, transforms="opacity 1.6*sparkle; scale 0.72+0.34*sparkle about the centre"),
    }
    geom = {
        "eyes": {s: list(EYES[s]) for s in "lr"}, "eyeR": [EYE_RX, EYE_RY], "look": list(LOOK), "lookLean": LOOK_LEAN,
        "lidSpan": round(LID_SPAN, 3), "lidEdge": {s: round(lid_edge_y(s), 3) for s in "lr"},
        "mouth": list(MOUTH_C), "smileY": round(MOUTH_C[1] - 1.6, 3),
        "antenna": {s: list(ANT[s][0]) for s in "lr"},
        "shoulder": {s: list(SHOULDER[s]) for s in "lr"}, "wrist": {s: list(WRIST[s]) for s in "lr"},
        "clawFollow": CLAW_FOLLOW,
        "clawFrame": {s: claw_frame_attr(s) for s in "lr"},
        "jaws": {"top": J["l"]["top"] | {"world": None}, "bottom": J["l"]["bottom"] | {"world": None}},
        "glass": r1(GLASS_C), "glassR": LENS_R, "grip": r1(GRIP), "lensMag": LENS_MAG,
        "lensRaise": {k: LENS_RAISE[k] for k in ("arm", "claw", "slide", "target")},
        "sweat": list(SWEAT), "sparkleC": list(SPARKLE_C), "bloom": list(BLOOM_C), "zzzPeriod": ZZZ_PERIOD,
    }
    for k in ("top", "bottom"):
        geom["jaws"][k].pop("world")
    return {
        "viewBox": [0, 0, 160, 160],
        "units": "viewBox user units; every transform is an SVG transform attribute about the listed pivot (equivalent to transform-box: view-box)",
        "feet": list(FEET),
        "order": "bloom, pinch-root > [tail, legs, body > [antenna-l, antenna-r, torso, belly, blush, eye-l > lid-l, eye-r > lid-r, mouth], "
                 "arm-l > claw-l > [jaw-l-bottom, jaw-l-top, palm, paper], arm-r > claw-r > [jaw-r-bottom, lens > [lens-glow, lens-view > lens-eye, rim, lens-glint], jaw-r-top, palm], sweat, zzz], sparkle",
        "parts": parts,
        "jaws": J,
        "params": [dict(name=n, default=d, min=lo, max=hi, unit=u, drives=dr) for n, d, lo, hi, u, dr in PARAMS],
        "geom": geom,
    }


def dump(obj, ind=0):
    """JSON with scalar arrays and keyframes on one line, objects indented one space per level."""
    pad, pad1 = " " * ind, " " * (ind + 1)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [f"{pad1}{json.dumps(k)}: {dump(v, ind + 1)}" for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}" + ("\n" if ind == 0 else "")
    if isinstance(obj, list):
        if all(not isinstance(v, (dict, list)) for v in obj):
            return "[" + ", ".join(json.dumps(v) for v in obj) + "]"
        if all(isinstance(v, list) and all(not isinstance(x, (dict, list)) for x in v) for v in obj):
            return "[" + ", ".join(dump(v) for v in obj) + "]"
        return "[\n" + ",\n".join(pad1 + dump(v, ind + 1) for v in obj) + "\n" + pad + "]"
    return json.dumps(obj)


# --------------------------------------------------------------------------------------------
# clips.json: moods (loops / holds), one-shot clips, blink, easings, policy.
# Track keys are [ms, value, ease]; the ease shapes the segment arriving at that key.
# Every clip starts and ends at rest; the engine blends it over the current mood (policy.blend_*).
# Conventions used below: anticipation 120-180 ms against the action; antennae lag the body by
# 60-90 ms and overshoot ~1.5x; claws settle 40 ms after the body; squash keeps volume.
# --------------------------------------------------------------------------------------------

EASINGS = {
    "linear": "linear",
    "step": "step",
    "out": "cubic-bezier(0.23,1,0.32,1)",          # --ease-out
    "in-out": "cubic-bezier(0.65,0,0.35,1)",       # --ease-in-out
    "sine": "cubic-bezier(0.37,0,0.63,1)",         # loops
    "anticip": "cubic-bezier(0.5,0,0.75,0)",       # wind-ups and falls (accelerating)
    "overshoot": "cubic-bezier(0.2,0.9,0.3,1.25)", # the action beat, ~7% past the key
    "settle": "spring(350,0.4)",                   # settle: response 0.35, damping 0.6
    "snappy": "spring(350,0.15)",                  # --spring-snappy
    "smooth": "spring(500,0)",                     # --spring-smooth
    "celebrate": "spring(600,0.4)",                # --spring-celebrate (mascot only)
}


def snap2(t0, param="pinchL"):
    """Pinch's signature: shut 90 ms, open 140 ms, shut 90 ms, then rest open."""
    return {param: [[t0, 0], [t0 + 90, 1, "out"], [t0 + 230, 0, "out"], [t0 + 320, 1, "out"], [t0 + 410, 0, "out"]]}


def merge(*ds):
    out = {}
    for d in ds:
        for k, v in d.items():
            out.setdefault(k, []).extend(v)
    for k in out:
        out[k].sort(key=lambda kf: kf[0])
    return out


MOODS = {
    "idle": dict(loop=True, dur=4000, key=0, tracks={
        "bodySquash": [[0, 1], [2000, 1.025, "sine"], [4000, 1, "sine"]],
        "antennaSway": [[0, 0], [1000, 3.5, "sine"], [3000, -3.5, "sine"], [4000, 0, "sine"]],
        "antennaLift": [[0, 0], [2070, 1.5, "sine"], [4000, 0, "sine"]],
    }),
    "focused": dict(loop=True, dur=3000, key=0, tracks={
        "eyeOpen": [[0, 0.8]],
        "browL": [[0, 4]],
        "browR": [[0, 4]],
        "lensGlow": [[0, 1]],
        "lookY": [[0, 0.2]],
        "lookX": [[0, -0.12], [1500, 0.12, "sine"], [3000, -0.12, "sine"]],
        "tilt": [[0, -2.5]],
        "bodySquash": [[0, 1], [1500, 1.015, "sine"], [3000, 1, "sine"]],
        "antennaLift": [[0, 3]],
        "antennaSway": [[0, 0], [70, 0], [190, 2.5, "out"], [520, 0, "settle"], [1570, 0], [1690, -2.5, "out"], [2020, 0, "settle"]],
        "clawL": [[0, 0], [120, 7, "out"], [420, 0, "settle"]],
        "clawR": [[0, 0], [1500, 0], [1620, 7, "out"], [1920, 0, "settle"]],
        "mouthCurve": [[0, 0.85]],
    }),
    "listening": dict(loop=True, dur=4000, key=0, tracks={
        "eyeOpen": [[0, 1.1]],
        "lookY": [[0, 0.55]],
        "tilt": [[0, 4]],
        "antennaLift": [[0, 8], [2070, 9.5, "sine"], [4000, 8, "sine"]],
        "antennaSway": [[0, 2]],
        "clawL": [[0, 6]],
        "bodySquash": [[0, 1], [2000, 1.02, "sine"], [4000, 1, "sine"]],
        "mouthCurve": [[0, 0.85]],
    }),
    "thinking": dict(loop=True, dur=1200, key=150, tracks={
        "lens": [[0, 0.5], [150, 0.58, "out"], [330, 0.5, "settle"], [600, 0.5], [750, 0.58, "out"], [930, 0.5, "settle"]],
        "lookX": [[0, -0.75]],
        "lookY": [[0, -0.85]],
        "antennaSway": [[0, -6], [300, 6, "sine"], [600, -6, "sine"], [900, 6, "sine"], [1200, -6, "sine"]],
        "antennaLift": [[0, 4]],
        "mouth": [[0, "flat"]],
        "mouthTilt": [[0, -7]],
        "eyeOpen": [[0, 0.95]],
        "tilt": [[0, -3]],
        "clawL": [[0, -8]],
    }),
    "sleepy": dict(loop=True, dur=5000, key=1250, tracks={
        "eyeOpen": [[0, 0.3]],
        "bodySquash": [[0, 0.97], [2500, 0.985, "sine"], [5000, 0.97, "sine"]],
        "bodyY": [[0, 0], [2500, 1.2, "sine"], [5000, 0, "sine"]],
        "tilt": [[0, -2.5], [2500, 2.5, "sine"], [5000, -2.5, "sine"]],
        "antennaLift": [[0, -12], [2570, -9, "sine"], [5000, -12, "sine"]],
        "antennaSway": [[0, -3], [2570, 3, "sine"], [5000, -3, "sine"]],
        "lookY": [[0, 0.4]],
        "zzz": [[0, 1]],
        "mouthCurve": [[0, 0.35]],
        "clawL": [[0, -14]],
        "clawR": [[0, -8]],
        "lensGlow": [[0, 0]],
    }),
    "reading": dict(loop=True, dur=2400, key=300, tracks={
        "paper": [[0, 1]],
        "lens": [[0, 1]],
        "lookX": [[0, -0.75], [1100, -0.15, "in-out"], [1250, -0.15], [1450, -0.75, "out"], [2400, -0.75]],
        "lookY": [[0, 0.1], [1100, 0.25, "in-out"], [1450, 0.4, "out"], [2400, 0.1, "in-out"]],
        "bodySquash": [[0, 1], [1200, 1.015, "sine"], [2400, 1, "sine"]],
        "antennaLift": [[0, 4]],
        "antennaSway": [[0, -2], [1170, 2, "in-out"], [1520, -2, "out"]],
        "mouthCurve": [[0, 0.6]],
        "tilt": [[0, -2]],
    }),
}

CLIPS = {
    # onboarding / first open of the day: crouch, pop up, crusher waves 3x, then the double snap
    "hello": dict(loop=False, dur=1400, priority=1, key=420, tracks=merge({
        "bodySquash": [[0, 1], [150, 0.9, "anticip"], [330, 1.08, "overshoot"], [480, 0.98, "out"], [800, 1, "settle"]],
        "bodyY": [[0, 0], [150, 2, "anticip"], [330, -8, "out"], [520, 0, "anticip"]],
        "antennaLift": [[0, 0], [220, -8, "anticip"], [400, 14, "overshoot"], [560, -4, "out"], [900, 0, "settle"]],
        "clawL": [[0, 0], [150, -8, "anticip"], [370, 32, "overshoot"], [540, 14, "in-out"], [710, 32, "in-out"], [880, 14, "in-out"],
                  [1050, 26, "in-out"], [1400, 0, "settle"]],
        "wristL": [[0, 0], [370, -10, "out"], [540, 12, "in-out"], [710, -10, "in-out"], [880, 12, "in-out"], [1050, -6, "in-out"], [1400, 0, "settle"]],
        "mouth": [[0, "smile"], [300, "open"], [1000, "smile"]],
        "eyeOpen": [[0, 1], [150, 0.85, "anticip"], [330, 1.12, "overshoot"], [700, 1, "out"]],
        "blush": [[0, 0], [400, 0.6, "out"], [1100, 0.6], [1400, 0, "out"]],
        "tilt": [[0, 0], [330, -3, "out"], [700, 3, "sine"], [1050, -2, "sine"], [1400, 0, "settle"]],
    }, snap2(960))),
    # a nudge alert: the lens goes up to the eye toward the cause; one dry lid, the other eye big in the glass
    "sideeye": dict(loop=False, dur=1400, priority=4, key=720, tracks={
        "bodySquash": [[0, 1], [140, 0.97, "anticip"], [380, 1.01, "out"], [1400, 1]],
        "clawR": [[0, 0], [140, -8, "anticip"], [380, 0, "out"]],
        "lens": [[0, 0], [140, 0], [420, 1, "overshoot"], [1100, 1], [1400, 0, "in-out"]],
        "tilt": [[0, 0], [140, 1.5, "anticip"], [420, -5, "out"], [1100, -5], [1400, 0, "settle"]],
        "lookX": [[0, 0], [160, 0], [380, 0.75, "out"], [700, 0.75], [820, 0.9, "out"], [1100, 0.9], [1400, 0, "in-out"]],
        "lookY": [[0, 0], [380, 0.3, "out"], [1100, 0.3], [1400, 0, "in-out"]],
        "lidL": [[0, 0], [200, 0], [420, 0.42, "out"], [1100, 0.42], [1360, 0, "in-out"]],
        "browL": [[0, 0], [420, -5, "out"], [1100, -5], [1360, 0, "in-out"]],
        "antennaLift": [[0, 0], [230, -2, "anticip"], [490, 5, "overshoot"], [1170, 5], [1400, 0, "settle"]],
        "antennaSway": [[0, 0], [230, 3, "anticip"], [490, -9, "overshoot"], [700, -6, "out"], [1170, -6], [1400, 0, "settle"]],
        "mouth": [[0, "smile"], [380, "flat"], [1250, "smile"]],
        "mouthTilt": [[0, 0], [380, -8, "out"], [1250, 0, "out"]],
        "lensGlow": [[0, 0], [420, 1, "out"], [1100, 1], [1400, 0, "out"]],
    }),
    # chained after sideeye: a lens tap toward the viewer, the crusher pinches twice, a sweat drop
    "nudge": dict(loop=False, dur=900, priority=4, key=330, tracks={
        "clawR": [[0, 0], [150, -12, "anticip"], [300, 14, "overshoot"], [560, 6, "out"], [900, 0, "settle"]],
        "lens": [[0, 0], [150, 0, "anticip"], [300, 0.22, "out"], [560, 0.18], [900, 0, "settle"]],
        "lensZoom": [[0, 1], [150, 0.92, "anticip"], [300, 1.3, "overshoot"], [460, 1.16, "out"], [900, 1, "settle"]],
        "pinchL": [[0, 0], [360, 0], [420, 1, "out"], [540, 0, "out"], [600, 1, "out"], [720, 0, "out"]],
        "clawL": [[0, 0], [150, -6, "anticip"], [340, 12, "overshoot"], [700, 8], [900, 0, "settle"]],
        "sweat": [[0, 0], [200, 1, "out"], [700, 1], [900, 0, "out"]],
        "eyeOpen": [[0, 1], [150, 0.9, "anticip"], [300, 1.06, "out"], [900, 1, "out"]],
        "mouth": [[0, "smile"], [120, "flat"], [300, "smile"]],
        "mouthCurve": [[0, 1], [300, 0.55, "out"], [900, 1, "out"]],
        "bodySquash": [[0, 1], [150, 0.95, "anticip"], [300, 1.04, "overshoot"], [500, 1, "settle"]],
        "tilt": [[0, 0], [150, -3, "anticip"], [300, 3, "out"], [900, 0, "settle"]],
        "antennaSway": [[0, 0], [220, -6, "anticip"], [370, 8, "overshoot"], [600, -2, "out"], [900, 0, "settle"]],
        "lensGlow": [[0, 0], [300, 1, "out"], [700, 1], [900, 0, "out"]],
    }),
    # verdict done: lens tucked, crouch, hop -18, land squash, claws up and clap (double snap x2), ^ ^, bloom, sparkles
    "celebrate": dict(loop=False, dur=1600, priority=5, key=760, tracks={
        "lensOut": [[0, 0], [120, 1, "out"], [1250, 1], [1600, 0, "out"]],
        "bodySquash": [[0, 1], [160, 0.88, "anticip"], [380, 1.12, "overshoot"], [520, 0.9, "out"], [640, 1.04, "out"], [800, 1, "settle"]],
        "bodyY": [[0, 0], [160, 4, "anticip"], [380, -18, "out"], [520, 0, "anticip"]],
        "clawL": [[0, 0], [160, -10, "anticip"], [420, 34, "overshoot"], [560, 26, "out"], [1250, 26], [1600, 0, "settle"]],
        "clawR": [[0, 0], [160, -10, "anticip"], [420, 84, "overshoot"], [560, 74, "out"], [1250, 74], [1600, 0, "settle"]],
        "wristL": [[0, 0], [420, 6, "out"], [1250, 6], [1600, 0, "settle"]],
        "wristR": [[0, 0], [420, 10, "out"], [1250, 10], [1600, 0, "settle"]],
        "pinch": [[0, 0], [600, 0], [690, 1, "out"], [830, 0, "out"], [920, 1, "out"], [1060, 0, "out"]],
        "joy": [[0, 0], [200, 1, "out"], [1300, 1], [1560, 0, "out"]],
        "mouth": [[0, "smile"], [200, "open"], [1350, "smile"]],
        "blush": [[0, 0], [380, 0.6, "out"], [520, 0.85, "out"], [1200, 0.85], [1600, 0, "out"]],
        "sparkle": [[0, 0], [380, 0], [560, 1, "out"], [900, 0.8], [1300, 0.2, "out"], [1600, 0]],
        "bloom": [[0, 0], [350, 1, "out"], [1100, 0.8], [1600, 0, "in-out"]],
        "antennaLift": [[0, 0], [230, 6, "anticip"], [450, -14, "out"], [590, 14, "overshoot"], [710, -4, "out"], [870, 2, "out"], [1100, 0, "settle"]],
        "tilt": [[0, 0], [800, 0], [960, -3, "sine"], [1120, 3, "sine"], [1300, 0, "settle"]],
    }),
    # verdict partial: honest, not a party. Half smile, crusher up 30, the other claw shrugs, two small nods
    "partial": dict(loop=False, dur=1000, priority=5, key=380, tracks={
        "clawL": [[0, 0], [140, -6, "anticip"], [380, 30, "overshoot"], [760, 28], [1000, 0, "settle"]],
        "wristL": [[0, 0], [380, -14, "out"], [760, -14], [1000, 0, "settle"]],
        "clawR": [[0, 0], [180, -12, "out"], [700, -12], [1000, 0, "settle"]],
        "bodySquash": [[0, 1], [140, 0.97, "anticip"], [300, 1.02, "out"], [420, 0.975, "in-out"], [560, 1.01, "in-out"], [680, 0.98, "in-out"], [900, 1, "settle"]],
        "lookY": [[0, 0], [300, 0.45, "in-out"], [420, 0, "in-out"], [560, 0.45, "in-out"], [680, 0, "in-out"]],
        "mouthCurve": [[0, 1], [300, 0.6, "out"], [800, 0.6], [1000, 1, "out"]],
        "mouthTilt": [[0, 0], [300, -11, "out"], [800, -11], [1000, 0, "out"]],
        "tilt": [[0, 0], [140, -1.5, "anticip"], [340, 4, "out"], [760, 3], [1000, 0, "settle"]],
        "browL": [[0, 0], [300, 5, "out"], [800, 5], [1000, 0]],
        "browR": [[0, 0], [300, 5, "out"], [800, 5], [1000, 0]],
        "antennaSway": [[0, 0], [210, -3, "anticip"], [410, 6, "overshoot"], [830, 4], [1000, 0, "settle"]],
    }),
    # verdict slacked: kind outward lids, a slow blink and a slow nod, claws lowered. Stays green.
    "supportive": dict(loop=False, dur=1400, priority=5, key=460, tracks={
        "browL": [[0, 0], [300, 9, "out"], [1100, 9], [1400, 0, "in-out"]],
        "browR": [[0, 0], [300, 9, "out"], [1100, 9], [1400, 0, "in-out"]],
        "lidL": [[0, 0], [300, 0.2, "out"], [1100, 0.2], [1400, 0, "in-out"]],
        "lidR": [[0, 0], [300, 0.2, "out"], [1100, 0.2], [1400, 0, "in-out"]],
        "eyeOpen": [[0, 1], [520, 1], [700, 0.08, "in-out"], [900, 1, "in-out"]],
        "clawL": [[0, 0], [200, -20, "out"], [1150, -20], [1400, 0, "settle"]],
        "clawR": [[0, 0], [240, -16, "out"], [1190, -16], [1400, 0, "settle"]],
        "tilt": [[0, 0], [300, 5, "in-out"], [1100, 5], [1400, 0, "settle"]],
        "lookY": [[0, 0], [420, 0], [680, 0.6, "in-out"], [940, 0, "in-out"]],
        "bodySquash": [[0, 1], [420, 1], [680, 0.97, "in-out"], [940, 1, "in-out"]],
        "mouthCurve": [[0, 1], [300, 1.2, "out"], [1100, 1.2], [1400, 1, "out"]],
        "antennaLift": [[0, 0], [370, -5, "out"], [1170, -5], [1400, 0, "settle"]],
        "blush": [[0, 0], [300, 0.5, "out"], [1100, 0.5], [1400, 0]],
    }),
    # correction saved: eyes 115%, a squash pop, antennae spring, "o", then a noted nod
    "surprise": dict(loop=False, dur=700, priority=3, key=260, tracks={
        "eyeOpen": [[0, 1], [80, 0.85, "anticip"], [200, 1.15, "overshoot"], [480, 1.1], [700, 1, "out"]],
        "bodySquash": [[0, 1], [80, 0.95, "anticip"], [200, 1.08, "overshoot"], [340, 0.98, "out"], [600, 1, "settle"]],
        "bodyY": [[0, 0], [200, -3, "out"], [340, 0, "anticip"]],
        "antennaLift": [[0, 0], [150, -4, "anticip"], [280, 22, "overshoot"], [400, 10, "out"], [520, 16, "out"], [700, 0, "settle"]],
        "mouth": [[0, "smile"], [150, "o"], [450, "smile"]],
        "sweat": [[0, 0], [200, 0.9, "out"], [500, 0.9], [700, 0, "out"]],
        "lookY": [[0, 0], [480, 0], [580, 0.5, "in-out"], [700, 0, "in-out"]],
        "clawL": [[0, 0], [80, -4, "anticip"], [240, 10, "overshoot"], [700, 0, "settle"]],
        "clawR": [[0, 0], [80, -4, "anticip"], [240, 8, "overshoot"], [700, 0, "settle"]],
    }),
    # a link (Strava, iPhone, Calendar): the lens glints green once, a lift toward the viewer, double snap
    "connected": dict(loop=False, dur=1000, priority=2, key=420, tracks=merge({
        "lensGlow": [[0, 0], [200, 1, "out"], [520, 1], [800, 0, "in-out"]],
        "glint": [[0, 0], [200, 0], [620, 1, "in-out"], [621, 0, "step"]],
        "lensZoom": [[0, 1], [120, 0.94, "anticip"], [260, 1.14, "overshoot"], [520, 1, "settle"]],
        "clawR": [[0, 0], [120, -6, "anticip"], [260, 22, "overshoot"], [580, 18], [1000, 0, "settle"]],
        "sparkle": [[0, 0], [200, 0.6, "out"], [600, 0.3], [900, 0]],
        "eyeOpen": [[0, 1], [260, 1.06, "out"], [600, 1, "out"]],
        "mouthCurve": [[0, 1], [260, 1.25, "out"], [800, 1, "out"]],
        "blush": [[0, 0], [260, 0.4, "out"], [800, 0, "out"]],
        "bodySquash": [[0, 1], [120, 0.97, "anticip"], [260, 1.03, "overshoot"], [520, 1, "settle"]],
        "antennaLift": [[0, 0], [190, -3, "anticip"], [330, 9, "overshoot"], [600, 0, "settle"]],
    }, snap2(560))),
}

BLINK = dict(dur=140, tracks={"eyeOpen": [[0, 1], [60, 0.05, "anticip"], [140, 1, "out"]]},
             every_ms=[3000, 6000], double_chance=0.15, double_gap_ms=180,
             compose="multiply eyeOpen; skipped while a clip drives eyeOpen or joy, and in still/reduced motion")

POLICY = {
    "cooldown_ms": 90000,
    "priority_order": ["celebrate", "partial", "supportive", "sideeye", "nudge", "surprise", "connected", "hello"],
    "preempt": "a higher priority clip pre-empts a lower one even inside the cooldown; equal or lower is dropped, not queued",
    "force": "{force:true} bypasses the cooldown (verdict clips, and the nudge chained after sideeye)",
    "chain": {"sideeye": "nudge"},
    "max_sideeye_per_session": 3,
    "blend_in_ms": 120,
    "blend_out_ms": 240,
    "idle_gaze": {"every_ms": [4000, 8000], "lookX": [-0.35, 0.35], "lookY": [-0.2, 0.25], "dur_ms": 420, "ease": "in-out", "moods": ["idle"]},
    "rest_after_ms": 120000,
    "still": "still:true and prefers-reduced-motion: render seek(name, key) with no loop, no breath and no blink; clips crossfade 200 ms to their key frame; lensGlow still follows the camera state",
    "composition": {
        "order": "neutral <- mood (loop time) <- clip (absolute, weighted by the blend) ; blink multiplies eyeOpen ; lookAt adds to lookX/lookY (clamped -1..1)",
        "lensGlow": "max(host camera state, clip value): the lens never claims the camera is off while it samples",
        "mouth": "string tracks switch at their key; the blend snaps the shape at 50%",
    },
}


def build_clips():
    out = {"moods": {}, "clips": {}, "blink": BLINK, "easings": EASINGS, "policy": POLICY}
    for name, d in MOODS.items():
        out["moods"][name] = d
    for name, d in CLIPS.items():
        out["clips"][name] = d
    # sanity: every track sorted, inside [0, dur], every ease known, every param known
    known = {n for n, *_ in PARAMS}
    for group in ("moods", "clips"):
        for name, d in out[group].items():
            for k, tr in d["tracks"].items():
                assert k in known, (name, k)
                ts = [kf[0] for kf in tr]
                assert ts == sorted(ts) and ts[0] >= 0 and ts[-1] <= d["dur"], (name, k, ts)
                for kf in tr:
                    assert len(kf) == 2 or kf[2] in EASINGS, (name, k, kf)
            if not d["loop"]:
                for k, tr in d["tracks"].items():
                    dflt = next(df for n, df, *_ in PARAMS if n == k)
                    assert tr[0][1] == dflt and tr[-1][1] == dflt, ("clip must start and end at rest", name, k)
    return out



SHEET = r"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pinch pose sheet</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600&display=swap">
<link rel="stylesheet" href="../tokens/tokens.css">
<style>
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);font:400 16px/var(--body-lh,1.6) var(--font-sans);letter-spacing:var(--body-ls,.01em);
  font-variant-numeric:tabular-nums;padding:var(--space-8) var(--space-8) var(--space-12);min-width:1520px}
header{display:flex;align-items:baseline;justify-content:space-between;gap:var(--space-6);margin-bottom:var(--space-6)}
header p{color:var(--ink-2);max-width:62ch}
section{margin-top:var(--space-8)}
section>h2{margin-bottom:var(--space-3)}
.panel{border-radius:var(--radius-lg);padding:var(--space-4) var(--space-4) var(--space-3);border:1px solid var(--hairline);background:var(--bg)}
.panel+.panel{margin-top:var(--space-3)}
.panel[data-theme=light]{background:var(--surface-1)}
.panel>.t-label{color:var(--ink-2);display:flex;justify-content:space-between;margin-bottom:var(--space-2)}
.row{display:flex;align-items:flex-end;gap:var(--space-4);flex-wrap:wrap}
figure{display:flex;flex-direction:column;align-items:center;gap:var(--space-1);cursor:pointer;border-radius:var(--radius-md);padding:var(--space-1) 0 var(--space-2)}
figure:hover{background:var(--surface-1)}
figure .stage{container-type:inline-size;container-name:pinch;display:block}
figure .stage svg{display:block;width:100%;height:100%}
figcaption{display:flex;flex-direction:column;align-items:center;gap:2px}
figcaption b{font:600 13px/1.3 var(--font-sans);color:var(--ink)}
figcaption span{font:500 12px/1.4 var(--font-mono);color:var(--ink-3)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:var(--space-3);align-items:start}
.grid2>.panel{margin-top:0}
.menubar{background:var(--surface-3);border-radius:var(--radius-sm);height:64px;display:flex;justify-content:center;gap:var(--space-8);align-items:flex-start;position:relative}
.notch{background:#000;height:32px;border-radius:0 0 12px 12px;display:flex;align-items:center;justify-content:space-between;padding:0 12px 0 10px} /* lint-ok: the notch is hardware black */
.notch .val{font:600 13px/1 var(--font-rounded);font-variant-numeric:tabular-nums;color:var(--ink)}
[data-theme=light] .notch .val{color:#F2F2F2} /* lint-ok: notch text is always on hardware black */
.cap{font:400 13px/1.45 var(--font-sans);color:var(--ink-2);text-align:center;margin-top:var(--space-2)}
.wings{display:flex;gap:var(--space-4);flex-wrap:wrap;align-items:flex-start}
.wings>div{display:flex;flex-direction:column;align-items:center}
.toast{display:flex;gap:var(--space-3);align-items:flex-start;background:var(--surface-2);border-radius:var(--radius-md);padding:var(--space-4);max-width:520px;box-shadow:var(--shadow-float)}
.toast .av{width:20px;height:20px;flex:none;margin-top:4px}
.toast .t-h3{margin-bottom:2px}
.toast .t-voice{color:var(--ink)}
.noun{color:var(--warn-ink)}
.btns{display:flex;gap:var(--space-2);margin-top:var(--space-3)}
.btn{white-space:nowrap;font:600 13px/1 var(--font-sans);border-radius:var(--radius-pill);padding:9px 14px;border:1px solid var(--hairline-strong);color:var(--ink);background:transparent}
.btn.primary{background:var(--accent);color:var(--on-accent);border-color:transparent}
.alert{background:#000;border-radius:0 0 28px 28px;width:430px;padding:var(--space-3) var(--space-4) var(--space-4);display:flex;gap:var(--space-3);align-items:center;color:#F2F2F2} /* lint-ok: hardware black island */
.alert .t-small{color:rgba(242,242,242,.6)} /* lint-ok: island secondary is 60% white */
.alert .btn{border-color:rgba(255,255,255,.24);color:#F2F2F2} /* lint-ok: island chrome */
.alert .btn.primary{color:#000;border-color:transparent} /* lint-ok: text on green is always black */
.ctx{display:flex;gap:var(--space-8);align-items:flex-start;flex-wrap:wrap}
.legend{color:var(--ink-2);font:400 13px/1.45 var(--font-sans);margin-top:var(--space-2)}
</style>
</head>
<body>
<header>
  <div><h1 class="t-h1">Pinch</h1><p class="t-small" style="color:var(--ink-2)">Canonical rig. Every tile is <code class="t-mono">pinch.svg</code> posed by <code class="t-mono">rig.js</code> from <code class="t-mono">clips.json</code> at the clip's key frame.</p></div>
  <p class="t-small">Click any figure to play it. Moods loop twice, clips play once and return to their key frame.</p>
</header>

<section><h2 class="t-h2">Moods</h2>
  <div class="panel" data-theme="dark"><div class="t-label"><span>On #000, no outline</span><span>160 px</span></div><div class="row" data-set="moods"></div></div>
  <div class="panel" data-theme="light"><div class="t-label"><span>On #FFF, outline 3</span><span>160 px</span></div><div class="row" data-set="moods"></div></div>
</section>

<section><h2 class="t-h2">Clips</h2>
  <div class="panel" data-theme="dark"><div class="t-label"><span>On #000, no outline</span><span>160 px, key frame</span></div><div class="row" data-set="clips"></div></div>
  <div class="panel" data-theme="light"><div class="t-label"><span>On #FFF, outline 3</span><span>160 px, key frame</span></div><div class="row" data-set="clips"></div></div>
</section>

<section><h2 class="t-h2">Size ladder</h2>
  <div class="grid2">
    <div class="panel" data-theme="dark"><div class="t-label"><span>On #000</span><span>full · 56 rung · lod24 · lod20 · lod16</span></div><div class="row" data-set="ladder"></div></div>
    <div class="panel" data-theme="light"><div class="t-label"><span>On #FFF</span><span>outline 3 · 3.6 · 5.5</span></div><div class="row" data-set="ladder"></div></div>
  </div>
</section>

<section><h2 class="t-h2">Notch wing</h2>
  <div class="grid2">
    <div class="panel" data-theme="dark"><div class="t-label"><span>Live wing, 185 × 32 notch</span><span>camera off · camera on</span></div>
      <div class="menubar" data-set="notch"></div>
      <p class="legend">The lens ring is its own colour; camera on fills the hole with spark green. The wing glyph is static: no loop in the wings.</p></div>
    <div class="panel" data-theme="dark"><div class="t-label"><span>State tints, 16 pt</span><span>on task · idle · phone · absent</span></div>
      <div class="wings" data-set="tints"></div>
      <p class="legend">Body and crusher take <code class="t-mono">--pinch-silhouette</code>; the lens keeps its colour, so camera on never collides with a tint.</p></div>
  </div>
</section>

<section><h2 class="t-h2">In context</h2>
  <div class="grid2">
    <div class="panel" data-theme="dark"><div class="t-label"><span>Nudge alert in the island</span><span>56 pt, sideeye key frame</span></div>
      <div class="ctx" data-set="alert"></div></div>
    <div class="panel" data-theme="dark"><div class="t-label"><span>Dashboard nudge toast</span><span>PinchLine: 20 px silhouette</span></div>
      <div class="ctx" data-set="toast"></div></div>
  </div>
</section>

<section><h2 class="t-h2">Rig stress</h2>
  <div class="panel" data-theme="dark"><div class="t-label"><span>Every param at its limits</span><span>120 px</span></div><div class="row" data-set="stress"></div></div>
  <div class="panel" data-theme="light"><div class="t-label"><span>Same, light</span><span>120 px</span></div><div class="row" data-set="stress"></div></div>
</section>

<script>
/*RIGJS*/
</script>
<script>
var SVG = /*SVG*/, LOD24 = /*LOD24*/, LOD20 = /*LOD20*/, LOD16 = /*LOD16*/;
var RIG = /*RIG*/;
var CLIPS = /*CLIPS*/;
var R = window.AlibiPinchRig, uid = 0;
R.setEasings(CLIPS.easings);
var NOTES = {
  idle: 'breath + blinks', focused: 'lids 20%, lens lit', listening: 'leans in, perks up', thinking: 'lens tap, eyes up-left',
  sleepy: 'lids 70%, zzz', reading: 'paper + lens', hello: 'wave + double snap', sideeye: 'magnified eye, dry lid',
  nudge: 'lens tap + sweat', celebrate: '^ ^, bloom, clap', partial: 'half smile, shrug', supportive: 'kind lids, nod',
  surprise: 'eyes 115%, antennae', connected: 'green glint'
};
function stage(markup, size, lod) {
  var d = document.createElement('div');
  d.className = 'stage'; d.style.width = d.style.height = size + 'px';
  d.innerHTML = R.prefixIds(markup, 'p' + (uid++) + '-');
  var svg = d.querySelector('svg');
  if (lod) svg.setAttribute('data-lod', lod);
  return d;
}
function figure(name, sub, size, params, opts) {
  opts = opts || {};
  var f = document.createElement('figure');
  var st = stage(opts.markup || SVG, size, opts.lod);
  f.appendChild(st);
  var c = document.createElement('figcaption');
  c.innerHTML = '<b>' + name + '</b>' + (sub ? '<span>' + sub + '</span>' : '');
  f.appendChild(c);
  var svg = st.querySelector('svg');
  if (params) R.apply(svg, params, RIG, opts.t || 0);
  if (opts.play) f.addEventListener('click', function () { play(svg, opts.play); });
  return f;
}
function play(svg, name) {
  var def = CLIPS.moods[name] || CLIPS.clips[name], t0 = performance.now(), total = def.loop ? def.dur * 2 : def.dur;
  function frame(now) {
    var t = now - t0, p = R.neutral(RIG), s = R.sample(def, Math.min(t, total));
    for (var k in s) p[k] = s[k];
    R.apply(svg, p, RIG, t);
    if (t < total) requestAnimationFrame(frame); else R.apply(svg, R.pose(RIG, CLIPS, name), RIG, 0);
  }
  requestAnimationFrame(frame);
}
function each(set, fn) { document.querySelectorAll('[data-set="' + set + '"]').forEach(fn); }

each('moods', function (row) {
  Object.keys(CLIPS.moods).forEach(function (m) {
    var d = CLIPS.moods[m];
    row.appendChild(figure(m, NOTES[m] , 160, R.pose(RIG, CLIPS, m), { play: m, t: d.key }));
  });
});
each('clips', function (row) {
  Object.keys(CLIPS.clips).forEach(function (c) {
    var d = CLIPS.clips[c];
    row.appendChild(figure(c, d.key + ' / ' + d.dur + ' ms · p' + d.priority, 160, R.pose(RIG, CLIPS, c), { play: c }));
  });
});
each('ladder', function (row) {
  var idle = R.neutral(RIG);
  [[160, null], [96, null], [56, '56'], [28, '28']].forEach(function (z) {
    row.appendChild(figure(String(z[0]), z[1] === '28' ? 'lod24' : (z[1] ? 'rung 56' : 'full'), z[0], idle, { lod: z[1], markup: z[0] === 28 ? LOD24 : SVG }));
  });
  row.appendChild(figure('20', 'lod20', 20, null, { markup: LOD20 }));
  row.appendChild(figure('16', 'lod16', 16, null, { markup: LOD16 }));
});
function glyph(n, lit, tint) {
  var s = stage(n === 16 ? LOD16 : LOD20, n);
  var svg = s.querySelector('svg');
  if (lit) svg.classList.add('lit');
  if (tint) svg.style.setProperty('--pinch-silhouette', 'var(' + tint + ')');
  return s;
}
function notch(n, lit, tint, val, w) {
  var wrap = document.createElement('div');
  var no = document.createElement('div');
  no.className = 'notch'; no.style.width = (w || 277) + 'px';
  no.appendChild(glyph(n, lit, tint));
  var v = document.createElement('span'); v.className = 'val'; v.textContent = val; no.appendChild(v);
  wrap.appendChild(no);
  return wrap;
}
each('notch', function (bar) {
  [[16, false, '16 pt · camera off'], [16, true, '16 pt · camera on'], [20, false, '20 pt · camera off'], [20, true, '20 pt · camera on']].forEach(function (c) {
    var w = notch(c[0], c[1], null, '24:10', 150);
    var cap = document.createElement('p'); cap.className = 'cap'; cap.textContent = c[2]; w.appendChild(cap);
    bar.appendChild(w);
  });
  bar.style.gap = '12px'; bar.style.height = 'auto'; bar.style.padding = '0 0 12px';
});
each('tints', function (row) {
  [['--on-task', '24m', 'on task'], ['--idle', 'idle', 'idle'], ['--phone', '3m', 'phone'], ['--absent', 'away', 'absent']].forEach(function (c, i) {
    var w = notch(16, i === 0, c[0], c[1], 120);
    var cap = document.createElement('p'); cap.className = 'cap'; cap.textContent = c[2] + (i === 0 ? ', camera on' : ''); w.appendChild(cap);
    row.appendChild(w);
  });
});
each('alert', function (box) {
  var a = document.createElement('div'); a.className = 'alert';
  var f = stage(SVG, 56, '56');
  R.apply(f.querySelector('svg'), R.pose(RIG, CLIPS, 'sideeye'), RIG, 0);
  f.style.flex = 'none';
  a.appendChild(f);
  var t = document.createElement('div');
  t.innerHTML = '<p style="font:500 15px/1.35 var(--font-sans)">You said drawing. I’ve seen your <span class="noun">phone</span> for 3 minutes.</p>' +
    '<p class="t-small">Drawing · 14:02 left</p>' +
    '<div class="btns"><span class="btn primary">Back to it</span><span class="btn">This counts</span><span class="btn">Quiet 5 min</span></div>';
  a.appendChild(t);
  box.appendChild(a);
});
each('toast', function (box) {
  var t = document.createElement('div'); t.className = 'toast';
  var av = glyph(20, true); av.classList.add('av'); t.appendChild(av);
  var b = document.createElement('div');
  b.innerHTML = '<p class="t-h3">Nudge</p><p class="t-voice">You said drawing. I’ve seen your <span class="noun">phone</span> for 3 minutes.</p>' +
    '<div class="btns"><span class="btn primary">Back to it</span><span class="btn">This counts</span></div>';
  t.appendChild(b);
  box.appendChild(t);
});
each('stress', function (row) {
  var L = {}; RIG.params.forEach(function (d) { L[d.name] = d; });
  function mx(n) { return L[n].max; } function mn(n) { return L[n].min; }
  var S = [
    ['neutral', {}], ['jaws shut', { pinch: 1 }], ['jaws wide', { pinch: -1 }], ['lids 0.5', { eyeOpen: 0.5 }],
    ['look right', { lookX: 1, lookY: 0.4 }], ['look up-left', { lookX: -1, lookY: -1 }], ['lens raised', { lens: 1, lensGlow: 1 }],
    ['squash ' + mn('bodySquash'), { bodySquash: mn('bodySquash') }], ['stretch ' + mx('bodySquash'), { bodySquash: mx('bodySquash'), bodyY: -12 }],
    ['tilt ' + mn('tilt'), { tilt: mn('tilt') }],
    ['claws max', { clawL: mx('clawL'), clawR: mx('clawR'), pinch: -1, lensOut: 1 }], ['claws min', { clawL: mn('clawL'), clawR: mn('clawR') }],
    ['eyes ' + mx('eyeOpen'), { eyeOpen: mx('eyeOpen'), antennaLift: mx('antennaLift') }],
    ['brows +' + mx('browL'), { browL: mx('browL'), browR: mx('browR'), lidL: 0.3, lidR: 0.3 }],
    ['antennae droop', { antennaLift: mn('antennaLift'), antennaSway: mx('antennaSway') }],
    ['mouth o, sweat', { mouth: 'o', sweat: 1, eyeOpen: 1.15 }]
  ];
  S.forEach(function (s) { var p = R.neutral(RIG); for (var k in s[1]) p[k] = s[1][k]; row.appendChild(figure(s[0], '', 120, p)); });
});
</script>
</body>
</html>
"""


def build_sheet():
    def js(v):
        return json.dumps(v, separators=(",", ":"))
    html = SHEET
    html = html.replace("/*RIGJS*/", (OUT / "rig.js").read_text())
    html = html.replace("/*SVG*/", js((OUT / "pinch.svg").read_text()))
    html = html.replace("/*LOD24*/", js((OUT / "pinch-lod24.svg").read_text()))
    html = html.replace("/*LOD20*/", js((OUT / "pinch-lod20.svg").read_text()))
    html = html.replace("/*LOD16*/", js((OUT / "pinch-lod16.svg").read_text()))
    html = html.replace("/*RIG*/", js(json.loads((OUT / "rig.json").read_text())))
    html = html.replace("/*CLIPS*/", js(json.loads((OUT / "clips.json").read_text())))
    return html


if __name__ == "__main__":
    (OUT / "pinch.svg").write_text(build_svg())
    (OUT / "pinch-lod24.svg").write_text(build_svg("24"))
    (OUT / "pinch-lod20.svg").write_text(build_silhouette(20))
    (OUT / "pinch-lod16.svg").write_text(build_silhouette(16))
    (OUT / "rig.json").write_text(dump(build_rig()))
    (OUT / "clips.json").write_text(dump(build_clips()))
    (OUT / "pose-sheet.html").write_text(build_sheet())
    print("close", CLOSE_TOP, CLOSE_BOT, "raise", LENS_RAISE)
