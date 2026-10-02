/* week.js: Today timeline, week hero, This week (7-dot grid, claimed vs seen bars, report line), pace rows.
   Also the shared marks the week and sessions areas draw with (wkIcon, wkDot, wkPill, wkGlyph).
   Classic script; load order core, now, week, sessions, setup, onboarding, boot. */

/* ---------- shared marks (week + sessions) ---------- */
// Icon set: 1.5px stroke on a 24 grid (system/project components). window.AlibiIcons (icons.js) wins when it is loaded.
const WK_ICONS = {
  play: '<path d="M8 5.6v12.8a1 1 0 0 0 1.53.85l10.2-6.4a1 1 0 0 0 0-1.7L9.53 4.75A1 1 0 0 0 8 5.6z"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  x: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
  camera: '<path d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2.4l1.3-2h5.6l1.3 2h2.4A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5z"/><circle cx="12" cy="12.75" r="3.25"/>',
  laptop: '<rect x="5" y="5.5" width="14" height="10" rx="1.5"/><path d="M3 18.5h18"/>',
  phone: '<rect x="7" y="3" width="10" height="18" rx="2.5"/><path d="M11 18h2"/>',
  run: '<circle cx="15.5" cy="4.5" r="1.75"/><path d="M13.5 7.5L10.5 13M13.2 8.4l2.8 1.8 2.5-.6M12.9 8.2l-3 .3-2.2 2M10.5 13l3.4 2-.6 4.5M10.5 13l-1.3 3.4H5.5"/>',
  heart: '<path d="M12 19.5s-7.5-4.4-7.5-10A4.25 4.25 0 0 1 12 6.9a4.25 4.25 0 0 1 7.5 2.6c0 5.6-7.5 10-7.5 10z"/>',
  moon: '<path d="M19.5 14.6A7.75 7.75 0 1 1 9.4 4.5a6.25 6.25 0 0 0 10.1 10.1z"/>',
  calendar: '<rect x="4" y="5.5" width="16" height="14.5" rx="2.5"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
  flag: '<path d="M5.5 21V4.5M5.5 4.5h11.5l-2.25 4 2.25 4H5.5"/>',
  film: '<rect x="4" y="4" width="16" height="16" rx="2.5"/><path d="M8.5 4v16M15.5 4v16M4 9h4.5M4 15h4.5M15.5 9H20M15.5 15H20"/>',
  "chevron-down": '<path d="M6 9.5l6 6 6-6"/>',
  "chevron-right": '<path d="M9.5 6l6 6-6 6"/>',
  undo: '<path d="M9 13.5L4 8.5l5-5"/><path d="M4 8.5h10.25a5.75 5.75 0 0 1 0 11.5H10"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  cup: '<path d="M5 9.5h11v4A5.5 5.5 0 0 1 10.5 19h0A5.5 5.5 0 0 1 5 13.5z"/><path d="M16 11h1.25a2.5 2.5 0 0 1 0 5H15.4M8.5 3.5v3M12.5 3.5v3"/>',
  "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
};
function wkIcon(name, size = 20) {
  try {
    const s = window.AlibiIcons && window.AlibiIcons.svg && window.AlibiIcons.svg(name, size);
    if (s) return typeof s === "string" ? s : s.outerHTML;
  } catch {}
  const p = WK_ICONS[name]; if (!p) return "";
  return `<svg class="al-icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${p}</svg>`;
}
const MOD_ICON = {physical: "camera", digital: "laptop", hybrid: "camera", strava: "run", health: "heart"};
const habitIcon = (key, mod) => /sleep/i.test(key || "") ? "moon" : /run/i.test(key || "") ? "run" : MOD_ICON[mod] || "flag";

// StatusDot: colour plus shape, always (README "Status is colour plus shape").
const WK_STATUS = {on_task: ["On task", "on-task"], idle: ["Idle", "idle"], phone: ["Phone", "phone"], off_task: ["Off task", "off-task"], absent: ["Away", "absent"]};
let wkUid = 0;
function wkMark(label, s) {
  const c = s / 2, r = s * 0.4;
  if (label === "on_task") return `<circle cx="${c}" cy="${c}" r="${r}" fill="currentColor"/>`;
  if (label === "idle") { const sw = s < 12 ? 1.5 : 2; return `<circle cx="${c}" cy="${c}" r="${r - sw / 2}" fill="none" stroke="currentColor" stroke-width="${sw}"/>`; }
  if (label === "phone") { const side = s * 0.76, o = (s - side) / 2; return `<rect x="${o}" y="${o}" width="${side}" height="${side}" rx="${s * 0.2}" fill="currentColor"/>`; }
  if (label === "off_task") {
    const id = "wkh" + (++wkUid), step = Math.max(2.5, s / 4.5); let d = "";
    for (let k = -s; k <= s; k += step) d += `M${k} ${s}L${k + s} 0`;
    return `<clipPath id="${id}"><circle cx="${c}" cy="${c}" r="${r}"/></clipPath><circle cx="${c}" cy="${c}" r="${r}" fill="currentColor" opacity="0.28"/><path d="${d}" stroke="currentColor" stroke-width="${Math.max(1, s / 10)}" clip-path="url(#${id})"/><circle cx="${c}" cy="${c}" r="${r - 0.6}" fill="none" stroke="currentColor" stroke-width="1.2"/>`;
  }
  const rr = r - 0.75, dash = 2 * Math.PI * rr / Math.max(6, Math.round(s / 1.6));
  return `<circle cx="${c}" cy="${c}" r="${rr}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="${(dash * .55).toFixed(2)} ${(dash * .45).toFixed(2)}"/>`;
}
function wkDot(label, s = 8, opts = {}) {
  const st = WK_STATUS[label] ? label : "absent", [word, cls] = WK_STATUS[st];
  const a = opts.word ? "" : opts.hidden ? ` aria-hidden="true"` : ` role="img" aria-label="${word}"`;
  return `<span class="al-dot al-dot--${cls}${s < 16 ? " is-small" : ""}"${a}><svg class="al-dot__mark" width="${s}" height="${s}" viewBox="0 0 ${s} ${s}" aria-hidden="true" focusable="false">${wkMark(st, s)}</svg>${opts.word ? `<span class="al-dot__word">${word}</span>` : ""}</span>`;
}
const wkWord = l => (WK_STATUS[l] || WK_STATUS.absent)[0];

