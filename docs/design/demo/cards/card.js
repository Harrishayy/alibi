/* Demo card runtime: one seekable clock for DOM entrances (Web Animations, paused) and Pinch (the rig, sampled).

   Card.init({duration})                      the card's length in ms (4000)
   Card.enter(el, at, opts)                   content in at `at` ms: opacity, translateY, scale, blur -> rest
   Card.pinch(host, {size, mood, cues, blinks, lens})
                                              Pinch from docs/design/pinch: mood loop <- one-shot clips (blended
                                              in/out per clips.json policy) ; blink multiplies eyeOpen ; lens =
                                              [[ms, glow], ...] keys for the camera light
   Card.seek(ms)                              render that instant (record.py calls this once per frame)
   Card.ready                                 true once fonts and Pinch are in

   Without ?record=1 the card plays itself once in real time (preview). Reduced motion: no clips, no movement,
   entrances become 150 ms fades, Pinch holds its mood's key pose.
   Easing and durations come from tokens.css custom properties, never literals. */
(function () {
  'use strict';
  var D = window.PINCH_DATA, R = window.AlibiPinchRig;
  if (D && D.engine && !window.AlibiPinch) {
    document.write('<script src="../../pinch/pinch.js"><\/script>');   // the AlibiPinch engine, when it has landed
  }
  var q = new URLSearchParams(location.search);
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var anims = [], pinches = [], duration = 4000, uid = 0;

  function tok(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function dur(name) { return parseFloat(tok(name)) || 0; }

  function enter(el, at, o) {
    o = o || {};
    var from = { opacity: 0 }, to = { opacity: 1 };
    if (!reduce) {
      from.transform = 'translateY(' + (o.y || 0) + 'px) scale(' + (o.scale || 1) + ')';
      to.transform = 'translateY(0px) scale(1)';
      if (o.blur) { from.filter = 'blur(' + o.blur + 'px)'; to.filter = 'blur(0px)'; }
    }
    var a = el.animate([from, to], {
      delay: at, fill: 'both',
      duration: reduce ? 150 : (o.dur || dur('--dur-medium')),
      easing: reduce ? 'ease' : (o.easing || tok('--ease-out'))
    });
    a.pause();
    anims.push(a);
    return a;
  }

  function Pinch(host, o) {
    this.o = o;
    var markup = D.svg;
    try { if (window.AlibiPinch && typeof window.AlibiPinch.svg === 'function') markup = window.AlibiPinch.svg() || markup; }
    catch (e) { markup = D.svg; }
    host.innerHTML = R.prefixIds(markup, 'c' + (uid++) + '-');
    this.svg = host.querySelector('svg');
    this.svg.setAttribute('width', o.size);
    this.svg.setAttribute('height', o.size);
    this.svg.classList.add('on-dark');
    this.mood = D.clips.moods[o.mood || 'idle'];
    this.cues = reduce ? [] : (o.cues || []);
    this.blinks = reduce ? [] : (o.blinks || []);
    this.lens = o.lens || null;
  }
  Pinch.prototype.render = function (t) {
    var C = D.clips, pol = C.policy, p = R.neutral(D.rig), k, s;
    s = R.sample(this.mood, reduce ? (this.mood.key || 0) : t);
    for (k in s) p[k] = s[k];
    var drivesEyes = false;
    for (var i = 0; i < this.cues.length; i++) {
      var cue = this.cues[i], def = C.clips[cue.clip], local = t - cue.at;
      if (local < 0 || local > def.dur + pol.blend_out_ms) continue;
      var w = Math.min(1, local / pol.blend_in_ms);
      if (local > def.dur) w *= Math.max(0, 1 - (local - def.dur) / pol.blend_out_ms);
      s = R.sample(def, Math.min(local, def.dur));
      for (k in s) {
        if (typeof s[k] === 'number' && typeof p[k] === 'number') p[k] += (s[k] - p[k]) * w;
        else if (w >= 0.5) p[k] = s[k];
      }
      if (w > 0 && ('eyeOpen' in s || 'joy' in s)) drivesEyes = true;
    }
    if (!drivesEyes) {
      for (var b = 0; b < this.blinks.length; b++) {
        var bl = t - this.blinks[b];
        if (bl >= 0 && bl <= C.blink.dur) p.eyeOpen *= R.sample(C.blink, bl).eyeOpen;
      }
    }
    if (this.lens) {
      var L = this.lens, g = L[0][1];
      for (var j = 1; j < L.length; j++) {
        if (t >= L[j][0]) { g = L[j][1]; continue; }
        if (t > L[j - 1][0]) {
          var e = (t - L[j - 1][0]) / (L[j][0] - L[j - 1][0]);
          g = L[j - 1][1] + (L[j][1] - L[j - 1][1]) * (reduce ? 1 : R.ease('in-out', e, L[j][0] - L[j - 1][0]));
        }
        break;
      }
      p.lensGlow = Math.max(p.lensGlow || 0, g);
    }
    R.apply(this.svg, p, D.rig, t);
  };

  function seek(t) {
    t = Math.max(0, Math.min(duration, t));
    for (var i = 0; i < anims.length; i++) anims[i].currentTime = t;
    for (var j = 0; j < pinches.length; j++) pinches[j].render(t);
  }

  var Card = window.Card = {
    ready: false,
    reduce: reduce,
    init: function (o) { duration = (o && o.duration) || duration; R.setEasings(D.clips.easings); },
    enter: enter,
    pinch: function (host, o) { var p = new Pinch(host, o); pinches.push(p); p.render(0); return p; },
    seek: seek,
    start: function () {
      seek(0);
      document.fonts.ready.then(function () {
        Card.ready = true;
        if (q.get('record')) return;
        var t0 = performance.now();
        (function frame(now) {
          var t = now - t0;
          seek(t);
          if (t < duration) requestAnimationFrame(frame);
        })(t0);
      });
    }
  };
})();
