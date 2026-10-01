"""P9 — setup checklist and habit editing, so nobody has to touch YAML or guess why the camera is dark."""
import json, os, re, shutil, subprocess, time
import yaml
from . import config, db, witness


def _check(key, label, ok, detail, fix=""):
    return {"key": key, "label": label, "ok": bool(ok), "detail": detail, "fix": "" if ok else fix}


def camera_auth() -> str:
    """authorized | denied | restricted | not_determined | unknown — asks AVFoundation, never turns the camera on."""
    try:
        return subprocess.run([str(witness.WITNESS_BIN), "--camera-auth"], capture_output=True, text=True,
                              timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def checks() -> dict:
    con = db.connect()
    out = []
    if config.CAMERA_SOURCE:
        out.append(_check("camera", "Camera", os.path.exists(config.CAMERA_SOURCE),
                          f"replaying {os.path.basename(config.CAMERA_SOURCE)}", "CAMERA_SOURCE points at a missing file"))
    else:
        a = camera_auth()
        out.append(_check("camera", "Camera", a in ("authorized", "not_determined"),
                          {"authorized": "allowed — only on during physical sessions",
                           "not_determined": "macOS will ask the first time a physical session starts"}.get(a, a),
                          "System Settings → Privacy & Security → Camera → turn on Alibi"))
    last = con.execute("SELECT payload, ts FROM events WHERE source='laptop' ORDER BY ts DESC LIMIT 1").fetchone()
    p = json.loads(last["payload"]) if last else {}
    fresh = last and time.time() - last["ts"] < 5 * 60
    out.append(_check("windows", "Window titles", fresh and p.get("title"),
                      f"last seen: {p.get('app', '?')} — {p.get('title', '')[:40]}" if fresh else "no recent window events",
                      "System Settings → Privacy & Security → Accessibility → turn on Alibi"
                      if fresh else "start Alibi; the logger runs inside the daemon"))
    out.append(_check("witness", "Vision witness", config.VISION_BACKEND in ("nvidia", "apple"),
                      {"nvidia": f"NVIDIA VLM · {config.VLM_MODEL}", "apple": "Apple Vision, on-device — frames never leave the Mac",
                       "mock": "mock (tests only)"}[config.VISION_BACKEND],
                      "unset VISION_BACKEND to use Apple Vision"))
    out.append(_check("text", "Language model", config.TEXT_READY,
                      config.LLM_MODEL if config.TEXT_READY else "rules (works offline; summaries are templated)",
                      "add NVIDIA_API_KEY + LLM_MODEL to .env for smarter parsing and summaries"))
    strava = bool(os.getenv("STRAVA_REFRESH_TOKEN"))
    out.append(_check("strava", "Strava", strava, "syncing hourly" if strava else "not connected",
                      "see PLAN.md P5: one browser approval, then python -m alibi.strava exchange <code>"))
    island = subprocess.run(["pgrep", "-f", "alibi-island|Alibi.app/Contents/MacOS"], capture_output=True).returncode == 0
    out.append(_check("island", "Notch island", island, "running — hover the notch or press ⌥⌘A" if island else "not running",
                      "./alibi.sh up  (or double-click Alibi.app)"))
    return {"checks": out, "ok": all(c["ok"] for c in out if c["key"] in ("camera", "windows", "witness", "island"))}


SLUG = re.compile(r"^[a-z][a-z0-9_]{0,23}$")


def save_habits(habits: dict) -> dict:
    """Validate and write habits back to habits.yaml, keeping verdict/nudge settings. Returns the new config."""
    clean = {}
    for key, h in habits.items():
        if not SLUG.match(key):
            raise ValueError(f"habit name {key!r}: lowercase letters, digits, underscores")
        if h.get("source") == "strava":
            clean[key] = {"source": "strava", "weekly_sessions": int(h.get("weekly_sessions", 3)),
                          "min_km": float(h.get("min_km", 5))}
            continue
        if h.get("modality") not in ("physical", "digital", "hybrid"):
            raise ValueError(f"{key}: modality must be physical, digital or hybrid")
        aliases = h.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [a.strip() for a in aliases.split(",")]
        clean[key] = {"modality": h["modality"], "aliases": [str(a) for a in aliases if str(a).strip()],
                      "weekly_target_min": max(0, int(h.get("weekly_target_min", 0))),
                      "default_min": max(1, int(h.get("default_min", 25))),
                      "on_task_looks_like": str(h.get("on_task_looks_like", key))}
    if not clean:
        raise ValueError("need at least one habit")
    cfg = config.habits()
    cfg["habits"] = clean
    path = config.HABITS_PATH
    shutil.copy(path, path.with_suffix(".yaml.bak"))
    path.write_text("# Edited from the Alibi dashboard. Keys are what the agent maps your sentence to.\n"
                    + yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    return cfg
