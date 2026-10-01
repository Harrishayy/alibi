#!/usr/bin/env python3
"""Pinch variant C ("glyph-first precision") generator.

Every part is a hand-placed primitive (circle, capsule, arc, rounded rect);
this script only does the trigonometry for arc end points and writes the rig
files with compact, rounded path data.  Poses are transforms on the same rig.
"""
import json, math, pathlib

OUT = pathlib.Path("/Users/harrishayyanar/Documents/nvidia_habits/docs/design/pinch/variants/C")
OUT.mkdir(parents=True, exist_ok=True)

# ---------- palette (only these) ----------
BODY, BELLY, SHADE, OUTLINE, RIM = "#76B900", "#97DC42", "#588C05", "#365900", "#8FD400"
EYE, SHINE, BLUSH, SPARK = "#000", "#FFF", "#F2A900", "#AAF059"
LENS_RIM, LENS_HANDLE, GLASS = "#D7D7D7", "#5E5E5E", "rgba(255,255,255,.15)"
SWEAT = "#A6A6A6"


def f(v):
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def pt(c, r, deg):
    a = math.radians(deg)
    return (c[0] + r * math.cos(a), c[1] + r * math.sin(a))


def arc(c, r, a0, a1):
    """Circular arc path from angle a0 to a1 (degrees, SVG angle sense)."""
    p0, p1 = pt(c, r, a0), pt(c, r, a1)
    sweep = 1 if a1 > a0 else 0
    large = 1 if abs(a1 - a0) > 180 else 0
    return f"M{f(p0[0])} {f(p0[1])}A{f(r)} {f(r)} 0 {large} {sweep} {f(p1[0])} {f(p1[1])}"


def star(cx, cy, s):
    k = s * 0.18
    return (f"M{f(cx)} {f(cy - s)}C{f(cx + k)} {f(cy - k)} {f(cx + k)} {f(cy - k)} {f(cx + s)} {f(cy)}"
            f"C{f(cx + k)} {f(cy + k)} {f(cx + k)} {f(cy + k)} {f(cx)} {f(cy + s)}"
            f"C{f(cx - k)} {f(cy + k)} {f(cx - k)} {f(cy + k)} {f(cx - s)} {f(cy)}"
            f"C{f(cx - k)} {f(cy - k)} {f(cx - k)} {f(cy - k)} {f(cx)} {f(cy - s)}Z")


# ---------- the rig: geometry (viewBox 0 0 160 160, feet at y=148) ----------
FEET = (80, 148)
BODY_D = "M44 84A36 36 0 0 1 116 84V110A26 26 0 0 1 90 136H70A26 26 0 0 1 44 110Z"
# form shade: lower-right crescent that hugs the body edge
SHADE_D = "M116 92V110A26 26 0 0 1 90 136H78C98 133 111 120 113.5 100Z"
GLINT_D = "M53.5 72.5C55.5 64 61 57.5 68.5 54"           # stroked highlight arc
BELLY_D = "M64 117a16 16 0 0 1 32 0v3a14 14 0 0 1-14 14h-4a14 14 0 0 1-14-14z"
SEGS = ["M67.5 121.5Q80 125 92.5 121.5", "M70 129Q80 131.5 90 129"]
EYES = {"l": (65.5, 82), "r": (94.5, 82)}
EYE_RX, EYE_RY = 8.6, 10.6
MOUTH_NEUTRAL = "M76 98Q80 101.5 84 98"

# claws: built in a local frame (wrist at 0,0, pointing up), then placed.
# jaw-bottom = palm + fixed finger (front); jaw-top = hinged dactyl (tucked behind the palm)
PALM_D = ("M-13 -13A13 13 0 1 0 12.2 -17.4C13 -27 10 -35 5.6 -39.4A2.8 2.8 0 0 0 0.9 -36.6"
          "C3.6 -32 3.2 -27 -0.5 -23.5C-5.5 -26 -11.5 -22 -13 -13Z")
DACTYL_D = ("M-3 -14L-12.4 -17.2C-15.2 -27 -12.6 -35.4 -7.6 -39.6A2.8 2.8 0 0 1 -3.2 -37.2"
            "C-7.2 -33 -7.4 -28 -3.6 -23.4Z")
