/* setup.js: setup drawer: tabs, connections + health checks, habits editor, your data. Classic script; load order core, now, week, sessions, setup, onboarding, boot. */
/* ---------- setup: connections ---------- */
const REQUIRED = new Set(["camera","windows","island"]);
const checkState = c => c.ok ? "ok" : (c.key === "witness" && /test mode|mock|demo/i.test(c.detail || "")) ? "demo" : REQUIRED.has(c.key) ? "bad" : "opt";
const ICON = {camera: "camera", windows: "laptop", witness: "lens", text: "sparkle", strava: "run", island: "laptop"};
// Icons from window.AlibiIcons (icons.js); a bare dot if it hasn't loaded.
const ico = (name, size = 20) => (window.AlibiIcons && AlibiIcons.svg(name, size)) || "";
// Where photos are judged, exact to the witness in use (AGENTS.md hard rule 5; same test as core.js renderPrivacy).
// Unknown witness: say nothing about where rather than guess.
function photoWhere(s) {
  s = s || (typeof lastState !== "undefined" && lastState) || {};
  const w = s.witness || "";
  return (w === "apple" || w === "mock" || /local/i.test(s.witness_label || "")) ? "Photos are checked on this Mac."
    : w ? "Photos go to NVIDIA's model to be checked." : "";
}
// Server copy (templates.py, onboarding.py) still says "Photos stay on this Mac." unconditionally; swap in the true line.
const photoFix = (t, s) => String(t ?? "").replace(/\s*Photos stay on this Mac\.?/g, m => { const w = photoWhere(s); return w ? " " + w : ""; });
function setTab(name) {
  ["Health", "Habits", "Data"].forEach(n => { $("#tab" + n).setAttribute("aria-selected", n === name); $("#pane" + n).hidden = n !== name; });
  if (name === "Data") loadData();
  updateFoot();
}
let habDirty = false;
function updateFoot() { $("#dfoot").hidden = !($("#tabHabits").getAttribute("aria-selected") === "true" && (habDirty || $("#saveMsg").textContent)); }
document.querySelector(".tabs").addEventListener("click", e => { const b = e.target.closest("[data-tab]"); if (b) setTab(b.dataset.tab); });
document.querySelector(".tabs").addEventListener("keydown", e => {
  if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
  const T = ["Health","Habits","Data"], cur = T.findIndex(n => $("#tab" + n).getAttribute("aria-selected") === "true");
  const n = T[(cur + (e.key === "ArrowRight" ? 1 : 2)) % 3]; setTab(n); $("#tab" + n).focus();
});
let lastHealth = null;
async function loadHealth() {
  let h;
  try { h = await api("/api/health"); } catch { $("#sdot").className = "sdot"; return null; }
  lastHealth = h;
  const bad = h.checks.filter(c => checkState(c) === "bad").length;
  $("#sdot").className = "sdot " + (bad ? "bad" : "ok");
  $("#setupN").textContent = bad ? ` · ${bad}` : "";
  $("#tabHealthN").textContent = bad ? `· ${bad}` : "";
  $("#setupBtn").title = !bad ? "Setup — everything needed is working" : `Setup — ${bad} thing${bad === 1 ? "" : "s"} to sort out`;
  return h;
}
function connCard({icon, title, ok, state, text, acts, msg, id}) {
  const tone = ok ? "ok" : /needs|blocked|reconnect/.test(state || "") ? "need" : /test/.test(state || "") ? "demo" : "";
  return `<div class="conn ${tone}" ${id ? `id="${id}"` : ""}><div class="ci" aria-hidden="true">${ico(icon)}</div><div>
    <h4><span>${esc(title)}</span>${state ? `<span class="st-pill ${tone}">${esc(state)}</span>` : ""}</h4><p>${text}</p></div>
    ${acts ? `<div class="cacts">${acts}</div>` : ""}<div class="cmsg">${msg || ""}</div></div>`;
}
function renderChecks(h) {
  if (!h) { $("#checks").innerHTML = `<div class="quiet">Alibi isn't running, so it can't check anything right now.</div>`; return; }
  $("#checks").innerHTML = h.checks.filter(c => c.key !== "strava").map(c => {
    const cls = checkState(c);
    let acts = "";
    if (c.key === "island" && !c.ok) acts = `<span class="cd">Open <b>Alibi</b> from your Applications folder — the notch appears at the top of your screen.</span>`;
    const fix = !c.ok && c.fix && !/see Details/i.test(c.fix) ? ` ${esc(c.fix)}.` : "";
    return connCard({icon: ICON[c.key] || "eye", title: c.label, ok: c.ok, state: ({ok: "working", bad: "needs you", demo: "test mode", opt: "optional"})[cls], text: esc(c.detail) + fix, acts});
  }).join("");
  const s = lastState || {};
  $("#modelsInfo").innerHTML = `Photo checker: <b>${esc(s.witness_label || s.witness || "—")}</b> · replies: <b>${esc(s.text_model || "—")}</b>${s.daemon?.up_since ? ` · running for ${esc(dur(s.now - s.daemon.up_since))}` : ""}`;
  $("#techPre").textContent = h.checks.map(c => `${c.key}: ${c.details || c.detail || ""}`).join("\n");
}
async function renderConnections() {
  const [cal, integ] = await Promise.allSettled([api("/api/calendar/status"), api("/api/integrations")]);
  if (cal.status === "fulfilled") {
    const c = cal.value;
    const acts = (c.action ? `<button type="button" class="${c.connected ? "ghostbtn" : "primary"}" data-cpost="${esc(c.action.post)}">${esc(c.action.label)}</button>` : "")
      + (c.connected ? `<label class="toggle"><input type="checkbox" data-calset="log_unplanned" ${c.log_unplanned ? "checked" : ""}>Also add sessions I start without a plan</label><button type="button" class="linkbtn" data-cpost="/api/calendar/disconnect">Disconnect</button>` : "");
    const extra = c.connected && c.last_sync_text ? `Last synced ${esc(c.last_sync_text)}.` : "";
    $("#connCal").innerHTML = connCard({id: "calCard", icon: "calendar", title: "Apple Calendar", ok: c.connected, state: c.connected ? "connected" : c.permission === "denied" ? "blocked" : "off", text: esc(c.message || "") + (extra ? ` ${extra}` : ""), acts});
  } else $("#connCal").innerHTML = `<div class="quiet">Calendar status isn't available.</div>`;
  if (integ.status === "fulfilled") {
    const {strava: st, health: he, phone: ph} = integ.value;
    const sActs = st.state === "connected" ? `<button type="button" class="ghostbtn" data-strava="sync">Check now</button><button type="button" class="linkbtn" data-strava="disconnect">Disconnect</button>`
      : `<a class="primary" style="text-decoration:none" href="${st.state === "needs_reconnect" || st.state === "ready_to_authorize" ? "/strava/connect" : "/strava/setup"}">${esc(st.action || "Connect Strava")}</a>`;
    const hActs = `<a class="${he.connected ? "ghostbtn" : "primary"}" style="text-decoration:none" href="/phone" target="_blank" rel="noopener">${esc(he.action || "Set up iPhone")}</a>`
      + (ph.enabled ? `<button type="button" class="linkbtn" data-phone="disable">Turn off iPhone sync</button>` : "");
    $("#connApps").innerHTML = connCard({id: "stravaCard", icon: "run", title: "Strava" + (st.athlete ? ` · ${st.athlete}` : ""), ok: st.connected, state: st.connected ? "connected" : st.state === "needs_reconnect" ? "reconnect" : "off", text: esc(st.text) + (st.last_error && !st.connected ? ` <span style="color:var(--warn-ink)">${esc(st.last_error)}</span>` : ""), acts: sActs})
      + connCard({icon: "heart", title: "Apple Health (iPhone)", ok: he.connected, state: he.connected ? "connected" : "off", text: esc(he.text) + (ph.enabled ? ` iPhone sync is on.` : ""), acts: hActs});
  }
}
$("#paneHealth").addEventListener("click", async e => {
  const c = e.target.closest("[data-cpost]"), sv = e.target.closest("[data-strava]"), ph = e.target.closest("[data-phone]");
  if (!c && !sv && !ph) return;
  const btn = c || sv || ph; btn.disabled = true;
  const card = btn.closest(".conn"), msg = card?.querySelector(".cmsg");
  if (msg) msg.innerHTML = `<span class="spin"></span>&nbsp; One moment…`;
  try {
    if (c) {
      const j = await postJSON(c.dataset.cpost, c.dataset.cpost.endsWith("/disconnect") ? {remove_future: false} : {});
      const sy = j.sync || j;
      if (msg) msg.textContent = j.ok === false ? (j.reason || "That didn't work.") : sy.created != null ? `Done — ${sy.created} added, ${sy.updated || 0} updated in your “Alibi” calendar.` : "";
    } else if (sv) {
      const j = await postJSON(sv.dataset.strava === "sync" ? "/api/strava/sync" : "/api/strava/disconnect", {});
      if (msg) msg.textContent = sv.dataset.strava === "sync" ? (j.error ? j.error : `${(j.added || []).length ? (j.added || []).length + " new run(s) found." : "No new runs."}`) : "Disconnected.";
      refreshSlow();
    } else await postJSON(`/api/phone-sync/${ph.dataset.phone}`, {});
    setTimeout(renderConnections, c || ph ? 300 : 2200);
  } catch (err) { if (msg) msg.textContent = `That didn't work: ${err.message}`; btn.disabled = false; }
});
$("#paneHealth").addEventListener("change", async e => {
  const t = e.target.closest("[data-calset]"); if (!t) return;
  try { await postJSON("/api/calendar/settings", {[t.dataset.calset]: t.checked}); } catch {}
});
/* ---------- setup: look and feel (theme via window.AlibiTheme; Quiet lobster is read by pinch-wire.js) ---------- */
(function prefs() {
  const pane = $("#paneHealth"), anchor = $("#rerunOnb")?.closest(".dsec");
  if (!pane || $("#prefs")) return;
  const quietOn = () => { try { return localStorage.getItem("alibi.quiet") === "1"; } catch { return false; } };
  const themeNow = () => window.AlibiTheme ? AlibiTheme.get() : (document.documentElement.dataset.theme || "system");
  const wrap = document.createElement("div");
  wrap.innerHTML = `<div class="dsec"><h3>Look and feel</h3></div>
    <div class="prefs" id="prefs">
      <div class="pref"><div><b id="themeLbl">Theme</b><p>Dark is the stage. System follows your Mac.</p></div>
        <div class="seg" role="radiogroup" aria-labelledby="themeLbl">${["system", "dark", "light"].map(m => `<button type="button" role="radio" data-theme-set="${m}" aria-checked="false">${m[0].toUpperCase() + m.slice(1)}</button>`).join("")}</div></div>
      <div class="pref"><div><b id="quietLbl">Quiet lobster</b><p>Pinch keeps its poses and lines, but skips the waves and confetti.</p></div>
        <label class="toggle"><input type="checkbox" role="switch" id="quietLobster" aria-labelledby="quietLbl"></label></div>
    </div>`;
  [...wrap.children].forEach(el => pane.insertBefore(el, anchor || null));
  const sync = () => {
    const t = themeNow();
    pane.querySelectorAll("[data-theme-set]").forEach(b => b.setAttribute("aria-checked", String(b.dataset.themeSet === t)));
    $("#quietLobster").checked = quietOn();
  };
  pane.querySelector(".seg").addEventListener("click", e => {
    const b = e.target.closest("[data-theme-set]"); if (!b) return;
    if (window.AlibiTheme) AlibiTheme.set(b.dataset.themeSet);
    else { const m = b.dataset.themeSet; if (m === "system") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = m; }
    sync();
  });
  pane.querySelector(".seg").addEventListener("keydown", e => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const bs = [...pane.querySelectorAll("[data-theme-set]")], i = bs.findIndex(b => b.getAttribute("aria-checked") === "true");
    const n = bs[(i + (e.key === "ArrowRight" ? 1 : bs.length - 1)) % bs.length]; n.click(); n.focus(); e.preventDefault();
  });
  $("#quietLobster").addEventListener("change", e => { try { e.target.checked ? localStorage.setItem("alibi.quiet", "1") : localStorage.removeItem("alibi.quiet"); } catch {} });
  document.addEventListener("alibi:theme", sync);
  sync();
})();
$("#rerunOnb").addEventListener("click", async () => { closeLayer("drawer"); await postJSON("/api/onboarding/reset", {}).catch(() => {}); startOnboarding(true); });

