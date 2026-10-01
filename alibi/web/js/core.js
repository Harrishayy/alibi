/* core.js: shared helpers, api()/postJSON, state polling + page mode, toast + alerts, layers (drawer/lightbox), schedule helpers, refreshAll/refreshSlow, route. Classic script; load order core, now, week, sessions, setup, onboarding, boot. */
const $ = s => document.querySelector(s);
const LABELS = ["on_task","phone","off_task","idle","absent"];
const LBL_TXT = {on_task:"on task",phone:"on phone",off_task:"something else",idle:"idle",absent:"away"};
const VWORD = {done:"Done", partial:"Partly", slacked:"Slacked"};
const CHECK_WORD = {physical:"checked by camera", digital:"checked by screen", hybrid:"camera + screen", strava:"Strava", health:"Apple Health"};
const plain = t => String(t || "").replace(/\bthe witness\b/gi, "Alibi").replace(/\bwitness\b/gi, "Alibi").replace(/(\d+) looks\b/g, "$1 checks").replace(/\bdeclared\b/g, "planned").replace(/\bdeclare\b/g, "start").replace(/: slacked\./g, ": didn't count.").replace(/: partial\b/g, ": partly done").replace(/ — a claim isn't evidence;/g, ";").replace(/\bmin seen\b/g, "min seen by Alibi").replace(/you're (.+?) behind pace/g, "$1 to go to stay on pace");
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const TOK = {on_task:"on-task", off_task:"off-task", phone:"phone", idle:"idle", absent:"absent"};
const cvar = l => `var(--${TOK[l] || "absent"})`;
const vvar = v => `var(--${({done:"done", partial:"partly", slacked:"slacked"})[v] || "absent"})`;
const NAMES = {cpp:"C++", internships:"Internships"};
const hname = h => NAMES[h] || (h ? h[0].toUpperCase() + h.slice(1) : "—");
// A habit name mid-sentence: plain words go lowercase ("drawing"), names keep their case ("C++", "LinkedIn"). Same rule as moments.js.
const habitLc = h => { h = String(h || ""); return /^[A-Z][a-z]+( [a-z]+)*$/.test(h) ? h.toLowerCase() : h; };
const pad = n => String(n).padStart(2,"0");
const clockT = t => { const d = new Date(t*1000); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
const dayT = t => new Date(t*1000).toLocaleDateString(undefined,{weekday:"short",day:"numeric",month:"short"});
const mmss = s => { s = Math.max(0, Math.round(s||0)); const h = Math.floor(s/3600), m = Math.floor(s%3600/60), x = s%60; return h ? `${h}:${pad(m)}:${pad(x)}` : `${pad(m)}:${pad(x)}`; };
const hm = min => { min = Math.round(min||0); return min >= 60 ? `${Math.floor(min/60)}h${min%60 ? " " + (min%60) + "m" : ""}` : `${min} min`; };
const pct = r => r == null ? "—" : Math.round(r*100) + "%";
const dur = s => { s = Math.max(0, s|0); const d = Math.floor(s/86400), h = Math.floor(s%86400/3600), m = Math.floor(s%3600/60); return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`; };

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

/* ---------- state / now ---------- */
let lastAlertId = null, firstState = true, nowSig = "", seenLabels = 0, lastFrame = null, liveSess = null, lastState = null;
let dismissedVerdict = null, lastSessions = [];
try { dismissedVerdict = +sessionStorage.getItem("alibi.dismissedVerdict") || null; } catch {}
const LBL_UP = {on_task:"On task",phone:"On your phone",off_task:"Off task",idle:"Idle",absent:"Away from desk"};
const cleanNote = n => (!n || /^seeded\b|\b(green|red|black|blue) frame\b|^mock\b/i.test(n)) ? "" : n;
const dispName = (key, label) => label || hname(key);

// Stage mode (demo + design renders): ?stage=NAME polls the fixture /web/fixtures/NAME.json instead of /api/state.
const STAGE = (/^[\w-]+$/.exec(new URLSearchParams(location.search).get("stage") || "") || [])[0] || null;
async function pollState() {
  let s;
  try { s = STAGE ? await api(`/web/fixtures/${STAGE}.json`, {cache: "no-store"}) : await api("/api/state?client=dashboard"); } catch {
    // dataset.sig = "off" so the next good poll repaints the pill instead of finding its old signature unchanged.
    const st = $("#status"); st.className = "statepill off"; st.dataset.sig = "off"; $("#conn").textContent = "Alibi isn't running"; document.title = "Alibi · not running"; return;
  }
  lastState = s;
  if (Array.isArray(s.habits)) s.habits.forEach(h => { if (h.label) NAMES[h.key] = h.label; });
  renderStatus(s);
  renderNow(s.session, s.now, s.recent_verdict);
  renderToday(s.today);
  renderHeroStrip();
  renderPrivacy(s);
  handleAlert(s.alert, s.now, s);
  AlibiMoments.state(s);
  if (s.session && $("#toast").classList.contains("planned")) hideToast();
  firstState = false;
}

// Header state pill (canvas: "Watching · Drawing", "Verdict ready · camera off", "Camera off"): a StatusDot plus one short phrase.
function renderStatus(s) {
  const sess = s.session, st = $("#status");
  const rv = !sess && s.recent_verdict && s.recent_verdict.id !== dismissedVerdict ? s.recent_verdict : null;
  let text, dot, cls;
  if (sess) {
    const name = dispName(sess.habit, sess.label);
    if (sess.on_break) { text = `On a break · ${name}`; dot = "idle"; cls = "brk"; }
    else if (sess.drifting) { text = `Drifting · ${({phone: "phone", off_task: sess.drifting.label_text && !/^off.task$/i.test(sess.drifting.label_text) ? sess.drifting.label_text : "off task", idle: "idle", absent: "away"})[sess.drifting.label] || "off task"}`; dot = sess.drifting.label === "off_task" ? "off_task" : sess.drifting.label === "idle" ? "idle" : sess.drifting.label === "absent" ? "absent" : "phone"; cls = "drift"; }
    else { text = `Watching · ${name}`; dot = "on_task"; cls = "live"; }
  } else if (rv) { text = "Verdict ready · camera off"; dot = "absent"; cls = "idle"; }
  else { text = "Camera off"; dot = "absent"; cls = "idle"; }
  const sig = cls + "|" + dot + "|" + text;
  if (st.dataset.sig !== sig) {
    st.dataset.sig = sig;
    st.className = "statepill " + cls;
    st.innerHTML = `<span class="pulse" id="pulse">${cls === "live" ? `<span class="ping" aria-hidden="true"></span>` : ""}${AlibiIcons.dot(dot, 8)}</span><span id="conn">${esc(text)}</span>`;
  }
  if (sess) {
    const left = sess.left_s ?? Math.max(0, sess.ends_at - s.now);
    const p = sess.warming_up || sess.on_task_so_far == null ? "" : ` · ${Math.round(sess.on_task_so_far * 100)}%`;
    document.title = `${sess.on_break ? "Break" : sess.drifting ? "Drifting" : mmss(left)} · ${dispName(sess.habit, sess.label)}${p} · Alibi`;
  } else if (rv) {
    document.title = `${VWORD[rv.verdict] || ""} · ${dispName(rv.habit, rv.label)} · Alibi`;
  } else document.title = "Alibi";
}

function setMode(mode) {
  const b = document.body;
  ["live", "verdict", "idle"].forEach(m => b.classList.toggle(m, m === mode));
  renderChips(habitsCfg?.habits, mode === "live");
  renderLatest();
}

/* ---------- hero strip: the honesty line, from /api/report ---------- */
// Totals use "2h 10m" (Voice.md); under an hour "45 min".
const tot = min => { min = Math.round(min || 0); const h = Math.floor(min / 60), m = min % 60; return h ? `${h}h ${m}m` : `${m} min`; };
function renderHeroStrip() {
  const r = typeof lastReport !== "undefined" ? lastReport : null, line = $("#heroLine"), sub = $("#heroSub"), streakEl = $("#heroStreak");
  if (!r || !r.totals) return;
  const T = r.totals, rows = r.rows || [];
  let claimed = T.declared_min || 0, seen = T.verified_min || 0, honesty = T.honesty;
  let n = rows.reduce((a, x) => a + (x.sessions || 0), 0), sl = rows.reduce((a, x) => a + (x.verdicts?.slacked || 0), 0);
  // The just-finished verdict counts at once, like Sessions and Week, instead of waiting for the next /api/report.
  // /api/sessions comes from the same refresh as the report, so a session it lists is already in the totals.
  const rv = lastState?.recent_verdict;
  if (rv && rv.id != null && rv.verdict && !(lastSessions || []).some(x => x.id === rv.id) && (rv.started_at || 0) >= (r.week_start || 0)) {
    claimed += rv.declared_min || 0;
    seen += rv.verified_min ?? Math.round((rv.declared_min || 0) * (rv.on_task_ratio || 0));
    n += 1; if (rv.verdict === "slacked") sl += 1;
    honesty = claimed ? seen / claimed : null;
  }
  let h1, sm = "";
  if (!claimed && !seen) h1 = "Nothing claimed yet. What are you about to do?";
  else {
    h1 = `Claimed ${tot(claimed)} this week. Seen ${tot(seen)}.`;
    const sess = lastState?.session;
    if (sess) sm = `Finished sessions only. ${dispName(sess.habit, sess.label)} joins the count at ${clockT(sess.ends_at)}.`;
    else {
      sm = `${honesty == null ? "" : Math.round(honesty * 100) + "% of claimed time seen. "}${n} session${n === 1 ? "" : "s"}, ${sl ? sl + " slacked" : "none slacked"}.`;
    }
  }
  if (line.textContent !== h1) line.textContent = h1;
  if (sub.textContent !== sm) sub.textContent = sm;
  const days = Math.max(0, ...rows.map(x => x.streak_days || 0));
  const fr = rows.reduce((a, x) => Math.max(a, x.freezes_left ?? x.freezes ?? 0), 0);
  const frT = fr > 0 ? `${fr} freeze${fr === 1 ? "" : "s"} left` : "";
  const sig = days + "|" + frT;
  if (streakEl.dataset.sig === sig) return;
  const bump = streakEl.dataset.sig && days > (+streakEl.dataset.sig.split("|")[0] || 0);
  streakEl.dataset.sig = sig;
  streakEl.innerHTML = days ? `<span class="al-streak${bump ? " is-bumping" : ""}" role="img" aria-label="Streak: ${days} day${days === 1 ? "" : "s"}${frT ? ", " + frT : ""}">${AlibiIcons.svg("claw", 16)}<span class="al-streak__days" aria-hidden="true">${days} day${days === 1 ? "" : "s"}</span>${frT ? `<span class="al-streak__freeze" aria-hidden="true">${frT}</span>` : ""}</span>` : "";
  if (bump) setTimeout(() => streakEl.querySelector(".al-streak")?.classList.remove("is-bumping"), 140);
}

// Privacy line, exact to the witness in use (AGENTS.md hard rule 5).
function renderPrivacy(s) {
  const w = s.witness || "", el = $("#privacy");
  const t = (w === "apple" || w === "mock" || /local/i.test(s.witness_label || "")) ? `Frames are judged on this Mac by ${s.witness_label || "Apple Vision"}. The camera is off whenever no session runs.`
    : w ? `Frames go to ${s.witness_label || "NVIDIA's endpoint"} to be judged. The camera is off whenever no session runs.` : "The camera is off whenever no session runs.";
  if (el.textContent !== t) el.textContent = t;
  if (!$("#host").textContent) $("#host").textContent = location.host;
}

/* ---------- theme: System, Dark or Light (pre-paint script in index.html applies the saved choice) ---------- */
window.AlibiTheme = {
  get() { let t = null; try { t = localStorage.getItem("alibi.theme"); } catch {} return t === "dark" || t === "light" ? t : "system"; },
  set(mode) {
    const m = mode === "dark" || mode === "light" ? mode : "system";
    try { m === "system" ? localStorage.removeItem("alibi.theme") : localStorage.setItem("alibi.theme", m); } catch {}
    if (m === "system") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = m;
    document.dispatchEvent(new CustomEvent("alibi:theme", {detail: {mode: m}}));
    return m;
  },
};

/* ---------- alerts ---------- */
let toastTimer;
function handleAlert(a, now, s) {
  if (!a || a.id == null) return;
  if (a.id === lastAlertId) return;
  const kind = a.kind || "info";
  const fresh = !firstState || (kind !== "info" && (now - (a.ts || 0)) < 30);
  lastAlertId = a.id;
  if (!fresh) return;
  if (kind === "nudge" && AlibiMoments.nudge(a, s)) return;   // moments drew the nudge card; skip the toast
  if (kind === "verdict" || kind === "report" || kind === "recap") refreshSlow();
  if (kind === "info" && /daemon up|dashboard:|witness:/i.test(a.text || "")) return;   // developer chatter, not for users
  if (!(a.text || "").trim()) return;                                                       // never show an empty toast
  if (kind === "planned") { plannedKey = a.block_key; loadPlan(); }
  if (kind === "verdict" && s && !s.session && s.recent_verdict) return;                   // the Now panel holds the verdict
  const t = $("#toast");
  t.className = "toast " + kind;
  if (kind === "verdict") t.style.setProperty("--c", vvar(a.verdict || (/\b(done|partial|slacked)\b/i.exec(a.text || "") || [])[1]?.toLowerCase()));
  $("#toastKind").textContent = ({nudge:"Still with it?", verdict:"How it went", report:"Your week", info:"Note", pace:"This week", recap:"Today's reel", planned:"Planned now", synced:"Synced"})[kind] || "Note";
  $("#toastText").textContent = plain(a.text || "");
  const img = $("#toastImg");
  if (a.image_url && kind !== "nudge") { img.src = a.image_url; img.hidden = false; } else { img.hidden = true; img.removeAttribute("src"); }
  renderToastActs(a.actions || []);
  requestAnimationFrame(() => t.classList.add("show"));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(hideToast, kind === "info" ? 5000 : kind === "nudge" || kind === "planned" ? 60000 : a.image_url ? 16000 : 11000);
}
let toastActs = [];
function renderToastActs(acts) {
  toastActs = acts;
  $("#toastActs").innerHTML = acts.map((x, i) => `<button type="button" class="al-btn al-btn--sm ${i ? "al-btn--quiet" : "al-btn--primary"}" data-ti="${i}">${esc(x.label)}</button>`).join("");
}
$("#toastActs").addEventListener("click", e => {
  const b = e.target.closest("[data-ti]"); if (!b) return;
  const x = toastActs[+b.dataset.ti]; if (!x) return;
  hideToast();
  if (x.undo) return x.undo();
  if (x.post) return postJSON(x.post, x.body || {}).then(j => { loadPlan(); if (j && j.reply) showToast("note", j.reply); }).catch(() => showToast("note", "That didn't save. Check Alibi is running, then try again."));
  if (x.say) return say(x.say);
  if (x.url) {
    if (x.url.startsWith("/api/reel")) return playReel(x.url, x.label);
    const m = /#session-(\d+)/.exec(x.url); if (m) return gotoSession(+m[1]);
    window.open(x.url, "_blank", "noopener");
  }
});
function hideToast() { $("#toast").classList.remove("show"); }

const localDate = (d = new Date()) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
/* ---------- layers: drawer, lightbox ---------- */
let lastFocus = null;
function openLayer(id) {
  lastFocus = document.activeElement;
  const el = document.getElementById(id);
  el.classList.add("show"); el.setAttribute("aria-hidden", "false");
  if (id === "drawer") $("#scrim").classList.add("show");
  syncInert();
  document.body.style.overflow = "hidden";
  setTimeout(() => el.querySelector(".xbtn")?.focus({preventScroll: true}), 60);
}
function closeLayer(id) {
  const el = document.getElementById(id);
  if (!el.classList.contains("show")) return;
  el.classList.remove("show"); el.setAttribute("aria-hidden", "true");
  if (id === "drawer") { $("#scrim").classList.remove("show"); loadHealth(); }
  if (id === "lightbox") { el.querySelector("video")?.pause(); setTimeout(() => { if (!el.classList.contains("show")) $("#lbBody").innerHTML = ""; }, 350); }
  if (!document.querySelector(".drawer.show,.lightbox.show")) document.body.style.overflow = "";
  syncInert();   // now, not in the observer's microtask: the page must be focusable again before focus returns to it
  lastFocus?.focus?.({preventScroll: true});
}
// Closed overlays (drawer, lightbox, onboarding) stay out of the tab order, and an open drawer or lightbox makes the page
// behind it inert, so Tab stays inside the dialog. Watches the .show class, so onboarding.js needs no change.
function syncInert() {
  const L = ["drawer", "lightbox", "onb"].map(id => document.getElementById(id)).filter(Boolean);
  L.forEach(el => { el.inert = !el.classList.contains("show"); });
  const modal = document.querySelector(".drawer.show,.lightbox.show"), wrap = document.querySelector(".wrap");
  if (wrap) wrap.inert = !!modal;
  document.querySelectorAll("body > .skip").forEach(el => { el.inert = !!modal; });
}
{ const mo = new MutationObserver(syncInert);
  ["drawer", "lightbox", "onb"].forEach(id => { const el = document.getElementById(id); if (el) mo.observe(el, {attributes: true, attributeFilter: ["class"]}); });
  syncInert(); }
// The count beside Setup is warn ink only; say it too.
{ const n = $("#setupN"), b = $("#setupBtn");
  if (n && b) new MutationObserver(() => { const k = parseInt((n.textContent || "").replace(/\D+/g, ""), 10) || 0;
    b.setAttribute("aria-label", k ? `Setup, ${k} need${k === 1 ? "s" : ""} you` : "Setup"); }).observe(n, {childList: true, characterData: true, subtree: true}); }
document.addEventListener("click", e => {
  const c = e.target.closest("[data-close]"); if (c) closeLayer(c.dataset.close);
  if (e.target.id === "lightbox") closeLayer("lightbox");
  if (e.target.id === "scrim") closeLayer("drawer");
  if ($("#pop").classList.contains("show") && !e.target.closest("#pop,.sm,.strip .dot,.vframe")) closePop();
});
document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if ($("#pop").classList.contains("show")) return closePop(true);
  if ($("#lightbox").classList.contains("show")) return closeLayer("lightbox");
  closeLayer("drawer");
});

function showToast(kind, text, c, acts, ms) {
  const t = $("#toast");
  t.className = "toast verdict"; t.style.setProperty("--c", c || "var(--accent)");
  const title = ({correction: "Fixed", started: "Started", note: "Note"})[kind] || (kind ? kind[0].toUpperCase() + kind.slice(1) : "Note");
  $("#toastKind").innerHTML = `<span>${esc(title)}</span>`;
  $("#toastText").textContent = text;
  const img = $("#toastImg"); img.hidden = true; img.removeAttribute("src");
  renderToastActs(acts || []);
  requestAnimationFrame(() => t.classList.add("show"));
  clearTimeout(toastTimer); toastTimer = setTimeout(hideToast, ms || (acts && acts.length ? 10000 : 7000));
}

/* ---------- helpers ---------- */
async function postJSON(path, body) {
  const r = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body || {})});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : (j.reason || r.status));
  return j;
}
const DAYS = ["mon","tue","wed","thu","fri","sat","sun"], DAY1 = {mon:"M",tue:"T",wed:"W",thu:"T",fri:"F",sat:"S",sun:"S"}, DAYNAME = {mon:"Monday",tue:"Tuesday",wed:"Wednesday",thu:"Thursday",fri:"Friday",sat:"Saturday",sun:"Sunday"};
const CHECKS = [["camera","Camera on my desk"],["screen","What's on my screen"],["both","Both"]];
const CHECK_TO_MOD = {camera:"physical", screen:"digital", both:"hybrid"}, MOD_TO_CHECK = {physical:"camera", digital:"screen", hybrid:"both"};
const METRIC = {steps:["steps","steps a day",1], sleep_h:["hours","hours of sleep",0.5], mindful_min:["min","mindful minutes a day",1], workout_min:["min","workout minutes a day",5]};
const slugify = t => (String(t || "").toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").replace(/^(\d)/, "h$1") || "habit").slice(0, 24);
let habView = {};
async function loadView() {
  try { const j = await api("/api/habits/view"); habView = Object.fromEntries((j.habits || []).map(h => [h.key, h])); } catch {}
}
function schedRows(sched, attr) {
  return (sched || []).map((r, i) => `<div class="srow" data-${attr}="${i}">
    <span class="days" role="group" aria-label="Days">${DAYS.map(d => `<button type="button" data-day="${d}" aria-pressed="${(r.days || []).includes(d)}" aria-label="${DAYNAME[d]}">${DAY1[d]}</button>`).join("")}</span>
    <input class="fld" type="time" data-sf="at" value="${esc(r.at || "19:00")}" aria-label="Time">
    <span class="minbox"><input class="fld" type="number" min="1" max="240" data-sf="min" value="${esc(r.min ?? 25)}" aria-label="Minutes">min</span>
    <button type="button" class="del" data-sdel="${i}" aria-label="Remove this time">Remove</button></div>`).join("");
}
function readSched(container, attr) {
  return [...container.querySelectorAll(`.srow[data-${attr}]`)].map(r => ({
    days: [...r.querySelectorAll("[data-day][aria-pressed=true]")].map(b => b.dataset.day),
    at: r.querySelector('[data-sf="at"]').value, min: Math.round(+r.querySelector('[data-sf="min"]').value || 0)}));
}
const schedOk = sc => sc.every(r => r.days.length && /^\d\d:\d\d$/.test(r.at) && r.min >= 1);

async function refreshAll() { await Promise.all([loadHabits(), loadView()]); pollState(); refreshSlow(); loadHealth(); }

async function refreshSlow() {
  const [r, s] = await Promise.allSettled([api("/api/report"), api("/api/sessions")]);
  if (s.status === "fulfilled") renderSessions(s.value);
  if (r.status === "fulfilled") { renderReport(r.value); renderHealthLines(); loadWeekPlan(); }
  if (s.status === "fulfilled") lastSessions = Array.isArray(s.value) ? s.value : (s.value?.sessions || []);
  loadPlan();
  renderHeroStrip(); renderLatest();
  $("#foot").textContent = `Updated ${clockT(Date.now()/1000)}`;
}

function route() {
  if (/^#setup/.test(location.hash)) openSetup();
  else if (location.hash === "#plan") $("#todayBlock").scrollIntoView({behavior: "smooth"});
}
