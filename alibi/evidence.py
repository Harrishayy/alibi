"""P1 — contact sheet of keyframes; P3 — title breakdown for digital sessions."""
import datetime as dt
from collections import Counter
from PIL import Image, ImageDraw, ImageFont
from . import config

CREAM, INK, MUTED, RULE = "#F4EFE6", "#1F1E1C", "#7A756C", "#DDD5C7"
COLOURS = {"on_task": "#5E8C61", "phone": "#D2553F", "off_task": "#B5452F", "idle": "#D99A3D", "absent": "#A39E95"}
VERDICT_COLOUR = {"done": COLOURS["on_task"], "partial": COLOURS["idle"], "slacked": COLOURS["phone"]}


def _font(name: str, size: int):
    for p in (f"/System/Library/Fonts/{name}", f"/System/Library/Fonts/Supplemental/{name}"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _hhmm(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%H:%M")


def contact_sheet(session, label_events: list[dict], ratio: float, verdict: str) -> str | None:
    frames = [e for e in label_events if e["payload"].get("frame")]
    if not frames:
        return None
    k = min(12, len(frames))
    picks = [frames[round(i * (len(frames) - 1) / max(1, k - 1))] for i in range(k)] if k > 1 else frames[:1]
    cols, tw, th, pad, gap = 4, 300, 225, 36, 14
    rows = (len(picks) + cols - 1) // cols
    head, strip = 150, 46
    W = pad * 2 + cols * tw + (cols - 1) * gap
    H = head + strip + rows * (th + 34 + gap) + pad
    sheet = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(sheet)
    serif, serif_s, mono = _font("NewYork.ttf", 44), _font("NewYork.ttf", 22), _font("Menlo.ttc", 15)

    d.text((pad, pad - 4), "Alibi", font=serif_s, fill=MUTED)
    d.text((pad, pad + 26), f"{session['habit'].capitalize()}, {session['declared_min']} min", font=serif, fill=INK)
    vc = VERDICT_COLOUR.get(verdict, INK)
    vtxt = f"{verdict.upper()}  ·  {ratio:.0%} on task"
    vw = d.textlength(vtxt, font=mono)
    d.rounded_rectangle([W - pad - vw - 32, pad + 34, W - pad, pad + 70], radius=18, fill=vc)
    d.text((W - pad - vw - 16, pad + 43), vtxt, font=mono, fill="white")
    d.text((pad, pad + 84), f"{_hhmm(session['started_at'])} → {_hhmm(label_events[-1]['ts'])}  ·  "
                            f"{len(label_events)} samples  ·  witness: {_witness(label_events)}",
           font=mono, fill=MUTED)

    # timeline: every sample, in order, as a coloured segment
    y0, seg = head, (W - 2 * pad) / len(label_events)
    for i, e in enumerate(label_events):
        d.rectangle([pad + i * seg, y0, pad + (i + 1) * seg - 1, y0 + 14], fill=COLOURS[e["payload"]["label"]])
    d.line([pad, y0 + 30, W - pad, y0 + 30], fill=RULE, width=1)

    for i, e in enumerate(picks):
        r, c = divmod(i, cols)
        x, y = pad + c * (tw + gap), head + strip + r * (th + 34 + gap)
        col = COLOURS[e["payload"]["label"]]
        try:
            im = Image.open(e["payload"]["frame"]).convert("RGB")
            im = im.resize((tw, int(tw * im.height / im.width)))
            im = im.crop((0, 0, tw, th)) if im.height >= th else im
        except OSError:
            im = Image.new("RGB", (tw, th), RULE)
        d.rounded_rectangle([x - 4, y - 4, x + tw + 3, y + th + 3], radius=8, fill=col)
        sheet.paste(im, (x, y))
        tag = f"{_hhmm(e['ts'])}  {e['payload']['label'].replace('_', ' ')}"
        if e["payload"].get("corrected_from"):
            tag += f"  ✎ was {e['payload']['corrected_from'].replace('_', ' ')}"
        d.text((x, y + th + 9), tag, font=mono, fill=INK)

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
