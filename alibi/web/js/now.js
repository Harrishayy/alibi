/* now.js: the Now slot. Composer (chips, say/reply, suggestCard); live session card (ring, on-task stat, last 6 samples,
   drift line, every-check strip for corrections); verdict card (pill, meter, sentence, proof frames); the idle
   "Latest verdict" card. Classic script; load order icons, pinch, moments, pinch-wire, confetti, core, now, week, sessions, setup, onboarding, boot.

   DOM contract for moments.js: #composer (composer wrapper, keeps #sayForm), #now (the swapping card slot),
   #pinch-now (persistent 96px Pinch mount: parked off-screen when idle, moved into .pn-slot of the live and verdict
   cards, never re-created), #pinch-hero (64px, hero strip, hidden while live or verdict).
   Verdict card parts follow moments.js: [data-m=card|pill|pct|meter|frames|line|actions]; meter is on the fill, frames on the grid.
   Live sample strip: #six .al-strip__cell (the newest gets .is-new, which runs the CSS develop from components.css). */
/* ---------- composer ---------- */
const VI = (n, s) => AlibiIcons.svg(n, s || 20);
let chipSay = {};
function renderChips(habits, live) {
  const box = $("#chips");
  if (live) { box.innerHTML = ""; chipSay = {}; return; }
  const hs = Object.entries(habits || {}).filter(([, h]) => h && !h.source && h.default_min).slice(0, 3);
  chipSay = {};
  box.innerHTML = hs.map(([k, h], i) => {
    const text = `${h.label || hname(k)} ${h.default_min} min`;
    chipSay[text] = `${k} for ${h.default_min} minutes`;
    return `<button class="al-chip" type="button" data-chip="${esc(text)}">${esc(text)}<kbd class="al-kbd">⌘${i + 1}</kbd></button>`;
  }).join("");
  syncComposer();
}
renderChips();
function syncComposer() {
  const v = $("#sayInput").value.trim(), f = $("#sayForm");
  $("#sayBtn").disabled = !v;
  f.classList.toggle("has-text", !!v);
  $("#sayHint").hidden = !!v || document.activeElement === $("#sayInput");
  $("#chips").querySelectorAll(".al-chip").forEach(c => c.classList.toggle("is-selected", c.dataset.chip === v));
}
function pickChip(i) {
  const c = $("#chips").querySelectorAll(".al-chip")[i]; if (!c) return;
  $("#sayInput").value = c.dataset.chip; $("#sayInput").focus(); syncComposer();
}
$("#chips").addEventListener("click", e => { const b = e.target.closest(".al-chip"); if (b) pickChip([...$("#chips").children].indexOf(b)); });
$("#sayInput").addEventListener("input", syncComposer);
$("#sayInput").addEventListener("focus", () => { $("#sayForm").classList.add("is-focused"); syncComposer(); });
$("#sayInput").addEventListener("blur", () => { $("#sayForm").classList.remove("is-focused"); syncComposer(); });
$("#sayInput").addEventListener("keydown", e => { if (e.key === "Escape") e.currentTarget.blur(); });
$("#sayForm").addEventListener("submit", e => {
  e.preventDefault();
  const v = $("#sayInput").value.trim(); if (!v) return;
  say(chipSay[v] || v, v);
});
// "/" focuses the composer; ⌘1–⌘3 pick a habit chip (Surfaces.md, keyboard).
document.addEventListener("keydown", e => {
  const t = e.target, typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
  const open = document.querySelector(".drawer.show,.lightbox.show,.onb.show,.hs.show");
  if (open || document.body.classList.contains("live")) return;
  if (e.key === "/" && !typing && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); $("#sayInput").focus(); return; }
  if ((e.metaKey || e.ctrlKey) && /^[1-3]$/.test(e.key)) { e.preventDefault(); pickChip(+e.key - 1); }
});

