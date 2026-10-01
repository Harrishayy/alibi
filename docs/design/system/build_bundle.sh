#!/usr/bin/env bash
# Build the Alibi design-system component bundle.
#
#   bash docs/design/system/build_bundle.sh            # uses docs/design/pinch/pinch.js
#   PINCH_JS=/path/to/engine.js bash .../build_bundle.sh  # any other AlibiPinch engine
#
# Writes (under docs/design/system/project/components/):
#   bundle.js   line 1 @ds-bundle header, then the Pinch engine, then src/components.js (window.Alibi)
#   bundle.css  the token block from docs/design/tokens/tokens.css (no @import), then src/components.css
# and regenerates docs/design/system/preview-harness.html (every preview.html, dark then light).
# Fails on anything a consumer could not inline: "</script", "<!--", an import statement, "</style".
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESIGN="$(cd "$HERE/.." && pwd)"
COMP="$HERE/project/components"
SRC_JS="$COMP/src/components.js"
SRC_CSS="$COMP/src/components.css"
TOKENS="$DESIGN/tokens/tokens.css"
PINCH="${PINCH_JS:-$DESIGN/pinch/pinch.js}"

# Display order = the component catalogue order on the artifact page.
COMPONENTS=(Button IconButton Icon Chip Kbd Composer StatusDot VerdictPill StreakBadge SampleStrip Meter RingTimer Stat Pinch PinchLine Card Toast NotchIsland)

for f in "$SRC_JS" "$SRC_CSS" "$TOKENS"; do
  [[ -f "$f" ]] || { echo "build_bundle: missing $f" >&2; exit 1; }
done

header_list=""
for c in "${COMPONENTS[@]}"; do header_list+="{\"name\":\"$c\"},"; done
header_list="${header_list%,}"

tmpdir="$(mktemp -d)"; tmp_js="$tmpdir/bundle.cjs"; tmp_css="$tmpdir/bundle.css"
trap 'rm -rf "$tmpdir"' EXIT

{
  printf '/* @ds-bundle: {"format":4,"namespace":"Alibi","components":[%s]} */\n' "$header_list"
  if [[ -f "$PINCH" ]]; then
    printf '/* ---- Pinch engine: %s ---- */\n' "$(basename "$PINCH")"
    cat "$PINCH"
    printf '\n;\n'
  else
    printf '/* Pinch engine not found at build time: Alibi.Pinch draws its still placeholder. */\n'
    echo "build_bundle: warning: no Pinch engine at $PINCH (Alibi.Pinch will show its placeholder)" >&2
  fi
  printf '/* ---- Alibi components ---- */\n'
  cat "$SRC_JS"
} > "$tmp_js"

{
  # The Onest fallback (for viewers without SF Pro) must stay the stylesheet's first rule: @import is ignored after any other rule.
  grep '^@import' "$TOKENS"
  printf '/* Alibi components: bundle.css. Token block copied from docs/design/tokens/tokens.css, then the component styles. */\n\n'
  grep -v '^@import' "$TOKENS"
  printf '\n'
  cat "$SRC_CSS"
} > "$tmp_css"

fail=0
check() { # file pattern message
  if rg -n -i --fixed-strings "$2" "$1" >/dev/null; then
    echo "build_bundle: forbidden \"$2\" in $(basename "$3"):" >&2
    rg -n -i --fixed-strings "$2" "$1" | head -5 >&2
    fail=1
  fi
}
check "$tmp_js" '</script' bundle.js
check "$tmp_js" '<!--' bundle.js
check "$tmp_css" '</style' bundle.css
if rg -n '^\s*import[\s{*"'"'"']|\bimport\s*\(|^\s*export\s' "$tmp_js" >/dev/null; then
  echo "build_bundle: an import/export statement in bundle.js:" >&2
  rg -n '^\s*import[\s{*"'"'"']|\bimport\s*\(|^\s*export\s' "$tmp_js" | head -5 >&2
  fail=1
fi
if command -v node >/dev/null 2>&1; then
  node --check "$tmp_js" || { echo "build_bundle: bundle.js does not parse" >&2; fail=1; }
fi
[[ $fail -eq 0 ]] || exit 1

cp "$tmp_js" "$COMP/bundle.js"
cp "$tmp_css" "$COMP/bundle.css"
echo "build_bundle: wrote $COMP/bundle.js ($(wc -c < "$COMP/bundle.js" | tr -d ' ') bytes, ${#COMPONENTS[@]} components)"
echo "build_bundle: wrote $COMP/bundle.css ($(wc -c < "$COMP/bundle.css" | tr -d ' ') bytes)"

