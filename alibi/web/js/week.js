/* week.js: Today plan blocks, week hero, report, habit x day grid, pace. Classic script; load order core, now, week, sessions, setup, onboarding, boot. */
function renderToday(t) { lastToday = t; renderHero(); }
let lastToday = null, lastReport = null;

/* ---------- report ---------- */
const fmtN = n => Math.round(n || 0).toLocaleString("en-GB");
function renderHero() {
  const r = lastReport, t = lastToday, box = $("#weekHero");
  if (!r || !r.totals) return;
  const T = r.totals, tgt = Math.max(1, T.target_min || 0);
  const w = v => Math.min(100, (v || 0) / tgt * 100).toFixed(2);
  const fresh = !(T.declared_min || T.verified_min);
  const gap = Math.max(0, (T.pace_min || 0) - (T.verified_min || 0));
  const hon = T.honesty, honP = hon == null ? null : Math.round(hon * 100);
  const honC = hon == null ? "var(--absent)" : hon >= .85 ? "var(--on_task)" : hon >= .6 ? "var(--idle)" : "var(--phone)";
  const C = 2 * Math.PI * 26;
  const dots = t ? Array.from({length: t.habits_total || 0}, (_, i) => `<i class="${i < (t.habits_done || 0) ? "on" : ""}"></i>`).join("") : "";
  const allNew = (r.rows || []).length && (r.rows || []).every(x => x.is_new);
  const sub = fresh ? `A fresh start — your first session sets the pace.`
    : allNew && gap <= 0 ? `Your first week — goals count from the day you added each habit.`
    : gap <= 0 ? `<b>On pace</b> for the week. Nice.` : `<b>${esc(hm(gap))}</b> to catch up to an even pace.`;
  box.innerHTML = `
    <div><span class="eyebrow">this week</span>
      <div class="big"><b>${fmtN(T.verified_min)}</b><small>of ${fmtN(T.target_min)} min done</small></div>
      <div class="hbar" role="img" aria-label="${fmtN(T.verified_min)} of ${fmtN(T.target_min)} minutes done this week"><div class="c" style="width:${w(T.declared_min)}%"></div><div class="v" style="width:${w(T.verified_min)}%"></div></div>
      <div class="hsub">${sub}</div></div>
    <div class="gauge" style="--c:${honC}" title="Of the minutes you said you'd do, how many Alibi actually saw."><svg viewBox="0 0 64 64" aria-hidden="true"><circle class="gt" cx="32" cy="32" r="26" fill="none" stroke-width="6"/><circle class="ga" cx="32" cy="32" r="26" fill="none" stroke-width="6" stroke-dasharray="${C.toFixed(2)}" stroke-dashoffset="${(C * (1 - (hon || 0))).toFixed(2)}"/></svg>
      <div><div class="gv">${honP == null ? "—" : honP + "%"}</div><div class="gl">${honP == null ? "Honesty score<br>appears after your first session" : `Honesty: ${fmtN(T.verified_min)} of ${fmtN(T.declared_min)} min<br>you said checked out`}</div></div></div>
    <div><span class="eyebrow">today</span><div class="big"><b>${t ? esc(t.tally || "—") : "—"}</b><small>habits done</small></div><div class="tally">${dots}</div>
      <div class="hsub">${t && t.declared_min ? `Alibi saw ${fmtN(t.verified_min)} of ${fmtN(t.declared_min)} min` : ""}</div></div>`;
}
function renderReport(r) {
  if (!r) return;
  lastReport = r; renderHero();
  if (r.week_start) {
    const ws = r.week_start, we = ws + 6*86400;
    $("#weekRange").textContent = `— ${new Date(ws*1000).toLocaleDateString(undefined,{day:"numeric",month:"short"})} to ${new Date(we*1000).toLocaleDateString(undefined,{day:"numeric",month:"short"})}`;
  }
  const sents = (r.summary || "").match(/[^.!?]+[.!?]+(\s|$)|[^.!?]+$/g) || [];
  const pull = sents.filter(x => /^\s*(Today|Tomorrow):/.test(x)).join(" ").trim() || sents.slice(-1).join("").trim();
  const fresh = !(r.totals?.declared_min || r.totals?.verified_min);
  $("#quote").innerHTML = fresh ? `<span class="none">Nothing logged yet this week. Your first session starts the story.</span>` : r.summary ? `<span class="hl">${esc(plain(pull))}</span><cite>— Alibi, ${r.generated_at ? "as of " + clockT(r.generated_at) : "this week"}</cite>` : `<span class="none">Nothing to report yet this week.</span>`;
  $("#fullRep").textContent = plain(r.summary || "");
  if (fresh) $(".readmore").hidden = true;
  if (!fresh) $(".readmore").hidden = !r.summary || sents.length < 2;
  renderGrid();
  const sorted = [...(r.rows || [])].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));
  const rows = sorted.map(x => {
    const scale = Math.max(x.target_min || 0, 1);
    const w = v => Math.min(100, (v || 0) / scale * 100).toFixed(2);
    const sev = x.severity || (x.status === "aligned" ? "on_pace" : "behind");
    const gap = x.gap_to_pace_min ?? x.behind_by_min ?? 0;
    const st = x.is_new && !(x.verified_min >= (x.target_min || 1)) ? `<div class="statusline">new · ${x.target_min ? esc(hm(x.target_min)) + " planned this week" : "starts next week"}</div>`
      : sev === "on_pace" ? `<div class="statusline aligned">on pace</div>`
      : fresh || !x.sessions ? `<div class="statusline">${x.target_min ? esc(hm(x.target_min)) + " this week" : ""}</div>` : `<div class="statusline">${esc(hm(gap))} to catch up</div>`;
    const tip = `Alibi saw ${x.verified_min} min · you said ${x.declared_min} min · target ${x.target_min} min`;
    const meta = [CHECK_WORD[x.modality], `${x.sessions ?? 0} session${x.sessions === 1 ? "" : "s"}`, x.streak_days ? `${x.streak_days}-day streak` : "", x.honesty != null && x.declared_min ? `${Math.round(x.honesty * 100)}% checked out` : ""].filter(Boolean).join(" · ");
    return `<div class="row sev-${sev === "worst" && !fresh ? "behind" : sev}">
      <div><span class="name">${esc(dispName(x.habit, x.label))}</span>${sev === "worst" && !fresh && x.sessions ? `<span class="wtag">needs the most love</span>` : ""}<span class="rowmeta">${esc(meta)}</span></div>
      <div class="track" title="${esc(tip)}"><div class="bg" style="width:100%"></div>
        <div class="decl" style="width:${w(x.declared_min)}%"></div><div class="ver" style="width:${w(x.verified_min)}%"></div>
        ${x.pace_target_min != null && !fresh && !x.is_new ? `<div class="pace" data-l="even pace" style="left:${w(x.pace_target_min)}%"></div>` : ""}</div>
      <div><div class="nums"><div><small>done</small><span class="v">${x.verified_min ?? 0}</span></div><div><small>you said</small>${x.declared_min ?? 0}</div><div><small>goal</small>${x.target_min ?? "—"}</div></div>${st}</div>
    </div>`;
  });
  const run = r.running;
  if (run) {
    const n = run.target_sessions || 3, runs = run.runs || [];
    const sorted = [...runs].sort((a,b) => (b.distance_km >= run.min_km) - (a.distance_km >= run.min_km) || a.start_date - b.start_date);
    const pips = Array.from({length: Math.max(n, runs.length)}, (_, i) => {
      const rr = sorted[i];
      if (!rr) return `<span class="pip" title="not yet">—</span>`;
      const ok = rr.distance_km >= (run.min_km || 0);
      return `<span class="pip ${ok ? "ok" : "short"}" title="${esc(rr.name)} · ${rr.distance_km} km · ${rr.moving_min} min · ${dayT(rr.start_date)}${ok ? "" : " — too short to count (needs " + run.min_km + " km)"}">${rr.distance_km}</span>`;
    }).join("");
    const behind = (run.qualifying ?? 0) < n;
    rows.push(`<div class="row ${behind ? "sev-behind" : "sev-on_pace"}">
      <div><span class="name">${esc(dispName(run.habit || "running", run.label))}</span><span class="rowmeta">from Strava · runs of ${run.min_km} km or more count</span></div>
      <div><div class="pips">${pips}</div><div class="runlist">${runs.length ? runs.map(x => `${dayT(x.start_date)} ${x.distance_km} km${x.distance_km >= run.min_km ? "" : " — too short to count"}`).join(" · ") : esc(run.strava && !run.strava.connected ? run.strava.text : "No runs this week yet.")}</div></div>
      <div><div class="nums"><div><small>runs</small><span class="v">${run.qualifying ?? 0} of ${n}</span></div><div><small>this week</small>${run.week_km ?? 0} km</div></div>
      <div class="statusline ${behind ? "" : "aligned"}">${behind ? `${n - (run.qualifying ?? 0)} more to go` : "goal met ✓"}</div></div>
    </div>`);
  }
  (r.health || []).forEach(x => {
    const days = (x.days || []).slice(-7);
    const pips = days.map(d => `<span class="pip ${d.met ? "ok" : d.met === false ? "short" : ""}" title="${esc(d.date)} · ${esc(d.text || "no data")}">${d.met ? "✓" : d.met === false ? "·" : "—"}</span>`).join("");
    rows.push(`<div class="row ${x.status === "aligned" ? "sev-on_pace" : "sev-behind"}">
      <div><span class="name">${esc(x.label || hname(x.habit))}</span><span class="rowmeta">from Apple Health · ${esc(x.target_text || "")}</span></div>
      <div><div class="pips">${pips || `<span class="runlist">No data from your iPhone yet.</span>`}</div><div class="runlist">${esc(x.today_text || x.text || "")}</div></div>
      <div><div class="nums"><div><small>days met</small><span class="v">${x.days_met ?? 0} of ${x.days_checked ?? 0}</span></div><div><small>streak</small>${x.streak_days ?? 0}</div></div>
      <div class="statusline ${x.status === "aligned" ? "aligned" : ""}">${x.status === "no_data" ? "waiting for iPhone" : x.status === "aligned" ? "on track" : esc(x.text || "")}</div></div>
    </div>`);
  });
  $("#rows").innerHTML = rows.join("") || `<p class="none">No habits yet.</p>`;
}
$("#readRep").addEventListener("click", e => {
  const f = $("#fullRep"), open = f.hidden; f.hidden = !open;
  e.target.setAttribute("aria-expanded", open); e.target.textContent = open ? "hide the full report" : "read the full report";
});

