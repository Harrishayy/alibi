#!/usr/bin/env python3
"""Format and design lint for the iPhone artboards of the "Alibi Screens" canvas.

Usage (from anywhere):
  python3 docs/design/canvas/tools/lint_iphone.py              # the seven iPhone boards
  python3 docs/design/canvas/tools/lint_iphone.py FILE.dc.html # just these files

Format checks (the .dc.html contract): the exact head lines with support.js first; one <x-dc> holding one <helmet>;
one data-dc-script block with `class Component extends DCLogic`; data-props valid JSON after entity decoding; holes
are dotted lookups only and resolve to renderVals() keys or loop variables; hint-* attributes on <sc-if>/<sc-for>;
every non-void element closed; attributes double-quoted (data-props single-quoted); no innerHTML / appendChild /
own window.X; no emoji; no iframe/object/embed; aria-labels on icon-only controls; the root sized exactly as
$preview; x-import names and props from the component contract.

Design checks (iPhone): 390x844 phone roots with data-theme and the base tokens; tokens only (no raw hex/rgb);
sans only, no italics or uppercase; type at or above the 11pt floor; Pinch sizes on the ladder and one Pinch per
screen; 44pt targets; prototype links that resolve.

Last line is `lint_iphone OK (N files)` or `lint_iphone: K findings in M files`; exit 1 on findings.
"""
import html
import html.parser
import json
import pathlib
import re
import sys

PROJECT = pathlib.Path(__file__).resolve().parents[1] / "project"
FILES = ["Phone-Today-Live.dc.html", "Phone-Today-Idle.dc.html", "Phone-Verdict.dc.html", "Phone-Week.dc.html",
         "Phone-Health.dc.html", "Phone-LockScreen.dc.html", "Phone-DynamicIsland.dc.html"]
# Boards that are a specimen sheet rather than one phone screen (sized freely, may show Pinch per presentation).
SPEC_SHEETS = {"Phone-DynamicIsland.dc.html"}

HEAD = [
    '<meta charset="utf-8">',
    None,  # <title>…</title>
    '<script src="./support.js"></script>',
    '<link rel="stylesheet" href="ds/alibi/components/bundle.css">',
    '<script src="ds/alibi/components/bundle.js"></script>',
]

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

ICONS = ["play", "pause", "stop", "plus", "check", "x", "camera", "laptop", "phone", "run", "heart", "moon",
         "calendar", "settings", "lens", "cup", "arrow-up", "arrow-right", "chevron-right", "chevron-down", "clock",
         "flag", "eye", "sparkle", "claw", "undo", "film"]
LABELS = ["on_task", "idle", "phone", "off_task", "absent"]
MOODS = ["idle", "focused", "listening", "thinking", "sleepy", "reading"]
CLIPS = ["hello", "sideeye", "nudge", "celebrate", "partial", "supportive", "surprise", "connected"]
PINCH_LADDER = {16, 20, 28, 32, 44, 56, 64, 96, 160}

