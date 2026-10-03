/* focus.js: the Focus section after Today. Phone pickups by hour over the day's plan, the week, each habit, the Mac and
   what to change, for Today, Yesterday or the Week. Every number is computed by code (alibi/focus.py) and arrives from
   GET /api/focus/day?date=today|yesterday and /api/focus/week; this file lays them out and adds up nothing but the week's
   average. The day's planned blocks come from day.blocks when the API sends them, else GET /api/calendar/plan.
   Stage (?stage=NAME): lastState._focus {today, yesterday, week}; a fixture without it hides the section, like the
   night card. An old daemon (404) keeps it hidden and is asked again each minute. ?focus=yesterday|week picks the tab;
   #focus/yesterday also scrolls to it.
   Classic script after week.js (wkIcon, wkGlyph, wkDot, wkHM, wkReduced, wkNow, habitIcon) and before boot.js. */

const FX_TABS = ["today", "yesterday", "week"];
// Block states, same words as routes_calendar TEXT, so the timeline, the island and this section agree.
const FX_STATE = {planned: "Planned", now: "Now", live: "In progress", done: "Done", partial: "Partly done", slacked: "Didn't count",
  missed: "Didn't happen", skipped: "Skipped", waiting: "Checking", nodata: "No data"};
const FX_SRC = {phone: ["phone", "Mostly lost to the phone"], mac: ["laptop", "Mostly lost to the Mac"], away: ["cup", "Mostly away from the desk"]};
const FX_HOT = 6, FX_HOT_N = 3;     // focus.py says "phone away" from 6 pickups an hour, and only on 3 or more
let fxTab = "today", fxCache = {}, fxReq = {}, fxPainted = "", fxWantPlay = false, fxHeld = false, fxSeen = false, fxPlayT = 0, fxFont = "";
let fxCtx = null, fxRO = null, fxW = 0, fxGo = false;

const fxNum = v => typeof v === "number" && isFinite(v);
const fxInt = v => fxNum(v) ? Math.round(v).toLocaleString("en-GB") : "—";
const fxRate = v => fxNum(v) ? String(Math.round(v * 10) / 10) : "—";          // 12, 9.6: the backend's own precision
const fxS = n => n === 1 ? "" : "s";
const fxF = v => (Math.round(v * 10) / 10).toString();
const fxStage = () => typeof STAGE !== "undefined" && !!STAGE;
const fxToday = () => localDate(new Date(wkNow() * 1000));
const fxDate = iso => { const m = /^(\d{4})-(\d\d)-(\d\d)$/.exec(iso || ""); return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null; };
const fxDay = (iso, o) => { const d = fxDate(iso); return d ? d.toLocaleDateString("en-GB", o) : ""; };
const fxStateOf = s => FX_STATE[s] ? s : "planned";

/* ---------- data ---------- */
// Stage reads the fixture; live asks the API. A day without blocks gets them from the plan for its date.
async function fxGet(tab) {
  if (fxStage()) {
    const f = typeof lastState !== "undefined" && lastState && lastState._focus;
    const v = f && typeof f === "object" ? f[tab] : null;
    if (!v || typeof v !== "object") return null;
    return tab === "week" ? {week: v} : {day: v, blocks: Array.isArray(v.blocks) ? v.blocks : []};
  }
  if (tab === "week") return {week: await api("/api/focus/week")};
  const day = await api(`/api/focus/day?date=${tab}`);
  let blocks = Array.isArray(day && day.blocks) ? day.blocks : null;
  if (!blocks && day && fxDate(day.date)) {
    try { blocks = (await api(`/api/calendar/plan?days=1&date=${day.date}`)).blocks || []; } catch { blocks = []; }
  }
  return {day, blocks: blocks || []};
}
async function fxLoad(tab, force) {
  const c = fxCache[tab], age = c ? Date.now() - c.at : Infinity;
  if (!force && age < (tab === "today" ? 55e3 : 5 * 60e3)) return;
  const my = fxReq[tab] = (fxReq[tab] || 0) + 1;
  let got;
  try { got = await fxGet(tab); }
  catch (e) { if (my === fxReq[tab] && String(e && e.message) === "404") fxHide(); return; }   // old daemon: no Focus yet
  if (my !== fxReq[tab]) return;                                                                // an older answer never wins
  if (!got) { if (fxStage()) fxHide(); return; }
  fxCache[tab] = {...got, at: Date.now()};
  if (tab === fxTab) fxPaint();
}
function fxHide() { const s = $("#focusBlock"); if (s) s.hidden = true; fxPainted = ""; }

/* ---------- paint ---------- */
function fxPaint() {
  const sec = $("#focusBlock"), box = $("#focusPanel"); if (!sec || !box) return;
  const c = fxCache[fxTab];
  if (!c) { box.classList.add("is-busy"); return; }           // refetch keeps the frame, dimmed
  box.classList.remove("is-busy");
  const html = fxTab === "week" ? fxWeekHTML(c.week) : fxDayHTML(c.day, c.blocks);
  const first = sec.hidden, sig = fxTab + "|" + html, swap = fxWantPlay && !first;
  sec.hidden = false;
  if (sig !== fxPainted) { fxPainted = sig; box.innerHTML = html; }
  fxCharts();
  if (first || fxWantPlay) { fxWantPlay = false; fxEnter(box, swap); }
  fxScroll();
}

// The headline: one number, one comparison with the week.
function fxDelta(p) {
  if (!fxNum(p)) return "";
  const cls = p >= 30 ? " fx-delta--warn" : p < 0 ? " fx-delta--good" : "";
  const t = p === 0 ? "Same as your week" : `${Math.abs(p)}% ${p > 0 ? "above" : "below"} your week`;
  return `<span class="fx-delta${cls}">${esc(t)}</span>`;
}
function fxHero(n, unit) {
  return `<p class="fx-hero"><span class="fx-num" data-count="${Math.round(n)}" aria-hidden="true">${fxInt(n)}</span><span class="fx-unit" aria-hidden="true">${esc(unit)}</span><span class="al-sr">${fxInt(n)} ${esc(unit)}</span></p>`;
}

