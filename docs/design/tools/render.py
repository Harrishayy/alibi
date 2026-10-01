#!/usr/bin/env python3
"""Render a local HTML/SVG file (or a URL) to PNG with headless Chromium (Playwright).
Usage: render.py INPUT OUT.png [--w 800] [--h 600] [--scale 2] [--wait 300] [--dark|--light] [--full] [--reduced-motion]
       [--eval "js expression run after load (e.g. to seek an animation)"]
"""
import argparse, pathlib, sys
from playwright.sync_api import sync_playwright
ap = argparse.ArgumentParser()
ap.add_argument("input"); ap.add_argument("out")
ap.add_argument("--w", type=int, default=800); ap.add_argument("--h", type=int, default=600)
ap.add_argument("--scale", type=float, default=2); ap.add_argument("--wait", type=int, default=300)
ap.add_argument("--dark", action="store_true"); ap.add_argument("--light", action="store_true")
ap.add_argument("--full", action="store_true"); ap.add_argument("--reduced-motion", action="store_true")
ap.add_argument("--eval", default=None)
a = ap.parse_args()
src = a.input if a.input.startswith(("http://", "https://", "file://")) else pathlib.Path(a.input).resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": a.w, "height": a.h}, device_scale_factor=a.scale,
                        color_scheme="dark" if a.dark else ("light" if a.light else "no-preference"),
                        reduced_motion="reduce" if a.reduced_motion else "no-preference")
    pg = ctx.new_page()
    errs = []
    pg.on("console", lambda m: errs.append(f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
    pg.goto(src); pg.wait_for_timeout(a.wait)
    if a.eval:
        r = pg.evaluate(a.eval); pg.wait_for_timeout(60)
        if r is not None: print("eval ->", r)
    pg.screenshot(path=a.out, full_page=a.full)
    b.close()
for e in errs: print(e, file=sys.stderr)
print("wrote", a.out)
