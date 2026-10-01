#!/usr/bin/env python3
"""Format lint for the Mac artboards of the "Alibi Screens" canvas (docs/design/canvas/project/*.dc.html).

    python3 docs/design/canvas/tools/lint_mac.py                 # the eight Mac boards
    python3 docs/design/canvas/tools/lint_mac.py FILE [FILE...]  # any .dc.html
    python3 docs/design/canvas/tools/lint_mac.py --all           # every board in project/

Exit status 1 when any error is found. Two classes of check:

  format  the .dc.html contract (head lines, one <x-dc> + <helmet>, one data-dc-script with
          class Component extends DCLogic, data-props JSON, dotted-lookup holes, sc-if/sc-for hints,
          balanced and closed elements, double-quoted attributes, no script-built UI, no emoji, no
          iframe/object/embed, named icon-only buttons, root size = $preview, x-import names and
          props from the Alibi component contract, prototype links that resolve)
  design  rules from docs/design/system/project/README.md that a parser can see (frozen type sizes per
          surface, colours by token only, no gradients or blur washes, no uppercase eyebrows, no
          left-border cards, onClick only on real controls, root theme + background tokens)
"""
import html
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parent / "project"
MAC_BOARDS = ["Dashboard", "Island-Proto", "Island-Idle", "Island-Live", "Island-Expanded",
              "Island-Nudge", "Island-Verdict", "Island-Break"]

HEAD = [
    re.compile(r'^<meta charset="utf-8">$'),
    re.compile(r'^<title>[^<]{2,80}</title>$'),
    re.compile(r'^<script src="\./support\.js"></script>$'),
    re.compile(r'^<link rel="stylesheet" href="ds/alibi/components/bundle\.css">$'),
    re.compile(r'^<script src="ds/alibi/components/bundle\.js"></script>$'),
]
HEAD_NAMES = ['<meta charset="utf-8">', "<title>…</title>", '<script src="./support.js"></script>',
              '<link rel="stylesheet" href="ds/alibi/components/bundle.css">',
              '<script src="ds/alibi/components/bundle.js"></script>']

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
BLOCK = {"div", "p", "ul", "ol", "li", "section", "article", "header", "footer", "main", "aside", "nav",
         "figure", "h1", "h2", "h3", "h4", "h5", "h6", "table", "form", "blockquote", "pre", "hr"}
INTERACTIVE = {"button", "a", "input", "select", "textarea", "label"}

# The COMPONENT CONTRACT (window.Alibi). Values: props the contract names plus the extras the bundle
# implements (components.js) and the canvas runtime always accepts (style, class, aria-*, data-*).
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

# Frozen type sizes (px). Web = the dashboard; island boards also carry the island scale plus the
# 13px macOS menu bar and the prototype's 12/13px control strip.
WEB_SIZES = {56, 32, 22, 17, 20, 16, 13, 12}
ISLAND_SIZES = {12, 13, 34, 17, 15, 14, 11}

EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000026FF\U00002B50\U00002B55\U0000FE0F\U0000200D"
                   "\U0000231A\U0000231B\U000023E9-\U000023FA\U00002700-\U00002712\U00002714\U00002716-\U000027BF]")
HOLE = re.compile(r"\{\{(.*?)\}\}", re.S)
LOOKUP = re.compile(r"^\$?[A-Za-z_][\w$]*(\.(\$?[A-Za-z_][\w$]*|\d+))*$")
LITERAL = re.compile(r"""^(true|false|null|-?\d+(\.\d+)?|"[^"]*"|'[^']*')$""")
TAG = re.compile(r"<(/?)([a-zA-Z][\w:.-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*?)(/?)>", re.S)
ATTR = re.compile(r"""\s+([^\s=/>"']+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>"']+))?""", re.S)


def camel(name):
    return re.sub(r"-([a-z])", lambda m: m.group(1).upper(), name)


