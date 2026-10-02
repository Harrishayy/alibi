#!/usr/bin/env python3
"""Writes docs/design/tokens/specimen.html. Colour data comes from build_tokens.py; every hex and
contrast ratio on the page is measured live from tokens.css in the browser."""
import json, os, runpy
HERE = os.path.dirname(os.path.abspath(__file__))
ns = runpy.run_path(f"{HERE}/build_tokens.py", run_name="tokens")
C, WEB, ISLAND, IOS, LA, SPRING, SPACE, RADIUS = (ns[k] for k in ("C", "WEB", "ISLAND", "IOS", "LA", "SPRING", "SPACE", "RADIUS"))
OUT = os.path.normpath(os.path.join(HERE, "..", "specimen.html"))

GROUPS = [("Surfaces", "Canvas, cards and the layers above them. Depth comes from hairlines, not shadows.", 0, 6),
          ("Ink", "Three steps of text plus the inverse for tooltips.", 6, 10),
          ("Lines", "A decorative hairline and a 3:1 boundary for controls without a fill.", 10, 12),
          ("Accent", "NVIDIA green, at most 5% of chrome. Text on a green fill is always black.", 12, 19),
          ("Green ramp", "Mascot and data only; hue held at 130.8 degrees.", 19, 26),
          ("Status", "Every status colour ships with a shape: dot, ring, square, hatch, dashed ring.", 26, 41),
          ("Verdict", "Aliases for the three verdicts.", 41, 44),
          ("Pinch", "The detective lobster's paint. Exempt from the green budget.", 44, 54),
          ("Bloom", "The one gradient: the celebration bloom.", 54, 55)]
data = [{"name": n, "kind": k, "grounds": g or [], "usage": u.split(" Contrast (")[0]} for n, d, l, k, g, u in C]
groups = [{"title": t, "lede": lede, "tokens": [r["name"] for r in data[a:b]]} for t, lede, a, b in GROUPS]
web = [{"name": n, "family": fam, "size": s, "lh": lh, "w": w, "ls": ls, "tnum": tn, "sample": smp, "usage": u}
       for n, fam, s, lh, w, ls, tn, smp, u in WEB]
apple = [{"group": g, "name": n, "family": fam, "size": s, "w": w, "ls": ls, "sample": smp}
         for g, rows in (("Mac island", ISLAND), ("iPhone", IOS), ("Live Activity", LA))
         for n, fam, s, lh, w, ls, tn, smp, u in rows]
