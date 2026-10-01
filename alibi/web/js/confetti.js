/* confetti.js: the claw burst for a done verdict (Motion.md, signature moment 1).
   window.AlibiConfetti.burst(x, y, {count = 28, cone = 60}) fires `count` particles in a `cone`-degree cone pointing up
   from viewport point (x, y): claw paths, four-point sparks and 3px dots in accent 50%, accent-ink 25%, white 15%,
   partial 10%. Each travels translate(dx, -h) -> translate(1.4dx, g), rotates up to 240 degrees and fades over its last
   30%, on WAAPI; the nodes go on finish. Reduced motion: nothing (the CSS hides .al-confetti too). Safe to load twice. */
(function () {
  "use strict";
  if (window.AlibiConfetti) return;
  const CLAW = '<svg viewBox="0 0 12 10" width="12" height="10" aria-hidden="true"><path fill="currentColor" d="M5.5 9.6C2.2 9.3.2 6.5.8 3.4 1.1 1.9 2 .8 3 .3c-.2 1.6.4 3 1.9 3.6.3-1.7 1.3-3 2.9-3.6 2.4 1 3.9 3.3 3.5 5.6-.4 2.2-2.8 3.8-5.8 3.7Z"/></svg>';
  const SPARK = '<svg viewBox="0 0 10 10" width="9" height="9" aria-hidden="true"><path fill="currentColor" d="M5 0c.4 2.6 1.4 3.6 5 5-3.6 1.4-4.6 2.4-5 5-.4-2.6-1.4-3.6-5-5 3.6-1.4 4.6-2.4 5-5Z"/></svg>';
  // colour mix by weight: accent 50, accent-ink 25, white 15, partial 10
  const COLOURS = [["var(--accent)", 50], ["var(--accent-ink)", 25], ["var(--pinch-shine)", 15], ["var(--partial)", 10]];
  const pickColour = r => { let a = 0; for (const [c, w] of COLOURS) { a += w; if (r * 100 < a) return c; } return COLOURS[0][0]; };
  const EASE = "cubic-bezier(.2,.6,.4,1)";   // lint-ok: Motion.md confetti curve, used only here

  function burst(x, y, o = {}) {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return null;
    const count = o.count || 28, cone = (o.cone || 60) * Math.PI / 180, spread = o.spread || 1;
    const box = document.createElement("div");
    box.className = "al-confetti m-confetti";
    box.setAttribute("aria-hidden", "true");
    box.style.left = x + "px"; box.style.top = y + "px";
    document.body.appendChild(box);
    let left = count;
    for (let i = 0; i < count; i++) {
      const p = document.createElement("i");
      const kind = i % 7 < 3 ? "claw" : i % 7 < 5 ? "spark" : "dot";   // 3 : 2 : 2
      p.className = "m-confetti__p m-confetti__p--" + kind;
      p.style.color = pickColour(Math.random());
      if (kind === "claw") p.innerHTML = CLAW; else if (kind === "spark") p.innerHTML = SPARK;
      box.appendChild(p);
      const a = -Math.PI / 2 + (Math.random() - 0.5) * cone;           // up, inside the cone
      const dist = (90 + Math.random() * 130) * spread;
      const dx = Math.cos(a) * dist, h = -Math.sin(a) * dist;           // h > 0 is up
      const g = (40 + Math.random() * 80) * spread;                      // where it lands below the claws
      const rot = (Math.random() < 0.5 ? -1 : 1) * (120 + Math.random() * 120);
      const s = 0.8 + Math.random() * 0.5;
      const anim = p.animate([
        {transform: `translate(0,0) rotate(0deg) scale(${s * 0.6})`, opacity: 1},
        {transform: `translate(${dx}px,${-h}px) rotate(${rot * 0.5}deg) scale(${s})`, opacity: 1, offset: 0.45},
        {transform: `translate(${dx * 1.2}px,${-h * 0.4}px) rotate(${rot * 0.8}deg) scale(${s})`, opacity: 1, offset: 0.7},
        {transform: `translate(${dx * 1.4}px,${g}px) rotate(${rot}deg) scale(${s})`, opacity: 0},
      ], {duration: 1100 + Math.random() * 500, delay: Math.random() * 60, easing: EASE, fill: "both"});
      anim.onfinish = anim.oncancel = () => { p.remove(); if (--left <= 0) box.remove(); };
    }
    return box;
  }
  function clear() { document.querySelectorAll(".m-confetti").forEach(b => b.remove()); }

  window.AlibiConfetti = {burst, clear};
})();
