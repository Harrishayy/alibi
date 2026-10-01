"""One function everyone calls. Prints, pops a macOS notification, and appends to alerts.jsonl so the island can react."""
import json, subprocess, time
from . import config


def notify(text: str, image_path: str | None = None, kind: str = "info", **extra) -> None:
    """kind: info | nudge | verdict | report | pace | recap. `extra` (session_id, habit, verdict, ...) is stored on the
    alert so the island/dashboard can render it natively instead of parsing the text."""
    print(f"[alibi] {text}" + (f"  ({image_path})" if image_path else ""), flush=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.ALERTS_PATH, "a") as f:
        f.write(json.dumps({"id": time.time_ns(), "ts": time.time(), "kind": kind,
                            "text": text, "image": image_path, **extra}, default=str) + "\n")
    if config.NOTIFY == "macos":
        safe = text.replace("\\", "").replace('"', "'")
        subprocess.Popen(["osascript", "-e", f'display notification "{safe}" with title "Alibi"'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def recent_alerts(n: int = 20) -> list[dict]:
    try:
        lines = config.ALERTS_PATH.read_text().splitlines()[-n:]
    except FileNotFoundError:
        return []
    return [json.loads(l) for l in lines if l.strip()]


def last_alert(kind: str, n: int = 500) -> dict | None:
    return next((a for a in reversed(recent_alerts(n)) if a.get("kind") == kind), None)