springs = [{"name": n, "d": d, "b": b, "ms": ms, "use": use} for n, d, b, ms, _lin, use in SPRING]
space = [{"name": n, "v": v} for n, v, _ in SPACE]
radius = [{"name": n, "v": v} for n, v, _ in RADIUS]
DATA = json.dumps({"colors": data, "groups": groups, "web": web, "apple": apple, "springs": springs,
                   "space": space, "radius": radius}, ensure_ascii=False).replace("</", "<\\/")

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alibi tokens</title>
<link rel="stylesheet" href="tokens.css">
<style>
  * { box-sizing: border-box; }
  body { margin: 0; }
  .page { max-width: 1120px; margin: 0 auto; padding: var(--space-12) var(--space-6) var(--space-18); }
  header.top { display: grid; grid-template-columns: 1fr auto; gap: var(--space-6); align-items: end; padding-bottom: var(--space-8); border-bottom: 1px solid var(--hairline); }
  .mark { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-4); }
  .wordmark { font: 800 12px/1 var(--font-sans); letter-spacing: 1.6px; color: var(--ink); }
  .mark .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }
  .top h1 { margin: 0 0 var(--space-3); }
  .top .t-voice { margin: 0; color: var(--ink-2); max-width: 46ch; }
  .meta { margin-top: var(--space-4); color: var(--ink-3); }
  .seg { justify-self: start; display: inline-flex; padding: 3px; gap: 2px; border-radius: var(--radius-pill); background: var(--surface-1); box-shadow: inset 0 0 0 1px var(--hairline); }
  .seg button { appearance: none; border: 0; background: transparent; color: var(--ink-2); font: 600 12px/1 var(--font-sans); letter-spacing: 0.01em;
    padding: 8px 14px; border-radius: var(--radius-pill); cursor: pointer; transition: background-color var(--dur-small) var(--ease-out), color var(--dur-small) var(--ease-out); }
  .seg button[aria-pressed="true"] { background: var(--surface-3); color: var(--ink); }
  @media (hover: hover) and (pointer: fine) { .seg button:hover { color: var(--ink); } }
  nav.toc { display: flex; flex-wrap: wrap; gap: var(--space-2); margin: var(--space-6) 0 0; }
  nav.toc a { color: var(--ink-2); text-decoration: none; padding: 6px 12px; border-radius: var(--radius-pill); box-shadow: inset 0 0 0 1px var(--hairline); }
  nav.toc a:hover { color: var(--ink); }
  section.block { padding-top: var(--space-12); }
  section.block > h2 { margin: 0 0 var(--space-2); }
  section.block > p.lede { margin: 0 0 var(--space-6); color: var(--ink-2); max-width: 62ch; }
  .group { margin-top: var(--space-8); }
  .group h3 { margin: 0; }
  .group p { margin: var(--space-1) 0 var(--space-4); color: var(--ink-2); }

  /* colour table: name | dark | light */
  .ctable { border-radius: var(--radius-md); overflow: hidden; box-shadow: 0 0 0 1px var(--hairline); }
  .crow { display: grid; grid-template-columns: minmax(220px, 1.1fr) 1fr 1fr; }
  .crow + .crow > * { border-top: 1px solid var(--hairline); }
  .chead { background: var(--surface-1); }
  .chead > div { padding: var(--space-2) var(--space-4); color: var(--ink-2); background: var(--surface-1); }
  .cname { padding: var(--space-4); background: var(--surface-1); }
  .cname code { font: 500 13px/1.3 var(--font-mono); color: var(--ink); }
  .cname .use { margin-top: var(--space-1); color: var(--ink-2); }
  .cell { padding: var(--space-4); background: var(--surface-1); color: var(--ink); display: grid; grid-template-columns: 48px 1fr; gap: var(--space-3); align-items: start; border-left: 1px solid var(--hairline); }
  .cell .sw { width: 48px; height: 48px; border-radius: var(--radius-sm); display: grid; place-items: center; position: relative; }
  .sw.flat { box-shadow: inset 0 0 0 1px var(--hairline); }
  .sw .aa { font: 600 20px/1 var(--font-sans); letter-spacing: -0.01em; }
  .hex { font: 500 12px/1.4 var(--font-mono); color: var(--ink); }
  .ratios { margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px 10px; font: 500 12px/1.4 var(--font-mono); color: var(--ink-2); font-variant-numeric: tabular-nums; }
  .ratios .r b { font-weight: 600; color: var(--ink); }
  .verdict { margin-top: 6px; display: inline-flex; align-items: center; gap: 6px; font: 600 12px/1.3 var(--font-sans); letter-spacing: 0.01em; }
  .verdict.ok { color: var(--accent-ink); }
  .verdict.no { color: var(--warn-ink); }
  .verdict.na { color: var(--ink-3); font-weight: 500; }
  /* status shapes */
  .shape { width: 22px; height: 22px; }
  .s-dot { border-radius: 50%; }
  .s-ring { border-radius: 50%; border: 3px solid; background: transparent !important; }
  .s-square { border-radius: 5px; }
  .s-hatch { border-radius: 5px; }
  .s-dash { border-radius: 50%; border: 2px dashed; background: transparent !important; }
  .s-half { border-radius: 50%; border: 2px solid; background: linear-gradient(90deg, currentColor 50%, transparent 50%) !important; }
  .s-focus { width: 30px; height: 22px; border-radius: 6px; background: var(--surface-2) !important; outline: 2px solid; outline-offset: 2px; }
  .s-line { width: 34px; height: 22px; border-radius: 6px; border: 1px solid; background: transparent !important; }
  .s-bloom { width: 48px; height: 48px; border-radius: 50%; }

  /* type */
  .trow { display: grid; grid-template-columns: 260px 1fr; gap: var(--space-6); padding: var(--space-6) 0; border-top: 1px solid var(--hairline); align-items: baseline; }
  .trow:first-of-type { border-top: 0; }
  .tmeta code { font: 500 13px/1.3 var(--font-mono); color: var(--ink); }
  .tmeta .spec { margin-top: var(--space-1); color: var(--ink-2); font: 500 12px/1.5 var(--font-mono); font-variant-numeric: tabular-nums; }
  .tmeta .use { margin-top: var(--space-2); color: var(--ink-3); }
  .tsample { margin: 0; color: var(--ink); overflow-wrap: anywhere; }
  .t-mono.tsample { justify-self: start; display: inline-block; padding: 2px 8px; border-radius: var(--radius-xs); background: var(--surface-3); }
  .card { background: var(--surface-1); border-radius: var(--radius-md); box-shadow: 0 0 0 1px var(--hairline); padding: var(--space-6); }
  .atable { width: 100%; border-collapse: collapse; }
  .atable th { text-align: left; color: var(--ink-2); font: 600 12px/1.3 var(--font-sans); letter-spacing: 0.01em; padding: 0 var(--space-3) var(--space-3) 0; }
  .atable td { padding: var(--space-3) var(--space-3) var(--space-3) 0; border-top: 1px solid var(--hairline); vertical-align: baseline; }
  .atable td.n { font: 500 12px/1.4 var(--font-mono); color: var(--ink-2); white-space: nowrap; }
  .atable td.g { color: var(--ink-3); white-space: nowrap; }
  .island-pane { background: var(--island); color: #fff; }
  .island-pane .atable td.n, .island-pane .atable th { color: rgba(255,255,255,0.6); }
  .island-pane .atable td.g { color: rgba(255,255,255,0.6); }
  .island-pane .atable td { border-top-color: rgba(255,255,255,0.08); }

  /* spacing, radius, motion */
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-6); }
  .srow { display: grid; grid-template-columns: 90px 44px 1fr; align-items: center; gap: var(--space-3); padding: 6px 0; }
  .srow code, .mrow code { font: 500 12px/1.4 var(--font-mono); color: var(--ink); }
  .srow .v { color: var(--ink-2); font: 500 12px/1.4 var(--font-mono); font-variant-numeric: tabular-nums; }
  .bar { height: 12px; border-radius: 3px; background: var(--surface-3); }
  .radii { display: flex; flex-wrap: wrap; gap: var(--space-4); }
  .radii figure { margin: 0; text-align: center; }
  .radii .box { width: 72px; height: 72px; background: var(--surface-3); box-shadow: inset 0 0 0 1px var(--hairline-strong); }
  .radii figcaption { margin-top: var(--space-2); font: 500 12px/1.4 var(--font-mono); color: var(--ink-2); }
  .mrow { display: grid; grid-template-columns: 240px 1fr 88px; gap: var(--space-4); align-items: center; padding: var(--space-3) 0; border-top: 1px solid var(--hairline); }
  .mrow:first-child { border-top: 0; }
  .mrow .use { color: var(--ink-2); }
  .track { position: relative; height: 28px; border-radius: var(--radius-pill); background: var(--surface-2); box-shadow: inset 0 0 0 1px var(--hairline); }
  .puck { position: absolute; top: 4px; left: 4px; width: 20px; height: 20px; border-radius: 50%; background: var(--accent); }
  .track.go .puck { transform: translateX(calc(var(--run) - 28px)); }
  .btn { appearance: none; border: 0; cursor: pointer; font: 600 13px/1 var(--font-sans); padding: 10px 14px; border-radius: var(--radius-sm);
    background: var(--surface-3); color: var(--ink); transition: transform var(--dur-micro) var(--ease-out), background-color var(--dur-small) var(--ease-out); }
  .btn:active { transform: scale(0.97); }
  .btn.primary { background: var(--accent); color: var(--on-accent); }
  @media (hover: hover) and (pointer: fine) { .btn.primary:hover { background: var(--accent-hover); } }
  .btn.primary:active { background: var(--accent-press); }
  .mhead { display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); margin-bottom: var(--space-3); }

  @media (max-width: 760px) {
    .page { padding: var(--space-8) var(--space-4) var(--space-12); }
    header.top { grid-template-columns: 1fr; }
    .crow { grid-template-columns: 1fr 1fr; }
    .crow .cname { grid-column: 1 / -1; }
    .chead > div:first-child { display: none; }
    .cell { grid-template-columns: 40px 1fr; padding: var(--space-3); }
    .cell .sw { width: 40px; height: 40px; }
    .cell:nth-child(2) { border-left: 0; }
    .trow { grid-template-columns: 1fr; gap: var(--space-2); }
    .grid2 { grid-template-columns: 1fr; }
    .mrow { grid-template-columns: 1fr 72px; }
    .mrow .use { grid-column: 1 / -1; }
    .t-display.tsample { font-size: 44px; }
  }