PALM_SHADE_D = "M-12.2 -8.6A13 13 0 0 0 9.4 -4C2 -1.6 -7 -3 -12.2 -8.6Z"
HINGE = (-6, -19)
CLAWS = {"l": {"w": (34, 86), "a": -28}, "r": {"w": (126, 86), "a": 28}}
SHOULDER = {"l": (51, 104), "r": (109, 104)}
ARM_W = 9

ANT = {"l": "M73.5 53C70 37 59 25.5 41 22.5", "r": "M86.5 53C90 37 101 25.5 119 22.5"}
ANT_BASE = {"l": (73.5, 53), "r": (86.5, 53)}

LEGS = [((51, 126), (45, 139.5)), ((58, 131), (55.5, 145)),
        ((102, 131), (104.5, 145)), ((109, 126), (115, 139.5))]
LEG_W = 7

# tail: a short segmented stub tucked behind the body, fan to the left

LENS_C, LENS_R, LENS_W = (94.5, 82), 14.5, 3.5
LENS_HANDLE_ANGLE, LENS_HANDLE_LEN, LENS_HANDLE_W = 52, 11, 5.5

BLUSH_POS = {"l": (53, 97.5), "r": (110, 95.5)}

SPARKS = [(25, 28, 7), (137, 24, 6), (150, 82, 4.5), (11, 90, 4.5), (116, 9, 3.5)]
SWEAT_D = "M120.5 41C123.5 45.5 125 48 125 50.2A4.5 4.5 0 0 1 116 50.2C116 48 117.5 45.5 120.5 41Z"


def claw_frame(side):
    w, a = CLAWS[side]["w"], CLAWS[side]["a"]
    m = " scale(-1 1)" if side == "r" else ""
    return f"translate({f(w[0])} {f(w[1])}) rotate({f(a)}){m}"


def arm_d(side):
    s, w = SHOULDER[side], CLAWS[side]["w"]
    return f"M{f(s[0])} {f(s[1])}L{f(w[0])} {f(w[1])}"


# ---------- pose description ----------
NEUTRAL = dict(
    root="", arm_l=0, arm_r=0, claw_l=0, claw_r=0, pinch_l=0.0, pinch_r=0.0,
    ant_l=0, ant_r=0, eyes="open", look=(0, 0), lid_l=0.0, lid_r=0.0, lid_tilt=0,
    eye_scale_r=1.0, mouth=MOUTH_NEUTRAL, mouth_fill=False, blush=0.0, sparkle=0.0,
    sweat=0.0, sweat_t="", lens="", lens_glow=False, tail=0, legs="", bloom=False, belly="",
)


def g_open(id_, transform="", extra=""):
    t = f' transform="{transform}"' if transform else ""
    return f'<g id="{id_}"{t}{extra}>'


def rot(a, p):
    return f"rotate({f(a)} {f(p[0])} {f(p[1])})" if a else ""


def jaw(id_, d, tip, angle, pivot):
    return (f'{g_open(id_, rot(angle, pivot))}'
            f'<path class="ou" d="{d}" stroke-width="{f(CLAW_W + 3)}"/>'
            f'<circle class="o" cx="{f(tip[0])}" cy="{f(tip[1])}" r="{f(CLAW_W / 2)}" fill="{BODY}"/>'
            f'<path d="{d}" stroke="{BODY}" stroke-width="{f(CLAW_W)}"/></g>')


