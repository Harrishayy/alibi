/* onboarding.js: first-run welcome wizard. Classic script; load order core, now, week, sessions, setup, onboarding, boot. */
/* ---------- first-run welcome ---------- */
let onb = null, onbPinch = null;
const TPL_ICON = {camera: "camera", screen: "laptop", both: "eye", strava: "run", health: "heart"};
const tplIcon = t => ico(TPL_ICON[t.check] || "sparkle", 20);
// One Pinch per view. Welcome: 160px and "hello" (Mascot.md). Practice: 64px, idle. Size comes from the host's data-size.
function onbPinchMount() {
  if (onbPinch) { try { onbPinch.destroy(); } catch {} onbPinch = null; }
  const host = $("#onbIn").querySelector(".onb-pinch");
  if (!host || !window.AlibiPinch) return;
  try {
    const size = +host.dataset.size || 160;
    onbPinch = AlibiPinch.mount(host, {size, mood: "idle", theme: "auto"});
    let quiet = false; try { quiet = localStorage.getItem("alibi.quiet") === "1"; } catch {}
    if (!quiet && host.dataset.hello) setTimeout(() => onbPinch && onbPinch.play("hello").catch?.(() => {}), 320);
  } catch { onbPinch = null; }
}
// Pinch's lines (at most 12 words, Voice.md). The welcome one is the canonical "hello" line.
const ONB_SAY = {welcome: "I'm Pinch. You say what you'll do; I check.", practice: "Two minutes. Do a bit, then drift. I'll notice."};
// Finishing: the dashboard's own Pinch says "connected" once the overlay has gone.
function onbFinishPinch() {
  setTimeout(() => { try { window.AlibiPinchWire?.ensure?.(); window.AlibiPinchWire?.play?.("connected"); } catch {} }, 420);
}
const ONB_STEPS = ["welcome","habits","schedule","connect","practice"];
async function startOnboarding(force) {
  let st, tp, ws;
  try { [st, tp, ws] = await Promise.all([api("/api/onboarding"), api("/api/onboarding/templates"), lastState || api("/api/state").catch(() => null)]); } catch { return; }
  if (!force && !st.needs_onboarding) return;
  const replay = !!(st.replay || (force && (st.habits || []).length));        // tour again: add to habits, never wipe them
  const haveH = {}; (st.habits || []).forEach(h => { const id = h.template || h.key; if (id !== "custom" && !haveH[id]) haveH[id] = h; });
  const have = new Set(Object.keys(haveH));
  onb = {st, tpl: tp.templates || [], step: ONB_STEPS.includes(st.step) && st.step !== "connect" && st.step !== "practice" ? st.step : "welcome", picked: new Set(replay ? (tp.templates || []).filter(t => have.has(t.id)).map(t => t.id) : st.picked || []), names: {}, sched: {}, cal: true, busy: false, replay, ws: ws ? {witness: ws.witness, witness_label: ws.witness_label} : null};
  if (replay) for (const id of onb.picked) if ((haveH[id]?.schedule || []).length) onb.sched[id] = haveH[id].schedule.map(x => ({...x}));   // keep their plan
  if (onb.step !== "welcome" && !onb.picked.size) onb.step = "welcome";
  if (onb.step === "schedule") onb.step = "habits";
  $("#onb").classList.add("show"); $("#onb").setAttribute("aria-hidden", "false"); document.body.style.overflow = "hidden";
  renderOnb();
}
function closeOnb() { if (onbPinch) { try { onbPinch.destroy(); } catch {} onbPinch = null; } $("#onb").classList.remove("show"); $("#onb").setAttribute("aria-hidden", "true"); document.body.style.overflow = ""; onb = null; }
const tplById = id => onb.tpl.find(t => t.id === id) || {};
function renderOnb() {
  const i = ONB_STEPS.indexOf(onb.step), meta = (onb.st.steps || []).find(x => x.id === onb.step) || {};
  const n = ONB_STEPS.length;
  const prog = `<div class="onbprog"><span class="n">Step ${i + 1} of ${n}</span><span class="onbdots" aria-hidden="true">${ONB_STEPS.map((_, j) => `<i class="${j === i ? "cur" : j < i ? "on" : ""}"></i>`).join("")}</span></div>`;
  const head = (title, lead) => `<header class="onbhead"><h1 id="onbTitle">${esc(title)}</h1>${lead ? `<p class="lead">${esc(lead)}</p>` : ""}</header>`;
  let body = "";
  if (onb.step === "welcome") body = `<div class="onbhero"><div class="onb-pinch" data-size="160" data-hello="1" aria-hidden="true"></div>
    <h1 id="onbTitle">${esc(meta.title || "Welcome to Alibi")}</h1>
    <p class="onb-say">${esc(ONB_SAY.welcome)}</p></div>
    <ul class="onblist" aria-label="What Alibi checks">
    <li><span class="e" aria-hidden="true">${ico("camera")}</span><div><b>Desk habits</b><span>Drawing, reading, an instrument: a photo every minute while you're at it.${onb.ws && photoWhere(onb.ws) ? " " + photoWhere(onb.ws) : ""}</span></div></li>
    <li><span class="e" aria-hidden="true">${ico("laptop")}</span><div><b>Computer habits</b><span>Coding or studying: Alibi notes which app or website is in front. Nothing is recorded.</span></div></li>
    <li><span class="e" aria-hidden="true">${ico("run")}</span><div><b>Runs, steps &amp; sleep</b><span>Strava and Apple Health count on their own — nothing to start.</span></div></li></ul>`;
  else if (onb.step === "habits") body = `${head(meta.title || "What do you want to do more of?", onb.replay ? "Your current habits are ticked and stay as they are, history included. Tick anything you'd like to add." : meta.text || "Pick a few.")}
    <div class="tgrid">${onb.tpl.map(t => { const on = onb.picked.has(t.id); return `<div class="tcard" role="button" tabindex="0" data-tpl="${esc(t.id)}" aria-pressed="${on}">
      <span class="e" aria-hidden="true">${tplIcon(t)}</span><b>${esc(t.title)}</b><span class="tk" aria-hidden="true">${ico("check", 16)}</span>
      <span>${esc(photoFix(t.blurb, onb.ws))}</span><span class="via">Checked by: ${esc(photoFix(t.check_text, onb.ws))}</span>
      ${on && t.ask_name ? `<input class="fld" data-name="${esc(t.id)}" placeholder="${esc(t.ask_name)}" value="${esc(onb.names[t.id] || "")}" aria-label="${esc(t.ask_name)}">` : ""}</div>`; }).join("")}</div>`;
  else if (onb.step === "schedule") {
    const ps = [...onb.picked].map(tplById);
    body = `${head(meta.title || "When will you do them?", meta.text || "")}
    ${ps.map(t => {
      const sc = onb.sched[t.id] ?? (t.schedule || []).map(x => ({...x}));
      const nm = onb.names[t.id] || t.label || t.title;
      if (t.check === "health") return `<div class="pickrow"><h3><span class="e" aria-hidden="true">${tplIcon(t)}</span>${esc(t.title)}</h3><div class="howtxt">Checked automatically each night from your iPhone — no set time needed.</div></div>`;
      return `<div class="pickrow" data-tid="${esc(t.id)}"><h3><span class="e" aria-hidden="true">${tplIcon(t)}</span>${esc(nm)}</h3><div class="howtxt">${esc(photoFix(t.how, onb.ws))}</div>
        <div class="scheds">${schedRows(sc, "s")}</div>${sc.length ? "" : `<div class="howtxt">No set time — you'll start it whenever you like.</div>`}
        <button type="button" class="addtime" data-oadd="${esc(t.id)}">${ico("plus", 16)}<span>Add a time</span></button></div>`;
    }).join("")}
    <div class="calask"><div><b>Put these in Apple Calendar?</b><p>Alibi makes its own calendar called “Alibi” and only touches that one. After each session, the event shows how it went. You'll be asked for permission on the next step.</p></div>
      <label class="toggle"><input type="checkbox" id="onbCal" ${onb.cal ? "checked" : ""}>${onb.cal ? "Yes" : "No"}</label></div>`;
  } else if (onb.step === "connect") {
    const list = [...(onb.st.connect || [])];
    const hasSched = Object.values(onb.sched).some(sc => sc.length) || [...onb.picked].some(id => !onb.sched[id] && (tplById(id).schedule || []).length && tplById(id).check !== "health");
    if (onb.cal && hasSched) list.unshift({id: "calendar", title: "Apple Calendar", why: "So your plan shows up on your Mac, iPhone and Watch. Your Mac will ask for permission — choose “Allow Full Access” so Alibi can update events with how each session went.", button: "Add to Apple Calendar", skip: "Not now"});
    if ([...onb.picked].some(id => tplById(id).check === "health") && !list.some(x => x.id === "health")) list.push({id: "health", title: "Apple Health on your iPhone", why: "A small Shortcut on your iPhone sends steps, sleep and mindful minutes to Alibi each night. Setup takes about 5 minutes and opens in a new tab.", button: "Set up iPhone", skip: "Later"});
    const ICO = {camera: "camera", screen: "laptop", strava: "run", health: "heart", calendar: "calendar"};
    body = `${head(meta.title || "Let Alibi check", meta.text || "Each one is optional.")}
      ${list.length ? list.map(c => connCard({id: "oc-" + c.id, icon: ICO[c.id] || "eye", title: c.title, ok: false, state: "", text: esc(photoFix(c.why, onb.ws)), acts: `<button type="button" class="primary" data-oconn="${esc(c.id)}">${esc(c.button)}</button>`})).join("") : `<p class="lead">Nothing to connect for these habits.</p>`}`;
  } else if (onb.step === "practice") {
    body = `${head(meta.title || "Try it once", "")}
      <div class="onbmeet"><div class="onb-pinch" data-size="64" aria-hidden="true"></div><p class="onb-say">${esc(ONB_SAY.practice)}</p></div>
      <ol class="onblist onblist--num" aria-label="How the practice goes"><li><span class="e" data-num>1</span><div><b>Start</b><span>A 2-minute session begins. The notch at the top of your screen shows the timer.</span></div></li>
      <li><span class="e" data-num>2</span><div><b>Do a bit, then drift</b><span>Do the habit for a minute, then pick up your phone. Alibi will nudge you.</span></div></li>
      <li><span class="e" data-num>3</span><div><b>See how it went</b><span>You get a score with the photos Alibi took. Tap any it got wrong to fix it.</span></div></li></ol>`;
  }
  const enter = onb.shown !== onb.step; onb.shown = onb.step;
  const keep = $("#onb").scrollTop;
  $("#onbIn").innerHTML = `<div class="onbtop"><span class="wordmark" aria-label="Alibi">ALIBI</span>${prog}</div><div class="onbstep onbstep--${onb.step}${enter ? " enter" : ""}">${body}</div>`;
  $("#onbIn").dataset.step = $("#onb").dataset.step = onb.step;
  onbPinchMount();
  $("#onbBack").style.display = i ? "" : "none";
  $("#onbNext").textContent = onb.step === "welcome" ? (meta.button || "Get started") : onb.step === "practice" ? (meta.button || "Start 2-minute practice") : onb.step === "connect" ? "Next" : "Next";
  $("#onbSkip").textContent = onb.step === "practice" ? (meta.skip || "Skip — go to my dashboard") : onb.step === "connect" ? "Skip for now" : "";
  $("#onbSkip").hidden = !$("#onbSkip").textContent;
  onbMsg(onb.step === "habits" ? (onb.picked.size ? `${onb.picked.size} picked` : "Pick at least one")
    : onb.step === "welcome" ? "This takes about two minutes. Everything can be changed later." : "");
  $("#onb").scrollTop = enter ? 0 : keep;
  requestAnimationFrame(onbEdge);
}
function onbEdge() { const o = $("#onb"); o.toggleAttribute("data-under", o.scrollTop + o.clientHeight < o.scrollHeight - 2); }
$("#onb").addEventListener("scroll", onbEdge, {passive: true});
addEventListener("resize", () => { if (onb) onbEdge(); });
function onbMsg(t, bad) { $("#onbMsg").textContent = t; $("#onbMsg").className = "msg" + (bad ? " bad" : ""); }
function onbReadSched() { $("#onbIn").querySelectorAll(".pickrow[data-tid]").forEach(r => { onb.sched[r.dataset.tid] = readSched(r, "s"); }); }
$("#onbIn").addEventListener("click", async e => {
  if (!onb) return;
  const t = e.target.closest("[data-tpl]");
  if (t && !e.target.closest("input")) { const id = t.dataset.tpl; onb.picked.has(id) ? onb.picked.delete(id) : onb.picked.add(id); renderOnb(); const inp = $("#onbIn").querySelector(`[data-name="${id}"]`); (inp || $("#onbIn").querySelector(`[data-tpl="${id}"]`))?.focus({preventScroll: true}); return; }
  const day = e.target.closest("[data-day]"); if (day) { day.setAttribute("aria-pressed", day.getAttribute("aria-pressed") !== "true"); onbReadSched(); return; }
  const add = e.target.closest("[data-oadd]"); if (add) { onbReadSched(); const t2 = tplById(add.dataset.oadd); (onb.sched[t2.id] = onb.sched[t2.id] || []).push({days: ["mon","wed","fri"], at: "19:00", min: t2.minutes || 25}); renderOnb(); return; }
  const sd = e.target.closest("[data-sdel]"); if (sd) { onbReadSched(); const tid = sd.closest(".pickrow").dataset.tid; onb.sched[tid].splice(+sd.dataset.sdel, 1); renderOnb(); return; }
  const oc = e.target.closest("[data-oconn]"); if (oc) return onbConnect(oc.dataset.oconn, oc);
});
$("#onbIn").addEventListener("keydown", e => { const t = e.target.closest("[data-tpl]"); if (t && e.target === t && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); t.click(); } });
$("#onbIn").addEventListener("input", e => {
  if (e.target.dataset.name) onb.names[e.target.dataset.name] = e.target.value;
  if (e.target.dataset.sf) onbReadSched();
  if (e.target.id === "onbCal") { onb.cal = e.target.checked; e.target.parentElement.lastChild.nodeValue = onb.cal ? "Yes" : "No"; }
});
async function onbConnect(id, btn) {
  const card = btn.closest(".conn"), msg = card.querySelector(".cmsg");
  const done = (t, ok) => { msg.innerHTML = t; if (ok) { card.classList.add("ok"); btn.textContent = "✓ Done"; btn.className = "ghostbtn"; } btn.disabled = !!ok; };
  btn.disabled = true; msg.innerHTML = `<span class="spin"></span>&nbsp; One moment…`;
  try {
    if (id === "calendar") { const j = await postJSON("/api/calendar/connect", {}); const s = j.status || {}; done(esc(j.ok ? `Added — ${j.sync?.created ?? 0} sessions are in your “Alibi” calendar.` : (s.message || j.reason || "Calendar wasn't allowed.")), j.ok); if (!j.ok && s.action) { btn.textContent = s.action.label; btn.disabled = false; btn.dataset.oconn = s.action.post.endsWith("open-settings") ? "calsettings" : "calendar"; } }
    else if (id === "calsettings") { await postJSON("/api/calendar/open-settings", {}); done("System Settings is open. Turn on Alibi under Calendars, then come back and tap again.", false); btn.dataset.oconn = "calendar"; btn.textContent = "Check again"; }
    else if (id === "camera" || id === "screen") { const h = await api("/api/health"); const c = h.checks.find(x => x.key === (id === "camera" ? "camera" : "windows")) || {}; done(esc(c.detail || "") + (c.ok ? "" : c.fix ? ` ${esc(c.fix)}.` : ""), c.ok); if (!c.ok) { btn.textContent = "Check again"; } }
    else if (id === "strava") { window.open("/strava/setup", "_blank", "noopener"); done("Strava setup opened in a new tab. Finish there, then come back — this updates on its own.", false); btn.textContent = "Open again"; btn.disabled = false; pollConn("strava", card, btn); }
    else if (id === "health") { window.open("/phone", "_blank", "noopener"); done("iPhone setup opened in a new tab. You can finish it later from Setup.", false); btn.textContent = "Open again"; btn.disabled = false; }
  } catch (err) { done(`That didn't work: ${esc(err.message)}`, false); btn.disabled = false; }
}
function pollConn(kind, card, btn) {
  let n = 0; const iv = setInterval(async () => {
    if (!onb || !card.isConnected || ++n > 120) return clearInterval(iv);
    try { const s = await api("/api/strava/status"); if (s.connected) { clearInterval(iv); card.classList.add("ok"); card.querySelector(".cmsg").textContent = s.text; btn.textContent = "✓ Connected"; btn.className = "ghostbtn"; btn.disabled = true; } } catch {}
  }, 3000);
}
$("#onbBack").addEventListener("click", () => { if (!onb) return; if (onb.step === "schedule") onbReadSched(); onb.step = ONB_STEPS[Math.max(0, ONB_STEPS.indexOf(onb.step) - 1)]; renderOnb(); });
$("#onbSkip").addEventListener("click", async () => {
  if (!onb) return;
  if (onb.step === "connect") { onb.step = "practice"; renderOnb(); return; }
  await postJSON("/api/onboarding/done", {}).catch(() => {}); closeOnb(); await refreshAll(); onbFinishPinch();
});
$("#onbNext").addEventListener("click", async () => {
  if (!onb || onb.busy) return;
  const step = onb.step, btn = $("#onbNext");
  if (step === "habits") {
    if (!onb.picked.size) return onbMsg("Pick at least one habit to continue.", true);
    const miss = [...onb.picked].map(tplById).find(t => t.ask_name && !String(onb.names[t.id] || "").trim());
    if (miss) { onbMsg(`${miss.ask_name} — type a name on the “${miss.title}” card.`, true); $("#onbIn").querySelector(`[data-name="${miss.id}"]`)?.focus(); return; }
  }
  if (step === "schedule") {
    onbReadSched();
    const bad = Object.entries(onb.sched).find(([, sc]) => !schedOk(sc));
    if (bad) return onbMsg(`${tplById(bad[0]).title}: each time needs a day, a time and a length.`, true);
    onb.busy = true; btn.disabled = true; onbMsg("Saving your habits…");
    const picks = [...onb.picked].map(id => { const t = tplById(id); const p = {template: id, calendar: onb.cal}; if (onb.names[id]) p.name = onb.names[id].trim(); if (t.check !== "health") p.schedule = onb.sched[id] ?? t.schedule ?? []; return p; });
    try { await postJSON("/api/onboarding/habits", {picks, replace: !onb.replay}); onb.st = await api("/api/onboarding"); }
    catch (err) { onb.busy = false; btn.disabled = false; return onbMsg(`Couldn't save: ${err.message}`, true); }
    onb.busy = false; btn.disabled = false;
  }
  if (step === "practice") {
    onb.busy = true; btn.disabled = true; onbMsg("Starting…");
    let j = null; try { j = await postJSON("/api/onboarding/practice", {}); } catch {}
    await postJSON("/api/onboarding/done", {}).catch(() => {});
    closeOnb(); await refreshAll(); onbFinishPinch();
    if (j?.reply) $("#convo").innerHTML = `<div class="line alibi"><span class="who">Alibi</span><span class="txt">${esc(j.reply)}</span></div>`;
    return;
  }
  onb.step = ONB_STEPS[ONB_STEPS.indexOf(step) + 1];
  postJSON("/api/onboarding/progress", {step: onb.step, picked: [...onb.picked]}).catch(() => {});
  renderOnb();
});