function fxDayHTML(d, blocks) {
  if (!d || typeof d !== "object") return `<p class="fx-empty">No numbers for this day yet.</p>`;
  const phone = d.phone === true && fxNum(d.pickups), today = d.date === fxToday() || d.name === "Today";
  const avg = fxNum(d.avg_7d) ? Math.round(d.avg_7d) : null, plan = (blocks || []).filter(b => b && fxSpan(b));
  const top = phone ? `<div class="fx-top">${fxHero(d.pickups, `phone pickup${fxS(d.pickups)}${today ? " so far" : ""}`)}${fxDelta(d.vs_avg_pct)}</div>`
    : `<div class="fx-top"><p class="fx-none">No phone data for this day.</p></div>`;
  // A running day's average is like for like (the other days up to the same time), so it isn't "a day" yet.
  const sub = [fxDay(d.date, {weekday: "long", day: "numeric", month: "long"}),
    phone ? (avg != null ? `Your week averages ${avg} ${today ? "by this time of day" : "a day"}` : "No week to compare with yet") : ""].filter(Boolean).join(". ");
  const chart = phone || plan.length ? `<figure class="fx-fig"><figcaption class="al-sr">${esc(d.line || "")}</figcaption>
      <div class="fx-chart" data-chart="day" tabindex="0" role="img" aria-label="${esc(`${phone ? d.line || "" : "No phone data for this day."} Arrow keys read each hour.`)}"></div>
      <div class="fx-tip" aria-hidden="true"></div>
      <div class="fx-key" aria-hidden="true">${phone ? `<span><i class="fx-k"></i>Pickups an hour</span><span><i class="fx-k fx-k--peak"></i>Peak hour</span>` : ""}${fxPlanKey(plan)}</div>
      ${fxDayTable(d, plan, phone)}<p class="al-sr" aria-live="polite" data-fx-live></p></figure>` : "";
  const ib = d.in_blocks && typeof d.in_blocks === "object" ? d.in_blocks : {};
  const stats = [];
  if (phone && d.peak && fxNum(d.peak.hour)) stats.push(["Peak hour", `${pad(d.peak.hour)}:00<small>${fxInt(d.peak.pickups)} pickup${fxS(d.peak.pickups)}</small>`]);
  if (fxNum(ib.blocks) && ib.blocks > 0) stats.push(["During your plans", phone && fxNum(ib.pickups)
    ? `${fxInt(ib.pickups)}<small>in ${ib.blocks} block${fxS(ib.blocks)}${fxNum(ib.minutes) && ib.minutes > 0 ? `, ${esc(wkHM(ib.minutes))}` : ""}</small>`
    : `—<small>${ib.blocks} block${fxS(ib.blocks)}</small>`]);
  else stats.push(["During your plans", `—<small>nothing planned</small>`]);
  if (fxNum(d.screen_time_picked_min)) stats.push(["Screen Time", esc(wkHM(d.screen_time_picked_min))]);
  const head = `<article class="al-card fx-card" style="--c:0">${top}${sub ? `<p class="fx-sub">${esc(sub)}.</p>` : ""}${chart}
    <div class="fx-stats">${stats.map(([l, v]) => `<div class="fx-stat"><span class="fx-stat__l">${l}</span><span class="fx-stat__v">${v}</span></div>`).join("")}</div></article>`;
  const hab = fxHabitsDay(d, plan, phone, 2), mac = fxMacHTML(d.mac, 3);
  return head + fxRecsHTML(d.recommendations, today ? "Nothing to change from today's numbers." : "Nothing to change from this day's numbers.", 1)
    + (mac ? `<div class="fx-two">${hab}${mac}</div>` : hab) + fxProv();
}

