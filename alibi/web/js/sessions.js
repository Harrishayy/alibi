/* sessions.js: sessions list + detail (contact sheet, reel, Fix a moment), reels + lightbox, correction popover + keyboard.
   Marks come from week.js (wkDot, wkPill, wkIcon). Classic script; load order core, now, week, sessions, setup, onboarding, boot. */
/* ---------- sessions ---------- */
const openSet = new Set(), sessHtml = new Map(), sessVerdict = new Map(), sessById = new Map();
let pendingPlay = null;
const sampleTip = l => { const n = cleanNote(l.note); return `${clockT(l.ts)} · ${wkWord(l.label)}${l.corrected_from ? ` · was ${wkWord(l.corrected_from).toLowerCase()}, fixed by you` : ""}${l.learned_from ? " · learned from your past fixes" : ""}${n ? ` · ${n}` : ""}`; };
const dayKey = s => s.day || localDate(new Date(s.started_at * 1000));
function whenLabel(s) {
  const k = dayKey(s), t = clockT(s.started_at);
  if (k === localDate()) return `Today ${t}`;
  const d = new Date(s.started_at * 1000);
  return Date.now() / 1000 - s.started_at < 6 * 86400 ? `${d.toLocaleDateString("en-GB", {weekday: "short"})} ${t}` : d.toLocaleDateString("en-GB", {day: "numeric", month: "short"});
}
function dotsAria(labels) {
  const n = {}; labels.forEach(l => { n[l.label] = (n[l.label] || 0) + 1; });
  return "One mark per check: " + Object.entries(n).map(([k, c]) => `${c} ${wkWord(k).toLowerCase()}`).join(", ");
}

