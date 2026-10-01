/* moments.js: window.AlibiMoments, the web hook contract (docs/design/IMPLEMENTATION.md Appendix D). Signatures are frozen.
   Classic script, loaded after pinch.js and before core.js, so the area scripts can call it unconditionally.
   Uses pinch-wire.js (window.AlibiPinchWire), confetti.js (window.AlibiConfetti) and css/moments.css; if the page
   doesn't link them yet, they are added at DOMContentLoaded (after every <script> tag has been parsed, so never twice).

   Pinch events (LANES.md): the server pinch block is {mood, event, seq, age_s, line}. An event plays once, when seq is
   newer than the last one this page saw and age_s < 15. The first poll only records seq, so a reload never replays.

   Verdict markup the reveal looks for inside cardEl (any of the selectors; missing parts are skipped):
     card    [data-m=card] | .al-verdict-card | .vpanel | first child      pill     [data-m=pill] | .al-verdict | .vpill
     number  [data-m=pct] | #vnum | .al-stat__value                       meter    [data-m=meter] | .al-meter__fill | .vmeter .f
     frames  [data-m=frames] > * | .vsheet img | .al-strip__cell           later    [data-m=line] | [data-m=actions] | .vsum | .vwhy | .vacts
   URL: ?moment=verdict replays the reveal once on load; ?moment=big also forces the big celebration. */
