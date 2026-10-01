#!/usr/bin/env python3
"""Lint for the next-phase artboards (docs/design/canvas/project/Next-*.dc.html).

    python3 docs/design/canvas/tools/lint_next.py              # every Next-*.dc.html
    python3 docs/design/canvas/tools/lint_next.py FILE [FILE…]

Runs every check in lint_mac.py (the .dc.html format contract, the Alibi component contract, frozen web type
sizes, colours by token only, no gradients, no uppercase eyebrows), then adds the rules the next-phase spec
(docs/NEXT_PHASE.md §5) and docs/design/system/project/{Motion,Voice}.md make checkable:

  space    padding, margin and gap sit on the 4/8 ladder (0 4 8 12 16 24 32 48 72; 1–2px nudges allowed)
  motion   transitions move transform/opacity (colour crossfades allowed); keyframes touch only transform,
           opacity and filter blur ≤ 12px; animation and transition durations come from --dur-*/--spring-*
           tokens; a rAF count-up must check prefers-reduced-motion
  type     weights 400/500/600 (800 only on the ALIBI wordmark); positive tracking only on the wordmark
           (+0.13em) and label style (+0.01em)
  voice    no "!" in copy; Pinch lines (PinchLine children and `line:` strings) are 12 words or fewer;
           status words are the four in the spec (On track, At risk, Off track, Can't see)
  bundle   every x-import names a component the shipped bundle really exports on window.Alibi
           (parsed from docs/design/system/project/components/bundle.js, not a hand-kept list)

    python3 docs/design/canvas/tools/lint_next.py --render DIR    # also render each board (Playwright)

--render needs DIR to hold the canvas runtime (support.js) and ds/alibi/components/bundle.{css,js}; each board
is copied in as _lint_<name> and opened at its $preview size. It reports what a parser can't see: runtime errors,
a fixed root whose content is clipped, a PAGE whose height at $preview width is not $preview height (±24px), and
a PAGE that scrolls sideways at 375px. The copies are deleted afterwards.
Exit status 1 when anything is found.
"""
import html
import json
import pathlib
import re
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.dont_write_bytecode = True  # importing lint_mac must not leave a __pycache__ in the repo
sys.path.insert(0, str(HERE))
import lint_mac  # noqa: E402

PROJECT = HERE.parent / "project"
BUNDLE = HERE.parents[1] / "system" / "project" / "components" / "bundle.js"
LADDER = {0, 1, 2, 4, 8, 12, 16, 24, 32, 48, 72}
MOVING = {"transform", "opacity", "color", "background-color", "filter"}
KEYFRAME_PROPS = {"transform", "opacity", "filter"}
STATUS_WORDS = {"On track", "At risk", "Off track", "Can’t see", "Can't see"}
STATUS_LIKE = re.compile(r"\b(On track|At risk|Off track|Behind|Ahead|Can.t see|Stale|Late|Due soon|Overdue|Pending)\b")


