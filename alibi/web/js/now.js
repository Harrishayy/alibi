/* now.js: composer: chips, say/reply, suggestCard; Now: renderNow, live windows, end/cancel, countUp, renderVerdict, confetti. Classic script; load order core, now, week, sessions, setup, onboarding, boot. */
/* ---------- prompt ---------- */
const TAIL_CHIPS = [["How am I doing?","how am I doing"]];
const LIVE_CHIPS = [["Break 5 min","break 5"],["Add 10 min","add 10"],["How am I doing?","how am I doing"],["End","end"]];
function renderChips(habits, live) {
  if (live) { $("#chips").innerHTML = LIVE_CHIPS.map(([l, t]) => `<button class="chip" type="button" data-say="${esc(t)}">${esc(l)}</button>`).join(""); return; }
  const hs = Object.entries(habits || {}).filter(([, h]) => h && !h.source && h.default_min);
  const chips = (hs.length ? hs.map(([k, h]) => [`${h.label || hname(k)} · ${h.default_min} min`, `${k} for ${h.default_min} minutes`])
                           : []).concat(TAIL_CHIPS);
  $("#chips").innerHTML = chips.map(([l, t]) => `<button class="chip" type="button" data-say="${esc(t)}">${esc(l)}</button>`).join("");
}
renderChips();
$("#chips").addEventListener("click", e => { const b = e.target.closest(".chip"); if (b) say(b.dataset.say || b.textContent); });
$("#sayForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#sayInput").value.trim(); if (v) say(v); });

