/* moments.js: window.AlibiMoments, the web hook contract (docs/design/IMPLEMENTATION.md Appendix D).
   p16 ships no-op stubs; lane M replaces the bodies. Signatures are frozen. Classic script, loaded after pinch.js and
   before core.js, so the area scripts can call it unconditionally. */
window.AlibiMoments = {
  state(s) {},                                       // every poll, after render; drives Pinch from s.pinch
  verdict(rv, cardEl, opts = {animate: false}) {},   // after renderVerdict paints the card
  nudge(alert, s) { return false; },                 // true = moments rendered the nudge card; core.js skips the red toast
  sample(label, imgEl, dotEl) {},                    // a new sample appeared in the live strip
  sessionStart(fromEl, toEl) {},                     // composer → live card (FLIP)
  correction(sid, ts, label, dotEl, reply) {},       // after POST /api/sessions/{id}/correct succeeds
};