</style>
</head>
<body>
<div class="page">
  <header class="top">
    <div>
      <div class="mark"><span class="dot" aria-hidden="true"></span><span class="wordmark">ALIBI</span></div>
      <h1 class="t-h1">Design tokens</h1>
      <p class="t-voice">One palette, one sans family, six springs. Dark comes first; light is designed, not inverted.</p>
      <p class="meta t-small">Every hex and contrast ratio below is read live from <span class="num">tokens.css</span>. Text needs 4.5:1, marks and focus rings 3:1, in both themes.</p>
    </div>
    <div class="seg" role="group" aria-label="Page theme">
      <button type="button" data-set="auto">Auto</button>
      <button type="button" data-set="dark">Dark</button>
      <button type="button" data-set="light">Light</button>
    </div>
  </header>
  <nav class="toc t-label" aria-label="Sections">
    <a href="#colour">Colour</a><a href="#type">Type</a><a href="#apple">Apple surfaces</a><a href="#space">Spacing and radius</a><a href="#motion">Motion</a>
  </nav>

  <section class="block" id="colour">
    <h2 class="t-h2">Colour</h2>
    <p class="lede t-body">Both themes side by side. Neutrals cover at least 85% of any screen; green stays under 5% outside the mascot; bad news is a dot, a word or a wash, never a red slab.</p>
    <div id="colour-groups"></div>
  </section>

  <section class="block" id="type">
    <h2 class="t-h2">Type</h2>
    <p class="lede t-body">All sans. SF Pro on Apple devices, Onest everywhere else, SF Pro Rounded for big numerals, mono only for keycaps and IDs. Every number uses tabular figures.</p>
    <div class="card" id="web-type"></div>
  </section>

  <section class="block" id="apple">
    <h2 class="t-h2">Apple surfaces</h2>
    <p class="lede t-body">Island, iPhone and Live Activity styles in points, previewed here at the same size in pixels. The island is always black.</p>
    <div class="card island-pane" id="apple-type"></div>
  </section>

  <section class="block" id="space">
    <h2 class="t-h2">Spacing and radius</h2>
    <p class="lede t-body">A 4-based ladder and one concentric radius ladder: an inner corner is the outer corner minus the padding.</p>
    <div class="grid2">
      <div class="card" id="space-list"></div>
      <div class="card"><div class="radii" id="radius-list"></div></div>
    </div>
  </section>

  <section class="block" id="motion">
    <h2 class="t-h2">Motion</h2>
    <p class="lede t-body">Six springs shared by the web, the island and the iPhone. Structure never bounces; only Pinch gets the celebrate spring. Under reduced motion every spring becomes a 150 ms ease.</p>
    <div class="card">
      <div class="mhead"><span class="t-h3">Springs</span><button class="btn primary" type="button" id="play">Play all</button></div>
      <div id="spring-list"></div>
    </div>
  </section>