// VerdictPill: glyph and word, always. ✓ Done · ◐ Partly · ✕ Slacked.
const WK_VERDICT = {done: "Done", partial: "Partly", slacked: "Slacked"};
function wkGlyph(v, size = 14) {
  const a = `width="${size}" height="${size}" viewBox="0 0 16 16" aria-hidden="true" focusable="false" class="al-verdict__glyph"`;
  if (v === "done") return `<svg ${a}><path d="M3.5 8.4l3 3 6-6.4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  if (v === "partial") return `<svg ${a}><circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" stroke-width="1.75"/><path d="M8 2.5a5.5 5.5 0 0 1 0 11z" fill="currentColor"/></svg>`;
  return `<svg ${a}><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`;
}
function wkPill(v, ratio) {
  if (!WK_VERDICT[v]) return `<span class="wk-nopill">No verdict</span>`;
  const r = ratio == null ? null : Math.round(ratio * 100);
  return `<span class="al-verdict al-verdict--${v}" role="img" aria-label="Verdict: ${WK_VERDICT[v].toLowerCase()}${r == null ? "" : ", " + r + "%"}">${wkGlyph(v)}<span class="al-verdict__word">${WK_VERDICT[v]}</span>${r == null ? "" : `<span class="al-verdict__ratio">${r}%</span>`}</span>`;
}
// Totals read "2h 10m"; chrome reads "25 min" (Voice).
const wkHM = min => { min = Math.round(min || 0); const h = Math.floor(min / 60), m = min % 60; return h ? `${h}h${m ? " " + m + "m" : ""}` : `${m} min`; };
// First paint of a block plays its entrance when it scrolls into view; later refreshes swap content quietly.
// Automated renders (navigator.webdriver) and reduced motion play at once, so full-page captures never catch a held state.
const wkReduced = () => { try { return matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; } };
const wkIO = !navigator.webdriver && "IntersectionObserver" in window
  ? new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { wkIO.unobserve(e.target); wkPlay(e.target); } }), {rootMargin: "0px 0px -12% 0px"}) : null;
function wkPlay(el) {
  el.classList.remove("wk-pre"); el.classList.add("wk-enter");
  setTimeout(() => el.classList.remove("wk-enter"), 1800);
}
function wkEnter(el) {
  if (wkIO && !wkReduced()) { el.classList.add("wk-pre"); wkIO.observe(el); } else wkPlay(el);
}
function wkPaint(el, html) {
  if (!el) return false;
  if (el.dataset.wkSig === html) return false;
  const first = !el.dataset.wkSig;
  el.dataset.wkSig = html; el.innerHTML = html;
  if (first) wkEnter(el);
  return true;
}

function renderToday(t) { lastToday = t; renderHero(); renderTodayMeta(); if (typeof syncLiveSession === "function") syncLiveSession(); }
// Stage fixtures carry their own clock; live pages use the wall clock.
const wkNow = () => (typeof STAGE !== "undefined" && STAGE && lastState?.now) || Date.now() / 1000;
let lastToday = null, lastReport = null;

/* ---------- week hero (kept compact; the hero strip above Now is the shell's) ---------- */
const fmtN = n => Math.round(n || 0).toLocaleString("en-GB");
function renderHero() {
  const r = lastReport, t = lastToday, box = $("#weekHero");
  if (!box || !r || !r.totals) return;
  const T = r.totals, tgt = Math.max(1, T.target_min || 0);
  const fresh = !(T.declared_min || T.verified_min);
  const gap = Math.max(0, (T.pace_min || 0) - (T.verified_min || 0));
  const hon = T.honesty, honP = hon == null ? null : Math.round(hon * 100);
  const frac = Math.min(1, (T.verified_min || 0) / tgt), pace = Math.min(1, (T.pace_min || 0) / tgt);
  const sub = fresh ? "Your first session sets the pace."
    : gap <= 0 ? "On pace for the week." : `${wkHM(gap)} to an even pace.`;
  wkPaint(box, `
    <div class="wh-stat"><span class="t-label">Seen this week</span>
      <span class="wh-num">${esc(wkHM(T.verified_min))}<small>of ${esc(wkHM(T.target_min))}</small></span>
      <span class="al-meter" role="img" aria-label="${fmtN(T.verified_min)} of ${fmtN(T.target_min)} minutes seen this week"><span class="al-meter__track"><span class="al-meter__fill" style="transform:scaleX(${frac.toFixed(3)})"></span></span>${!fresh && pace > 0 && pace < 1 ? `<span class="al-meter__tick" style="left:${(pace * 100).toFixed(1)}%"></span>` : ""}</span>
      <span class="wh-sub">${esc(sub)}</span></div>
    <div class="wh-stat"><span class="t-label">Claims that held up</span>
      <span class="wh-num">${honP == null ? "—" : honP + "%"}</span>
      <span class="wh-sub">${honP == null ? "Appears after your first session." : `${esc(wkHM(T.verified_min))} seen of ${esc(wkHM(T.declared_min))} claimed`}</span></div>
    <div class="wh-stat"><span class="t-label">Today</span>
      <span class="wh-num">${t ? `${t.habits_done || 0}<small>of ${t.habits_total || 0} habits</small>` : "—"}</span>
      <span class="wh-sub">${t && t.declared_min ? `${esc(wkHM(t.verified_min))} seen of ${esc(wkHM(t.declared_min))}` : "Nothing claimed yet."}</span></div>`);
}