function sessionHtml(s) {
  wkUid = (s.id % 100000) * 1000;   // hatch clip ids stay stable per session, so an unchanged row keeps its HTML (and its open popover)
  const labels = s.labels || [], live = !!s.live || (!s.verdict && !s.ended_at);
  const title = dispName(s.habit, s.label);
  const meta = live ? `${s.verified_min ?? 0} of ${s.declared_min ?? "—"} min seen so far`
    : `${s.verified_min ?? 0} of ${s.declared_min ?? "—"} min seen`;
  const byApp = !labels.length && s.windows && s.windows.length ? `<span class="sess-app">${wkIcon("laptop", 16)}<span>${esc(s.windows[0].title)} · ${pct(s.windows[0].share)}</span></span>` : "";
  const dots = labels.length ? `<span class="sess-dots" role="img" aria-label="${esc(dotsAria(labels))}">${labels.map(l => wkDot(l.label, 8, {hidden: true})).join("")}</span>` : byApp;
  const end = live ? `<span class="sess-live"><span class="sess-pulse" aria-hidden="true"></span>Live</span>` : wkPill(s.verdict);

  // detail: what Alibi says, the contact sheet as proof, the reel, Fix a moment, the facts
  const say = s.summary ? `<p class="sess-say">${esc(plain(s.summary))}</p>` : "";
  const why = s.score_line ? `<p class="sess-why">${esc(s.score_line)}</p>` : "";
  let hero = "";
  if (s.evidence_url) hero = `<figure class="sheet"><a href="${esc(s.evidence_url)}" target="_blank" rel="noopener" aria-label="Open the contact sheet for ${esc(title)}"><img loading="lazy" src="${esc(s.evidence_url)}" alt="Contact sheet: the photos Alibi took during ${esc(title)}"></a><figcaption class="veil"><span class="spin"></span>Cutting the reel…</figcaption></figure>`;
  else if (s.reel_url) hero = `<figure class="sheet"><video controls playsinline preload="metadata" src="${esc(s.reel_url)}" aria-label="Reel of ${esc(title)}"></video></figure>`;
  const reelBtn = labels.length || s.reel_url ? `<button class="al-btn al-btn--secondary al-btn--sm" type="button" data-reel="${s.id}">${wkIcon("film", 16)}${s.reel_url ? "Watch reel" : "Make reel"}</button>` : "";
  const fixedN = labels.filter(l => l.corrected_from).length;
  const fix = labels.length && !live ? `<div class="fixm">
      <div class="fixm-head"><span class="t-label">Fix a moment</span><span class="fixm-hint">${fixedN ? `${fixedN} fixed by you · ` : ""}Tap a check I got wrong.</span></div>
      <div class="fixm-strip"><div class="fixm-seg" role="toolbar" aria-label="Checks for ${esc(title)}">${labels.map((l, i) => `<button type="button" tabindex="${i === 0 ? 0 : -1}" class="sm${l.corrected_from ? " fixed" : ""}" data-sid="${s.id}" data-i="${i}" title="${esc(sampleTip(l))}" aria-label="Check at ${clockT(l.ts)}: ${esc(wkWord(l.label))}. Fix it">${wkDot(l.label, 12, {hidden: true})}</button>`).join("")}</div>
      <div class="axis"><span>${clockT(labels[0].ts)}</span><span>${clockT(labels[labels.length - 1].ts)}</span></div></div></div>` : "";
  const counts = LABELS.map(l => [l, labels.filter(x => x.label === l).length]).filter(x => x[1]);
  const parts = [s.camera_ratio != null ? `camera ${pct(s.camera_ratio)}` : "", s.screen_ratio != null ? `screen ${pct(s.screen_ratio)}` : "", s.coverage != null && s.coverage < 0.995 ? `happened ${pct(s.coverage)}` : ""].filter(Boolean).join(" · ");
  const facts = `<dl class="facts">
      <div><dt>When</dt><dd>${clockT(s.started_at)} to ${clockT(s.ended_at || s.ends_at)}${CHECK_WORD[s.modality] ? ` · ${esc(CHECK_WORD[s.modality])}` : ""}</dd></div>
      <div><dt>On task</dt><dd>${pct(s.on_task_ratio)}${parts ? ` · ${parts}` : ""}</dd></div>
      ${counts.length ? `<div><dt>Checks</dt><dd class="facts-dots">${counts.map(([l, n]) => `<span>${wkDot(l, 12, {hidden: true})}${esc(wkWord(l))} ${n}</span>`).join("")}</dd></div>` : ""}
      ${s.artefact ? `<div><dt>Artefact</dt><dd><a href="${esc(s.artefact)}" target="_blank" rel="noopener">${esc(s.artefact)}</a></dd></div>` : ""}
    </dl>`;
  const wins = s.windows && s.windows.length && typeof renderWindows === "function" ? `<div class="wins">${renderWindows(s.windows)}</div>` : "";
  const acts = reelBtn || s.evidence_url ? `<div class="sess-acts">${reelBtn}${s.evidence_url ? `<a class="al-btn al-btn--quiet al-btn--sm" href="${esc(s.evidence_url)}" target="_blank" rel="noopener">Open contact sheet</a>` : ""}</div>` : "";
  return `<li class="sess${live ? " is-live" : ""}" data-id="${s.id}" id="session-${s.id}">
    <button type="button" aria-expanded="false" aria-controls="sd-${s.id}">
      <span class="sess-when">${live ? "Now" : esc(whenLabel(s))}</span>
      <span class="sess-main"><span class="sess-head"><span class="sess-h">${esc(title)}</span><span class="sess-meta">${esc(meta)}</span></span>${dots}</span>
      <span class="sess-end">${end}<span class="chev" aria-hidden="true">${wkIcon("chevron-down", 16)}</span></span>
    </button>
    <div class="detail" id="sd-${s.id}" inert><div><div class="in">${say}${why}${hero}${fix}${acts}${facts}${wins}</div></div></div>
  </li>`;
}

