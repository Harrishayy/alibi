#!/usr/bin/env python3
"""Compare two PNGs pixel by pixel (for "no visual change" checks).

Usage: imgdiff.py BEFORE.png AFTER.png [--max-ratio 0.002] [--out DIFF.png]
Prints `identical`, or `diff ratio=R bbox=(x0, y0, x1, y1)` where R is the share of pixels that differ by more
than a small tolerance. Exit code 0 when R <= --max-ratio, 1 otherwise. --out writes a red-on-grey diff mask.
"""
import argparse
import sys

from PIL import Image, ImageChops

ap = argparse.ArgumentParser()
ap.add_argument("before")
ap.add_argument("after")
ap.add_argument("--max-ratio", type=float, default=0.002)
ap.add_argument("--tolerance", type=int, default=8, help="per-channel difference treated as equal (anti-aliasing)")
ap.add_argument("--out", default=None)
a = ap.parse_args()

x = Image.open(a.before).convert("RGB")
y = Image.open(a.after).convert("RGB")
if x.size != y.size:
    print(f"size differs: {x.size} vs {y.size}")
    sys.exit(1)
d = ImageChops.difference(x, y).convert("L").point(lambda v: 255 if v > a.tolerance else 0)
bbox = d.getbbox()
if bbox is None:
    print("identical")
    sys.exit(0)
changed = sum(1 for v in d.getdata() if v)
ratio = changed / (x.size[0] * x.size[1])
print(f"diff ratio={ratio:.5f} bbox={bbox}")
if a.out:
    base = Image.blend(x.convert("L").convert("RGB"), Image.new("RGB", x.size, (40, 40, 40)), 0.6)
    base.paste((229, 72, 77), mask=d)
    base.save(a.out)
    print("wrote", a.out)
sys.exit(0 if ratio <= a.max_ratio else 1)
