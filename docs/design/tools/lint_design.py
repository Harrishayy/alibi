#!/usr/bin/env python3
"""Design-rule lint for the Alibi redesign (all-sans, dark-first, token-only colour, token-only motion).

Usage (from the repo root):
  python3 docs/design/tools/lint_design.py                 # web + swift
  python3 docs/design/tools/lint_design.py --web           # alibi/web only
  python3 docs/design/tools/lint_design.py --swift         # island + iPhone + Live Activity views
  python3 docs/design/tools/lint_design.py --paths FILE..  # just these files
  python3 docs/design/tools/lint_design.py --summary       # counts per rule instead of every line

Last line is `lint_design OK (0 findings, N files)` or `lint_design: K findings in M files`; exit 1 on findings.
Silence a deliberate exception by ending the line with `lint-ok` in a comment, and say why next to it.
Token sources are exempt by design: alibi/web/css/tokens.css, alibi/web/js/pinch.js, native/Theme.swift,
native/Pinch.swift, native/PinchData.swift (the mascot palette and the token values live there).
"""
import argparse
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
# Token definitions and the generated Pinch rig (canonical in native/shared/, copied into the iPhone app).
EXEMPT = {"alibi/web/css/tokens.css", "alibi/web/js/pinch.js"} | {
    f"{d}/{n}.swift" for d in ("native/shared", "ios/AlibiPhone/Views/Shared") for n in ("Theme", "Pinch", "PinchData")}

# (rule, regex, applies-to) — applies-to is a set of suffixes.
WEB = {".css", ".html", ".js"}
SWIFT = {".swift"}
ANY = WEB | SWIFT
RULES = [
    # Type: one sans superfamily; no serif, no italic, no uppercase eyebrows.
    ("serif-font", re.compile(r"Newsreader|Source Serif|Figtree|JetBrains|Iowan|Georgia|\"New York\"|NewYork"), ANY),
    ("inter-font", re.compile(r"[\"'=+]Inter\b|family=Inter"), WEB),
    ("serif-generic", re.compile(r"(?<!sans-)\bserif\b(?!-)"), WEB),
    ("italic", re.compile(r"font-style\s*:\s*italic|\.italic\(\)"), ANY),
    ("uppercase", re.compile(r"text-transform\s*:\s*uppercase|\.uppercased\(\)|\.textCase\(\.uppercase\)"), ANY),
    ("swift-serif", re.compile(r"design:\s*\.serif|\.serif\b"), SWIFT),
    # Colour: retired leftovers anywhere; raw colours only in token sources.
    ("retired-colour", re.compile(r"(?i)C8362B|A39E95|7FA7D9"), ANY),
    ("raw-hex-css", re.compile(r":[^;{}]*?(?<![&\w])#[0-9a-fA-F]{3,8}\b"), {".css", ".html"}),
    ("raw-hex-js", re.compile(r"[\"'`]#[0-9a-fA-F]{3,8}[\"'`]"), {".js", ".html"}),
    ("raw-colour-swift", re.compile(r"Color\((hex:|red:|\.sRGB)|#colorLiteral"), SWIFT),
    ("gradient", re.compile(r"(linear|radial|conic)-gradient|LinearGradient|RadialGradient|AngularGradient"), ANY),
    ("glass", re.compile(r"\.glassEffect|backdrop-filter"), ANY),
    # Motion: tokens only, transform/opacity only, never ease-in on UI.
    ("ease-in", re.compile(r"\bease-in\b(?!-out)|\.easeIn\("), ANY),
    ("transition-all", re.compile(r"transition\s*:\s*all\b"), WEB),
    ("layout-anim", re.compile(r"transition(-property)?\s*:[^;]*\b(width|height|top|left|right|bottom|margin|padding)\b"),
     WEB),
    ("adhoc-spring", re.compile(r"\.spring\(response:|\.interpolatingSpring|\.spring\(duration:"), SWIFT),
    ("adhoc-bezier", re.compile(r"cubic-bezier\("), WEB),
    # Floors and icon language.
    ("font-floor", re.compile(r"\.font\(\.system\(size:\s*(?:[0-9]|10)(?:\.\d+)?\b"), SWIFT),
    ("emoji", re.compile("[\U0001F300-\U0001FAFF❤⬛⭐⏰⌚]"), ANY),
]


def targets(web: bool, swift: bool) -> list[pathlib.Path]:
    out = []
    if web:
        w = ROOT / "alibi" / "web"
        out += [p for p in [w / "index.html", w / "signals.html"] if p.exists()]
        out += sorted((w / "css").glob("*.css")) + sorted((w / "js").glob("*.js"))
    if swift:
        out += [p for p in [ROOT / "native" / "Island.swift", ROOT / "native" / "main.swift"] if p.exists()]
        out += sorted((ROOT / "ios" / "AlibiPhone" / "Views").rglob("*.swift"))
        out += sorted((ROOT / "ios" / "AlibiLive").rglob("*.swift")) if (ROOT / "ios" / "AlibiLive").exists() else []
    return out


def lint(path: pathlib.Path) -> list[tuple[int, str, str]]:
    rel = path.resolve().relative_to(ROOT).as_posix() if path.resolve().is_relative_to(ROOT) else str(path)
    if rel in EXEMPT:
        return []
    found = []
    for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        if "lint-ok" in line:
            continue
        for rule, rx, kinds in RULES:
            if path.suffix in kinds and rx.search(line):
                if rule == "gradient" and "bloom" in line:
                    continue                     # the one celebration bloom is allowed
                if rule == "uppercase" and "ALIBI" in line:
                    continue                     # the island wordmark is set in caps on purpose
                found.append((n, rule, line.strip()[:110]))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", action="store_true")
    ap.add_argument("--swift", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--paths", nargs="*")
    a = ap.parse_args()
    files = [pathlib.Path(p) for p in a.paths] if a.paths else targets(a.web or not a.swift, a.swift or not a.web)
    total, bad, per_rule = 0, 0, collections.Counter()
    for f in files:
        hits = lint(f)
        if hits:
            bad += 1
            total += len(hits)
            for n, rule, text in hits:
                per_rule[rule] += 1
                if not a.summary:
                    print(f"{f.resolve().relative_to(ROOT) if f.resolve().is_relative_to(ROOT) else f}:{n}: {rule}: {text}")
    if a.summary:
        for rule, c in per_rule.most_common():
            print(f"{c:5d}  {rule}")
    if total:
        print(f"lint_design: {total} findings in {bad} files")
        return 1
    print(f"lint_design OK (0 findings, {len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