/* ---------- report ---------- */
let wkFullOpen = false;
// Report sentences in Pinch's voice: totals as "1h 37m", pace as a fact, not a nag.
const wkVoice = t => plain(String(t || "").replace(/, you're (.+?) behind pace/g, " is $1 behind an even pace")).replace(/(\d+) h (\d+) min\b/g, "$1h $2m").replace(/(\d+) h\b/g, "$1h");
// One sentence per row: split after . ? or ! followed by a space, so "5.2 km" and "08:00" stay whole.
const wkSentences = t => String(t || "").replace(/([.!?])\s+(?=\S)/g, "$1\u0000").split("\u0000").map(x => x.trim()).filter(Boolean);
function reportLine(r) {
  const sents = (r.summary || "").match(/[^.!?]+[.!?]+(\s|$)|[^.!?]+$/g) || [];
  const pull = sents.filter(x => /^\s*(Today|Tomorrow):/.test(x)).join(" ").trim() || sents.slice(-1).join("").trim();
  return {pull: wkVoice(pull), more: sents.length > 1};
}
function renderReport(r) {
  if (!r) return;
  lastReport = r; renderHero();
  try { document.dispatchEvent(new CustomEvent("alibi:report", {detail: r})); } catch {}
  if (r.week_start && $("#weekRange")) {
    const ws = new Date(r.week_start * 1000), we = new Date((r.week_start + 6 * 86400) * 1000);
    const f = d => `${d.getDate()} ${"Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ")[d.getMonth()]}`;
    $("#weekRange").textContent = `${f(ws)} to ${f(we)}`;
  }
  // The report line now lives inside the week card; the legacy quote block stays empty.
  const q = $("#quote"); if (q) { q.textContent = ""; q.hidden = true; }
  const rm = document.querySelector("#weekBlock .readmore"); if (rm) rm.hidden = true;
  const fr = $("#fullRep"); if (fr) fr.hidden = true;
  renderGrid();
  renderPace(r);
}

function renderPace(r) {
  const box = $("#rows"); if (!box) return;
  const fresh = !(r.totals?.declared_min || r.totals?.verified_min);
  const sorted = [...(r.rows || [])].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));
  const rows = sorted.map(x => {
    const scale = Math.max(x.target_min || 0, x.declared_min || 0, 1);
    const f = v => Math.min(1, (v || 0) / scale).toFixed(3);
    const sev = x.severity || (x.status === "aligned" ? "on_pace" : "behind");
    const gap = x.gap_to_pace_min ?? x.behind_by_min ?? 0;
    const st = x.is_new && !(x.verified_min >= (x.target_min || 1)) ? `New · ${x.target_min ? wkHM(x.target_min) + " planned" : "starts next week"}`
      : sev === "on_pace" ? "On pace"
      : fresh || !x.sessions ? (x.target_min ? `${wkHM(x.target_min)} this week` : "")
      : `${wkHM(gap)} to an even pace`;
    const meta = [CHECK_WORD[x.modality], `${x.sessions ?? 0} session${x.sessions === 1 ? "" : "s"}`, x.streak_days ? `${x.streak_days}\u2011day streak` : ""].filter(Boolean).join(" · ");
    const pace = x.pace_target_min != null && !fresh && !x.is_new ? Math.min(1, x.pace_target_min / scale) : null;
    return `<div class="pr" role="row">
      <div class="pr-name" role="rowheader"><span class="pr-ic">${wkIcon(habitIcon(x.habit, x.modality), 16)}</span><span><b>${esc(dispName(x.habit, x.label))}</b><small>${esc(meta)}</small></span></div>
      <div class="pr-bars" role="cell" aria-label="Claimed ${x.declared_min || 0} min, seen ${x.verified_min || 0} min, goal ${x.target_min || 0} min">
        <span class="pr-bar pr-claimed"><i style="transform:scaleX(${f(x.declared_min)})"></i></span>
        <span class="pr-bar pr-seen"><i style="transform:scaleX(${f(x.verified_min)})"></i></span>
        ${pace != null && pace > 0 && pace < 1 ? `<span class="pr-pace" style="left:${(pace * 100).toFixed(1)}%" title="Even pace: ${x.pace_target_min} min"></span>` : ""}
      </div>
      <div class="pr-nums" role="cell"><span><b>${x.verified_min ?? 0}</b> of ${x.declared_min ?? 0} min</span><small class="${sev === "on_pace" ? "ok" : ""}">${esc(st)}</small></div>
    </div>`;
  });
  const run = r.running;
  if (run) {
    const n = run.target_sessions || 3, runs = run.runs || [];
    const pips = Array.from({length: Math.max(n, runs.length)}, (_, i) => {
      const rr = [...runs].sort((a, b) => (b.distance_km >= run.min_km) - (a.distance_km >= run.min_km) || a.start_date - b.start_date)[i];
      if (!rr) return `<span class="pr-pip" title="Not yet">${wkCell("notyet")}</span>`;
      const ok = rr.distance_km >= (run.min_km || 0);
      return `<span class="pr-pip" title="${esc(rr.name)} · ${rr.distance_km} km · ${dayT(rr.start_date)}${ok ? "" : ` · under ${run.min_km} km`}">${wkCell(ok ? "done" : "partial")}<small>${rr.distance_km}</small></span>`;
    }).join("");
    const left = n - (run.qualifying ?? 0);
    rows.push(`<div class="pr" role="row">
      <div class="pr-name" role="rowheader"><span class="pr-ic">${wkIcon("run", 16)}</span><span><b>${esc(dispName(run.habit || "running", run.label))}</b><small>Strava · runs of ${run.min_km} km or more</small></span></div>
      <div class="pr-pips" role="cell">${pips}</div>
      <div class="pr-nums" role="cell"><span><b>${run.qualifying ?? 0}</b> of ${n} runs</span><small class="${left > 0 ? "" : "ok"}">${left > 0 ? `${left} to go · ${run.week_km ?? 0} km` : "Goal met"}</small></div>
    </div>`);
  }
  (r.health || []).forEach(x => {
    const pips = (x.days || []).slice(-7).map(d => `<span class="pr-pip" title="${esc(d.date)} · ${esc(d.text || "no data")}">${wkCell(d.met ? "done" : d.met === false ? "slacked" : "notyet")}</span>`).join("");
    rows.push(`<div class="pr" role="row">
      <div class="pr-name" role="rowheader"><span class="pr-ic">${wkIcon(habitIcon(x.habit, "health"), 16)}</span><span><b>${esc(x.label || hname(x.habit))}</b><small>Apple Health · ${esc(x.target_text || "")}</small></span></div>
      <div class="pr-pips" role="cell">${pips || `<small class="pr-none">No data from your iPhone yet.</small>`}</div>
      <div class="pr-nums" role="cell"><span><b>${x.days_met ?? 0}</b> of ${x.days_checked ?? 0} days</span><small class="${x.status === "aligned" ? "ok" : ""}">${x.status === "no_data" ? "Waiting for iPhone" : x.status === "aligned" ? "On track" : esc(x.text || "")}</small></div>
    </div>`);
  });
  const legend = `<div class="pr-key"><span><i class="k-claimed"></i>Claimed</span><span><i class="k-seen"></i>Seen</span><span><i class="k-pace"></i>Even pace</span></div>`;
  wkPaint(box, rows.length ? legend + `<div class="pr-list" role="table" aria-label="Minutes, targets and pace by habit">${rows.join("")}</div>` : `<p class="wk-empty">No habits yet.</p>`);
}