/* ---------- setup: habits (plain words) ---------- */
let habitsCfg = null, habModel = [];
async function loadHabits() {
  try { habitsCfg = await api("/api/habits"); } catch { return; }
  renderChips(habitsCfg.habits, document.body.classList.contains("live"));
}
function modelFromCfg() {
  habModel = Object.entries(habitsCfg?.habits || {}).map(([k, h]) => ({key: k, isNew: false, h: JSON.parse(JSON.stringify({...h, aliases: (h.aliases || []).join(", ")}))}));
}
function habCard(m, i) {
  const h = m.h, src = h.source, v = habView[m.key] || {};
  const label = h.label || h.display || v.label || (m.key ? hname(m.key) : "");
  const num = (f, lab, u, val, step = 1) => `<label><span>${lab}</span><span class="unit" data-u="${u}"><input class="fld" type="number" inputmode="decimal" min="0" step="${step}" data-f="${f}" value="${esc(val ?? "")}"></span></label>`;
  const check = MOD_TO_CHECK[h.modality] || h.check || "camera";
  const top = `<div class="habtop"><span class="hemoji" aria-hidden="true">${ico(src === "strava" ? "run" : src === "health" ? "heart" : check === "screen" ? "laptop" : "camera")}</span>
      <div class="hn"><input class="fld" data-f="label" placeholder="Name, e.g. Guitar" value="${esc(label)}" aria-label="Habit name"></div>
      <button class="del" type="button" data-del="${i}" aria-label="Delete ${esc(label || "new habit")}">Delete</button></div>`;
  let body;
  if (src === "strava") body = `<div class="howtxt">Checked by Strava — runs count on their own.</div><div class="hgrid" style="margin-top:12px">${num("weekly_sessions", "Runs a week", "runs", h.weekly_sessions)}${num("min_km", "Counts from", "km", h.min_km, 0.5)}</div>`;
  else if (src === "health") { const M = METRIC[h.metric] || ["", "", 1]; body = `<div class="howtxt">Checked by Apple Health — your iPhone sends it each night.</div><div class="hgrid" style="margin-top:12px">${num("daily_target", "Daily goal", M[0], h.daily_target, M[2])}</div>`; }
  else body = `<span class="flabel">How should Alibi check it?</span><div class="seg3" role="group">${CHECKS.map(([c, t]) => `<button type="button" data-check="${c}" aria-pressed="${c === check}">${t}</button>`).join("")}</div>
      <div class="howtxt">${esc(v.how && MOD_TO_CHECK[h.modality] === v.check ? photoFix(v.how) : ({camera: `A photo every minute while you're at it. ${photoWhere()}`.trim(), screen: "Alibi notes which app or website is in front — nothing else.", both: "A minute counts if the camera or your screen shows you at it."})[check])}</div>
      <div class="hgrid" style="margin-top:14px">${num("default_min", "Usual length", "min", h.default_min)}${num("weekly_target_min", "Weekly goal", "min", h.weekly_target_min, 5)}</div>`;
  const sched = h.schedule || [];
  const when = src === "health" ? "" : `<span class="flabel">When? <small>— Alibi reminds you, and it shows on your Today list</small></span>
      <div class="scheds">${sched.length ? schedRows(sched, "s") : `<div class="howtxt" style="margin:0 0 6px">No set time yet.</div>`}</div>
      <button type="button" class="ghostbtn" data-sadd="1" style="margin-top:6px">+ Add a time</button>
      ${sched.length ? `<div style="margin-top:12px"><label class="toggle"><input type="checkbox" data-f="calendar" ${h.calendar !== false ? "checked" : ""}>Show in Apple Calendar</label></div>` : ""}`;
  const details = src ? "" : `<details class="techd"><summary>Details</summary><div class="hgrid" style="margin-top:8px">
        <label class="wide"><span>Other words for it</span><input class="fld" data-f="aliases" value="${esc(h.aliases)}" placeholder="sketch, draw, art" spellcheck="false"></label>
        <label class="wide"><span>What it looks like when you're doing it</span><textarea class="fld" rows="2" data-f="on_task_looks_like" placeholder="e.g. hands on a guitar">${esc(h.on_task_looks_like || "")}</textarea></label></div></details>`;
  return `<div class="hab${m.isNew ? " new" : ""}" data-i="${i}">${top}${body}${when}${details}<div class="herr"></div></div>`;
}
function syncSched(card) { const m = habModel[+card.dataset.i]; m.h.schedule = readSched(card, "s"); }
function renderHabitsEd() {
  // The "Your habits" sheet (habits.js) is the editor now; this tab points at it. The form below stays as the fallback.
  if (window.AlibiHabits) {
    const hs = habitsCfg?.habits || {}, n = Object.keys(hs).length;
    const tot = Object.values(hs).reduce((a, h) => a + (h.schedule || []).reduce((b, r) => b + (r.days || []).length * (+r.min || 0), 0), 0);
    $("#habitsEd").innerHTML = `<div class="conn hsum"><div class="ci" aria-hidden="true">${ico("calendar")}</div><div><h4><span>${n} habit${n === 1 ? "" : "s"}</span></h4>
      <p>${tot ? `${esc(tot >= 60 ? `${Math.floor(tot / 60)}h${tot % 60 ? " " + (tot % 60) + "m" : ""}` : tot + " min")} planned a week. Times, length and how each one is checked.` : "No set times yet."}</p></div>
      <div class="cacts"><button type="button" class="primary" data-openhabits="1">Open habits</button></div></div>`;
    $("#addHabit").hidden = true;
    return;
  }
  $("#habitsEd").innerHTML = habModel.length ? habModel.map(habCard).join("") : `<div class="quiet">No habits yet. Add one below.</div>`;
}
function setMsg(t, cls = "") { const m = $("#saveMsg"); m.textContent = t; m.className = "msg " + cls; habDirty = /unsaved|fix|keep/.test(t); updateFoot(); }
$("#habitsEd").addEventListener("input", e => {
  const card = e.target.closest(".hab"); if (!card) return;
  const m = habModel[+card.dataset.i], f = e.target.dataset.f;
  if (e.target.dataset.sf) syncSched(card);
  else if (f === "calendar") m.h.calendar = e.target.checked;
  else if (f) m.h[f] = e.target.value;
  e.target.classList.remove("bad"); card.classList.remove("err"); card.querySelector(".herr").textContent = "";
  setMsg("unsaved changes");
});
$("#habitsEd").addEventListener("click", e => {
  if (e.target.closest("[data-openhabits]")) { closeLayer("drawer"); return openHabits(); }
  const card = e.target.closest(".hab"); if (!card) return;
  const m = habModel[+card.dataset.i];
  const day = e.target.closest("[data-day]");
  if (day) { day.setAttribute("aria-pressed", day.getAttribute("aria-pressed") !== "true"); syncSched(card); setMsg("unsaved changes"); return; }
  const ck = e.target.closest("[data-check]");
  if (ck) { m.h.modality = CHECK_TO_MOD[ck.dataset.check]; syncSchedSafe(card); renderHabitsEd(); setMsg("unsaved changes"); return; }
  if (e.target.closest("[data-sadd]")) { syncSchedSafe(card); m.h.schedule = [...(m.h.schedule || []), {days: ["mon","wed","fri"], at: "19:00", min: +m.h.default_min || 25}]; if (m.h.calendar == null) m.h.calendar = true; renderHabitsEd(); setMsg("unsaved changes"); return; }
  const sd = e.target.closest("[data-sdel]");
  if (sd) { syncSchedSafe(card); m.h.schedule.splice(+sd.dataset.sdel, 1); renderHabitsEd(); setMsg("unsaved changes"); return; }
  const d = e.target.closest("[data-del]"); if (!d) return;
  card.style.opacity = "0"; card.style.transform = "translateX(12px)";
  setTimeout(() => { habModel.splice(+d.dataset.del, 1); renderHabitsEd(); setMsg("unsaved changes — Undo puts it back"); }, 200);
});
function syncSchedSafe(card) { if (card.querySelector(".srow")) syncSched(card); }
$("#addHabit").addEventListener("click", () => {
  habModel.push({key: "", isNew: true, h: {label: "", modality: "physical", default_min: 25, weekly_target_min: 75, aliases: "", on_task_looks_like: "", schedule: [], calendar: true}});
  renderHabitsEd();
  const cards = $("#habitsEd").querySelectorAll(".hab"), last = cards[cards.length - 1];
  last.scrollIntoView({behavior: "smooth", block: "center"});
  setTimeout(() => last.querySelector('[data-f="label"]').focus({preventScroll: true}), 250);
  setMsg("unsaved changes");
});
$("#revertHabits").textContent = "Undo changes";
$("#revertHabits").addEventListener("click", () => { modelFromCfg(); renderHabitsEd(); setMsg(""); });
function cardErr(i, text, field) {
  const card = $("#habitsEd").querySelector(`.hab[data-i="${i}"]`); if (!card) return false;
  card.classList.add("err"); card.querySelector(".herr").textContent = text;
  if (field) card.querySelector(`[data-f="${field}"]`)?.classList.add("bad");
  return true;
}
$("#saveHabits").addEventListener("click", async () => {
  $("#habitsEd").querySelectorAll(".hab.err").forEach(c => { c.classList.remove("err"); c.querySelector(".herr").textContent = ""; });
  $("#habitsEd").querySelectorAll(".fld.bad").forEach(f => f.classList.remove("bad"));
  $("#habitsEd").querySelectorAll(".hab").forEach(c => syncSchedSafe(c));
  let bad = null; const seen = new Set(), out = {};
  habModel.forEach((m, i) => {
    const h = m.h, label = String(h.label || h.display || "").trim();
    const fail = (t, f) => { cardErr(i, t, f); bad = bad ?? i; };
    if (!label && m.isNew) return fail("Give the habit a name.", "label");
    let key = m.isNew ? slugify(label) : m.key;
    if (m.isNew) { const taken = new Set(habModel.filter(x => !x.isNew).map(x => x.key)); let n = 2; const base = key; while (seen.has(key) || taken.has(key)) key = `${base}_${n++}`; }
    if (seen.has(key)) return fail(`There's already a habit called “${label}”.`, "label");
    seen.add(key);
    const sched = (h.schedule || []);
    if (!schedOk(sched)) return fail("Each time needs at least one day, a time and a length.");
    const base = {...h}; delete base.aliases;
    const extra = sched.length ? {schedule: sched, calendar: h.calendar !== false} : {schedule: [], calendar: false};
    if (h.source === "strava") { out[key] = {...base, ...extra, label: label || base.label, weekly_sessions: +h.weekly_sessions || 0, min_km: +h.min_km || 0}; return; }
    if (h.source === "health") { if (!(+h.daily_target > 0)) return fail("The daily goal needs to be more than 0.", "daily_target"); out[key] = {...base, display: label || base.display, daily_target: +h.daily_target}; if (sched.length) Object.assign(out[key], {schedule: sched, calendar: h.calendar !== false}); else { delete out[key].schedule; delete out[key].calendar; } if (label) out[key].label = label; return; }
    if (!(+h.default_min >= 1)) return fail("Usual length needs to be at least 1 minute.", "default_min");
    if (!(+h.weekly_target_min >= 0)) return fail("Weekly goal can't be negative.", "weekly_target_min");
    delete base.check;
    out[key] = {...base, ...extra, label, modality: h.modality || "physical", default_min: Math.round(+h.default_min), weekly_target_min: Math.round(+h.weekly_target_min || 0),
                aliases: String(h.aliases || "").split(",").map(a => a.trim()).filter(Boolean), on_task_looks_like: String(h.on_task_looks_like || "").trim() || label.toLowerCase()};
  });
  if (bad != null) { setMsg("fix the highlighted habit", "bad"); $("#habitsEd").querySelector(`.hab[data-i="${bad}"]`)?.scrollIntoView({behavior: "smooth", block: "center"}); return; }
  if (!Object.keys(out).length) { setMsg("keep at least one habit", "bad"); return; }
  const btn = $("#saveHabits"); btn.disabled = true; setMsg("saving…");
  try {
    const r = await fetch("/api/habits", {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({habits: out})});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      const d = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail || r.status);
      const k = (/habit name '([^']+)'/.exec(d) || /^([a-z][a-z0-9_]*):/.exec(d) || [])[1];
      const i = k != null ? habModel.findIndex(m => m.key === k || slugify(m.h.label) === k) : -1;
      if (i < 0 || !cardErr(i, d.replace(/^[a-z0-9_]+: /, ""))) setMsg(d, "bad"); else setMsg("fix the highlighted habit", "bad");
      return;
    }
    habitsCfg = j; await loadView(); modelFromCfg(); renderHabitsEd(); renderChips(j.habits, document.body.classList.contains("live"));
    setMsg("Saved. Your plan and calendar update in a moment.", "good");
    refreshSlow(); setTimeout(loadPlan, 1500);
  } catch { setMsg("Alibi isn't running — couldn't save", "bad"); }
  finally { btn.disabled = false; }
});
async function openSetup(tab) {
  openLayer("drawer");
  $("#checks").innerHTML = `<div class="quiet"><span class="spin"></span>&nbsp; Checking…</div>`;
  setMsg(""); setTab(typeof tab === "string" ? tab : "Health");
  const [h] = await Promise.all([loadHealth(), loadHabits(), loadView(), renderConnections()]);
  renderChecks(h); modelFromCfg(); renderHabitsEd();
}
$("#setupBtn").addEventListener("click", () => openSetup());
$("#recheck").addEventListener("click", async () => { $("#checks").style.opacity = ".5"; renderChecks(await loadHealth()); renderConnections(); $("#checks").style.opacity = ""; });