async function say(text, shown) {
  $("#sayInput").value = ""; syncComposer(); $("#sayBtn").disabled = true;
  const convo = $("#convo");
  convo.innerHTML = `<div class="line you"><span class="who">You</span><span class="txt">${esc(shown || text)}</span></div>
    <div class="line alibi"><span class="who">Alibi</span><span class="txt pending">Thinking it over…</span></div>`;
  try {
    const r = await api("/api/say", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text})});
    reply(r.reply);
    if (/^Started\b/.test(r.reply || "")) AlibiMoments.sessionStart($("#composer"), $("#now"));
    if (/isn.t one of your habits yet|not a habit yet/i.test(r.reply || "")) suggestCard(text);
  } catch (err) { reply("Alibi isn't running. Start it with ./alibi.sh up, then try again."); }
  syncComposer();
  pollState(); refreshSlow();
}
function reply(t) {
  const el = $("#convo .line.alibi .txt");
  if (el) { el.classList.remove("pending"); el.textContent = plain(t) || "(no reply)"; }
}

/* ---------- Now: one slot that swaps between idle, live and verdict ---------- */
// The 96px Pinch is mounted once by pinch-wire.js and moved between cards, so its animation state survives a swap.
function parkPinch() { const pn = $("#pinch-now"), park = document.querySelector(".parking"); if (pn && park && pn.parentElement !== park) park.appendChild(pn); }
function placePinch(root) { const slot = root.querySelector(".pn-slot"), pn = $("#pinch-now"); if (slot && pn) slot.replaceWith(pn); }
const minutes = n => `${n} minute${n === 1 ? "" : "s"}`;
const lc = s => String(s || "").toLowerCase();
const whenT = t => { const d = new Date(t * 1000), today = new Date().toDateString() === d.toDateString();
  return `${today ? "today" : d.toLocaleDateString("en-GB", {weekday: "short", day: "numeric", month: "short"})}, ${clockT(t)}`; };
const nowStamp = t => `${new Date(t * 1000).toLocaleDateString("en-GB", {weekday: "short", day: "numeric", month: "short"})} · ${clockT(t)}`;
const CHECK_SRC = {physical: "desk camera", digital: "window titles", hybrid: "desk camera and window titles", strava: "Strava", health: "Apple Health"};

