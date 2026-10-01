/* core.js: shared helpers, api()/postJSON, state polling + page mode, toast + alerts, layers (drawer/lightbox), schedule helpers, refreshAll/refreshSlow, route. Classic script; load order core, now, week, sessions, setup, onboarding, boot. */
const $ = s => document.querySelector(s);
const LABELS = ["on_task","phone","off_task","idle","absent"];
const LBL_TXT = {on_task:"on task",phone:"on phone",off_task:"something else",idle:"idle",absent:"away"};
const VWORD = {done:"Done", partial:"Partly done", slacked:"Didn't count"};
const CHECK_WORD = {physical:"checked by camera", digital:"checked by screen", hybrid:"camera + screen", strava:"Strava", health:"Apple Health"};
const plain = t => String(t || "").replace(/\bthe witness\b/gi, "Alibi").replace(/\bwitness\b/gi, "Alibi").replace(/(\d+) looks\b/g, "$1 checks").replace(/\bdeclared\b/g, "planned").replace(/\bdeclare\b/g, "start").replace(/: slacked\./g, ": didn't count.").replace(/: partial\b/g, ": partly done").replace(/ — a claim isn't evidence;/g, ";").replace(/\bmin seen\b/g, "min seen by Alibi").replace(/you're (.+?) behind pace/g, "$1 to go to stay on pace");
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const cvar = l => `var(--${LABELS.includes(l) ? l : "absent"})`;
const vvar = v => `var(--${["done","partial","slacked"].includes(v) ? v : "absent"})`;
const NAMES = {cpp:"C++", internships:"Internships"};
const hname = h => NAMES[h] || (h ? h[0].toUpperCase() + h.slice(1) : "—");
const pad = n => String(n).padStart(2,"0");
const clockT = t => { const d = new Date(t*1000); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
const dayT = t => new Date(t*1000).toLocaleDateString(undefined,{weekday:"short",day:"numeric",month:"short"});
const mmss = s => { s = Math.max(0, Math.round(s||0)); const h = Math.floor(s/3600), m = Math.floor(s%3600/60), x = s%60; return h ? `${h}:${pad(m)}:${pad(x)}` : `${pad(m)}:${pad(x)}`; };
const hm = min => { min = Math.round(min||0); return min >= 60 ? `${Math.floor(min/60)} h${min%60 ? " " + (min%60) + " min" : ""}` : `${min} min`; };
const pct = r => r == null ? "—" : Math.round(r*100) + "%";
const dur = s => { s = Math.max(0, s|0); const d = Math.floor(s/86400), h = Math.floor(s%86400/3600), m = Math.floor(s%3600/60); return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`; };

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

/* ---------- state / now ---------- */
let lastAlertId = null, firstState = true, nowSig = "", seenLabels = 0, lastFrame = null, liveSess = null, lastState = null;
let dismissedVerdict = null;
try { dismissedVerdict = +sessionStorage.getItem("alibi.dismissedVerdict") || null; } catch {}
const LBL_UP = {on_task:"On task",phone:"On your phone",off_task:"Off task",idle:"Idle",absent:"Away from desk"};
const cleanNote = n => (!n || /^seeded\b|\b(green|red|black|blue) frame\b|^mock\b/i.test(n)) ? "" : n;
const dispName = (key, label) => label || hname(key);

// Stage mode (demo + design renders): ?stage=NAME polls the fixture /web/fixtures/NAME.json instead of /api/state.
const STAGE = (/^[\w-]+$/.exec(new URLSearchParams(location.search).get("stage") || "") || [])[0] || null;
async function pollState() {
  let s;
  try { s = STAGE ? await api(`/web/fixtures/${STAGE}.json`, {cache: "no-store"}) : await api("/api/state?client=dashboard"); } catch {
    const st = $("#status"); st.className = "statepill idle"; $("#conn").textContent = "Alibi isn't running"; document.title = "Alibi — not running"; return;
  }
  lastState = s;
  if (Array.isArray(s.habits)) s.habits.forEach(h => { if (h.label) NAMES[h.key] = h.label; });
  renderStatus(s);
  renderNow(s.session, s.now, s.recent_verdict);
  renderToday(s.today);
  handleAlert(s.alert, s.now, s);
  AlibiMoments.state(s);
  if (s.session && $("#toast").classList.contains("planned")) hideToast();
  firstState = false;
}

function renderStatus(s) {
  const sess = s.session, st = $("#status");
  const rv = !sess && s.recent_verdict && s.recent_verdict.id !== dismissedVerdict ? s.recent_verdict : null;
  let text = rv ? `Just finished · ${dispName(rv.habit, rv.label)} — ${VWORD[rv.verdict] || rv.verdict || ""}` : s.status_text || (sess ? `In progress · ${dispName(sess.habit, sess.label)}` : "Ready");
  text = text.replace(/^Idle\b.*$/i, nextPlanText() || "Ready when you are").replace(/^Watching\b/, "In progress").replace(/\bWitness\b/g, "Alibi").replace(/\bdeclared\b/gi, "planned");
  st.className = "statepill " + (!sess ? "idle" : sess.on_break ? "brk" : sess.drifting ? "drift" : "");
  st.innerHTML = `<span class="pulse" id="pulse"></span><span id="conn">${esc(text)}</span>`;
  st.title = "";
  if (sess) {
    const left = sess.left_s ?? Math.max(0, sess.ends_at - s.now);
    const p = sess.warming_up || sess.on_task_so_far == null ? "" : ` · ${Math.round(sess.on_task_so_far * 100)}%`;
    document.title = `${sess.on_break ? "Break" : sess.drifting ? "Drifting" : mmss(left)} · ${dispName(sess.habit, sess.label)}${p} — Alibi`;
  } else if (s.recent_verdict && s.recent_verdict.id !== dismissedVerdict) {
    document.title = `${VWORD[s.recent_verdict.verdict] || ""} · ${dispName(s.recent_verdict.habit, s.recent_verdict.label)} — Alibi`;
  } else document.title = "Alibi";
}

function setMode(mode) {
  document.body.classList.toggle("live", mode === "live");
  document.body.classList.toggle("verdict", mode === "verdict");
  document.body.classList.toggle("idle", mode === "idle");
  $("#sayInput").placeholder = mode === "live" ? "Type “break 5”, “add 10” or “end”" : "What are you about to do? e.g. “draw for 25 minutes”";
  renderChips(habitsCfg?.habits, mode === "live");
}

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
  $("#toastKind").textContent = ({nudge:"still with it?", verdict:"how it went", report:"your week", info:"note", pace:"this week", recap:"today's reel", planned:"planned now"})[kind] || kind;
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
  $("#toastActs").innerHTML = acts.map((x, i) => `<button type="button" data-ti="${i}">${esc(x.label)}</button>`).join("");
}
$("#toastActs").addEventListener("click", e => {
  const b = e.target.closest("[data-ti]"); if (!b) return;
  const x = toastActs[+b.dataset.ti]; if (!x) return;
  hideToast();
  if (x.undo) return x.undo();
  if (x.post) return postJSON(x.post, x.body || {}).then(j => { loadPlan(); if (j && j.reply) showToast("note", j.reply); }).catch(() => showToast("note", "That didn't work — is Alibi running?"));
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
  lastFocus?.focus?.({preventScroll: true});
}
document.addEventListener("click", e => {
  const c = e.target.closest("[data-close]"); if (c) closeLayer(c.dataset.close);
  if (e.target.id === "lightbox") closeLayer("lightbox");
  if (e.target.id === "scrim") closeLayer("drawer");
  if ($("#pop").classList.contains("show") && !e.target.closest("#pop,.sm,.strip .dot")) closePop();
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
  $("#toastKind").innerHTML = `<span>${esc(kind === "correction" ? "fixed — you have the last word" : kind)}</span>`;
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
    <button type="button" class="del" data-sdel="${i}" aria-label="Remove this time">remove</button></div>`).join("");
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
  loadPlan();
  $("#foot").textContent = `updated ${clockT(Date.now()/1000)}`;
}

function route() {
  if (/^#setup/.test(location.hash)) openSetup();
  else if (location.hash === "#plan") $("#todayBlock").scrollIntoView({behavior: "smooth"});
}