// The chart's table twin for screen readers, in a clipped div (a table can't shrink below its content).
function fxDayTable(d, plan, phone) {
  const hrs = phone && Array.isArray(d.pickups_by_hour) ? d.pickups_by_hour : null;
  if (!hrs) return "";
  const rows = hrs.map((v, h) => {
    const over = plan.filter(b => { const s = fxSpan(b); return s[0] < h + 1 && s[1] > h; }).map(b => `${b.label || hname(b.habit)} ${b.at || ""}`.trim());
    return `<tr><th scope="row">${pad(h)}:00</th><td>${fxInt(v)}</td><td>${esc(over.join(", ") || "—")}</td></tr>`;
  }).join("");
  return `<div class="al-sr"><table><caption>Phone pickups by hour</caption><thead><tr><th scope="col">Hour</th><th scope="col">Pickups</th><th scope="col">Planned</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

// "20-minute" never breaks at its hyphen.
const fxCopy = t => dispText(t.trim()).replace(/(\d)-(?=[a-z])/g, "$1\u2011");
function fxRecsHTML(recs, empty, c) {
  const list = (Array.isArray(recs) ? recs : []).filter(r => r && typeof r.text === "string" && r.text.trim()).slice(0, 3);
  const body = list.length ? `<ol class="fx-recs">${list.map((r, i) => `<li class="fx-rec" style="--i:${i}"><span class="fx-rec__n" aria-hidden="true">${i + 1}</span><div>
      <p class="fx-rec__t">${esc(fxCopy(r.text))}</p>${typeof r.why === "string" && r.why.trim() ? `<p class="fx-rec__w">${esc(fxCopy(r.why))}</p>` : ""}</div></li>`).join("")}</ol>`
    : `<p class="fx-empty">${esc(empty)}</p>`;
  return `<article class="al-card fx-card" style="--c:${c}" aria-labelledby="fxRecsH"><h3 class="fx-h" id="fxRecsH">What to change</h3>${body}</article>`;
}

// One mark and word per state: ✓ Done, ◐ Partly done, ✕ Didn't count, ○ Didn't happen; the rest are words alone.
function fxStateHTML(s) {
  const st = fxStateOf(s), g = ["done", "partial", "slacked"].includes(st) ? wkGlyph(st, 12)
    : st === "missed" ? `<svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="8" cy="8" r="5.25" fill="none" stroke="currentColor" stroke-width="1.75"/></svg>` : "";
  return `<span class="fx-state fx-state--${st}">${g}${esc(FX_STATE[st])}</span>`;
}

function fxHabitsDay(d, plan, phone, c) {
  const rows = (Array.isArray(d.by_habit) ? d.by_habit : []).filter(h => h && (h.label || h.habit));
  const body = rows.length ? `<div class="fx-rows">${rows.map(h => {
    const b = plan.find(x => x.habit === h.habit), mod = b ? CHECK_TO_MOD[b.check] || b.check : null;
    const meta = [b && b.at ? b.at : "", fxNum(h.planned_min) ? `${wkHM(h.planned_min)} planned` : ""].filter(Boolean).join(" · ");
    const rate = phone && fxNum(h.per_hour) ? h.per_hour : null, mac = fxNum(h.mac_distraction_min) && h.mac_distraction_min > 0 ? Math.round(h.mac_distraction_min) : 0;
    const macT = mac ? `<span class="fx-src" title="${mac} min on distracting sites and apps on the Mac during this block">${wkIcon("laptop", 12)}${mac} min<span class="al-sr"> on distracting sites and apps on the Mac</span></span>` : "";
    const nums = phone && fxNum(h.pickups)
      ? `<b>${rate != null && rate >= FX_HOT && h.pickups >= FX_HOT_N ? wkDot("phone", 8, {hidden: true}) : ""}${fxInt(h.pickups)} pickup${fxS(h.pickups)}</b><small>${rate != null ? `${fxRate(rate)} an hour` : ""}${mac ? `${rate != null ? " · " : ""}${macT}` : ""}</small>`
      : `<b>—</b><small>${mac ? macT : "no phone data"}</small>`;
    return `<div class="fx-row"><div class="fx-name"><span class="fx-ic">${wkIcon(habitIcon(h.habit, mod), 16)}</span><span><b>${esc(h.label || hname(h.habit))}</b>
      <small>${meta ? `<span>${esc(meta)}</span>` : ""}${fxStateHTML(h.state)}</small></span></div><div class="fx-nums">${nums}</div></div>`;
  }).join("")}</div>` : `<p class="fx-empty">Nothing was planned this day.</p>`;
  return `<article class="al-card fx-card" style="--c:${c}" aria-labelledby="fxHabH"><h3 class="fx-h" id="fxHabH">By habit<small>pickups inside each block</small></h3>${body}</article>`;
}

function fxMacHTML(m, c) {
  if (!m || typeof m !== "object") return "";
  const top = (Array.isArray(m.top) ? m.top : []).filter(t => t && typeof t.name === "string" && t.name.trim() && fxNum(t.min) && t.min > 0).slice(0, 3);
  const max = Math.max(1, ...top.map(t => t.min)), dm = fxNum(m.distraction_min) ? Math.max(0, Math.round(m.distraction_min)) : 0;
  const meta = [fxNum(m.notifications) ? `${fxInt(m.notifications)} notification${fxS(m.notifications)}` : "",
    fxNum(m.switches_per_min) ? `${fxRate(m.switches_per_min)} app switches a minute` : ""].filter(Boolean).join(" · ");
  const lead = dm > 0 ? `<p class="fx-macn"><b>${esc(dm < 60 ? String(dm) : wkHM(dm))}</b><span>${dm < 60 ? "min " : ""}on distracting sites and apps</span></p>`
    : `<p class="fx-empty">Nothing distracting on the Mac.</p>`;
  const list = top.length ? `<ul class="fx-tops">${top.map((t, i) => `<li class="fx-topr" style="--i:${i}"><span class="fx-topr__n">${esc(t.name.trim())}</span>
      <span class="fx-topr__t" aria-hidden="true"><i style="--f:${(t.min / max).toFixed(3)}"></i></span><span class="fx-topr__m">${Math.round(t.min)} min</span></li>`).join("")}</ul>` : "";
  return `<article class="al-card fx-card" style="--c:${c}" aria-labelledby="fxMacH"><h3 class="fx-h" id="fxMacH">On your Mac</h3>${lead}${list}${meta ? `<p class="fx-macmeta">${esc(meta)}</p>` : ""}</article>`;
}

function fxProv() {
  return `<p class="fx-prov">${wkIcon("eye", 16)}<span>Counted on this Mac from iPhone pickups and window titles. Your agent gets the numbers, never the titles.</span></p>`;
}

function fxWeekHTML(w) {
  const days = w && Array.isArray(w.days) ? w.days.filter(x => x && fxDate(x.date)).slice(-7) : [];
  if (!days.length) return `<p class="fx-empty">No week to show yet.</p>` + fxProv();
  const withP = days.filter(x => fxNum(x.pickups)), hi = withP.reduce((a, x) => !a || x.pickups > a.pickups ? x : a, null);
  // "a day": the backend's avg_day (full earlier days only); an older one: the days before today, never today so far
  const past = withP.filter(x => x.date !== fxToday());
  const avg = fxNum(w.avg_day) ? w.avg_day : past.length ? past.reduce((a, x) => a + x.pickups, 0) / past.length : null;
  const inPlans = withP.reduce((a, x) => a + (fxNum(x.in_blocks_pickups) ? x.in_blocks_pickups : 0), 0);
  const seen = days.reduce((a, x) => a + (fxNum(x.seen_min) ? x.seen_min : 0), 0);
  const tdy = withP.find(x => x.date === fxToday());                 // only today so far: say so, not "a day"
  const top = avg != null ? `<div class="fx-top">${fxHero(avg, "phone pickups a day")}</div>`
    : tdy ? `<div class="fx-top">${fxHero(tdy.pickups, `phone pickup${fxS(tdy.pickups)} so far today`)}</div>`
    : `<div class="fx-top"><p class="fx-none">No phone data this week.</p></div>`;
  const sub = [hi ? `${fxDay(hi.date, {weekday: "long"})} was highest with ${fxInt(hi.pickups)}` : "", withP.length ? `${fxInt(inPlans)} came during your plans` : "",
    `Seen by Alibi: ${wkHM(seen)}`].filter(Boolean).join(". ") + ".";
  const range = `${fxDay(days[0].date, {day: "numeric", month: "short"})} to ${fxDay(days[days.length - 1].date, {day: "numeric", month: "short"})}`;
  const chart = `<figure class="fx-fig"><figcaption class="al-sr">Phone pickups a day, ${esc(range)}.</figcaption>
      <div class="fx-chart" data-chart="week" tabindex="0" role="img" aria-label="${esc(`Phone pickups a day, ${range}: ${days.map(x => `${fxDay(x.date, {weekday: "long"})} ${fxNum(x.pickups) ? x.pickups : "no data"}`).join(", ")}. Arrow keys read each day.`)}"></div>
      <div class="fx-tip" aria-hidden="true"></div>
      <div class="fx-key" aria-hidden="true"><span><i class="fx-k fx-k--plan"></i>During your plans</span><span><i class="fx-k"></i>Other times</span></div>
      ${fxWeekTable(days)}<p class="al-sr" aria-live="polite" data-fx-live></p></figure>`;
  const s = w.struggle && typeof w.struggle === "object" && (w.struggle.label || w.struggle.habit) ? w.struggle : null;
  const struggle = s ? `<div class="fx-struggle" style="--c:1">${wkDot("phone", 10, {hidden: true})}<p><b>${esc(s.label || hname(s.habit))}</b> had it hardest${fxNum(s.per_hour) ? `: ${fxRate(s.per_hour)} pickups an hour during its blocks` : ""}.${fxReason(s.reason, fxNum(s.per_hour))}</p></div>` : "";
  return `<article class="al-card fx-card" style="--c:0">${top}<p class="fx-sub">${esc(sub)}</p>${chart}</article>` + struggle
    + fxRecsHTML(w.recommendations, "Nothing to change from this week's numbers.", 2) + fxHabitsWeek(w.by_habit, 3) + fxProv();
}
// struggle.reason: a source word (phone, mac, away) reads as a sentence; anything else is the backend's own sentence,
// shown only when the rate isn't (focus.py's is that rate again: "7 pickups an hour during Portfolio this week.").
function fxReason(r, rated) {
  if (typeof r !== "string" || !r.trim()) return "";
  const t = {phone: "", mac: "Mostly lost to the Mac.", away: "Mostly away from the desk."}[r.trim().toLowerCase()];
  return t === undefined ? (rated ? "" : `<small>${esc(dispText(r.trim()))}</small>`) : t ? `<small>${esc(t)}</small>` : "";
}

function fxWeekTable(days) {
  const rows = days.map(x => `<tr><th scope="row">${esc(fxDay(x.date, {weekday: "long", day: "numeric", month: "long"}))}</th><td>${fxInt(x.pickups)}</td><td>${fxInt(x.in_blocks_pickups)}</td><td>${fxNum(x.seen_min) ? esc(wkHM(x.seen_min)) : "—"}</td></tr>`).join("");
  return `<div class="al-sr"><table><caption>Phone pickups a day</caption><thead><tr><th scope="col">Day</th><th scope="col">Pickups</th><th scope="col">During your plans</th><th scope="col">Seen by Alibi</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function fxHabitsWeek(list, c) {
  const rows = (Array.isArray(list) ? list : []).filter(h => h && (h.label || h.habit));
  const body = rows.length ? `<div class="fx-rows">${rows.map(h => {
    const src = FX_SRC[h.top_source], rate = fxNum(h.pickups_per_hour) ? h.pickups_per_hour : null;
    const meta = [fxNum(h.sessions) ? `${h.sessions} session${fxS(h.sessions)}` : "", fxNum(h.best_hour) ? `best at ${pad(h.best_hour)}:00` : ""].filter(Boolean).join(" · ");
    return `<div class="fx-row"><div class="fx-name"><span class="fx-ic">${wkIcon(habitIcon(h.habit, (habView[h.habit] && CHECK_TO_MOD[habView[h.habit].check]) || null), 16)}</span><span><b>${esc(h.label || hname(h.habit))}</b>
      <small>${meta ? `<span>${esc(meta)}</span>` : ""}</small></span></div>
      <div class="fx-nums"><b>${rate != null && rate >= FX_HOT ? wkDot("phone", 8, {hidden: true}) : ""}${rate != null ? `${fxRate(rate)} an hour` : "—"}</b>
      <small>${src ? `<span class="fx-src">${wkIcon(src[0], 12)}${esc(src[1])}</span>` : "pickups inside its blocks"}</small></div></div>`;
  }).join("")}</div>` : `<p class="fx-empty">No habit had a planned block this week.</p>`;
  return `<article class="al-card fx-card" style="--c:${c}" aria-labelledby="fxHabH"><h3 class="fx-h" id="fxHabH">By habit<small>phone pickups an hour inside its blocks</small></h3>${body}</article>`;
}

/* ---------- charts: inline SVG drawn at the card's real width, so 12px text stays 12px ---------- */
// [start, end) in hours of the block's own day: "HH:MM" + min first (timezone-proof), else the epochs.
function fxSpan(b) {
  const m = /^(\d\d):(\d\d)$/.exec(b && b.at || "");
  let h0 = m ? +m[1] + +m[2] / 60 : null;
  if (h0 == null && b && fxNum(b.start)) { const t = new Date(b.start * 1000); h0 = t.getHours() + t.getMinutes() / 60; }
  if (h0 == null) return null;
  const mins = fxNum(b.min) ? b.min : fxNum(b.end) && fxNum(b.start) ? (b.end - b.start) / 60 : 30;
  return [h0, Math.min(24, h0 + Math.max(5, mins) / 60)];
}
function fxMeasure(t) {
  try {
    if (!fxCtx) { fxCtx = document.createElement("canvas").getContext("2d"); fxFont = `500 12px ${getComputedStyle(document.body).fontFamily}`; }
    fxCtx.font = fxFont; return Math.ceil(fxCtx.measureText(t).width);
  } catch { return t.length * 7; }
}
const fxStep = max => max <= 4 ? 1 : max <= 8 ? 2 : max <= 20 ? 5 : max <= 40 ? 10 : max <= 100 ? 25 : 50;
// A column with a 4px round data end and a square foot on the baseline.
function fxBarPath(x, y, w, yB, r) {
  r = Math.max(0, Math.min(r, w / 2, yB - y));
  return r > .5 ? `M${fxF(x)} ${fxF(yB)}V${fxF(y + r)}A${fxF(r)} ${fxF(r)} 0 0 1 ${fxF(x + r)} ${fxF(y)}H${fxF(x + w - r)}A${fxF(r)} ${fxF(r)} 0 0 1 ${fxF(x + w)} ${fxF(y + r)}V${fxF(yB)}Z`
    : `M${fxF(x)} ${fxF(yB)}V${fxF(y)}H${fxF(x + w)}V${fxF(yB)}Z`;
}
// A 12px state mark for the plan lane: ✓ done, ◐ partly, ✕ didn't count, ● live, – skipped, ○ didn't happen, dashed ring later.
function fxGlyph(st, x, y) {
  const g = (inner) => `<g class="fx-g fx-g--${st}" transform="translate(${fxF(x)} ${fxF(y)})">${inner}</g>`;
  if (st === "done") return g(`<path d="M2.4 6.4l2.4 2.4 4.8-5.2"/>`);
  if (st === "partial") return g(`<circle cx="6" cy="6" r="4.4" stroke-width="1.5"/><path class="fx-fill" d="M6 1.6a4.4 4.4 0 0 1 0 8.8z"/>`);
  if (st === "slacked") return g(`<path d="M3 3l6 6M9 3l-6 6"/>`);
  if (st === "live") return g(`<circle class="fx-fill" cx="6" cy="6" r="4"/>`);
  if (st === "skipped") return g(`<path d="M3 6h6"/>`);
  if (st === "missed") return g(`<circle cx="6" cy="6" r="4.25" stroke-width="1.5"/>`);
  return g(`<circle cx="6" cy="6" r="4.25" stroke-width="1.5" stroke-dasharray="2.2 1.6"/>`);
}

// The plan's key: only the states this day has, each a tinted swatch with its glyph, then the word.
function fxPlanKey(plan) {
  const order = ["done", "partial", "slacked", "missed", "live", "now", "planned", "waiting", "nodata", "skipped"];
  const have = new Set(plan.map(b => fxStateOf(b.state)));
  return order.filter(st => have.has(st)).map(st => `<span><svg class="fx-ks" width="18" height="14" viewBox="0 0 18 14" aria-hidden="true" focusable="false"><rect class="fx-band fx-band--${st}" x=".5" y=".5" width="17" height="13" rx="3"/>${fxGlyph(st, 3, 1)}</svg>${esc(FX_STATE[st])}</span>`).join("");
}

function fxDaySVG(d, plan, W) {
  const hrs = d.phone === true && Array.isArray(d.pickups_by_hour) && d.pickups_by_hour.length === 24 ? d.pickups_by_hour.map(v => fxNum(v) && v > 0 ? v : 0) : null;
  const padL = hrs ? 26 : 2, padR = 2, slot = Math.max(4, (W - padL - padR) / 24), X = h => padL + h * slot;
  const y0 = 22, H = !hrs ? 48 : W < 560 ? 112 : 140, yB = y0 + H;          // no phone data: a short strip of the plan
  const max = hrs ? Math.max(1, ...hrs) : 1, step = fxStep(max), yv = v => yB - v / max * H;
  const peak = hrs ? (d.peak && fxNum(d.peak.hour) && hrs[d.peak.hour] ? d.peak.hour : hrs.indexOf(max)) : -1;
  const spans = plan.map((b, i) => ({b, s: fxSpan(b), st: fxStateOf(b.state), i})).filter(x => x.s);
  const o = [];
  // Each block tints the hours it touches by how it went (the chart is hourly; the minute is in the tooltip and By habit).
  spans.forEach(({s, st}) => {
    const a = Math.floor(s[0]), z = Math.max(a + 1, Math.ceil(s[1] - 1e-6));
    o.push(`<rect class="fx-band fx-band--${st}" x="${fxF(X(a) + 1)}" y="${y0 - 4}" width="${fxF((z - a) * slot - 2)}" height="${H + 4}" rx="4"/>`);
  });
  if (hrs) for (let v = step; v <= max; v += step) o.push(`<line class="fx-grid" x1="${padL}" x2="${fxF(W - padR)}" y1="${fxF(Math.round(yv(v)) + .5)}" y2="${fxF(Math.round(yv(v)) + .5)}"/><text class="fx-tick" x="${padL - 8}" y="${fxF(yv(v) + 4)}" text-anchor="end">${v}</text>`);
  o.push(`<line class="fx-base" x1="${padL}" x2="${fxF(W - padR)}" y1="${yB + .5}" y2="${yB + .5}"/>`);
  if (hrs) {
    const bw = Math.max(3, Math.min(24, Math.round(slot * .62)));
    hrs.forEach((v, h) => { if (v) o.push(`<path class="fx-bar fx-hbar${h === peak ? " fx-bar--peak" : ""}" data-h="${h}" style="--i:${h}" d="${fxBarPath(X(h) + (slot - bw) / 2, yv(v), bw, yB, 4)}"/>`); });
    if (peak >= 0 && hrs[peak]) o.push(`<text class="fx-cap fx-cap--peak" style="--i:${peak}" x="${fxF(X(peak) + slot / 2)}" y="${fxF(yv(hrs[peak]) - 7)}" text-anchor="middle">${hrs[peak]}</text>`);
  }
  if (d.date === fxToday()) {                    // the now-line, as on the Today timeline
    const n = new Date(wkNow() * 1000), x = X(n.getHours() + n.getMinutes() / 60);
    o.push(`<line class="fx-now" x1="${fxF(x)}" x2="${fxF(x)}" y1="${y0 - 6}" y2="${yB}"/><circle class="fx-nowdot" cx="${fxF(x)}" cy="${y0 - 6}" r="3"/>`);
  }
  const every = slot * 3 < 46 ? 6 : 3;
  for (let h = 0; h < 24; h += every) o.push(`<text class="fx-tick" x="${fxF(h ? X(h) : padL)}" y="${yB + 18}" text-anchor="${h ? "middle" : "start"}">${pad(h)}:00</text>`);
  // The plan lane: each block's glyph and name under its first hour, in up to two rows that never overlap.
  let Ht = yB + 26;
  if (spans.length) {
    const yL = yB + 42, ends = [-1e9, -1e9]; let rows = 0;
    spans.forEach(({b, s, st, i}) => {
      const label = String(b.label || hname(b.habit) || ""), lw = 16 + fxMeasure(label);
      const lx = Math.max(padL, Math.min(X(Math.floor(s[0])) + 1, W - padR - lw)), row = lx >= ends[0] + 10 ? 0 : lx >= ends[1] + 10 ? 1 : -1;
      if (row < 0 || !label) return;
      ends[row] = lx + lw; rows = Math.max(rows, row + 1);
      const ty = yL + row * 18;
      o.push(`<g class="fx-lanem" style="--i:${i}">${fxGlyph(st, lx, ty - 10)}<text class="fx-lanel" x="${fxF(lx + 16)}" y="${ty}">${esc(label)}</text></g>`);
    });
    if (rows) Ht = yL + (rows - 1) * 18 + 6;
  }
  return {svg: `<svg width="${fxF(W)}" height="${Ht}" viewBox="0 0 ${fxF(W)} ${Ht}" aria-hidden="true" focusable="false">${o.join("")}</svg>`,
    geo: {padL, slot, n: 24, top: h => hrs && hrs[h] ? yv(hrs[h]) : yB, tip: h => fxHourTip(hrs, spans, peak, h)}};
}
function fxHourTip(hrs, spans, peak, h) {
  const over = spans.filter(({s}) => s[0] < h + 1 && s[1] > h);
  const lines = [`${pad(h)}:00 to ${pad((h + 1) % 24)}:00${h === peak ? ", the peak" : ""}`]
    .concat(over.map(({b, st}) => `${b.label || hname(b.habit)} ${b.at || ""}: ${FX_STATE[st].toLowerCase()}`));
  const head = hrs ? `${hrs[h]} pickup${fxS(hrs[h])}` : "No phone data";
  return {html: `<b>${esc(head)}</b>${lines.map(t => `<span>${esc(t)}</span>`).join("")}`, text: `${head}. ${lines.join(". ")}.`};
}

function fxWeekSVG(w, W) {
  const days = w.days.filter(x => x && fxDate(x.date)).slice(-7), n = days.length || 1, today = fxToday();
  const padL = 26, padR = 2, slot = (W - padL - padR) / n, y0 = 22, H = W < 560 ? 112 : 140, yB = y0 + H;
  const max = Math.max(1, ...days.map(x => fxNum(x.pickups) ? x.pickups : 0)), step = fxStep(max), yv = v => yB - v / max * H;
  const hi = days.reduce((a, x, i) => fxNum(x.pickups) && (a < 0 || x.pickups > days[a].pickups) ? i : a, -1);
  const bw = Math.max(6, Math.min(24, Math.round(slot * .5))), o = [];
  for (let v = step; v <= max; v += step) o.push(`<line class="fx-grid" x1="${padL}" x2="${fxF(W - padR)}" y1="${fxF(Math.round(yv(v)) + .5)}" y2="${fxF(Math.round(yv(v)) + .5)}"/><text class="fx-tick" x="${padL - 8}" y="${fxF(yv(v) + 4)}" text-anchor="end">${v}</text>`);
  o.push(`<line class="fx-base" x1="${padL}" x2="${fxF(W - padR)}" y1="${yB + .5}" y2="${yB + .5}"/>`);
  days.forEach((x, i) => {
    const cx = padL + i * slot + slot / 2, bx = cx - bw / 2;
    if (fxNum(x.pickups) && x.pickups > 0) {
      const tot = x.pickups, inb = Math.max(0, Math.min(tot, fxNum(x.in_blocks_pickups) ? x.in_blocks_pickups : 0)), oth = tot - inb, g = [];
      // pickups during plans sit on the baseline in phone red; the rest stack above, 2px of card between them
      if (inb > 0) g.push(`<path class="fx-bar fx-bar--plan" d="${fxBarPath(bx, yv(inb), bw, yB, oth > 0 ? 0 : 4)}"/>`);
      if (oth > 0) { const foot = inb > 0 ? yv(inb) - 2 : yB; if (foot - yv(tot) > .5) g.push(`<path class="fx-bar" d="${fxBarPath(bx, yv(tot), bw, foot, 4)}"/>`); }
      o.push(`<g class="fx-col" data-h="${i}" style="--i:${i}">${g.join("")}</g><text class="fx-cap${i === hi ? " fx-cap--peak" : ""}" style="--i:${i}" x="${fxF(cx)}" y="${fxF(yv(tot) - 7)}" text-anchor="middle">${tot}</text>`);
    } else if (!fxNum(x.pickups)) o.push(`<text class="fx-nil" x="${fxF(cx)}" y="${yB - 8}" text-anchor="middle">—</text>`);
    o.push(`<text class="fx-tick${x.date === today ? " is-today" : ""}" x="${fxF(cx)}" y="${yB + 18}" text-anchor="middle">${esc(fxDay(x.date, {weekday: "short"}))}</text>`);
  });
  const Ht = yB + 26;
  return {svg: `<svg width="${fxF(W)}" height="${Ht}" viewBox="0 0 ${fxF(W)} ${Ht}" aria-hidden="true" focusable="false">${o.join("")}</svg>`,
    geo: {padL, slot, n, top: i => fxNum(days[i] && days[i].pickups) && days[i].pickups > 0 ? yv(days[i].pickups) : yB, tip: i => fxDayTip(days[i])}};
}
function fxDayTip(x) {
  if (!x) return {html: "", text: ""};
  const when = fxDay(x.date, {weekday: "long", day: "numeric", month: "long"});
  const head = fxNum(x.pickups) ? `${fxInt(x.pickups)} pickup${fxS(x.pickups)}` : "No phone data";
  const lines = [when, fxNum(x.in_blocks_pickups) && fxNum(x.pickups) ? `${fxInt(x.in_blocks_pickups)} during your plans` : "",
    fxNum(x.seen_min) ? `${wkHM(x.seen_min)} seen by Alibi` : ""].filter(Boolean);
  return {html: `<b>${esc(head)}</b>${lines.map(t => `<span>${esc(t)}</span>`).join("")}`, text: `${head}. ${lines.join(". ")}.`};
}

// Draw every chart in the panel, again only when its width or its data changed. Listeners ride on the element, set once.
function fxCharts() {
  const box = $("#focusPanel"), c = fxCache[fxTab]; if (!box || !c) return;
  box.querySelectorAll(".fx-chart[data-chart]").forEach(el => {
    const W = Math.floor(el.clientWidth); if (W < 80) return;
    const week = el.dataset.chart === "week", plan = week ? [] : (c.blocks || []).filter(b => b && fxSpan(b));
    // today's now-line moves in 5-minute steps, so a quiet refresh redraws it even when no pickup came in
    const sig = `${W}|${week ? JSON.stringify(c.week.days) : JSON.stringify([c.day.date, c.day.phone, c.day.pickups_by_hour, c.day.peak, fxToday(),
      c.day.date === fxToday() ? Math.floor(wkNow() / 300) : 0, plan.map(b => [b.at, b.min, b.start, b.state, b.label])])}`;
    if (el.dataset.fxSig === sig) return;
    const r = week ? fxWeekSVG(c.week, W) : fxDaySVG(c.day, plan, W);
    el.dataset.fxSig = sig; el.innerHTML = r.svg; el.__fxGeo = r.geo;
    if (fxNum(el.__fxAt)) fxShowAt(el, Math.min(el.__fxAt, r.geo.n - 1));      // a redraw under the pointer keeps its hour lit
    if (el.__fxOn) return;
    el.__fxOn = true;
    el.addEventListener("pointermove", e => fxPoint(el, e));
    el.addEventListener("pointerdown", e => fxPoint(el, e));
    // a tap keeps its tooltip until the next tap elsewhere (blur); a mouse leaving hides it
    el.addEventListener("pointerleave", e => { if (e.pointerType !== "touch" && document.activeElement !== el) fxTipHide(el); });
    el.addEventListener("focus", () => { if (el.matches(":focus-visible")) fxShowAt(el, fxStart(el), true); });
    el.addEventListener("blur", () => fxTipHide(el));
    el.addEventListener("keydown", e => {
      const g = el.__fxGeo; if (!g) return;
      const k = {ArrowLeft: -1, ArrowRight: 1}[e.key], cur = fxNum(el.__fxAt) ? el.__fxAt : fxStart(el);
      let to = null;
      if (k) to = Math.max(0, Math.min(g.n - 1, cur + k)); else if (e.key === "Home") to = 0; else if (e.key === "End") to = g.n - 1; else if (e.key === "Escape") { fxTipHide(el); return; }
      if (to == null) return;
      e.preventDefault(); fxShowAt(el, to, true);
    });
  });
}
// Keyboard starts at the peak (or the busiest day), which is the point of the chart.
function fxStart(el) {
  const c = fxCache[fxTab];
  if (el.dataset.chart === "week") { const d = (c && c.week && c.week.days || []).slice(-7); let b = 0; d.forEach((x, i) => { if (fxNum(x.pickups) && x.pickups > ((d[b] || {}).pickups || 0)) b = i; }); return b; }
  const p = c && c.day && c.day.peak; return p && fxNum(p.hour) ? p.hour : 12;
}
function fxPoint(el, e) {
  const g = el.__fxGeo; if (!g) return;
  const r = el.getBoundingClientRect(), i = Math.floor((e.clientX - r.left - g.padL) / g.slot);
  if (i < 0 || i >= g.n) return fxTipHide(el);
  if (i !== el.__fxAt) fxShowAt(el, i);
}
function fxShowAt(el, i, say) {
  const g = el.__fxGeo, fig = el.closest(".fx-fig"), tip = fig && fig.querySelector(".fx-tip"); if (!g || !tip) return;
  el.__fxAt = i;
  const t = g.tip(i); tip.innerHTML = t.html; tip.classList.add("show");
  el.classList.add("is-hover");
  el.querySelectorAll(".is-hot").forEach(x => x.classList.remove("is-hot"));
  el.querySelectorAll(`[data-h="${i}"]`).forEach(x => x.classList.add("is-hot"));
  const cx = g.padL + i * g.slot + g.slot / 2, tw = tip.offsetWidth, th = tip.offsetHeight, fw = fig.clientWidth;
  tip.style.left = `${Math.max(0, Math.min(fw - tw, cx - tw / 2))}px`;
  tip.style.top = `${Math.max(-8, g.top(i) - th - 10)}px`;
  if (say) { const live = fig.querySelector("[data-fx-live]"); if (live) live.textContent = t.text; }
}
function fxTipHide(el) {
  const fig = el.closest(".fx-fig"), tip = fig && fig.querySelector(".fx-tip");
  if (tip) tip.classList.remove("show");
  el.classList.remove("is-hover"); el.__fxAt = null;
  el.querySelectorAll(".is-hot").forEach(x => x.classList.remove("is-hot"));
}

/* ---------- entrance: bars grow and the number counts up on first sight (held until the section scrolls into view, as
   week.js does); a tab switch also lifts the cards in. Automated renders and reduced motion never hold. ---------- */
const fxIO = !navigator.webdriver && "IntersectionObserver" in window
  ? new IntersectionObserver(es => es.forEach(e => { if (!e.isIntersecting) return; fxSeen = true; fxIO.disconnect(); if (fxHeld) { fxHeld = false; fxPlay($("#focusPanel"), false); } }), {rootMargin: "0px 0px -15% 0px"})
  : null;
function fxEnter(box, swap) {
  if (wkReduced()) { box.classList.remove("fx-pre"); if (swap) fxPlay(box, true); else fxCount(box, false); return; }
  if (fxIO && !fxSeen) { box.classList.add("fx-pre"); fxHeld = true; fxIO.observe($("#focusBlock")); return; }
  fxPlay(box, swap);
}
function fxPlay(box, swap) {
  if (!box) return;
  box.classList.remove("fx-pre", "fx-play", "fx-swap"); void box.offsetWidth;
  box.classList.add("fx-play"); if (swap) box.classList.add("fx-swap");
  fxCount(box, !wkReduced());
  clearTimeout(fxPlayT); fxPlayT = setTimeout(() => box.classList.remove("fx-play", "fx-swap"), 1800);
}
// The big number counts up over 700 ms (tabular figures, so nothing jitters); reduced motion shows it at once.
function fxCount(box, animate) {
  box.querySelectorAll("[data-count]").forEach(el => {
    const to = +el.dataset.count; if (!isFinite(to)) return;
    if (!animate || to < 3) { el.textContent = to.toLocaleString("en-GB"); return; }
    const t0 = performance.now(), step = t => { const k = Math.min(1, (t - t0) / 700), v = Math.round(to * (1 - Math.pow(1 - k, 3)));
      el.textContent = v.toLocaleString("en-GB"); if (k < 1 && el.isConnected) requestAnimationFrame(step); };
    el.textContent = "0"; requestAnimationFrame(step);
  });
}

/* ---------- tabs (roving tabindex; arrows, Home and End move and select) ---------- */
function fxMark(tab, focus) {
  document.querySelectorAll("#focusTabs [role=tab]").forEach(b => {
    const on = b.dataset.fx === tab;
    b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1;
    if (on) { $("#focusPanel")?.setAttribute("aria-labelledby", b.id); if (focus) b.focus(); }
  });
}
function fxSelect(tab, focus) {
  if (!FX_TABS.includes(tab)) return;
  fxMark(tab, focus);
  if (tab === fxTab) return;
  fxTab = tab;
  try { localStorage.setItem("alibi.focusTab", tab); } catch {}
  fxWantPlay = true; fxPaint(); fxLoad(tab);
}
function fxTick() { if (!document.hidden) fxLoad(fxTab); }
// #focus or #focus/yesterday (a link from a card or a brief): pick the tab, then scroll there once shown.
// core.js route() ignores these hashes, so this listener owns them.
function fxRoute() {
  const m = /^#focus(?:\/(today|yesterday|week))?$/.exec(location.hash); if (!m) return;
  if (m[1]) fxSelect(m[1], false);
  fxGo = true; fxScroll();
}
function fxScroll() {
  const sec = $("#focusBlock"); if (!fxGo || !sec || sec.hidden) return;
  fxGo = false; sec.scrollIntoView({behavior: wkReduced() ? "auto" : "smooth", block: "start"});
}

(function fxInit() {
  const sec = $("#focusBlock"), tabs = $("#focusTabs"); if (!sec || !tabs) return;
  let t = new URLSearchParams(location.search).get("focus");
  if (!FX_TABS.includes(t)) { t = null; try { t = localStorage.getItem("alibi.focusTab"); } catch {} }
  if (FX_TABS.includes(t)) fxTab = t;
  fxMark(fxTab, false);
  tabs.addEventListener("click", e => { const b = e.target.closest("[role=tab]"); if (b) fxSelect(b.dataset.fx, false); });
  tabs.addEventListener("keydown", e => {
    const i = FX_TABS.indexOf(fxTab), k = {ArrowLeft: -1, ArrowRight: 1}[e.key];
    const to = k ? FX_TABS[(i + k + FX_TABS.length) % FX_TABS.length] : e.key === "Home" ? FX_TABS[0] : e.key === "End" ? FX_TABS[FX_TABS.length - 1] : null;
    if (to) { e.preventDefault(); fxSelect(to, true); }
  });
  // Charts follow the card's width (window resize, the drawer, a phone turned sideways).
  if ("ResizeObserver" in window) {
    let raf = 0;
    fxRO = new ResizeObserver(es => { const w = Math.round(es[0].contentRect.width); if (w === fxW) return; fxW = w; cancelAnimationFrame(raf); raf = requestAnimationFrame(fxCharts); });
    fxRO.observe($("#focusPanel"));
  }
  document.addEventListener("visibilitychange", fxTick);
  addEventListener("hashchange", fxRoute);
  fxRoute();
  fxLoad(fxTab, true);
  // Stage reads the fixture from lastState once the first poll lands; live asks every minute (stale answers are skipped).
  setInterval(fxTick, fxStage() ? 1500 : 60000);
})();
