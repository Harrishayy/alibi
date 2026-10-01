#!/usr/bin/env python3
"""Format and design lint for the entry, Pinch and storyboard artboards of the "Alibi Screens" canvas.

    python3 docs/design/canvas/tools/lint_story.py                 # Main, Pinch-Moods, Pinch-Sizes, Story
    python3 docs/design/canvas/tools/lint_story.py FILE [FILE...]  # any .dc.html
    python3 docs/design/canvas/tools/lint_story.py --all           # every board in project/

Exit status 1 when any issue is found. Two classes of check:

  format  the .dc.html contract: the exact five head lines (support.js first after charset and title), one
          <x-dc> opening with <helmet>, one data-dc-script holding class Component extends DCLogic, data-props
          that is JSON after entity decoding, holes that are dotted lookups, hint-* attrs on sc-if / sc-for,
          balanced and closed elements, double-quoted attributes, no script-built UI (innerHTML, appendChild,
          window.X), no emoji, no iframe / object / embed, accessible names (icon-only controls, role="img",
          aria-labelledby targets), a fixed root equal to $preview, x-import names, props and enum values from
          the Alibi COMPONENT CONTRACT, and prototype links that land on a board that exists
  design  what a parser can see of docs/design/system/project/README.md: every font-size / line-height /
          weight / tracking combination is one of the frozen styles in tokens.json (web, island, Live
          Activity), digits sit under tabular-nums, colours come from tokens, no gradients or blur washes,
          no uppercase eyebrows, no left-border cards, onClick only on real controls, Pinch only on the
          size ladder, and the root carries data-theme plus the bg / ink / sans tokens
"""
import html
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parent / "project"
TOKENS = HERE.parent.parent / "system" / "project" / "tokens.json"
BOARDS = ["Main", "Pinch-Moods", "Pinch-Sizes", "Story"]

# Boards the prototype links may land on (the canvas index plus the entry itself).
LINK_TARGETS = {"Main.dc.html", "Dashboard.dc.html", "Island-Proto.dc.html", "Phone-Today-Live.dc.html",
                "Pinch-Moods.dc.html", "Pinch-Sizes.dc.html", "Story.dc.html"}

HEAD = [
    (re.compile(r'^<meta charset="utf-8">$'), '<meta charset="utf-8">'),
    (re.compile(r'^<title>[^<]{2,80}</title>$'), "<title>…</title>"),
    (re.compile(r'^<script src="\./support\.js"></script>$'), '<script src="./support.js"></script>'),
    (re.compile(r'^<link rel="stylesheet" href="ds/alibi/components/bundle\.css">$'),
     '<link rel="stylesheet" href="ds/alibi/components/bundle.css">'),
    (re.compile(r'^<script src="ds/alibi/components/bundle\.js"></script>$'),
     '<script src="ds/alibi/components/bundle.js"></script>'),
]

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
BLOCK = {"div", "p", "ul", "ol", "li", "section", "article", "header", "footer", "main", "aside", "nav",
         "figure", "h1", "h2", "h3", "h4", "h5", "h6", "table", "form", "blockquote", "pre", "hr"}
RAW = {"style", "script"}

# COMPONENT CONTRACT (window.Alibi): contract props plus the extras components.js implements.
COMMON = {"style", "class", "className", "id", "key", "title", "role", "tabIndex", "onClick"}
CONTRACT = {
    "Button": {"variant", "size", "icon", "iconOnly", "ariaLabel", "disabled", "type", "onClick"},
    "IconButton": {"icon", "ariaLabel", "size", "disabled", "onClick"},
    "Icon": {"name", "size"},
    "Chip": {"selected", "icon", "kbd", "onClick"},
    "Kbd": set(),
    "Composer": {"placeholder", "value", "chips", "focused", "onSubmit", "onChange"},
    "Card": {"tone", "padding", "as"},
    "StatusDot": {"label", "size", "text"},
    "SampleStrip": {"labels", "size", "develop", "frames"},
    "VerdictPill": {"verdict", "ratio"},
    "Meter": {"value", "partAt", "doneAt", "label"},
    "RingTimer": {"progress", "value", "caption", "size", "tone"},
    "Stat": {"value", "label", "sub"},
    "StreakBadge": {"days", "freezes"},
    "PinchLine": {"mood", "theme", "compact"},
    "Pinch": {"mood", "size", "play", "playKey", "theme", "still", "force"},
    "NotchIsland": {"state", "width", "leading", "trailing", "shake", "label"},
    "Toast": {"kind", "title", "actions", "onClose", "icon", "mood"},
}
ICONS = set("play pause stop plus check x camera laptop phone run heart moon calendar settings lens cup "
            "arrow-up arrow-right chevron-right chevron-down clock flag eye sparkle claw undo film".split())
