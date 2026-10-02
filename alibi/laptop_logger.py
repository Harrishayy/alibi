"""Log frontmost app + window title (+ browser URL) every 30 s. Runs always; free.

Run in tmux:  python -m alibi.laptop_logger
Contract: events(source='laptop', kind='window', payload={app, title, url}).
"""
import platform, subprocess, time
from . import config, db

MAC_APP_TITLE = '''
tell application "System Events"
  set p to first application process whose frontmost is true
  set appName to name of p
  set winTitle to ""
  try
    set winTitle to name of front window of p
  end try
end tell
return appName & "||" & winTitle
'''


def _osa(script: str) -> str:
    """osascript's stdout, "" when it fails. It runs on the daemon tick, and a busy app or a pending Automation
    prompt can hang it, so a read past 3 s counts as failed too (empty, same as a non-zero exit)."""
    try:
        return subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3).stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def frontmost() -> dict:
    if platform.system() == "Darwin":
        app, _, title = _osa(MAC_APP_TITLE).partition("||")
        url = ""
        if app in ("Google Chrome", "Arc", "Brave Browser"):
            url = _osa(f'tell application "{app}" to get URL of active tab of front window')
        elif app == "Safari":
            url = _osa('tell application "Safari" to get URL of front document')
        return {"app": app, "title": title, "url": url}
    # Linux isn't supported yet; the active window would come from one of:
    #   X11:      xdotool getactivewindow getwindowname
    #   Hyprland: hyprctl activewindow -j
    #   KDE/Wayland: kdotool getactivewindow getwindowname
    return {"app": "", "title": "", "url": ""}


_last_log = 0.0


def log_once(con, force: bool = False) -> dict | None:
    """Called from the daemon tick; logs at most every LAPTOP_EVERY_S. Never raises."""
    global _last_log
    now = time.time()
    if not force and now - _last_log < config.LAPTOP_EVERY_S:
        return None
    _last_log = now
    try:
        w = frontmost()
    except Exception:
        return None
    if not w.get("app"):
        return None
    s = db.active_session(con)
    db.add_event(con, "laptop", "window", w, session_id=s["id"] if s else None, ts=now)
    return w


def main(every_s: int = 30):
    con = db.connect()
    last = None
    while True:
        w = frontmost()
        s = db.active_session(con)
        db.add_event(con, "laptop", "window", w, session_id=s["id"] if s else None)
        if w != last:
            print(w)
            last = w
        time.sleep(every_s)


if __name__ == "__main__":
    main()