/* ---------- today: the plan ---------- */
let planData = null, weekPlan = [], plannedKey = null;
const createdTs = k => { const c = habView[k]?.created_at; if (!c) return 0; const [d, t] = c.split(" "); const [Y, M, D] = d.split("-").map(Number); const [h, m] = (t || "0:0").split(":").map(Number); return new Date(Y, M - 1, D, h, m).getTime() / 1000; };
const createdDay = k => (habView[k]?.created_at || "").slice(0, 10);
const beforeCreated = b => b.end && createdTs(b.habit) && b.end < createdTs(b.habit) && !b.session_id;
const STATE_C = {planned:"var(--faint)", now:"var(--accent)", live:"var(--accent)", done:"var(--done)", partial:"var(--partial)", slacked:"var(--slacked)", missed:"var(--slacked)", skipped:"var(--faint)", waiting:"var(--idle)"};
const inWords = sec => { sec = Math.max(0, sec|0); const h = Math.floor(sec/3600), m = Math.round(sec%3600/60); return h ? `${h} h${m ? " " + m + " min" : ""}` : `${Math.max(1, m)} min`; };
function nextPlanText() {
  const n = planData?.next; if (!n) return "";
  return n.state === "now" ? `${n.label} is planned now` : `Next: ${n.label} at ${n.at}`;
}
async function loadPlan() {
  try { planData = await api("/api/calendar/plan?days=1"); } catch { planData = null; }
  renderPlan();
}
function renderPlan() {
  const d = new Date();
  $("#todayTitle").innerHTML = `Today <em>— ${esc(d.toLocaleDateString(undefined, {weekday: "long", day: "numeric", month: "long"}))}</em>`;
  const box = $("#blocks"), nx = $("#nextUp");
  if (!planData) { box.innerHTML = `<div class="quiet">Couldn't load today's plan.</div>`; nx.textContent = ""; return; }
  const blocks = (planData.blocks || []).filter(b => !beforeCreated(b));
  const pk = plannedKey && blocks.find(b => b.key === plannedKey);
  if (pk && !["planned","now"].includes(pk.state) && $("#toast").classList.contains("planned")) hideToast();
  const anySched = Object.values(habView).some(h => (h.schedule || []).length);
  $("#planWeek").textContent = anySched ? "Change times" : "Plan my week";
  const n = planData.next;
  nx.innerHTML = n && !document.body.classList.contains("live") ? (n.state === "now" ? `<b>${esc(n.label)}</b> is planned right now.` : `Next up: <b>${esc(n.label)}</b> at ${esc(n.at)} · ${esc(hm(n.min))}${n.starts_in_s > 0 ? ` — in ${esc(inWords(n.starts_in_s))}` : ""}`) : "";
  if (!blocks.length) {
    box.innerHTML = anySched
      ? `<div class="todayempty"><p>Nothing planned for today. <b>Start something below</b> whenever you like.</p></div>`
      : `<div class="todayempty"><p><b>Give your habits a time.</b> Alibi reminds you when it's time — and can put them in Apple Calendar.</p><button class="primary" type="button" data-plan="1">Plan my week</button></div>`;
    renderHealthLines(); return;
  }
  box.innerHTML = blocks.map(b => {
    const v = habView[b.habit] || {}, auto = b.check === "strava" || b.check === "health";
    const st = b.state, done = ["done","partial","slacked"].includes(st);
    const pill = `<span class="spill" style="--c:${STATE_C[st] || "var(--faint)"}">${done ? (st === "done" ? "✓ " : "") : ""}${esc(b.state_text || st)}${done && b.ratio != null && !auto ? ` · ${Math.round(b.ratio * 100)}%` : ""}</span>`;
    let acts = "";
    const k = esc(b.key);
    if (st === "planned" || st === "now" || st === "missed") {
      acts = (auto ? "" : `<button type="button" class="${st === "now" ? "primary" : "ghostbtn"}" data-pa="start" data-key="${k}">${st === "now" ? "Start" : "Start now"}</button>`)
        + (st !== "missed" ? `<button type="button" class="ghostbtn" data-pa="move" data-key="${k}" data-at="${esc(b.at)}">Move</button><button type="button" class="ghostbtn" data-pa="skip" data-key="${k}">Skip</button>` : "");
    } else if (st === "skipped") acts = `<button type="button" class="ghostbtn" data-pa="unskip" data-key="${k}">Undo skip</button>`;
    else if (done && b.session_id) acts = `<button type="button" class="ghostbtn" data-pa="see" data-sid="${b.session_id}">See how it went</button>`;
    const sub = [`${hm(b.min)}`, CHECK_WORD[CHECK_TO_MOD[b.check]] || CHECK_WORD[b.check] || "", b.detail || "", b.in_calendar ? "in your calendar" : ""].filter(Boolean).join(" · ");
    return `<div class="blk st-${esc(st)}" id="blk-${k}">
      <div class="tm">${esc(b.at)}${b.moved ? `<small>was ${esc(b.planned_at)}</small>` : ""}</div><div class="em" aria-hidden="true">${esc(v.emoji || "•")}</div>
      <div class="bt"><b>${esc(b.label || dispName(b.habit))}</b><span>${esc(sub)}</span></div>
      <div class="ba">${pill}${acts}</div></div>`;
  }).join("");
  renderHealthLines();
}
function renderHealthLines() {
  const hs = lastReport?.health || [];
  $("#hlines").innerHTML = hs.map(x => `<span class="hline ${x.today_met ? "met" : ""}" title="${esc(x.text || "")}">${x.today_met ? "✓ " : ""}<b>${esc(x.label || x.habit)}</b> · ${esc(x.today_text || (x.status === "no_data" ? "waiting for your iPhone" : "no data yet"))}</span>`).join("");
}
$("#todayBlock").addEventListener("click", async e => {
  if (e.target.closest("[data-plan]") || e.target.closest("#planWeek")) return openSetup("Habits");
  const b = e.target.closest("[data-pa]"); if (!b) return;
  const key = b.dataset.key, act = b.dataset.pa;
  if (act === "see") return gotoSession(+b.dataset.sid);
  if (act === "move") {
    const ba = b.closest(".ba");
    ba.innerHTML = `<span class="movebox"><input class="fld" type="time" value="${esc(b.dataset.at)}" aria-label="New time"><button type="button" class="primary" data-pa="moveok" data-key="${esc(key)}">Move</button><button type="button" class="ghostbtn" data-pa="cancel">Cancel</button></span>`;
    ba.querySelector("input").focus(); return;
  }
  if (act === "cancel") return renderPlan();
  b.disabled = true;
  try {
    let j;
    if (act === "start") { j = await postJSON("/api/calendar/plan/start", {key}); if (j.reply) { $("#convo").innerHTML = `<div class="line alibi"><span class="who">Alibi</span><span class="txt">${esc(j.reply)}</span></div>`; } pollState(); }
    else if (act === "skip") j = await postJSON("/api/calendar/plan/skip", {key});
    else if (act === "unskip") j = await postJSON("/api/calendar/plan/unskip", {key});
    else if (act === "moveok") j = await postJSON("/api/calendar/plan/move", {key, at: b.closest(".movebox").querySelector("input").value});
    if (j && j.reply && act !== "start") showToast("note", j.reply);
  } catch (err) { showToast("note", `That didn't work: ${err.message}`); }
  loadPlan();
});