class NextLint(lint_mac.Lint):
    def run(self):
        super().run()
        if not hasattr(self, "x0"):
            return self.errors
        body = self.text[self.x0:self.x1]
        self.check_space(body)
        self.check_motion(body)
        self.check_type(body)
        self.check_voice(body)
        self.check_bundle(body)
        return self.errors

    # ---------- bundle ----------
    def check_bundle(self, body):
        names = exported()
        if names is None:
            self.err("bundle", None, "can't read the window.Alibi export block in %s" % BUNDLE)
            return
        for m in re.finditer(r'component-from-global-scope="([^"]*)"', body):
            g = m.group(1)
            if not g.startswith("Alibi.") or g.split(".", 1)[1] not in names:
                self.err("bundle", self.x0 + m.start(), "%s is not exported on window.Alibi by bundle.js" % g)

    # ---------- space ----------
    def check_space(self, body):
        for m in re.finditer(r"(?<![-\w])(padding|margin|gap|row-gap|column-gap)(-[a-z]+)?:\s*([^;\"]+)", body):
            for v in re.findall(r"(-?\d+(?:\.\d+)?)px", m.group(3)):
                if abs(float(v)) not in LADDER:
                    self.err("space", self.x0 + m.start(), "%s %spx is off the 4/8 ladder" % (m.group(1) + (m.group(2) or ""), v))

    # ---------- motion ----------
    def check_motion(self, body):
        for m in re.finditer(r"transition:\s*([^;\"]+)", body):
            for part in m.group(1).split(","):
                prop = part.strip().split()[0] if part.strip() else ""
                if prop and prop not in MOVING:
                    self.err("motion", self.x0 + m.start(), "transition on %s: move transform/opacity (colour may crossfade)" % prop)
                if prop and not re.search(r"var\(--(dur|spring)-[\w-]+\)", part):
                    self.err("motion", self.x0 + m.start(), "transition duration must be a --dur-*/--spring-* token: %s" % part.strip()[:60])
        for m in re.finditer(r"animation:\s*([^;\"]+)", body):
            if not re.search(r"var\(--(dur|spring)-[\w-]+\)", m.group(1)):
                self.err("motion", self.x0 + m.start(), "animation duration must be a --dur-*/--spring-* token: %s" % m.group(1)[:60])
        for km in re.finditer(r"@keyframes\s+([\w-]+)\s*\{((?:[^{}]*\{[^{}]*\})*)[^{}]*\}", body):
            for prop, val in re.findall(r"([\w-]+)\s*:\s*([^;}]+)", km.group(2)):
                if prop not in KEYFRAME_PROPS:
                    self.err("motion", self.x0 + km.start(), "@keyframes %s animates %s: transform/opacity only" % (km.group(1), prop))
                b = re.search(r"blur\((\d+)px\)", val)
                if b and int(b.group(1)) > 12:
                    self.err("motion", self.x0 + km.start(), "@keyframes %s blurs %spx: 12px is the ceiling" % (km.group(1), b.group(1)))
        js = self.text[self.x1:]
        if "requestAnimationFrame" in js and "prefers-reduced-motion" not in js:
            self.err("motion", self.x1, "a rAF count-up must jump to its final value under prefers-reduced-motion")

    # ---------- type ----------
    def check_type(self, body):
        for m in re.finditer(r"font-weight:\s*(\d+)", body):
            w = int(m.group(1))
            if w == 800:
                if ">ALIBI<" not in body[m.end():m.end() + 160]:
                    self.err("type", self.x0 + m.start(), "weight 800 is the ALIBI wordmark only")
            elif w not in (400, 500, 600):
                self.err("type", self.x0 + m.start(), "font-weight %d: use 400, 500 or 600" % w)
        for m in re.finditer(r"letter-spacing:\s*(-?[\d.]+)em", body):
            ls = float(m.group(1))
            if ls > 0.01 and not (abs(ls - 0.13) < 1e-6 and ">ALIBI<" in body[m.end():m.end() + 160]):
                self.err("type", self.x0 + m.start(), "tracking +%sem: only the wordmark is tracked out" % m.group(1))
            if ls < -0.025:
                self.err("type", self.x0 + m.start(), "tracking %sem is tighter than -0.025em" % m.group(1))

    # ---------- voice ----------
    def check_voice(self, body):
        markup = re.sub(r"<helmet>.*?</helmet>", "", body, flags=re.S)
        text = re.sub(r"<[^>]+>", "\n", markup)
        for m in re.finditer(r"[^\n]*!", text):
            frag = m.group(0).strip()
            if frag and "{{" not in frag:
                self.err("voice", None, "\"!\" in copy: %r" % frag[:60])
        js = self.text[self.x1:]
        strings = re.findall(r"'((?:[^'\\\n]|\\.)*)'", js)
        for s in strings:
            if "!" in s and " " in s:
                self.err("voice", None, "\"!\" in copy: %r" % s[:60])
        lines = [re.sub(r"<[^>]+>", "", m.group(1)) for m in re.finditer(
            r'component-from-global-scope="Alibi\.PinchLine"[^>]*>(.*?)</x-import>', body, re.S)]
        lines += re.findall(r"\bline:\s*'([^']*)'", js)
        for ln in lines:
            if "{{" in ln:
                continue
            n = len(ln.split())
            if n > 12:
                self.err("voice", None, "Pinch line has %d words (12 at most): %r" % (n, ln[:60]))
        for word in re.findall(r"word:\s*'([^']*)'", js):
            if STATUS_LIKE.search(word) and word not in STATUS_WORDS:
                self.err("voice", None, "status word %r: use On track, At risk, Off track or Can't see" % word)


_EXPORTED = []


def exported():
    """Component names in bundle.js's final Object.assign(Alibi, {...}) block."""
    if not _EXPORTED:
        try:
            js = BUNDLE.read_text(encoding="utf-8")
        except OSError:
            return None
        blocks = re.findall(r"Object\.assign\(Alibi,\s*\{(.*?)\}\s*\)", js, re.S)
        if not blocks:
            return None
        _EXPORTED.append(set(re.findall(r"(\w+)\s*:", blocks[-1])))
    return _EXPORTED[0]


