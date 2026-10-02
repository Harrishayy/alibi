"""Turn a session's events into on_task_ratio + verdict + evidence.

physical -> camera labels; digital -> laptop window titles (classified once, cached); hybrid -> per-minute OR of both.
"""
import json, re, time
from collections import Counter
from . import config, db, evidence, llm

DISTRACTIONS = ("youtube", "netflix", "twitter", "x.com", "reddit", "instagram", "tiktok", "twitch", "messages",
                "whatsapp", "discord", "facebook", "prime video", "disney+", "spotify")
# Proper names for a title, the way Screen Time / Opal show "YouTube", never half a tab title.
SITE_NAMES = {"youtube": "YouTube", "netflix": "Netflix", "twitter": "Twitter", "x.com": "X", "reddit": "Reddit",
              "instagram": "Instagram", "tiktok": "TikTok", "twitch": "Twitch", "whatsapp": "WhatsApp",
              "discord": "Discord", "facebook": "Facebook", "prime video": "Prime Video", "disney+": "Disney+",
              "spotify": "Spotify", "chatgpt": "ChatGPT", "claude": "Claude", "gmail": "Gmail", "slack": "Slack",
              "google meet": "Google Meet", "meet -": "Google Meet", "zoom": "Zoom", "linkedin": "LinkedIn",
              "github": "GitHub", "stack overflow": "Stack Overflow", "cppreference": "cppreference",
              "learncpp": "learncpp", "greenhouse": "Greenhouse", "workday": "Workday", "lever": "Lever",
              "messages": "Messages"}
BROWSERS = ("google chrome", "chrome", "safari", "arc", "firefox", "microsoft edge", "brave browser", "opera",
            "vivaldi", "orion", "zen", "dia")
# Editors, IDEs and terminals are where code happens, even when the title is empty (Rize's default IDE category).
CODE_APPS = {"cursor", "code", "visual studio code", "vscodium", "xcode", "clion", "iterm2", "iterm", "terminal",
             "warp", "zed", "sublime text", "intellij idea", "pycharm", "ghostty", "kitty", "alacritty", "wezterm",
             "nova", "android studio", "goland", "rider", "webstorm", "neovim", "vim", "emacs", "windsurf"}
CODE_HINTS = ("code", "editor", "compiler", "terminal", "ide", "programming")
STOP = {"with", "or", "and", "the", "on", "in", "of", "a", "to", "files", "content", "next", "screen", "docs",
        "working", "hands", "holding", "output", "pages"}
TITLE_SYSTEM = ('You decide whether each window title is on task for a habit. Reply with JSON only: '
                '{"labels": {"<title>": "on_task|off_task", ...}}')


def verdict_for(ratio: float) -> str:
    t = config.habits().get("verdict", {})
    return "done" if ratio >= t.get("done", 0.7) else "partial" if ratio >= t.get("partial", 0.4) else "slacked"


def _outside_breaks(con, session, events):
    br = db.breaks(con, session["id"])
    if not br:
        return events
    return [e for e in events if not any(a <= e["ts"] < b for a, b in br)]


def camera_labels(con, session) -> list[dict]:
    """Camera label events with the user's corrections applied, minus samples taken during a declared break."""
    cam = db.session_events(con, session["id"], source="camera")
    fixes = {round(e["payload"]["target_ts"], 3): e["payload"]["label"]
             for e in db.session_events(con, session["id"], source="user") if e["kind"] == "correction"
             and "target_ts" in e["payload"]}
    for e in cam:
        new = fixes.get(round(e["ts"], 3))
        if new and new != e["payload"]["label"]:
            e["payload"] = {**e["payload"], "corrected_from": e["payload"]["label"], "label": new}
    return _outside_breaks(con, session, cam)