MOODS = {"idle", "focused", "listening", "thinking", "sleepy", "reading"}
CLIPS = {"hello", "sideeye", "nudge", "celebrate", "partial", "supportive", "surprise", "connected"}
ENUMS = {
    ("Button", "variant"): {"primary", "secondary", "ghost", "quiet"},
    ("Button", "size"): {"sm", "md", "lg"},
    ("IconButton", "size"): {"sm", "md", "lg"},
    ("Card", "tone"): {"default", "raised", "accent", "warn"},
    ("Card", "padding"): {"sm", "md", "lg"},
    ("StatusDot", "label"): {"on_task", "idle", "phone", "off_task", "absent"},
    ("VerdictPill", "verdict"): {"done", "partial", "slacked"},
    ("RingTimer", "tone"): {"accent", "partial", "warn"},
    ("Pinch", "mood"): MOODS,
    ("Pinch", "play"): CLIPS,
    ("Pinch", "theme"): {"dark", "light", "auto"},
    ("PinchLine", "mood"): MOODS,
    ("Toast", "kind"): {"nudge", "verdict", "info"},
    ("Toast", "mood"): MOODS,
    ("NotchIsland", "state"): {"idle", "live", "peek", "expanded", "nudge", "verdict", "break"},
}
# README "Size ladder": nothing in between.
PINCH_LADDER = {16, 20, 28, 32, 44, 56, 64, 96, 160}

EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000026FF\U00002B50\U00002B55\U0000FE0F\U0000200D"
                   "\U0000231A\U0000231B\U000023E9-\U000023FA\U00002700-\U00002712\U00002714\U00002716-\U000027BF]")