/* ---------- this week: habit × day grid ---------- */
async function loadWeekPlan() {
  if (!lastReport?.week_start) return;
  try { weekPlan = (await api(`/api/calendar/plan?days=7&date=${localDate(new Date(lastReport.week_start * 1000))}`)).blocks || []; } catch { weekPlan = []; }
  renderGrid();
}
function renderGrid() {
  const r = lastReport; if (!r || !r.week_start) return;
  const ws = new Date(r.week_start * 1000), today = localDate();
  const dates = Array.from({length: 7}, (_, i) => { const d = new Date(ws); d.setDate(ws.getDate() + i); return localDate(d); });
  const rank = {done: 3, partial: 2, slacked: 1};
  const rows = [];
  const timeHabits = (r.rows || []).map(x => x.habit);
  const keys = [...new Set([...Object.keys(habView).filter(k => !["strava","health"].includes(habView[k].check)), ...timeHabits])];
  keys.forEach(k => {
    const v = habView[k] || {}, rr = (r.rows || []).find(x => x.habit === k) || {};
    const cells = dates.map(ds => {
      if (createdDay(k) && ds < createdDay(k)) return {c: "future", t: "", tip: "Before you added this habit"};
      let best = null;
      sessById.forEach(s => { if (s.habit === k && dayKey(s) === ds && s.verdict && (!best || rank[s.verdict] > rank[best.verdict])) best = s; });
      if (best) return {c: best.verdict, t: best.verdict === "done" ? "✓" : best.verdict === "partial" ? "◐" : "✗", tip: `${VWORD[best.verdict]} · ${pct(best.on_task_ratio)}`};
      const pb = weekPlan.find(b => b.habit === k && b.date === ds && !beforeCreated(b));
      if (pb) {
        if (pb.state === "missed") return {c: "missed", t: "✗", tip: "Didn't happen"};
        if (pb.state === "skipped") return {c: "skipped", t: "–", tip: "Skipped"};
        if (["planned","now","live","waiting"].includes(pb.state)) return {c: "planned", t: pb.at, tip: `Planned ${pb.at}`};
      }
      return {c: ds > today ? "future" : "", t: "", tip: ""};
    });
    const streak = rr.streak_days || 0;
    rows.push({name: dispName(k, v.label || rr.label), sub: v.schedule_text || v.target_text || "", cells, stat: streak ? `<b class="${streak >= 3 ? "hot" : ""}">${streak}</b>day streak` : `<b>${rr.sessions || 0}</b>this week`});
  });
  const run = r.running;
  if (run) {
    const ck = run.habit || "running";
    const cells = dates.map(ds => {
      const rs = (run.runs || []).filter(x => localDate(new Date(x.start_date * 1000)) === ds);
      if (!rs.length) { if (createdDay(ck) && ds < createdDay(ck)) return {c: "future", t: ""}; const pb = weekPlan.find(b => b.habit === ck && b.date === ds && ["planned","now"].includes(b.state) && !beforeCreated(b)); return pb ? {c: "planned", t: pb.at, tip: "Planned run"} : {c: ds > today ? "future" : "", t: ""}; }
      const best = Math.max(...rs.map(x => x.distance_km || 0));
      return best >= run.min_km ? {c: "done", t: "✓", tip: `${best} km`} : {c: "partial", t: "◐", tip: `${best} km — too short to count (needs ${run.min_km} km)`};
    });
    rows.push({name: dispName(run.habit || "running", run.label), sub: `${run.target_sessions}× a week · ${run.min_km} km+`, cells, stat: `<b>${run.qualifying ?? 0}/${run.target_sessions}</b>runs`});
  }
  (r.health || []).forEach(x => {
    const byDate = Object.fromEntries((x.days || []).map(d => [d.date, d]));
    const cells = dates.map(ds => { const d = byDate[ds]; if (!d || d.met == null) return {c: ds > today || (createdDay(x.habit) && ds < createdDay(x.habit)) ? "future" : "", t: "", tip: d?.text || ""}; return d.met ? {c: "done", t: "✓", tip: d.text} : {c: "slacked", t: "·", tip: d.text}; });
    rows.push({name: x.label || hname(x.habit), sub: x.target_text || "", cells, stat: `<b>${x.days_met ?? 0}</b>days met`});
  });
  if (!rows.length) { $("#wgrid").innerHTML = ""; return; }
  const ti = dates.indexOf(today);
  const head = `<div class="gh"></div>${dates.map((ds, i) => { const d = new Date(ws); d.setDate(ws.getDate() + i); return `<div class="gh${i === ti ? " today" : ""}">${d.toLocaleDateString(undefined, {weekday: "narrow"})}<br>${d.getDate()}</div>`; }).join("")}<div class="gh gs"></div>`;
  $("#wgrid").innerHTML = `<div class="wgrid" role="table" aria-label="This week, habit by day">${head}${rows.map(x => `<div class="gn">${esc(x.name)}<small>${esc(x.sub)}</small></div>${x.cells.map((c, i) => `<div class="cell ${c.c}${i === ti ? " todaycol" : ""}" title="${esc(c.tip || "")}">${esc(c.t)}</div>`).join("")}<div class="gs">${x.stat}</div>`).join("")}</div>
    <div class="gkey"><span><i style="background:var(--on_task)"></i>done</span><span><i style="background:color-mix(in srgb,var(--idle) 30%,transparent);box-shadow:inset 0 0 0 1.5px var(--idle)"></i>partly</span><span><i style="background:color-mix(in srgb,var(--phone) 12%,transparent)"></i>didn't count / didn't happen</span><span><i style="box-shadow:inset 0 0 0 1.5px var(--rule)"></i>planned</span></div>`;
}
