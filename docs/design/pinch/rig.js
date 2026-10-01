/* Pinch rig: the reference mapping from the param vector to SVG part transforms.
   Data-agnostic: pass rig.json and clips.json objects in.  No DOM globals beyond the SVG element
   you hand to apply(); no rAF, no timers (that is the engine's job, see pinch.js).

   AlibiPinchRig.neutral(rig)                      -> params object at rest
   AlibiPinchRig.sample(def, ms)                   -> {param: value} for every track in a mood/clip/blink def
   AlibiPinchRig.pose(rig, clips, name, ms)        -> neutral + the mood or clip at ms (sheet / seek helper)
   AlibiPinchRig.apply(svgEl, params, rig, tMs)    -> writes transform/opacity attributes on [data-part] nodes
   AlibiPinchRig.prefixIds(markup, prefix)         -> markup with every id / url(#id) / href="#id" namespaced
   AlibiPinchRig.ease(name, t01, segMs, elapsedMs) -> eased 0..1 (cubic-bezier, spring(duration,bounce), step)
*/
(function (root) {
  'use strict';

  /* ---------- easing ---------- */
  var BEZ = {};
  function bezier(x1, y1, x2, y2) {
    function a(p1, p2) { return 1 - 3 * p2 + 3 * p1; }
    function b(p1, p2) { return 3 * p2 - 6 * p1; }
    function c(p1) { return 3 * p1; }
    function calc(t, p1, p2) { return ((a(p1, p2) * t + b(p1, p2)) * t + c(p1)) * t; }
    function slope(t, p1, p2) { return 3 * a(p1, p2) * t * t + 2 * b(p1, p2) * t + c(p1); }
    return function (x) {
      if (x <= 0) return 0;
      if (x >= 1) return 1;
      var t = x;
      for (var i = 0; i < 8; i++) {
        var s = slope(t, x1, x2);
        if (Math.abs(s) < 1e-6) break;
        t -= (calc(t, x1, x2) - x) / s;
      }
      if (t < 0 || t > 1) { // bisection fallback
        var lo = 0, hi = 1; t = x;
        for (var j = 0; j < 30; j++) { var v = calc(t, x1, x2); if (v < x) lo = t; else hi = t; t = (lo + hi) / 2; }
      }
      return calc(t, y1, y2);
    };
  }
  /* SwiftUI-compatible spring(duration, bounce): omega = 2pi/duration, damping ratio = 1 - bounce.
     Evaluated on real elapsed time so a long segment simply holds the settled value. */
  function spring(durMs, bounce, elapsedMs) {
    var t = Math.max(0, elapsedMs) / 1000, w = 2 * Math.PI / (durMs / 1000), z = 1 - bounce;
    if (z >= 1) return 1 - Math.exp(-w * t) * (1 + w * t);
    var wd = w * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + (z * w / wd) * Math.sin(wd * t));
  }
  var EASINGS = null;
  function setEasings(map) { EASINGS = map || {}; }
  function ease(name, t, segMs, elapsedMs) {
    var spec = (EASINGS && EASINGS[name]) || name || 'linear';
    if (spec === 'linear') return t;
    if (spec === 'step') return t >= 1 ? 1 : 0;
    var m = /^cubic-bezier\(([^)]+)\)$/.exec(spec);
    if (m) {
      if (!BEZ[spec]) { var v = m[1].split(',').map(Number); BEZ[spec] = bezier(v[0], v[1], v[2], v[3]); }
      return BEZ[spec](t);
    }
    m = /^spring\(([^,]+),([^)]+)\)$/.exec(spec);
    if (m) return t >= 1 ? 1 : spring(Number(m[1]), Number(m[2]), elapsedMs == null ? t * segMs : elapsedMs);
    return t;
  }

  /* ---------- tracks ---------- */
  function sampleTrack(tr, ms) {
    if (!tr.length) return undefined;
    if (ms <= tr[0][0]) return tr[0][1];
    for (var i = 1; i < tr.length; i++) {
      var a = tr[i - 1], b = tr[i];
      if (ms < b[0]) {
        if (typeof b[1] !== 'number' || typeof a[1] !== 'number') return a[1];
        var seg = b[0] - a[0] || 1, k = (ms - a[0]) / seg;
        return a[1] + (b[1] - a[1]) * ease(b[2] || 'out', k, seg, ms - a[0]);
      }
    }
    return tr[tr.length - 1][1];
  }
  function sample(def, ms) {
    var out = {}, t = def.loop ? ((ms % def.dur) + def.dur) % def.dur : ms;
    for (var k in def.tracks) out[k] = sampleTrack(def.tracks[k], t);
    return out;
  }
  function neutral(rig) {
    var p = {};
    rig.params.forEach(function (d) { p[d.name] = d['default']; });
    return p;
  }
  function pose(rig, clips, name, ms) {
    setEasings(clips.easings);
    var p = neutral(rig), def = clips.moods[name] || clips.clips[name];
    var s = sample(def, ms == null ? (def.key || 0) : ms);
    for (var k in s) p[k] = s[k];
    return p;
  }

  /* ---------- tiny affine helpers: [a b c d e f] like SVG matrix() ---------- */
  function mul(m, n) {
    return [m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1], m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
      m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5]];
  }
  function T(x, y) { return [1, 0, 0, 1, x, y]; }
  function R(deg, cx, cy) {
    var r = deg * Math.PI / 180, c = Math.cos(r), s = Math.sin(r);
    return mul(mul(T(cx || 0, cy || 0), [c, s, -s, c, 0, 0]), T(-(cx || 0), -(cy || 0)));
  }
  function S(sx, sy, cx, cy) { return mul(mul(T(cx, cy), [sx, 0, 0, sy, 0, 0]), T(-cx, -cy)); }
  function inv(m) {
    var det = m[0] * m[3] - m[1] * m[2];
    return [m[3] / det, -m[1] / det, -m[2] / det, m[0] / det, (m[2] * m[5] - m[3] * m[4]) / det, (m[1] * m[4] - m[0] * m[5]) / det];
  }
  function ap(m, p) { return [m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5]]; }
  function str(m) { return 'matrix(' + m.map(function (v) { return +v.toFixed(4); }).join(' ') + ')'; }
  function n2(v) { return +(+v).toFixed(3); }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function smooth(a, b, v) { var t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); }

  /* ---------- apply ---------- */
  function apply(svg, p, rig, tMs) {
    var G = rig.geom, part = {};
    svg.querySelectorAll('[data-part]').forEach(function (el) { part[el.getAttribute('data-part')] = el; });
    function set(id, attr, v) { var el = part[id]; if (el) el.setAttribute(attr, v); }
    function op(id, v) { set(id, 'opacity', n2(clamp(v, 0, 1))); }

    // root: squash about the feet with volume kept, then tilt (+ gaze lean), then bodyY
    var sy = p.bodySquash, sx = 1 / Math.sqrt(sy), F = rig.feet;
    var rootM = mul(mul(T(0, p.bodyY), R(p.tilt + G.lookLean * p.lookX, F[0], F[1])), S(sx, sy, F[0], F[1]));
    set('pinch-root', 'transform', str(rootM));

    // antennae: lift is mirrored (both perk up), sway is same-direction (the right one at 0.85)
    set('antenna-l', 'transform', 'rotate(' + n2(p.antennaLift + p.antennaSway) + ' ' + G.antenna.l.join(' ') + ')');
    set('antenna-r', 'transform', 'rotate(' + n2(-p.antennaLift + 0.85 * p.antennaSway) + ' ' + G.antenna.r.join(' ') + ')');

    // eyes: gaze translate, >1 eyeOpen scales the eye up (surprise), joy crossfades to ^ ^
    var cEye = clamp(1 - p.eyeOpen, 0, 1), es = Math.max(1, p.eyeOpen);
    var eyeM = {};
    ['l', 'r'].forEach(function (s) {
      var c = G.eyes[s];
      var m = mul(T(p.lookX * G.look[0], p.lookY * G.look[1]), S(es, es, c[0], c[1]));
      eyeM[s] = m;
      set('eye-' + s, 'transform', str(m));
      var lid = s === 'l' ? p.lidL : p.lidR, brow = s === 'l' ? -p.browL : p.browR;
      var cov = clamp(1 - (1 - cEye) * (1 - lid), 0, 1);
      var lidT = 'translate(0 ' + n2(cov * G.lidSpan) + ') rotate(' + n2(brow) + ' ' + c[0] + ' ' + G.lidEdge[s] + ')';
      set('lid-' + s, 'transform', lidT);
      op('lid-' + s + '-lash', cov / 0.06);
      op('eye-' + s + '-open', 1 - p.joy);
      op('eye-' + s + '-joy', p.joy);
      if (s === 'r') { set('lens-lid', 'transform', lidT); op('lens-lid-lash', cov / 0.06); op('lens-eye-r-open', 1 - p.joy); }
    });

    // mouth: one of four shapes; smile height scales with mouthCurve (never below -0.2: no frowns)
    var shapes = ['smile', 'flat', 'open', 'o'];
    shapes.forEach(function (k) { op('mouth-' + k, p.mouth === k ? 1 : 0); });
    var mc = clamp(p.mouthCurve, -0.2, 1.4);
    set('mouth-smile', 'transform', 'translate(0 ' + n2(G.smileY * (1 - mc)) + ') scale(1 ' + n2(mc) + ')');
    set('mouth', 'transform', 'rotate(' + n2(p.mouthTilt) + ' ' + G.mouth.join(' ') + ')');
    op('blush', p.blush);

    // arms and claws: + is a raise on both sides. The lens macro adds its IK angles to the right side.
    var L = clamp(p.lens, 0, 1), LR = G.lensRaise;
    var armL = p.clawL, armR = -p.clawR + L * LR.arm;
    var clawL = G.clawFollow * p.clawL + p.wristL, clawR = -G.clawFollow * p.clawR - p.wristR + L * LR.claw;
    set('arm-l', 'transform', 'rotate(' + n2(armL) + ' ' + G.shoulder.l.join(' ') + ')');
    set('arm-r', 'transform', 'rotate(' + n2(armR) + ' ' + G.shoulder.r.join(' ') + ')');
    set('claw-l', 'transform', 'rotate(' + n2(clawL) + ' ' + G.wrist.l.join(' ') + ')');
    set('claw-r', 'transform', 'rotate(' + n2(clawR) + ' ' + G.wrist.r.join(' ') + ')');
    ['l', 'r'].forEach(function (s) {
      var v = clamp(p.pinch + (s === 'l' ? p.pinchL : p.pinchR), -1, 1), J = G.jaws;
      var top = v >= 0 ? v * J.top.close_deg : -v * J.top.open_deg;
      var bot = v >= 0 ? v * J.bottom.close_deg : -v * J.bottom.open_deg;
      set('jaw-' + s + '-top', 'transform', 'rotate(' + n2(top) + ' ' + J.top.local.join(' ') + ')');
      set('jaw-' + s + '-bottom', 'transform', 'rotate(' + n2(bot) + ' ' + J.bottom.local.join(' ') + ')');
    });

    // lens: slide along the handle, zoom about the glass, tuck away (celebrate) about the grip
    var gc = G.glass, grip = G.grip, out = clamp(p.lensOut, 0, 1);
    var lensM = mul(mul(T(L * LR.slide[0], L * LR.slide[1]), S(p.lensZoom, p.lensZoom, gc[0], gc[1])),
      S(1 - 0.35 * out, 1 - 0.35 * out, grip[0], grip[1]));
    set('lens', 'transform', str(lensM));
    op('lens', 1 - out);
    op('lens-ring', p.lensGlow);
    op('lens-wash', p.lensGlow);
    var gl = clamp(p.glint, 0, 1), sw = (2 * gl - 1) * 1.25 * G.glassR * 0.7071;
    set('lens-sweep', 'transform', 'translate(' + n2(-sw) + ' ' + n2(sw) + ')');
    op('lens-sweep', Math.sin(Math.PI * gl));
    // the magnified eye behind the glass: what is behind the lens, scaled about the glass centre
    var view = smooth(0.72, 0.96, L);
    op('lens-view', view);
    if (view > 0) {
      var W = mul(mul(R(armR, G.shoulder.r[0], G.shoulder.r[1]), R(clawR, G.wrist.r[0], G.wrist.r[1])), lensM);
      var gw = ap(W, gc);
      set('lens-eye', 'transform', str(mul(mul(inv(W), S(G.lensMag, G.lensMag, gw[0], gw[1])), eyeM.r)));
    }
    op('paper', p.paper);

    // effects
    op('sweat', p.sweat);
    set('sweat', 'transform', 'translate(0 ' + n2(3.5 * (clamp(p.sweat, 0, 1) - 1)) + ')');
    var spk = clamp(p.sparkle, 0, 1), sc = G.sparkleC;
    op('sparkle', spk * 1.6);
    set('sparkle', 'transform', str(S(0.72 + 0.34 * spk, 0.72 + 0.34 * spk, sc[0], sc[1])));
    op('bloom', p.bloom);
    set('bloom', 'transform', str(S(0.8 + 0.2 * p.bloom, 0.8 + 0.2 * p.bloom, G.bloom[0], G.bloom[1])));
    op('zzz', p.zzz);
    var ph = ((tMs || 0) % G.zzzPeriod) / G.zzzPeriod;
    for (var i = 0; i < 3; i++) {
      var q = (ph + i / 3) % 1;
      set('z' + i, 'transform', 'translate(' + n2(5 * q) + ' ' + n2(-11 * q) + ')');
      op('z' + i, Math.sin(Math.PI * q));
    }
  }

  function prefixIds(markup, prefix) {
    return markup
      .replace(/\bid="([^"]+)"/g, 'id="' + prefix + '$1"')
      .replace(/url\(#([^)]+)\)/g, 'url(#' + prefix + '$1)')
      .replace(/href="#([^"]+)"/g, 'href="#' + prefix + '$1"');
  }

  root.AlibiPinchRig = { neutral: neutral, sample: sample, sampleTrack: sampleTrack, pose: pose, apply: apply,
    prefixIds: prefixIds, ease: ease, setEasings: setEasings };
})(typeof window !== 'undefined' ? window : globalThis);