HOLE = re.compile(r"\{\{(.*?)\}\}", re.S)
LOOKUP = re.compile(r"^\$?[A-Za-z_][\w$]*(\.(\$?[A-Za-z_][\w$]*|\d+))*$")
LITERAL = re.compile(r"""^(true|false|null|-?\d+(\.\d+)?|"[^"]*"|'[^']*')$""")
TAG = re.compile(r"<(/?)([a-zA-Z][\w:.-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*?)(/?)>", re.S)
ATTR = re.compile(r"""\s+([^\s=/>"']+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>"']+))?""", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def camel(name):
    return re.sub(r"-([a-z])", lambda m: m.group(1).upper(), name)


def load_styles():
    """Frozen type styles as {size: [(name, line-height, weight, tracking-em)]} from tokens.json."""
    styles = {}
    try:
        groups = json.loads(TOKENS.read_text(encoding="utf-8"))["type"]["groups"]
    except (OSError, ValueError, KeyError):
        return styles
    for g in groups:
        if g.get("name") == "iPhone":
            continue  # the iPhone boards have their own linter; these boards draw web, island and LA type
        for s in g["styles"]:
            size = int(float(str(s["fontSize"]).rstrip("px")))
            ls = str(s.get("letterSpacing", "0"))
            em = float(ls[:-2]) if ls.endswith("em") else float(ls.rstrip("px") or 0) / size
            styles.setdefault(size, []).append((s["name"], float(s["lineHeight"]), int(s["fontWeight"]), round(em, 3)))
    # dark body: 16 / 1.6 / +0.01em (README "Surfaces")
    styles.setdefault(16, []).append(("body-dark", 1.6, 400, 0.01))
    return styles


STYLES = load_styles()


class Lint:
    def __init__(self, path):
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.errors = []
        self.ids = set(re.findall(r'\sid="([^"{}]+)"', self.text))
        self.pinch_holes = set()

    def line(self, idx):
        return self.text.count("\n", 0, idx) + 1

    def err(self, kind, idx, msg):
        self.errors.append((kind, self.line(idx) if idx is not None else 0, msg))

    def run(self):
        t = self.text
        if not t.lstrip().lower().startswith("<!doctype html>"):
            self.err("format", 0, "file must start with <!doctype html>")
        if not re.search(r'<html lang="[a-z]{2}(-[A-Z]{2})?">', t):
            self.err("format", 0, '<html lang="…"> missing')
        self.check_head()
        self.check_xdc()
        self.check_script()
        for m in EMOJI.finditer(t):
            self.err("format", m.start(), "emoji or pictographic symbol U+%04X" % ord(m.group(0)))
        return self.errors

    # ---------- head ----------
    def check_head(self):
        m = re.search(r"<head>(.*?)</head>", self.text, re.S)
        if not m:
            self.err("format", 0, "no <head>…</head>")
            return
        lines = [ln.strip() for ln in m.group(1).split("\n") if ln.strip()]
        if len(lines) != len(HEAD):
            self.err("format", m.start(), "head must be exactly %d lines in order: %s (found %d)"
                     % (len(HEAD), " · ".join(n for _, n in HEAD), len(lines)))
        for i, (pat, want) in enumerate(HEAD):
            if i >= len(lines) or not pat.match(lines[i]):
                self.err("format", m.start(), "head line %d must be %s, found %r"
                         % (i + 1, want, lines[i] if i < len(lines) else None))

    # ---------- <x-dc> ----------
    def check_xdc(self):
        t = self.text
        opens = [m.start() for m in re.finditer(r"<x-dc>", t)]
        closes = [m.start() for m in re.finditer(r"</x-dc>", t)]
        if len(opens) != 1 or len(closes) != 1:
            self.err("format", None, "need exactly one <x-dc> … </x-dc> (found %d / %d)" % (len(opens), len(closes)))
            return
        self.x0, self.x1 = opens[0], closes[0] + len("</x-dc>")
        body = t[self.x0:self.x1]
        helmets = re.findall(r"<helmet>", body)
        hm = re.match(r"<x-dc>\s*<helmet>(.*?)</helmet>", body, re.S)
        if len(helmets) != 1 or not hm:
            self.err("format", self.x0, "<x-dc> must open with exactly one <helmet>…</helmet>")
        else:
            inner = re.sub(r"<style>.*?</style>", "", hm.group(1), flags=re.S)
            inner = re.sub(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/css2[^"]*">', "", inner).strip()
            if inner:
                self.err("format", self.x0, "helmet may hold only <style> and a Google Fonts link: %r" % inner[:60])
            for st in re.finditer(r"<style>(.*?)</style>", hm.group(1), re.S):
                css = re.sub(r"@keyframes\s+[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", st.group(1))
                css = re.sub(r"\s+", "", css)
                for rule in (r"body\{margin:0;?\}", r"a\{color:[^}]*\}", r"a:hover\{color:[^}]*\}"):
                    css = re.sub(rule, "", css)
                if css:
                    self.err("format", self.x0, "helmet <style> beyond body{margin:0}, a/a:hover and @keyframes: %r" % css[:80])
        self.check_tags(body, self.x0)
        self.check_holes(body, self.x0)
        self.check_root(body, self.x0)

    def check_tags(self, body, off):
        stack = []  # (tag, pos, tnum)
        last = 0
        clean = COMMENT.sub(lambda m: " " * len(m.group(0)), body)
        for m in TAG.finditer(clean):
            closing, tag, raw, selfclose = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
            pos = off + m.start()
            if stack and stack[-1][0] in RAW and not (closing and tag == stack[-1][0]):
                continue
            self.check_text(clean[last:m.start()], off + last, stack)
            last = m.end()
            if closing:
                if not stack:
                    self.err("format", pos, "stray </%s>" % tag)
                    continue
                if stack[-1][0] != tag:
                    self.err("format", pos, "</%s> closes <%s> opened on line %d" % (tag, stack[-1][0], self.line(stack[-1][1])))
                    if tag in [s[0] for s in stack]:
                        while stack and stack[-1][0] != tag:
                            stack.pop()
                        stack.pop()
                    continue
                stack.pop()
                continue
            a = self.attrs(raw, pos, tag)
            parents = [s[0] for s in stack]
            if tag in ("iframe", "object", "embed"):
                self.err("format", pos, "<%s> is not allowed" % tag)
            if selfclose and tag not in VOID:
                self.err("format", pos, "<%s/> self-closed: close it explicitly" % tag)
            if tag in BLOCK and parents and parents[-1] == "p":
                self.err("format", pos, "<%s> inside <p> (the parser closes the <p>)" % tag)
            if tag in ("button", "a") and tag in parents:
                self.err("format", pos, "<%s> nested inside <%s>" % (tag, tag))
            if "a" in parents and (tag in ("button", "input") or (tag == "x-import" and re.search(
                    r"Alibi\.(Button|IconButton|Chip|Composer)\b", a.get("component-from-global-scope", ""))
                    and a.get("tab-index") != "{{ noTab }}")):
                self.err("format", pos, "a control inside <a> swallows the click; style the <a> itself")
            self.check_element(tag, a, pos)
            st = a.get("style", "")
            tnum = (stack[-1][2] if stack else False) or "tabular-nums" in st or tag in ("code", "kbd")
            if tag == "x-import":
                tnum = True  # components set their own numerals
            if tag not in VOID and not selfclose:
                stack.append((tag, pos, tnum))
        for tag, pos, _ in stack:
            self.err("format", pos, "<%s> is never closed" % tag)

    def check_text(self, text, pos, stack):
        bare = HOLE.sub("", text)
        if re.search(r"\d", bare) and stack and not stack[-1][2] and stack[-1][0] not in RAW:
            self.err("design", pos, "digits %r without font-variant-numeric: tabular-nums" % bare.strip()[:30])

    def attrs(self, raw, pos, tag):
        out = {}
        for m in ATTR.finditer(raw):
            k, v = m.group(1), m.group(2)
            if v is None:
                if k not in ("data-dc-script", "disabled", "hidden", "checked", "selected", "readonly", "required", "open", "multiple"):
                    self.err("format", pos, "<%s> attribute %s has no value" % (tag, k))
                out[k] = ""
                continue
            if not v.startswith('"'):
                self.err("format", pos, "<%s> attribute %s is not double-quoted: %s" % (tag, k, v[:40]))
                v = v.strip("'")
            else:
                v = v[1:-1]
            if k in out:
                self.err("format", pos, "<%s> repeats attribute %s" % (tag, k))
            out[k] = v
        return out

    def inner_text(self, pos, tag):
        close = self.text.find("</%s>" % tag, pos)
        inner = self.text[pos:close]
        inner = inner[inner.find(">") + 1:]
        inner = re.sub(r'<span class="al-sr">', "", inner)
        return HOLE.sub("x", re.sub(r"<[^>]+>", "", inner)).strip()

    def check_element(self, tag, a, pos):
        for k, v in a.items():
            if k.lower() in ("onclick", "on-click"):
                if not re.fullmatch(r"\{\{\s*[\w.$]+\s*\}\}", v):
                    self.err("format", pos, "%s must be one {{ handler }} hole" % k)
                if tag in ("div", "span", "li", "p", "section", "article", "img", "svg"):
                    self.err("design", pos, "onClick on <%s>: use a real <button> or <a href>" % tag)
            elif k.startswith("on") and k[2:3].isupper() and not re.fullmatch(r"\{\{\s*[\w.$]+\s*\}\}", v):
                self.err("format", pos, "%s must be one {{ handler }} hole" % k)
        if tag == "sc-if" and ("value" not in a or "hint-placeholder-val" not in a):
            self.err("format", pos, 'sc-if needs value="{{ … }}" and hint-placeholder-val')
        if tag == "sc-for":
            for need in ("list", "as", "hint-placeholder-count"):
                if need not in a:
                    self.err("format", pos, "sc-for needs %s" % need)
        if tag in ("div", "span", "article", "section") and a.get("role") in ("button", "link", "checkbox", "tab"):
            self.err("design", pos, "role=%s on <%s>: use the real element" % (a["role"], tag))
        if a.get("role") == "img" and not (a.get("aria-label") or a.get("aria-labelledby")):
            self.err("format", pos, 'role="img" needs aria-label')
        if a.get("role") == "group" and not a.get("aria-label"):
            self.err("format", pos, 'role="group" needs aria-label')
        for ref in a.get("aria-labelledby", "").split():
            if ref not in self.ids:
                self.err("format", pos, "aria-labelledby=%s names no element id" % ref)
        if tag == "a":
            href = a.get("href", "")
            if not href:
                self.err("format", pos, "<a> without href")
            elif href.endswith(".dc.html"):
                name = href.lstrip("./")
                if name not in LINK_TARGETS:
                    self.err("format", pos, "prototype link %s is not one of the canvas boards" % href)
                elif not (PROJECT / name).exists():
                    self.err("format", pos, "prototype link to missing artboard %s" % href)
            if not self.inner_text(pos, "a") and not a.get("aria-label"):
                self.err("format", pos, "<a> with no text needs aria-label")
        if tag == "button":
            if a.get("type") not in ("button", "submit", "reset"):
                self.err("format", pos, '<button> needs type="button"')
            if not self.inner_text(pos, "button") and not a.get("aria-label") and not a.get("aria-labelledby"):
                self.err("format", pos, "icon-only <button> needs aria-label")
        if tag in ("input", "select", "textarea") and not (a.get("aria-label") or a.get("id")):
            self.err("format", pos, "<%s> needs a <label for> or aria-label" % tag)
        if tag == "x-import":
            self.check_import(a, pos)
        st = a.get("style", "")
        if st:
            self.check_style(tag, st, pos, wordmark="al-wordmark" in a.get("class", "").split())

    def check_import(self, a, pos):
        g = a.get("component-from-global-scope")
        if not g:
            self.err("format", pos, "<x-import> without component-from-global-scope")
            return
        m = re.fullmatch(r"Alibi\.(\w+)", g)
        if not m or m.group(1) not in CONTRACT:
            self.err("format", pos, "x-import %s is not in the Alibi COMPONENT CONTRACT" % g)
            return
        comp = m.group(1)
        allowed = CONTRACT[comp] | COMMON
        for k, v in a.items():
            if k in ("component-from-global-scope", "style", "hint-size") or k.startswith(("data-", "aria-")):
                continue
            prop = camel(k[len("sc-camel-"):]) if k.startswith("sc-camel-") else camel(k)
            if prop not in allowed:
                self.err("format", pos, "Alibi.%s has no prop %s" % (comp, prop))
            enum = ENUMS.get((comp, prop))
            if enum and "{{" not in v and v not in enum:
                self.err("format", pos, "Alibi.%s %s=%r: expected one of %s" % (comp, prop, v, sorted(enum)))
        icon = a.get("name") if comp == "Icon" else a.get("icon")
        if icon and "{{" not in icon and icon not in ICONS:
            self.err("format", pos, "Alibi.%s icon %r is not in the icon set" % (comp, icon))
        if comp == "IconButton" and not a.get("sc-camel-aria-label"):
            self.err("format", pos, 'Alibi.IconButton needs sc-camel-aria-label="…" (it reads ariaLabel)')
        if comp == "Button" and "icon-only" in a and not a.get("sc-camel-aria-label"):
            self.err("format", pos, 'icon-only Alibi.Button needs sc-camel-aria-label="…"')
        if comp == "Pinch":
            size = a.get("size", "")
            hm = re.fullmatch(r"\{\{\s*([\w$]+)\s*\}\}", size)
            if hm:
                self.pinch_holes.add(hm.group(1))
            if size.isdigit() and int(size) not in PINCH_LADDER:
                self.err("design", pos, "Pinch size %s is off the ladder %s" % (size, sorted(PINCH_LADDER)))

    def check_style(self, tag, st, pos, wordmark=False):
        if re.search(r"#[0-9a-fA-F]{3,8}\b", st):
            self.err("design", pos, "hex colour in a style: pick colours by token (var(--…))")
        if re.search(r"\brgba?\(|\bhsla?\(", st):
            self.err("design", pos, "raw rgb()/hsl() in a style: pick colours by token")
        if re.search(r"(linear|radial|conic)-gradient", st):
            self.err("design", pos, "gradient: the only gradient is the celebration bloom")
        b = re.search(r"filter:\s*blur\((\d+)", st)
        if b and int(b.group(1)) > 12:
            self.err("design", pos, "blur(%spx) wash: blur bridges swaps, never decorates" % b.group(1))
        if re.search(r"text-transform:\s*uppercase", st):
            self.err("design", pos, "uppercase text: only the ALIBI wordmark is capitals, typed that way")
        if re.search(r"border-left:\s*[2-9]px", st):
            self.err("design", pos, "left-border card")
        if re.search(r"font-family:\s*(?!\s|var\(--font-)", st):
            self.err("design", pos, "font-family must be var(--font-sans|rounded|mono)")
        if wordmark:
            # the one heavy setting: 12 in the island, 72 on the title card, scaled in thumbnails
            if re.search(r"font-weight|letter-spacing|font-family", st):
                self.err("design", pos, "al-wordmark sets its own weight, tracking and family: override font-size only")
            return
        self.check_type(st, pos)

    def check_type(self, st, pos):
        fs = re.search(r"(?<![-\w])font-size:\s*([\d.]+)px", st)
        if not fs:
            return
        size = int(float(fs.group(1)))
        cands = STYLES.get(size)
        if not cands:
            self.err("design", pos, "font-size %dpx is no frozen style (sizes: %s)" % (size, sorted(STYLES)))
            return
        lh = re.search(r"line-height:\s*([\d.]+)(?![\w%])", st)
        fw = re.search(r"font-weight:\s*(\d+)", st)
        ls = re.search(r"letter-spacing:\s*(-?[\d.]+)(em|px)", st)
        lh = float(lh.group(1)) if lh else None
        fw = int(fw.group(1)) if fw else 400
        em = None
        if ls:
            em = float(ls.group(1)) if ls.group(2) == "em" else float(ls.group(1)) / size
        for name, clh, cfw, cem in cands:
            if (lh is None or abs(lh - clh) < 0.011) and fw == cfw and (em is None or abs(em - cem) < 0.003):
                return
        self.err("design", pos, "type %dpx/%s/w%d/%s matches no frozen style; at %dpx: %s" % (
            size, lh if lh is not None else "-", fw, ("%gem" % em) if em is not None else "-", size,
            ", ".join("%s %g/w%d/%gem" % c for c in cands)))

    def check_holes(self, body, off):
        for m in HOLE.finditer(body):
            inner = m.group(1).strip()
            if not inner:
                self.err("format", off + m.start(), "empty hole {{ }}")
            elif not (LOOKUP.match(inner) or LITERAL.match(inner)):
                self.err("format", off + m.start(), "hole {{ %s }} is not a dotted lookup: compute it in renderVals()" % inner[:50])

    def check_root(self, body, off):
        hm = re.match(r"<x-dc>\s*<helmet>.*?</helmet>\s*", body, re.S)
        if not hm:
            return
        rest = COMMENT.sub(lambda m: " " * len(m.group(0)), body[hm.end():])
        rm = TAG.match(rest)
        pos = off + hm.end()
        if not rm or rm.group(1):
            self.err("format", pos, "no root element after <helmet>")
            return
        a = {m.group(1): (m.group(2) or '""')[1:-1] for m in ATTR.finditer(rm.group(3))}
        depth, end = 1, len(rest)
        for m in TAG.finditer(rest, rm.end()):
            if m.group(4) or m.group(2).lower() in VOID:
                continue
            depth += -1 if m.group(1) else 1
            if depth == 0:
                end = m.end()
                break
        if re.sub(r"\s+", "", rest[end:]).replace("</x-dc>", ""):
            self.err("format", pos, "more than one root element inside <x-dc>")
        theme = a.get("data-theme", "")
        if theme not in ("dark", "light") and not HOLE.fullmatch(theme.strip()):
            self.err("design", pos, 'root needs data-theme="dark" (or "light")')
        st = a.get("style", "")
        for need in ("background: var(--bg)", "color: var(--ink)", "font-family: var(--font-sans)"):
            if need not in st:
                self.err("design", pos, "root style needs %s" % need)
        w = re.search(r"(?<![-\w])width:\s*(\d+)px", st)
        h = re.search(r"(?<![-\w])height:\s*(\d+)px", st)
        self.root_fixed = (int(w.group(1)), int(h.group(1))) if w and h else None
        self.root_pos = pos
        if not self.root_fixed and "max-width" not in rest[:end]:
            self.err("format", pos, "root is neither fixed (px width and height) nor a max-width PAGE")

    # ---------- logic ----------
    def check_script(self):
        t = self.text
        blocks = list(re.finditer(r"<script type=\"text/x-dc\" data-dc-script data-props='([^']*)'>(.*?)</script>", t, re.S))
        anyblocks = re.findall(r"<script[^>]*data-dc-script", t)
        if len(blocks) != 1 or len(anyblocks) != 1:
            self.err("format", None, "need exactly one <script type=\"text/x-dc\" data-dc-script data-props='…'> (found %d)" % len(anyblocks))
            return
        b = blocks[0]
        if hasattr(self, "x1") and b.start() < self.x1:
            self.err("format", b.start(), "the logic script must follow </x-dc>")
        raw = b.group(1)
        if re.search(r"&(?!amp;|#39;|quot;|lt;|gt;)", raw):
            self.err("format", b.start(), "data-props: escape & as &amp;")
        try:
            props = json.loads(html.unescape(raw))
        except ValueError as e:
            self.err("format", b.start(), "data-props is not JSON after entity decoding: %s" % e)
            props = {}
        pv = props.get("$preview")
        if not (isinstance(pv, dict) and isinstance(pv.get("width"), int) and isinstance(pv.get("height"), int)):
            self.err("format", b.start(), "data-props needs $preview {width, height} as integers")
            pv = None
        for k, v in props.items():
            if k == "$preview":
                continue
            if not isinstance(v, dict) or "editor" not in v:
                self.err("format", b.start(), "data-props %s needs an editor" % k)
            elif v["editor"] == "enum" and v.get("default") not in v.get("options", []):
                self.err("format", b.start(), "data-props %s default is not one of its options" % k)
            elif v["editor"] == "text":
                self.err("design", b.start(), "data-props %s is a text tweak: copy stays literal markup" % k)
        root = getattr(self, "root_fixed", None)
        if pv and root and (pv["width"], pv["height"]) != root:
            self.err("format", self.root_pos, "fixed root is %dx%d but $preview is %dx%d" % (root + (pv["width"], pv["height"])))
        js = b.group(2)
        if not re.search(r"\bclass\s+Component\s+extends\s+DCLogic\b", js):
            self.err("format", b.start(), "logic must be class Component extends DCLogic")
        if not re.search(r"\brenderVals\s*\(", js):
            self.err("format", b.start(), "no renderVals()")
        if re.search(r"^\s*(import|export)\b", js, re.M):
            self.err("format", b.start(), "no import/export in the logic block")
        for pat, what in ((r"\binnerHTML\b", "innerHTML"), (r"\bouterHTML\b", "outerHTML"),
                          (r"\bappendChild\b", "appendChild"), (r"\binsertAdjacentHTML\b", "insertAdjacentHTML"),
                          (r"\bcreateElement\b", "createElement"), (r"\bwindow\.\w+\s*=(?!=)", "assigning window.X"),
                          (r"\bdocument\.(write|body|getElement|querySelector)", "DOM access"),
                          (r"addEventListener\(\s*['\"]key", "global key handler"), (r"\bfetch\(|XMLHttpRequest", "network")):
            for m in re.finditer(pat, js):
                self.err("format", b.start(2) + m.start(), "%s in the logic block" % what)
        if re.search(r"</?[a-z]+[\s>]", js):
            self.err("format", b.start(2), "markup inside the logic block")
        for name in sorted(self.pinch_holes):
            for m in re.finditer(r"\b%s\s*:\s*(\d+)\b" % re.escape(name), js):
                if int(m.group(1)) not in PINCH_LADDER:
                    self.err("design", b.start(2) + m.start(), "Pinch size %s: %s is off the ladder %s"
                             % (name, m.group(1), sorted(PINCH_LADDER)))


def main(argv):
    if "--all" in argv:
        files = sorted(PROJECT.glob("*.dc.html"))
    elif len([a for a in argv[1:] if not a.startswith("--")]):
        files = [pathlib.Path(a) for a in argv[1:] if not a.startswith("--")]
    else:
        files = [PROJECT / ("%s.dc.html" % n) for n in BOARDS]
    if not STYLES:
        print("warning: %s unreadable; type styles not checked" % TOKENS)
    total = 0
    for f in files:
        if not f.exists():
            print("%s: missing" % f)
            total += 1
            continue
        errs = Lint(f).run()
        total += len(errs)
        print("%-24s %s" % (f.name, "ok" if not errs else "%d issue%s" % (len(errs), "" if len(errs) == 1 else "s")))
        for kind, ln, msg in sorted(errs, key=lambda e: e[1]):
            print("  %-6s L%-4d %s" % (kind, ln, msg))
    print("\n%d issue%s in %d file%s" % (total, "" if total == 1 else "s", len(files), "" if len(files) == 1 else "s"))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