def build(pose, title):
    P = dict(NEUTRAL, **pose)
    o = []
    o.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" class="pinch pinch-c" '
             f'role="img" aria-label="{title}">')
    o.append(STYLE)
    if P["bloom"]:
        o.append('<defs><radialGradient id="pinch-c-bloom"><stop offset="0" stop-color="#76B900" stop-opacity=".35"/>'
                 '<stop offset="1" stop-color="#76B900" stop-opacity="0"/></radialGradient></defs>'
                 '<circle id="bloom" cx="80" cy="82" r="72" fill="url(#pinch-c-bloom)"/>')
    o.append(f'<g id="pinch-root"{" transform=%s" % chr(34) + P["root"] + chr(34) if P["root"] else ""}>')
    # antennae (behind the head)
    for s in "lr":
        a = P[f"ant_{s}"]
        o.append(f'{g_open("antenna-" + s, rot(a, ANT_BASE[s]), " class=" + chr(34) + "lod-24" + chr(34))}'
                 f'<path d="{ANT[s]}" stroke="{SHADE}" stroke-width="3"/></g>')
    # tail: the abdomen curls under; its fan peeks out between the feet
    fan = []
    for ang, rx, ry, col in [(-34, 5.2, 8.6, SHADE), (34, 5.2, 8.6, SHADE), (0, 5.6, 9.4, BODY)]:
        cx, cy = 80 + math.sin(math.radians(ang)) * 6, 137 - math.cos(math.radians(ang)) * -1 + 2
        cx = 80 + math.sin(math.radians(ang)) * 7.5
        cy = 139 + (1 - math.cos(math.radians(ang))) * 3
        fan.append(f'<ellipse class="o" cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" '
                   f'transform="rotate({f(-ang)} {f(cx)} {f(cy)})" fill="{col}"/>')
    o.append(f'{g_open("tail", rot(P["tail"], (80, 132)), " class=" + chr(34) + "lod-48" + chr(34))}' + "".join(fan) + "</g>")
    # legs
    legs = "".join(
        f'<path class="ou" d="M{f(a[0])} {f(a[1])}L{f(b[0])} {f(b[1])}" stroke-width="{f(LEG_W + 3)}"/>'
        f'<path d="M{f(a[0])} {f(a[1])}L{f(b[0])} {f(b[1])}" stroke="{SHADE}" stroke-width="{f(LEG_W)}"/>'
        for a, b in LEGS)
    o.append(f'{g_open("legs", P["legs"], " class=" + chr(34) + "lod-48" + chr(34))}{legs}</g>')
    # arms + claws
    for s in "lr":
        w = CLAWS[s]["w"]
        pinch = P[f"pinch_{s}"]          # 0 rest (slightly open), 1 shut, <0 wide open
        o.append(g_open("arm-" + s, rot(P[f"arm_{s}"], SHOULDER[s])))
        o.append(f'<path class="ou" d="{arm_d(s)}" stroke-width="{f(ARM_W + 3)}"/>'
                 f'<path d="{arm_d(s)}" stroke="{SHADE}" stroke-width="{f(ARM_W)}"/>')
        o.append(g_open("claw-" + s, rot(P[f"claw_{s}"], w)))
        o.append(f'<g transform="{claw_frame(s)}">')
        o.append(f'{g_open("jaw-" + s + "-top", rot(11 * pinch, HINGE))}<path class="o" d="{DACTYL_D}" fill="{BODY}"/></g>')
        o.append(f'{g_open("jaw-" + s + "-bottom", rot(-3 * pinch, (0, -13)))}<path class="o" d="{PALM_D}" fill="{BODY}"/>'
                 f'<path class="lod-48" d="{PALM_SHADE_D}" fill="{SHADE}"/></g>')
        o.append("</g></g></g>")
    # body
    o.append(f'<g id="body"><path class="o" d="{BODY_D}" fill="{BODY}"/>'
             f'<path d="{SHADE_D}" fill="{SHADE}"/>'
             f'<path class="lod-48" d="{GLINT_D}" stroke="{BELLY}" stroke-width="4.5"/></g>')
    o.append(f'{g_open("belly", P["belly"], " class=" + chr(34) + "lod-24" + chr(34))}<path d="{BELLY_D}" fill="{BELLY}"/>'
             + "".join(f'<path d="{d}" stroke="{SHADE}" stroke-width="2"/>' for d in SEGS) + "</g>")
    # blush
    bl = "".join(f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="5.5" ry="3.2" fill="{BELLY}"/>'
                 f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="5.5" ry="3.2" fill="{BLUSH}" fill-opacity=".4"/>' for x, y in BLUSH_POS.values())
    o.append(f'<g id="blush" class="lod-24" opacity="{f(P["blush"])}">{bl}</g>' if P["blush"] else
             f'<g id="blush" class="lod-24" opacity="0">{bl}</g>')
    # lens: a loupe worn like a monocle over eye-r
    lc = LENS_C
    h0 = pt(lc, LENS_R + LENS_W / 2 - 0.5, LENS_HANDLE_ANGLE)
    h1 = pt(lc, LENS_R + LENS_W / 2 + LENS_HANDLE_LEN, LENS_HANDLE_ANGLE)
    c0 = pt(lc, LENS_R + LENS_W / 2 + 2.6, LENS_HANDLE_ANGLE)
    glow = (f'<g id="lens-glow"{"" if P["lens_glow"] else " opacity=" + chr(34) + "0" + chr(34)}>'
            f'<circle cx="{lc[0]}" cy="{lc[1]}" r="{f(LENS_R)}" fill="none" stroke="#76B900" stroke-width="9" stroke-opacity=".35"/>'
            f'<circle cx="{lc[0]}" cy="{lc[1]}" r="{f(LENS_R - LENS_W / 2)}" fill="#AAF059" fill-opacity=".18"/></g>')
    o.append(f'{g_open("lens", P["lens"], " class=" + chr(34) + "lod-48" + chr(34))}'
             f'<path d="M{f(h0[0])} {f(h0[1])}L{f(h1[0])} {f(h1[1])}" stroke="{LENS_HANDLE}" stroke-width="{f(LENS_HANDLE_W)}"/>'
             f'<path d="M{f(pt(lc, LENS_R + 0.5, LENS_HANDLE_ANGLE)[0])} {f(pt(lc, LENS_R + 0.5, LENS_HANDLE_ANGLE)[1])}'
             f'L{f(c0[0])} {f(c0[1])}" stroke="{LENS_RIM}" stroke-width="8.5" style="stroke-linecap:butt"/>'
             + glow +
             f'<circle cx="{lc[0]}" cy="{lc[1]}" r="{f(LENS_R)}" fill="{GLASS}" stroke="{LENS_RIM}" stroke-width="{f(LENS_W)}"/>'
             f'<path d="{arc(lc, LENS_R - 3.4, 196, 240)}" stroke="#FFF" stroke-opacity=".7" stroke-width="2"/></g>')
    # eyes
    lx, ly = P["look"]
    for s in "lr":
        cx, cy = EYES[s]
        t = []
        if lx or ly:
            t.append(f"translate({f(lx)} {f(ly)})")
        if s == "r" and P["eye_scale_r"] != 1:
            k = P["eye_scale_r"]
            t.append(f"translate({f(cx * (1 - k))} {f(cy * (1 - k))}) scale({f(k)})")
        o.append(g_open("eye-" + s, " ".join(t)))
        happy = P["eyes"] == "happy"
        soft = P["eyes"] == "soft"
        o.append(f'<g class="eye-open"{" display=" + chr(34) + "none" + chr(34) if (happy or soft) else ""}>'
                 f'<ellipse cx="{cx}" cy="{cy}" rx="{EYE_RX}" ry="{EYE_RY}" fill="{EYE}"/>'
                 f'<circle class="eye-shine" cx="{f(cx - 2.6)}" cy="{f(cy - 4.2 + (6.2 * min(1, P[f"lid_{s}"] * 1.6)))}" r="{f(2.9 - 0.6 * min(1, P[f"lid_{s}"] * 1.6))}" fill="{SHINE}"/></g>')
        o.append(f'<path class="eye-happy" d="M{f(cx - 7)} {f(cy + 2.5)}Q{f(cx)} {f(cy - 8.5)} {f(cx + 7)} {f(cy + 2.5)}" '
                 f'stroke="{EYE}" stroke-width="4"{"" if happy else " display=" + chr(34) + "none" + chr(34)}/>')
        o.append(f'<path class="eye-soft" d="M{f(cx - 7)} {f(cy - 0.5)}Q{f(cx)} {f(cy + 7)} {f(cx + 7)} {f(cy - 0.5)}" '
                 f'stroke="{EYE}" stroke-width="4"{"" if soft else " display=" + chr(34) + "none" + chr(34)}/>')
        lid = P[f"lid_{s}"]
        # lid: top half of a slightly larger ellipse in body colour, scaled down from the brow
        top = cy - EYE_RY - 1.5
        lid_t = f"translate(0 {f(top)}) scale(1 {f(lid)}) translate(0 {f(-top)})"
        if P["lid_tilt"]:
            lid_t = rot(P["lid_tilt"] * (1 if s == "l" else -1), (cx, top)) + " " + lid_t
        o.append(f'<g id="lid-{s}" transform="{lid_t}"{"" if lid else " opacity=" + chr(34) + "0" + chr(34)}>'
                 f'<path d="M{f(cx - 10)} {f(top + 23.5)}V{f(top + 6)}A10 6 0 0 1 {f(cx + 10)} {f(top + 6)}V{f(top + 23.5)}Z" fill="{BODY}"/>'
                 f'<path d="M{f(cx - 9)} {f(top + 23.5)}H{f(cx + 9)}" stroke="{OUTLINE}" stroke-width="2" opacity=".55"/></g>')
        o.append("</g>")
    # mouth
    mf = f' fill="{EYE}"' if P["mouth_fill"] else ""
    o.append(f'<g id="mouth" class="lod-24"><path d="{P["mouth"]}" stroke="{EYE}" stroke-width="2.5"{mf}/></g>')
    # sparkle + sweat
    sp = "".join(f'<path d="{star(x, y, s)}" fill="{SPARK}"/>' for x, y, s in SPARKS)
    o.append(f'<g id="sweat" class="lod-24"{(" transform=" + chr(34) + P["sweat_t"] + chr(34)) if P["sweat_t"] else ""} opacity="{f(P["sweat"])}"><path d="{SWEAT_D}" fill="{SWEAT}"/>'
             f'<path d="M118.6 49.5a2 2 0 0 0 1.6 2" stroke="#FFF" stroke-width="1.2" opacity=".8"/></g>')
    o.append("</g>")
    o.append(f'<g id="sparkle" class="lod-24" opacity="{f(P["sparkle"])}">{sp}</g>')
    o.append("</svg>")
    return "\n".join(o) + "\n"


STYLE = """<style>
.pinch path,.pinch circle,.pinch ellipse{stroke-linecap:round;stroke-linejoin:round}
.pinch path:not([fill]){fill:none}
.pinch .o{stroke:var(--pinch-outline,#365900);stroke-width:3;paint-order:stroke}
.pinch .ou{fill:none;stroke:var(--pinch-outline,#365900);stroke-linecap:round}
.pinch.on-dark{--pinch-outline:transparent}
.pinch.on-dark.rim{--pinch-outline:#8FD400}
@media (prefers-color-scheme:dark){.pinch:not(.on-light){--pinch-outline:transparent}}
@media (max-width:47px){.pinch .lod-48{display:none}}
@media (max-width:23px){.pinch .lod-24{display:none}}
@container pinch (max-width:47px){.pinch .lod-48{display:none}}
@container pinch (max-width:23px){.pinch .lod-24{display:none}}
</style>"""



def about(p, t):
    return f"translate({f(p[0])} {f(p[1])}) {t} translate({f(-p[0])} {f(-p[1])})"


L = LENS_C
POSES = {
    "pinch": ({}, "Pinch, idle"),
    "pose-celebrate": (dict(
        root="translate(0 -9) " + about(FEET, "scale(.95 1.07)"),
        arm_l=24, arm_r=-24, claw_l=-10, claw_r=10, pinch_l=-0.7, pinch_r=-0.7,
        ant_l=-14, ant_r=14, eyes="happy", mouth="M72.5 96.5Q80 97.5 87.5 96.5Q86.5 106 80 106Q73.5 106 72.5 96.5Z",
        mouth_fill=True, blush=1.0, sparkle=1.0, bloom=True, legs="translate(0 3)", tail="",
        lens=f"translate(3 -8) rotate(-16 {L[0]} {L[1]})"), "Pinch, celebrating"),
    "pose-sideeye": (dict(
        root=f"rotate(-6 {FEET[0]} {FEET[1]})",
        arm_l=8, arm_r=4, claw_r=-6, pinch_r=0.55, look=(3.2, -0.4), lid_l=0.5, lid_r=0.42,
        ant_l=-6, ant_r=-12, sweat_t="translate(-70 8)", mouth="M76.5 99.6Q80.5 98.9 84.5 98", lens_glow=True,
        lens=f"translate(39 -43) rotate(9 {L[0]} {L[1]})", sweat=1.0), "Pinch, side-eye with the lens raised"),
    "pose-supportive": (dict(
        root=f"rotate(3 {FEET[0]} {FEET[1]})",
        arm_l=-42, arm_r=34, claw_l=56, claw_r=-60, pinch_l=-0.6, pinch_r=-0.5,
        ant_l=-10, ant_r=10, eyes="soft", mouth="M75.5 98Q80 102.5 84.5 98", blush=0.7,
        lens=f"rotate(4 {L[0]} {L[1]})"), "Pinch, a gentle shrug"),
}

# ---------- 16 px glyph: body (eyes cut out) + two notched claws = 5 shapes ----------
def silhouette():
    """16 px glyph. 5 shapes: body, two eye holes (cut with evenodd), two claws.
    Claws are mittens with a V bite at the tip, raised in the same V as the 160 px drawing."""
    body = ("M4.5 9A3.5 3.5 0 0 1 11.5 9V12.9A2.1 2.1 0 0 1 9.4 15H6.6A2.1 2.1 0 0 1 4.5 12.9Z"
            "M5.3 9.9a1.1 1.1 0 1 0 2.2 0a1.1 1.1 0 1 0-2.2 0Z"
            "M8.5 9.9a1.1 1.1 0 1 0 2.2 0a1.1 1.1 0 1 0-2.2 0Z")
    # local frame: wrist at 0,0, claw pointing up; a fat mitten with a short U bite
    claw = ("M-2.2 -2.2A2.2 2.2 0 0 0 2.2 -2.2V-4.6A0.825 0.825 0 0 0 0.55 -4.6V-4.1"
            "A0.55 0.55 0 0 1 -0.55 -4.1V-4.6A0.825 0.825 0 0 0 -2.2 -4.6Z")
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" class="pinch-glyph" role="img" aria-label="Pinch">\n'
            '<g id="pinch-root" fill="#76B900">\n'
            f'<path id="body" fill-rule="evenodd" d="{body}"/>\n'
            f'<path id="claw-l" transform="translate(2.9 8.6) rotate(-6)" d="{claw}"/>\n'
            f'<path id="claw-r" transform="translate(13.1 8.6) rotate(6)" d="{claw}"/>\n'
            '</g></svg>\n')


