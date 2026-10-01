/* pinch-wire.js: one Pinch per view on the dashboard (Mascot.md "Where Pinch must not appear").
   window.AlibiPinchWire owns two engine instances: the hero (64, #pinch-hero, shown while idle) and the Now card (96,
   #pinch-now, shown while live or on a verdict). The shell may rebuild those mounts with innerHTML at any time, so each
   instance lives in a persistent host that is re-attached to whichever mount exists (call ensure() after a render).
   Server mood comes from /api/state pinch; client-only moods (listening, reading) layer on top and fall back to it.
   Classic script; needs pinch.js (window.AlibiPinch). Safe to load twice. */
(function () {
  "use strict";
  if (window.AlibiPinchWire) return;
  const P = () => window.AlibiPinch;
  const RM = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const quiet = () => { try { return localStorage.getItem("alibi.quiet") === "1"; } catch { return false; } };
  const SIZES = {hero: 64, now: 96};
  const slots = {};          // name -> {host, inst, size}
  let serverMood = "idle", clientMood = null, cameraOn = false, sessId = null, lastMode = "";

  function makeSlot(name) {
    if (slots[name] || !P()) return slots[name];
    const host = document.createElement("div");
    host.className = "al-pinch m-pinch m-pinch--" + name;
    host.dataset.pinchSlot = name;
    host.setAttribute("role", "img");
    const inst = P().mount(host, {size: SIZES[name], mood: serverMood, theme: "auto"});
    slots[name] = {host, inst, size: SIZES[name]};
    label(name);
    return slots[name];
  }
  function label(name) {
    const s = slots[name]; if (!s) return;
    const m = clientMood || serverMood;
    s.host.setAttribute("aria-label", `Pinch, ${({idle: "watching", focused: "watching you work", listening: "listening", thinking: "checking", sleepy: "on a break", reading: "reading the report"})[m] || m}`);
  }

  // Fallback mounts while the shell has none: the hero beside the week line, the Now Pinch in the Now header.
  function mountEl(name) {
    const real = document.getElementById("pinch-" + name);
    document.querySelectorAll(`[data-m-fallback="${name}"]`).forEach(f => { if (real && f !== real) f.remove(); });
    if (real) return real;
    const near = name === "hero" ? document.getElementById("weekHero") : document.querySelector("#nowBlock .sechead");
    if (!near) return null;
    const f = document.createElement("div");
    f.id = "pinch-" + name; f.dataset.mFallback = name; f.className = "m-fallback m-fallback--" + name;
    near.prepend(f);
    return f;
  }

  // The Now Pinch is on stage when the shell has placed #pinch-now in the Now card (not parked, not hidden);
  // without a shell placement, fall back to the page mode classes.
  function mode() {
    const el = document.getElementById("pinch-now");
    if (el && !el.dataset.mFallback) return el.closest(".parking, [hidden]") || !el.isConnected ? "idle" : "now";
    return document.body.classList.contains("live") || document.body.classList.contains("verdict") ? "now" : "idle";
  }

  // Re-attach hosts to the current mounts; returns the slot that should be visible.
  function ensure() {
    if (!P()) return null;
    for (const name of ["hero", "now"]) {
      const s = makeSlot(name), el = mountEl(name);
      if (s && el && s.host.parentNode !== el) el.appendChild(s.host);
    }
    const m = mode(), active = m === "idle" ? "hero" : "now", from = active === "hero" ? "now" : "hero";
    const moving = lastMode && m !== lastMode && slots[from] && !slots[from].host.classList.contains("is-away");
    const fromRect = moving && slots[from].host.isConnected ? slots[from].host.getBoundingClientRect() : null;
    lastMode = m;
    for (const name in slots) slots[name].host.classList.toggle("is-away", name !== active);
    if (fromRect) travel(fromRect, active);
    document.documentElement.classList.toggle("m-pinch-live", active === "now");
    return slots[active];
  }

  // FLIP: the one Pinch travels between the hero (64) and the Now card (96) on spring-smooth.
  function travel(ra, toName) {
    const b = slots[toName];
    if (!b || RM() || !b.host.isConnected) return;
    const rb = b.host.getBoundingClientRect();
    if (!ra.width || !rb.width || Math.abs(ra.top - rb.top) > innerHeight * 1.5) return;
    const k = ra.width / rb.width, css = getComputedStyle(document.documentElement);
    b.host.animate([
      {transform: `translate(${ra.left - rb.left}px, ${ra.top - rb.top}px) scale(${k})`, transformOrigin: "0 0"},
      {transform: "none", transformOrigin: "0 0"}
    ], {duration: parseFloat(css.getPropertyValue("--spring-smooth-dur")) || 686, easing: css.getPropertyValue("--spring-smooth").trim() || "ease-out"});
  }

  function applyMood() {
    const m = clientMood || serverMood;
    for (const name in slots) { slots[name].inst.set(m); label(name); }
  }

  const W = window.AlibiPinchWire = {
    ensure,
    slot: name => (ensure(), slots[name] || null),
    active: () => ensure(),
    quiet,
    // server state from each poll: mood, lens truth, per-session side-eye budget
    server(s) {
      const p = s && s.pinch || {}, sess = s && s.session;
      serverMood = P() && P().moods.includes(p.mood) ? p.mood : sess ? (sess.on_break ? "sleepy" : "focused") : "idle";
      const id = sess ? sess.id : null;
      if (id !== sessId) {                     // a fresh session gets a fresh 3-side-eye budget
        sessId = id;
        for (const name in slots) if (slots[name].inst.state().sideeyes >= 3) {
          const s2 = slots[name]; s2.inst.destroy(); s2.inst = P().mount(s2.host, {size: s2.size, mood: serverMood, theme: "auto"});
        }
      }
      // the lens tells the truth: it glows only while the camera samples
      cameraOn = !!(sess && sess.modality !== "digital" && !sess.on_break && !sess.ended);
      for (const name in slots) slots[name].inst.camera(cameraOn);
      applyMood();
    },
    client(mood) { clientMood = mood || null; applyMood(); },
    clientMood: () => clientMood,
    // one-shot on the visible Pinch; quiet lobster keeps poses and lines, drops clips
    play(clip, opts) {
      const s = ensure();
      if (!s || quiet() || !P().clips.includes(clip)) return Promise.resolve(false);
      return s.inst.play(clip, opts || {});
    },
    // centre of the visible Pinch's claws, for the confetti cone
    claws() {
      const s = ensure(); if (!s || !s.host.isConnected) return null;
      const r = s.host.getBoundingClientRect();
      if (!r.width) return null;
      return {x: r.left + r.width / 2, y: r.top + r.height * 0.3, w: r.width};
    },
    // static avatar markup for a PinchLine (20px lod, still); the lens glows only if the camera is sampling now
    avatar(mood, size = 20) {
      if (!P()) return "";
      return `<span class="al-pinch m-avatar" aria-hidden="true">${P().svg({size, mood: P().moods.includes(mood) ? mood : "idle", camera: cameraOn, theme: "auto"})}</span>`;
    },
  };

  // Client-only moods: the composer listens; the weekly report in view reads. Both fall back to the server mood.
  function wireClient() {
    const field = document.getElementById("sayInput");
    if (field && !field.dataset.mWired) {
      field.dataset.mWired = "1";
      field.addEventListener("focus", () => W.client("listening"));
      field.addEventListener("input", () => { if (clientMood !== "listening") W.client("listening"); });
      field.addEventListener("blur", () => { if (clientMood === "listening") W.client(null); });
    }
    const rep = document.getElementById("fullRep") || document.getElementById("quote");
    if (rep && window.IntersectionObserver && !rep.dataset.mWired) {
      rep.dataset.mWired = "1";
      let reading = false;
      new IntersectionObserver(es => {
        const vis = es.some(e => e.isIntersecting && e.intersectionRatio > 0.5) && !rep.hidden;
        if (vis && !clientMood && mode() === "idle") { reading = true; W.client("reading"); }
        else if (!vis && reading && clientMood === "reading") { reading = false; W.client(null); }
      }, {threshold: [0, 0.5, 1]}).observe(rep);
    }
  }
  const start = () => { ensure(); wireClient(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