// /api/state rows the list may not have yet: the live session leads (canvas "Now · Live") until its verdict lands,
// and the just-finished verdict joins at once instead of waiting for the next 15 s refresh.
let lastSessList = [], stateRowsKey = "", sessAll = false;
const SESS_FIRST = 8;
function withStateRows(list) {
  const st = typeof lastState !== "undefined" ? lastState : null, out = [...list];
  const rv = st && st.recent_verdict;
  if (rv && rv.id != null && rv.verdict && !out.some(s => s.id === rv.id)) {
    const i = out.findIndex(s => (s.started_at || 0) < (rv.started_at || 0));
    out.splice(i < 0 ? out.length : i, 0, rv);
  }
  const ls = st && st.session;
  if (ls && !out.some(s => s.id === ls.id)) {
    const now = st.now || Date.now() / 1000, el = Math.max(0, (now - ls.started_at) / 60);
    const seen = ls.on_task_so_far == null ? 0 : Math.round(el * ls.on_task_so_far);
    out.unshift({...ls, verdict: null, ended_at: null, verified_min: seen, live: true, day: localDate(new Date(ls.started_at * 1000))});
  }
  return out;
}
const stateKey = () => { const st = typeof lastState !== "undefined" ? lastState : null; return `${st?.session?.id ?? ""}|${st?.recent_verdict?.id ?? ""}|${st?.recent_verdict?.verdict ?? ""}`; };
function syncLiveSession() {
  if (stateKey() === stateRowsKey) return;
  renderSessions(lastSessList);
  if (typeof renderPlan === "function") renderPlan();
  if (typeof renderGrid === "function") renderGrid();
}
function renderSessions(list) {
  lastSessList = list = list || [];
  stateRowsKey = stateKey();
  list = withStateRows(list);
  const box = $("#sessions"); if (!box) return;
  const cnt = $("#sessCount"); if (cnt) cnt.textContent = list.length ? `${list.length} session${list.length === 1 ? "" : "s"}` : "";
  sessById.clear(); list.forEach(s => { if (!s.live) sessById.set(s.id, s); });
  if (!list.length) { box.innerHTML = `<p class="sess-empty">No sessions yet. Start one above and it shows up here with the photos Alibi took.</p>`; sessHtml.clear(); return; }
  box.querySelector(":scope>.sess-empty")?.remove();
  let ul = box.querySelector(":scope>.sess-list");
  if (!ul) { box.innerHTML = ""; ul = document.createElement("ul"); ul.className = "sess-list"; box.append(ul); wkEnter(ul); }
  // keyed: only changed sessions rebuild, so a playing reel or an open popover survives the refresh
  const nodes = list.map(s => {
    const html = sessionHtml(s), sig = html.replace(/\baldh\d+/g, "");   // icons.js numbers its hatch clips per call
    let el = ul.querySelector(`:scope>.sess[data-id="${s.id}"]`);
    if (!el || sessHtml.get(s.id) !== sig) {
      const t = document.createElement("ul"); t.innerHTML = html.trim();
      const n = t.firstElementChild, open = openSet.has(s.id);
      n.classList.toggle("open", open); n.firstElementChild.setAttribute("aria-expanded", open); n.querySelector(".detail").inert = !open;
      const oldV = el && el.querySelector("video"), newV = n.querySelector("video");
      if (oldV && newV && !oldV.paused && oldV.getAttribute("src") === newV.getAttribute("src")) newV.replaceWith(oldV);
      const was = sessVerdict.get(s.id);
      if (el && was && was !== s.verdict) n.querySelector(".al-verdict")?.classList.add("flip");
      if (el && sessVerdict.has(s.id) && !was) n.querySelector(".al-verdict")?.classList.add("flip");
      if (el) el.replaceWith(n);
      el = n; sessHtml.set(s.id, sig);
    }
    sessVerdict.set(s.id, s.verdict);
    return el;
  });
  [...ul.children].forEach(c => { if (!nodes.includes(c)) c.remove(); });
  nodes.forEach((n, i) => { if (ul.children[i] !== n) ul.insertBefore(n, ul.children[i] || null); });
  // Calm by default: the latest SESS_FIRST sessions, the rest one click away.
  nodes.forEach((n, i) => { n.hidden = !sessAll && i >= SESS_FIRST && !openSet.has(+n.dataset.id); });
  let more = box.querySelector(":scope>.sess-more");
  if (!more) { more = document.createElement("button"); more.type = "button"; more.className = "al-btn al-btn--quiet al-btn--sm sess-more"; more.addEventListener("click", () => { sessAll = !sessAll; renderSessions(lastSessList); }); box.append(more); }
  const extra = nodes.length - SESS_FIRST;
  more.hidden = extra <= 0;
  more.textContent = sessAll ? "Show fewer" : `Show ${extra} more`;
  more.setAttribute("aria-expanded", sessAll);
  if (pendingPlay != null) {
    const v = ul.querySelector(`.sess[data-id="${pendingPlay}"] video`);
    if (v) { pendingPlay = null; v.play().catch(() => {}); }
  }
  if (pendingGoto != null) gotoSession(pendingGoto);
}
let pendingGoto = null;
function setOpen(el, open) {
  const id = +el.dataset.id;
  el.classList.toggle("open", open);
  open ? openSet.add(id) : openSet.delete(id);
  el.firstElementChild.setAttribute("aria-expanded", open);
  el.querySelector(".detail").inert = !open;   // a folded detail is 0 px tall and transparent: keep its links and video out of the tab order
  if (!open) { el.querySelector("video")?.pause(); closePop(); }
}
function gotoSession(id) {
  const el = document.querySelector(`.sess[data-id="${id}"]`);
  if (!el) { pendingGoto = id; refreshSlow(); return; }
  pendingGoto = null;
  el.hidden = false;
  if (!el.classList.contains("open")) setOpen(el, true);
  el.scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start"});
  setTimeout(() => el.querySelector(".sm")?.focus({preventScroll: true}), 450);
}
addEventListener("hashchange", () => { const m = /^#session-(\d+)$/.exec(location.hash); if (m) gotoSession(+m[1]); });
$("#sessions")?.addEventListener("click", e => {
  const sm = e.target.closest(".sm"); if (sm) { openPop(sm); return; }
  const rb = e.target.closest("[data-reel]"); if (rb) { makeReel(+rb.dataset.reel, rb); return; }
  const b = e.target.closest(".sess>button"); if (!b) return;
  const el = b.parentElement;
  setOpen(el, !el.classList.contains("open"));
});

/* ---------- reels ---------- */
async function makeReel(id, btn) {
  const s = sessById.get(id), title = s ? dispName(s.habit, s.label) : "Reel";
  if (s && s.reel_url) return playReel(s.reel_url, title);
  const sess = btn.closest(".sess"), shot = sess?.querySelector(".sheet");
  btn.disabled = true; btn.innerHTML = `<span class="spin"></span>Cutting…`;
  shot?.classList.add("busy");
  try {
    const r = await fetch(`/api/reel?session=${id}`);
    if (r.status === 404) throw new Error("none");
    if (!r.ok) throw new Error("fail");
    const { url } = await r.json();
    playReel(url, title);
    refreshSlow();
  } catch (err) {
    btn.disabled = false; btn.innerHTML = `${wkIcon("film", 16)}Make reel`;
    showToast("note", err.message === "none" ? "No frames were kept for this session." : "Couldn't cut the reel. Is ffmpeg installed?");
  } finally { shot?.classList.remove("busy"); }
}
const lbWait = t => `<div class="wait"><span class="spin"></span><span>${t}</span></div>`;
async function todayReel() {
  const day = new Date();
  $("#lbTitle").innerHTML = `Today's reel <span class="lbsub">${esc(day.toLocaleDateString("en-GB", {weekday: "long", day: "numeric", month: "long"}))}</span>`;
  $("#lbBody").innerHTML = lbWait("Cutting today's frames into a reel…");
  openLayer("lightbox");
  const b = $("#todayReel"); if (b) b.disabled = true;
  try {
    const r = await fetch(`/api/reel?date=${localDate(day)}`);
    if (r.status === 404) { $("#lbBody").innerHTML = `<div class="wait wait--empty"><span>No photos today yet. Alibi only takes photos during camera-checked habits.</span></div>`; return; }
    if (!r.ok) throw new Error(r.status);
    const { url } = await r.json();
    if (!$("#lightbox").classList.contains("show")) return;
    $("#lbBody").innerHTML = `<video controls playsinline autoplay src="${esc(url)}?t=${Date.now()}"></video>`;
    $("#lbBody video").play().catch(() => {});
  } catch { $("#lbBody").innerHTML = `<div class="wait wait--empty"><span>Couldn't cut today's reel. Is ffmpeg installed?</span></div>`; }
  finally { if (b) b.disabled = false; }
}
$("#todayReel")?.addEventListener("click", todayReel);
async function playReel(path, title) {
  $("#lbTitle").innerHTML = `${esc(title || "Reel")} <span class="lbsub">Reel</span>`;
  $("#lbBody").innerHTML = lbWait("Cutting the frames into a reel…");
  openLayer("lightbox");
  try {
    let url = path;
    if (path.startsWith("/api/reel")) { const r = await fetch(path); if (r.status === 404) throw new Error("none"); if (!r.ok) throw new Error(r.status); url = (await r.json()).url; }
    if (!$("#lightbox").classList.contains("show")) return;
    $("#lbBody").innerHTML = `<video controls playsinline autoplay src="${esc(url)}"></video>`;
    $("#lbBody video").play().catch(() => {});
  } catch (e) { $("#lbBody").innerHTML = `<div class="wait wait--empty"><span>${e.message === "none" ? "No frames were kept for this one." : "Couldn't cut the reel. Is ffmpeg installed?"}</span></div>`; }
}

/* ---------- corrections ---------- */
let popFor = null;
function sampleFor(el) {
  const i = +el.dataset.i;
  if (el.dataset.live) return {sid: +el.dataset.sid, live: true, l: (liveSess && liveSess.id === +el.dataset.sid ? liveSess.labels || [] : [])[i]};
  return {sid: +el.dataset.sid, live: false, l: (sessById.get(+el.dataset.sid)?.labels || [])[i]};
}
function openPop(anchor) {
  if (popFor === anchor && $("#pop").classList.contains("show")) return closePop();
  const {sid, live, l} = sampleFor(anchor); if (!l) return;
  document.querySelectorAll(".sm.sel,.strip .dot.sel").forEach(x => x.classList.remove("sel"));
  anchor.classList.add("sel"); popFor = anchor;
  const pop = $("#pop"), note = cleanNote(l.note);
  wkUid = 1e9;
  pop.innerHTML = `<div class="ph">${l.frame_url ? `<img src="${esc(l.frame_url)}" alt="What Alibi saw at ${clockT(l.ts)}">` : `<span>No photo kept for this check</span>`}<span class="ph-time">${clockT(l.ts)}</span></div>
    <div class="pt">${wkDot(l.label, 12, {word: true})}${l.corrected_from ? `<span class="was">was ${esc(wkWord(l.corrected_from).toLowerCase())}</span>` : l.reused ? `<span class="was">reused, no motion</span>` : ""}</div>
    ${note ? `<p class="pn">${esc(note)}</p>` : ""}
    <div class="pq"><span class="t-label">What were you really doing?</span>${live ? `<span class="pq-hint">Counts when the session ends</span>` : ""}</div>
    <div class="pbtns">${LABELS.map((k, n) => `<button type="button" data-label="${k}" aria-pressed="${k === l.label}">${wkDot(k, 12, {hidden: true})}<span class="pb-w">${wkWord(k)}</span><span class="al-kbd">${n + 1}</span></button>`).join("")}</div>
    <div class="pm" role="status" aria-live="polite"></div>`;
  pop.dataset.sid = sid; pop.dataset.ts = l.ts; pop.dataset.live = live ? "1" : ""; pop.dataset.was = l.label;
  placePop(anchor);
  requestAnimationFrame(() => pop.classList.add("show"));
  pop.querySelector(`.pbtns button[aria-pressed=false]`)?.focus({preventScroll: true});
}
function placePop(anchor) {
  const pop = $("#pop"), r = anchor.getBoundingClientRect();
  pop.style.left = "0px"; pop.style.top = "0px";
  const w = pop.offsetWidth, h = pop.offsetHeight, vw = document.documentElement.clientWidth;
  let left = r.left + r.width / 2 - w / 2;
  left = Math.max(12, Math.min(left, vw - w - 12));
  let top = r.top - h - 12, below = false;
  if (top < 12) { top = r.bottom + 12; below = true; }
  pop.classList.toggle("below", below);
  pop.style.setProperty("--ox", `${Math.round(r.left + r.width / 2 - left)}px`);
  pop.style.left = `${left + scrollX}px`; pop.style.top = `${top + scrollY}px`;
}
function closePop(refocus) {
  const pop = $("#pop"); if (!pop.classList.contains("show")) return;
  pop.classList.remove("show");
  popFor?.classList.remove("sel");
  if (refocus && popFor?.isConnected) popFor.focus({preventScroll: true});
  popFor = null;
}
$("#pop")?.addEventListener("click", async e => {
  const b = e.target.closest("button[data-label]"); if (!b || b.getAttribute("aria-pressed") === "true") return;
  const pop = $("#pop"), sid = +pop.dataset.sid, live = !!pop.dataset.live;
  pop.querySelectorAll(".pbtns button").forEach(x => x.disabled = true);
  pop.querySelector(".pm").innerHTML = `<span class="spin"></span>Updating the score…`;
  try {
    const j = await postCorrect(sid, +pop.dataset.ts, b.dataset.label);
    closePop();
    if (live) await pollState(); else await refreshSlow();
    const v = /\b(done|partial|slacked)\b/i.exec(j.reply || "");
    const was = pop.dataset.was, ts = +pop.dataset.ts;
    AlibiMoments.correction(sid, ts, b.dataset.label, null, j.reply);
    showToast("correction", j.reply || "Correction noted.", v ? vvar(v[1].toLowerCase()) : "var(--accent)",
      was ? [{label: "Undo", undo: () => correct(sid, ts, was, live, true)}] : []);
  } catch (err) {
    pop.querySelectorAll(".pbtns button").forEach(x => x.disabled = false);
    pop.querySelector(".pm").textContent = `Couldn't record that: ${err.message}`;
  }
});
addEventListener("resize", () => closePop());
async function postCorrect(sid, ts, label) {
  const r = await fetch(`/api/sessions/${sid}/correct`, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ts, label})});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || r.status);
  return j;
}
async function correct(sid, ts, label, live, isUndo) {
  try {
    const j = await postCorrect(sid, ts, label);
    if (live) await pollState(); else await refreshSlow();
    AlibiMoments.correction(sid, ts, label, null, j.reply);
    const v = /\b(done|partial|slacked)\b/i.exec(j.reply || "");
    showToast("correction", isUndo ? "Undone. " + (j.reply || "") : (j.reply || "Correction noted."), v ? vvar(v[1].toLowerCase()) : "var(--accent)");
  } catch (err) { showToast("correction", `Couldn't record that: ${err.message}`); }
}
// keyboard: one tab stop per strip; ←/→ move, 1–5 relabel, Enter opens the inspector
document.addEventListener("keydown", e => {
  const el = e.target.closest?.(".sm,.strip .dot"); if (!el || e.metaKey || e.ctrlKey || e.altKey) return;
  const all = [...el.parentElement.querySelectorAll(".sm,.dot")], i = all.indexOf(el);
  let j = null;
  if (e.key === "ArrowRight") j = Math.min(all.length - 1, i + 1);
  else if (e.key === "ArrowLeft") j = Math.max(0, i - 1);
  else if (e.key === "Home") j = 0; else if (e.key === "End") j = all.length - 1;
  if (j != null) { e.preventDefault(); all.forEach(x => x.tabIndex = -1); all[j].tabIndex = 0; all[j].focus(); if ($("#pop").classList.contains("show")) openPop(all[j]); return; }
  const n = "12345".indexOf(e.key);
  if (n >= 0) {
    e.preventDefault();
    const {sid, live, l} = sampleFor(el); if (!l || l.label === LABELS[n]) return;
    closePop();
    const was = l.label, ts = l.ts;
    postCorrect(sid, ts, LABELS[n]).then(async j => {
      if (live) await pollState(); else await refreshSlow();
      AlibiMoments.correction(sid, ts, LABELS[n], null, j.reply);
      showToast("correction", j.reply || "Correction noted.", cvar(LABELS[n]), [{label: "Undo", undo: () => correct(sid, ts, was, live, true)}]);
      document.querySelector(`[data-sid="${sid}"][data-i="${el.dataset.i}"]`)?.focus({preventScroll: true});
    }).catch(err => showToast("correction", `Couldn't record that: ${err.message}`));
  }
});