async function say(text) {
  $("#sayInput").value = ""; $("#sayBtn").disabled = true;
  const convo = $("#convo");
  convo.innerHTML = `<div class="line you"><span class="who">You</span><span class="txt">${esc(text)}</span></div>
    <div class="line alibi"><span class="who">Alibi</span><span class="txt pending">thinking it over…</span></div>`;
  try {
    const r = await api("/api/say", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text})});
    reply(r.reply);
    if (/^Started\b/.test(r.reply || "")) AlibiMoments.sessionStart($("#sayForm"), $("#now"));
    if (/isn.t one of your habits yet|not a habit yet/i.test(r.reply || "")) suggestCard(text);
  } catch (err) { reply("Alibi isn't running right now. Open the Alibi app, then try again."); }
  $("#sayBtn").disabled = false;
  pollState(); refreshSlow();
}
function reply(t) {
  const el = $("#convo .line.alibi .txt");
  if (el) { el.classList.remove("pending"); el.textContent = plain(t) || "(no reply)"; }
}

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
      $("#nowEyebrow").textContent = `session #${rv.id} · ended ${rv.ended_ago_s == null ? "" : rv.ended_ago_s < 60 ? "just now" : dur(rv.ended_ago_s) + " ago"}`;
      return;
    }
    if (nowSig !== "empty") {
      nowSig = "empty"; seenLabels = 0; lastFrame = null; liveSess = null; setMode("idle");
      if (popFor?.dataset.live) closePop();
      $("#nowEyebrow").textContent = "no session";
      box.innerHTML = "";
    }
    return;
  }
  const sig = "s" + sess.id;
  if (nowSig !== sig) {
    nowSig = sig; seenLabels = 0; lastFrame = null; setMode("live");
    if (popFor?.dataset.live) closePop();
    const hasCam = sess.modality !== "digital";
    box.innerHTML = `<div class="now" id="nowGrid">
      <div>
        <div class="eyebrow">in progress · ${esc(CHECK_WORD[sess.modality] || "checked by Alibi")}</div>
        <div class="now-habit">${esc(dispName(sess.habit, sess.label))}</div>
        <div class="now-sub" id="nowSub"></div>
        <div class="clock">
          <div class="ring"><svg viewBox="0 0 120 120"><circle class="track" cx="60" cy="60" r="54" fill="none" stroke-width="4"/>
            <circle class="arc" id="arc" cx="60" cy="60" r="54" fill="none" stroke-width="4" stroke-dasharray="339.29" stroke-dashoffset="339.29"/></svg>
            <div class="t"><div><span id="left">--:--</span><small id="leftLbl">left</small></div></div></div>
          <div><div class="stat-big" id="otk">—</div><div class="stat-lbl" id="otkLbl">on task so far</div></div>
        </div>
        <div class="driftline" id="drift"></div>
        <div class="liveacts" id="liveActs"></div>
        <div class="seenline" id="seenLine"></div>
      </div>
      <div>
        ${hasCam ? `<div class="frame" id="frame"><div class="nofeed">The first photo arrives in a moment.<br>Photos stay on this Mac.</div></div>` : ""}
        ${hasCam ? `<div class="eyebrow" style="margin-top:16px">each square is one check — tap one if Alibi got it wrong</div><div class="strip" id="strip" role="toolbar" aria-label="Checks so far — arrow keys to move, 1 to 5 to fix"></div>
        <div class="legend">${LABELS.map(l => `<span style="--c:${cvar(l)}">${LBL_TXT[l]}</span>`).join("")}</div>` : ""}
        <div class="wins" id="wins"></div>
      </div></div>`;
  }
  $("#nowEyebrow").textContent = `live`;
  $("#nowSub").textContent = `${hm(sess.declared_min)} · started ${clockT(sess.started_at)} · ends ${clockT(sess.ends_at)}${sess.nudges ? ` · ${sess.nudges} reminder${sess.nudges === 1 ? "" : "s"}` : ""}`;
  const left = sess.left_s ?? Math.max(0, sess.ends_at - now);
  const brk = sess.on_break;
  $("#left").textContent = brk ? mmss(brk.left_s) : mmss(left);
  $("#leftLbl").textContent = brk ? "break" : "left";
  const prog = sess.progress ?? 0;
  $("#arc").style.strokeDashoffset = (339.29 * (1 - Math.min(1, Math.max(0, prog)))).toFixed(2);
  const cur = (sess.recent || [])[ (sess.recent || []).length - 1 ] || sess.last_seen?.label;
  const grid = $("#nowGrid");
  grid.className = "now " + (brk ? "st-break" : sess.drifting ? "st-" + (sess.drifting.label || "phone") : cur === "on_task" ? "st-on" : cur ? "st-" + cur : "") + (sess.warming_up ? " warm" : "");
  if (sess.warming_up || sess.on_task_so_far == null) {
    const more = Math.max(1, 6 - (sess.samples || 0));
    $("#otk").innerHTML = "—"; $("#otkLbl").textContent = `Getting started… ${more} more check${more === 1 ? "" : "s"} until a score`;
  } else {
    $("#otk").innerHTML = `${Math.round(sess.on_task_so_far*100)}<sup>%</sup>`; $("#otkLbl").textContent = `on task so far · ${sess.samples} checks`;
  }
  const dr = $("#drift");
  if (brk) { dr.className = "driftline brk"; dr.textContent = `On a break · resumes in ${mmss(brk.left_s)}`; }
  else if (sess.drifting) { dr.className = "driftline"; dr.textContent = `Looks like you drifted · ${sess.drifting.label_text || LBL_UP[sess.drifting.label] || "off task"} · ${mmss(sess.drifting.since_s)}`; }
  else { dr.className = "driftline"; dr.textContent = ""; }
  const canCancel = (now - sess.started_at) < 90 && (sess.samples || 0) < 2;   // matches cli.cancellable
  const actsSig = (brk ? "b" : sess.drifting ? "d" : "n") + (canCancel ? "c" : "");
  const la = $("#liveActs");
  if (la.dataset.sig !== actsSig) {
    la.dataset.sig = actsSig;
    const acts = brk ? [["I'm back", "back", "primary"]] : sess.drifting ? [["I'm back", "back", "primary"], ["It's on task", "it's on task"], ["Break 5 min", "break 5"]] : [["Break 5 min", "break 5"], ["Add 10 min", "add 10"]];
    la.innerHTML = acts.map(([l, t, c]) => `<button type="button" class="${c || "ghostbtn"}" data-say="${esc(t)}">${esc(l)}</button>`).join("") + (canCancel ? `<button class="endbtn" id="cancelBtn" type="button" title="Started by mistake? Cancel it — nothing gets logged.">Cancel</button>` : `<button class="endbtn" id="endBtn" type="button">End now</button>`);
  }
  $("#seenLine").textContent = sess.last_seen ? (sess.last_seen.text || "").replace(/^Witness\b/, "Last check").replace(/\blooks?\b/g, m => m === "look" ? "check" : "checks") : "";

  const labels = sess.labels || [];
  const strip = $("#strip");
  if (strip) {
    if (labels.length < seenLabels) { strip.innerHTML = ""; seenLabels = 0; }
    liveSess = sess;
    const fresh = [];
    for (let i = seenLabels; i < labels.length; i++) {
      const d = document.createElement("button");
      d.type = "button"; d.className = "dot"; d.dataset.sid = sess.id; d.dataset.i = i; d.dataset.live = "1"; d.tabIndex = -1;
      if (firstState || i < labels.length - 3) d.style.animation = "none"; else fresh.push([i, d]);
      strip.appendChild(d);
    }
    seenLabels = labels.length;
    const dots = strip.querySelectorAll(".dot");
    if (dots.length && !strip.querySelector('.dot[tabindex="0"]')) dots[dots.length - 1].tabIndex = 0;
    dots.forEach((d, i) => {     // corrections recolour samples already on the strip
      const l = labels[i]; if (!l) return;
      d.style.setProperty("--c", cvar(l.label));
      d.classList.toggle("fixed", !!l.corrected_from);
      d.title = sampleTip(l);
      d.setAttribute("aria-label", `Check at ${clockT(l.ts)}: ${LBL_TXT[l.label] || l.label}. Correct it`);
    });
    fresh.forEach(([i, d]) => AlibiMoments.sample(labels[i].label, null, d));   // after the dot has its colour
    if (!labels.length && !strip.childElementCount) strip.innerHTML = `<span class="now-sub">No checks yet.</span>`;
    else strip.querySelector(".now-sub")?.remove();
  }
  const frame = $("#frame");
  if (frame && sess.last_frame_url && sess.last_frame_url !== lastFrame) {
    lastFrame = sess.last_frame_url;
    const last = labels.filter(l => l.source !== "screen").slice(-1)[0] || labels[labels.length - 1] || {};
    const note = cleanNote(last.note);
    frame.innerHTML = `<img src="${esc(lastFrame)}" alt="Latest desk frame"><span class="live">LIVE</span>
      <span class="cap"><span style="width:8px;height:8px;border-radius:2px;background:${cvar(last.label)}"></span>${esc(clockT(last.ts || now))} · ${esc(last.label_text || LBL_TXT[last.label] || last.label || "")}${note ? ` — ${esc(note)}` : ""}</span>`;
  }
  const wins = $("#wins");
  if (wins) wins.innerHTML = renderWindows(sess.windows);
}