/* ---------- today: the timeline ---------- */
let planData = null, weekPlan = [], plannedKey = null;
const createdTs = k => { const c = habView[k]?.created_at; if (!c) return 0; const [d, t] = c.split(" "); const [Y, M, D] = d.split("-").map(Number); const [h, m] = (t || "0:0").split(":").map(Number); return new Date(Y, M - 1, D, h, m).getTime() / 1000; };
const createdDay = k => (habView[k]?.created_at || "").slice(0, 10);
const beforeCreated = b => b.end && createdTs(b.habit) && b.end < createdTs(b.habit) && !b.session_id;
const inWords = sec => { sec = Math.max(0, sec | 0); const h = Math.floor(sec / 3600), m = Math.round(sec % 3600 / 60); return h ? `${h}h${m ? " " + m + "m" : ""}` : `${Math.max(1, m)} min`; };
function nextPlanText() {
  const n = planData?.next; if (!n) return "";
  return n.state === "now" ? `${n.label} is planned now` : `Next: ${n.label} at ${n.at}`;
}
async function loadPlan() {
  try { planData = await api("/api/calendar/plan?days=1"); } catch { planData = null; }
  renderPlan();
}
function renderTodayMeta() {
  const head = document.querySelector("#todayBlock .todayhead"); if (!head) return;
  let m = $("#todayMeta");
  if (!m) { m = document.createElement("span"); m.id = "todayMeta"; m.className = "wk-meta"; const acts = head.querySelector(".sacts"); acts ? acts.prepend(m) : head.append(m); }
  const t = lastToday, now = clockT(wkNow()), pt = typeof lastPlanToday !== "undefined" ? lastPlanToday : null;
  // Same metric as the island footer: blocks kept of blocks planned today, once there's a plan.
  const txt = pt && pt.total > 0 ? `${pt.kept || 0} of ${pt.total} kept · ${now}` : t && t.habits_total ? `${t.habits_done || 0} of ${t.habits_total} done · ${now}` : now;
  if (m.textContent !== txt) m.textContent = txt;
}
function renderPlan() {
  const tt = $("#todayTitle"); if (tt && tt.textContent !== "Today") tt.textContent = "Today";
  renderTodayMeta();
  const box = $("#blocks"), nx = $("#nextUp"); if (!box) return;
  const anySched = Object.values(habView).some(h => (h.schedule || []).length);
  const pw = $("#planWeek"); if (pw) pw.textContent = anySched ? "Change times" : "Plan my week";
  const blocks = planData ? (planData.blocks || []).filter(b => !beforeCreated(b)) : [];
  const pk = plannedKey && blocks.find(b => b.key === plannedKey);
  if (pk && !["planned", "now"].includes(pk.state) && $("#toast")?.classList.contains("planned")) hideToast();
  // The composer's next line (now.js) already says what's next; the timeline shows it in place.
  if (nx) { nx.dataset.html = ""; nx.innerHTML = ""; if (typeof renderPlanSummary === "function") renderPlanSummary(lastPlanToday); }
  // Items: plan blocks, plus today's sessions that weren't planned, plus the live session.
  const today = localDate(), nowS = wkNow(), items = [];
  const planned = new Set(blocks.map(b => b.session_id).filter(Boolean));
  const liveId = lastState?.session?.id;
  blocks.forEach(b => {
    const s = b.session_id ? sessById.get(b.session_id) : null, auto = b.check === "strava" || b.check === "health";
    const v = ["done", "partial", "slacked"].includes(b.state) ? b.state : null;
    const meta = s && s.verified_min != null ? `${s.verified_min} of ${s.declared_min} min seen`
      : [hm(b.min), CHECK_WORD[CHECK_TO_MOD[b.check]] || CHECK_WORD[b.check] || "", b.in_calendar ? "Calendar" : "", b.moved ? `was ${b.planned_at}` : ""].filter(Boolean).join(" · ");
    items.push({ts: b.start, time: b.at, title: b.label || dispName(b.habit), meta, icon: v || b.state === "live" ? habitIcon(b.habit, CHECK_TO_MOD[b.check] || b.check) : "calendar",
      state: b.state, verdict: v, ratio: auto ? null : b.ratio, key: b.key, at: b.at, auto, sid: b.session_id});
  });
  sessById.forEach(s => {
    if (planned.has(s.id) || dayKey(s) !== today) return;
    const live = s.id === liveId || (!s.verdict && !s.ended_at);
    items.push({ts: s.started_at, time: clockT(s.started_at), title: dispName(s.habit, s.label), icon: habitIcon(s.habit, s.modality),
      meta: live ? `${hm(s.declared_min)} · in progress` : `${s.verified_min ?? 0} of ${s.declared_min ?? 0} min seen`,
      state: live ? "live" : s.verdict || "done", verdict: live ? null : s.verdict, sid: s.id});
  });
  if (liveId && !items.some(i => i.sid === liveId) && lastState.session) {
    const s = lastState.session;
    items.push({ts: s.started_at, time: clockT(s.started_at), title: dispName(s.habit, s.label), icon: habitIcon(s.habit, s.modality), meta: `${hm(s.declared_min)} · in progress`, state: "live", sid: s.id});
  }
  items.sort((a, b) => a.ts - b.ts);
  if (!items.length) {
    wkPaint(box, `<div class="tl-empty"><p>${anySched ? "Nothing planned for today. Start something whenever you like." : "Give your habits a time and Alibi reminds you when it's time. It can put them in Apple Calendar too."}</p>${anySched ? "" : `<button class="al-btn al-btn--secondary al-btn--sm" type="button" data-plan="1">${wkIcon("calendar", 16)}Plan my week</button>`}</div>`);
    renderHealthLines(); return;
  }
  const at = items.findIndex(i => i.ts > nowS && i.state !== "live" && i.state !== "now");
  const nowRow = {now: true, time: clockT(nowS)};
  at < 0 ? items.push(nowRow) : items.splice(at, 0, nowRow);
  const rows = items.map(i => {
    if (i.now) return `<li class="tl-row tl-now"><span class="tl-time">${i.time}</span><span class="tl-line" role="separator" aria-label="Now, ${i.time}"></span></li>`;
    const k = esc(i.key || ""), st = i.state;
    let end = "";
    if (i.verdict) end = `<span class="tl-v tl-v--${i.verdict}" role="img" aria-label="Verdict: ${WK_VERDICT[i.verdict].toLowerCase()}">${wkGlyph(i.verdict, 14)}</span>`;
    else if (st === "live") end = `<span class="tl-live">Live</span>`;
    else if (st === "planned" || st === "now" || st === "missed") {
      end = (st === "missed" ? `<span class="tl-word">Missed</span>` : `<button type="button" class="al-btn al-btn--quiet al-btn--sm" data-pa="move" data-key="${k}" data-at="${esc(i.at)}">Move</button><button type="button" class="al-btn al-btn--quiet al-btn--sm" data-pa="skip" data-key="${k}">Skip</button>`)
        + (i.auto ? "" : `<button type="button" class="al-iconbtn al-iconbtn--sm tl-play" data-pa="start" data-key="${k}" aria-label="Start ${esc(i.title)} now">${wkIcon("play", 16)}</button>`);
    } else if (st === "skipped") end = `<span class="tl-word">Skipped</span><button type="button" class="al-btn al-btn--quiet al-btn--sm" data-pa="unskip" data-key="${k}">Undo</button>`;
    else if (st === "waiting") end = `<span class="tl-word">Checking</span>`;
    const body = `<span class="tl-ic">${wkIcon(i.icon, 20)}</span><span class="tl-txt"><span class="tl-title">${esc(i.title)}</span><span class="tl-meta">${esc(i.meta)}</span></span><span class="tl-end">${end}</span>`;
    const cls = `tl-blk st-${esc(st)}`;
    return `<li class="tl-row"><span class="tl-time">${esc(i.time)}</span>${i.sid && i.verdict
      ? `<button type="button" class="${cls}" data-pa="see" data-sid="${i.sid}" aria-label="${esc(i.title)}, ${esc(i.meta)}. See the session">${body}</button>`
      : `<div class="${cls}" id="blk-${k}">${body}</div>`}</li>`;
  });
  wkPaint(box, `<ol class="tl" aria-label="Today's timeline">${rows.join("")}</ol>`);
  renderHealthLines();
}
function renderHealthLines() {
  const el = $("#hlines"); if (!el) return;
  const hs = lastReport?.health || [];
  wkPaint(el, hs.map(x => `<span class="hline${x.today_met ? " met" : ""}" title="${esc(x.text || "")}">${wkIcon(habitIcon(x.habit, "health"), 16)}<b>${esc(x.label || x.habit)}</b><span>${esc(x.today_text || (x.status === "no_data" ? "Waiting for your iPhone" : "No data yet"))}</span>${x.today_met ? `<span class="tl-v tl-v--done" role="img" aria-label="Met">${wkGlyph("done", 12)}</span>` : ""}</span>`).join(""));
}
$("#todayBlock")?.addEventListener("click", async e => {
  if (e.target.closest("[data-plan]") || e.target.closest("#planWeek")) return typeof openHabits === "function" ? openHabits() : openSetup("Habits");
  if (e.target.closest("[data-brief-more]")) { const c = $("#agent"); c?.classList.toggle("is-full"); e.target.closest("[data-brief-more]").textContent = c?.classList.contains("is-full") ? "Show less" : "Read all of it"; return; }
  const b = e.target.closest("[data-pa]"); if (!b) return;
  const key = b.dataset.key, act = b.dataset.pa;
  if (act === "see") return gotoSession(+b.dataset.sid);
  if (act === "move") {
    const end = b.closest(".tl-end");
    end.innerHTML = `<span class="movebox"><input class="fld" type="time" value="${esc(b.dataset.at)}" aria-label="New time"><button type="button" class="al-btn al-btn--secondary al-btn--sm" data-pa="moveok" data-key="${esc(key)}">Move</button><button type="button" class="al-btn al-btn--quiet al-btn--sm" data-pa="cancel">Cancel</button></span>`;
    end.querySelector("input").focus(); return;
  }
  if (act === "cancel") { $("#blocks").dataset.wkSig = ""; return renderPlan(); }
  b.disabled = true;
  try {
    let j;
    if (act === "start") { j = await postJSON("/api/calendar/plan/start", {key}); if (j.reply && $("#convo")) { $("#convo").innerHTML = `<div class="line alibi"><span class="who">Alibi</span><span class="txt">${esc(j.reply)}</span></div>`; } pollState(); }
    else if (act === "skip") j = await postJSON("/api/calendar/plan/skip", {key});
    else if (act === "unskip") j = await postJSON("/api/calendar/plan/unskip", {key});
    else if (act === "moveok") j = await postJSON("/api/calendar/plan/move", {key, at: b.closest(".movebox").querySelector("input").value});
    if (j && j.reply && act !== "start") showToast("note", j.reply);
  } catch (err) { showToast("note", `That didn't work: ${err.message}`); }
  loadPlan();
});

