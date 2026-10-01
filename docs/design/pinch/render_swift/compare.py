#!/usr/bin/env python3
"""Render the same Pinch frames with the web rig (pinch.svg + rig.js in Chromium) and the SwiftUI port
(main.swift + ImageRenderer), then build swift-renders/compare.png: web | swift | diff, one row per case.

    python3 docs/design/pinch/render_swift/compare.py           # needs playwright + Pillow and swiftc

Prints the mean and 99th-percentile channel difference per case. Anti-aliasing differs between Skia and Core Graphics,
so expect a small mean (< 2) with edge-only diffs; a moved or missing part shows up as a large mean and a solid blob.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
PINCH = HERE.parent
OUT = PINCH / "swift-renders"
WEB = OUT / "web"

CASES = []
for theme in ("dark", "light"):
    CASES += [
        dict(id=f"idle-160-{theme}", mood="idle", clip=None, ms=0, size=160, theme=theme),
        dict(id=f"celebrate380-160-{theme}", mood="idle", clip="celebrate", ms=380, size=160, theme=theme),
        dict(id=f"sideeye600-160-{theme}", mood="idle", clip="sideeye", ms=600, size=160, theme=theme),
        dict(id=f"supportive700-160-{theme}", mood="idle", clip="supportive", ms=700, size=160, theme=theme),
        dict(id=f"celebrate60-160-{theme}", mood="idle", clip="celebrate", ms=60, size=160, theme=theme),
        dict(id=f"hello420-160-{theme}", mood="idle", clip="hello", ms=420, size=160, theme=theme),
        dict(id=f"connected420-160-{theme}", mood="idle", clip="connected", ms=420, size=160, theme=theme),
        dict(id=f"surprise260-160-{theme}", mood="idle", clip="surprise", ms=260, size=160, theme=theme),
        dict(id=f"partial380-160-{theme}", mood="idle", clip="partial", ms=380, size=160, theme=theme),
        dict(id=f"focused-160-{theme}", mood="focused", clip=None, ms=0, size=160, theme=theme),
        dict(id=f"listening-160-{theme}", mood="listening", clip=None, ms=0, size=160, theme=theme),
        dict(id=f"thinking-160-{theme}", mood="thinking", clip=None, ms=150, size=160, theme=theme),
        dict(id=f"sleepy-96-{theme}", mood="sleepy", clip=None, ms=1250, size=96, theme=theme),
        dict(id=f"reading-96-{theme}", mood="reading", clip=None, ms=300, size=96, theme=theme),
        dict(id=f"nudge330-56-{theme}", mood="idle", clip="nudge", ms=330, size=56, theme=theme),
        dict(id=f"idle-28-{theme}", mood="idle", clip=None, ms=0, size=28, theme=theme),
        dict(id=f"idle-20-{theme}", mood="idle", clip=None, ms=0, size=20, theme=theme),
        dict(id=f"idle-16-{theme}", mood="idle", clip=None, ms=0, size=16, theme=theme),
        dict(id=f"focused-16-{theme}", mood="focused", clip=None, ms=0, size=16, theme=theme),
    ]


def web_html():
    js = lambda p: (PINCH / p).read_text()
    data = {
        "SVG": js("pinch.svg"), "LOD24": js("pinch-lod24.svg"), "LOD20": js("pinch-lod20.svg"), "LOD16": js("pinch-lod16.svg"),
        "RIG": json.loads(js("rig.json")), "CLIPS": json.loads(js("clips.json")), "CASES": CASES,
    }
    tokens = (PINCH.parent / "tokens" / "tokens.css").as_uri()
    return f"""<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{tokens}">