</div>

<script>
const D = __DATA__;
const $ = (s, r = document) => r.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };

/* ---------- theme switch ---------- */
const root = document.documentElement;
function setTheme(t) {
  if (t === 'auto') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', t);
  document.querySelectorAll('.seg button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.set === t)));
  try { localStorage.setItem('alibi-specimen-theme', t); } catch (e) {}
}
document.querySelectorAll('.seg button').forEach(b => b.addEventListener('click', () => setTheme(b.dataset.set)));
let saved = 'auto'; try { saved = localStorage.getItem('alibi-specimen-theme') || 'auto'; } catch (e) {}
setTheme(saved);

/* ---------- colour maths (WCAG 2) ---------- */
function rgba(str) {
  const m = str.match(/rgba?\(([^)]+)\)/); if (!m) return null;
  const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
  return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
}
const lin = c => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
const lum = c => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
const over = (f, b) => ({ r: f.r * f.a + b.r * (1 - f.a), g: f.g * f.a + b.g * (1 - f.a), b: f.b * f.a + b.b * (1 - f.a), a: 1 });
function contrast(f, b) { const x = lum(over(f, b)), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
const hx = n => Math.round(n).toString(16).padStart(2, '0').toUpperCase();
const fmt = c => c.a === 1 ? `#${hx(c.r)}${hx(c.g)}${hx(c.b)}` : `#${hx(c.r)}${hx(c.g)}${hx(c.b)} · ${Math.round(c.a * 100)}%`;
function read(scope, name) {
  const p = document.createElement('span'); p.style.color = `var(--${name})`; scope.appendChild(p);
  const c = rgba(getComputedStyle(p).color); p.remove(); return c;
}

/* ---------- colour table ---------- */
const byName = Object.fromEntries(D.colors.map(c => [c.name, c]));
const SHAPES = { 'on-task': 's-dot', done: 's-dot', idle: 's-ring', partial: 's-half', partly: 's-half', phone: 's-square', 'off-task': 's-hatch',
  warn: 's-square', slacked: 's-square', absent: 's-dash', 'focus-ring': 's-focus', 'hairline-strong': 's-line', hairline: 's-line', 'green-600': 's-dot',
  'pinch-outline': 's-ring', 'pinch-lens': 's-ring', 'pinch-eye': 's-dot' };
const SHORT = { bg: 'bg', 'surface-1': 's1', 'surface-2': 's2', 'surface-3': 's3', 'accent-wash': 'wash', 'partial-wash': 'wash', 'warn-wash': 'wash' };

function swatch(cell, tok) {
  const sw = el('div', 'sw');
  const name = tok.name;
  if (tok.kind === 'text') {
    const g = tok.grounds[0] || 'surface-1';
    sw.style.background = `var(--${g})`; sw.classList.add('flat');
    const aa = el('span', 'aa', 'Aa'); aa.style.color = `var(--${name})`; sw.appendChild(aa);
  } else if (name === 'bloom') {
    sw.style.background = 'var(--bg)'; sw.classList.add('flat');
    const b = el('div', 'shape s-bloom'); b.style.background = 'radial-gradient(closest-side, var(--bloom), transparent)'; sw.appendChild(b);
  } else if (SHAPES[name]) {
    const g = name === 'pinch-eye' ? 'pinch-body' : (tok.grounds[0] || 'surface-1');
    sw.style.background = `var(--${g})`; sw.classList.add('flat');
    const s = el('div', 'shape ' + SHAPES[name]);
    s.style.color = `var(--${name})`; s.style.borderColor = `var(--${name})`; s.style.outlineColor = `var(--${name})`;
    if (SHAPES[name] === 's-hatch') s.style.background = `repeating-linear-gradient(45deg, var(--${name}) 0 2px, transparent 2px 4px)`;
    else if (!/ring|dash|line|focus|half/.test(SHAPES[name])) s.style.background = `var(--${name})`;
    sw.appendChild(s);
  } else {
    sw.style.background = `var(--${name})`;
    sw.classList.add('flat');
  }
  cell.appendChild(sw);
}

function fillCell(cell, tok) {
  swatch(cell, tok);
  const info = el('div');
  const c = read(cell, tok.name);
  info.appendChild(el('div', 'hex', fmt(c)));
  if (tok.grounds.length) {
    const need = tok.kind === 'text' ? 4.5 : 3;
    const rs = el('div', 'ratios');
    let min = Infinity;
    tok.grounds.forEach(g => {
      const r = contrast(c, read(cell, g)); min = Math.min(min, r);
      rs.appendChild(el('span', 'r', `${SHORT[g] || g} <b>${r.toFixed(2)}</b>`));
    });
    info.appendChild(rs);
    const ok = min >= need;
    info.appendChild(el('div', 'verdict ' + (ok ? 'ok' : 'no'),
      (ok ? '✓ ' : '✕ ') + (ok ? 'Passes ' : 'Fails ') + (tok.kind === 'text' ? '4.5:1 text' : '3:1 mark')));
  } else {
    info.appendChild(el('div', 'verdict na', tok.kind === 'ground' ? 'Ground' : tok.kind === 'fill' ? 'Fill · carries on-accent' : tok.kind === 'line' ? 'Decorative line' : 'Decorative'));
  }
  cell.appendChild(info);
}

const host = $('#colour-groups');
D.groups.forEach(g => {
  const wrap = el('div', 'group');
  wrap.appendChild(el('h3', 't-h3', g.title));
  wrap.appendChild(el('p', 't-small', g.lede));
  const table = el('div', 'ctable');
  const head = el('div', 'crow chead t-label');
  head.append(el('div', '', 'Token'), el('div', '', 'Dark'), el('div', '', 'Light'));
  head.children[1].setAttribute('data-theme', 'dark'); head.children[2].setAttribute('data-theme', 'light');
  table.appendChild(head);
  g.tokens.forEach(n => {
    const tok = byName[n];
    const row = el('div', 'crow');
    const nm = el('div', 'cname');
    nm.appendChild(el('code', '', '--' + n));
    nm.appendChild(el('div', 'use t-small', tok.usage));
    row.appendChild(nm);
    ['dark', 'light'].forEach(t => { const c = el('div', 'cell'); c.setAttribute('data-theme', t); row.appendChild(c); });
    table.appendChild(row);
    host.appendChild(wrap);
    wrap.appendChild(table);
    [...row.querySelectorAll('.cell')].forEach(c => fillCell(c, tok));
  });
});

/* ---------- web type ---------- */
const wt = $('#web-type');
D.web.forEach(s => {
  const row = el('div', 'trow');
  const meta = el('div', 'tmeta');
  meta.appendChild(el('code', '', '.t-' + s.name));
  const lh = s.name === 'body' ? '1.55 · dark 1.6' : s.lh;
  meta.appendChild(el('div', 'spec', `${s.size} / ${lh} · ${s.w} · ${s.ls}${s.tnum ? ' · tnum' : ''}<br>${s.family}`));
  meta.appendChild(el('div', 'use t-small', s.usage));
  const smp = el(/^h[123]$/.test(s.name) ? s.name : 'p', 't-' + s.name + ' tsample', s.sample);
  if (/^h[123]$/.test(s.name)) smp.style.margin = '0';
  row.append(meta, smp);
  wt.appendChild(row);
});

/* ---------- Apple ---------- */
const at = $('#apple-type');
const tbl = el('table', 'atable');
tbl.innerHTML = '<thead><tr><th>Style</th><th>Surface</th><th>Spec (pt)</th><th>Sample</th></tr></thead>';
const tb = el('tbody');
D.apple.forEach(s => {
  const tr = el('tr');
  const fam = s.family === 'rounded' ? 'var(--font-rounded)' : 'var(--font-sans)';
  const tn = s.family === 'rounded' ? 'font-variant-numeric:tabular-nums;' : '';
  tr.innerHTML = `<td class="n">${s.name}</td><td class="g t-small">${s.group}</td><td class="n">${s.size} · ${s.w}${s.ls !== '0px' ? ' · ' + s.ls : ''}</td>` +
    `<td><span style="font-family:${fam};font-size:${s.size}px;font-weight:${s.w};letter-spacing:${s.ls};line-height:1.2;${tn}">${s.sample}</span></td>`;
  tb.appendChild(tr);
});
tbl.appendChild(tb); at.appendChild(tbl);

/* ---------- spacing + radius ---------- */
const sl = $('#space-list');
D.space.forEach(s => {
  const r = el('div', 'srow');
  r.append(el('code', '', '--' + s.name), el('span', 'v', s.v + 'px'));
  const bar = el('div'); const b = el('div', 'bar'); b.style.width = s.v * 3 + 'px'; bar.appendChild(b); r.appendChild(bar);
  sl.appendChild(r);
});
const rl = $('#radius-list');
D.radius.forEach(s => {
  const f = el('figure'); const b = el('div', 'box'); b.style.borderRadius = `var(--${s.name})`;
  f.append(b, el('figcaption', '', `${s.name.replace('radius-', '')} · ${s.v}`)); rl.appendChild(f);
});

/* ---------- motion ---------- */
const ml = $('#spring-list');
D.springs.forEach(s => {
  const r = el('div', 'mrow');
  const left = el('div'); left.append(el('code', '', '--spring-' + s.name), el('div', 'use t-small', s.use));
  const tr = el('div', 'track'); const p = el('div', 'puck'); tr.appendChild(p);
  p.style.transition = `transform var(--spring-${s.name}-dur) var(--spring-${s.name})`;
  const btn = el('button', 'btn', 'Play'); btn.type = 'button';
  btn.addEventListener('click', () => play(tr));
  r.append(left, tr, btn); ml.appendChild(r);
});
function play(tr) {
  tr.style.setProperty('--run', tr.clientWidth + 'px');
  tr.classList.toggle('go');
}
$('#play').addEventListener('click', () => document.querySelectorAll('.track').forEach((t, i) => setTimeout(() => play(t), i * 40)));
</script>
</body>
</html>
'''
with open(OUT, "w") as f:
    f.write(HTML.replace("__DATA__", DATA))
print(OUT)