/* ---------- setup: your data ---------- */
async function loadData() {
  const [runs, days] = await Promise.allSettled([api("/api/strava/runs?days=30"), api("/api/apple-health/days?days=14")]);
  const minKm = Object.values(habitsCfg?.habits || {}).find(h => h.source === "strava")?.min_km || 0;
  const rs = runs.status === "fulfilled" ? runs.value.runs || [] : [];
  $("#dataRuns").innerHTML = rs.length ? `<table class="dtable"><thead><tr><th>Day</th><th>Run</th><th class="n">Distance</th><th class="n">Time</th><th>Counts?</th></tr></thead><tbody>${rs.map(x => {
    const ok = x.distance_km >= minKm;
    return `<tr><td>${esc(dayT(typeof x.start_date === "number" ? x.start_date : Date.parse(x.start_date) / 1000))}</td><td>${x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name || "Run")}</a>` : esc(x.name || "Run")}<small>${esc(x.sport_type || "")}${x.elevation_m ? ` · ${Math.round(x.elevation_m)} m climb` : ""}</small></td><td class="n">${esc(x.distance_km)} km</td><td class="n">${esc(Math.round(x.moving_min || 0))} min</td><td class="${ok ? "ok" : "no"}">${minKm ? (ok ? "✓ yes" : `too short (needs ${minKm} km)`) : "—"}</td></tr>`;
  }).join("")}</tbody></table>` : `<div class="quiet">No runs yet. ${esc(lastReport?.running?.strava?.connected ? "Runs from the last 30 days appear here." : "Connect Strava in the Connections tab and your runs appear here.")}</div>`;
  const ds = days.status === "fulfilled" ? days.value.days || [] : [];
  const hh = Object.entries(habitsCfg?.habits || {}).filter(([, h]) => h.source === "health");
  const tgt = m => hh.find(([, h]) => h.metric === m)?.[1].daily_target;
  const cellv = (m, v, f) => { if (v == null) return `<td class="n no">—</td>`; const t = tgt(m); return `<td class="n ${t != null ? (v >= t ? "ok" : "") : ""}">${f(v)}${t != null && v >= t ? " ✓" : ""}</td>`; };
  $("#dataHealth").innerHTML = ds.length ? `<table class="dtable"><thead><tr><th>Day</th><th class="n">Steps</th><th class="n">Sleep</th><th class="n">Mindful</th><th class="n">Workouts</th></tr></thead><tbody>${ds.map(d => {
    const [Y, M, D] = d.date.split("-").map(Number);
    return `<tr><td>${esc(new Date(Y, M - 1, D).toLocaleDateString(undefined, {weekday: "short", day: "numeric", month: "short"}))}</td>${cellv("steps", d.steps, v => fmtN(v))}${cellv("sleep_h", d.sleep_h, v => `${Math.floor(v)} h ${pad(Math.round(v % 1 * 60))}`)}${cellv("mindful_min", d.mindful_min, v => `${Math.round(v)} min`)}${cellv("workout_min", d.workout_min, v => `${Math.round(v)} min`)}</tr>`;
  }).join("")}</tbody></table><div class="howtxt">✓ means you hit the goal for a habit that day.</div>` : `<div class="quiet">Nothing from your iPhone yet. Set up the nightly Shortcut from the Connections tab — it takes about 5 minutes.</div>`;
}
