"""P9 — setup checklist and habit editing, so nobody has to touch YAML or guess why the camera is dark."""
import json, os, re, shutil, subprocess, time
import yaml
from . import config, db, witness


CLIENT_SEEN: dict[str, float] = {}     # R9: clients send X-Alibi-Client (island | dashboard) when they poll


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
    out.append(_check("windows", "Window titles", fresh and p.get("app"),
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
                      "Connect Strava once in the browser, then runs are checked hourly"))
    seen = CLIENT_SEEN.get("island")
    if seen and time.time() - seen < 10:
        island, detail = True, f"running — last seen {int(time.time() - seen)} s ago · hover the notch or press ⌥⌘A"
    else:
        island = any(subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0
                     for name in ("alibi-island", "Alibi"))
        detail = ("running — hover the notch or press ⌥⌘A" if island else
                  f"not seen for {int(time.time() - seen)} s" if seen else "not running")
    out.append(_check("island", "Notch island", island, detail, "./alibi.sh up  (or double-click Alibi.app)"))
    return {"checks": out, "ok": all(c["ok"] for c in out if c["key"] in ("camera", "windows", "witness", "island"))}


def _num(h: dict, field: str, default, cast, key: str):
    v = h.get(field, default)
    if v is None or v == "":
        v = default
    try:
        return cast(float(v)) if cast is int else cast(v)
    except (TypeError, ValueError):
        raise ValueError(f"{key}: {field} must be a number (got {v!r})")


SLUG = re.compile(r"^[a-z][a-z0-9_]{0,23}$")


def save_habits(habits: dict) -> dict:
    """Validate and write habits back to habits.yaml, keeping verdict/nudge settings. Returns the new config."""
    if not isinstance(habits, dict):
        raise ValueError("habits must be an object of {name: {...}}")
    clean = {}
    for key, h in habits.items():
        if not isinstance(key, str) or not SLUG.match(key):
            raise ValueError(f"habit name {key!r}: lowercase letters, digits, underscores")
        if not isinstance(h, dict):
            raise ValueError(f"{key}: expected an object like {{modality: physical, default_min: 25}}")
        if h.get("source") == "strava":
            clean[key] = {"source": "strava", "weekly_sessions": _num(h, "weekly_sessions", 3, int, key),
                          "min_km": _num(h, "min_km", 5, float, key)}
            if h.get("label"):
                clean[key]["label"] = str(h["label"])[:24]
            continue
        if h.get("modality") not in ("physical", "digital", "hybrid"):
            raise ValueError(f"{key}: modality must be physical, digital or hybrid")
        aliases = h.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [a.strip() for a in aliases.split(",")]
        elif not isinstance(aliases, list):
            aliases = [str(aliases)]
        clean[key] = {"modality": h["modality"], "aliases": [str(a) for a in aliases if str(a).strip()],
                      "weekly_target_min": max(0, _num(h, "weekly_target_min", 0, int, key)),
                      "default_min": min(config.MAX_SESSION_MIN, max(1, _num(h, "default_min", 25, int, key))),
                      "on_task_looks_like": str(h.get("on_task_looks_like") or key)}
        if h.get("label"):
            clean[key]["label"] = str(h["label"])[:24]
    if not clean:
        raise ValueError("need at least one habit")
    cfg = config.habits()
    cfg["habits"] = clean
    path = config.HABITS_PATH
    shutil.copy(path, path.with_suffix(".yaml.bak"))
    path.write_text("# Edited from the Alibi dashboard. Keys are what the agent maps your sentence to.\n"
                    + yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    return cfg