def correct(con, session_id: int, target_ts: float | None, label: str, title: str | None = None) -> str:
    """Record a correction and re-score the (finished or live) session.

    Camera sample: target_ts must be within 1 s of a sample. Digital: pass `title` (or a ts that hits a window
    event) and the title is re-labelled in title_cache, so every future session learns it."""
    if label not in db.LABELS:
        raise ValueError(f"label must be one of {db.LABELS}")
    s = db.get_session(con, session_id)
    if s is None:
        raise LookupError(f"no session {session_id}")
    cam = db.session_events(con, session_id, source="camera")
    hit = min(cam, key=lambda e: abs(e["ts"] - target_ts), default=None) if target_ts is not None else None
    if hit and abs(hit["ts"] - target_ts) <= 1.0 and not title:
        old = camera_labels(con, s)
        was = next((e["payload"]["label"] for e in old if e["ts"] == hit["ts"]), hit["payload"]["label"])
        db.add_event(con, "user", "correction", {"target_ts": hit["ts"], "label": label, "was": was,
                                                 "note": hit["payload"].get("note", "")}, session_id=session_id)
        what = hit["payload"].get("note") or config.LABEL_TEXT.get(was, was).lower()
        at = time.strftime("%H:%M", time.localtime(hit["ts"]))
        new = config.LABEL_TEXT.get(label, label).lower()
        if was == label:
            reply = f"{at} already says {new} — nothing to change."
        else:
            reply = f"Changed that moment ({at}) to {new}."
            # One camera fix is one moment. Only the same fix twice becomes a rule (witness._apply_lessons).
            same = sum(1 for e in con.execute(
                "SELECT e.payload FROM events e JOIN sessions s ON s.id=e.session_id WHERE e.source='user' "
                "AND e.kind='correction' AND s.habit=?", (s["habit"],))
                if (lambda p: p.get("was") == was and p.get("label") == label
                    and p.get("note", "") == hit["payload"].get("note", ""))(json.loads(e["payload"])))
            if same == 2 and config.VISION_BACKEND != "nvidia":
                reply += f" That's twice for \"{what}\" — from now on Alibi counts it as {new}."
            elif same == 2:
                reply += " Alibi will keep that in mind next time."
    else:
        if not title and target_ts is not None:
            w = min(_window_events(con, s), key=lambda e: abs(e["ts"] - target_ts), default=None)
            if w and abs(w["ts"] - target_ts) <= 1.0:
                title = evidence._title_key(w["payload"])
        if not title:
            raise ValueError("no sample at that time (ts must be within 1 s of a sample)")
        lab = "on_task" if label == "on_task" else "off_task"
        con.execute("INSERT OR REPLACE INTO title_cache(habit, title, label) VALUES (?,?,?)", (s["habit"], title, lab))
        con.commit()
        db.add_event(con, "user", "correction", {"title": title, "label": lab}, session_id=session_id)
        reply = f"Got it — \"{title[:40]}\" counts as {'work' if lab == 'on_task' else 'a distraction'} " \
                f"for {config.display_name(s['habit'])} from now on."
    if s["status"] != "done":
        return reply + " It'll count in the final score."
    old_v = s["verdict"]
    finalise(con, s, artefact=s["artefact"], keep_end=True)
    reel = config.DATA_DIR / "reels" / f"session-{session_id}.mp4"
    reel.unlink(missing_ok=True)                 # the daemon rebuilds it with the corrected labels
    s2 = db.get_session(con, session_id)
    word = {"done": "done ✓", "partial": "partial", "slacked": "slacked"}[s2["verdict"]]
    return f"{reply} New score: {s2['on_task_ratio']:.0%} — {'still ' if s2['verdict'] == old_v else 'now '}{word}."


def close(con, session, artefact: str | None = None, ended_at: float | None = None) -> dict | None:
    """The only way a live session ends. Atomic: returns None if someone else already closed it."""
    import time
    if not db.claim_session(con, session["id"], ended_at or time.time()):
        return None
    s = db.get_session(con, session["id"])
    line = finalise(con, s, artefact=artefact, keep_end=True)
    s = db.get_session(con, session["id"])
    return {"line": line, "voice": voice(con, s), "session": s}