def f2(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def world(side, p):
    w, a = CLAWS[side]["w"], math.radians(CLAWS[side]["a"])
    x, y = p
    if side == "r":
        x = -x
    return (round(w[0] + x * math.cos(a) - y * math.sin(a), 1), round(w[1] + x * math.sin(a) + y * math.cos(a), 1))


def pivots():
    d = {
        "_note": "Rotation pivots [x, y] in viewBox units (0 0 160 160). Jaw pivots are given in their parent's local claw frame "
                 "(\"local\", used by the rotate() already on the jaw group; the right claw frame is mirrored, so the same "
                 "positive angle closes both claws) and in world space (\"world\").",
        "pinch-root": list(FEET), "body": [80, 136], "belly": [80, 120], "tail": [80, 132], "legs": [80, 128],
        "arm-l": list(SHOULDER["l"]), "arm-r": list(SHOULDER["r"]),
        "claw-l": list(CLAWS["l"]["w"]), "claw-r": list(CLAWS["r"]["w"]),
    }
    for s in "lr":
        d[f"jaw-{s}-top"] = {"local": list(HINGE), "world": list(world(s, HINGE)), "close_deg": 11, "open_deg": -9}
        d[f"jaw-{s}-bottom"] = {"local": [0, -13], "world": list(world(s, (0, -13))), "close_deg": -3, "open_deg": 3}
    for s in "lr":
        cx, cy = EYES[s]
        d[f"eye-{s}"] = [cx, cy]
        d[f"lid-{s}"] = {"origin": [cx, round(cy - EYE_RY - 1.5, 2)], "drive": "scaleY 0 (open) to 1 (shut)"}
    d.update({"mouth": [80, 99], "antenna-l": list(ANT_BASE["l"]), "antenna-r": list(ANT_BASE["r"]),
              "blush": [80, 96.5], "lens": list(LENS_C), "lens-grip": [round(pt(LENS_C, 27, LENS_HANDLE_ANGLE)[0], 1),
                                                                round(pt(LENS_C, 27, LENS_HANDLE_ANGLE)[1], 1)],
              "sparkle": [80, 60], "sweat": [120.5, 47]})
    d["rig"] = {"lookX_px": 3.2, "lookY_px": 3, "squash_origin": list(FEET), "volume": "scaleX = 1/sqrt(scaleY)"}
    return d


def uri(svg_text, cls=None):
    import urllib.parse
    if cls:
        svg_text = svg_text.replace('class="pinch pinch-c"', f'class="pinch pinch-c {cls}"', 1)
    return "data:image/svg+xml;charset=utf-8," + urllib.parse.quote(svg_text, safe=" =:/,;'")


def sheet():
    idle = (OUT / "pinch.svg").read_text()
    sil = (OUT / "silhouette-16.svg").read_text()
    sizes = [16, 20, 28, 56, 96, 160]

    def ladder(cls):
        return "".join(f'<figure class="sz"><img src="{uri(idle, cls)}" width="{n}" height="{n}" alt=""><figcaption>{n}</figcaption></figure>' for n in sizes)

    def poses(cls):
        out = []
        for name, label in [("pose-celebrate", "Celebrate"), ("pose-sideeye", "Side-eye, lens raised"), ("pose-supportive", "Supportive shrug")]:
            out.append(f'<figure class="pose"><img src="{uri((OUT / (name + ".svg")).read_text(), cls)}" width="160" height="160" alt="{label}"><figcaption>{label}</figcaption></figure>')
        return "".join(out)

    sil_uri = uri(sil)
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pinch variant C</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#000;--surface-1:#1A1A1A;--surface-2:#262626;--ink:#F2F2F2;--ink-2:#A6A6A6;--ink-3:#8C8C8C;--hairline:rgba(255,255,255,.08);--accent:#76B900;--accent-ink:#8FD400;
--font-sans:-apple-system,BlinkMacSystemFont,"SF Pro Text","Onest",system-ui,sans-serif;--font-rounded:ui-rounded,-apple-system,"SF Pro Rounded","Onest",system-ui,sans-serif;--font-mono:ui-monospace,"SF Mono",Menlo,monospace}}
*{{box-sizing:border-box;margin:0}}
body{{background:var(--bg);color:var(--ink);font:400 16px/1.6 var(--font-sans);letter-spacing:.01em;font-variant-numeric:tabular-nums;padding:32px 32px 24px;max-width:1200px}}
header{{display:flex;align-items:baseline;gap:16px;margin-bottom:20px}}
h1{{font-size:22px;line-height:1.25;font-weight:600;letter-spacing:-.015em}}
header p{{color:var(--ink-2);font-size:13px;line-height:1.45}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.panel{{border-radius:16px;padding:16px 20px 14px;border:1px solid var(--hairline)}}
.panel.dark{{background:#000}} .panel.light{{background:#FFF;color:#000;border-color:#D7D7D7}}
.label{{font-size:12px;line-height:1.3;font-weight:600;letter-spacing:.01em;color:var(--ink-2);margin-bottom:10px;display:flex;justify-content:space-between}}
.light .label{{color:#5E5E5E}}
.row{{display:flex;align-items:flex-end;gap:18px}}
figure{{display:flex;flex-direction:column;align-items:center;gap:6px}}
figcaption{{font:500 12px/1.4 var(--font-mono);color:var(--ink-3)}}
.light figcaption{{color:#6E6E6E}}
.pose figcaption{{font:400 13px/1.45 var(--font-sans)}}
img{{display:block}}
.wide{{grid-column:1/-1}}
.bar{{background:#D7D7D7;border-radius:10px;height:56px;position:relative;display:flex;justify-content:center;gap:120px;align-items:flex-start}}
.notch{{width:185px;height:32px;background:#000;border-radius:0 0 12px 12px;display:flex;align-items:center;justify-content:space-between;padding:0 12px}}
.notch.live{{width:277px}}
.wing{{font:600 13px/1 var(--font-rounded);color:#F2F2F2;font-variant-numeric:tabular-nums}}
.tints{{display:flex;gap:12px;background:#D7D7D7;border-radius:10px;padding:0 12px 10px}}
.notch.sm{{width:120px;height:28px;border-radius:0 0 10px 10px;padding:0 10px}}
.cmp{{display:flex;gap:16px;align-items:flex-end}}
.zoom{{image-rendering:pixelated;background:#000;outline:1px solid #262626}}
.bottom{{display:grid;grid-template-columns:1.25fr 1fr;gap:12px;margin-top:12px}}
.note{{color:var(--ink-2);font-size:13px;line-height:1.45;max-width:62ch}}
</style></head>
<body>
<header><h1>Pinch, variant C: glyph-first precision</h1><p>Drawn from the 16 px notch silhouette upward. Circles, capsules and two bold claw arcs; a loupe worn as a monocle.</p></header>
<div class="grid">
  <section class="panel dark"><div class="label"><span>Size ladder on #000</span><span>no outline</span></div><div class="row">{ladder("on-dark")}</div></section>
  <section class="panel light"><div class="label"><span>Size ladder on #FFFFFF</span><span>#365900 outline, 1.5 px</span></div><div class="row">{ladder("on-light")}</div></section>
  <section class="panel dark"><div class="label"><span>Poses at 160, dark</span></div><div class="row">{poses("on-dark")}</div></section>
  <section class="panel light"><div class="label"><span>Poses at 160, light</span></div><div class="row">{poses("on-light")}</div></section>
</div>
<div class="bottom">
  <section class="panel dark"><div class="label"><span>Notch wings: silhouette-16 at 16 and 20 pt</span><span>185 × 32 notch</span></div>
    <div class="bar">
      <div class="notch"><img src="{sil_uri}" width="16" height="16" alt="Pinch glyph at 16"><span class="wing">24m</span></div>
      <div class="notch"><img src="{sil_uri}" width="20" height="20" alt="Pinch glyph at 20"><span class="wing">24m</span></div>
    </div>
    <div class="label" style="margin-top:14px"><span>Wing glyph tinted by state, 16 pt</span><span>on task · idle · phone · absent</span></div>
    <div class="tints">{"".join(f'<div class="notch sm"><img src="{uri(sil.replace("#76B900", c))}" width="16" height="16" alt=""><span class="wing">{t}</span></div>' for c, t in [("#76B900", "24m"), ("#F2A900", "idle"), ("#E5484D", "3m"), ("#A6A6A6", "away")])}</div>
  </section>
  <section class="panel dark"><div class="label"><span>Dark grounds: no outline vs #8FD400 rim</span><span>16 px glyph, 8×</span></div>
    <div class="cmp">
      <figure><img src="{uri(idle, "on-dark")}" width="96" height="96" alt=""><figcaption>none</figcaption></figure>
      <figure><img src="{uri(idle, "on-dark rim")}" width="96" height="96" alt=""><figcaption>rim</figcaption></figure>
      <figure><img src="{uri(idle.replace('<g id="lens-glow" opacity="0">', '<g id="lens-glow">'), "on-dark")}" width="96" height="96" alt=""><figcaption>camera on</figcaption></figure>
      <figure><img class="zoom" src="{sil_uri}" width="128" height="128" alt=""><figcaption>5 shapes</figcaption></figure>
    </div>
  </section>
</div>
</body></html>
"""
    (OUT / "sheet.html").write_text(html)


if __name__ == "__main__":
    for name, (pose, title) in POSES.items():
        (OUT / f"{name}.svg").write_text(build(pose, title))
    (OUT / "silhouette-16.svg").write_text(silhouette())
    import re
    txt = json.dumps(pivots(), indent=2)
    txt = re.sub(r"\[\s+([-\d.]+),\s+([-\d.]+)\s+\]", r"[\1, \2]", txt)
    (OUT / "pivots.json").write_text(txt + "\n")
    sheet()
    print("ok")