# Component contract: prop -> allowed literal values (None = any). Common DOM props are allowed on every component.
COMMON = {"style": None, "className": None, "class": None, "id": None, "title": None, "children": None}
CONTRACT = {
    "Button": {"variant": ["primary", "secondary", "ghost", "quiet"], "size": ["sm", "md", "lg"], "icon": ICONS,
               "iconOnly": None, "ariaLabel": None, "onClick": None, "disabled": None, "type": None},
    "IconButton": {"icon": ICONS, "ariaLabel": None, "size": ["sm", "md", "lg"], "onClick": None, "disabled": None},
    "Icon": {"name": ICONS, "size": None},
    "Chip": {"selected": None, "icon": ICONS, "kbd": None, "onClick": None},
    "Kbd": {},
    "Composer": {"placeholder": None, "value": None, "chips": None, "focused": None, "onSubmit": None,
                 "onChange": None},
    "Card": {"tone": ["default", "raised", "accent", "warn"], "padding": ["sm", "md", "lg"], "as": None},
    "StatusDot": {"label": LABELS, "size": None, "text": None},
    "SampleStrip": {"labels": None, "size": None, "develop": None, "frames": None},
    "VerdictPill": {"verdict": ["done", "partial", "slacked"], "ratio": None},
    "Meter": {"value": None, "partAt": None, "doneAt": None, "label": None},
    "RingTimer": {"progress": None, "value": None, "caption": None, "size": None,
                  "tone": ["accent", "partial", "warn"]},
    "Stat": {"value": None, "label": None, "sub": None},
    "StreakBadge": {"days": None, "freezes": None},
    "PinchLine": {"mood": MOODS, "compact": None, "theme": ["dark", "light"]},
    "Pinch": {"mood": MOODS, "size": None, "play": CLIPS, "playKey": None, "theme": ["dark", "light"],
              "still": None, "force": None},
    "NotchIsland": {"state": ["idle", "live", "peek", "expanded", "nudge", "verdict", "break"], "width": None,
                    "leading": None, "trailing": None, "shake": None, "label": None},
    "Toast": {"kind": ["nudge", "verdict", "info"], "title": None, "actions": None, "onClose": None, "icon": ICONS,
              "mood": MOODS},
}

HOLE = re.compile(r"\{\{(.*?)\}\}", re.S)
DOTTED = re.compile(r"^\$?[A-Za-z_][\w$]*(\.[\w$]+)*$")
LITERAL = re.compile(r"^(true|false|null|-?\d+(\.\d+)?|'[^']*'|\"[^\"]*\")$")
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍⃣]")


def camel(name: str) -> str:
    if name.startswith("sc-camel-"):
        name = name[len("sc-camel-"):]
    return re.sub(r"-([a-z])", lambda m: m.group(1).upper(), name)