function renderNow(sess, now, rv) {
  const box = $("#now");
  if (!sess) {
    if (rv && rv.id !== dismissedVerdict) {
      const sig = "v" + rv.id + ":" + rv.verdict + ":" + Math.round((rv.on_task_ratio || 0) * 100);
      if (nowSig !== sig) {
        const anim = !nowSig.startsWith("v" + rv.id + ":");
        nowSig = sig; seenLabels = 0; lastFrame = null; liveSess = null; setMode("verdict");
        if (popFor?.dataset.live) closePop();
        renderVerdict(rv, anim);
      }
      $("#nowEyebrow").textContent = `Finished ${clockT(rv.ended_at || rv.ends_at)}`;
      return;
    }
    if (nowSig !== "empty") {
      nowSig = "empty"; seenLabels = 0; lastFrame = null; liveSess = null;
      if (popFor?.dataset.live) closePop();
      parkPinch(); box.innerHTML = "";
      setMode("idle");
    }
    $("#nowEyebrow").textContent = nowStamp(now || Date.now() / 1000);
    renderNextLine();
    return;
  }
  const sig = "s" + sess.id;
  if (nowSig !== sig) {
    nowSig = sig; seenLabels = 0; lastFrame = null; setMode("live");
    if (popFor?.dataset.live) closePop();
    parkPinch();
    box.innerHTML = `<article class="al-card livecard" id="nowGrid" aria-label="Live session">
      <div class="al-ring is-ticking ringbox" id="ring" role="progressbar" aria-valuemin="0" aria-valuemax="100">
        <svg class="al-ring__svg" width="160" height="160" viewBox="0 0 160 160" aria-hidden="true" focusable="false">
          <circle class="al-ring__track" cx="80" cy="80" r="75" stroke-width="10" fill="none"/>
          <circle class="al-ring__arc" id="arc" cx="80" cy="80" r="75" stroke-width="10" fill="none" stroke-linecap="round" stroke-dasharray="471.24" stroke-dashoffset="471.24"/></svg>
        <div class="al-ring__center" aria-hidden="true"><span class="al-ring__value" id="left">--:--</span><span class="al-ring__caption" id="leftLbl"></span></div>
      </div>
      <div class="livebody">
        <div class="livehead"><div class="livetitle"><h3 class="t-h3">${esc(dispName(sess.habit, sess.label))}</h3><span class="meta" id="nowSub"></span></div><span class="pn-slot"></span></div>
        <div class="livestats">
          <div class="al-stat"><span class="al-stat__label">On task</span><span class="al-stat__value" id="otk">—</span><span class="al-stat__sub" id="otkLbl"></span></div>
          <div class="samples"><div class="al-strip has-frames" id="six" role="img"></div><span class="meta" id="sixLbl">Last 6 samples</span></div>
        </div>
        <p class="driftline" id="drift"></p>
        <div class="liveacts" id="liveActs"></div>
        <div class="checks" id="checks-live">
          <div class="checks-head"><span class="t-label">Every check</span><span class="meta">Tap one if I got it wrong</span></div>
          <div class="strip" id="strip" role="toolbar" aria-label="Checks so far. Arrow keys move, 1 to 5 fix"></div>
        </div>
        <div class="wins" id="wins"></div>
      </div></article>`;
    placePinch(box);
  }
  const name = dispName(sess.habit, sess.label);
  $("#nowEyebrow").textContent = nowStamp(now);
  $("#nowSub").textContent = `Started ${clockT(sess.started_at)} · ${CHECK_SRC[sess.modality] || "checked by Alibi"}${sess.nudges ? ` · ${sess.nudges} nudge${sess.nudges === 1 ? "" : "s"}` : ""}`;
  const left = sess.left_s ?? Math.max(0, sess.ends_at - now);
  const brk = sess.on_break;
  $("#left").textContent = brk ? mmss(brk.left_s) : mmss(left);
  $("#leftLbl").textContent = brk ? "break left" : `left of ${sess.declared_min} min`;
  const prog = Math.min(1, Math.max(0, sess.progress ?? 0));
  $("#arc").style.strokeDashoffset = (471.24 * (1 - prog)).toFixed(2);
  const ring = $("#ring");
  ring.setAttribute("aria-valuenow", Math.round(prog * 100));
  ring.setAttribute("aria-valuetext", `${brk ? mmss(brk.left_s) + " of break left" : mmss(left) + " left of " + sess.declared_min + " min"}`);
  const dl = sess.drifting?.label;
  ring.classList.toggle("al-ring--partial", !!brk);
  ring.classList.toggle("al-ring--warn", !brk && (dl === "phone" || dl === "off_task"));
  ring.classList.toggle("is-final", !brk && left <= 60);
  if (sess.warming_up || sess.on_task_so_far == null) {
    const more = Math.max(1, 6 - (sess.samples || 0));
    $("#otk").textContent = "—"; $("#otkLbl").textContent = `${more} more check${more === 1 ? "" : "s"} until a score`;
  } else {
    const labels = sess.labels || [], on = labels.filter(l => l.label === "on_task").length;
    $("#otk").textContent = `${Math.round(sess.on_task_so_far * 100)}%`;
    $("#otkLbl").textContent = `${on} of ${labels.length || sess.samples} checks`;
  }
  // Drift line, in Pinch's voice: only the cause is in warn ink.
  const dr = $("#drift"), C = t => `<span class="al-cause">${esc(t)}</span>`;
  let line = "";
  if (brk) line = `On a break. Back at ${clockT(now + (brk.left_s || 0))}.`;
  else if (sess.drifting) {
    const m = Math.max(1, Math.round((sess.drifting.since_s || 0) / 60)), d = sess.drifting;
    line = d.label === "phone" ? `You said ${esc(habitLc(name))}. I've seen your ${C("phone")} for ${minutes(m)}.`
      : d.label === "off_task" ? (d.label_text && !/^off.task$/i.test(d.label_text) ? `You said ${esc(habitLc(name))}. That's been ${C(d.label_text)} for ${minutes(m)}.` : `You said ${esc(habitLc(name))}. I've seen ${C("something else")} for ${minutes(m)}.`)
      : d.label === "idle" ? `You said ${esc(habitLc(name))}. Nothing's ${C("moved")} in ${minutes(m)}.`
      : `Your desk's been ${C("empty")} for ${minutes(m)}. Still ${esc(habitLc(name))}?`;
  } else line = esc(lastState?.pinch?.line || (sess.last_seen ? `Last seen ${clockT(now - (sess.last_seen.ago_s || 0))}: ${lc(sess.last_seen.label_text || LBL_TXT[sess.last_seen.label] || "")}.` : "Watching. The first check lands in a moment."));
  if (dr.dataset.html !== line) { dr.dataset.html = line; dr.innerHTML = line; }
  dr.classList.toggle("is-drift", !!sess.drifting && !brk);
  const canCancel = (now - sess.started_at) < 90 && (sess.samples || 0) < 2;   // matches cli.cancellable
  const actsSig = (brk ? "b" : sess.drifting ? "d" : "n") + (canCancel ? "c" : "");
  const la = $("#liveActs");
  if (la.dataset.sig !== actsSig) {
    la.dataset.sig = actsSig;
    const B = (label, attrs, variant, icon) => `<button type="button" class="al-btn al-btn--${variant || "secondary"}" ${attrs}>${icon ? VI(icon, 16) : ""}${esc(label)}</button>`;
    const acts = brk ? [B("Back to it", 'data-say="back"', "primary")]
      : sess.drifting ? [B("Back to it", 'data-say="back"', "primary"), B("This counts", 'data-say="it\'s on task"'), B("Break", 'data-say="break 5"', "secondary", "cup")]
      : [B("Break", 'data-say="break 5"', "secondary", "cup"), B("10 min", 'data-say="add 10"', "secondary", "plus")];
    la.innerHTML = acts.join("") + (canCancel ? B("Cancel", 'id="cancelBtn" title="Started by mistake? Nothing gets logged."', "quiet")
      : B("Finish", 'id="endBtn"', "secondary", "stop"));
  }

  const labels = sess.labels || [];
  liveSess = sess;
  // Last 6 samples, newest on the right; the newest develops (CSS) when a sample arrives.
  const six = $("#six"), grew = labels.length > seenLabels && !firstState && seenLabels > 0;
  const tail = labels.slice(-6);
  const sixSig = tail.map(l => l.ts + l.label).join("|");
  if (six.dataset.sig !== sixSig) {
    six.dataset.sig = sixSig;
    six.classList.toggle("has-frames", tail.some(l => l.frame_url));
    six.innerHTML = tail.map((l, i) => {
      const nw = grew && i === tail.length - 1;
      const img = l.frame_url ? `<img class="al-strip__img" src="${esc(l.frame_url)}" alt="">` : "";
      return `<span class="al-strip__cell${nw ? " is-new" : ""}${l.frame_url ? " has-img" : ""}">${img}<span class="al-strip__dot">${AlibiIcons.dot(l.label, l.frame_url ? 10 : 12)}</span></span>`;
    }).join("");
    six.setAttribute("aria-label", `Last ${tail.length} samples: ${tail.map(l => LBL_TXT[l.label] || l.label).join(", ")}`);
    $("#sixLbl").textContent = tail.length ? `Last ${tail.length} sample${tail.length === 1 ? "" : "s"}` : "No samples yet";
    if (grew) { const cell = six.lastElementChild; AlibiMoments.sample(tail[tail.length - 1].label, cell?.querySelector("img") || null, cell?.querySelector(".al-strip__dot") || null); }
  }
  const strip = $("#strip");
  if (strip) {
    if (labels.length < seenLabels) { strip.innerHTML = ""; seenLabels = 0; }
    for (let i = seenLabels; i < labels.length; i++) {
      const d = document.createElement("button");
      d.type = "button"; d.className = "dot"; d.dataset.sid = sess.id; d.dataset.i = i; d.dataset.live = "1"; d.tabIndex = -1;
      strip.appendChild(d);
    }
    seenLabels = labels.length;
    const dots = strip.querySelectorAll(".dot");
    if (dots.length && !strip.querySelector('.dot[tabindex="0"]')) dots[dots.length - 1].tabIndex = 0;
    dots.forEach((d, i) => {     // corrections recolour and reshape samples already on the strip
      const l = labels[i]; if (!l) return;
      if (d.dataset.l !== l.label) { d.dataset.l = l.label; d.innerHTML = AlibiIcons.dot(l.label, 12).replace(' role="img"', "").replace(/ aria-label="[^"]*"/, ""); }
      d.classList.toggle("fixed", !!l.corrected_from);
      d.title = sampleTip(l);
      d.setAttribute("aria-label", `Check at ${clockT(l.ts)}: ${LBL_TXT[l.label] || l.label}. Fix it`);
    });
    $("#checks-live").hidden = !labels.length;
  }
  const wins = $("#wins");
  if (wins) wins.innerHTML = renderWindows(sess.windows);
}

/* ---------- verdict card ---------- */
// The verdict sentence, in Pinch's voice (Voice.md "Verdicts"), built from the numbers so it never overclaims.
function verdictSentence(rv) {
  const seen = rv.verified_min ?? Math.round((rv.on_task_ratio || 0) * (rv.declared_min || 0));
  const of = rv.declared_min || rv.elapsed_min || 0;
  const off = {};
  (rv.labels || []).forEach(l => { if (l.label !== "on_task") off[l.label] = (off[l.label] || 0) + 1; });
  const top = Object.entries(off).sort((a, b) => b[1] - a[1])[0];
  const cause = top ? ({phone: "The phone", off_task: "Something else", idle: "Idle time", absent: "An empty desk"})[top[0]] : null;
  const unit = of === 1 ? "minute" : "minutes";
  if (rv.verdict === "done") return `Done. ${seen} of ${of} ${unit} on task.${cause && top[1] > 1 ? ` ${cause} had a little of it.` : ""}`;
  if (rv.verdict === "partial") return `Partly. ${seen} of ${of} ${unit} on task.${cause ? ` ${cause} had the rest.` : ""} Tap any frame if I got it wrong.`;
  return `Slacked, by my count. ${seen} of ${of} ${unit} on task. Tap any frame if I got it wrong.`;
}
// Up to n frames spread across the session. Partly and slacked keep the off-task ones first (they're what you'd want
// to fix); a Done keeps them in proportion, so a 79% Done doesn't show half its proof in red.
function pickFrames(labels, n, verdict, ratio) {
  const idx = labels.map((l, i) => l.frame_url ? i : -1).filter(i => i >= 0);
  if (idx.length <= n) return idx;
  const spread = (arr, k) => k <= 0 ? [] : k >= arr.length ? [...arr] : Array.from({length: k}, (_, j) => arr[Math.round(j * (arr.length - 1) / Math.max(1, k - 1))]);
  const off = idx.filter(i => labels[i].label !== "on_task");
  let out;
  if (verdict === "done") {
    const r = ratio != null ? ratio : 1 - off.length / idx.length;
    const bad = spread(off, off.length ? Math.max(1, Math.round(n * (1 - r))) : 0);
    out = [...bad, ...spread(idx.filter(i => labels[i].label === "on_task"), n - bad.length)];
    if (out.length < n) out.push(...off.filter(i => !out.includes(i)).slice(0, n - out.length));
  } else {
    const bad = off.slice(0, Math.ceil(n / 2));
    out = [...bad, ...spread(idx.filter(i => !bad.includes(i)), n - bad.length)];
  }
  return [...new Set(out)].sort((a, b) => a - b);
}
function frameBtn(rv, i, cls) {
  const l = rv.labels[i], word = LBL_TXT[l.label] || l.label, bad = l.label !== "on_task";
  return `<button type="button" class="vframe${cls ? " " + cls : ""}" data-fix="1" data-sid="${rv.id}" data-i="${i}" aria-label="Frame at ${clockT(l.ts)}, ${esc(word)}. Fix it">
    <img src="${esc(l.frame_url)}" alt="" loading="lazy">
    ${bad ? `<span class="vf-tag vf-${esc(l.label)}">${AlibiIcons.dot(l.label, 8)}<span>${esc(({phone: "Phone", off_task: "Off task", idle: "Idle", absent: "Away"})[l.label] || word)}</span></span>` : `<span class="vf-dot">${AlibiIcons.dot(l.label, 8)}</span>`}
    <span class="vf-time">${clockT(l.ts)}</span></button>`;
}
function renderVerdict(rv, anim) {
  const v = ["done", "partial", "slacked"].includes(rv.verdict) ? rv.verdict : "partial", ratio = rv.on_task_ratio || 0, r = Math.round(ratio * 100);
  const name = dispName(rv.habit, rv.label);
  const doneAt = rv.done_at ?? 0.7, partAt = rv.partial_at ?? 0.4;
  const seen = rv.verified_min ?? "—", of = rv.declared_min ?? "—";
  const labels = rv.labels || [], picks = pickFrames(labels, 6, rv.verdict, rv.on_task_ratio);
  const proof = picks.length ? `<div class="vproof">
        <div class="vproof-head"><span class="t-label">Proof, ${picks.length} of ${labels.length} frames</span><span class="meta">Tap any frame to fix it</span></div>
        <div class="vframes" data-m="frames">${picks.map(i => frameBtn(rv, i)).join("")}</div></div>`
    : rv.evidence_url ? `<div class="vproof"><div class="vproof-head"><span class="t-label">Proof</span><span class="meta">${labels.length} checks</span></div><a class="vsheet" href="${esc(rv.evidence_url)}" target="_blank" rel="noopener"><img src="${esc(rv.evidence_url)}" alt="Contact sheet for session ${rv.id}"></a></div>`
    : `<div class="vproof">${renderWindows(rv.windows) || `<p class="meta">No frames for this one. The camera was off.</p>`}</div>`;
  parkPinch();
  $("#now").innerHTML = `<article class="al-card vcard vcard--${v}" data-m="card" role="status" aria-live="polite" aria-label="Verdict">
    <button type="button" class="al-iconbtn al-iconbtn--sm vclose" data-act="dismiss" data-id="${rv.id}" aria-label="Dismiss verdict">${VI("x", 16)}</button>
    <div class="vtop">
      <div class="vpinch"><span class="pn-slot"></span></div>
      <div class="vmain">
        <span class="meta">${esc(name)} · ${clockT(rv.started_at)} to ${clockT(rv.ended_at || rv.ends_at)} · ${esc(String(of))} min claimed</span>
        <div class="vpillrow" data-m="pill">${AlibiIcons.pill(v)}<span class="t-h3">${esc(String(seen))} of ${esc(String(of))} min</span></div>
        <div class="al-meter al-meter--${v} vmeter" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${r}" aria-label="On task ${r}%. ${Math.round(partAt * 100)}% counts as partly, ${Math.round(doneAt * 100)}% as done.">
          <div class="al-meter__track"><div class="al-meter__fill" data-m="meter" style="transform:scaleX(${Math.min(1, ratio).toFixed(3)})"></div></div>
          <span class="al-meter__tick" style="left:${partAt * 100}%" aria-hidden="true"></span><span class="al-meter__tick" style="left:${doneAt * 100}%" aria-hidden="true"></span>
        </div>
      </div>
      <div class="al-stat vstat"><span class="al-stat__label">On task</span><span class="al-stat__value" data-m="pct" data-value="${r}">${r}%</span></div>
    </div>
    <p class="vsentence" data-m="line">${esc(verdictSentence(rv))}</p>
    ${proof}
    <div class="vacts" data-m="actions">
      <button type="button" class="al-btn al-btn--primary" data-say="${esc(`${rv.habit} for ${rv.declared_min || 25} minutes`)}">Go again</button>
      ${rv.reel_url || labels.length ? `<button type="button" class="al-btn al-btn--secondary" data-act="reel" data-id="${rv.id}">${VI("film", 16)}Watch reel</button>` : ""}
      ${labels.length ? `<button type="button" class="al-btn al-btn--quiet" data-act="fix" data-id="${rv.id}">Fix a moment</button>` : ""}
    </div></article>`;
  placePinch($("#now"));
  AlibiMoments.verdict(rv, $("#now"), {animate: !!anim});
}

/* ---------- idle: latest verdict, the proof one glance below the composer ---------- */
function renderLatest() {
  const box = $("#latest"); if (!box) return;
  const mode = document.body.classList.contains("verdict") ? "verdict" : "other";
  const s = mode === "verdict" ? null : (lastSessions || []).find(x => x.verdict && x.ended_at && x.id !== liveSess?.id);
  const sig = s ? `${s.id}:${s.verdict}:${Math.round((s.on_task_ratio || 0) * 100)}` : "";
  if (box.dataset.sig === sig) return;
  box.dataset.sig = sig;
  if (!s) { box.innerHTML = ""; return; }
  const name = dispName(s.habit, s.label), labels = s.labels || [], picks = pickFrames(labels, 3, s.verdict, s.on_task_ratio);
  const off = labels.filter(l => l.label !== "on_task"), top = off.length ? off[0].label : null;
  const why = top ? ` ${({phone: "The phone", off_task: "Something else", idle: "Idle", absent: "Away"})[top]} had ${off.length === 1 ? "one check" : off.length + " checks"}.` : "";
  box.innerHTML = `<article class="al-card latestcard" aria-label="Latest verdict">
    <div class="latest-txt"><span class="t-label">Latest verdict</span>
      <div class="vpillrow">${AlibiIcons.pill(s.verdict)}<span class="t-h3">${esc(name)}, ${esc(String(s.verified_min ?? "—"))} of ${esc(String(s.declared_min ?? "—"))} min</span></div>
      <span class="meta">Finished ${whenT(s.ended_at)}.${esc(why)}</span></div>
    ${picks.length ? `<div class="latest-frames">${picks.map(i => frameBtn(s, i, "mini")).join("")}</div>` : ""}
    <button type="button" class="al-btn al-btn--secondary al-btn--sm" data-act="proof" data-id="${s.id}">${VI("eye", 16)}See proof</button>
  </article>`;
}
function renderNextLine() {
  const el = $("#nextLine"); if (!el) return;
  const t = typeof nextPlanText === "function" ? nextPlanText() : "";
  const html = t ? `${VI("calendar", 16)}<span>${esc(t)}</span>` : "";
  if (el.dataset.html !== html) { el.dataset.html = html; el.innerHTML = html; }
}

function onNowClick(e) {
  const f = e.target.closest(".vframe[data-fix]"); if (f) return openPop(f);
  const d = e.target.closest(".strip .dot"); if (d) return openPop(d);
  if (e.target.closest("#endBtn")) return endNow();
  if (e.target.closest("#cancelBtn")) return cancelNow();
  const sy = e.target.closest("[data-say]"); if (sy) return say(sy.dataset.say);
  const a = e.target.closest("[data-act]"); if (!a) return;
  const id = +a.dataset.id;
  if (a.dataset.act === "dismiss") { dismissedVerdict = id; try { sessionStorage.setItem("alibi.dismissedVerdict", id); } catch {} nowSig = ""; pollState(); renderLatest(); }
  if (a.dataset.act === "reel") playReel(`/api/reel?session=${id}`, `Session #${id}`);
  if (a.dataset.act === "fix" || a.dataset.act === "proof") gotoSession(id);
}
$("#now").addEventListener("click", onNowClick);
$("#latest").addEventListener("click", onNowClick);

function renderWindows(ws) {
  if (!ws || !ws.length) return "";
  return `<div class="wins-head t-label">Windows, share of screen time</div>` + ws.slice(0, 6).map(w => `
    <div class="win"><span class="title" title="${esc(w.title)}">${AlibiIcons.dot(w.label, 8)}<span>${esc(w.title)}</span></span><span class="pct">${pct(w.share)}</span>
    <span class="bar"><i style="--c:${cvar(w.label)};transform:scaleX(${(w.share || 0).toFixed(3)})"></i></span></div>`).join("");
}

async function endNow() {
  const b = $("#endBtn"); if (b) { b.disabled = true; b.lastChild.textContent = "Finishing…"; }
  $("#convo").innerHTML = `<div class="line alibi"><span class="who">Alibi</span><span class="txt pending">Closing the session and weighing the evidence…</span></div>`;
  try { const r = await api("/api/end", {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"}); reply(r.reply); }
  catch { reply("That session didn't close. Check Alibi is running, then try again."); }
  pollState(); refreshSlow();
}

async function cancelNow(undo, removeHabit) {
  const b = $("#cancelBtn"); if (b) { b.disabled = true; b.lastChild.textContent = "Cancelling…"; }
  try {
    const j = await postJSON("/api/session/cancel", {undo: !!undo, remove_habit: removeHabit || null});
    reply([j.reply, j.reply_extra].filter(Boolean).join(" "));
    if (j.removed) await Promise.all([loadHabits(), loadView()]);
  } catch { reply("That didn't cancel. Check Alibi is running, then try again."); }
  pollState(); refreshSlow();
}

/* ---------- "isn't one of your habits yet" → one-tap add ---------- */
async function suggestCard(text) {
  let j; try { j = await api(`/api/habits/suggest?text=${encodeURIComponent(text)}`); } catch { return; }
  const d = j.draft; if (!d) return;
  const el = document.createElement("div"); el.className = "sugcard";
  el.innerHTML = `<button type="button" class="al-btn al-btn--primary">${esc(j.card_label || `Add “${d.name}”`)} and start</button><button type="button" class="al-btn al-btn--secondary">Set it up first</button>`;
  $("#convo").appendChild(el);
  el.firstElementChild.addEventListener("click", async () => {
    el.querySelectorAll("button").forEach(b => b.disabled = true);
    try {
      const r = await postJSON("/api/habits/add", {name: d.name, minutes: d.minutes, check: d.check, schedule: [], start: true});
      reply(r.reply); el.remove(); await Promise.all([loadHabits(), loadView()]); pollState(); refreshSlow();
      if (/^Started\b/.test(r.reply || "")) showToast("started", `${r.label} added and started.`, "var(--accent)", [{label: "Undo", undo: () => cancelNow(true, r.key)}], 5000);
    }
    catch (err) { reply(`Couldn't add it: ${err.message}`); el.querySelectorAll("button").forEach(b => b.disabled = false); }
  });
  el.lastElementChild.addEventListener("click", async () => {
    if (typeof openHabits === "function") return openHabits(null, {name: d.name, check: d.check, minutes: d.minutes});
    await openSetup("Habits");
    habModel.push({key: "", isNew: true, h: {label: d.name, modality: CHECK_TO_MOD[d.check] || "physical", default_min: d.minutes || 25, weekly_target_min: (d.minutes || 25) * 3, schedule: [], calendar: true}});
    renderHabitsEd(); setMsg("unsaved changes");
    $("#habitsEd").lastElementChild?.scrollIntoView({behavior: "smooth", block: "center"});
  });
}