def finalise(con, session, artefact: str | None = None, keep_end: bool = False) -> str:
    """Score the session, render evidence, close it. Returns a one-line numeric summary (the dashboard's record).

    on_task_ratio = (share of samples on task) x (share of the declared time that actually happened), so ending a
    600-minute claim after 10 s is 'slacked', and report.verified = on_task_ratio x declared = seen ratio x elapsed."""
    cam = camera_labels(con, session)
    win = _window_events(con, session)
    mod = session["modality"]
    if mod == "physical" or (mod == "hybrid" and not win):
        marks = [e["payload"]["label"] == "on_task" for e in cam]
    elif mod == "digital" or not cam:
        labels = classify_titles(con, session["habit"], {evidence._title_key(e["payload"]) for e in win})
        marks = [labels.get(evidence._title_key(e["payload"])) == "on_task" for e in win]
    else:
        marks = _hybrid_marks(con, session, cam, win)
    end_kw = {"ended_at": session["ended_at"]} if keep_end else {}
    name = config.display_name(session["habit"])
    if not marks:
        db.finish_session(con, session["id"], on_task_ratio=0.0, verdict="slacked", artefact=artefact, **end_kw)
        return f"{name}: no evidence collected — logged as slacked."
    seen = sum(marks) / len(marks)
    probe = dict(session)
    probe["ended_at"] = session["ended_at"] if keep_end else None
    cov = _covered(con, probe)
    ratio, sig_reason = _fuse(con, probe, seen * cov, cov)
    verdict = verdict_for(ratio)
    path = evidence.contact_sheet(session, cam, ratio, verdict) if cam else None
    db.finish_session(con, session["id"], on_task_ratio=ratio, verdict=verdict, evidence_path=path, artefact=artefact,
                      **end_kw)
    line = f"{name}: {verdict.upper()} — {ratio:.0%} on task"
    if cov < 0.98:
        line += f" (seen {seen:.0%} of {round(cov * session['declared_min'])} of {session['declared_min']} min)"
    if cam:
        cnt = Counter(e["payload"]["label"] for e in cam)
        off = ", ".join(f"{l.replace('_', ' ')} ×{n}" for l, n in cnt.items() if l != "on_task")
        line += f" over {_plural(len(cam), 'sample')}" + (f" ({off})" if off else "")
    if win and mod != "physical":
        top = window_breakdown(con, session)[:2]
        line += "; screen: " + ", ".join(f"{short_title(w['title'])} {w['share']:.0%}" for w in top)
    if sig_reason:
        line += f"; lowered by phone/Mac signals: {sig_reason[0].lower() + sig_reason[1:]}"
    return line + "."


def _fuse(con, session, ratio: float, cov: float) -> tuple[float, str | None]:
    """Phone/Mac signals (docs/SIGNALS.md) may LOWER the score with a stated reason; they never raise it. The decision
    is recorded as events(source='alibi', kind='signals_cap') so the dashboard and the voice can say why."""
    try:
        from . import signals
        new, reason, detail = signals.cap(con, session, ratio, cov)
        prior = signals.last_cap(con, session["id"])
        if reason and new < ratio:
            db.add_event(con, "alibi", "signals_cap", {"capped": True, "from": round(ratio, 4), "to": new,
                                                       "reason": reason, **detail}, session_id=session["id"])
            return min(ratio, new), reason
        if prior:
            db.add_event(con, "alibi", "signals_cap", {"capped": False, **detail}, session_id=session["id"])
    except Exception as e:
        print(f"[alibi] signal fusion skipped: {e!r}", flush=True)
    return ratio, None


LATE_WINDOW_S = 12 * 3600          # phone rows for a session that ended this recently can still lower its score


def refuse_late(con, session_id: int, now: float | None = None) -> dict | None:
    """Phone rows usually arrive after the verdict (BGAppRefresh / the 180 s poll). Re-run signal fusion on a finished
    session and LOWER its score if the late rows say so (never raise). Records signals_cap {late: true}.
    Returns {from, to, verdict, reason} when the score changed, else None. Never raises."""
    try:
        from . import signals
        s = db.get_session(con, session_id)
        if s is None or s["status"] != "done" or s["on_task_ratio"] is None or not s["ended_at"]:
            return None
        s = dict(s)
        if (now or time.time()) - s["ended_at"] > LATE_WINDOW_S:
            return None
        old = float(s["on_task_ratio"])
        if old <= 0:
            return None
        cov = _covered(con, s)
        new, reason, detail = signals.cap(con, s, old, cov)
        if not reason or new >= old - 0.005:
            return None
        new = round(min(old, new), 4)
        verdict = verdict_for(new)
        con.execute("UPDATE sessions SET on_task_ratio=?, verdict=? WHERE id=? AND status='done'",
                    (new, verdict, session_id))
        con.commit()
        db.add_event(con, "alibi", "signals_cap", {"capped": True, "late": True, "from": round(old, 4), "to": new,
                                                   "verdict_was": s["verdict"], "verdict": verdict,
                                                   "reason": reason, **detail}, session_id=session_id)
        return {"from": round(old, 4), "to": new, "verdict": verdict, "verdict_was": s["verdict"], "reason": reason}
    except Exception as e:
        print(f"[alibi] late signal fusion skipped: {e!r}", flush=True)
        return None


