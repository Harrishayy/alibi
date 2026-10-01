/* icons.js: window.AlibiIcons, the dashboard's icon set and status marks as SVG strings (no React).
   Same paths as Alibi.Icon in docs/design/system/project/components (1.5px stroke on a 24 grid, round caps, currentColor).
   AlibiIcons.svg(name, size)      → icon markup (aria-hidden); unknown names return "".
   AlibiIcons.dot(label, size)     → StatusDot markup: ● on_task, ○ idle, ■ phone, hatched disc off_task, dashed ring absent.
   AlibiIcons.verdict(v, size)     → the VerdictPill glyph: ✓ done, ◐ partial, ✕ slacked.
   Classic script, loaded first so every area script can use it. */
(function () {
  const P = (d) => ["path", {d}];
  const ICONS = {
    play: [P("M8 5.6v12.8a1 1 0 0 0 1.53.85l10.2-6.4a1 1 0 0 0 0-1.7L9.53 4.75A1 1 0 0 0 8 5.6z")],
    pause: [["rect", {x: 6.5, y: 5, width: 3.5, height: 14, rx: 1}], ["rect", {x: 14, y: 5, width: 3.5, height: 14, rx: 1}]],
    stop: [["rect", {x: 6, y: 6, width: 12, height: 12, rx: 2.5}]],
    plus: [P("M12 5v14M5 12h14")],
    check: [P("M5 12.5l4.5 4.5L19 7.5")],
    x: [P("M6.5 6.5l11 11M17.5 6.5l-11 11")],
    camera: [P("M4 8.5A1.5 1.5 0 0 1 5.5 7h2.4l1.3-2h5.6l1.3 2h2.4A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5z"), ["circle", {cx: 12, cy: 12.75, r: 3.25}]],
    laptop: [["rect", {x: 5, y: 5.5, width: 14, height: 10, rx: 1.5}], P("M3 18.5h18")],
    phone: [["rect", {x: 7, y: 3, width: 10, height: 18, rx: 2.5}], P("M11 18h2")],
    run: [["circle", {cx: 15.5, cy: 4.5, r: 1.75}], P("M13.5 7.5L10.5 13M13.2 8.4l2.8 1.8 2.5-.6M12.9 8.2l-3 .3-2.2 2M10.5 13l3.4 2-.6 4.5M10.5 13l-1.3 3.4H5.5")],
    heart: [P("M12 19.5s-7.5-4.4-7.5-10A4.25 4.25 0 0 1 12 6.9a4.25 4.25 0 0 1 7.5 2.6c0 5.6-7.5 10-7.5 10z")],
    moon: [P("M19.5 14.6A7.75 7.75 0 1 1 9.4 4.5a6.25 6.25 0 0 0 10.1 10.1z")],
    calendar: [["rect", {x: 4, y: 5.5, width: 16, height: 14.5, rx: 2.5}], P("M4 10h16M8.5 3.5v4M15.5 3.5v4")],
    settings: [P("M10.07 5.27L10.72 2.89L13.28 2.89L13.93 5.27A7 7 0 0 1 15.39 5.88L17.54 4.65L19.35 6.46L18.12 8.61A7 7 0 0 1 18.73 10.07L21.11 10.72L21.11 13.28L18.73 13.93A7 7 0 0 1 18.12 15.39L19.35 17.54L17.54 19.35L15.39 18.12A7 7 0 0 1 13.93 18.73L13.28 21.11L10.72 21.11L10.07 18.73A7 7 0 0 1 8.61 18.12L6.46 19.35L4.65 17.54L5.88 15.39A7 7 0 0 1 5.27 13.93L2.89 13.28L2.89 10.72L5.27 10.07A7 7 0 0 1 5.88 8.61L4.65 6.46L6.46 4.65L8.61 5.88A7 7 0 0 1 10.07 5.27Z"), ["circle", {cx: 12, cy: 12, r: 3}]],
    lens: [["circle", {cx: 10.5, cy: 10.5, r: 6}], P("M15 15l5 5")],
    cup: [P("M5 9.5h11v4A5.5 5.5 0 0 1 10.5 19h0A5.5 5.5 0 0 1 5 13.5z"), P("M16 11h1.25a2.5 2.5 0 0 1 0 5H15.4M8.5 3.5v3M12.5 3.5v3")],
    "arrow-up": [P("M12 19V5M6 11l6-6 6 6")],
    "arrow-right": [P("M5 12h14M13 6l6 6-6 6")],
    "chevron-right": [P("M9.5 6l6 6-6 6")],
    "chevron-down": [P("M6 9.5l6 6 6-6")],
    clock: [["circle", {cx: 12, cy: 12, r: 8.5}], P("M12 7.5V12l3 2")],
    flag: [P("M5.5 21V4.5M5.5 4.5h11.5l-2.25 4 2.25 4H5.5")],
    eye: [P("M2.75 12S6.25 5.75 12 5.75 21.25 12 21.25 12 17.75 18.25 12 18.25 2.75 12 2.75 12z"), ["circle", {cx: 12, cy: 12, r: 3}]],
    sparkle: [P("M12 3.5c.75 4.75 2.75 7.25 7.5 8.5-4.75 1.25-6.75 3.75-7.5 8.5-.75-4.75-2.75-7.25-7.5-8.5 4.75-1.25 6.75-3.75 7.5-8.5z")],
    claw: [P("M7.5 20.5C4.8 17.8 4.6 13.2 6.9 9.6 8.6 7 11.1 4.9 14.2 3.5c.2 2.6-.4 5.1-1.7 7.2 2.5-1 5.4-1.1 8.3-.3-1.3 3.5-4.4 5.9-8 6.5-1.4.3-2.4 1.6-2.7 3.6z"), P("M7.5 20.5h2.6")],
    undo: [P("M9 13.5L4 8.5l5-5"), P("M4 8.5h10.25a5.75 5.75 0 0 1 0 11.5H10")],
    film: [["rect", {x: 4, y: 4, width: 16, height: 16, rx: 2.5}], P("M8.5 4v16M15.5 4v16M4 9h4.5M4 15h4.5M15.5 9H20M15.5 15H20")],
  };
  const attrs = o => Object.entries(o).map(([k, v]) => `${k}="${v}"`).join(" ");
  const el = ([tag, o]) => `<${tag} ${attrs(o)}/>`;

  function svg(name, size = 20, cls = "") {
    const parts = ICONS[name]; if (!parts) return "";
    return `<svg class="al-icon${cls ? " " + cls : ""}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${parts.map(el).join("")}</svg>`;
  }

  const DOT = {on_task: ["on-task", "On task"], idle: ["idle", "Idle"], phone: ["phone", "Phone"], off_task: ["off-task", "Off task"], absent: ["absent", "Away"]};
  let uid = 0;
  const n = v => Math.round(v * 100) / 100;
  function mark(label, s) {
    const c = s / 2, r = s * 0.4;
    if (label === "on_task") return `<circle cx="${c}" cy="${c}" r="${n(r)}" fill="currentColor"/>`;
    if (label === "idle") return `<circle cx="${c}" cy="${c}" r="${n(r - 1)}" fill="none" stroke="currentColor" stroke-width="2"/>`;
    if (label === "phone") { const side = s * 0.76, o = (s - side) / 2; return `<rect x="${n(o)}" y="${n(o)}" width="${n(side)}" height="${n(side)}" rx="${n(s * 0.2)}" fill="currentColor"/>`; }
    if (label === "off_task") {
      const id = "aldh" + (++uid), step = Math.max(2.5, s / 4.5); let d = "";
      for (let k = -s; k <= s; k += step) d += `M${n(k)} ${s}L${n(k + s)} 0`;
      return `<clipPath id="${id}"><circle cx="${c}" cy="${c}" r="${n(r)}"/></clipPath><circle cx="${c}" cy="${c}" r="${n(r)}" fill="currentColor" opacity="0.28"/>` +
        `<path d="${d}" stroke="currentColor" stroke-width="${n(Math.max(1, s / 10))}" clip-path="url(#${id})"/><circle cx="${c}" cy="${c}" r="${n(r - 0.6)}" fill="none" stroke="currentColor" stroke-width="1.2"/>`;
    }
    const rr = r - 0.75, circ = 2 * Math.PI * rr, dash = circ / Math.max(6, Math.round(s / 1.6));
    return `<circle cx="${c}" cy="${c}" r="${n(rr)}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="${n(dash * 0.55)} ${n(dash * 0.45)}"/>`;
  }
  // StatusDot: colour plus shape. With text=true the word follows the mark; otherwise the mark carries an aria-label.
  function dot(label, size = 12, text = false) {
    const k = DOT[label] ? label : "absent", [cls, word] = DOT[k];
    const m = `<svg class="al-dot__mark" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" aria-hidden="true" focusable="false">${mark(k, size)}</svg>`;
    const c = `al-dot al-dot--${cls}${size < 16 ? " is-small" : ""}`;
    return text ? `<span class="${c}">${m}<span class="al-dot__word">${word}</span></span>` : `<span class="${c}" role="img" aria-label="${word}">${m}</span>`;
  }
  function verdict(v, size = 14) {
    const o = `width="${size}" height="${size}" viewBox="0 0 16 16" aria-hidden="true" focusable="false" class="al-verdict__glyph"`;
    if (v === "done") return `<svg ${o}><path d="M3.5 8.4l3 3 6-6.4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    if (v === "partial") return `<svg ${o}><circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" stroke-width="1.75"/><path d="M8 2.5a5.5 5.5 0 0 1 0 11z" fill="currentColor"/></svg>`;
    return `<svg ${o}><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`;
  }
  const VWORD = {done: "Done", partial: "Partly", slacked: "Slacked"};
  // VerdictPill: glyph and word, always; ratio (0..1) optional.
  function pill(v, ratio) {
    const k = VWORD[v] ? v : "partial", r = ratio == null || isNaN(ratio) ? null : Math.round(ratio * 100);
    return `<span class="al-verdict al-verdict--${k}" role="img" aria-label="Verdict: ${VWORD[k].toLowerCase()}${r == null ? "" : ", " + r + "%"}">${verdict(k)}<span class="al-verdict__word">${VWORD[k]}</span>${r == null ? "" : `<span class="al-verdict__ratio">${r}%</span>`}</span>`;
  }
  window.AlibiIcons = {svg, dot, verdict, pill, names: Object.keys(ICONS)};
})();
