/* card.js: window.AlibiCard, the one renderer for backend cards (alibi/cards.py). The backend owns every string;
   this file only lays them out, so the toast, the agent card and the Night review card read the same.
   ok(card)            true only for v == 1 with a string title (anything else: the caller shows `text`)
   html(card, {compact, actions})   compact = the toast caps (2 groups, 6 items, 6 bars); page cards show everything
   bind(root, onAction) one click handler for the card's own actions (API rows only; alerts use alert.actions)
   Classic script, loaded before core.js. Every string is escaped; a malformed part is skipped, never rendered. */
(function () {
  "use strict";
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const TONES = {accent: 1, partial: 1, warn: 1, neutral: 1};
  const tone = t => TONES[t] ? t : "neutral";
  const str = v => typeof v === "string" && v.trim() ? v.trim() : "";
  const num = v => typeof v === "number" && isFinite(v);
  const obj = v => v && typeof v === "object" && !Array.isArray(v);
  // 1.5px stroke on a 24 grid, the same language as week.js WK_ICONS. Unknown names render no icon.
  const P = {
    check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    half: '<circle cx="12" cy="12" r="7.5"/><path d="M12 4.5a7.5 7.5 0 0 1 0 15z" fill="currentColor"/>',
    x: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    phone: '<rect x="7" y="3" width="10" height="18" rx="2.5"/><path d="M11 18h2"/>',
    run: '<circle cx="15.5" cy="4.5" r="1.75"/><path d="M13.5 7.5L10.5 13M13.2 8.4l2.8 1.8 2.5-.6M12.9 8.2l-3 .3-2.2 2M10.5 13l3.4 2-.6 4.5M10.5 13l-1.3 3.4H5.5"/>',
    calendar: '<rect x="4" y="5.5" width="16" height="14.5" rx="2.5"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
    camera: '<path d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2.4l1.3-2h5.6l1.3 2h2.4A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5z"/><circle cx="12" cy="12.75" r="3.25"/>',
    laptop: '<rect x="5" y="5.5" width="14" height="10" rx="1.5"/><path d="M3 18.5h18"/>',
    heart: '<path d="M12 19.5s-7.5-4.4-7.5-10A4.25 4.25 0 0 1 12 6.9a4.25 4.25 0 0 1 7.5 2.6c0 5.6-7.5 10-7.5 10z"/>',
    moon: '<path d="M19.5 14.6A7.75 7.75 0 1 1 9.4 4.5a6.25 6.25 0 0 0 10.1 10.1z"/>',
    flag: '<path d="M5.5 21V4.5M5.5 4.5h11.5l-2.25 4 2.25 4H5.5"/>',
    cpu: '<rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M10 3.5V7M14 3.5V7M10 17v3.5M14 17v3.5M3.5 10H7M3.5 14H7M17 10h3.5M17 14h3.5"/>',
    list: '<path d="M9.5 7H20M9.5 12H20M9.5 17H20"/><circle cx="5" cy="7" r=".9" fill="currentColor"/><circle cx="5" cy="12" r=".9" fill="currentColor"/><circle cx="5" cy="17" r=".9" fill="currentColor"/>',
    eye: '<path d="M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12s-3.5 6.5-9.5 6.5S2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
  };
  const SRC = {nemotron: "cpu", agent: "cpu", rules: "list", strava: "run", apple_vision: "eye", nvidia_vlm: "eye", health: "heart", calendar: "calendar"};
  const icon = (name, size = 12) => P[name] ? `<svg class="cd-ic" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${P[name]}</svg>` : "";

  function ok(card) { return !!(obj(card) && card.v === 1 && typeof card.title === "string" && card.title.trim()); }

  // A chip: {text, tone, icon?}. `i` drives the entrance stagger (40 ms a step, capped at 6).
  function chip(c, i) {
    if (!obj(c) || !str(c.text)) return "";
    return `<span class="cd-chip cd--${tone(c.tone)}" style="--i:${Math.min(i, 5)}">${icon(c.icon)}<span>${esc(str(c.text))}</span></span>`;
  }
  function chips(list, cap, start = 0) {
    const ok_ = (Array.isArray(list) ? list : []).filter(c => obj(c) && str(c.text));
    const shown = ok_.slice(0, cap).map((c, i) => chip(c, start + i)).join("");
    const more = ok_.length - Math.min(ok_.length, cap);
    return shown ? shown + (more > 0 ? `<span class="cd-chip cd--neutral cd-chip--more" style="--i:${Math.min(start + cap, 5)}">+${more}</span>` : "") : "";
  }
  // A bar: {label, value, min, max, tone, caption}. Length = |value| / max(|min|, |max|), from the leading edge.
  function bar(b, i) {
    if (!obj(b) || !str(b.label) || !num(b.value) || !num(b.min) || !num(b.max) || !(b.min < b.max)) return "";
    const span = Math.max(Math.abs(b.min), Math.abs(b.max)) || 1;
    const v = Math.min(b.max, Math.max(b.min, b.value)), f = Math.min(1, Math.abs(v) / span);
    const cap = str(b.caption), lab = str(b.label);
    return `<div class="cd-bar cd--${tone(b.tone)}" role="img" aria-label="${esc(lab)}: ${esc(cap || String(v))}" style="--i:${Math.min(i, 5)}">`
      + `<span class="cd-bar__l">${esc(lab)}</span><span class="cd-bar__t"><i style="--f:${f.toFixed(3)}"></i></span><span class="cd-bar__c">${esc(cap)}</span></div>`;
  }
  function group(g, cap, start) {
    if (!obj(g)) return "";
    const label = str(g.label);
    let body = "";
    if (Array.isArray(g.items)) {
      const c = chips(g.items, cap, start);
      if (c) body = `<div class="cd-chips">${c}</div>`;
    } else if (Array.isArray(g.bars)) {
      const rows = g.bars.map((b, i) => bar(b, start + i)).filter(Boolean);
      if (rows.length) {
        const more = rows.length - Math.min(rows.length, cap);
        body = `<div class="cd-bars">${rows.slice(0, cap).join("")}</div>${more > 0 ? `<span class="cd-more">+${more} more</span>` : ""}`;
      }
    }
    return body ? `<div class="cd-group">${label ? `<p class="cd-glabel">${esc(label)}</p>` : ""}${body}</div>` : "";
  }
  function stat(s) {
    if (!obj(s) || !str(s.value)) return "";
    return `<div class="cd-stat cd--${tone(s.tone)}"><span class="cd-stat__v">${esc(str(s.value))}${str(s.unit) ? `<small${str(s.unit) === "%" ? ' class="is-pct"' : ""}>${esc(str(s.unit))}</small>` : ""}</span>`
      + `${str(s.caption) ? `<span class="cd-stat__c">${esc(str(s.caption))}</span>` : ""}</div>`;
  }
  function prov(p) {
    if (!obj(p) || !str(p.text)) return "";
    const d = str(p.detail);
    return `<p class="cd-prov">${icon(SRC[p.source])}<span class="cd-prov__t">${esc(str(p.text))}</span>${d ? `<span class="cd-prov__d"> · ${esc(d)}</span>` : ""}</p>`;
  }
  function acts(list) {
    const a = (Array.isArray(list) ? list : []).filter(x => obj(x) && str(x.label)).slice(0, 3);
    if (!a.length) return "";
    return `<div class="cd-acts">${a.map((x, i) => `<button type="button" class="al-btn al-btn--sm ${i === 0 && (x.post || x.say || x.url) ? "al-btn--primary" : "al-btn--quiet"}" data-cd-act="${i}">${esc(str(x.label))}</button>`).join("")}</div>`;
  }

  // compact: the toast (title as <p>, 2 groups, 6 items, 6 bars, no card actions). Otherwise a page card (<h3>, all).
  function html(card, opts) {
    if (!ok(card)) return "";
    const o = opts || {}, compact = !!o.compact;
    const capG = compact ? 2 : 3, capI = compact ? 6 : 8, capC = 6;
    const title = esc(str(card.title)), sub = str(card.subtitle);
    const head = `<div class="cd-head"><div class="cd-main">${compact ? `<p class="cd-title">${title}</p>` : `<h3 class="cd-title">${title}</h3>`}`
      + `${sub ? `<p class="cd-sub">${esc(sub)}</p>` : ""}</div>${stat(card.stat)}</div>`;
    const top = chips(card.chips, capC, 0);
    let n = top ? Math.min((card.chips || []).length, capC) : 0;
    const groups = (Array.isArray(card.groups) ? card.groups : []).slice(0, capG).map(g => {
      const out = group(g, capI, n);
      if (out) n += 1;
      return out;
    }).join("");
    const actions = !compact && o.actions !== false ? acts(card.actions) : "";
    const data = actions ? ` data-cd-acts="${esc(JSON.stringify(card.actions.filter(x => obj(x) && str(x.label)).slice(0, 3)))}"` : "";
    return `<div class="cd cd--${tone(card.tone)}${compact ? " cd--compact" : " cd--page"}" data-kind="${esc(str(card.kind))}"${data}>`
      + `<div class="cd-body">${head}${prov(card.provenance)}${top ? `<div class="cd-chips cd-chips--top">${top}</div>` : ""}${groups}</div>` + actions + `</div>`;
  }

  // One listener per root; it survives re-renders because the actions ride on the card element itself.
  function bind(root, onAction) {
    if (!root || root.__cdBound) return;
    root.__cdBound = true;
    root.addEventListener("click", e => {
      const b = e.target.closest("[data-cd-act]"); if (!b || !root.contains(b)) return;
      const cd = b.closest(".cd"); let list = [];
      try { list = JSON.parse(cd && cd.dataset.cdActs || "[]"); } catch {}
      const x = list[+b.dataset.cdAct]; if (x && typeof onAction === "function") onAction(x, b, cd);
    });
  }

  // Entrance: chips and bars rise in with a 40 ms stagger, once per new card. Reduced motion is handled in card.css.
  function enter(root) {
    const cd = root && root.querySelector(".cd"); if (!cd) return;
    cd.classList.remove("cd-enter"); void cd.offsetWidth; cd.classList.add("cd-enter");
    setTimeout(() => cd.classList.remove("cd-enter"), 1400);
  }

  window.AlibiCard = {ok, html, bind, enter};
})();