# ---- preview harness: every preview.html in a srcdoc frame, preloaded like the artifact's preview frame ----
python3 - "$HERE" <<'PY'
import html, pathlib, re, sys
here = pathlib.Path(sys.argv[1])
comp = here / "project" / "components"
order = ["Cover", "Button", "IconButton", "Icon", "Chip", "Kbd", "Composer", "StatusDot", "VerdictPill", "StreakBadge",
         "SampleStrip", "Meter", "RingTimer", "Stat", "Pinch", "PinchLine", "Card", "Toast", "NotchIsland"]
found = sorted(p.parent.name for p in comp.glob("*/preview.html"))
names = [n for n in order if n in found] + [n for n in found if n not in order]
REACT = "https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js"
REACT_DOM = "https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js"

def frame(name, theme):
    text = (comp / name / "preview.html").read_text()
    first, _, rest = text.partition("\n")
    m = re.search(r"height=(\d+)", first)
    g = re.search(r'group="([^"]+)"', first)
    height = int(m.group(1)) if m else 120
    pre = ("<script>window.addEventListener('error',function(e){parent.console.error('[%s/%s] '+e.message)});</script>"
           '<link rel="stylesheet" href="project/components/bundle.css">'
           '<script src="%s"></script><script src="%s"></script>'
           '<script src="project/components/bundle.js"></script>') % (name, theme, REACT, REACT_DOM)
    doc = re.sub(r"<html([^>]*)>", lambda mm: '<html%s data-theme="%s">' % (mm.group(1), theme), rest, count=1)
    doc = re.sub(r"<head>", "<head>" + pre, doc, count=1)
    return height, (g.group(1) if g else ""), doc

rows = []
for n in names:
    cells = []
    for theme in ("dark", "light"):
        height, group, doc = frame(n, theme)
        cells.append('<iframe title="%s, %s" data-h="%d" style="height:%dpx" srcdoc="%s"></iframe>'
                     % (n, theme, height, height, html.escape(doc, quote=True)))
    rows.append('<section class="row"><h2>%s <span>%s</span></h2><div class="pair%s">%s</div></section>'
                % (n, html.escape(group), " wide" if n == "Cover" else "", "".join(cells)))

page = """<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alibi previews</title>
<link rel="stylesheet" href="project/components/bundle.css">
<style>
  body { padding: var(--space-6); }
  header { display: flex; gap: var(--space-6); align-items: baseline; margin-bottom: var(--space-6); }
  header h1 { margin: 0; font-size: 22px; font-weight: 600; letter-spacing: -0.015em; }
  header p, .cols span { margin: 0; color: var(--ink-2); font-size: 13px; }
  .cols, .pair { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
  .cols { margin-bottom: var(--space-2); }
  .row { margin-bottom: var(--space-8); }
  .row h2 { margin: 0 0 var(--space-2); font-size: 17px; font-weight: 600; letter-spacing: -0.01em; }
  .row h2 span { color: var(--ink-3); font-weight: 500; font-size: 13px; margin-left: var(--space-2); }
  .pair.wide { grid-template-columns: 960px; }
  iframe { width: 100%; border: 1px solid var(--hairline); border-radius: var(--radius-sm); display: block; background: var(--bg); }
</style>
</head>
<body>
<header><h1>Alibi components</h1><p>Each preview.html in the artifact's preview frame: tokens, bundle.css, React 18.3.1, bundle.js. Dark left, light right.</p></header>
<div class="cols"><span>dark</span><span>light</span></div>
@@ROWS@@
<script>
  function fit(f) {
    try {
      var d = f.contentDocument; if (!d || !d.documentElement) return;
      var h = Math.max(Number(f.dataset.h) || 0, d.documentElement.scrollHeight);
      f.style.height = h + 'px';
    } catch (e) { console.error('fit: ' + e.message); }
  }
  document.querySelectorAll('iframe').forEach(function (f) {
    f.addEventListener('load', function () { fit(f); setTimeout(function () { fit(f); }, 400); });
  });
</script>
</body>
</html>
""".replace("@@ROWS@@", "\n".join(rows))
(here / "preview-harness.html").write_text(page)
print("build_bundle: wrote %s (%d previews)" % (here / "preview-harness.html", len(names)))
PY