try:
    import http.server as _hs

    class Quiet(_hs.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
except ImportError:  # pragma: no cover
    Quiet = None


PROBE = """() => {
  const root = document.querySelector('x-dc [data-theme], [data-theme]');
  if (!root) return null;
  const r = root.getBoundingClientRect();
  // page height = the bottom of the root's own children (their padding counts); clipping = any painted descendant
  let content = 0, deep = 0, who = '';
  for (const el of root.children) content = Math.max(content, el.getBoundingClientRect().bottom - r.top);
  for (const el of root.querySelectorAll('*')) {
    const st = getComputedStyle(el);
    if (st.position === 'fixed' || st.display === 'none' || st.visibility === 'hidden') continue;
    const b = el.getBoundingClientRect();
    let vis = b.bottom;  // what actually paints: cut by any clipping ancestor below the root (digit tickers etc.)
    for (let a = el.parentElement; a && a !== root; a = a.parentElement) {
      if (getComputedStyle(a).overflow !== 'visible') vis = Math.min(vis, a.getBoundingClientRect().bottom);
    }
    if (b.width && b.height && vis - r.top > deep) { deep = vis - r.top; who = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + ' ' + (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40); }
  }
  return { w: r.width, h: r.height, sw: root.scrollWidth, sh: root.scrollHeight, cw: root.clientWidth, ch: root.clientHeight,
           content: Math.round(content), deep: Math.round(deep), who, docW: document.documentElement.scrollWidth };
}"""


def render_check(f, rdir, lint):
    """Open the board at its $preview size and report what only a browser can see."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        lint.err("render", None, "playwright is not installed; skip --render or pip install playwright")
        return
    m = re.search(r"data-props='([^']*)'", lint.text)
    props = json.loads(html.unescape(m.group(1))) if m else {}
    pv = props.get("$preview") or {}
    w, h = pv.get("width", 1280), pv.get("height", 800)
    fixed = getattr(lint, "root_fixed", None)
    # one render per value of every enum tweak (state, stage, selected…), the others left at their defaults
    variants = [("", lint.text)]
    for key, spec in props.items():
        if isinstance(spec, dict) and spec.get("editor") == "enum":
            for opt in spec.get("options", []):
                if opt == spec.get("default"):
                    continue
                pat = r'("%s":\{"editor":"enum","options":\[[^\]]*\],"default":")[^"]*"' % re.escape(key)
                variants.append(("%s=%s " % (key, opt), re.sub(pat, lambda m: m.group(1) + opt + '"', lint.text, count=1)))
    copy = rdir / ("_lint_" + f.name)
    # the canvas runtime fetches beside itself, which file:// refuses: serve DIR on a free loopback port
    import functools, http.server, threading
    handler = functools.partial(Quiet, directory=str(rdir))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/%s" % (srv.server_address[1], copy.name)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            for tag, text in variants:
              copy.write_text(text, encoding="utf-8")
              for width, height in ((w, h), (375, 812)) if not fixed else ((w, h),):
                  pg = b.new_page(viewport={"width": width, "height": height})
                  errs = []
                  pg.on("pageerror", lambda e: errs.append(str(e)))
                  pg.on("console", lambda msg: errs.append(msg.text) if msg.type == "error" else None)
                  pg.goto(url)
                  pg.wait_for_timeout(2500)
                  r = pg.evaluate(PROBE)
                  for e in sorted(set(errs)):
                      lint.err("render", None, "%sat %dpx: %s" % (tag, width, e[:120]))
                  if r is None:
                      lint.err("render", None, "%sat %dpx: no [data-theme] root rendered" % (tag, width))
                      continue
                  if fixed and width == w:
                      if r["deep"] > h + 1:
                          lint.err("render", None, "%sfixed root clips its content: %dpx tall in a %dpx frame (lowest: %s)" % (tag, r["deep"], h, r["who"]))
                      if r["sw"] > r["cw"] + 1:
                          lint.err("render", None, "%sfixed root clips sideways: %dpx wide in %dpx" % (tag, r["sw"], r["cw"]))
                  elif not fixed and width == w and not tag and abs(r["content"] - h) > 24:
                      lint.err("render", None, "PAGE is %dpx tall at %dpx but $preview height is %d" % (r["content"], w, h))
                  elif not fixed and width == 375 and r["docW"] > 375:
                      lint.err("render", None, "%sPAGE scrolls sideways at 375px (%dpx wide)" % (tag, r["docW"]))
                  pg.close()
            b.close()
    finally:
        srv.shutdown()
        srv.server_close()
        copy.unlink(missing_ok=True)


def main(argv):
    args = argv[1:]
    rdir = None
    if "--render" in args:
        i = args.index("--render")
        if i + 1 >= len(args):
            print("--render needs DIR (holding support.js and ds/alibi/components/)")
            return 2
        rdir = pathlib.Path(args[i + 1])
        del args[i:i + 2]
        if not (rdir / "support.js").exists() or not (rdir / "ds/alibi/components/bundle.js").exists():
            print("%s needs support.js and ds/alibi/components/bundle.{css,js}" % rdir)
            return 2
    files = [pathlib.Path(a) for a in args if not a.startswith("--")] or sorted(PROJECT.glob("Next-*.dc.html"))
    total = 0
    for f in files:
        if not f.exists():
            print("%s: missing" % f)
            total += 1
            continue
        lint = NextLint(f)
        errs = lint.run()
        if rdir is not None:
            render_check(f, rdir, lint)
            errs = lint.errors
        total += len(errs)
        print("%-30s %s" % (f.name, "ok" if not errs else "%d issue%s" % (len(errs), "" if len(errs) == 1 else "s")))
        for kind, ln, msg in sorted(errs, key=lambda e: e[1]):
            print("  %-6s L%-4d %s" % (kind, ln, msg))
    print("\n%d issue%s in %d file%s" % (total, "" if total == 1 else "s", len(files), "" if len(files) == 1 else "s"))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
