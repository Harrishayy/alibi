"""P1 — contact sheet of keyframes; P3 — title breakdown for digital sessions.

Drawn on the dark-first tokens (docs/design/tokens/tokens.css): surface-1 sheet, ink text, all-sans (SF Pro),
status = colour + shape + word, and black text on the green verdict pill.
"""
import datetime as dt
from collections import Counter
from PIL import Image, ImageDraw, ImageFont
from . import config

# Dark tokens: surface-1 · surface-2 · ink · ink-2 · ink-3 · hairline · hairline-strong
BG, SURFACE_2, INK, INK_2, INK_3 = "#1A1A1A", "#262626", "#F2F2F2", "#A6A6A6", "#8F8F8F"
HAIRLINE, KEYLINE = (255, 255, 255, 20), (255, 255, 255, 97)
CREAM, MUTED, RULE = BG, INK_2, SURFACE_2            # old names, kept for callers
ON_ACCENT = "#000000"                                # text on any green fill is black
# Status marks. phone and off_task share the red; off_task is told apart by its 45° hatch.
COLOURS = {"on_task": "#76B900", "phone": "#E5484D", "off_task": "#E5484D", "idle": "#F2A900", "absent": "#A6A6A6"}
WASH = {"on_task": "#1C2A06", "phone": "#3A1414", "off_task": "#3A1414", "idle": "#2E2203", "absent": "#262626"}
VERDICT_COLOUR = {"done": COLOURS["on_task"], "partial": COLOURS["idle"], "slacked": COLOURS["phone"]}
VERDICT_INK = {"done": "#8FD400", "partial": "#FFC233", "slacked": "#FF7A7E"}
VERDICT_WORD = {"done": "Done", "partial": "Partly", "slacked": "Slacked"}
LABEL_WORD = {"on_task": "on task", "phone": "phone", "off_task": "off task", "idle": "idle", "absent": "absent"}

_SANS = ("/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/HelveticaNeue.ttc",
         "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf")
_HELVETICA_INDEX = {400: 0, 500: 10, 600: 1, 800: 1}  # HelveticaNeue.ttc faces: 0 regular, 10 medium, 1 bold


def sans(size: int, weight: int = 400):
    """SF Pro at a weight (variable axes), else Helvetica Neue, else PIL's default. Never a serif."""
    for p in _SANS:
        try:
            if p.endswith("SFNS.ttf"):
                f = ImageFont.truetype(p, size)
                f.set_variation_by_axes([100, min(96, max(17, size)), 400, weight])  # width, optical size, grade, weight
                return f
            return ImageFont.truetype(p, size, index=_HELVETICA_INDEX.get(weight, 0) if p.endswith(".ttc") else 0)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default(size=size)


def _font(name: str, size: int):
    """Kept for callers: any old serif/mono request now resolves to the sans."""
    return sans(size, 600 if size >= 28 else 400)