/* ---------- this week: habit × day dots, claimed vs seen bars, report line ---------- */
async function loadWeekPlan() {
  if (!lastReport?.week_start) return;
  try { weekPlan = (await api(`/api/calendar/plan?days=7&date=${localDate(new Date(lastReport.week_start * 1000))}`)).blocks || []; } catch { weekPlan = []; }
  renderGrid();
}
// One mark per habit-day, shape-coded: ● done · ◐ partly · ✕ slacked · ○ missed · dashed ring not yet · dash rest.
const CELL_WORD = {done: "done", partial: "partly", slacked: "slacked", missed: "missed", notyet: "not yet", planned: "planned", rest: "rest day", live: "live now", none: ""};
function wkCell(c) {
  if (c === "done") return `<i class="wc wc-done"></i>`;
  if (c === "partial") return `<i class="wc wc-partial"></i>`;
  if (c === "slacked") return `<i class="wc wc-slacked">${wkGlyph("slacked", 12)}</i>`;
  if (c === "missed") return `<i class="wc wc-missed"></i>`;
  if (c === "notyet" || c === "planned") return `<i class="wc wc-notyet"></i>`;
  if (c === "live") return `<i class="wc wc-live"></i>`;
  if (c === "rest") return `<i class="wc wc-rest"></i>`;
  return "";
}
let wkAvatar = null;
function renderGrid() {
  const r = lastReport, box = $("#wgrid"); if (!box || !r || !r.week_start) return;
  const ws = new Date(r.week_start * 1000), today = localDate();
  const days = Array.from({length: 7}, (_, i) => { const d = new Date(ws); d.setDate(ws.getDate() + i); return d; });
  const dates = days.map(d => localDate(d));
  const ti = dates.indexOf(today);
  const rank = {done: 3, partial: 2, slacked: 1};
  const liveId = lastState?.session?.id;
  const rows = [];
  const keys = [...new Set([...Object.keys(habView).filter(k => !["strava", "health"].includes(habView[k].check)), ...(r.rows || []).map(x => x.habit)])];
  keys.forEach(k => {
    const v = habView[k] || {}, rr = (r.rows || []).find(x => x.habit === k) || {};
    const cells = dates.map(ds => {
      if (createdDay(k) && ds < createdDay(k)) return "none";
      if (liveId && lastState.session.habit === k && ds === today) return "live";
      let best = null;
      sessById.forEach(s => { if (s.habit === k && dayKey(s) === ds && s.verdict && (!best || rank[s.verdict] > rank[best.verdict])) best = s; });
      if (best) return best.verdict;
      const pb = weekPlan.find(b => b.habit === k && b.date === ds && !beforeCreated(b));
      if (pb && pb.state === "missed") return "missed";
      if (pb && ["planned", "now", "waiting"].includes(pb.state)) return "planned";
      return ds >= today ? "notyet" : "rest";
    });
    rows.push({name: dispName(k, v.label || rr.label), icon: habitIcon(k, rr.modality || CHECK_TO_MOD[v.check] || v.check), cells});
  });
  const run = r.running;
  if (run) {
    const ck = run.habit || "running";
    const cells = dates.map(ds => {
      const rs = (run.runs || []).filter(x => localDate(new Date(x.start_date * 1000)) === ds);
      if (!rs.length) return createdDay(ck) && ds < createdDay(ck) ? "none" : ds >= today ? "notyet" : "rest";
      return Math.max(...rs.map(x => x.distance_km || 0)) >= run.min_km ? "done" : "partial";
    });
    rows.push({name: dispName(ck, run.label), icon: "run", cells});
  }
  (r.health || []).forEach(x => {
    const byDate = Object.fromEntries((x.days || []).map(d => [d.date, d]));
    const cells = dates.map(ds => { const d = byDate[ds]; if (!d || d.met == null) return ds >= today ? "notyet" : "rest"; return d.met ? "done" : "slacked"; });
    rows.push({name: x.label || hname(x.habit), icon: habitIcon(x.habit, "health"), cells});
  });
  if (!rows.length) { wkPaint(box, ""); return; }
  const full = d => d.toLocaleDateString("en-GB", {weekday: "long", day: "numeric"});
  const short = d => d.toLocaleDateString("en-GB", {weekday: "narrow"});
  const head = `<div class="wg-r wg-head" role="row"><span role="columnheader" class="wg-hab">Habit</span>${days.map((d, i) => `<span role="columnheader" class="wg-day${i === ti ? " is-today" : ""}" aria-label="${esc(full(d))}${i === ti ? ", today" : ""}">${short(d)}</span>`).join("")}</div>`;
  const body = rows.map(x => `<div class="wg-r" role="row"><span role="rowheader" class="wg-hab"><span class="wg-ic">${wkIcon(x.icon, 16)}</span><span class="wg-name">${esc(x.name)}</span></span>${x.cells.map((c, i) => `<span role="cell" class="wg-cell${i === ti ? " is-today" : ""}" aria-label="${esc(full(days[i]))}: ${CELL_WORD[c] || "nothing"}" title="${esc(x.name)} · ${esc(full(days[i]))}: ${CELL_WORD[c] || "nothing"}" style="--i:${i}">${wkCell(c)}</span>`).join("")}</div>`).join("");
  const legend = `<div class="wg-key"><span>${wkCell("done")}Done</span><span>${wkCell("partial")}Partly</span><span>${wkCell("slacked")}Slacked</span><span>${wkCell("rest")}Rest</span><span>${wkCell("notyet")}Not yet</span></div>`;
  // Claimed vs seen per day, from the finished sessions of this week.
  const cl = dates.map(() => 0), se = dates.map(() => 0);
  sessById.forEach(s => { const i = dates.indexOf(dayKey(s)); if (i >= 0 && s.verdict) { cl[i] += s.declared_min || 0; se[i] += s.verified_min || 0; } });
  const max = Math.max(1, ...cl, ...se), H = 88;
  const bars = dates.map((_, i) => `<div class="wb-col" style="--i:${i}"><span class="wb-top" style="--i:${i}">${cl[i] ? se[i] : ""}</span><span class="wb-pair"><span class="wb-c" style="height:${Math.round(cl[i] / max * H)}px"></span><span class="wb-s" style="height:${Math.round(se[i] / max * H)}px"></span></span></div>`).join("");
  const T = r.totals || {}, peak = cl.indexOf(Math.max(...cl));
  const summary = `Claimed ${wkHM(T.declared_min)}, seen ${wkHM(T.verified_min)} this week.${cl[peak] ? ` ${full(days[peak]).split(" ")[0]} had the most: ${cl[peak]} claimed, ${se[peak]} seen.` : ""}`;
  const fresh = !(T.declared_min || T.verified_min);
  const {pull, more} = reportLine(r);
  const line = fresh ? "Nothing logged yet this week. Your first session starts the story." : pull || "Nothing to report yet this week.";
  const html = `<div class="wk-card">
    <div class="wk-top">
      <div class="wg" role="table" aria-label="Habits by day this week">${head}${body}${legend}</div>
      <figure class="wb" aria-label="${esc(summary)}">
        <div class="wb-cap"><figcaption>Claimed and seen, minutes</figcaption><span class="wb-key"><span><i class="k-claimed"></i>Claimed</span><span><i class="k-seen"></i>Seen</span></span></div>
        <div class="wb-plot" aria-hidden="true">${bars}</div>
        <div class="wb-days" aria-hidden="true">${days.map((d, i) => `<span class="${i === ti ? "is-today" : ""}">${short(d)}</span>`).join("")}</div>
      </figure>
    </div>
    <div class="wk-report">
      <div class="wk-line"><span class="wk-avatar" aria-hidden="true"></span><p class="t-voice">${esc(line)}</p></div>
      ${!fresh && more ? `<button type="button" class="al-btn al-btn--quiet al-btn--sm wk-more" aria-expanded="${wkFullOpen}" aria-controls="wkFull">${wkFullOpen ? "Hide the full report" : "Read the full report"}</button>
      <ul class="wk-full" id="wkFull"${wkFullOpen ? "" : " hidden"}>${wkSentences(wkVoice(r.summary)).map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    </div>
  </div>`;
  if (wkPaint(box, html)) {
    // Pinch beside the report line: one still 20px avatar, mounted once and carried across refreshes.
    const slot = box.querySelector(".wk-avatar");
    if (slot) {
      if (!wkAvatar) {
        wkAvatar = document.createElement("span"); wkAvatar.className = "wk-pinch";
        try { if (window.AlibiPinch?.mount) window.AlibiPinch.mount(wkAvatar, {size: 20, mood: "reading", still: true}); } catch {}
      }
      slot.append(wkAvatar);
    }
  }
}
$("#wgrid")?.addEventListener("click", e => {
  const b = e.target.closest(".wk-more"); if (!b) return;
  wkFullOpen = !wkFullOpen;
  const f = $("#wkFull"); if (f) f.hidden = !wkFullOpen;
  b.setAttribute("aria-expanded", wkFullOpen); b.textContent = wkFullOpen ? "Hide the full report" : "Read the full report";
});
$("#readRep")?.addEventListener("click", e => {
  const f = $("#fullRep"); if (!f) return; const open = f.hidden; f.hidden = !open;
  e.target.setAttribute("aria-expanded", open); e.target.textContent = open ? "Hide the full report" : "Read the full report";
});

/* ---------- Pinch's line on Today, what's left, and the agent's brief ---------- */
// One source per fact: the line is pinch.line, else phrase.text; what's left is plan_today; the brief is
// GET /api/briefs. Each part hides itself when an older daemon doesn't send its field.
let lastPlanToday = null, planSig = null, briefsOK = null, lastBrief = null, briefsReq = 0, wkUpSince = null;
const wkPretty = m => /nemotron-3-super/i.test(m || "") ? "Nemotron 3 Super" : /nemotron-3-nano/i.test(m || "") ? "Nemotron 3 Nano" : /nemotron/i.test(m || "") ? "Nemotron" : "";
function todaySlots() {
  const blk = $("#todayBlock"), head = blk && blk.querySelector(".sechead"); if (!head) return {};
  let line = $("#todayLine"), card = $("#agent");
  if (!line) { line = document.createElement("div"); line.id = "todayLine"; line.className = "today-line"; line.hidden = true; head.after(line); }
  if (!card) { card = document.createElement("article"); card.id = "agent"; card.className = "al-card agentcard"; card.hidden = true; card.setAttribute("aria-labelledby", "agentH"); line.after(card); }
  let night = $("#night");
  if (!night) { night = document.createElement("article"); night.id = "night"; night.className = "al-card nightcard"; night.hidden = true; night.setAttribute("aria-labelledby", "nightH"); card.before(night); }
  return {line, card, night};
}
function renderTodayExtras(s) {
  const {line} = todaySlots(); if (!line) return;
  // Pinch's line: hidden on an old daemon (no phrase), so the island and the web never disagree about who said what.
  const ph = s && s.phrase, p = (s && s.pinch) || {};
  const text = dispText(p.line || (ph && ph.text) || "");
  const agent = !p.line && ph && ph.source === "agent";
  const mood = agent ? "reading" : (p.mood || "idle");
  const sig = ph ? `${text}|${agent ? ph.ts : ""}|${mood}` : "";
  if (line.dataset.sig !== sig) {
    const first = !line.dataset.sig;
    line.dataset.sig = sig;
    line.hidden = !ph || !text;
    if (ph && text) {
      line.innerHTML = `<div class="al-pinchline is-compact"><span class="al-pinchline__avatar">${window.AlibiPinchWire ? AlibiPinchWire.avatar(mood, 20) : ""}</span>
        <p class="al-pinchline__text">${esc(text)}${agent ? ` <span class="today-src">Your agent · ${esc(clockT(ph.ts))}</span>` : ""}</p></div>`;
      if (!first && !wkReduced()) line.firstElementChild.animate([{opacity: 0, transform: "translateY(4px)"}, {opacity: 1, transform: "none"}], {duration: 260, easing: getComputedStyle(document.documentElement).getPropertyValue("--ease-out").trim() || "ease-out"});
    }
  }
  // What's left today (plan_today), and a re-render of the timeline whenever the plan's shape changes.
  if (s && "plan_today" in s) {
    const pt = s.plan_today;
    lastPlanToday = pt || null;
    const ps = pt ? JSON.stringify([(pt.left || []).map(i => i.key + ":" + i.status), (pt.done || []).map(i => i.key)]) : "";
    if (planSig !== null && ps !== planSig) loadPlan();
    planSig = ps;
    renderPlanSummary(pt);
  }
  renderTodayMeta();
  // The agent card: only once the daemon is new enough to have /api/briefs (it sends `agent` with every state).
  // A restarted daemon (new daemon.up_since) asks again at once, so a tab left open across a restart keeps up.
  const up = s && s.daemon && s.daemon.up_since;
  if (up && wkUpSince && up !== wkUpSince) { briefsOK = null; if (!("agent" in s)) renderBrief(null); }
  if (up) wkUpSince = up;
  if (typeof STAGE !== "undefined" && STAGE) renderNight(nightAccepted && s._night_accepted ? s._night_accepted : s._night || null);
  else if (nightRow) renderNight(nightRow);
  if (s && s._briefs) { briefsOK = true; renderBrief((s._briefs || [])[0] || null); }
  else if (s && "agent" in s && briefsOK === null) { briefsOK = true; loadBriefs(); }
}
function renderPlanSummary(pt) {
  const nx = $("#nextUp"); if (!nx) return;
  // "N of M kept" is already the Today meta, so the line keeps only what's left.
  const t = pt && pt.scheduled && pt.total > 0 ? (pt.summary || "").replace(/\s*\d+ of \d+ kept\.$/, "") : "";
  const html = t ? esc(t).replace(/^(\d+ left)/, "<b>$1</b>").replace(/^(Nothing left today\.)/, "<b>$1</b>") : "";
  if (nx.dataset.html !== html) { nx.dataset.html = html; nx.innerHTML = html; }
}
window.AlibiToday = {plan(pt) { if (!pt) return; lastPlanToday = pt; renderPlanSummary(pt); renderTodayMeta(); loadPlan(); }};
async function loadBriefs() {
  if (!briefsOK) return;
  if (typeof STAGE !== "undefined" && STAGE) { renderBrief((lastState && lastState._briefs || [])[0] || null); return; }
  const my = ++briefsReq;
  let j;
  try { j = await api("/api/briefs?limit=1"); }
  catch (e) {
    // Only a 404 means this daemon has no briefs (an old one): hide the card until it restarts. A dropped connection or
    // a 5xx (a daemon restart) keeps the card as it is, and the next refreshSlow asks again.
    if (my === briefsReq && String(e && e.message) === "404") { briefsOK = false; renderBrief(null); }
    return;
  }
  if (my === briefsReq) renderBrief((j.briefs || [])[0] || null);   // an older, slower answer never wins
}
function renderBrief(b) {
  const {card} = todaySlots(); if (!card) return;
  const now = wkNow(), fresh = b && b.text && (b.age_s != null ? b.age_s : now - (b.ts || 0)) < 12 * 3600;
  const cardOK = fresh && window.AlibiCard && AlibiCard.ok(b.card);
  const sig = fresh ? `${b.ts}|${b.text}|${cardOK ? JSON.stringify(b.card) : ""}` : "";
  if (card.dataset.sig === sig) return;
  const first = !card.dataset.sig;
  card.dataset.sig = sig; lastBrief = fresh ? b : null;
  card.hidden = !fresh;
  if (!fresh) { card.innerHTML = ""; return; }
  const host = (lastState && lastState.agent && lastState.agent.host) || "";
  // With a card, its provenance says who and where ("Your agent · DGX Spark · Nemotron 3 Super"), so the meta is the time.
  const meta = cardOK ? clockT(b.ts) : [clockT(b.ts), host, wkPretty(b.model)].filter(Boolean).join(" · ");
  const text = dispText(b.text || "");
  const shown = cardOK ? (b.card.title || "").length + (typeof b.card.subtitle === "string" ? b.card.subtitle.length : 0) + 2 : 0;
  const long = cardOK ? text.length > shown : text.length > 280;
  const head = `<div class="ag-head"><span class="ag-av" aria-hidden="true">${window.AlibiPinchWire ? AlibiPinchWire.avatar("reading", 20) : ""}</span>
      <h3 class="ag-title" id="agentH">From your agent</h3><span class="ag-meta">${esc(meta)}</span></div>`;
  const more = long ? `<button type="button" class="al-btn al-btn--quiet al-btn--sm ag-more" data-brief-more="1">Read all of it</button>` : "";
  card.classList.remove("is-full");
  card.innerHTML = cardOK ? `${head}${AlibiCard.html(b.card, {actions: false})}${long ? `<div class="ag-full"><p class="ag-text">${esc(text)}</p></div>` : ""}${more}`
    : `${head}<p class="ag-text">${esc(text)}</p>${more}`;
  card.classList.toggle("is-long", long && !cardOK);
  if (cardOK && !first) AlibiCard.enter(card);
  if (!first && !wkReduced()) card.animate([{opacity: 0, transform: "translateY(6px)"}, {opacity: 1, transform: "none"}], {duration: 260, easing: "ease-out"});
}

/* ---------- the Night review on Today, from GET /api/digests/latest?kind=night (row.card) ---------- */
// Shown for 14 h from the row's ts (a 22:00 review stays until noon). Accept posts card.actions[0].post and re-reads the
// row, whose card then reads "On the plan: ..."; Not now hides this slot (remembered per slot). Stage: lastState._night.
// Stage keeps Accept and Not now in memory and never posts: the fixtures carry a real night's slot and share the live
// dashboard's origin, so a rehearsal click must not hide the live card or accept the real proposal. A reload resets it.
let nightRow = null, nightReq = 0, nightAccepted = false, nightHiddenStage = "";
const nightStage = () => typeof STAGE !== "undefined" && !!STAGE;
const nightHidden = () => { if (nightStage()) return nightHiddenStage; try { return localStorage.getItem("alibi.nightHidden") || ""; } catch { return ""; } };
function stageNightAccept() { nightAccepted = true; renderNight(lastState && (lastState._night_accepted || lastState._night) || null); }
async function loadNight() {
  if (typeof STAGE !== "undefined" && STAGE) return renderNight(lastState && lastState._night || null);
  const my = ++nightReq;
  let row;
  try { row = await api("/api/digests/latest?kind=night"); } catch { return; }   // an old daemon or a restart: keep what's shown
  if (my !== nightReq) return;
  nightRow = row || null;
  renderNight(nightRow);
}
function renderNight(row) {
  const {night} = todaySlots(); if (!night) return;
  const show = !!(row && row.card && window.AlibiCard && AlibiCard.ok(row.card) && row.slot !== nightHidden()
    && wkNow() - (row.ts || 0) < 14 * 3600 && wkNow() - (row.ts || 0) > -600);
  const sig = show ? JSON.stringify([row.slot, row.ts, row.card]) : "";
  if (night.dataset.sig === sig) return;
  const first = !night.dataset.sig;
  night.dataset.sig = sig; night.dataset.slot = show ? row.slot || "" : "";
  night.hidden = !show;
  if (!show) { night.innerHTML = ""; return; }
  night.innerHTML = `<div class="ag-head"><span class="nc-ic" aria-hidden="true">${wkIcon("moon", 12)}</span>
      <h3 class="ag-title" id="nightH">Night review</h3><span class="ag-meta">${esc(clockT(row.ts))}</span></div>${AlibiCard.html(row.card)}`;
  AlibiCard.bind(night, nightAction);
  if (first || !wkReduced()) AlibiCard.enter(night);
}
async function nightAction(x, btn) {
  const slot = $("#night")?.dataset.slot || "";
  if (x.post) {
    if (nightStage()) return stageNightAccept();
    btn.disabled = true;
    try { const j = await postJSON(x.post, x.body || {}); if (j && j.reply) showToast("note", j.reply); }
    catch { btn.disabled = false; return showToast("note", "That didn't save. Check Alibi is running, then try again."); }
    if ($("#toast")?.classList.contains("has-card") && /report|digest/.test($("#toast").className)) hideToast();   // the toast asked the same question
    await loadNight(); loadPlan(); return;
  }
  if (x.say && typeof say === "function") return say(x.say);
  if (x.url) { if (/^\/?#/.test(x.url)) { location.hash = x.url.replace(/^\//, ""); return route(); } return window.open(x.url, "_blank", "noopener"); }
  if (x.dismiss) {
    if (nightStage()) nightHiddenStage = slot;
    else try { localStorage.setItem("alibi.nightHidden", slot); } catch {}
    renderNight(null);
  }
}
document.addEventListener("alibi:report", () => { if (!(typeof STAGE !== "undefined" && STAGE)) loadNight(); });