function countUp(el, to, ms = 900) {
  const t0 = performance.now();
  const step = t => { const k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3); el.firstChild.nodeValue = Math.round(to * e); if (k < 1) requestAnimationFrame(step); };
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { el.firstChild.nodeValue = to; return; }
  requestAnimationFrame(step);
}
function renderVerdict(rv, anim) {
  const v = rv.verdict || "—", r = Math.round((rv.on_task_ratio || 0) * 100);
  const name = dispName(rv.habit, rv.label);
  const doneAt = rv.done_at ?? 0.7, partAt = rv.partial_at ?? 0.4;
  const short = Math.round(doneAt * 100) - r;
  const meterTxt = v === "done" ? `You were on task ${r}% of the time — that's a full tick.` : v === "partial" ? `You were on task ${r}% of the time — ${short}% short of a full tick.` : v === "slacked" ? `You were on task ${r}% of the time. It needs ${Math.round(partAt * 100)}% to count at all.` : "";
  const streak = (lastReport?.rows || []).find(x => x.habit === rv.habit)?.streak_days || 0;
  const sheet = rv.evidence_url ? `<div class="vsheet"><a href="${esc(rv.evidence_url)}" target="_blank" rel="noopener"><img src="${esc(rv.evidence_url)}" alt="Photos from session ${rv.id}"></a>
      <div class="cap"><span>the photos Alibi took · ${(rv.labels || []).length}</span><span>${clockT(rv.started_at)} → ${clockT(rv.ended_at || rv.ends_at)}</span></div></div>`
    : `<div class="vsheet">${renderWindows(rv.windows) || `<div class="none">No frames kept for this one.</div>`}</div>`;
  $("#now").innerHTML = `<div class="vpanel">
    <div>
      <div class="eyebrow">${esc(name)} · ${esc(hm(rv.declared_min))} planned</div>
      <div style="margin-top:18px"><span class="vpill${v === "done" && anim ? " celebrate" : ""}" style="--c:${vvar(v)}">${v === "done" ? "✓ " : ""}${esc(VWORD[v] || v)}</span>${v === "done" && streak > 1 ? `<span class="streakline">${streak} days in a row</span>` : ""}</div>
      <div class="vratio"><span id="vnum">${anim ? 0 : r}</span><sup>%</sup></div>
      <div class="stat-lbl">on task · Alibi saw ${esc(String(rv.verified_min ?? "—"))} of ${esc(String(rv.declared_min ?? "—"))} min</div>
      <div class="vmeter" style="--c:${vvar(v)}" role="img" aria-label="${r}% on task. ${Math.round(partAt*100)}% counts as partly done, ${Math.round(doneAt*100)}% as done."><div class="f" style="width:${Math.min(100, r)}%"></div>
        <div class="tk" style="left:${partAt*100}%"><span>partly ${Math.round(partAt*100)}%</span></div><div class="tk" style="left:${doneAt*100}%"><span>done ${Math.round(doneAt*100)}%</span></div></div>
      <p class="vsum">${esc(meterTxt)}</p>
      <div class="vwhy">${esc(plain(rv.summary || ""))}</div>
      <div class="vacts">
        ${rv.reel_url || (rv.labels || []).length ? `<button type="button" class="primary" data-act="reel" data-id="${rv.id}">▶&nbsp; Watch reel</button>` : ""}
        ${(rv.labels || []).length ? `<button type="button" class="ghostbtn" data-act="fix" data-id="${rv.id}">Fix a mistake</button>` : ""}
        <button type="button" class="ghostbtn" data-say="${esc(`${rv.habit} for ${rv.declared_min || 25} minutes`)}">Go again · ${esc(hm(rv.declared_min))}</button>
        <button type="button" class="ghostbtn" data-act="dismiss" data-id="${rv.id}">Done</button>
      </div>
    </div>
    ${sheet}</div>`;
  if (anim) countUp($("#vnum"), r);
  if (anim && v === "done") confetti();
  AlibiMoments.verdict(rv, $("#now"), {animate: !!anim});
}
$("#now").addEventListener("click", e => {
  const d = e.target.closest(".strip .dot"); if (d) return openPop(d);
  if (e.target.closest("#endBtn")) return endNow();
  if (e.target.closest("#cancelBtn")) return cancelNow();
  const sy = e.target.closest("[data-say]"); if (sy) return say(sy.dataset.say);
  const a = e.target.closest("[data-act]"); if (!a) return;
  const id = +a.dataset.id;
  if (a.dataset.act === "dismiss") { dismissedVerdict = id; try { sessionStorage.setItem("alibi.dismissedVerdict", id); } catch {} nowSig = ""; pollState(); }
  if (a.dataset.act === "reel") playReel(`/api/reel?session=${id}`, `Session #${id}`);
  if (a.dataset.act === "fix") gotoSession(id);
});