(function () {
  "use strict";
  const Q = new URLSearchParams(location.search);
  const MOMENT = Q.get("moment") || "";
  const RM = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const W = () => window.AlibiPinchWire;
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const ms = (n, d) => parseFloat(css(n)) || d;
  const ease = n => css(n) || "ease-out";
  const escH = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const VERDICT_CLIP = {done: "celebrate", partial: "partial", slacked: "supportive"};
  const VERDICT_EVENTS = new Set(Object.values(VERDICT_CLIP));

  /* ---------- dependencies: link the lane's files if the shell hasn't yet ---------- */
  function linkDeps() {
    const has = (sel) => !!document.querySelector(sel);
    if (!has('link[href*="/css/moments.css"]')) {
      const l = document.createElement("link"); l.rel = "stylesheet"; l.href = "/web/css/moments.css"; document.head.appendChild(l);
    }
    for (const f of ["pinch-wire", "confetti"]) if (!has(`script[src*="/js/${f}.js"]`)) {
      const s = document.createElement("script"); s.src = `/web/js/${f}.js`; s.async = false; document.body.appendChild(s);
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", linkDeps); else linkDeps();

  /* ---------- Pinch event bookkeeping ---------- */
  let booted = false, lastSeq = 0, reveal = null, momentDone = false, pendingFlip = null;

  function playEvent(p, s) {
    const ev = p.event;
    if (!ev || !W()) return;
    if (VERDICT_EVENTS.has(ev)) {
      if (reveal && performance.now() - reveal.t0 < 4000) return;   // the reveal plays it on its own beat
      return W().play(ev, {force: true});
    }
    if (ev === "sideeye") return W().play("sideeye");                 // the engine chains nudge with force
    return W().play(ev);
  }

  /* ---------- verdict reveal (Motion.md, signature moment 1) ---------- */
  const pick = (root, sels) => { for (const s of sels) { const el = root.querySelector(s); if (el) return el; } return null; };
  const pickAll = (root, sels) => { for (const s of sels) { const els = root.querySelectorAll(s); if (els.length) return [...els]; } return []; };

  function streakFor(habit) {
    try { return ((typeof lastReport !== "undefined" && lastReport && lastReport.rows) || []).find(r => r.habit === habit)?.streak_days || 0; }
    catch { return 0; }
  }
  const milestone = n => n === 3 || n === 7 || n === 14 || n === 21 || (n > 21 && n % 7 === 0);
  function bigToday() {
    const d = new Date(), k = `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
    try { if (localStorage.getItem("alibi.bigDay") === k) return false; localStorage.setItem("alibi.bigDay", k); } catch {}
    return true;
  }

  // the --ease-out token (0.23, 1, 0.32, 1) as a bezier solved for y(x) so the count stays in step with the WAAPI meter
  const EASE_OUT = (() => {
    const x1 = 0.23, y1 = 1, x2 = 0.32, y2 = 1;
    const bz = (t, a, b) => 3 * a * t * (1 - t) * (1 - t) + 3 * b * t * t * (1 - t) + t * t * t;
    return x => {
      if (x <= 0) return 0; if (x >= 1) return 1;
      let lo = 0, hi = 1, t = x;
      for (let i = 0; i < 24; i++) { t = (lo + hi) / 2; if (bz(t, x1, x2) < x) lo = t; else hi = t; }
      return bz(t, y1, y2);
    };
  })();

  // Count the number's digits from 0 to `to` in rAF with tabular numerals; keeps any suffix (%, <sup>).
  function countUp(el, to, dur, delay, R) {
    const tn = [...el.childNodes].find(n => n.nodeType === 3 && /\d/.test(n.nodeValue)) || el.firstChild;
    if (!tn) return;
    const set = v => { tn.nodeValue = tn.nodeValue.replace(/\d+/, String(v)); };
    set(0);
    const t0 = performance.now() + delay;
    const step = t => {
      if (R.skipped) return set(to);
      const k = Math.max(0, Math.min(1, (t - t0) / dur));
      set(Math.round(to * EASE_OUT(k)));                     // the meter's curve, so number and bar land together
      if (k < 1) R.raf = requestAnimationFrame(step);
    };
    R.raf = requestAnimationFrame(step);
    R.finishers.push(() => { cancelAnimationFrame(R.raf); set(to); });
  }

  function anim(R, el, frames, opts) {
    if (!el) return null;
    const a = el.animate(frames, Object.assign({fill: "backwards"}, opts));
    R.anims.push(a);
    return a;
  }

  function finishReveal(R) {
    if (!R || R.skipped) return;
    R.skipped = true;
    R.timers.forEach(clearTimeout);
    R.anims.forEach(a => { try { a.finish(); } catch {} });
    R.finishers.forEach(f => f());
    if (!R.clipStarted) R.startClip(false);
    R.off();
  }

  function verdict(rv, cardEl, opts = {animate: false}) {
    if (!rv || !cardEl) return;
    W()?.ensure();
    const replay = MOMENT && !momentDone && (MOMENT === "verdict" || MOMENT === "big");
    if (replay) momentDone = true;
    if (!(opts && opts.animate) || !(replay || booted)) return;   // first paint of an old verdict: end state, no replay
    if (reveal) finishReveal(reveal);

    const v = rv.verdict, r = Math.round((rv.on_task_ratio || 0) * 100);
    const card = pick(cardEl, ["[data-m=card]", ".al-verdict-card", ".vpanel"]) || cardEl.firstElementChild || cardEl;
    const pill = pick(cardEl, ["[data-m=pill]", ".al-verdict", ".vpill"]);
    const num = pick(cardEl, ["[data-m=pct]", "#vnum", ".al-stat__value"]);
    const fill = pick(cardEl, ["[data-m=meter]", ".al-meter__fill", ".vmeter .f"]);
    const frames = pickAll(cardEl, ["[data-m=frames] > *", ".al-strip__cell", ".vsheet img", ".vsheet .win"]).slice(0, 6);
    const later = pickAll(cardEl, ["[data-m=line], [data-m=actions]", ".vsum, .vwhy, .vacts"]);
    const clip = VERDICT_CLIP[v];
    const streak = streakFor(rv.habit);
    const big = v === "done" && !RM() && (MOMENT === "big" || (milestone(streak) && bigToday()));

    const R = reveal = {t0: performance.now(), id: rv.id, anims: [], timers: [], finishers: [], skipped: false, clipStarted: false};
    R.startClip = (withConfetti) => {
      R.clipStarted = true;
      if (!clip || !W()) return;
      if (big) return bigCelebration(rv, streak, R);
      W().play(clip, {force: true});
      if (withConfetti && v === "done" && window.AlibiConfetti && !W().quiet()) {
        const c = W().claws();
        if (c) window.AlibiConfetti.burst(c.x, c.y, {count: 28, cone: 60});
      }
    };

    if (RM()) {     // fewer, gentler: everything fades in together, numbers already final, Pinch on its key pose
      const f = [{opacity: 0}, {opacity: 1}];
      [card].forEach(el => anim(R, el, f, {duration: 150, easing: "ease"}));
      R.startClip(false);
      R.off = () => {};
      return;
    }

    const OUT = ease("--ease-out");
    anim(R, card, [{opacity: 0, transform: "translateY(12px)"}, {opacity: 1, transform: "none"}],
      {duration: ms("--spring-smooth-dur", 686), delay: 120, easing: ease("--spring-smooth")});
    anim(R, pill, [{opacity: 0, transform: "scale(0.94)", filter: "blur(8px)"}, {opacity: 1, transform: "none", filter: "blur(0)"}],
      {duration: ms("--spring-bouncy-dur", 720), delay: 270, easing: ease("--spring-bouncy")});
    if (num) countUp(num, r, ms("--dur-reveal", 900), 420, R);
    if (fill) {
      // scaleX(0) is singular, so a matrix end would interpolate discretely: animate scaleX to scaleX
      const mx = /matrix\(([-\d.e]+)/.exec(getComputedStyle(fill).transform || "");
      const sx = mx ? +mx[1] : 1;
      anim(R, fill, [{transform: "scaleX(0.0001)", transformOrigin: "left center"}, {transform: `scaleX(${sx})`, transformOrigin: "left center"}],
        {duration: ms("--dur-reveal", 900), delay: 420, easing: OUT});
    }
    frames.forEach((el, i) => anim(R, el, [{opacity: 0, transform: "translateY(6px)"}, {opacity: 1, transform: "none"}],
      {duration: ms("--dur-medium", 260), delay: 560 + 40 * Math.min(i, 5), easing: OUT}));
    later.forEach(el => anim(R, el, [{opacity: 0, transform: "translateY(4px)"}, {opacity: 1, transform: "none"}],
      {duration: ms("--dur-medium", 260), delay: 1000, easing: OUT}));
    R.timers.push(setTimeout(() => { if (!R.skipped) R.startClip(true); }, 1000));
    if (v === "done") R.timers.push(setTimeout(() => {           // streak bump once the count has landed
      const st = document.querySelector(".al-streak");
      if (st && !R.skipped) st.animate([{transform: "scale(1)"}, {transform: "scale(1.18)", offset: 0.35}, {transform: "scale(1)"}],
        {duration: ms("--spring-bouncy-dur", 720), easing: ease("--spring-bouncy")});
    }, 1320));

    // click anywhere, Esc or Space skips to the end state (the click still reaches its button)
    const skip = e => { if (e.type === "keydown" && e.key !== "Escape" && e.key !== " ") return; finishReveal(R); };
    R.off = () => { removeEventListener("pointerdown", skip, true); removeEventListener("keydown", skip, true); };
    addEventListener("pointerdown", skip, true);
    addEventListener("keydown", skip, true);
    R.timers.push(setTimeout(() => R.off(), 2600));
  }

  /* Big celebration: the first win and streak milestones. 160px Pinch on the scrim with the single bloom; the card Pinch
     steps aside so there is still one Pinch per view. */
  function bigCelebration(rv, streak, R) {
    const n = streak || 1;
    const line = n >= 3 ? (n === 3 ? "3 days in a row. That's how it starts." : `${n} days in a row. I've seen every one.`) : "First one done. I saw all of it.";
    const ov = document.createElement("div");
    ov.className = "m-big"; ov.setAttribute("role", "status");
    ov.innerHTML = `<div class="m-big__stage"><span class="al-bloom m-big__bloom" aria-hidden="true"></span><div class="m-big__pinch"></div></div>
      <p class="m-big__line">${escH(line)}</p>`;
    document.body.appendChild(ov);
    const slot = W().slot("now");
    slot?.host.classList.add("is-stepped");
    const inst = window.AlibiPinch.mount(ov.querySelector(".m-big__pinch"), {size: 160, mood: "idle", theme: "auto"});
    inst.camera(false);
    inst.play("celebrate", {force: true});
    const c = ov.querySelector(".m-big__pinch").getBoundingClientRect();
    if (window.AlibiConfetti) window.AlibiConfetti.burst(c.left + c.width / 2, c.top + c.height * 0.3, {count: 28, cone: 60, spread: 1.5});
    const close = () => {
      if (!ov.isConnected) return;
      ov.classList.add("is-leaving");
      setTimeout(() => { inst.destroy(); ov.remove(); slot?.host.classList.remove("is-stepped"); }, 170);
      removeEventListener("pointerdown", close, true); removeEventListener("keydown", close, true);
    };
    R.timers.push(setTimeout(close, 1600));          // hold to 2600 from the trigger, exit in 170
    R.finishers.push(close);
    setTimeout(() => { addEventListener("pointerdown", close, true); addEventListener("keydown", close, true); }, 0);
  }

  /* ---------- nudge card (signature moment 2, web side) ---------- */
  const RELABEL = {"I'm back": "Back to it", "It's on task": "This counts", "Snooze 5m": "Quiet 5 min"};
  const CAUSES = ["phone", "empty", "moved", "something else", "YouTube", "Twitter", "Reddit", "Netflix", "Instagram", "TikTok", "Slack", "Discord", "WhatsApp", "Messages", "Mail", "Steam"];
  // same rounding as the Now card's drift line, so the card and the toast never disagree
  function spanText(sec) {
    if (sec == null) return null;
    const m = Math.max(1, Math.round(sec / 60));
    return m === 1 ? "1 minute" : `${m} minutes`;
  }
  const habitWord = h => /^[A-Z][a-z]+( [a-z]+)*$/.test(h) ? h.toLowerCase() : h;
  function nudgeLine(a, s) {
    const dr = s && s.session && s.session.drifting || {};
    const h = habitWord(a.habit_label || (typeof dispName === "function" ? dispName(a.habit) : a.habit) || "this");
    const t = spanText(dr.since_s) || (/(\d+\s*(?:seconds?|minutes?))/.exec(a.text || "") || [])[1];
    const serverLine = (s && s.pinch && s.pinch.line) || "";
    if (/^You said\b/.test(serverLine)) return serverLine;
    if (/^You said\b/.test(a.text || "")) return a.text;
    if (t) {
      if (a.label === "phone") return `You said ${h}. I've seen your phone for ${t}.`;
      if (a.label === "absent") return `Your desk's been empty for ${t}. Still ${h}?`;
      if (a.label === "idle") return `You said ${h}. Nothing's moved in ${t}.`;
      if (a.label === "off_task" && dr.label_text && !/^(off task|something else)$/i.test(dr.label_text)) return `You said ${h}. That's been ${dr.label_text} for ${t}.`;
    }
    return serverLine || a.text || "";
  }
  function markCause(line, a, s) {
    const dr = s && s.session && s.session.drifting || {};
    const extra = dr.label_text && !/^(on your phone|off task|something else|idle|away)/i.test(dr.label_text) ? [dr.label_text] : [];
    const words = [...extra, ...CAUSES].map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const re = new RegExp(`\\b(${words.join("|")})\\b`);
    const m = re.exec(line);
    if (!m) return escH(line);
    return escH(line.slice(0, m.index)) + `<span class="al-cause">${escH(m[1])}</span>` + escH(line.slice(m.index + m[1].length));
  }
  function stack() {
    let st = document.getElementById("m-toasts");
    if (!st) { st = document.createElement("div"); st.id = "m-toasts"; st.className = "m-toasts"; st.setAttribute("aria-live", "polite"); document.body.appendChild(st); }
    return st;
  }
  function closeCard(card) {
    if (!card || !card.isConnected || card.classList.contains("is-leaving")) return;
    card.classList.add("is-leaving");
    const a = card.animate([{opacity: 1, transform: "none"}, {opacity: 0, transform: "translateY(-4px)"}], {duration: RM() ? 150 : 170, easing: ease("--ease-out"), fill: "forwards"});
    a.onfinish = () => card.remove();
  }
  const X_ICON = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';
  function runAction(x) {
    if (x.say && typeof say === "function") return say(x.say);
    if (x.post && typeof postJSON === "function") return postJSON(x.post, x.body || {}).catch(() => {});
    if (x.url) window.open(x.url, "_blank", "noopener");
  }
  function nudge(alert, s) {
    if (!alert) return false;
    const line = nudgeLine(alert, s);
    if (!line) return false;
    if (s && W()) W().server(s);                              // lens truth for the avatar before state() runs
    const st = stack();
    st.querySelectorAll(".m-nudge").forEach(closeCard);
    const when = typeof clockT === "function" && alert.ts ? ` · ${clockT(alert.ts)}` : "";
    const title = (alert.habit_label || (typeof dispName === "function" ? dispName(alert.habit) : "")) + when;
    const acts = (alert.actions || []).slice(0, 3);
    const VAR = ["primary", "secondary", "quiet"];
    const card = document.createElement("div");
    card.className = "al-toast m-nudge"; card.setAttribute("role", "alert");
    card.dataset.alert = alert.id;
    card.innerHTML = `<div class="al-toast__head"><span class="al-toast__title">${escH(title)}</span>
        <button type="button" class="al-iconbtn al-iconbtn--sm al-toast__close" aria-label="Dismiss">${X_ICON}</button></div>
      <div class="al-pinchline is-compact"><span class="al-pinchline__avatar">${W() ? W().avatar("thinking", 20) : ""}</span>
        <p class="al-pinchline__text">${markCause(line, alert, s)}</p></div>
      ${acts.length ? `<div class="al-toast__actions">${acts.map((x, i) => `<button type="button" class="al-btn al-btn--sm al-btn--${VAR[i] || "quiet"}" data-i="${i}">${escH(RELABEL[x.label] || x.label)}</button>`).join("")}</div>` : ""}`;
    card.addEventListener("click", e => {
      if (e.target.closest(".al-toast__close")) return closeCard(card);
      const b = e.target.closest("[data-i]"); if (!b) return;
      closeCard(card); runAction(acts[+b.dataset.i] || {});
    });
    st.appendChild(card);
    return true;
  }
  // a nudge card leaves on its own once the session ends or the drift is over
  function tidyNudges(s) {
    const st = document.getElementById("m-toasts"); if (!st) return;
    if (!s.session || (!s.session.drifting && !(s.alert && s.alert.kind === "nudge" && (s.now - s.alert.ts) < 20)))
      st.querySelectorAll(".m-nudge").forEach(closeCard);
  }

  /* ---------- polaroid develop (signature moment 8) ---------- */
  let lastDeveloped = null;
  function sample(label, imgEl, dotEl) {
    if (!booted || RM()) return;
    if ((imgEl || dotEl)?.closest?.(".is-new")) return;     // the strip's .is-new CSS already develops and pops it
    const OUT = ease("--ease-out");
    requestAnimationFrame(() => {            // the frame <img> is painted after the strip in the same render
      const img = imgEl || document.querySelector("#frame img, .al-strip__cell:last-child .al-strip__img");
      const fresh = img && img.getAttribute("src") !== lastDeveloped;
      if (fresh) {
        lastDeveloped = img.getAttribute("src");
        img.animate([{opacity: 0, transform: "translateY(6px)"}, {opacity: 1, transform: "none"}], {duration: ms("--dur-medium", 260), easing: OUT});
        img.animate([{filter: "grayscale(1) brightness(1.5) blur(6px)"}, {filter: "none"}], {duration: ms("--dur-reveal", 900), easing: OUT});
      }
      if (dotEl) dotEl.animate([{transform: "scale(0.6)", opacity: 0}, {transform: "none", opacity: 1}],
        {duration: ms("--spring-bouncy-dur", 720), delay: fresh ? ms("--dur-reveal", 900) : 0, easing: ease("--spring-bouncy"), fill: "backwards"});
    });
  }

  /* ---------- composer -> session FLIP (signature moment 5) ---------- */
  function sessionStart(fromEl, toEl) {
    if (!fromEl) return;
    const btn = fromEl.querySelector("button[type=submit], .al-composer__send");
    if (btn && !RM()) btn.animate([{transform: "scale(0.97)"}, {transform: "none"}], {duration: ms("--spring-micro-dur", 376), easing: ease("--spring-micro")});
    pendingFlip = {rect: fromEl.getBoundingClientRect(), t: performance.now(), toEl};
  }
  function runFlip() {
    const f = pendingFlip;
    if (!f || !document.body.classList.contains("live")) { if (f && performance.now() - f.t > 6000) pendingFlip = null; return; }
    pendingFlip = null;
    const target = (f.toEl || document.getElementById("now"))?.firstElementChild;
    if (!target) return;
    if (RM()) { target.animate([{opacity: 0}, {opacity: 1}], {duration: 150, easing: "ease"}); return; }
    const b = target.getBoundingClientRect(), a = f.rect;
    if (!b.width || !b.height) return;
    target.animate([
      {transformOrigin: "0 0", transform: `translate(${a.left - b.left}px, ${a.top - b.top}px) scale(${a.width / b.width}, ${a.height / b.height})`, opacity: 0.6},
      {transformOrigin: "0 0", transform: "none", opacity: 1}
    ], {duration: ms("--spring-snappy-dur", 484), easing: ease("--spring-snappy")});
    [...target.children].slice(0, 6).forEach((el, i) => el.animate(
      [{opacity: 0, transform: "scale(0.96)", filter: "blur(8px)"}, {opacity: 1, transform: "none", filter: "blur(0)"}],
      {duration: ms("--spring-snappy-dur", 484), delay: 180 + 40 * i, easing: ease("--spring-snappy"), fill: "backwards"}));
  }

  /* ---------- fix a moment (signature moment 6) ---------- */
  function correction(sid, ts, label, dotEl, reply) {
    const dot = dotEl || [...document.querySelectorAll(`[data-sid="${sid}"]`)].find(d => {
      const l = (typeof sampleFor === "function") ? sampleFor(d)?.l : null;
      return l && Math.abs(l.ts - ts) < 0.5;
    });
    if (dot && !RM()) dot.animate([{transform: "scale(0.6)"}, {transform: "none"}], {duration: ms("--spring-bouncy-dur", 720), delay: 0, easing: ease("--spring-bouncy")});
    setTimeout(() => W()?.play("surprise"), 200);
    setTimeout(() => {                         // Pinch's line leads the correction toast; Undo stays where it is
      const tx = document.getElementById("toastText");
      if (tx && !/^Fair\./.test(tx.textContent)) tx.textContent = "Fair. I've changed that one. " + tx.textContent;
    }, 0);
  }
  // the correction popover grows from the dot that opened it (transform-origin computed, never a fixed corner)
  function wirePop() {
    const pop = document.getElementById("pop");
    if (!pop || pop.dataset.mWired) return;
    pop.dataset.mWired = "1";
    new MutationObserver(() => {
      if (!pop.classList.contains("show") || pop.dataset.mShown === pop.dataset.ts) { if (!pop.classList.contains("show")) delete pop.dataset.mShown; return; }
      pop.dataset.mShown = pop.dataset.ts;
      const anchor = (typeof popFor !== "undefined" && popFor) || document.querySelector(".strip .dot.sel, .sm.sel");
      if (!anchor || RM()) return;
      const r = anchor.getBoundingClientRect(), p = pop.getBoundingClientRect();
      const ox = r.left + r.width / 2 - p.left, oy = (r.top > p.top ? r.top : r.bottom) - p.top;
      pop.animate([{opacity: 0, transform: "scale(0.96)", transformOrigin: `${ox}px ${oy}px`}, {opacity: 1, transform: "none", transformOrigin: `${ox}px ${oy}px`}],
        {duration: ms("--dur-small", 180), easing: ease("--ease-out")});
    }).observe(pop, {attributes: true, attributeFilter: ["class"]});
  }

  /* ---------- every poll ---------- */
  function state(s) {
    if (!s) return;
    wirePop();
    const w = W();
    if (w) { w.ensure(); w.server(s); }
    const p = s.pinch || {};
    const seq = +p.seq || 0;
    if (!booted) lastSeq = seq;                                    // record, never replay on load
    else if (seq > lastSeq) {
      lastSeq = seq;
      if (p.event && (p.age_s == null || p.age_s < 15)) playEvent(p, s);
    }
    tidyNudges(s);
    runFlip();
    booted = true;
  }

  window.AlibiMoments = {
    state,                                                     // every poll, after render; drives Pinch from s.pinch
    verdict,                                                   // after renderVerdict paints the card
    nudge,                                                     // true = moments rendered the nudge card; core.js skips the red toast
    sample,                                                    // a new sample appeared in the live strip
    sessionStart,                                              // composer -> live card (FLIP)
    correction,                                                // after POST /api/sessions/{id}/correct succeeds
  };
})();