def _cap_reason(con, session) -> str | None:
    try:
        from . import signals
        c = signals.last_cap(con, session["id"])
        return c.get("reason") if c else None
    except Exception:
        return None


def _covered(con, session) -> float:
    """Share of the declared time that both happened AND was watched: min(time coverage, evidence coverage)."""
    t, e, _ = coverage_parts(con, session)
    return min(t, e)


def coverage_parts(con, session) -> tuple[float, float, float]:
    """(time_cov, evidence_cov, dark_s) — dark_s: total length of the unwatched stretches, for the copy.

    time_cov: elapsed wall-clock (minus breaks) / declared. evidence_cov: the same, minus every stretch with no
    sample longer than a grace of max(3 cadences, 2 min) — a closed lid isn't an alibi (Beeminder: no data = derail)."""
    import time
    start = session["started_at"]
    end = min(session["ended_at"] or time.time(), session["ends_at"])
    br = db.breaks(con, session["id"], end)
    brk = sum(max(0.0, min(b, end) - max(a, start)) for a, b in br)
    declared = max(60.0, session["declared_min"] * 60)
    elapsed = max(0.0, end - start - brk)
    time_cov = max(0.0, min(1.0, elapsed / declared))
    mod = session["modality"]
    ts = []
    if mod in ("physical", "hybrid"):
        ts += [e["ts"] for e in camera_labels(con, session)]
    if mod in ("digital", "hybrid"):
        ts += [e["ts"] for e in _window_events(con, session)]
    cadence = {"physical": config.SAMPLE_EVERY_S, "digital": config.LAPTOP_EVERY_S}.get(
        mod, min(config.SAMPLE_EVERY_S, config.LAPTOP_EVERY_S))
    grace = max(3.0 * cadence, 120.0)
    pts = [start] + sorted(t for t in ts if start <= t <= end) + [end]
    unobserved = dark = 0.0
    for a, b in zip(pts, pts[1:]):
        gap = (b - a) - sum(max(0.0, min(y, b) - max(x, a)) for x, y in br)
        if gap > grace:
            unobserved += gap - grace
            dark += gap
    ev_cov = max(0.0, min(1.0, (elapsed - unobserved) / declared))
    return time_cov, min(time_cov, ev_cov), dark


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' * (n != 1)}"


def stats(con, session, cam=None, windows=None) -> dict:
    """Numbers behind a verdict, for the dashboard's 'why this verdict' line."""
    cam = camera_labels(con, session) if cam is None else cam
    tcov, cov, dark = coverage_parts(con, session)
    cam_ratio = (sum(e["payload"]["label"] == "on_task" for e in cam) / len(cam)) if cam else None
    scr = None
    if session["modality"] != "physical":
        windows = window_breakdown(con, session, top=99) if windows is None else windows
        scr = sum(w["share"] for w in windows if w["label"] == "on_task") if windows else None
    r = session["on_task_ratio"]
    seen = (r / cov) if (r is not None and cov > 0) else None
    elapsed = round(cov * session["declared_min"])
    how = {"physical": "how many camera checks showed you working", "digital": "how much screen time was on task",
           "hybrid": "minutes where the camera or the screen showed the work"}[session["modality"]]
    parts = []
    if cam_ratio is not None:
        parts.append(f"camera {cam_ratio:.0%}")
    if scr is not None:
        parts.append(f"screen {scr:.0%}")
    why = f"Score = {how}" + (f" ({', '.join(parts)})" if parts else "")
    if cov < 0.98 and session["status"] == "done":
        if tcov - cov > 0.02:
            dk = min(session["declared_min"], round(dark / 60))
            why += f"; nothing was seen for {dk} of {session['declared_min']} min (laptop asleep?)"
        else:
            why += f"; only {elapsed} of {session['declared_min']} min happened"
    cap_reason = _cap_reason(con, session) if session["status"] == "done" else None
    if cap_reason:
        why += f"; lowered because {cap_reason[0].lower() + cap_reason[1:]}"
    t = config.habits().get("verdict", {})
    done_at, partial_at = float(t.get("done", 0.7)), float(t.get("partial", 0.4))
    score_line = None
    if r is not None:
        if r >= done_at:
            score_line = f"You were on task {r:.0%} — a full tick."
        elif r >= partial_at:
            score_line = f"You were on task {r:.0%} — {round((done_at - r) * 100)}% short of a full tick."
        else:
            score_line = f"You were on task {r:.0%} — {round((partial_at - r) * 100)}% short of a partial."
    return {"done_at": done_at, "partial_at": partial_at, "score_line": score_line, "coverage": round(cov, 3), "time_coverage": round(tcov, 3), "elapsed_min": elapsed, "seen_ratio": seen, "camera_ratio": cam_ratio,
            "screen_ratio": scr, "verified_min": round((r or 0) * session["declared_min"]),
            "signals_reason": cap_reason, "why": why + "."}


