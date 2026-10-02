"""One function everyone calls. Prints, pops a macOS notification, appends to alerts.jsonl so the island can react, and
(with NTFY_TOPIC set) pushes the alerts worth a buzz to the phone."""
import json, subprocess, threading, time
from . import config

# kind -> (ntfy priority 1-5, tag). By kind only: the nudge is the alarm (5, urgent); the rest are a normal buzz. info
# (e.g. "Strava: … logged."), recap, pace and synced never leave the Mac, whatever their source.
PUSH = {"nudge": (5, "rotating_light"), "verdict": (3, "white_check_mark"), "digest": (3, "memo"),
        "report": (3, "crescent_moon"), "planned": (3, "alarm_clock"), "brief": (3, "memo")}
AGENT_TITLE = "Alibi · your agent"


def notify(text: str, image_path: str | None = None, kind: str = "info", **extra) -> None:
    """kind: info | nudge | verdict | report | digest | brief | planned | pace | recap | synced. `extra` (session_id,
    habit, verdict, ...) is stored on the alert so the island/dashboard can render it natively instead of parsing the
    text. Kinds in PUSH also go to the phone (push). An optional `card` extra is allowed but not needed: cards are built
    when the alert is served (alibi/cards.py), and a stored one still goes through cards.clean()."""
    print(f"[alibi] {text}" + (f"  ({image_path})" if image_path else ""), flush=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.ALERTS_PATH, "a") as f:
        f.write(json.dumps({"id": time.time_ns(), "ts": time.time(), "kind": kind,
                            "text": text, "image": image_path, **extra}, default=str) + "\n")
    if config.NOTIFY == "macos":
        safe = text.replace("\\", "").replace('"', "'")
        subprocess.Popen(["osascript", "-e", f'display notification "{safe}" with title "Alibi"'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    push(text, kind, extra)


def push(text: str, kind: str, extra: dict) -> threading.Thread | None:
    """Phone push through ntfy (config.NTFY_TOPIC). Off when unset; never raises, never blocks the caller.

    Published as JSON to the server root, so the title travels as UTF-8: a `Title` header would send the "·" as latin-1
    byte 0xB7 and the phone would show it garbled. The agent's brief (kind "brief", or anything from NemoClaw) gets its
    own title, so the phone says who's talking."""
    if not config.NTFY_TOPIC:
        return None
    pr = PUSH.get(kind)
    if not pr:
        return None
    agent = kind == "brief" or "nemoclaw" in (extra.get("source"), extra.get("via"))
    body = {"topic": config.NTFY_TOPIC, "title": AGENT_TITLE if agent else "Alibi", "message": text,
            "priority": pr[0], "tags": [pr[1]]}

    def run():
        try:
            import requests
            requests.post(config.NTFY_URL, json=body, timeout=5).raise_for_status()
        except Exception as e:                       # the type only: the message could carry the topic
            print(f"[alibi] phone push failed: {type(e).__name__}", flush=True)
    t = threading.Thread(target=run, daemon=True, name="alibi-push")
    t.start()
    return t


def recent_alerts(n: int = 20) -> list[dict]:
    try:
        lines = config.ALERTS_PATH.read_text().splitlines()[-n:]
    except FileNotFoundError:
        return []
    return [json.loads(l) for l in lines if l.strip()]


def last_alert(kind: str, n: int = 500) -> dict | None:
    return next((a for a in reversed(recent_alerts(n)) if a.get("kind") == kind), None)