class Lint:
    def __init__(self, path):
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.errors = []

    def line(self, idx):
        return self.text.count("\n", 0, idx) + 1

    def err(self, kind, idx, msg):
        self.errors.append((kind, self.line(idx) if idx is not None else 0, msg))

    # ---------- structure ----------
    def run(self):
        t = self.text
        name = self.path.stem.replace(".dc", "")
        self.island = name.startswith("Island")
        if not t.lstrip().lower().startswith("<!doctype html>"):
            self.err("format", 0, "file must start with <!doctype html>")
        if not re.search(r'<html lang="[a-z]{2}(-[A-Z]{2})?">', t):
            self.err("format", 0, '<html lang="…"> missing')
        self.check_head()
        self.check_xdc()
        self.check_script()
        self.check_emoji()
        return self.errors

    def check_head(self):
        m = re.search(r"<head>(.*?)</head>", self.text, re.S)
        if not m:
            self.err("format", 0, "no <head>…</head>")
            return
        lines = [ln.strip() for ln in m.group(1).split("\n") if ln.strip()]
        if len(lines) != len(HEAD):
            self.err("format", m.start(), "head must be exactly %d lines in order: %s (found %d)"
                     % (len(HEAD), " · ".join(HEAD_NAMES), len(lines)))
        for i, (pat, want) in enumerate(zip(HEAD, HEAD_NAMES)):
            if i >= len(lines) or not pat.match(lines[i]):
                self.err("format", m.start(), "head line %d must be %s, found %r"
                         % (i + 1, want, lines[i] if i < len(lines) else None))

    def check_xdc(self):
        t = self.text
        opens = [m.start() for m in re.finditer(r"<x-dc>", t)]
        closes = [m.start() for m in re.finditer(r"</x-dc>", t)]
        if len(opens) != 1 or len(closes) != 1:
            self.err("format", None, "need exactly one <x-dc> … </x-dc> (found %d / %d)" % (len(opens), len(closes)))
            return
        self.x0, self.x1 = opens[0], closes[0] + len("</x-dc>")
        body = t[self.x0:self.x1]
        if not re.match(r"<x-dc>\s*<helmet>.*?</helmet>", body, re.S):
            self.err("format", self.x0, "<x-dc> must open with <helmet>…</helmet>")
        else:
            hm = re.match(r"<x-dc>\s*<helmet>(.*?)</helmet>", body, re.S)
            inner = re.sub(r"<style>.*?</style>", "", hm.group(1), flags=re.S).strip()
            if inner:
                self.err("format", self.x0, "helmet may hold only <style> (and a Google Fonts link): %r" % inner[:60])
            for st in re.finditer(r"<style>(.*?)</style>", hm.group(1), re.S):
                css = re.sub(r"@keyframes\s+[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", st.group(1))
                css = re.sub(r"\s+", "", css)
                css = re.sub(r"body\{margin:0;?\}", "", css)
                css = re.sub(r"a\{color:[^}]*\}", "", css)
                css = re.sub(r"a:hover\{color:[^}]*\}", "", css)
                if css:
                    self.err("format", self.x0, "helmet <style> beyond body{margin:0}, a/a:hover and @keyframes: %r" % css[:80])
        self.check_tags(body, self.x0)
        self.check_holes(body, self.x0)
        self.check_root(body, self.x0)

    def check_tags(self, body, off):
        stack = []
        for m in TAG.finditer(body):
            closing, tag, attrs, selfclose = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
            pos = off + m.start()
            if tag in ("style", "script") and not closing:
                # skip raw text: the matching close is handled by the regex scan below
                pass
            if closing:
                if not stack:
                    self.err("format", pos, "stray </%s>" % tag)
                    continue
                if stack[-1][0] != tag:
                    self.err("format", pos, "</%s> closes <%s> opened on line %d" % (tag, stack[-1][0], self.line(stack[-1][1])))
                    # recover: pop to the matching tag if present
                    names = [s[0] for s in stack]
                    if tag in names:
                        while stack and stack[-1][0] != tag:
                            stack.pop()
                        stack.pop()
                    continue
                stack.pop()
                continue
            a = self.attrs(attrs, pos, tag)
            if tag in ("iframe", "object", "embed"):
                self.err("format", pos, "<%s> is not allowed" % tag)
            if selfclose and tag not in VOID:
                self.err("format", pos, "<%s/> self-closed: close it explicitly" % tag)
            # nesting rules a browser would silently "fix"
            parents = [s[0] for s in stack]
            if tag in BLOCK and parents and parents[-1] == "p":
                self.err("format", pos, "<%s> inside <p> (the parser closes the <p>)" % tag)
            if tag in ("button", "a") and tag in parents:
                self.err("format", pos, "<%s> nested inside <%s>" % (tag, tag))
            if tag == "li" and parents and parents[-1] not in ("ul", "ol", "sc-for", "sc-if"):
                self.err("format", pos, "<li> outside <ul>/<ol>")
            if "a" in parents and (tag in ("button", "input") or
                                   (tag == "x-import" and re.search(r"Alibi\.(Button|IconButton|Chip|Composer)\b", a.get("component-from-global-scope", "")))):
                self.err("format", pos, "a control inside <a> swallows the click; style the <a> itself")
            self.check_element(tag, a, pos, attrs)
            if tag not in VOID and not selfclose:
                stack.append((tag, pos))
                if tag in ("style", "script"):
                    pass
        for tag, pos in stack:
            self.err("format", pos, "<%s> is never closed" % tag)

    def attrs(self, raw, pos, tag):
        out = {}
        for m in ATTR.finditer(raw):
            k, v = m.group(1), m.group(2)
            if v is None:
                if k not in ("data-dc-script", "disabled", "hidden", "checked", "selected", "readonly", "required", "open", "multiple", "autofocus"):
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

    def check_element(self, tag, a, pos, raw):
        # events only on real controls, always a whole hole
        for k, v in a.items():
            if k.lower().startswith("on") and k.lower() != "onclick" and tag != "x-import":
                if k[2:3].isupper() or k.lower() in ("onchange", "oninput", "onsubmit", "onkeydown", "onfocus", "onblur"):
                    if not re.fullmatch(r"\{\{\s*[\w.$]+\s*\}\}", v):
                        self.err("format", pos, "%s must be one {{ handler }} hole" % k)
            if k == "onClick" or k == "onclick" or k == "on-click":
                if not re.fullmatch(r"\{\{\s*[\w.$]+\s*\}\}", v):
                    self.err("format", pos, "%s must be one {{ handler }} hole" % k)
                if tag in ("div", "span", "li", "p", "section", "img", "svg"):
                    self.err("design", pos, "onClick on <%s>: use a real <button> or <a href>" % tag)
        if tag in ("sc-if",):
            if "value" not in a or "hint-placeholder-val" not in a:
                self.err("format", pos, "<sc-if> needs value=\"{{ … }}\" and hint-placeholder-val")
        if tag in ("sc-for",):
            for need in ("list", "as", "hint-placeholder-count"):
                if need not in a:
                    self.err("format", pos, "<sc-for> needs %s" % need)
        if tag in ("div", "span") and "role" in a and a["role"] in ("button", "link", "checkbox", "tab"):
            self.err("design", pos, "role=%s on <%s>: use the real element" % (a["role"], tag))
        if tag == "a":
            href = a.get("href", "")
            if not href:
                self.err("format", pos, "<a> without href")
            elif href.endswith(".dc.html") and "{{" not in href:
                target = (self.path.parent / href.lstrip("/")).resolve() if not href.startswith("/") else (PROJECT / href[1:])
                if not target.exists():
                    self.err("format", pos, "prototype link to missing artboard %s" % href)
        if tag == "button":
            if "type" not in a:
                self.err("format", pos, "<button> without type=\"button\"")
            # name: aria-label, or visible text (checked after the element closes; approximated here)
            close = self.text.find("</button>", pos)
            inner = self.text[pos:close]
            inner_text = re.sub(r"<[^>]+>", "", inner[inner.find(">") + 1:])
            inner_text = HOLE.sub("x", inner_text).strip()
            if not inner_text and not a.get("aria-label") and not a.get("aria-labelledby"):
                self.err("format", pos, "icon-only <button> needs aria-label")
        if tag == "x-import":
            self.check_import(a, pos)
        # styles
        st = a.get("style", "")
        if st:
            self.check_style(tag, st, pos)

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
            if k in ("component-from-global-scope", "style", "hint-size"):
                continue
            if k.startswith("data-"):
                continue
            if k.startswith("aria-"):
                if comp in ("IconButton",) and k == "aria-label":
                    self.err("format", pos, "Alibi.IconButton reads ariaLabel, so aria-label is dropped and the button "
                             "has no name: write sc-camel-aria-label=\"…\"")
                continue
            prop = camel(k[len("sc-camel-"):]) if k.startswith("sc-camel-") else camel(k)
            if prop not in allowed:
                self.err("format", pos, "Alibi.%s has no prop %s" % (comp, prop))
            enum = ENUMS.get((comp, prop))
            if enum and "{{" not in v and v not in enum:
                self.err("format", pos, "Alibi.%s %s=%r: expected one of %s" % (comp, prop, v, sorted(enum)))
        if comp in ("Icon", "IconButton"):
            nm = a.get("name") if comp == "Icon" else a.get("icon")
            if nm and "{{" not in nm and nm not in ICONS:
                self.err("format", pos, "Alibi.%s icon %r is not in the icon set" % (comp, nm))
        if comp == "Button" and a.get("icon") and "{{" not in a["icon"] and a["icon"] not in ICONS:
            self.err("format", pos, "Alibi.Button icon %r is not in the icon set" % a["icon"])
        if comp == "IconButton" and not a.get("sc-camel-aria-label"):
            if "aria-label" not in a:
                self.err("format", pos, "Alibi.IconButton needs sc-camel-aria-label=\"…\"")
        if comp == "Button" and "icon-only" in a and not a.get("sc-camel-aria-label"):
            self.err("format", pos, "icon-only Alibi.Button needs sc-camel-aria-label=\"…\"")

    def check_style(self, tag, st, pos):
        if re.search(r"#[0-9a-fA-F]{3,8}\b", st):
            self.err("design", pos, "hex colour in a style: pick colours by token (var(--…))")
        if re.search(r"\brgba?\(|\bhsla?\(", st):
            self.err("design", pos, "raw rgb()/hsl() in a style: pick colours by token")
        if re.search(r"(linear|radial|conic)-gradient", st):
            self.err("design", pos, "gradient: the only gradient is the celebration bloom")
        if re.search(r"filter:\s*blur\((\d+)", st):
            b = int(re.search(r"filter:\s*blur\((\d+)", st).group(1))
            if b > 12:
                self.err("design", pos, "blur(%dpx) wash: blur bridges swaps (12px max), never decorates" % b)
        if re.search(r"text-transform:\s*uppercase", st):
            self.err("design", pos, "uppercase text: only the ALIBI wordmark is capitals, and it is typed that way")
        if re.search(r"border-left:\s*[2-9]px", st):
            self.err("design", pos, "left-border card")
        sizes = [int(float(x)) for x in re.findall(r"font-size:\s*([\d.]+)px", st)]
        sizes += [int(float(x)) for x in re.findall(r"\bfont:\s*(?:\d{3}\s+)?([\d.]+)px", st)]
        allowed = ISLAND_SIZES if self.island else WEB_SIZES
        for s in sizes:
            if s not in allowed:
                self.err("design", pos, "font-size %dpx is off the frozen %s scale %s"
                         % (s, "island" if self.island else "web", sorted(allowed)))

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
        rest = body[hm.end():]
        rm = TAG.match(rest)
        if not rm or rm.group(1):
            self.err("format", off + hm.end(), "no root element after <helmet>")
            return
        a = {}
        for m in ATTR.finditer(rm.group(3)):
            a[m.group(1)] = (m.group(2) or '""')[1:-1]
        pos = off + hm.end()
        tail = rest[rm.end():]
        # the root must be the only top-level element
        depth, i = 1, 0
        for m in TAG.finditer(tail):
            tag = m.group(2).lower()
            if m.group(4) or tag in VOID:
                continue
            depth += -1 if m.group(1) else 1
            if depth == 0:
                i = m.end()
                break
        if re.sub(r"\s+", "", tail[i:]).replace("</x-dc>", ""):
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
        if not self.root_fixed:
            if w:
                self.err("format", pos, "a PAGE root has no px width (use a max-width container)")
            if "max-width" not in body[:hm.end() + 2000]:
                self.err("format", pos, "a PAGE needs a max-width container")

    # ---------- logic block ----------
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
        if "renderVals" not in js:
            self.err("format", b.start(), "no renderVals()")
        if re.search(r"^\s*(import|export)\b", js, re.M):
            self.err("format", b.start(), "no import/export in the logic block")
        for pat, what in ((r"\binnerHTML\b", "innerHTML"), (r"\bouterHTML\b", "outerHTML"), (r"\bappendChild\b", "appendChild"),
                          (r"\binsertAdjacentHTML\b", "insertAdjacentHTML"), (r"\bcreateElement\b", "createElement"),
                          (r"\bwindow\.\w+\s*=(?!=)", "assigning window.X"), (r"\bdocument\.(write|body|getElement|querySelector)", "DOM access"),
                          (r"addEventListener\(\s*['\"]key", "global key handler"), (r"\bfetch\(|XMLHttpRequest", "network")):
            for m in re.finditer(pat, js):
                self.err("format", b.start(2) + m.start(), "%s in the logic block" % what)
        if "<" in js and re.search(r"</?[a-z]+[\s>]", js):
            self.err("format", b.start(2), "markup inside the logic block")

    def check_emoji(self):
        for m in EMOJI.finditer(self.text):
            self.err("format", m.start(), "emoji or pictographic symbol U+%04X" % ord(m.group(0)))


def main(argv):
    if "--all" in argv:
        files = sorted(PROJECT.glob("*.dc.html"))
    elif len(argv) > 1:
        files = [pathlib.Path(a) for a in argv[1:] if not a.startswith("--")]
    else:
        files = [PROJECT / ("%s.dc.html" % n) for n in MAC_BOARDS]
    total = 0
    for f in files:
        if not f.exists():
            print("%s: missing" % f)
            total += 1
            continue
        errs = Lint(f).run()
        total += len(errs)
        status = "ok" if not errs else "%d issue%s" % (len(errs), "" if len(errs) == 1 else "s")
        print("%-28s %s" % (f.name, status))
        for kind, ln, msg in sorted(errs, key=lambda e: e[1]):
            print("  %-6s L%-4d %s" % (kind, ln, msg))
    print("\n%d issue%s in %d file%s" % (total, "" if total == 1 else "s", len(files), "" if len(files) == 1 else "s"))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