<style>*{{margin:0}} body{{background:#808080;display:flex;flex-wrap:wrap;gap:8px;padding:8px}}
.cell{{position:relative;overflow:hidden}} .cell[data-theme=dark]{{background:#000}} .cell[data-theme=light]{{background:#fff}}
.stage{{position:absolute;container-type:inline-size;container-name:pinch}} .stage svg{{display:block;width:100%;height:100%;overflow:visible}}</style>
</head><body><script>{js("rig.js")}</script><script>
var D = {json.dumps(data)}, R = window.AlibiPinchRig, uid = 0;
R.setEasings(D.CLIPS.easings);
D.CASES.forEach(function (c) {{
  var box = c.size + 2 * Math.round(c.size * 0.15), cell = document.createElement('div');
  cell.className = 'cell'; cell.id = c.id; cell.setAttribute('data-theme', c.theme);
  cell.style.width = cell.style.height = box + 'px';
  var st = document.createElement('div'); st.className = 'stage';
  st.style.width = st.style.height = c.size + 'px'; st.style.left = st.style.top = ((box - c.size) / 2) + 'px';
  var glyph = c.size < 24, markup = glyph ? (c.size < 20 ? D.LOD16 : D.LOD20) : (c.size < 40 ? D.LOD24 : D.SVG);
  st.innerHTML = glyph ? markup : R.prefixIds(markup, 'p' + (uid++) + '-');  // the glyph's .lit rule targets #lens-glow
  cell.appendChild(st); document.body.appendChild(cell);
  var svg = st.querySelector('svg'), p = R.pose(D.RIG, D.CLIPS, c.clip || c.mood, c.ms);
  if (glyph) {{ if (p.lensGlow >= 0.5) svg.classList.add('lit'); return; }}
  if (c.size < 40) svg.setAttribute('data-lod', '28'); else if (c.size < 96) svg.setAttribute('data-lod', '56');
  R.apply(svg, p, D.RIG, c.ms);
}});
</script></body></html>"""


def render_web():
    from playwright.sync_api import sync_playwright
    WEB.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        page_path = pathlib.Path(td) / "web-ref.html"
        page_path.write_text(web_html())
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(page_path.as_uri())
            pg.wait_for_timeout(300)
            for c in CASES:
                pg.locator("#" + c["id"]).screenshot(path=str(WEB / (c["id"] + ".png")))
            b.close()
            for e in errs:
                print("web error:", e, file=sys.stderr)


def render_swift():
    (HERE / "cases.json").write_text(json.dumps(CASES, indent=1) + "\n")
    with tempfile.TemporaryDirectory() as td:
        exe = pathlib.Path(td) / "pinch-render"
        subprocess.run(["swiftc", "-O", "main.swift", "../Pinch.swift", "../PinchData.swift", "-o", str(exe)],
                       cwd=HERE, check=True)
        subprocess.run([str(exe)], cwd=HERE, check=True, stdout=subprocess.DEVNULL)


def compare():
    from PIL import Image, ImageChops, ImageDraw
    rows, report = [], []
    for c in CASES:
        a = Image.open(WEB / (c["id"] + ".png")).convert("RGB")
        b = Image.open(OUT / (c["id"] + ".png")).convert("RGB")
        if a.size != b.size:
            b = b.resize(a.size)
        d = ImageChops.difference(a, b)
        px = sorted(sum(v) / 3 for v in d.get_flattened_data())
        mean, p99 = sum(px) / len(px), px[int(len(px) * 0.99)]
        report.append((c["id"], mean, p99))
        amp = d.point(lambda v: min(255, v * 4))
        scale = max(1, 300 // a.size[0])
        tiles = [im.resize((a.size[0] * scale, a.size[1] * scale), Image.NEAREST) for im in (a, b, amp)]
        rows.append((c["id"], mean, tiles))
    w = max(sum(t.size[0] for t in r[2]) + 40 for r in rows) + 220
    h = sum(r[2][0].size[1] + 16 for r in rows) + 16
    sheet = Image.new("RGB", (w, h), (40, 40, 40))
    dr = ImageDraw.Draw(sheet)
    y = 16
    for cid, mean, tiles in rows:
        dr.text((16, y + 4), cid, fill=(230, 230, 230))
        dr.text((16, y + 20), "web | swift | diff x4", fill=(150, 150, 150))
        dr.text((16, y + 36), "mean %.2f" % mean, fill=(150, 150, 150))
        x = 220
        for t in tiles:
            sheet.paste(t, (x, y))
            x += t.size[0] + 20
        y += tiles[0].size[1] + 16
    sheet.save(OUT / "compare.png")
    for cid, mean, p99 in report:
        print("%-28s mean %5.2f  p99 %6.1f" % (cid, mean, p99))
    print("wrote", (OUT / "compare.png").relative_to(PINCH.parent.parent.parent))


if __name__ == "__main__":
    render_web()
    render_swift()
    compare()
