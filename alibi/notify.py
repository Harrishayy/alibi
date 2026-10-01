"""One function everyone calls. Prints, pops a macOS notification, and appends to alerts.jsonl so the island can react."""
import json, subprocess, time
from . import config


def notify(text: str, image_path: str | None = None, kind: str = "info") -> None:
    print(f"[alibi] {text}" + (f"  ({image_path})" if image_path else ""), flush=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.ALERTS_PATH, "a") as f:
        f.write(json.dumps({"id": time.time_ns(), "ts": time.time(), "kind": kind,
                            "text": text, "image": image_path}) + "\n")
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