def voice(con, s) -> str:
    """The dry witness's verdict line for notify(), plus why phone/Mac signals lowered it, if they did."""
    line = _voice(con, s)
    reason = _cap_reason(con, s)
    return f"{line} {reason}." if reason and reason.lower() not in line.lower() else line


def _voice(con, s) -> str:
    name = config.display_name(s["habit"])
    v, r = s["verdict"], s["on_task_ratio"] or 0
    cam = camera_labels(con, s)
    tcov, cov, dark = coverage_parts(con, s)
    elapsed = round(cov * s["declared_min"])
    early = f" Ended after {elapsed} min of {s['declared_min']}." if cov < 0.9 else ""
    if not cam and not _window_events(con, s):
        return f"{name}: no evidence. Logged as slacked."
    if tcov - cov > 0.1 and v != "done":
        dm, dk = s["declared_min"], min(s["declared_min"], round(dark / 60))
        return (f"{name}: {v}. No evidence for {dk} of {dm} min — the laptop slept "
                f"or the camera couldn't see; {max(0, min(round(r * dm), dm - dk))} min seen.")
    if cov < 0.5 and v != "done":
        return (f"{name}: {v}. Ended after {elapsed} min of {s['declared_min']} — "
                f"a claim isn't evidence; {round(r * s['declared_min'])} min seen.")
    if v == "done":
        return f"{name}, {elapsed} min. Alibi checks out." + (" Corrected by you." if any(
            e["payload"].get("corrected_from") for e in cam) else "")
    off = Counter(e["payload"]["label"] for e in cam if e["payload"]["label"] != "on_task")
    worst, n = (off.most_common(1)[0] if off else (None, 0))
    pct = f"{r:.0%}"
    if s["modality"] != "physical":
        win = off_task_names(con, s)
        if win and (not cam or win[0][1] >= 0.3):
            title, share = win[0]
            if v == "slacked":
                if share >= 0.5:
                    when = "the whole time" if share >= 0.9 else f"{share:.0%} of the time"
                    return f"{name}: slacked. The screen was {title} {when}.{early}"
                names = [n for n, _ in win[:4]]
                return (f"{name}: slacked. {pct} on task. The screen was {join_names(names)} — "
                        f"none of it {config.spoken_name(s['habit'])}.{early}")
            return f"{name}: partial. {pct} on task; {title} took {share:.0%} of the screen.{early}"
    def what(l: str, n: int) -> str:
        return {"phone": f"{n} look{'s' * (n != 1)} at the phone",
                "absent": "the desk was empty once" if n == 1 else f"the desk was empty {n} times",
                "idle": f"{n} sample{'s' * (n != 1)} of staring",
                "off_task": f"{n} sample{'s' * (n != 1)} of something else"}[l]
    if v == "partial":
        tail = (", " + ", ".join(what(l, k) for l, k in off.most_common(2))) if worst else ""
        return f"{name}: partial. {pct} on task{tail}.{early}"
    seen = config.LABEL_TEXT.get(worst, "nothing").lower() if worst else "nothing useful"
    return f"{name}: slacked. {pct} on task. The camera mostly saw: {seen}.{early}"


def _window_events(con, session):
    end = min(session["ended_at"] or session["ends_at"], session["ends_at"])
    return _outside_breaks(con, session, [e for e in db.events_between(con, session["started_at"], end, "laptop")
                                          if e["payload"].get("app") and e["ts"] < end])   # half-open: bell isn't evidence


def window_breakdown(con, session, top: int = 5) -> list[dict]:
    win = _window_events(con, session)
    labels = classify_titles(con, session["habit"], {evidence._title_key(e["payload"]) for e in win})
    return evidence.title_summary(win, labels, top=top)


