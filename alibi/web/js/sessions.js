/* sessions.js: sessions list, reels + lightbox playback, correction popover + keyboard. Classic script; load order core, now, week, sessions, setup, onboarding, boot. */
/* ---------- sessions ---------- */
const openSet = new Set(), sessHtml = new Map(), sessVerdict = new Map(), sessById = new Map();
let pendingPlay = null, maxMin = 60;
const sampleTip = l => { const n = cleanNote(l.note); return `${clockT(l.ts)} · ${l.label_text || LBL_TXT[l.label] || l.label}${l.corrected_from ? ` — was ${LBL_TXT[l.corrected_from] || l.corrected_from}, corrected by you` : ""}${l.learned_from ? ` — learned from your past corrections` : ""}${n ? ` — ${n}` : ""}`; };

function sessionHtml(s) {
  const labels = s.labels || [];
  const wpct = Math.max(18, Math.min(100, (s.declared_min || 0) / maxMin * 100)).toFixed(1);
  let tl;
  if (labels.length) tl = `<span class="tlw" style="--w:${wpct}%"><span class="tl">${labels.map(l => `<i style="--c:${cvar(l.label)}"></i>`).join("")}</span></span>`;
  else if (s.windows && s.windows.length) tl = `<span class="tlw" style="--w:${wpct}%"><span class="tl byapp">${s.windows.map(w => `<i style="--c:${cvar(w.label)};flex:${w.share || 0}" title="${esc(w.title)} ${pct(w.share)}"></i>`).join("")}</span><span class="tlk">by app · ${esc(s.windows[0].title)} ${pct(s.windows[0].share)}</span></span>`;
  else tl = `<span class="tlw" style="--w:${wpct}%"><span class="tl empty"></span></span>`;
  const v = s.verdict || "—";
  let media = "";
  if (s.reel_url) {
    media = `<div class="media"><video controls playsinline preload="none" src="${esc(s.reel_url)}" ${s.evidence_url ? `poster="${esc(s.evidence_url)}"` : ""} aria-label="Memories reel for session ${s.id}"></video>
      <div class="reelrow"><span>memories reel · ${labels.length} frames</span>${s.evidence_url ? `<a href="${esc(s.evidence_url)}" target="_blank" rel="noopener">contact sheet ↗</a>` : ""}</div></div>`;
  } else if (s.evidence_url || labels.length) {
    media = `<div class="media">${s.evidence_url ? `<div class="shot"><a href="${esc(s.evidence_url)}" target="_blank" rel="noopener"><img loading="lazy" src="${esc(s.evidence_url)}" alt="Contact sheet for session ${s.id}"></a><div class="veil"><span><span class="spin"></span>&nbsp; cutting the reel…</span></div></div>` : ""}
      ${labels.length ? `<div class="reelrow"><button class="ghostbtn" type="button" data-reel="${s.id}"><span class="tri">▶</span>Make reel</button><span class="rmsg">a timelapse of Alibi's ${labels.length} photo${labels.length === 1 ? "" : "s"}</span></div>` : ""}</div>`;
  }
  const counts = LABELS.map(l => [l, labels.filter(x => x.label === l).length]).filter(x => x[1]);
  const fixedN = labels.filter(l => l.corrected_from).length;
  const parts = [s.camera_ratio != null ? `camera <b>${pct(s.camera_ratio)}</b>` : "", s.screen_ratio != null ? `screen <b>${pct(s.screen_ratio)}</b>` : "", s.coverage != null && s.coverage < 0.995 ? `happened <b>${pct(s.coverage)}</b>` : ""].filter(Boolean).join(" · ");
  const meta = `<div class="meta">
      <div>${clockT(s.started_at)} → ${clockT(s.ended_at || s.ends_at)} · ${esc(CHECK_WORD[s.modality] || "")}</div>
      <div>on task <b>${pct(s.on_task_ratio)}</b>${parts ? " · " + parts : ""}</div>
      <div>Alibi saw <b>${s.verified_min ?? "—"}</b> of ${esc(String(s.declared_min ?? "—"))} min</div>
      ${counts.length ? `<div>${counts.map(([l,n]) => `<span style="color:${cvar(l)}">●</span> ${LBL_TXT[l]} ${n}`).join(" &nbsp;")}</div>` : ""}
      ${fixedN ? `<div>${fixedN} check${fixedN === 1 ? "" : "s"} fixed by you</div>` : ""}
      ${s.artefact ? `<div>artefact <a href="${esc(s.artefact)}" target="_blank" rel="noopener"><b>${esc(s.artefact)}</b></a></div>` : ""}
    </div>`;
  const why = (s.summary || s.why) ? `<div class="vwhyrow">${s.summary ? `<b>${esc(plain(s.summary))}</b>` : ""}${s.score_line ? esc(s.score_line) : ""}</div>` : "";
  const wins = s.windows && s.windows.length ? `<div class="wins" style="margin-top:16px">${renderWindows(s.windows)}</div>` : "";
  const side = `<div>${meta}${wins}</div>`;
  const samples = labels.length ? `<div class="samples">
      <div class="eyebrow"><span>what Alibi saw, minute by minute</span><span>got one wrong? tap it to fix it</span></div>
      <div class="seg" role="toolbar" aria-label="Samples for session ${s.id}">${labels.map((l, i) => `<button type="button" tabindex="${i === 0 ? 0 : -1}" class="sm${l.corrected_from ? " fixed" : ""}" style="--c:${cvar(l.label)}" data-sid="${s.id}" data-i="${i}" title="${esc(sampleTip(l))}" aria-label="Check at ${clockT(l.ts)}: ${esc(LBL_TXT[l.label] || l.label)}. Fix it"></button>`).join("")}</div>
      <div class="axis"><span>${clockT(labels[0].ts)}</span><span>${clockT(labels[labels.length - 1].ts)}</span></div></div>` : "";
  const inner = media ? `<div class="in">${why}${samples}${media}${side}</div>` : `<div class="in solo">${why}${samples}${side}</div>`;
  return `<div class="sess" data-id="${s.id}" id="session-${s.id}">
    <button type="button" aria-expanded="false">
      <span class="when"><b>${clockT(s.started_at)}</b>${esc(hm(s.declared_min))}</span>
      <span class="h">${esc(dispName(s.habit, s.label))}<small>${esc(CHECK_WORD[s.modality] || "")}</small></span>
      <span class="pill" style="--c:${vvar(s.verdict)}">${esc(VWORD[v] || v)}</span>
      ${tl}
      <span class="ratio"><b>${pct(s.on_task_ratio)}</b><small>${s.verified_min ?? "—"} / ${s.declared_min ?? "—"} min</small></span>
      <span class="chev" aria-hidden="true">▸</span>
    </button>
    <div class="detail"><div>${inner}</div></div>
  </div>`;
}

