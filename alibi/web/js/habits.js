/* habits.js: the "Your habits" sheet (#habitsSheet).
   A full-page sheet over the dashboard: one card per habit that expands in place, a "Your usual week" ribbon that
   re-plans live from the drafts, and a save sequence (the card folds, Pinch nods, the receipt ticks in as each fact is
   proven by a GET). One habit per write: re-read GET /api/habits, change only this key (order kept), PUT the whole map,
   so a habit added elsewhere meanwhile is never dropped. Adding is one POST /api/habits/add. Every write sends
   X-Alibi-Client: dashboard; undo sends X-Alibi-Intent: undo. Works against an old daemon (no `saved` in the reply):
   the line is built here and the island and agent chips are left out.
   window.openHabits(key?, draft?) opens it (draft = {name, check, minutes} prefills a custom habit);
   window.AlibiHabits = {open, close, isOpen}. Classic script, one IIFE; loads after onboarding.js, before boot.js. */
(function () {
  "use strict";
  if (window.AlibiHabits) return;

  /* ---------- helpers ---------- */
  const q = (s, r) => (r || document).querySelector(s);
  const qa = (s, r) => [...(r || document).querySelectorAll(s)];
  const RM = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cssv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const tok = (n, d) => parseFloat(cssv(n)) || d;
  const ease = (n, d) => cssv(n) || d || "ease-out";
  const E = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const quiet = () => { try { return localStorage.getItem("alibi.quiet") === "1"; } catch { return false; } };
  const icon = (n, s) => (window.AlibiIcons && window.AlibiIcons.svg(n, s || 20)) || "";
  const MINUS = s => `<svg class="al-icon" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true" focusable="false"><path d="M5 12h14"/></svg>`;
  const clone = o => o == null ? o : JSON.parse(JSON.stringify(o));
  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  const P2 = n => String(n).padStart(2, "0");
  const nowS = () => Date.now() / 1000;
  const st = () => (typeof lastState !== "undefined" ? lastState : null);
  const call = (name, ...a) => { try { const f = window[name] || (typeof globalThis[name] === "function" ? globalThis[name] : null); if (typeof f === "function") return f(...a); } catch {} return undefined; };

  const WD = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
  const WD1 = {mon: "M", tue: "T", wed: "W", thu: "T", fri: "F", sat: "S", sun: "S"};
  const WD3 = {mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun"};
  const WDN = {mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday", fri: "Friday", sat: "Saturday", sun: "Sunday"};
  const C2M = {camera: "physical", screen: "digital", both: "hybrid"}, M2C = {physical: "camera", digital: "screen", hybrid: "both"};
  const CHECK_LONG = [["camera", "Camera on my desk"], ["screen", "What's on my screen"], ["both", "Both"]];
  const CHECK_SHORT = {camera: "Camera", screen: "Screen", both: "Camera and screen", strava: "Strava", health: "Apple Health"};
  const GLYPH = {camera: "camera", screen: "laptop", both: "eye", strava: "run", health: "heart"};
  const METRICS = {
    steps: {unit: "steps", per: "steps a day", step: 500, min: 500, max: 100000, def: 8000},
    sleep_h: {unit: "h", per: "hours a night", step: 0.5, min: 0.5, max: 16, def: 7},
    mindful_min: {unit: "min", per: "min a day", step: 5, min: 1, max: 600, def: 10},
    workout_min: {unit: "min", per: "min a day", step: 5, min: 5, max: 600, def: 30},
  };
  const TPL_HEALTH = {steps: "steps", sleep: "sleep_h", meditate: "mindful_min"};
  // The story Alibi is built around (a student who draws, plays piano, cooks): one client preset on top of the server's custom template.
  const PRESETS = [{id: "cook", base: "custom", title: "Cook", label: "Cooking", check: "camera", minutes: 30,
    blurb: "A real meal, start to finish.", schedule: [{days: ["sun"], at: "18:00", min: 30}]}];
  const CHECKINS = [["07:30", "Morning check-in"], ["12:00", "Next check-in"], ["16:00", "Next check-in"], ["20:00", "Next check-in"], ["22:00", "Night review"]];
  const NEW = "+new";

  const hm = t => /^([01]?\d|2[0-3]):([0-5]\d)$/.exec(String(t || "").trim());
  const toMin = t => { const m = hm(t); return m ? +m[1] * 60 + +m[2] : null; };
  const fromMin = n => `${P2(Math.floor(n / 60))}:${P2(n % 60)}`;
  const fmtHM = min => { min = Math.round(min || 0); const h = Math.floor(min / 60), m = min % 60; return h ? `${h}h${m ? " " + m + "m" : ""}` : `${m} min`; };
  const spokenHM = min => { min = Math.round(min || 0); const h = Math.floor(min / 60), m = min % 60; return [h ? `${h} hour${h === 1 ? "" : "s"}` : "", m || !h ? `${m} minute${m === 1 ? "" : "s"}` : ""].filter(Boolean).join(" "); };
  const fmtN = n => Number(n || 0).toLocaleString("en-GB", {maximumFractionDigits: 1});
  const byWD = (a, b) => WD.indexOf(a) - WD.indexOf(b);
  function daysText(days) {
    const d = WD.filter(x => (days || []).includes(x));
    if (d.length === 7) return "Every day";
    if (d.join() === "mon,tue,wed,thu,fri") return "Weekdays";
    if (d.join() === "sat,sun") return "Weekends";
    return d.map(x => WD3[x]).join(", ");
  }
  const habitLcW = h => /^[A-Z][a-z]+( [a-z]+)*$/.test(h) ? h.toLowerCase() : h;
  const kindOf = h => h && h.source === "strava" ? "strava" : h && h.source === "health" ? "health" : "watch";
  const checkOf = h => M2C[h && h.modality] || (h && h.check) || "camera";
  const titleCase = k => String(k || "").replace(/_/g, " ").replace(/^./, c => c.toUpperCase());
  function nameOf(key, h) {
    h = h || (S.cfg && S.cfg.habits && S.cfg.habits[key]) || {};
    return h.label || h.display || (S.view[key] && S.view[key].label) || (typeof hname === "function" ? hname(key) : titleCase(key));
  }
  const glyphOf = d => d.kind === "strava" ? "run" : d.kind === "health" ? (d.metric === "sleep_h" ? "moon" : "heart") : GLYPH[d.check] || "camera";
  const planned = sched => (sched || []).reduce((a, r) => a + ((r.days || []).length * (+r.min || 0)), 0);
  const rowOk = r => (r.days || []).length && hm(r.at) && +r.min >= 1 && +r.min <= 240;
  const cleanSched = sched => (sched || []).filter(rowOk).map(r => ({days: WD.filter(x => r.days.includes(x)), at: fromMin(toMin(r.at)), min: Math.round(+r.min)}));
  const photoLine = () => { try { return typeof photoWhere === "function" ? photoWhere() : ""; } catch { return ""; } };
  const howText = c => ({camera: `A photo every minute while you're at it. ${photoLine()}`.trim(),
    screen: "Alibi notes which app or website is in front. Nothing else.",
    both: "A minute counts if the camera or your screen shows you at it."})[c] || "";

  /* ---------- state ---------- */
  const S = {
    el: null, open: false, cfg: null, order: [], view: {}, tpls: [], phone: null, err: null,
    drafts: {}, openKey: null, add: null, grid: false, busy: false, opener: null,
    pinch: null, line: "", rc: null, snack: null, confirm: false, focusField: null, lastSig: "",
  };

  /* ---------- network ---------- */
  async function getJSON(path) { const r = await fetch(path, {cache: "no-store"}); if (!r.ok) throw Object.assign(new Error(String(r.status)), {status: r.status}); return r.json(); }
  const HDR = intent => Object.assign({"Content-Type": "application/json", "X-Alibi-Client": "dashboard"}, intent ? {"X-Alibi-Intent": intent} : {});
  function httpErr(status, j) { return Object.assign(new Error(typeof (j && j.detail) === "string" ? j.detail : String(status)), {status, http: true}); }
  // Re-read, change only what `mutate` touches (key order kept), write the whole map back.
  async function commit(mutate, intent) {
    const fresh = await getJSON("/api/habits");
    const before = clone(fresh.habits || {});
    const after = mutate(clone(fresh.habits || {}));
    const r = await fetch("/api/habits", {method: "PUT", headers: HDR(intent), body: JSON.stringify({habits: after})});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw httpErr(r.status, j);
    return {before, cfg: j, saved: j.saved || null};
  }
  function insertAt(map, key, entry, idx) {
    const out = {}, keys = Object.keys(map).filter(k => k !== key);
    keys.splice(clamp(idx, 0, keys.length), 0, key);
    keys.forEach(k => { out[k] = k === key ? entry : map[k]; });
    return out;
  }
  const planWeek = () => getJSON("/api/calendar/plan?days=7").then(j => j.blocks || []).catch(() => null);
  const calStatus = () => getJSON("/api/calendar/status").catch(() => null);

  async function load() {
    const [cfg, view, tpl, integ] = await Promise.allSettled([getJSON("/api/habits"), getJSON("/api/habits/view"),
      getJSON("/api/onboarding/templates"), getJSON("/api/integrations")]);
    if (cfg.status !== "fulfilled") throw cfg.reason || new Error("offline");
    setCfg(cfg.value);
    if (view.status === "fulfilled") S.view = Object.fromEntries((view.value.habits || []).map(h => [h.key, h]));
    if (tpl.status === "fulfilled") S.tpls = tpl.value.templates || [];
    S.phone = integ.status === "fulfilled" ? !!(integ.value.phone && integ.value.phone.enabled) : null;
  }
  function setCfg(cfg) {
    const c = Object.assign({}, cfg); delete c.saved;
    S.cfg = c; S.order = Object.keys(c.habits || {});
  }

  /* ---------- drafts ---------- */
  function draftOf(key, h) {
    h = h || {};
    const kind = kindOf(h);
    const d = {key, kind, isNew: false, label: h.label || h.display || nameOf(key, h), sched: clone(h.schedule || []),
      calendar: h.calendar !== false, touched: {}};
    if (kind === "watch") Object.assign(d, {check: checkOf(h), goal: +h.weekly_target_min || 0, len: +h.default_min || 25,
      shield: h.phone_shield !== false, aliases: (h.aliases || []).join(", "), looks: h.on_task_looks_like || ""});
    else if (kind === "strava") Object.assign(d, {runs: +h.weekly_sessions || 3, km: h.min_km == null ? 5 : +h.min_km});
    else Object.assign(d, {metric: h.metric || "steps", target: +h.daily_target || (METRICS[h.metric] || METRICS.steps).def});
    return d;
  }
  function newDraft(t, pre) {
    const kind = t.check === "strava" ? "strava" : t.check === "health" ? "health" : "watch";
    const d = {key: NEW, kind, isNew: true, tid: t.base || t.id, preset: t.base ? t.id : null, ask: t.ask_name || (t.base ? "" : null),
      label: t.ask_name ? "" : (t.label || t.title || ""), sched: clone(t.schedule || []), calendar: true, touched: {}};
    if (kind === "watch") {
      const len = +(pre && pre.minutes) || +t.minutes || 25;
      d.sched.forEach(r => { r.min = len; });
      Object.assign(d, {check: (pre && pre.check) || t.check || "camera", len, goal: 0, shield: true, aliases: "", looks: ""});
      d.goal = planned(d.sched) || len * 4;
    } else if (kind === "strava") Object.assign(d, {runs: 3, km: 5, label: "Running"});
    else { const m = TPL_HEALTH[t.id] || "steps"; Object.assign(d, {metric: m, target: METRICS[m].def, label: ({steps: "Steps", sleep: "Sleep", meditate: "Meditate"})[t.id] || d.label}); if (m !== "mindful_min") d.sched = []; }
    if (pre && pre.name) d.label = String(pre.name).slice(0, 24);
    return d;
  }
  const sig = d => d ? JSON.stringify([d.label, d.check, d.goal, d.len, d.shield, d.aliases, d.looks, d.runs, d.km, d.target, d.calendar,
    (d.sched || []).map(r => [WD.filter(x => (r.days || []).includes(x)).join(""), r.at, +r.min])]) : "";
  const dirty = key => { if (key === NEW) return !!S.add; const d = S.drafts[key]; return !!d && sig(d) !== sig(draftOf(key, S.cfg.habits[key])); };
  const draftFor = key => key === NEW ? (S.add && S.add.d) : S.drafts[key];
  function toEntry(d, prev) {
    const e = clone(prev) || {};
    const label = String(d.label || "").trim().slice(0, 24);
    const sched = cleanSched(d.sched);
    const shown = prev ? nameOf(d.key, prev) : "";
    const renamed = !!label && label !== shown;
    if (d.kind === "watch") {
      if (label && (renamed || e.label)) e.label = label;
      e.modality = C2M[d.check] || e.modality || "physical";
      delete e.check;
      e.default_min = clamp(Math.round(+d.len || 25), 1, 240);
      e.weekly_target_min = Math.max(0, Math.round(+d.goal || 0));
      if (d.touched.shield || "phone_shield" in e) e.phone_shield = !!d.shield;
      let al = d.touched.aliases ? String(d.aliases || "").split(",").map(a => a.trim()).filter(Boolean) : (e.aliases || []);
      if (renamed && !al.map(a => String(a).toLowerCase()).includes(label.toLowerCase())) al = [...al, label.toLowerCase()];
      e.aliases = al;
      if (d.touched.looks) e.on_task_looks_like = String(d.looks || "").trim() || e.on_task_looks_like;
    } else if (d.kind === "strava") {
      if (label && (renamed || e.label)) e.label = label;
      e.weekly_sessions = clamp(Math.round(+d.runs || 3), 1, 14);
      e.min_km = Math.max(0, Math.round((+d.km || 0) * 2) / 2);
    } else {
      if (label && (renamed || e.display)) { e.display = label; if (e.label) e.label = label; }
      e.daily_target = d.metric === "sleep_h" ? Math.round(+d.target * 2) / 2 : Math.round(+d.target);
    }
    if (sched.length) { e.schedule = sched; e.calendar = !!d.calendar; }
    else { delete e.schedule; if ("calendar" in e) e.calendar = !!d.calendar; }
    return e;
  }
  function validate(d) {
    const label = String(d.label || "").trim();
    if (!label) return {field: "label", text: d.ask ? `${d.ask.replace(/\?$/, "")}: type a name first.` : "Give the habit a name."};
    if (d.isNew) {
      const taken = Object.keys(S.cfg.habits || {}).find(k => nameOf(k).toLowerCase() === label.toLowerCase() || k === slug(label));
      if (taken) return {field: "label", text: `You already have ${nameOf(taken)}.`};
    } else {
      const other = Object.keys(S.cfg.habits || {}).find(k => k !== d.key && nameOf(k).toLowerCase() === label.toLowerCase());
      if (other) return {field: "label", text: `You already have ${nameOf(other)}.`};
    }
    for (let i = 0; i < (d.sched || []).length; i++) {
      const r = d.sched[i];
      if (!(r.days || []).length) return {field: "days", row: i, text: "Pick at least one day for this time."};
      if (!hm(r.at)) return {field: "at", row: i, text: "Use a 24-hour time, like 18:30."};
      if (!(+r.min >= 1 && +r.min <= 240)) return {field: "min", row: i, text: "A planned session runs 1 to 240 min."};
    }
    if ((d.sched || []).length > 14) return {field: "when", text: "Up to 14 times per habit."};
    if (d.kind === "watch") {
      if (!(+d.len >= 1 && +d.len <= 240)) return {field: "len", text: "Usual length is 1 to 240 min."};
      if (!(+d.goal >= 0 && +d.goal <= 3000)) return {field: "goal", text: "Weekly goal is 0 to 3,000 min."};
    }
    if (d.kind === "health" && !(+d.target > 0)) return {field: "target", text: "The daily goal needs to be more than 0."};
    if (d.kind === "health" && d.metric === "sleep_h" && +d.target > 16) return {field: "target", text: "That's more sleep than a day holds. Try 7."};
    return null;
  }
  const slug = t => (String(t || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").replace(/^(\d)/, "habit_$1") || "habit").slice(0, 24).replace(/_+$/, "");
  // A 400 detail, minus its "key: " prefix, goes to the field it names.
  function mapErr(detail, d) {
    const msg = String(detail || "").replace(/^[a-z][a-z0-9_]*: /, "");
    if (/is already one of your habits/.test(msg)) return {field: "label", text: `You already have ${msg.replace(/ is already one of your habits\.?$/, "")}.`};
    if (/habit name/.test(msg)) return {field: "label", text: "Use letters and numbers in the name."};
    if (/Give the habit a name/.test(msg)) return {field: "label", text: "Give the habit a name."};
    if (/isn't a time/.test(msg)) return {field: "at", row: firstBad(d, r => !hm(r.at)), text: "Use a 24-hour time, like 18:30."};
    if (/planned length must be/.test(msg)) return {field: "min", row: firstBad(d, r => !(+r.min >= 1 && +r.min <= 240)), text: "A planned session runs 1 to 240 min."};
    if (/pick at least one day|isn't a day/.test(msg)) return {field: "days", row: firstBad(d, r => !(r.days || []).length), text: "Pick at least one day for this time."};
    if (/schedule must be a list|each planned time needs/.test(msg)) return {field: "when", text: "Each time needs days, a time and minutes. Up to 14 times."};
    const num = /(default_min|weekly_target_min|weekly_sessions|min_km|daily_target) must be a number/.exec(msg);
    if (num) return {field: ({default_min: "len", weekly_target_min: "goal", weekly_sessions: "runs", min_km: "km", daily_target: "target"})[num[1]], text: "That needs to be a number."};
    if (/daily target must be more than 0|hours of sleep/.test(msg)) return {field: "target", text: msg.replace(/ — /g, ". ")};
    if (/choose how Alibi checks it/.test(msg)) return {field: "check", text: "Choose how Alibi checks it."};
    if (/need at least one habit/.test(msg)) return {field: null, text: "Keep at least one habit."};
    return {field: null, text: msg || "That didn't save."};
  }
  const firstBad = (d, f) => Math.max(0, (d && d.sched || []).findIndex(f));

  /* ---------- copy built here only when the daemon is too old to send saved.line ---------- */
  function clientLine(before, after, key) {
    const H = nameOf(key, after), h = habitLcW(H);
    if (!before) return `Noted. ${H} is on your list.`;
    const bs = cleanSched(before.schedule), as = cleanSched(after.schedule);
    if ((before.label || "") !== (after.label || "") && after.label) return `Noted. ${H} it is.`;
    if (checkOf(before) !== checkOf(after) && kindOf(after) === "watch") return ({camera: `Noted. I'll use the desk camera for ${h} now.`, screen: `Noted. I'll watch your screen for ${h} now.`, both: `Noted. I'll check camera and screen for ${h} now.`})[checkOf(after)];
    if (JSON.stringify(bs) !== JSON.stringify(as)) {
      if (!as.length) return `Noted. ${H} has no set time now.`;
      const days = new Set(as.flatMap(r => r.days));
      if (as.length === 1 && bs.length === 1 && bs[0].days.join() === as[0].days.join() && bs[0].at !== as[0].at) return `Noted. ${H} moves to ${as[0].at}.`;
      return `Noted. ${H} is ${days.size} day${days.size === 1 ? "" : "s"} a week now.`;
    }
    if ((before.weekly_target_min || 0) !== (after.weekly_target_min || 0)) return `Noted. ${after.weekly_target_min} minutes a week for ${h}.`;
    if ((before.default_min || 0) !== (after.default_min || 0)) return `Noted. ${H} sessions are ${after.default_min} minutes now.`;
    if ((before.phone_shield !== false) !== (after.phone_shield !== false)) return after.phone_shield === false ? `Noted. Your iPhone stays open during ${h}.` : `Noted. Your iPhone blocks distractions during ${h}.`;
    if ((before.calendar !== false) !== (after.calendar !== false)) return after.calendar === false ? `Noted. ${H} stays off Apple Calendar.` : `Noted. ${H} goes in Apple Calendar.`;
    return `Noted. ${H} is updated.`;
  }
  function openLine() {
    const hs = S.cfg && S.cfg.habits || {};
    if (!Object.keys(hs).length) return "No habits yet. Pick one and I'll start watching.";
    const gaps = Object.entries(hs).filter(([, h]) => kindOf(h) === "watch" && (h.schedule || []).length && planned(h.schedule) < (+h.weekly_target_min || 0));
    if (gaps.length > 1) return `${gaps.length} habits plan fewer minutes than their goals.`;
    if (gaps.length === 1) return `${nameOf(gaps[0][0])} plans fewer minutes than its goal.`;
    return "Change anything. I'll re-plan around it.";
  }

  /* ---------- motion ---------- */
  function flip(nodes, mutate, t = "--spring-smooth") {
    const list = [...nodes].filter(n => n && n.isConnected);
    const first = new Map(list.map(n => [n, n.getBoundingClientRect()]));
    mutate();
    if (RM()) return;
    const dur = tok(t + "-dur", 686), ez = ease(t);
    for (const n of list) {
      if (!n.isConnected) continue;
      const a = first.get(n), b = n.getBoundingClientRect(), dx = a.left - b.left, dy = a.top - b.top;
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue;
      if (n._flip) n._flip.cancel();
      n._flip = n.animate([{transform: `translate(${dx}px,${dy}px)`}, {transform: "none"}], {duration: dur, easing: ez});
    }
  }
  function enter(els, delay = 0, step = 40, y = 6) {
    els.forEach((el, i) => {
      if (!el) return;
      if (RM()) { el.animate([{opacity: 0}, {opacity: 1}], {duration: 150, delay, easing: "ease", fill: "backwards"}); return; }
      el.animate([{opacity: 0, transform: `translateY(${y}px)`, filter: "blur(4px)"}, {opacity: 1, transform: "none", filter: "blur(0)"}],
        {duration: tok("--dur-medium", 260), delay: delay + step * Math.min(i, 5), easing: ease("--ease-out"), fill: "backwards"});
    });
  }
  function pop(el, delay = 0) {
    if (!el) return;
    if (RM()) { el.animate([{opacity: 0}, {opacity: 1}], {duration: 150, delay, easing: "ease", fill: "backwards"}); return; }
    el.animate([{opacity: 0, transform: "scale(0.94)"}, {opacity: 1, transform: "none"}],
      {duration: tok("--spring-snappy-dur", 484), delay, easing: ease("--spring-snappy"), fill: "backwards"});
  }
  function blurSwap(el, html) {
    if (!el || el.innerHTML === html) return;
    if (RM()) { el.innerHTML = html; el.animate([{opacity: 0}, {opacity: 1}], {duration: 150, easing: "ease"}); return; }
    const out = el.animate([{opacity: 1, filter: "blur(0)"}, {opacity: 0, filter: "blur(4px)"}], {duration: 120, easing: ease("--ease-out"), fill: "forwards"});
    out.onfinish = () => { el.innerHTML = html; out.cancel(); el.animate([{opacity: 0, filter: "blur(4px)"}, {opacity: 1, filter: "blur(0)"}], {duration: tok("--dur-medium", 260), easing: ease("--ease-out")}); };
  }
  // Digit ticker (Motion.md): each digit is a 0-9 reel in a 1em window; same-shape updates roll, others blur-swap.
  function roll(el, text) {
    if (!el) return;
    text = String(text);
    const prev = el.dataset.v;
    if (prev === text) return;
    el.dataset.v = text; el.setAttribute("aria-label", text); el.classList.add("al-roll");
    const shape = s => String(s).replace(/\d/g, "0");
    if (prev != null && shape(prev) === shape(text) && !RM()) {
      const reels = qa(".al-roll__reel", el); let i = 0;
      for (const ch of text) if (/\d/.test(ch)) { const r = reels[i++]; if (r) r.style.transform = `translateY(${-ch}em)`; }
      return;
    }
    const html = `<span class="al-roll__vis" aria-hidden="true">${[...text].map(ch => /\d/.test(ch)
      ? `<span class="al-roll__col"><span class="al-roll__reel" style="transform:translateY(${-ch}em)">${"0123456789".split("").map(n => `<span>${n}</span>`).join("")}</span></span>`
      : `<span class="al-roll__sym">${E(ch)}</span>`).join("")}</span>`;
    if (prev == null) el.innerHTML = html; else blurSwap(el, html);
  }

  /* ---------- Pinch (one per view: the sheet is opaque and full-page) ---------- */
  function baseMood() { const s = st(), m = s && s.pinch && s.pinch.mood; return s && s.session && (m === "focused" || m === "sleepy") ? m : "idle"; }
  function mountPinch() {
    const host = S.el && q(".hs-pinch", S.el);
    if (!host || S.pinch || !window.AlibiPinch) return;
    try {
      S.pinch = window.AlibiPinch.mount(host, {size: 64, mood: baseMood(), theme: "auto", ambient: true});
      const s = st(); S.pinch.camera(!!(s && s.session && s.session.modality !== "digital" && !s.session.on_break));
    } catch { S.pinch = null; }
  }
  function pinchMood(m) { if (S.pinch) S.pinch.set(m || baseMood()); }
  function pinchPlay(clip) { if (!S.pinch || quiet()) return; try { S.pinch.play(clip); } catch {} }
  function gazeAt(el) {
    if (!S.pinch || !el || RM()) return;
    const host = q(".hs-pinch", S.el); if (!host) return;
    const a = host.getBoundingClientRect(), b = el.getBoundingClientRect();
    S.pinch.lookAt(clamp(((b.left + b.width / 2) - (a.left + a.width / 2)) / 480, -1, 1), clamp(((b.top + b.height / 2) - (a.top + a.height / 2)) / 480, -1, 1));
  }
  function say(line, source) {
    const p = S.el && q(".hs-line", S.el);
    if (!line || !p) return;
    S.line = line;
    const src = S.el && q(".hs-src", S.el);
    if (src) src.textContent = source || "";
    if (p.textContent === line) return;
    if (RM() || !p.textContent) { p.textContent = line; p.animate([{opacity: 0}, {opacity: 1}], {duration: RM() ? 150 : tok("--dur-medium", 260), easing: "ease"}); return; }
    const out = p.animate([{opacity: 1, transform: "none"}, {opacity: 0, transform: "translateY(-4px)"}], {duration: 120, easing: ease("--ease-out"), fill: "forwards"});
    out.onfinish = () => { p.textContent = line; out.cancel(); p.animate([{opacity: 0, transform: "translateY(4px)"}, {opacity: 1, transform: "none"}], {duration: tok("--dur-medium", 260), easing: ease("--ease-out")}); };
  }

  /* ---------- markup ---------- */
  function sumParts(d) {
    const sched = cleanSched(d.sched);
    const when = sched.length ? sched.map(r => `${daysText(r.days)} at ${r.at}`).join("; ") : (d.kind === "health" ? (d.metric === "sleep_h" ? "every night" : "every day") : "No set time");
    if (d.kind === "strava") return [["check", "Strava"], ["when", when], ["goal", `${fmtN(d.km)} km or more`]];
    if (d.kind === "health") return [["check", "Apple Health"], ["when", when]];
    return [["check", CHECK_SHORT[d.check] || "Camera"], ["when", when], ["len", `${d.len} min`]];
  }
  const sumHTML = d => sumParts(d).map(([k, t]) => `<span data-frag="${k}">${E(t)}</span>`).join(`<span class="hs-dot" aria-hidden="true"> · </span>`);
  function statOf(d) {
    if (d.kind === "strava") return [String(d.runs), `run${+d.runs === 1 ? "" : "s"} a week`];
    if (d.kind === "health") { const M = METRICS[d.metric] || METRICS.steps; return [fmtN(d.target), M.per]; }
    return [String(Math.round(+d.goal || 0)), "min a week"];
  }
  const cardId = key => key === NEW ? "new" : key;
  const liveKey = () => { const s = st(); return s && s.session ? s.session.habit : null; };
  function cardHTML(key) {
    const isNew = key === NEW, d = draftFor(key) || draftOf(key, S.cfg.habits[key]), open = S.openKey === key, id = cardId(key);
    const [n, unit] = statOf(d);
    const name = String(d.label || "").trim() || (isNew ? (d.ask ? "New habit" : "New habit") : nameOf(key));
    return `<article class="hs-card${open ? " is-open" : ""}${isNew ? " is-new" : ""}${!isNew && dirty(key) ? " is-dirty" : ""}" data-key="${E(key)}">
      <button type="button" class="hs-row" id="hs-r-${E(id)}" aria-expanded="${open}" aria-controls="hs-p-${E(id)}">
        <span class="hs-glyph" aria-hidden="true">${icon(glyphOf(d), 20)}</span>
        <span class="hs-name"><b><span class="hs-nm">${E(name)}</span><span class="hs-unsaved">Unsaved</span></b><small class="hs-sum">${sumHTML(d)}</small></span>
        <span class="hs-stat"><b class="hs-statn" data-n="${E(n)}"></b><small>${E(unit)}</small></span>
        <span class="hs-chev" aria-hidden="true">${icon("chevron-right", 16)}</span>
      </button>
      ${open ? panelHTML(key, d) : `<div class="hs-panel" id="hs-p-${E(id)}" hidden></div>`}
    </article>`;
  }
  function stepper(f, val, unit, label, o = {}) {
    return `<span class="hs-step" role="group" aria-label="${E(label)}">
      <button type="button" class="hs-sb" data-step="${f}" data-dir="-1" aria-label="Less">${MINUS(16)}</button>
      <input class="hs-num" type="number" inputmode="decimal" data-f="${f}" value="${E(val)}" min="${o.min ?? 0}" max="${o.max ?? 3000}" step="${o.step ?? 1}" aria-label="${E(label)}${unit ? ", " + E(unit) : ""}">
      <button type="button" class="hs-sb" data-step="${f}" data-dir="1" aria-label="More">${icon("plus", 16)}</button>
      ${unit ? `<span class="hs-unit">${E(unit)}</span>` : ""}</span>`;
  }
  const sw = (f, on, label, o = {}) => `<button type="button" class="hs-sw" role="switch" data-sw="${f}" aria-checked="${!!on}"${o.disabled ? " disabled" : ""}><span class="hs-sw__track" aria-hidden="true"><span class="hs-sw__knob"></span></span><span class="hs-sw__l">${E(label)}</span></button>`;
  function rowsHTML(d) {
    const rows = d.sched || [];
    return `<div class="hs-rows">${rows.map((r, i) => `<div class="hs-srow" data-row="${i}">
        <span class="hs-days" role="group" aria-label="Days">${WD.map(x => `<button type="button" class="hs-dayb" data-day="${x}" aria-pressed="${(r.days || []).includes(x)}" aria-label="${WDN[x]}">${WD1[x]}</button>`).join("")}</span>
        <input class="hs-time" type="time" data-rf="at" value="${E(r.at || "19:00")}" aria-label="Time">
        <span class="hs-minbox"><input class="hs-num hs-num--sm" type="number" inputmode="numeric" data-rf="min" min="1" max="240" value="${E(r.min ?? d.len ?? 25)}" aria-label="Minutes"><span class="hs-unit">min</span></span>
        <button type="button" class="hs-qbtn hs-rowdel" data-rowdel="${i}" aria-label="Remove this time">${icon("x", 16)}</button>
        <span class="hs-presets">${[["mon,tue,wed,thu,fri", "Weekdays"], ["mon,tue,wed,thu,fri,sat,sun", "Every day"], ["sat,sun", "Weekends"]].map(([v, t]) => `<button type="button" class="hs-link" data-preset="${v}">${t}</button>`).join(`<span aria-hidden="true">·</span>`)}</span>
      </div>`).join("")}
      ${rows.length ? "" : `<p class="hs-help">No times yet. Add one and it goes on your Today list.</p>`}</div>
      <div class="hs-whenfoot">${rows.length < 14 ? `<button type="button" class="hs-qbtn hs-addtime" data-rowadd="1">${icon("plus", 16)}<span>Add a time</span></button>` : ""}<p class="hs-clash" aria-live="polite"></p></div>`;
  }
  function coverHTML(d) {
    if (d.kind !== "watch") return "";
    const p = planned(cleanSched(d.sched)), g = Math.round(+d.goal || 0);
    if (!(d.sched || []).length) return "";
    const frac = g ? Math.min(1, p / g) : 1, full = p >= g;
    const gap = Math.max(0, g - p);
    return `<div class="hs-cover">
      <span class="al-meter al-meter--${full ? "done" : "partial"} is-settled hs-meter" role="meter" aria-valuemin="0" aria-valuemax="${g}" aria-valuenow="${p}" aria-label="Planned ${p} of ${g} minutes a week"><span class="al-meter__track"><span class="al-meter__fill" style="transform:scaleX(${frac.toFixed(3)})"></span></span></span>
      <p class="hs-help"><b>Planned ${p} of ${g} min a week.</b> ${full ? "Your times cover the goal." : `${gap} min a week aren't on the plan yet, so pace reads off track.`}</p>
      ${full ? "" : `<div class="hs-acts"><button type="button" class="al-btn al-btn--secondary al-btn--sm" data-fill="1">Fill the gap</button><button type="button" class="al-btn al-btn--quiet al-btn--sm" data-goalfit="1">Make ${p} min the goal</button></div>`}
    </div>`;
  }
  function panelHTML(key, d) {
    const id = cardId(key), live = !d.isNew && liveKey() === key;
    const f = (label, body, sec, forId) => `<div class="hs-f" data-sec="${sec}">${label ? (forId ? `<label class="hs-l" for="${forId}">${E(label)}</label>` : `<span class="hs-l">${E(label)}</span>`) : `<span class="hs-l" aria-hidden="true"></span>`}<div class="hs-v">${body}<p class="hs-err" role="alert" id="hs-e-${E(id)}-${sec}"></p></div></div>`;
    const nameLabel = d.isNew && d.ask ? d.ask : "Name";
    const ph = d.isNew && d.tid === "instrument" ? "Piano" : d.isNew && d.tid === "custom" ? "Cooking" : "";
    let h = live ? `<p class="hs-note">${icon("clock", 16)}<span>Running now. Changes apply from the next session.</span></p>` : "";
    h += f(nameLabel, `<input class="hs-in" id="hs-name-${E(id)}" type="text" data-f="label" maxlength="24" autocomplete="off" spellcheck="false" value="${E(d.label)}"${ph ? ` placeholder="${E(ph)}"` : ""}>`, "label", `hs-name-${E(id)}`);
    if (d.kind === "watch") {
      h += f("Checked by", `<span class="hs-seg" role="radiogroup" aria-label="Checked by">${CHECK_LONG.map(([c, t]) => `<button type="button" role="radio" class="hs-segb" data-check="${c}" aria-checked="${d.check === c}" tabindex="${d.check === c ? 0 : -1}">${E(t)}</button>`).join("")}</span><p class="hs-help hs-how">${E(howText(d.check))}</p>`, "check");
      h += f("Weekly goal", `<div class="hs-pair">${stepper("goal", Math.round(+d.goal || 0), "min a week", "Weekly goal", {min: 0, max: 3000, step: 15})}<span class="hs-pairl">Usual length</span>${stepper("len", d.len, "min", "Usual length", {min: 1, max: 240, step: 5})}</div>`, "goal");
    } else if (d.kind === "strava") {
      h += f("Runs a week", `<div class="hs-pair">${stepper("runs", d.runs, "runs", "Runs a week", {min: 1, max: 14, step: 1})}<span class="hs-pairl">Counts from</span>${stepper("km", d.km, "km", "Counts from", {min: 0, max: 100, step: 0.5})}</div><p class="hs-help">Alibi reads your runs from Strava every hour.</p>`, "runs");
    } else {
      const M = METRICS[d.metric] || METRICS.steps;
      h += f("Daily goal", `${stepper("target", d.target, M.per, "Daily goal", {min: M.min, max: M.max, step: M.step})}<p class="hs-help">Your iPhone sends this from Apple Health each night.</p>`, "target");
    }
    const showWhen = d.kind !== "health" || d.metric === "mindful_min" || (d.sched || []).length;
    if (showWhen) h += f("When", `${rowsHTML(d)}<div class="hs-coverbox">${coverHTML(d)}</div>`, "when");
    const plan = [];
    if (showWhen) plan.push(`<div class="hs-swrow" data-calrow ${(d.sched || []).length ? "" : "hidden"}>${sw("calendar", d.calendar, "Show in Apple Calendar")}</div>`);
    if (d.kind === "watch") plan.push(`<div class="hs-swrow">${sw("shield", d.shield, "Block distracting iPhone apps during it", {disabled: S.phone === false})}${S.phone === false ? `<a class="hs-link" href="/phone" target="_blank" rel="noopener">Set up iPhone</a>` : ""}</div>`);
    if (plan.length) h += f("On the plan", plan.join(""), "plan");
    if (d.kind === "watch" && !d.isNew) h += `<details class="hs-more"><summary>${icon("chevron-right", 16)}<span>What counts</span></summary>
        ${f("Other words for it", `<input class="hs-in" id="hs-al-${E(id)}" data-f="aliases" value="${E(d.aliases)}" placeholder="sketch, draw, art" spellcheck="false"><p class="hs-help">Say any of them to start it.</p>`, "aliases", `hs-al-${E(id)}`)}
        ${f("What it looks like", `<textarea class="hs-in hs-ta" id="hs-lk-${E(id)}" data-f="looks" rows="2" placeholder="hands on a guitar">${E(d.looks)}</textarea><p class="hs-help">The camera checker reads this.</p>`, "looks", `hs-lk-${E(id)}`)}
      </details>`;
    const rmAttr = live ? ` disabled title="Running now. Change it after the session."` : "";
    h += `<div class="hs-foot">${d.isNew ? `<span class="hs-msg" role="status"></span>` : `<button type="button" class="hs-qbtn hs-remove" data-remove="1"${rmAttr}>Remove</button><span class="hs-msg" role="status"></span>`}
      <button type="button" class="al-btn al-btn--quiet" data-cancel="1">Cancel</button>
      <button type="button" class="al-btn al-btn--primary hs-save" data-save="1"><span class="hs-save__ck" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></span><span class="hs-save__t">${d.isNew ? "Add habit" : "Save"}</span></button></div>`;
    return `<div class="hs-panel" id="hs-p-${E(id)}" role="group" aria-labelledby="hs-r-${E(id)}">${h}</div>`;
  }
  function tplList() {
    const base = (S.tpls || []).filter(t => t.id !== "custom");
    const custom = (S.tpls || []).find(t => t.id === "custom");
    const camText = ((S.tpls || []).find(t => t.check === "camera") || {}).check_text || "Camera on my desk";
    const presets = PRESETS.map(p => Object.assign({check_text: camText}, p));
    const i = base.findIndex(t => t.id === "instrument");
    const out = [...base];
    out.splice(i < 0 ? out.length : i + 1, 0, ...presets);
    if (custom) out.push(custom);
    return out;
  }
  function haveTpl(t) {
    const hs = S.cfg && S.cfg.habits || {};
    if (t.id === "custom" || t.id === "instrument") return false;
    return Object.entries(hs).some(([k, h]) => h.template === t.id || k === t.id || (t.label && nameOf(k).toLowerCase() === String(t.label).toLowerCase())
      || (t.check === "strava" && h.source === "strava") || (TPL_HEALTH[t.id] && h.source === "health" && h.metric === TPL_HEALTH[t.id]));
  }
  function addZoneHTML() {
    if (!S.grid) return `<button type="button" class="hs-addtile" data-addopen="1">${icon("plus", 20)}<span>Add a habit</span></button>`;
    const ts = tplList();
    return `<div class="hs-tpls" role="group" aria-labelledby="hs-tpls-h">
      <div class="hs-tpls__head"><h2 class="t-h3" id="hs-tpls-h">Add a habit</h2><p class="hs-help">Pick one. Everything can change after.</p><button type="button" class="al-iconbtn al-iconbtn--sm" data-addclose="1" aria-label="Close the list">${icon("x", 16)}</button></div>
      <div class="hs-tgrid">${ts.map(t => { const had = haveTpl(t); const g = t.check === "health" ? (t.id === "sleep" ? "moon" : "heart") : GLYPH[t.check] || "sparkle";
        return `<button type="button" class="hs-tcard" data-tpl="${E(t.id)}"${had ? ` disabled aria-disabled="true"` : ""}>
          <span class="hs-tglyph" aria-hidden="true">${icon(t.id === "custom" ? "sparkle" : g, 20)}</span>
          <span class="hs-tt"><b>${E(t.title)}</b><span>${E(t.blurb || "")}</span><small>${had ? "Added" : "Checked by: " + E(t.check_text || CHECK_SHORT[t.check] || "")}</small></span>
          ${had ? `<span class="hs-had">${icon("check", 16)}</span>` : ""}</button>`; }).join("")}</div></div>`;
  }
  function shellHTML() {
    return `<div class="hs-bar"><span class="wordmark" aria-label="Alibi">ALIBI</span><span class="hs-bartitle" aria-hidden="true">Your habits</span>
        <span class="hs-barr"><span class="hs-confirm" hidden></span><kbd class="al-kbd hs-esc">esc</kbd><button type="button" class="al-btn al-btn--secondary al-btn--sm" data-hsclose="1">Done</button></span></div>
      <div class="hs-col">
        <header class="hs-head"><div><h1 class="t-h1" id="hsTitle">Your habits</h1><p class="hs-meta"></p></div>
          <button type="button" class="al-btn al-btn--secondary al-btn--sm hs-addbtn" data-addopen="1">${icon("plus", 16)}Add a habit</button></header>
        <div class="hs-stick">
          <div class="hs-hero"><div class="hs-pinch" aria-hidden="true"></div>
            <div class="hs-said"><p class="hs-line t-voice"></p><span class="hs-src"></span><div class="hs-receipt" aria-label="What changed"></div><p class="al-sr hs-announce" role="status" aria-live="polite"></p></div></div>
          <section class="hs-week" role="group" aria-label="Your usual week">
            <div class="hs-wk-head"><h2 class="hs-wk-t">Your usual week</h2><span class="hs-wk-tot"><b class="hs-wk-totn"></b> planned</span></div>
            <div class="hs-wk-scroll"><div class="hs-wk-grid"></div></div>
          </section>
        </div>
        <div class="hs-list" role="list"></div>
        <div class="hs-addzone"></div>
      </div>
      <div class="hs-snack" role="status" aria-live="polite" hidden></div>`;
  }
  function offlineHTML() {
    return `<div class="hs-bar"><span class="wordmark" aria-label="Alibi">ALIBI</span><span></span><span class="hs-barr"><button type="button" class="al-btn al-btn--secondary al-btn--sm" data-hsclose="1">Done</button></span></div>
      <div class="hs-col"><header class="hs-head"><div><h1 class="t-h1" id="hsTitle">Your habits</h1></div></header>
      <div class="hs-off"><p>Alibi isn't running, so habits can't load. Start Alibi, then try again.</p><button type="button" class="al-btn al-btn--secondary" data-retry="1">Try again</button></div></div>`;
  }

  /* ---------- render ---------- */
  const listEl = () => S.el && q(".hs-list", S.el);
  const cardEl = key => S.el && q(`.hs-card[data-key="${CSS.escape(key)}"]`, S.el);
  const flipNodes = () => S.el ? [...qa(".hs-card", S.el), q(".hs-addzone", S.el)] : [];
  function renderMeta() {
    const m = S.el && q(".hs-meta", S.el); if (!m) return;
    const hs = S.cfg.habits || {}, n = Object.keys(hs).length;
    const tot = Object.values(hs).reduce((a, h) => a + planned(cleanSched(h.schedule)), 0);
    if (!m.firstChild) m.innerHTML = `<span class="hs-mn"></span> <span class="hs-mw"></span> · <span class="hs-mt"></span> planned a week`;
    roll(q(".hs-mn", m), String(n)); q(".hs-mw", m).textContent = n === 1 ? "habit" : "habits"; roll(q(".hs-mt", m), fmtHM(tot));
  }
  function renderList() {
    const box = listEl(); if (!box) return;
    const keys = [...S.order]; if (S.add) keys.push(NEW);
    box.innerHTML = keys.map(cardHTML).join("") || `<p class="hs-empty">Nothing here yet. Pick a habit below and Alibi starts checking.</p>`;
    qa(".hs-card", box).forEach(c => { c.setAttribute("role", "listitem"); roll(q(".hs-statn", c), q(".hs-statn", c).dataset.n); });
  }
  function renderAddZone() { const z = S.el && q(".hs-addzone", S.el); if (z) z.innerHTML = addZoneHTML(); }
  function weekItems() {
    const out = [], hs = S.cfg && S.cfg.habits || {};
    const keys = [...S.order]; if (S.add) keys.push(NEW);
    for (const key of keys) {
      const isNew = key === NEW, h = hs[key] || {}, d = draftFor(key);
      const label = d ? (String(d.label || "").trim() || "New habit") : nameOf(key, h);
      const srv = new Map(); if (!isNew) cleanSched(h.schedule).forEach(r => r.days.forEach(x => srv.set(`${x}|${r.at}`, r)));
      const cur = d ? new Map() : srv;
      if (d) cleanSched(d.sched).forEach(r => r.days.forEach(x => cur.set(`${x}|${r.at}`, r)));
      cur.forEach((r, k) => { const [day, at] = k.split("|"); out.push({id: `${key}|${k}`, key, day, at, min: r.min, label, draft: !!d && !srv.has(k), mine: S.openKey === key}); });
      if (d) srv.forEach((r, k) => { if (!cur.has(k)) { const [day, at] = k.split("|"); out.push({id: `${key}|${k}`, key, day, at, min: r.min, label, ghost: true, mine: S.openKey === key}); } });
    }
    // overlaps between the open habit and the others, same day
    const mine = out.filter(i => i.mine && !i.ghost), others = out.filter(i => !i.mine && !i.ghost);
    S.clash = null;
    for (const a of mine) {
      const a0 = toMin(a.at), a1 = a0 + (+a.min || 0);
      const b = others.find(o => o.day === a.day && toMin(o.at) < a1 && toMin(o.at) + (+o.min || 0) > a0);
      if (b) { a.clash = true; b.clash = true; if (!S.clash) S.clash = `Overlaps ${b.label} on ${WD3[b.day]} at ${b.at}.`; }
    }
    return out;
  }
  function renderWeek(o = {}) {
    const grid = S.el && q(".hs-wk-grid", S.el); if (!grid) return;
    const items = weekItems();
    const today = WD[(new Date().getDay() + 6) % 7];
    if (!grid.children.length) grid.innerHTML = WD.map(x => `<div class="hs-day${x === today ? " is-today" : ""}" data-day="${x}">
        <span class="hs-dname">${WD3[x]}${x === today ? `<span class="hs-today">Today</span>` : ""}</span><ul class="hs-pills"></ul><span class="hs-dtot"></span></div>`).join("");
    const rects = new Map(); qa(".hs-pill:not(.is-leaving)", grid).forEach(p => rects.set(p.dataset.id, p.getBoundingClientRect()));
    const fresh = [];
    let total = 0;
    WD.forEach((x, ci) => {
      const col = q(`.hs-day[data-day="${x}"]`, grid), ul = q(".hs-pills", col);
      const list = items.filter(i => i.day === x).sort((a, b) => a.at.localeCompare(b.at) || a.label.localeCompare(b.label));
      const keep = new Set(list.map(i => i.id));
      qa(".hs-pill:not(.is-leaving)", ul).forEach(p => { if (!keep.has(p.dataset.id)) leave(p, ul); });
      let prev = null;
      list.forEach(i => {
        let p = qa(".hs-pill:not(.is-leaving)", ul).find(n => n.dataset.id === i.id);
        if (!p) { p = document.createElement("li"); p.className = "hs-pill"; p.dataset.id = i.id; p.innerHTML = `<button type="button" class="hs-pb"><time></time><span></span></button>`; fresh.push([p, ci]); }
        const b = q(".hs-pb", p);
        b.dataset.hk = i.key; b.setAttribute("aria-label", `Edit ${i.label}, ${WDN[x]} at ${i.at}${i.draft ? ", not saved yet" : i.ghost ? ", removed, not saved yet" : ""}`);
        if (q("time", b).textContent !== i.at) q("time", b).textContent = i.at;
        if (q("span", b).textContent !== i.label) q("span", b).textContent = i.label;
        p.classList.toggle("is-mine", !!i.mine); p.classList.toggle("is-draft", !!i.draft); p.classList.toggle("is-ghost", !!i.ghost); p.classList.toggle("is-clash", !!i.clash && !!i.mine);
        const ref = prev ? prev.nextElementSibling : ul.firstElementChild;
        if (p !== ref) ul.insertBefore(p, ref);
        prev = p;
      });
      const sum = list.filter(i => !i.ghost).reduce((a, i) => a + (+i.min || 0), 0);
      total += sum;
      const n = list.filter(i => !i.ghost).length;
      ul.setAttribute("aria-label", `${WDN[x]}, ${n} session${n === 1 ? "" : "s"}, ${n ? spokenHM(sum) : "rest"}`);
      const tt = q(".hs-dtot", col);
      if (sum) roll(tt, fmtHM(sum)); else { tt.removeAttribute("data-v"); tt.textContent = "Rest"; tt.setAttribute("aria-label", "Rest"); }
      col.classList.toggle("is-rest", !sum);
    });
    if (!RM()) qa(".hs-pill:not(.is-leaving)", grid).forEach(p => {
      const a = rects.get(p.dataset.id); if (!a || fresh.some(f => f[0] === p)) return;
      const b = p.getBoundingClientRect(), dx = a.left - b.left, dy = a.top - b.top;
      if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) p.animate([{transform: `translate(${dx}px,${dy}px)`}, {transform: "none"}], {duration: tok("--spring-snappy-dur", 484), easing: ease("--spring-snappy")});
    });
    fresh.forEach(([p, ci], i) => pop(p, o.entrance ? 160 + 40 * Math.min(ci, 5) : 0));
    roll(q(".hs-wk-totn", S.el), fmtHM(total));
    const wk = q(".hs-week", S.el);
    wk.setAttribute("aria-label", `Your usual week, ${spokenHM(total)} planned`);
    wk.classList.toggle("is-focus", !!S.openKey);
    const cl = S.openKey && cardEl(S.openKey) && q(".hs-clash", cardEl(S.openKey));
    if (cl && cl.textContent !== (S.clash || "")) cl.textContent = S.clash || "";
  }
  function leave(p, ul) {
    const r = p.getBoundingClientRect(), u = ul.getBoundingClientRect();
    p.classList.add("is-leaving");
    if (RM() || !r.width) { p.remove(); return; }
    Object.assign(p.style, {position: "absolute", left: (r.left - u.left) + "px", top: (r.top - u.top) + "px", width: r.width + "px", margin: "0"});
    const a = p.animate([{opacity: 1, transform: "none"}, {opacity: 0, transform: "scale(0.97)"}], {duration: 120, easing: ease("--ease-out"), fill: "forwards"});
    a.onfinish = () => p.remove();
  }
  function renderAll(entrance) {
    if (!S.el) return;
    if (!S.cfg) { S.el.innerHTML = offlineHTML(); return; }
    if (!q(".hs-list", S.el)) S.el.innerHTML = shellHTML();
    renderMeta(); renderList(); renderAddZone(); renderWeek({entrance});
    if (!S.line) say(openLine());
    measureStick();
  }
  let stickRO = null;
  function measureStick() {
    const s = S.el && q(".hs-stick", S.el), bar = S.el && q(".hs-bar", S.el);
    if (!s || !bar) return;
    if (window.ResizeObserver && s._ro !== true) { s._ro = true; if (stickRO) stickRO.disconnect(); stickRO = new ResizeObserver(() => measureStick()); stickRO.observe(s); }
    const sticky = getComputedStyle(s).position === "sticky";
    S.el.style.setProperty("--hs-stick", (bar.offsetHeight + (sticky ? s.offsetHeight : 0)) + "px");
  }
  // After an input: name, summary, stat, coverage, calendar row, ribbon. Never rebuilds the inputs (focus stays).
  function syncCard(key, o = {}) {
    const card = cardEl(key), d = draftFor(key); if (!card || !d) return;
    const nm = q(".hs-nm", card), name = String(d.label || "").trim() || (d.isNew ? "New habit" : nameOf(key));
    if (nm.textContent !== name) nm.textContent = name;
    const sum = q(".hs-sum", card), html = sumHTML(d);
    if (sum.innerHTML !== html) sum.innerHTML = html;
    const [n, unit] = statOf(d);
    roll(q(".hs-statn", card), n); const u = q(".hs-stat small", card); if (u.textContent !== unit) u.textContent = unit;
    q(".hs-glyph", card).innerHTML = icon(glyphOf(d), 20);
    if (!o.skipCover) { const cb = q(".hs-coverbox", card); if (cb) { const c = coverHTML(d); if (cb.dataset.sig !== c) { updateCover(cb, d, c); } } }
    const cr = q("[data-calrow]", card); if (cr) cr.hidden = !(d.sched || []).length;
    card.classList.toggle("is-dirty", !d.isNew && dirty(key));
    renderWeek();
  }
  function updateCover(cb, d, html) {
    const fill = q(".al-meter__fill", cb);
    const had = !!fill;
    const old = fill ? fill.style.transform : null;
    cb.dataset.sig = html; cb.innerHTML = html;
    const nf = q(".al-meter__fill", cb);
    if (had && nf && !RM()) { const to = nf.style.transform; nf.style.transform = old; nf.getBoundingClientRect(); nf.style.transform = to; }
  }

  /* ---------- open / close ---------- */
  async function open(key, pre) {
    S.el = S.el || document.getElementById("habitsSheet");
    if (!S.el) return;
    const already = S.open && S.el.classList.contains("show");
    if (S.loading) return;
    if (!already) { S.opener = document.activeElement; S.open = true; }
    // Load first (local, ~20 ms), then show: the sheet never flashes empty.
    S.loading = true;
    try { await load(); S.err = null; } catch (e) { S.cfg = null; S.err = e; }
    S.loading = false;
    if (!S.open) return;
    if (!already) {
      S.line = ""; S.confirm = false;
      S.el.innerHTML = "";
      S.el.hidden = false; S.el.setAttribute("aria-hidden", "false");
      S.el.classList.add("show"); document.body.classList.add("hs-open");
      call("syncInert");
      try { if (!/^#habits/.test(location.hash)) history.replaceState(null, "", "#habits" + (key ? "/" + key : "")); } catch {}
      S.el.scrollTop = 0;
      S.el.animate([{opacity: 0}, {opacity: 1}], RM() ? {duration: 150, easing: "ease"} : {duration: tok("--dur-medium", 260), easing: ease("--ease-out")});
    }
    renderAll(!already);
    if (!S.cfg) { q("[data-retry]", S.el)?.focus({preventScroll: true}); return; }
    if (!already) {
      const col = q(".hs-col", S.el);
      if (!RM()) col.animate([{opacity: 0, transform: "translateY(12px)"}, {opacity: 1, transform: "none"}], {duration: tok("--dur-drawer", 420), easing: ease("--ease-drawer")});
      enter(qa(".hs-card", S.el).concat([q(".hs-addzone", S.el)]), 200);
      setTimeout(() => { if (S.open) mountPinch(); }, RM() ? 0 : 120);
    }
    if (pre && typeof pre === "object") return pickTemplate("custom", null, pre);
    if (key && S.cfg.habits[key]) { setTimeout(() => expand(key, {focus: true}), already ? 0 : 260); return; }
    if (!Object.keys(S.cfg.habits || {}).length) { S.grid = true; renderAddZone(); }
    setTimeout(() => { const r = S.el && q(".hs-row", S.el); if (r && S.open && !S.el.contains(document.activeElement)) r.focus({preventScroll: true}); }, already ? 0 : 280);
  }
  function close(force) {
    if (!S.open) return;
    const unsaved = Object.keys(S.drafts).filter(dirty).concat(S.add && (S.add.d.label || "").trim() ? [NEW] : []);
    if (unsaved.length && !force) return askClose(unsaved);
    S.open = false;
    stopReceipt(); hideSnack(true);
    const el = S.el;
    const done = () => {
      if (S.open) return;
      el.classList.remove("show"); el.hidden = true; el.setAttribute("aria-hidden", "true"); el.innerHTML = "";
      if (S.pinch) { try { S.pinch.destroy(); } catch {} S.pinch = null; }
      document.body.classList.remove("hs-open");
      call("syncInert");
      S.drafts = {}; S.openKey = null; S.add = null; S.grid = false; S.line = "";
      try { if (/^#habits/.test(location.hash)) history.replaceState(null, "", location.pathname + location.search); } catch {}
      const back = S.opener && S.opener.isConnected ? S.opener : document.getElementById("habitsBtn");
      try { back && back.focus({preventScroll: true}); } catch {}
    };
    if (RM()) { el.animate([{opacity: 1}, {opacity: 0}], {duration: 150, easing: "ease", fill: "forwards"}).onfinish = done; return; }
    const col = q(".hs-col", el);
    if (col) col.animate([{transform: "none"}, {transform: "translateY(8px)"}], {duration: 270, easing: ease("--ease-out"), fill: "forwards"});
    el.animate([{opacity: 1}, {opacity: 0}], {duration: 270, easing: ease("--ease-out"), fill: "forwards"}).onfinish = done;
  }
  function askClose(keys) {
    const box = q(".hs-confirm", S.el); if (!box) return close(true);
    const names = keys.map(k => k === NEW ? (String(S.add.d.label || "").trim() || "the new habit") : nameOf(k));
    box.innerHTML = `<span>Unsaved changes to ${E(names.slice(0, 2).join(" and "))}.</span><button type="button" class="al-btn al-btn--quiet al-btn--sm" data-discard="1">Discard</button><button type="button" class="al-btn al-btn--secondary al-btn--sm" data-keep="1">Keep editing</button>`;
    box.hidden = false; S.confirm = true;
    if (!RM()) box.animate([{opacity: 0, transform: "translateY(-4px)"}, {opacity: 1, transform: "none"}], {duration: tok("--dur-small", 180), easing: ease("--ease-out")});
    q("[data-keep]", box).focus({preventScroll: true});
  }
  function hideConfirm() { const box = S.el && q(".hs-confirm", S.el); if (box) { box.hidden = true; box.innerHTML = ""; } S.confirm = false; }

  /* ---------- expand / collapse ---------- */
  function expand(key, o = {}) {
    if (!S.cfg || (key !== NEW && !S.cfg.habits[key])) return;
    if (S.openKey === key) return;
    if (key !== NEW && !S.drafts[key]) S.drafts[key] = draftOf(key, S.cfg.habits[key]);
    const prevKey = S.openKey;
    S.openKey = key;
    let panel = null;
    flip(flipNodes(), () => {
      if (prevKey) foldNow(prevKey);
      const card = cardEl(key); if (!card) return;
      card.classList.add("is-open");
      q(".hs-row", card).setAttribute("aria-expanded", "true");
      const old = q(".hs-panel", card), tmp = document.createElement("div");
      tmp.innerHTML = panelHTML(key, draftFor(key));
      panel = tmp.firstElementChild; old.replaceWith(panel);
      const cb = q(".hs-coverbox", panel); if (cb) cb.dataset.sig = coverHTML(draftFor(key));
    });
    if (panel) enter(qa(":scope > .hs-f, :scope > .hs-note, :scope > .hs-more, :scope > .hs-foot", panel), 60);
    renderWeek();
    const card = cardEl(key);
    if (card) {
      measureStick();
      setTimeout(() => { if (!S.open) return; const r = card.getBoundingClientRect(), top = parseFloat(getComputedStyle(S.el).getPropertyValue("--hs-stick")) || 56;
        if (r.top < top || r.bottom > innerHeight) card.scrollIntoView({block: r.height > innerHeight - top ? "start" : "nearest", behavior: RM() ? "auto" : "smooth"}); }, RM() ? 0 : 120);
      if (o.focus) { const f = o.focusSel ? q(o.focusSel, card) : q(".hs-in", card); setTimeout(() => f && f.focus({preventScroll: true}), RM() ? 0 : 200); }
    }
  }
  // Fold a card in the same layout pass (no animation of its own): content goes, the row stays.
  function foldNow(key) {
    const card = cardEl(key); if (!card) return;
    card.classList.remove("is-open");
    q(".hs-row", card).setAttribute("aria-expanded", "false");
    const p = q(".hs-panel", card); if (p) { const e = document.createElement("div"); e.className = "hs-panel"; e.id = p.id; e.hidden = true; p.replaceWith(e); }
    card.classList.toggle("is-dirty", key !== NEW && dirty(key));
  }
  function collapse(key, then) {
    const card = cardEl(key); if (!card) { then && then(); return; }
    const panel = q(".hs-panel:not([hidden])", card);
    const run = () => { flip(flipNodes(), () => { foldNow(key); if (S.openKey === key) S.openKey = null; }); renderWeek(); then && then(); };
    if (!panel || RM()) return run();
    const a = panel.animate([{opacity: 1}, {opacity: 0}], {duration: 120, easing: ease("--ease-out"), fill: "forwards"});
    a.onfinish = run;
  }
  function toggle(key) { if (S.openKey === key) collapse(key); else expand(key); }

  /* ---------- the template grid and the new-habit draft ---------- */
  function openGrid() {
    if (S.add) { expand(NEW, {focus: true}); return; }
    const z = q(".hs-addzone", S.el);
    if (S.grid) { z.scrollIntoView({block: "start", behavior: RM() ? "auto" : "smooth"}); return; }
    S.grid = true;
    flip(flipNodes(), () => renderAddZone());
    const g = q(".hs-tpls", z);
    enter(qa(".hs-tcard", g), 40, 30, 8);
    setTimeout(() => { z.scrollIntoView({block: "start", behavior: RM() ? "auto" : "smooth"}); const f = q(".hs-tcard:not([disabled])", z); f && f.focus({preventScroll: true}); }, RM() ? 0 : 60);
  }
  function closeGrid() { S.grid = false; flip(flipNodes(), () => renderAddZone()); }
  function pickTemplate(id, fromEl, pre) {
    const t = tplList().find(x => x.id === id) || (id === "custom" ? {id: "custom", title: "Something else", check: "camera", minutes: 25, ask_name: "What's the habit?", schedule: []} : null);
    if (!t || !S.cfg) return;
    const from = fromEl ? fromEl.getBoundingClientRect() : null;
    const prevKey = S.openKey && S.openKey !== NEW ? S.openKey : null;
    S.add = {d: newDraft(t, pre), t};
    S.openKey = NEW; S.grid = false;
    const box = listEl();
    flip(flipNodes(), () => {
      if (prevKey) foldNow(prevKey);
      const tmp = document.createElement("div"); tmp.innerHTML = cardHTML(NEW);
      const card = tmp.firstElementChild; card.setAttribute("role", "listitem");
      q(".hs-empty", box)?.remove();
      box.appendChild(card); roll(q(".hs-statn", card), q(".hs-statn", card).dataset.n);
      const cb = q(".hs-coverbox", card); if (cb) cb.dataset.sig = coverHTML(S.add.d);
      renderAddZone();
    });
    const card = cardEl(NEW);
    if (card && from && !RM()) {
      const to = card.getBoundingClientRect(), k = from.width / to.width;
      card.animate([{transformOrigin: "0 0", transform: `translate(${from.left - to.left}px,${from.top - to.top}px) scale(${k})`, opacity: 0.6}, {transformOrigin: "0 0", transform: "none", opacity: 1}],
        {duration: tok("--spring-snappy-dur", 484), easing: ease("--spring-snappy")});
      enter(qa(".hs-panel > *", card), 120);
    } else if (card) enter([card]);
    renderWeek();
    setTimeout(() => {
      if (!card || !S.open) return;
      card.scrollIntoView({block: "start", behavior: RM() ? "auto" : "smooth"});
      const f = S.add && (S.add.d.ask != null && !S.add.d.label) ? q(".hs-in", card) : q(".hs-dayb", card) || q(".hs-in", card);
      f && f.focus({preventScroll: true});
    }, RM() ? 0 : 140);
  }

  /* ---------- editing ---------- */
  function onInput(e) {
    const t = e.target, card = t.closest(".hs-card"); if (!card) return;
    const key = card.dataset.key, d = draftFor(key); if (!d) return;
    clearErr(card, t);
    const f = t.dataset.f, rf = t.dataset.rf;
    if (rf) {
      const i = +t.closest(".hs-srow").dataset.row, r = d.sched[i]; if (!r) return;
      if (rf === "at") r.at = t.value; else r.min = t.value === "" ? "" : +t.value;
      if (d.kind === "watch" && d.isNew && !d.touched.goal) d.goal = planned(cleanSched(d.sched)) || d.len * 4;
    } else if (f === "label") d.label = t.value;
    else if (f === "aliases" || f === "looks") { d[f] = t.value; d.touched[f] = true; }
    else if (f) {
      const v = t.value === "" ? "" : +t.value;
      d[f] = v; d.touched[f] = true;
      if (f === "len" && d.kind === "watch") { if (d.isNew && !d.touched.goal) { d.sched.forEach(r => { r.min = v || r.min; }); qa('[data-rf="min"]', card).forEach(i => { i.value = v || i.value; }); d.goal = planned(cleanSched(d.sched)) || (+v || 25) * 4; const g = q('[data-f="goal"]', card); if (g) g.value = Math.round(d.goal); } }
    }
    syncCard(key);
  }
  function stepField(card, f, dir, big) {
    const inp = q(`.hs-num[data-f="${f}"]`, card); if (!inp) return;
    const step = +inp.step || 1, min = +inp.min, max = +inp.max;
    const v = clamp(Math.round(((+inp.value || 0) + dir * step * (big ? 4 : 1)) / step) * step, min, max);
    inp.value = Number.isInteger(step) ? String(v) : String(Math.round(v * 10) / 10);
    inp.dispatchEvent(new Event("input", {bubbles: true}));
    if (!RM()) inp.animate([{transform: `translateY(${dir > 0 ? -4 : 4}px)`, opacity: 0.4}, {transform: "none", opacity: 1}], {duration: tok("--dur-small", 180), easing: ease("--ease-out")});
  }
  function setCheck(card, c) {
    const key = card.dataset.key, d = draftFor(key); if (!d || d.check === c) return;
    d.check = c; d.touched.check = true;
    qa("[data-check]", card).forEach(b => { const on = b.dataset.check === c; b.setAttribute("aria-checked", on); b.tabIndex = on ? 0 : -1; });
    const how = q(".hs-how", card); if (how) blurSwap(how, E(howText(c)));
    const g = q(".hs-glyph", card);
    if (g && !RM()) { const a = g.animate([{opacity: 1, filter: "blur(0)"}, {opacity: 0, filter: "blur(4px)"}], {duration: 120, easing: ease("--ease-out"), fill: "forwards"}); a.onfinish = () => { a.cancel(); syncCard(key); g.animate([{opacity: 0, filter: "blur(4px)"}, {opacity: 1, filter: "blur(0)"}], {duration: tok("--dur-medium", 260), easing: ease("--ease-out")}); }; }
    else syncCard(key);
  }
  function rerenderWhen(card, focusSel) {
    const key = card.dataset.key, d = draftFor(key), sec = q('[data-sec="when"] .hs-v', card); if (!sec) return;
    const err = q(".hs-err", sec);
    const rows = q(".hs-rows", sec), foot = q(".hs-whenfoot", sec), tmp = document.createElement("div");
    tmp.innerHTML = rowsHTML(d);
    rows.replaceWith(tmp.children[0]); foot.replaceWith(tmp.children[0]);
    if (err) sec.appendChild(err);
    syncCard(key);
    if (focusSel) { const f = q(focusSel, card); f && f.focus({preventScroll: true}); }
  }
  function onDay(card, b) {
    const d = draftFor(card.dataset.key), i = +b.closest(".hs-srow").dataset.row, r = d.sched[i]; if (!r) return;
    const day = b.dataset.day, on = !(r.days || []).includes(day);
    r.days = on ? WD.filter(x => x === day || r.days.includes(x)) : r.days.filter(x => x !== day);
    b.setAttribute("aria-pressed", on);
    if (d.kind === "watch" && d.isNew && !d.touched.goal) { d.goal = planned(cleanSched(d.sched)) || d.len * 4; const g = q('[data-f="goal"]', card); if (g) g.value = Math.round(d.goal); }
    clearErr(card, b);
    syncCard(card.dataset.key);
  }
  function fillGap(card) {
    const key = card.dataset.key, d = draftFor(key); if (!d || d.kind !== "watch") return;
    const sched = cleanSched(d.sched), gap = Math.round(+d.goal || 0) - planned(sched), len = Math.round(+d.len || 25);
    if (gap <= 0 || len < 1) return;
    const mine = new Set(sched.flatMap(r => r.days));
    const load = Object.fromEntries(WD.map(x => [x, 0])), busy = Object.fromEntries(WD.map(x => [x, []]));
    Object.entries(S.cfg.habits || {}).forEach(([k, h]) => { if (k === key) return; cleanSched(h.schedule).forEach(r => r.days.forEach(x => { load[x] += r.min; busy[x].push([toMin(r.at), toMin(r.at) + r.min]); })); });
    const free = WD.filter(x => !mine.has(x)).sort((a, b) => load[a] - load[b] || byWD(a, b)).slice(0, Math.ceil(gap / len));
    if (!free.length) return;
    const base = toMin((sched[0] || {}).at) ?? 19 * 60;
    const fits = (x, s) => s >= 7 * 60 && s + len <= 22 * 60 && !busy[x].some(([a, b]) => s < b && s + len > a);
    const pick = x => { for (const k of [0, 60, -60, 120, -120, 180, -180, 240, -240, 300, -300]) if (fits(x, base + k)) return base + k; return base; };
    const byT = {};
    free.forEach(x => { const t = fromMin(pick(x)); (byT[t] = byT[t] || []).push(x); });
    Object.entries(byT).forEach(([at, days]) => { if (d.sched.length < 14) d.sched.push({days: days.sort(byWD), at, min: len}); });
    rerenderWhen(card);
  }

  /* ---------- errors ---------- */
  function clearErr(card, t) {
    const sec = t && t.closest(".hs-f");
    (sec ? [sec] : qa(".hs-f", card)).forEach(s => { const e = q(":scope > .hs-v > .hs-err", s); if (e) e.textContent = ""; qa("[aria-invalid]", s).forEach(i => { i.removeAttribute("aria-invalid"); i.removeAttribute("aria-describedby"); }); s.classList.remove("is-bad"); });
    const m = q(".hs-msg", card); if (m && m.classList.contains("is-bad")) { m.textContent = ""; m.classList.remove("is-bad"); }
  }
  function showErr(card, err) {
    if (!card) return;
    const secName = err.field === "at" || err.field === "min" || err.field === "days" ? "when" : err.field === "len" ? "goal" : err.field === "km" ? "runs" : err.field;
    const sec = secName && q(`.hs-f[data-sec="${secName}"]`, card);
    if (!sec) { const m = q(".hs-msg", card); if (m) { m.textContent = err.text; m.classList.add("is-bad"); } return; }
    sec.classList.add("is-bad");
    const e = q(":scope > .hs-v > .hs-err", sec); e.textContent = err.text;
    let target = null;
    if (err.field === "at" || err.field === "min") target = q(`.hs-srow[data-row="${err.row || 0}"] [data-rf="${err.field}"]`, sec);
    else if (err.field === "days") target = q(`.hs-srow[data-row="${err.row || 0}"] .hs-dayb`, sec);
    else if (err.field === "check") target = q(".hs-segb", sec);
    else target = q(`[data-f="${err.field}"]`, sec) || q("input,button", sec);
    if (target) { target.setAttribute("aria-invalid", "true"); target.setAttribute("aria-describedby", e.id); target.focus({preventScroll: true}); }
    sec.scrollIntoView({block: "nearest", behavior: RM() ? "auto" : "smooth"});
  }

  /* ---------- save, add, remove, undo ---------- */
  function busyBtn(card, on) {
    const b = card && q(".hs-save", card); if (!b) return;
    b.disabled = on; b.classList.toggle("is-busy", on);
  }
  async function save(key) {
    const d = draftFor(key), card = cardEl(key);
    if (!d || !card || S.busy) return;
    clearErr(card);
    const bad = validate(d); if (bad) { showErr(card, bad); return; }
    S.busy = true; busyBtn(card, true);
    const think = setTimeout(() => pinchMood("thinking"), 600);
    const [planBefore, calBefore] = await Promise.all([planWeek(), calStatus()]);
    const t0 = nowS();
    let res, newKey = key;
    try {
      if (d.isNew) {
        const t = S.add.t, body = {template: d.tid, minutes: d.kind === "watch" ? Math.round(+d.len) : undefined, schedule: cleanSched(d.sched), calendar: !!d.calendar};
        const label = String(d.label || "").trim();
        if (d.ask != null || d.preset || label !== (t.label || t.title)) body.name = label;
        if (d.kind === "watch") { body.check = d.check; if (d.touched.goal) body.weekly_target_min = Math.round(+d.goal); if (d.touched.shield) body.phone_shield = !!d.shield; }
        if (d.kind === "strava") body.target = Math.round(+d.runs);
        if (d.kind === "health") body.target = +d.target;
        const r = await fetch("/api/habits/add", {method: "POST", headers: HDR(), body: JSON.stringify(body)});
        const j = await r.json().catch(() => ({}));
        if (!r.ok) throw httpErr(r.status, j);
        newKey = j.key;
        res = {before: null, saved: j.saved || null, reply: j.reply, added: true};
        // A change the template can't take in one request (checked by on a fixed template, Strava's distance): one more write.
        const fix = {};
        if (d.kind === "watch" && d.tid !== "custom" && d.check !== (t.check || "camera")) fix.modality = C2M[d.check];
        if (d.kind === "strava" && +d.km !== 5) fix.min_km = Math.max(0, +d.km);
        if (Object.keys(fix).length) { const c2 = await commit(m => { if (m[newKey]) Object.assign(m[newKey], fix); return m; }); res.cfg = c2.cfg; }
        else res.cfg = await getJSON("/api/habits");
      } else {
        res = await commit(m => { m[key] = toEntry(d, m[key]); return m; });
      }
    } catch (e) {
      clearTimeout(think); pinchMood(); S.busy = false; busyBtn(card, false);
      if (e.http && e.status === 400) showErr(card, mapErr(e.message, d));
      else showErr(card, {field: null, text: "Alibi isn't running, so this didn't save. Your changes are still here."});
      return;
    }
    clearTimeout(think);
    const prevEntry = !d.isNew ? clone(S.cfg.habits[key]) : null, before = res.before;
    setCfg(res.cfg);
    if (d.isNew) {
      S.add = null;
      // the draft's pills become the habit's pills: same nodes, so the dashed edge fades instead of a swap
      qa(".hs-pill", S.el).forEach(p => { if (p.dataset.id.startsWith(NEW + "|")) p.dataset.id = newKey + p.dataset.id.slice(NEW.length); });
    } else delete S.drafts[key];
    renderWeek();
    loadView2();
    const line = (res.saved && res.saved.line) || (d.isNew ? res.reply : clientLine(prevEntry, S.cfg.habits[key], key)) || "Noted.";
    // The sequence: Saved -> the card folds -> Pinch nods with the line -> the receipt ticks in.
    const b = q(".hs-save", card);
    if (b) { b.disabled = false; b.classList.remove("is-busy"); b.classList.add("is-saved"); swapText(q(".hs-save__t", b), "Saved"); }
    const hold = RM() ? 200 : 650;
    setTimeout(() => {
      if (!S.open) return;
      const oldSum = q(".hs-sum", card) ? [...qa("[data-frag]", card)].map(s => [s.dataset.frag, s.textContent]) : [];
      collapse(key, () => {
        const c = cardEl(key);
        if (c) {
          const tmp = document.createElement("div"); tmp.innerHTML = cardHTML(newKey);
          const nc = tmp.firstElementChild; nc.setAttribute("role", "listitem");
          c.replaceWith(nc);
          const sn = q(".hs-statn", nc), od = q(".hs-statn", c);
          if (od && od.dataset.v != null) { sn.dataset.v = od.dataset.v; sn.innerHTML = od.innerHTML; sn.classList.add("al-roll"); }
          roll(sn, sn.dataset.n);
          glow(nc, oldSum, d.isNew);
          const r = nc.getBoundingClientRect(), top = parseFloat(getComputedStyle(S.el).getPropertyValue("--hs-stick")) || 56;
          if (r.top < top || r.bottom > innerHeight) nc.scrollIntoView({block: "nearest", behavior: RM() ? "auto" : "smooth"});
        }
        renderMeta(); renderWeek(); renderAddZone();
      });
    }, hold);
    setTimeout(() => {
      if (!S.open) return;
      pinchMood();
      pinchPlay(d.isNew ? "connected" : "surprise");
      say(line);
    }, hold + (RM() ? 0 : 260));
    setTimeout(() => { if (S.open) receipt(t0, res.saved, planBefore, calBefore, {key: newKey, undo: d.isNew ? {kind: "add", key: newKey} : {kind: "edit", key, entry: before ? before[key] : prevEntry, idx: before ? Object.keys(before).indexOf(key) : -1}}); }, hold + (RM() ? 0 : 360));
    S.busy = false;
    refreshDash(res.saved);
  }
  function swapText(el, text) {
    if (!el) return;
    if (RM()) { el.textContent = text; return; }
    const a = el.animate([{opacity: 1, filter: "blur(0)"}, {opacity: 0, filter: "blur(4px)"}], {duration: 120, easing: ease("--ease-out"), fill: "forwards"});
    a.onfinish = () => { el.textContent = text; a.cancel(); el.animate([{opacity: 0}, {opacity: 1}], {duration: tok("--dur-medium", 260), easing: ease("--ease-out")}); };
  }
  function glow(card, oldParts, all) {
    const old = new Map(oldParts);
    qa("[data-frag]", card).forEach(s => {
      if (!all && old.get(s.dataset.frag) === s.textContent) return;
      s.classList.add("is-fresh");
      if (!RM()) s.animate([{opacity: 0, filter: "blur(4px)"}, {opacity: 1, filter: "blur(0)"}], {duration: tok("--dur-medium", 260), easing: ease("--ease-out")});
      setTimeout(() => s.classList.remove("is-fresh"), 60);
    });
    if (all && !RM()) q(".hs-glyph", card)?.animate([{transform: "scale(0.94)", opacity: 0.4}, {transform: "none", opacity: 1}], {duration: tok("--spring-bouncy-dur", 720), easing: ease("--spring-bouncy")});
  }
  async function loadView2() { try { const j = await getJSON("/api/habits/view"); S.view = Object.fromEntries((j.habits || []).map(h => [h.key, h])); } catch {} }
  // The dashboard behind is current before the sheet closes: Today from saved.plan_today at once, then the slow loads.
  function refreshDash(saved) {
    try { if (saved && saved.plan_today && typeof window.AlibiToday === "object") window.AlibiToday.plan(saved.plan_today); } catch {}
    call("loadHabits"); call("loadView"); call("loadPlan");
    setTimeout(() => call("refreshSlow"), 300);
  }

  async function remove(key) {
    const card = cardEl(key); if (!card || S.busy) return;
    if (liveKey() === key) return;
    S.busy = true; stopReceipt(true);
    const idx = S.order.indexOf(key), label = nameOf(key);
    const [pb, cb] = await Promise.all([planWeek(), calStatus()]), t0 = nowS();
    let res;
    try { res = await commit(m => { delete m[key]; return m; }); }
    catch (e) {
      S.busy = false;
      showErr(card, e.http && e.status === 400 ? mapErr(e.message) : {field: null, text: "Alibi isn't running, so this didn't save."});
      return;
    }
    S.busy = false;
    const entry = res.before[key];
    setCfg(res.cfg); delete S.drafts[key]; if (S.openKey === key) S.openKey = null;
    const go = () => { flip(flipNodes(), () => card.remove()); renderWeek(); renderMeta(); renderAddZone(); };
    if (RM()) go();
    else { card.style.pointerEvents = "none"; card.animate([{opacity: 1, transform: "none"}, {opacity: 0, transform: "scale(0.98)"}], {duration: 170, easing: ease("--ease-out"), fill: "forwards"}).onfinish = go; }
    say((res.saved && res.saved.line) || `${label} is off the plan. Past sessions stay put.`);
    snack(`Removed ${label}.`, () => undoRemove(key, entry, idx));
    later2(() => receipt(t0, res.saved, pb, cb, {}), 200);
    refreshDash(res.saved);
  }
  async function undoRemove(key, entry, idx) {
    if (!entry) return;
    stopReceipt(true);
    const [pb, cb] = await Promise.all([planWeek(), calStatus()]), t0 = nowS();
    let res;
    try { res = await commit(m => insertAt(m, key, entry, idx), "undo"); }
    catch { say("That didn't go back. Check Alibi is running, then try again."); return; }
    setCfg(res.cfg);
    flip(flipNodes(), () => renderList());
    const c = cardEl(key); if (c && !RM()) c.animate([{opacity: 0, transform: "scale(0.98)"}, {opacity: 1, transform: "none"}], {duration: tok("--dur-medium", 260), easing: ease("--ease-out")});
    renderWeek(); renderMeta(); renderAddZone();
    say((res.saved && res.saved.line) || "Back as it was.");
    later2(() => receipt(t0, res.saved, pb, cb, {}), 200);
    refreshDash(res.saved);
  }
  async function undoSave(u) {
    stopReceipt(true);
    const [pb, cb] = await Promise.all([planWeek(), calStatus()]), t0 = nowS();
    let res;
    try {
      if (u.kind === "add") res = await commit(m => { delete m[u.key]; return m; }, "undo");
      else res = await commit(m => { if (u.entry) m = m[u.key] ? Object.assign(m, {[u.key]: u.entry}) : insertAt(m, u.key, u.entry, u.idx); return m; }, "undo");
    } catch { say("That didn't go back. Check Alibi is running, then try again."); return; }
    setCfg(res.cfg);
    flip(flipNodes(), () => renderList());
    renderWeek(); renderMeta(); renderAddZone();
    say((res.saved && res.saved.line) || "Back as it was.");
    later2(() => receipt(t0, res.saved, pb, cb, {}), 200);
    refreshDash(res.saved);
  }
  // after a beat, and only while the sheet is still open
  function later2(fn, ms) { setTimeout(() => { if (S.open) fn(); }, RM() ? 0 : ms); }

  /* ---------- snackbar (the shared toast sits under the sheet) ---------- */
  function snack(text, undo) {
    const el = S.el && q(".hs-snack", S.el); if (!el) return;
    hideSnack(true);
    el.innerHTML = `<span>${E(text)}</span><button type="button" class="al-btn al-btn--secondary al-btn--sm" data-snackundo="1">${icon("undo", 16)}Undo</button>`;
    el.hidden = false;
    if (!RM()) el.animate([{opacity: 0, transform: "translate(-50%, 12px)"}, {opacity: 1, transform: "translate(-50%, 0)"}], {duration: tok("--spring-snappy-dur", 484), easing: ease("--spring-snappy")});
    const sn = S.snack = {undo, left: 6000, t: performance.now(), paused: false, timer: 0};
    const tick = () => { if (S.snack !== sn) return; if (!sn.paused) { const n = performance.now(); sn.left -= n - sn.t; sn.t = n; if (sn.left <= 0) return hideSnack(); } else sn.t = performance.now(); sn.timer = setTimeout(tick, 200); };
    sn.timer = setTimeout(tick, 200);
    el.onmouseenter = el.onfocusin = () => { sn.paused = true; };
    el.onmouseleave = el.onfocusout = () => { sn.paused = false; sn.t = performance.now(); };
  }
  function hideSnack(now) {
    const el = S.el && q(".hs-snack", S.el), sn = S.snack;
    if (sn) clearTimeout(sn.timer);
    S.snack = null;
    if (!el || el.hidden) return;
    if (now || RM()) { el.hidden = true; el.innerHTML = ""; return; }
    el.animate([{opacity: 1}, {opacity: 0}], {duration: 170, easing: ease("--ease-out"), fill: "forwards"}).onfinish = () => { if (!S.snack) { el.hidden = true; el.innerHTML = ""; } };
  }

  /* ---------- the receipt: each chip appears only once a GET proves it ---------- */
  function stopReceipt(clear) {
    const R = S.rc; if (R) { R.alive = false; R.timers.forEach(clearTimeout); }
    S.rc = null;
    if (clear && S.el) { const b = q(".hs-receipt", S.el); if (b) b.innerHTML = ""; }
  }
  function receipt(t0, saved, planBefore, calBefore, o) {
    stopReceipt();
    const box = S.el && q(".hs-receipt", S.el); if (!box) return;
    box.innerHTML = ["island", "week", "cal", "agent", "next"].map(id => `<span class="hs-rc" data-rc="${id}" hidden></span>`).join("") + (o.undo ? `<button type="button" class="al-btn al-btn--quiet al-btn--sm hs-undo" data-undo="1">${icon("undo", 16)}Undo</button>` : "");
    const R = S.rc = {t0, alive: true, timers: [], said: [], undo: o.undo, shown: 0};
    const later = (fn, ms) => { R.timers.push(setTimeout(() => { if (R.alive && S.rc === R) fn(); }, ms)); };
    const show = (id, text, ok) => {
      if (!R.alive) return;
      const c = q(`[data-rc="${id}"]`, box); if (!c) return;
      const first = c.hidden;
      c.className = "hs-rc" + (ok ? " is-ok" : " is-quiet");
      c.innerHTML = `${ok ? `<span class="hs-rc__ck" aria-hidden="true">${icon("check", 16)}</span>` : `<span class="hs-rc__dot" aria-hidden="true"></span>`}<span>${E(text)}</span>`;
      c.hidden = false;
      if (first) { R.said.push(text); const d = 120 * R.shown++; if (!RM()) { c.animate([{opacity: 0, transform: "translateY(4px)"}, {opacity: 1, transform: "none"}], {duration: tok("--dur-medium", 260), delay: d, easing: ease("--ease-out"), fill: "backwards"}); const ck = q(".hs-rc__ck", c); if (ck) ck.animate([{transform: "scale(0.6)", opacity: 0}, {transform: "none", opacity: 1}], {duration: tok("--spring-bouncy-dur", 720), delay: d + 80, easing: ease("--spring-bouncy"), fill: "backwards"}); } }
    };
    const undoB = q(".hs-undo", box);
    if (undoB) {
      if (!RM()) undoB.animate([{opacity: 0}, {opacity: 1}], {duration: tok("--dur-medium", 260), easing: "ease"});
      later(() => { if (!RM()) undoB.animate([{opacity: 1}, {opacity: 0}], {duration: 170, easing: ease("--ease-out"), fill: "forwards"}).onfinish = () => undoB.remove(); else undoB.remove(); R.undo = null; }, 6000);
    }
    // 1. the island: the save raised an alert, and the island has polled since
    const s0 = st();
    if (saved && saved.alert_id != null && s0 && "clients" in s0) {
      let n = 0;
      const poll = () => { const s = st(), c = s && s.clients; if (s && s.now > t0 && c && c.island_ago_s != null && c.island_ago_s <= 3) return show("island", "Island has it", true);
        if (++n > 12) return show("island", "Island isn't open", false); later(poll, 500); };
      later(poll, 400);
    }
    // 2. this week's plan, before and after
    (async () => {
      const after = await planWeek(); if (!R.alive || !after || !planBefore) return;
      const b = new Map(planBefore.map(x => [x.key, x])), a = new Map(after.map(x => [x.key, x]));
      const added = [...a.keys()].filter(k => !b.has(k)), gone = [...b.keys()].filter(k => !a.has(k));
      const sameDay = k => k.split("T")[0];
      let moved = 0; const g2 = [...gone];
      added.slice().forEach(k => { const j = g2.findIndex(x => sameDay(x) === sameDay(k)); if (j >= 0) { g2.splice(j, 1); moved++; } });
      const add = added.length - moved, rem = gone.length - moved, upd = [...a.keys()].filter(k => b.has(k) && b.get(k).min !== a.get(k).min).length;
      const parts = [[add, "added"], [moved, "moved"], [rem, "removed"], [upd, "updated"]].filter(([n]) => n)
        .map(([n, v], i) => i ? `${n} ${v}` : `${n} block${n === 1 ? "" : "s"} ${v}`);
      show("week", `Week re-planned · ${parts.join(", ") || "no change"}`, true);
    })();
    // 3. Apple Calendar: synced after the save, or honestly off
    (async () => {
      const c = calBefore || await calStatus(); if (!R.alive || !c) return;
      if (!c.connected) { if (c.available !== false) show("cal", "Apple Calendar is off", false); return; }
      const base = calBefore ? calBefore.planned_next_14d : null; let n = 0;
      const poll = async () => { const s = await calStatus(); if (!R.alive) return;
        if (s && s.last_sync && s.last_sync >= t0) { const dlt = base == null ? null : (s.planned_next_14d || 0) - base;
          return show("cal", dlt ? `Apple Calendar · ${Math.abs(dlt)} ${dlt > 0 ? "more" : "fewer"} in the next 2 weeks` : "Apple Calendar is up to date", true); }
        if (++n < 14) later(poll, 3000); };
      later(poll, 2000);
    })();
    // 4. the agent on the Spark read the new context (only while it's online; never claimed otherwise)
    if (s0 && s0.agent && s0.agent.online) {
      let n = 0;
      const poll = () => { const s = st(), a = s && s.agent; if (a && a.last_seen && a.last_seen > t0) return show("agent", `Your agent has it · ${Math.max(1, Math.round(a.last_seen - t0))} s`, true);
        if (++n < 90) later(poll, 500); };
      later(poll, 500);
    }
    // 5. when Alibi next looks at the day (config defaults)
    const d = new Date(), m = d.getHours() * 60 + d.getMinutes();
    const nx = CHECKINS.find(([t]) => toMin(t) > m) || CHECKINS[0];
    later(() => show("next", `${nx[1]} ${nx[0]}`, true), 240);
    later(() => { const a = q(".hs-announce", S.el); if (a) a.textContent = `Saved. ${R.said.join(". ")}.`; }, 2600);
  }

  /* ---------- events ---------- */
  function onClick(e) {
    const t = e.target;
    if (t.closest("[data-hsclose]")) return close();
    if (t.closest("[data-retry]")) { S.el.innerHTML = ""; S.open = true; return open(); }
    if (t.closest("[data-discard]")) { hideConfirm(); S.drafts = {}; S.add = null; return close(true); }
    if (t.closest("[data-keep]")) { hideConfirm(); const k = Object.keys(S.drafts).find(dirty) || (S.add ? NEW : null); if (k) { expand(k); const c = cardEl(k); c && q(".hs-row", c).focus({preventScroll: true}); } return; }
    if (t.closest("[data-snackundo]")) { const sn = S.snack; hideSnack(); if (sn && sn.undo) sn.undo(); return; }
    if (t.closest("[data-undo]")) { const R = S.rc; if (R && R.undo) undoSave(R.undo); return; }
    if (t.closest("[data-addopen]")) return openGrid();
    if (t.closest("[data-addclose]")) return closeGrid();
    const tp = t.closest("[data-tpl]"); if (tp) { if (!tp.disabled) pickTemplate(tp.dataset.tpl, tp); return; }
    const pb = t.closest(".hs-pb"); if (pb) { const k = pb.dataset.hk; const at = q("time", pb).textContent; if (k) { expand(k); setTimeout(() => { const c = cardEl(k); const r = c && qa(".hs-srow", c).find(x => q('[data-rf="at"]', x).value === at); (r ? q('[data-rf="at"]', r) : null)?.focus({preventScroll: true}); }, 240); } return; }
    const card = t.closest(".hs-card"); if (!card) return;
    const key = card.dataset.key;
    if (t.closest(".hs-row")) return toggle(key);
    const ck = t.closest("[data-check]"); if (ck) return setCheck(card, ck.dataset.check);
    const day = t.closest("[data-day]"); if (day) return onDay(card, day);
    const pr = t.closest("[data-preset]"); if (pr) { const d = draftFor(key), i = +pr.closest(".hs-srow").dataset.row; if (d.sched[i]) { d.sched[i].days = pr.dataset.preset.split(","); qa(".hs-dayb", pr.closest(".hs-srow")).forEach(b => b.setAttribute("aria-pressed", d.sched[i].days.includes(b.dataset.day))); if (d.kind === "watch" && d.isNew && !d.touched.goal) d.goal = planned(cleanSched(d.sched)) || d.len * 4; syncCard(key); } return; }
    if (t.closest("[data-rowadd]")) { const d = draftFor(key); const last = d.sched[d.sched.length - 1]; d.sched.push({days: last ? [] : ["mon", "wed", "fri"], at: last ? last.at : "19:00", min: d.len || (last && last.min) || 25}); rerenderWhen(card, `.hs-srow[data-row="${d.sched.length - 1}"] .hs-dayb`); const r = q(`.hs-srow[data-row="${d.sched.length - 1}"]`, card); enter([r]); return; }
    const rd = t.closest("[data-rowdel]"); if (rd) { const d = draftFor(key); d.sched.splice(+rd.dataset.rowdel, 1); if (d.kind === "watch" && d.isNew && !d.touched.goal) d.goal = planned(cleanSched(d.sched)) || d.len * 4; rerenderWhen(card, ".hs-addtime"); return; }
    const sb = t.closest("[data-step]"); if (sb) return stepField(card, sb.dataset.step, +sb.dataset.dir, e.shiftKey);
    const swb = t.closest("[data-sw]"); if (swb) { const d = draftFor(key), f = swb.dataset.sw; d[f] = !(swb.getAttribute("aria-checked") === "true"); d.touched[f] = true; swb.setAttribute("aria-checked", d[f]); syncCard(key); return; }
    if (t.closest("[data-fill]")) return fillGap(card);
    if (t.closest("[data-goalfit]")) { const d = draftFor(key); d.goal = planned(cleanSched(d.sched)); d.touched.goal = true; const g = q('[data-f="goal"]', card); if (g) g.value = d.goal; syncCard(key); return; }
    if (t.closest("[data-save]")) return save(key);
    if (t.closest("[data-cancel]")) {
      if (key === NEW) { S.add = null; S.openKey = null; flip(flipNodes(), () => { card.remove(); renderAddZone(); }); renderWeek(); return; }
      delete S.drafts[key]; collapse(key, () => { const c = cardEl(key); if (c) { const tmp = document.createElement("div"); tmp.innerHTML = cardHTML(key); const nc = tmp.firstElementChild; nc.setAttribute("role", "listitem"); c.replaceWith(nc); roll(q(".hs-statn", nc), q(".hs-statn", nc).dataset.n); } renderWeek(); }); return;
    }
    if (t.closest("[data-remove]")) return remove(key);
  }
  function onKey(e) {
    if (!S.open) return;
    if (e.key === "Escape") {
      e.preventDefault(); e.stopPropagation();
      if (S.confirm) { hideConfirm(); return; }
      if (S.snack && S.el.contains(document.activeElement) && document.activeElement.closest(".hs-snack")) { hideSnack(); return; }
      if (S.openKey) { const k = S.openKey; collapse(k); const c = cardEl(k); if (c) q(".hs-row", c).focus({preventScroll: true}); return; }
      if (S.grid) { closeGrid(); return; }
      close(); return;
    }
    if ((e.metaKey || e.ctrlKey) && (e.key === "s" || e.key === "Enter")) { if (S.openKey) { e.preventDefault(); save(S.openKey); } return; }
    const rg = e.target.closest && e.target.closest('[role="radiogroup"]');
    if (rg && /^Arrow/.test(e.key)) {
      const bs = qa('[role="radio"]', rg), i = bs.indexOf(e.target.closest('[role="radio"]'));
      const n = bs[(i + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : bs.length - 1)) % bs.length];
      e.preventDefault(); n.focus(); n.click();
    }
  }
  function onFocusIn(e) {
    const t = e.target;
    if (!S.pinch || !t.closest || !t.closest(".hs-panel")) return;
    if (!t.matches("input, textarea, [role=radio], .hs-dayb, .hs-sb, [role=switch]")) return;
    S.focusField = t; pinchMood("listening"); gazeAt(t);
  }
  function onFocusOut(e) {
    if (!S.pinch) return;
    const n = e.relatedTarget;
    if (n && n.closest && n.closest(".hs-panel") && n.matches("input, textarea, [role=radio], .hs-dayb, .hs-sb, [role=switch]")) return;
    S.focusField = null;
    setTimeout(() => { if (!S.focusField && S.pinch) { pinchMood(); S.pinch.lookAt(null); } }, 80);
  }

  /* ---------- wiring ---------- */
  function wire() {
    S.el = document.getElementById("habitsSheet");
    if (!S.el || S.el.dataset.hsWired) return;
    S.el.dataset.hsWired = "1";
    S.el.addEventListener("click", onClick);
    S.el.addEventListener("input", e => { if (e.target.matches("[data-f], [data-rf]")) onInput(e); });
    S.el.addEventListener("change", e => { if (e.target.matches('[data-rf="at"]')) onInput(e); });
    S.el.addEventListener("focusin", onFocusIn);
    S.el.addEventListener("focusout", onFocusOut);
    S.el.addEventListener("scroll", () => {
      S.el.toggleAttribute("data-scrolled", S.el.scrollTop > 8);
      const k = q(".hs-stick", S.el); if (k) S.el.toggleAttribute("data-stuck", getComputedStyle(k).position === "sticky" && k.getBoundingClientRect().top <= 57);
    }, {passive: true});
    if (window.ResizeObserver) new ResizeObserver(() => { if (S.open) measureStick(); }).observe(S.el);
    document.addEventListener("keydown", onKey, true);
    addEventListener("resize", () => { if (S.open) measureStick(); });
    const btn = document.getElementById("habitsBtn");
    if (btn) btn.addEventListener("click", () => open());
    // Server state each second: the lens and the live guard follow the session; Today's line follows plan_today.
    setInterval(() => {
      if (!S.open || !S.pinch) return;
      const s = st(); if (!s) return;
      try { S.pinch.camera(!!(s.session && s.session.modality !== "digital" && !s.session.on_break)); } catch {}
      if (!S.focusField && S.pinch.state().mood !== "thinking") pinchMood();
    }, 1000);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire); else wire();

  window.openHabits = (key, draft) => { wire(); return open(key || null, draft || null); };
  window.AlibiHabits = {open: window.openHabits, close: () => close(), isOpen: () => S.open};
})();