def _hybrid_marks(con, session, cam, win) -> list[bool]:
    labels = classify_titles(con, session["habit"], {evidence._title_key(e["payload"]) for e in win})
    minutes = {}
    for e in cam:
        minutes.setdefault(int((e["ts"] - session["started_at"]) // 60), []).append(e["payload"]["label"] == "on_task")
    for e in win:
        minutes.setdefault(int((e["ts"] - session["started_at"]) // 60), []).append(
            labels.get(evidence._title_key(e["payload"])) == "on_task")
    return [any(v) for _, v in sorted(minutes.items())]


def classify_titles(con, habit: str, titles: set[str]) -> dict[str, str]:
    """title_cache first; uncached titles go to ONE batch LLM call (or keyword rules offline); write back."""
    titles = {t for t in titles if t}
    cached = {r["title"]: r["label"] for r in con.execute(
        f"SELECT title, label FROM title_cache WHERE habit=? AND title IN ({','.join('?' * len(titles))})",
        (habit, *titles))} if titles else {}
    todo = sorted(titles - cached.keys())
    if todo:
        fresh = {}
        if config.TEXT_READY:
            try:
                h = config.habits()["habits"].get(habit, {})
                out = llm.chat_json(TITLE_SYSTEM, f"Habit: {habit}. On task looks like: {h.get('on_task_looks_like')}\n"
                                                  "Titles:\n" + "\n".join(todo), max_tokens=1500)
                fresh = {t: l for t, l in out.get("labels", {}).items() if t in todo and l in ("on_task", "off_task")}
            except Exception:
                fresh = {}
        for t in todo:
            fresh.setdefault(t, _rule_label(habit, t))
        con.executemany("INSERT OR REPLACE INTO title_cache(habit, title, label) VALUES (?,?,?)",
                        [(habit, t, l) for t, l in fresh.items()])
        con.commit()
        cached.update(fresh)
    return cached


def _rule_label(habit: str, title: str) -> str:
    t = title.lower()
    if any(d in t for d in DISTRACTIONS):
        return "off_task"
    if is_code_app(title) and _codes(habit):
        return "on_task"
    h = config.habits()["habits"].get(habit, {})
    words = {habit, *map(str, h.get("aliases", []))}
    words |= {w for w in re.findall(r"[\w.+#-]+", str(h.get("on_task_looks_like", "")).lower())
              if len(w) > 2 and w not in STOP}
    return "on_task" if any(re.search(rf"(?<![\w]){re.escape(w.lower())}", t) for w in words) else "off_task"


def short_title(key: str, url: str = "") -> str:
    """'Google Chrome — But how do AI images… - YouTube - Google Chrome – Work' -> 'YouTube'; 'Cursor' -> 'Cursor'.

    Known site/app keyword first; else for a browser, the site from the URL host or the tab's last short segment;
    else the app name."""
    key = (key or "").strip()
    app, _, title = key.partition(" — ")
    low = f"{key} {url}".lower()
    if app.lower() not in CODE_APPS or not title:
        for kw, name in SITE_NAMES.items():
            if kw in low:
                return name
    if app.lower() in BROWSERS:
        host = re.sub(r"^www\.", "", re.sub(r"^\w+://", "", url or "").split("/")[0])
        if host:
            return host
        parts = [p.strip() for p in re.split(r" [-|–—] ", title) if p.strip()]
        parts = [p for p in parts if p.lower() not in BROWSERS]
        if parts and len(parts) > 1:
            parts = parts[:-1] if len(parts) > 2 else parts          # 'page - site - profile' -> drop profile
        site = parts[-1] if parts else ""
        return site if site and len(site) <= 24 else (app or "the browser")
    return app or "something else"


def is_code_app(key: str) -> bool:
    return key.partition(" — ")[0].strip().lower() in CODE_APPS


def _codes(habit: str) -> bool:
    h = config.habits()["habits"].get(habit, {})
    return any(re.search(rf"\b{w}", str(h.get("on_task_looks_like", "")).lower()) for w in CODE_HINTS)


def off_task_names(con, session) -> list[tuple[str, float]]:
    """[(short name, share of screen)] for off-task window time, merged by short name, biggest first."""
    agg: dict[str, float] = {}
    for w in window_breakdown(con, session, top=99):
        if w["label"] != "on_task":
            n = short_title(w["title"])
            agg[n] = agg.get(n, 0.0) + w["share"]
    return sorted(agg.items(), key=lambda kv: -kv[1])


def join_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