const dayKey = s => s.day || localDate(new Date(s.started_at * 1000));
function dayLabel(k) {
  const today = localDate(), y = new Date(); y.setDate(y.getDate() - 1);
  if (k === today) return "Today"; if (k === localDate(y)) return "Yesterday";
  const [Y, M, D] = k.split("-").map(Number);
  return new Date(Y, M - 1, D).toLocaleDateString(undefined, {weekday: "long", day: "numeric", month: "short"});
}
function renderSessions(list) {
  list = list || [];
  const box = $("#sessions");
  $("#sessCount").textContent = list.length ? `${list.length} so far` : "";
  sessById.clear(); list.forEach(s => sessById.set(s.id, s));
  maxMin = Math.max(30, ...list.map(s => s.declared_min || 0));
  if (!list.length) { box.innerHTML = `<p class="none">No sessions yet. Start one above — it'll show up here with the photos Alibi took.</p>`; sessHtml.clear(); return; }
  box.querySelector(":scope>.none")?.remove();
  // group by day; keyed so only changed sessions rebuild and a playing reel / open popover survives the refresh
  const groups = [];
  list.forEach(s => { const k = dayKey(s); let g = groups[groups.length - 1]; if (!g || g.k !== k) groups.push(g = {k, items: []}); g.items.push(s); });
  const keepGroups = [];
  groups.forEach((g, gi) => {
    let ge = box.querySelector(`:scope>.daygrp[data-k="${g.k}"]`);
    if (!ge) { ge = document.createElement("div"); ge.className = "daygrp"; ge.dataset.k = g.k; ge.innerHTML = `<div class="dayhead"><span></span><span></span></div>`; }
    const seen = g.items.reduce((a, s) => a + (s.verified_min || 0), 0), claimed = g.items.reduce((a, s) => a + (s.declared_min || 0), 0);
    ge.firstElementChild.firstElementChild.textContent = dayLabel(g.k);
    ge.firstElementChild.lastElementChild.textContent = `Alibi saw ${hm(seen)} of ${hm(claimed)}`;
    const nodes = g.items.map(s => {
      const html = sessionHtml(s);
      let el = box.querySelector(`.sess[data-id="${s.id}"]`);
      if (!el || sessHtml.get(s.id) !== html) {
        const t = document.createElement("div"); t.innerHTML = html.trim();
        const n = t.firstElementChild, open = openSet.has(s.id);
        n.classList.toggle("open", open); n.firstElementChild.setAttribute("aria-expanded", open);
        const oldV = el && el.querySelector("video");
        const newV = n.querySelector("video");
        if (oldV && newV && !oldV.paused && oldV.getAttribute("src") === newV.getAttribute("src")) newV.replaceWith(oldV);
        const was = sessVerdict.get(s.id);
        if (el && was && was !== s.verdict) n.querySelector(".pill").classList.add("flip");
        if (el) el.replaceWith(n);
        el = n; sessHtml.set(s.id, html);
      }
      sessVerdict.set(s.id, s.verdict);
      return el;
    });
    [...ge.children].slice(1).forEach(c => { if (!nodes.includes(c)) c.remove(); });
    nodes.forEach((n, i) => { if (ge.children[i + 1] !== n) ge.insertBefore(n, ge.children[i + 1] || null); });
    if (box.children[gi] !== ge) box.insertBefore(ge, box.children[gi] || null);
    keepGroups.push(ge);
  });
  [...box.children].forEach(c => { if (!keepGroups.includes(c)) c.remove(); });
  if (pendingPlay != null) {
    const v = box.querySelector(`.sess[data-id="${pendingPlay}"] video`);
    if (v) { pendingPlay = null; v.play().catch(() => {}); }
  }
  if (pendingGoto != null) gotoSession(pendingGoto);
}
let pendingGoto = null;
function gotoSession(id) {
  const el = document.querySelector(`.sess[data-id="${id}"]`);
  if (!el) { pendingGoto = id; refreshSlow(); return; }
  pendingGoto = null;
  if (!el.classList.contains("open")) { el.classList.add("open"); openSet.add(id); el.firstElementChild.setAttribute("aria-expanded", "true"); }
  el.scrollIntoView({behavior: "smooth", block: "start"});
  setTimeout(() => el.querySelector(".sm")?.focus({preventScroll: true}), 450);
}
addEventListener("hashchange", () => { const m = /^#session-(\d+)$/.exec(location.hash); if (m) gotoSession(+m[1]); });
$("#sessions").addEventListener("click", e => {
  const sm = e.target.closest(".sm"); if (sm) { openPop(sm); return; }
  const rb = e.target.closest("[data-reel]"); if (rb) { makeReel(+rb.dataset.reel, rb); return; }
  const b = e.target.closest(".sess>button"); if (!b) return;
  const el = b.parentElement, id = +el.dataset.id;
  el.classList.toggle("open");
  el.classList.contains("open") ? openSet.add(id) : openSet.delete(id);
  b.setAttribute("aria-expanded", el.classList.contains("open"));
  if (!el.classList.contains("open")) { el.querySelector("video")?.pause(); closePop(); }
});

/* ---------- reels ---------- */
async function makeReel(id, btn) {
  const sess = btn.closest(".sess"), shot = sess.querySelector(".shot"), msg = sess.querySelector(".rmsg");
  btn.disabled = true; btn.innerHTML = `<span class="spin"></span>Cutting…`;
  shot?.classList.add("busy");
  if (msg) msg.textContent = "stitching frames — a few seconds";
  try {
    const r = await fetch(`/api/reel?session=${id}`);
    if (r.status === 404) throw new Error("none");
    if (!r.ok) throw new Error("fail");
    const { url } = await r.json();
    pendingPlay = id;
    await refreshSlow();
    if (pendingPlay === id) {            // the server didn't report it yet; play what we were given
      pendingPlay = null;
      const media = sess.isConnected ? sess.querySelector(".media") : document.querySelector(`.sess[data-id="${id}"] .media`);
      if (media) { media.innerHTML = `<video controls playsinline autoplay src="${esc(url)}"></video>`; media.querySelector("video").play().catch(() => {}); }
    }
  } catch (err) {
    shot?.classList.remove("busy");
    btn.disabled = false; btn.innerHTML = `<span class="tri">▶</span>Make reel`;
    if (msg) msg.textContent = err.message === "none" ? "no frames were kept for this session" : "couldn't cut the reel — is ffmpeg installed?";
  }
}

async function todayReel() {
  const day = new Date();
  $("#lbTitle").innerHTML = `Today's reel <em>— ${esc(day.toLocaleDateString(undefined, {weekday:"long", day:"numeric", month:"long"}))}</em>`;
  $("#lbBody").innerHTML = `<div class="wait"><span><span class="spin"></span>&nbsp; Cutting today's frames into a reel…</span></div>`;
  openLayer("lightbox");
  const b = $("#todayReel"); b.disabled = true;
  try {
    const r = await fetch(`/api/reel?date=${localDate(day)}`);
    if (r.status === 404) { $("#lbBody").innerHTML = `<div class="wait">No photos today yet.<br>Alibi only takes photos during camera-checked habits.</div>`; return; }
    if (!r.ok) throw new Error(r.status);
    const { url } = await r.json();
    if (!$("#lightbox").classList.contains("show")) return;
    $("#lbBody").innerHTML = `<video controls playsinline autoplay src="${esc(url)}?t=${Date.now()}"></video>`;
    $("#lbBody video").play().catch(() => {});
  } catch { $("#lbBody").innerHTML = `<div class="wait">Couldn't cut today's reel.<br>Is ffmpeg installed?</div>`; }
  finally { b.disabled = false; }
}
$("#todayReel").addEventListener("click", todayReel);
async function playReel(path, title) {
  $("#lbTitle").innerHTML = `${esc(title || "Reel")} <em>— memories</em>`;
  $("#lbBody").innerHTML = `<div class="wait"><span><span class="spin"></span>&nbsp; Cutting the frames into a reel…</span></div>`;
  openLayer("lightbox");
  try {
    let url = path;
    if (path.startsWith("/api/reel")) { const r = await fetch(path); if (r.status === 404) throw new Error("none"); if (!r.ok) throw new Error(r.status); url = (await r.json()).url; }
    if (!$("#lightbox").classList.contains("show")) return;
    $("#lbBody").innerHTML = `<video controls playsinline autoplay src="${esc(url)}"></video>`;
    $("#lbBody video").play().catch(() => {});
  } catch (e) { $("#lbBody").innerHTML = `<div class="wait">${e.message === "none" ? "No frames were kept for this one." : "Couldn't cut the reel.<br>Is ffmpeg installed?"}</div>`; }
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
  const pop = $("#pop");
  pop.style.setProperty("--c", cvar(l.label));
  pop.innerHTML = `<div class="ph">${l.frame_url ? `<img src="${esc(l.frame_url)}" alt="What Alibi saw at ${clockT(l.ts)}">` : "no photo kept for this check"}</div>
    <div class="pt"><span>${clockT(l.ts)}</span>·<b>${esc(LBL_TXT[l.label] || l.label)}</b>${l.corrected_from ? `<span class="was">was ${esc(LBL_TXT[l.corrected_from] || l.corrected_from)}</span>` : l.reused ? `<span class="was">reused · no motion</span>` : ""}</div>
    <p class="pn">${esc(cleanNote(l.note))}</p>
    <div class="eyebrow">${live ? "what were you really doing? · counts at the end" : "what were you really doing?"}</div>
    <div class="pbtns">${LABELS.map(k => `<button type="button" style="--c:${cvar(k)}" data-label="${k}" aria-pressed="${k === l.label}">${LBL_TXT[k]} <span class="kbd">${LABELS.indexOf(k) + 1}</span></button>`).join("")}</div>
    <div class="pm"></div>`;
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
  let top = r.top - h - 12;
  if (top < 12) top = r.bottom + 12;
  pop.style.left = `${left + scrollX}px`; pop.style.top = `${top + scrollY}px`;
}
function closePop(refocus) {
  const pop = $("#pop"); if (!pop.classList.contains("show")) return;
  pop.classList.remove("show");
  popFor?.classList.remove("sel");
  if (refocus && popFor?.isConnected) popFor.focus({preventScroll: true});
  popFor = null;
}
$("#pop").addEventListener("click", async e => {
  const b = e.target.closest("button[data-label]"); if (!b || b.getAttribute("aria-pressed") === "true") return;
  const pop = $("#pop"), sid = +pop.dataset.sid, live = !!pop.dataset.live;
  pop.querySelectorAll(".pbtns button").forEach(x => x.disabled = true);
  pop.querySelector(".pm").innerHTML = `<span class="spin"></span>&nbsp; updating the score…`;
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