class Tree(html.parser.HTMLParser):
    """Collects tags with attributes, text content per element and unclosed / mismatched elements."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.elements = [], [], []

    def handle_starttag(self, tag, attrs):
        el = {"tag": tag, "attrs": dict(attrs), "line": self.getpos()[0], "text": "", "kids": [],
              "parent": self.stack[-1] if self.stack else None}
        if self.stack:
            self.stack[-1]["kids"].append(el)
        self.elements.append(el)
        if tag not in VOID:
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        if tag not in VOID and tag not in {"path", "circle", "rect", "line", "polyline", "polygon", "ellipse"}:
            self.errors.append((self.getpos()[0], f"self-closed <{tag}/>: close it with </{tag}>"))
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1]["tag"] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append((self.getpos()[0], f"stray </{tag}>"))
            return
        if self.stack[-1]["tag"] == tag:
            self.stack.pop()
            return
        names = [e["tag"] for e in self.stack]
        if tag in names:
            while self.stack and self.stack[-1]["tag"] != tag:
                e = self.stack.pop()
                self.errors.append((e["line"], f"<{e['tag']}> is never closed (closed by </{tag}>)"))
            self.stack.pop()
        else:
            self.errors.append((self.getpos()[0], f"stray </{tag}>"))

    def handle_data(self, data):
        for e in self.stack:
            e["text"] += data


def px(style: str, prop: str):
    m = re.search(r"(?:^|;)\s*" + re.escape(prop) + r"\s*:\s*(-?[\d.]+)px", style or "")
    return float(m.group(1)) if m else None


def lint(path: pathlib.Path) -> list[tuple[int, str]]:
    src = path.read_text()
    out: list[tuple[int, str]] = []
    name = path.name
    spec_sheet = name in SPEC_SHEETS

    def line_of(idx: int) -> int:
        return src.count("\n", 0, idx) + 1

    # ---- head ---------------------------------------------------------------------------------------------
    if not src.startswith("<!doctype html>\n<html lang=\"en\">"):
        out.append((1, 'file must start with <!doctype html> and <html lang="en">'))
    hm = re.search(r"<head>\n(.*?)\n</head>", src, re.S)
    if not hm:
        out.append((1, "no <head> block"))
    else:
        lines = [l.strip() for l in hm.group(1).split("\n") if l.strip()]
        if len(lines) != len(HEAD):
            out.append((line_of(hm.start()), f"head must be exactly {len(HEAD)} lines, found {len(lines)}"))
        for i, want in enumerate(HEAD):
            got = lines[i] if i < len(lines) else ""
            if want is None:
                if not re.fullmatch(r"<title>[^<]{3,60}</title>", got):
                    out.append((line_of(hm.start()) + 1 + i, f"head line {i + 1} must be a short <title>, got {got!r}"))
            elif got != want:
                out.append((line_of(hm.start()) + 1 + i, f"head line {i + 1} must be {want!r}, got {got!r}"))

    # ---- x-dc, helmet ---------------------------------------------------------------------------------------
    if src.count("<x-dc>") != 1 or src.count("</x-dc>") != 1:
        out.append((1, "need exactly one <x-dc>…</x-dc>"))
    xm = re.search(r"<x-dc>(.*?)</x-dc>", src, re.S)
    body = xm.group(1) if xm else ""
    xoff = xm.start(1) if xm else 0
    if body.count("<helmet>") != 1 or body.count("</helmet>") != 1:
        out.append((line_of(xoff), "need exactly one <helmet> inside <x-dc>"))
    hel = re.search(r"<helmet>(.*?)</helmet>", body, re.S)
    if hel:
        inner = hel.group(1)
        css = "".join(re.findall(r"<style>(.*?)</style>", inner, re.S))
        rest_markup = re.sub(r"<style>.*?</style>", "", inner, flags=re.S)
        rest_markup = re.sub(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/css2[^"]*">', "", rest_markup)
        if rest_markup.strip():
            out.append((line_of(xoff + hel.start()), "helmet holds only <style> (and a Google Fonts css2 link)"))
        leftover = re.sub(r"@keyframes\s+[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
        leftover = re.sub(r"body\s*\{\s*margin\s*:\s*0;?\s*\}", "", leftover)
        leftover = re.sub(r"a(?::hover)?\s*\{\s*color\s*:\s*[^;{}]+;?\s*\}", "", leftover)
        if leftover.strip():
            out.append((line_of(xoff + hel.start()),
                        f"helmet <style> allows only body{{margin:0}}, a/a:hover colours and @keyframes; found {leftover.strip()[:60]!r}"))

    # ---- logic script ---------------------------------------------------------------------------------------
    scripts = re.findall(r"<script\b[^>]*data-dc-script[^>]*>", src)
    if len(scripts) != 1:
        out.append((1, f"need exactly one data-dc-script block, found {len(scripts)}"))
    sm = re.search(r"<script type=\"text/x-dc\" data-dc-script data-props='([^']*)'>(.*?)</script>", src, re.S)
    logic, props = "", {}
    if not sm:
        out.append((1, "data-dc-script must read <script type=\"text/x-dc\" data-dc-script data-props='…'>"))
    else:
        logic = sm.group(2)
        try:
            props = json.loads(html.unescape(sm.group(1)))
        except json.JSONDecodeError as e:
            out.append((line_of(sm.start()), f"data-props is not valid JSON after entity decoding: {e}"))
        if "class Component extends DCLogic" not in logic:
            out.append((line_of(sm.start()), "logic must be `class Component extends DCLogic`"))
        if "renderVals()" not in logic:
            out.append((line_of(sm.start()), "logic has no renderVals()"))
        if re.search(r"^\s*(import|export)\b", logic, re.M):
            out.append((line_of(sm.start()), "logic is classic JS: no import/export"))
        for k, v in props.items():
            if k != "$preview" and isinstance(v, dict) and v.get("editor") == "text":
                out.append((line_of(sm.start()), f"tweak {k!r} is copy, not a lever"))
    other_scripts = [s for s in re.findall(r"<script\b[^>]*>", src)
                     if "data-dc-script" not in s and s not in ('<script src="./support.js">',
                                                                 '<script src="ds/alibi/components/bundle.js">')]
    for s in other_scripts:
        out.append((1, f"extra script tag {s!r}"))

    # ---- forbidden APIs and tags ------------------------------------------------------------------------------
    for rx, why in [(r"\binnerHTML\b|\bouterHTML\b|insertAdjacentHTML", "innerHTML-style DOM writes"),
                    (r"\bappendChild\b|\binsertBefore\b|\bcreateElement\b|\breplaceChildren\b", "script-built DOM"),
                    (r"\bwindow\.[A-Za-z_$][\w$]*\s*=(?!=)", "own window.X global"),
                    (r"addEventListener\(\s*['\"]key", "global keydown handler"),
                    (r"<(iframe|object|embed)\b", "iframe/object/embed")]:
        for m in re.finditer(rx, src):
            out.append((line_of(m.start()), f"forbidden: {why}"))
    for m in EMOJI.finditer(src):
        out.append((line_of(m.start()), f"emoji or pictograph U+{ord(m.group()):04X}: use Alibi.Icon"))

    # ---- attribute quoting (raw scan of tags inside x-dc) -----------------------------------------------------
    for m in re.finditer(r"<([a-zA-Z][\w-]*)((?:\s+[^\s=>]+(?:=(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?)*)\s*/?>", src):
        for a in re.finditer(r"([^\s=>]+)(?:=(\"[^\"]*\"|'[^']*'|[^\s>]+))?", m.group(2)):
            val = a.group(2)
            if val is None:
                if a.group(1) not in ("data-dc-script",) and m.group(1) != "html":
                    out.append((line_of(m.start()), f"attribute {a.group(1)!r} on <{m.group(1)}> needs a quoted value"))
            elif val.startswith("'") and a.group(1) != "data-props":
                out.append((line_of(m.start()), f"attribute {a.group(1)!r} is single-quoted: use double quotes"))
            elif not val.startswith(("'", '"')):
                out.append((line_of(m.start()), f"attribute {a.group(1)!r} is unquoted"))

    # ---- holes ------------------------------------------------------------------------------------------------
    loop_vars = set(re.findall(r"<sc-for\b[^>]*\bas=\"([\w$]+)\"", body)) | {"$index"}
    for m in HOLE.finditer(body):
        expr = m.group(1).strip()
        ln = line_of(xoff + m.start())
        if LITERAL.match(expr):
            continue
        if not DOTTED.match(expr):
            out.append((ln, f"hole {{{{ {expr} }}}} is not a dotted lookup"))
            continue
        root = expr.split(".")[0]
        if root in loop_vars:
            continue
        if not re.search(r"(?<![\w$.])" + re.escape(root) + r"\s*(:|,|\n\s*\})", logic):
            out.append((ln, f"hole {{{{ {expr} }}}}: {root!r} is not returned by renderVals()"))

    # ---- structure ----------------------------------------------------------------------------------------------
    t = Tree()
    t.feed(src)
    t.close()
    for ln, msg in t.errors:
        out.append((ln, msg))
    for e in t.stack:
        if e["tag"] not in ("html", "body"):
            out.append((e["line"], f"<{e['tag']}> is never closed"))

    els = t.elements
    for e in els:
        a, tag, ln = e["attrs"], e["tag"], e["line"]
        style = a.get("style") or ""
        if tag == "sc-if":
            if "value" not in a or "hint-placeholder-val" not in a:
                out.append((ln, "<sc-if> needs value= and hint-placeholder-val="))
        if tag == "sc-for":
            for need in ("list", "as", "hint-placeholder-count"):
                if need not in a:
                    out.append((ln, f"<sc-for> needs {need}="))
        if tag == "dc-import":
            out.append((ln, "dc-import is not used on the iPhone boards"))
        # tokens only
        for m in re.finditer(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", style):
            out.append((ln, f"raw colour {m.group()!r} in style: use a var(--token)"))
        for attr in ("fill", "stroke", "color"):
            v = a.get(attr) or ""
            if re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", v):
                out.append((ln, f"raw colour in {attr}=: use a var(--token)"))
        if re.search(r"(linear|conic)-gradient", style) or ("radial-gradient" in style and "--bloom" not in style):
            out.append((ln, "gradient: only the celebration bloom is allowed"))
        fam = re.search(r"font-family\s*:\s*([^;]+)", style)
        if fam and not re.fullmatch(r"var\(--font-(sans|rounded|mono)\)", fam.group(1).strip()):
            out.append((ln, f"font-family must be var(--font-sans|rounded|mono), got {fam.group(1).strip()!r}"))
        fshort = re.search(r"(?:^|;)\s*font\s*:\s*([^;]+)", style)
        if fshort and not re.search(r"var\(--font-(sans|rounded|mono)\)", fshort.group(1)):
            out.append((ln, "font shorthand must use var(--font-*)"))
        if re.search(r"font-style\s*:\s*italic|text-transform\s*:\s*uppercase|\bserif\b", style.replace("sans-serif", "")):
            out.append((ln, "no italics, uppercase or serif"))
        fs = px(style, "font-size")
        if fs is None and fshort:
            mm = re.search(r"(\d+(?:\.\d+)?)px", fshort.group(1))
            fs = float(mm.group(1)) if mm else None
        if fs is not None and fs < 11:
            out.append((ln, f"font-size {fs:g}px is under the 11pt floor"))
        if re.search(r"transition\s*:[^;]*\b(width|height|top|left|margin|padding)\b", style):
            out.append((ln, "animate transform/opacity only"))
        if re.search(r"cubic-bezier\(|\bease-in\b(?!-out)", style):
            out.append((ln, "motion must use the easing/spring tokens"))

        # interactive targets and names
        if tag in ("button", "a"):
            text = re.sub(r"\s+", "", e["text"])
            if not text and not a.get("aria-label"):
                out.append((ln, f"icon-only <{tag}> needs aria-label"))
            if tag == "a" and "href" in a:
                href = a["href"]
                if href.endswith(".dc.html") and not (path.parent / href).exists():
                    out.append((ln, f"link to missing artboard {href!r}"))
            if not spec_sheet:
                h = px(style, "height")
                mh = px(style, "min-height")
                big = max(v for v in (h, mh, 0) if v is not None)
                if big and big < 44:
                    out.append((ln, f"<{tag}> target is {big:g}px tall: 44pt minimum"))
        if tag == "x-import":
            comp = (a.get("component-from-global-scope") or "")
            if not comp.startswith("Alibi."):
                out.append((ln, f"x-import must name Alibi.<Comp>, got {comp!r}"))
                continue
            cname = comp.split(".", 1)[1]
            if cname not in CONTRACT:
                out.append((ln, f"{comp} is not in the component contract"))
                continue
            allowed = dict(COMMON, **CONTRACT[cname])
            given = {}
            for k, v in a.items():
                if k in ("component-from-global-scope", "hint-size"):
                    continue
                if k.startswith(("aria-", "data-")) and not k.startswith("sc-camel-"):
                    if cname in ("IconButton", "Button") and k == "aria-label":
                        out.append((ln, f"{comp}: aria-label is dropped by the component; write sc-camel-aria-label"))
                    continue
                prop = camel(k)
                given[prop] = v
                if prop not in allowed:
                    out.append((ln, f"{comp}: unknown prop {prop!r}"))
                    continue
                choices = allowed[prop]
                if choices and v is not None and not HOLE.search(v) and v not in choices:
                    out.append((ln, f"{comp}: {prop}={v!r} is not one of {choices}"))
            if cname == "IconButton" and not given.get("ariaLabel"):
                out.append((ln, "Alibi.IconButton needs sc-camel-aria-label"))
            if cname == "Button" and given.get("iconOnly") and not given.get("ariaLabel"):
                out.append((ln, "icon-only Alibi.Button needs sc-camel-aria-label"))
            if not spec_sheet:
                if cname in ("Button", "IconButton") and given.get("size", "md") != "lg":
                    out.append((ln, f"{comp} size {given.get('size', 'md')!r} is under 44pt on iPhone: use size=\"lg\""))
                if cname == "Chip" and (px(a.get("style", ""), "min-height") or px(a.get("style", ""), "height") or 32) < 44:
                    out.append((ln, "Alibi.Chip is 32px: give it style=\"min-height: 44px\" on iPhone"))
            if cname in ("Pinch",):
                size = given.get("size")
                val = None
                if size is None:
                    val = 96
                else:
                    hm2 = HOLE.fullmatch(size.strip())
                    if hm2:
                        key = hm2.group(1).strip()
                        mm = re.search(r"(?<![\w$.])" + re.escape(key) + r"\s*:\s*(\d+)", logic)
                        val = int(mm.group(1)) if mm else None
                    elif size.isdigit():
                        val = int(size)
                ok = PINCH_LADDER | ({10} if spec_sheet else set())
                if val is not None and val not in ok:
                    out.append((ln, f"Pinch size {val} is off the ladder {sorted(PINCH_LADDER)}"))

    # one Pinch per screen
    if not spec_sheet:
        n = sum(1 for e in els if e["tag"] == "x-import" and e["attrs"].get("component-from-global-scope") in
                ("Alibi.Pinch", "Alibi.PinchLine"))
        if n > 1:
            out.append((1, f"{n} Pinches on one screen: one Pinch per view"))

    # ---- root ---------------------------------------------------------------------------------------------------
    xdc = next((e for e in els if e["tag"] == "x-dc"), None)
    root = next((k for k in (xdc["kids"] if xdc else []) if k["tag"] != "helmet"), None)
    roots = [k for k in (xdc["kids"] if xdc else []) if k["tag"] != "helmet"]
    if len(roots) != 1:
        out.append((1, f"x-dc needs exactly one root element after <helmet>, found {len(roots)}"))
    if root:
        st = root["attrs"].get("style") or ""
        w, h = px(st, "width"), px(st, "height")
        pv = props.get("$preview") or {}
        if not pv:
            out.append((root["line"], "data-props has no $preview"))
        elif (w, h) != (pv.get("width"), pv.get("height")):
            out.append((root["line"], f"root {w}x{h} differs from $preview {pv.get('width')}x{pv.get('height')}"))
        if not spec_sheet and (w, h) != (390, 844):
            out.append((root["line"], f"phone root must be 390x844, got {w}x{h}"))
        theme = root["attrs"].get("data-theme")
        if theme is None or not (theme in ("dark", "light") or HOLE.fullmatch(theme.strip())):
            out.append((root["line"], "root needs data-theme=\"dark\" (or \"light\", or the theme tweak)"))
        for need in ("background: var(--bg)", "color: var(--ink)", "font-family: var(--font-sans)"):
            if need not in st:
                out.append((root["line"], f"root style needs {need!r}"))
    return out


def main() -> int:
    files = [pathlib.Path(p) for p in sys.argv[1:]] or [PROJECT / f for f in FILES]
    total, bad = 0, 0
    for f in files:
        if not f.exists():
            print(f"{f}: missing")
            total += 1
            bad += 1
            continue
        found = sorted(set(lint(f)))
        if found:
            bad += 1
            total += len(found)
            for ln, msg in found:
                print(f"{f.name}:{ln}: {msg}")
    if total:
        print(f"lint_iphone: {total} findings in {bad} files")
        return 1
    print(f"lint_iphone OK ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