def _hhmm(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%H:%M")


def _hatch(w: int, h: int, fg: str, bg: str, step: int, lw: int) -> Image.Image:
    tile = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(tile)
    for k in range(-h, w + h, step):
        d.line([(k, h), (k + h, 0)], fill=fg, width=lw)
    return tile


def mark(label: str, size: int) -> Image.Image:
    """StatusDot as an RGBA tile: ● on_task, ○ idle, ■ phone, ▨ off_task (hatched disc), ◌ absent (dashed ring)."""
    S = size * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = COLOURS.get(label, INK_2)
    ring = max(4, round(S * 2 / 12))
    if label == "idle":
        d.ellipse([ring // 2, ring // 2, S - ring // 2, S - ring // 2], outline=c, width=ring)
    elif label == "phone":
        i = round(S * 0.08)
        d.rounded_rectangle([i, i, S - i, S - i], radius=round(S * 0.24), fill=c)
    elif label == "off_task":
        disc = Image.new("L", (S, S), 0)
        ImageDraw.Draw(disc).ellipse([0, 0, S - 1, S - 1], fill=255)
        im.paste(_hatch(S, S, c, WASH["off_task"], max(6, S // 4), max(3, S // 9)), (0, 0), disc)
        d.ellipse([0, 0, S - 1, S - 1], outline=c, width=max(3, S // 12))
    elif label == "absent":
        w = max(3, round(S * 1.5 / 12))
        for a in range(0, 360, 45):
            d.arc([w // 2, w // 2, S - w // 2, S - w // 2], a, a + 26, fill=c, width=w)
    else:
        d.ellipse([0, 0, S - 1, S - 1], fill=c)
    return im.resize((size, size), Image.LANCZOS)


def _rounded(w: int, h: int, r: int) -> Image.Image:
    m = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], radius=r * 4, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def _keyline(w: int, h: int, r: int, rgba=KEYLINE) -> Image.Image:
    o = Image.new("RGBA", (w * 4, h * 4), (0, 0, 0, 0))
    ImageDraw.Draw(o).rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], radius=r * 4, outline=rgba, width=4)
    return o.resize((w, h), Image.LANCZOS)


def _verdict_glyph(d: ImageDraw.ImageDraw, x: float, cy: float, verdict: str, colour: str, s: int = 14):
    """✓ ◐ ✕ drawn as shapes (SF Pro's PIL path has no ◐/✕ glyphs)."""
    y = cy - s / 2
    if verdict == "done":
        d.line([(x + s * .1, y + s * .55), (x + s * .4, y + s * .85), (x + s * .95, y + s * .2)], fill=colour,
               width=max(2, s // 7), joint="curve")
    elif verdict == "partial":
        d.ellipse([x, y, x + s, y + s], outline=colour, width=max(2, s // 8))
        d.pieslice([x, y, x + s, y + s], 90, 270, fill=colour)
    else:
        w = max(2, s // 7)
        d.line([(x + s * .15, y + s * .15), (x + s * .85, y + s * .85)], fill=colour, width=w)
        d.line([(x + s * .15, y + s * .85), (x + s * .85, y + s * .15)], fill=colour, width=w)


def _wordmark(d: ImageDraw.ImageDraw, x: float, y: float, size: int, colour: str):
    f = sans(size, 800)
    for ch in "ALIBI":                                # tracking +0.13em, the one uppercase setting
        d.text((x, y), ch, font=f, fill=colour)
        x += d.textlength(ch, font=f) + size * 0.13


def verdict_pill(d: ImageDraw.ImageDraw, right: float, cy: float, verdict: str, text: str, size: int = 17) -> float:
    """VerdictPill: done = green fill with black text; partly/slacked = 10% wash with ink text (never a red slab).
    Draws right-aligned at `right`, vertically centred on cy; returns the pill's left edge."""
    f = sans(size, 600)
    h, g = round(size * 2.35), round(size * 0.8)
    tw = d.textlength(text, font=f)
    w = 16 + g + 8 + tw + 18
    x0, y0 = right - w, cy - h / 2
    if verdict == "done":
        fill, ink = VERDICT_COLOUR["done"], ON_ACCENT
    else:
        fill, ink = WASH["idle" if verdict == "partial" else "phone"], VERDICT_INK.get(verdict, INK)
    d.rounded_rectangle([x0, y0, right, y0 + h], radius=h / 2, fill=fill)
    _verdict_glyph(d, x0 + 16, cy, verdict, ink, g)
    d.text((x0 + 16 + g + 8, cy), text, font=f, fill=ink, anchor="lm")
    return x0


def status_strip(labels: list[str], w: int, h: int) -> Image.Image:
    """Every sample in order as a segment; off_task hatched; rounded ends. RGBA."""
    S = 4
    im = Image.new("RGB", (w * S, h * S), SURFACE_2)
    d = ImageDraw.Draw(im)
    seg = w * S / max(1, len(labels))
    for i, lab in enumerate(labels):
        x0, x1 = round(i * seg), round((i + 1) * seg)
        if lab == "off_task":
            im.paste(_hatch(max(1, x1 - x0), h * S, COLOURS["off_task"], WASH["off_task"], 6 * S, 2 * S), (x0, 0))
        else:
            d.rectangle([x0, 0, x1 - 1, h * S], fill=COLOURS.get(lab, INK_3))
    out = im.resize((w, h), Image.LANCZOS).convert("RGBA")
    out.putalpha(_rounded(w, h, h // 2))
    return out


def contact_sheet(session, label_events: list[dict], ratio: float, verdict: str) -> str | None:
    frames = [e for e in label_events if e["payload"].get("frame")]
    if not frames:
        return None
    k = min(12, len(frames))
    picks = [frames[round(i * (len(frames) - 1) / max(1, k - 1))] for i in range(k)] if k > 1 else frames[:1]
    cols, tw, th, pad, gap = 4, 300, 224, 48, 16
    rows = (len(picks) + cols - 1) // cols
    cap, pitch = 44, 224 + 44 + 24                   # caption band under each frame, row pitch
    head = 280
    W = pad * 2 + cols * tw + (cols - 1) * gap
    H = head + rows * pitch - 24 + pad
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet, "RGBA")

    # Header: wordmark, the claim, the verdict pill, then the facts.
    _wordmark(d, pad, pad, 13, INK_2)
    title = f"{config.display_name(session['habit'])}, {session['declared_min']} min"
    d.text((pad, pad + 28), title, font=sans(40, 600), fill=INK)
    word = VERDICT_WORD.get(verdict, verdict.capitalize())
    verdict_pill(d, W - pad, pad + 54, verdict, f"{word} · {ratio:.0%} on task")
    meta = (f"{_hhmm(session['started_at'])} → {_hhmm(label_events[-1]['ts'])}  ·  "
            f"{len(label_events)} samples  ·  witness: {_witness(label_events)}")
    d.text((pad, pad + 96), meta, font=sans(17), fill=INK_2)

    # Timeline: every sample, in order, then a legend with shape + word for each label present.
    ys = pad + 140
    strip = status_strip([e["payload"]["label"] for e in label_events], W - 2 * pad, 12)
    sheet.paste(strip, (pad, ys), strip)
    x, f13 = pad, sans(14)
    for lab in [k for k in COLOURS if any(e["payload"]["label"] == k for e in label_events)]:
        m = mark(lab, 12)
        sheet.paste(m, (round(x), ys + 30), m)
        d.text((x + 20, ys + 36), LABEL_WORD[lab], font=f13, fill=INK_2, anchor="lm")
        x += 20 + round(d.textlength(LABEL_WORD[lab], font=f13)) + 24
    d.line([pad, head - 25, W - pad, head - 25], fill=HAIRLINE, width=1)

    # Frames: radius-sm 10, hairline-strong keyline, caption = status mark + time + word.
    mask, key = _rounded(tw, th, 10), _keyline(tw, th, 10)
    ft, fl, fs = sans(15, 600), sans(15), sans(14)
    for i, e in enumerate(picks):
        r, c = divmod(i, cols)
        x, y = pad + c * (tw + gap), head + r * pitch
        try:
            im = Image.open(e["payload"]["frame"]).convert("RGB")
            im = im.resize((tw, max(th, int(tw * im.height / im.width))))
            top = (im.height - th) // 2
            im = im.crop((0, top, tw, top + th))
        except OSError:
            im = Image.new("RGB", (tw, th), SURFACE_2)
            ImageDraw.Draw(im).text((tw / 2, th / 2), "No frame", font=fs, fill=INK_3, anchor="mm")
        sheet.paste(im, (x, y), mask)
        sheet.paste(key, (x, y), key)
        lab = e["payload"]["label"]
        m = mark(lab, 12)
        cy = y + th + 22
        sheet.paste(m, (x, cy - 6), m)
        t = _hhmm(e["ts"])
        d.text((x + 20, cy), t, font=ft, fill=INK, anchor="lm")
        tx = x + 20 + d.textlength(t, font=ft) + 8
        d.text((tx, cy), LABEL_WORD.get(lab, lab.replace("_", " ")), font=fl, fill=INK_2, anchor="lm")
        if e["payload"].get("corrected_from"):
            tx += d.textlength(LABEL_WORD.get(lab, lab), font=fl) + 8
            was = LABEL_WORD.get(e["payload"]["corrected_from"], e["payload"]["corrected_from"].replace("_", " "))
            d.text((tx, cy), f"· was {was}", font=fs, fill=INK_3, anchor="lm")

    config.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out = config.EVIDENCE_DIR / f"{session['id']}.jpg"
    sheet.save(out, quality=88)
    return str(out)


def _witness(events) -> str:
    seen = Counter(e["payload"].get("backend") for e in events if e["payload"].get("backend") != "motion-gate")
    return seen.most_common(1)[0][0] if seen else "?"


def title_summary(window_events: list[dict], labels: dict[str, str], top: int = 5) -> list[dict]:
    """Top N (app — title) by time with their label. Each window event stands for one logger interval."""
    counts = Counter(_title_key(e["payload"]) for e in window_events)
    total = sum(counts.values()) or 1
    return [{"title": t, "share": n / total, "label": labels.get(t, "off_task")} for t, n in counts.most_common(top)]


def _title_key(p: dict) -> str:
    title = (p.get("title") or "").strip()
    return f"{p.get('app', '?')} — {title}" if title else p.get("app", "?")