function renderWindows(ws) {
  if (!ws || !ws.length) return "";
  return `<div class="eyebrow" style="margin-bottom:4px">windows · share of screen time</div>` + ws.slice(0, 6).map(w => `
    <div class="win" style="--c:${cvar(w.label)}"><span class="title" title="${esc(w.title)}">${esc(w.title)}</span><span class="pct">${pct(w.share)}</span>
    <span class="bar"><i style="width:${Math.round((w.share||0)*100)}%"></i></span></div>`).join("");
}

async function endNow() {
  const b = $("#endBtn"); if (b) { b.disabled = true; b.textContent = "Ending…"; }
  $("#convo").innerHTML = `<div class="line alibi"><span class="who">Alibi</span><span class="txt pending">Closing the session and weighing the evidence…</span></div>`;
  try { const r = await api("/api/end", {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"}); reply(r.reply); }
  catch { reply("Couldn't end the session."); }
  pollState(); refreshSlow();
}

async function cancelNow(undo, removeHabit) {
  const b = $("#cancelBtn"); if (b) { b.disabled = true; b.textContent = "Cancelling…"; }
  try {
    const j = await postJSON("/api/session/cancel", {undo: !!undo, remove_habit: removeHabit || null});
    reply([j.reply, j.reply_extra].filter(Boolean).join(" "));
    if (j.removed) await Promise.all([loadHabits(), loadView()]);
  } catch { reply("Couldn't cancel it — is Alibi running?"); }
  pollState(); refreshSlow();
}

function confetti() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const box = document.createElement("div"); box.className = "confetti";
  const cols = ["var(--on_task)","var(--ink)","var(--idle)","#7FA7D9"];
  box.innerHTML = Array.from({length: 46}, (_, i) => `<i style="left:${Math.random()*100}%;background:${cols[i%4]};animation-delay:${Math.random()*.35}s;animation-duration:${1.2+Math.random()*.9}s"></i>`).join("");
  document.body.appendChild(box); setTimeout(() => box.remove(), 2600);
}
/* ---------- "isn't one of your habits yet" → one-tap add ---------- */
async function suggestCard(text) {
  let j; try { j = await api(`/api/habits/suggest?text=${encodeURIComponent(text)}`); } catch { return; }
  const d = j.draft; if (!d) return;
  const el = document.createElement("div"); el.className = "sugcard";
  el.innerHTML = `<button type="button" class="primary">${esc(j.card_label || `Add “${d.name}”`)} and start</button><button type="button" class="ghostbtn">Set it up first</button>`;
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
    await openSetup("Habits");
    habModel.push({key: "", isNew: true, h: {label: d.name, modality: CHECK_TO_MOD[d.check] || "physical", default_min: d.minutes || 25, weekly_target_min: (d.minutes || 25) * 3, schedule: [], calendar: true}});
    renderHabitsEd(); setMsg("unsaved changes");
    $("#habitsEd").lastElementChild?.scrollIntoView({behavior: "smooth", block: "center"});
  });
}
