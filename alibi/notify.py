"""P0 (print/macos) -> P2 (telegram). One function everyone calls."""
import subprocess
from . import config


def notify(text: str, image_path: str | None = None) -> None:
    print(f"[alibi] {text}" + (f"  ({image_path})" if image_path else ""))
    if config.NOTIFY == "macos":
        safe = text.replace('"', "'")
        subprocess.run(["osascript", "-e", f'display notification "{safe}" with title "Alibi"'],
                       check=False)
    elif config.NOTIFY == "telegram":
        # TODO (P2): POST to https://api.telegram.org/bot<token>/sendMessage (and sendPhoto for image_path)
        pass
