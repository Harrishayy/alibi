"""P10 — memories reel: a session's (or a whole day's) frames as an H.264 timelapse.

  python -m alibi.reel session 12
  python -m alibi.reel day 2026-10-01
"""
import datetime as dt, os, shutil, subprocess, sys, tempfile, threading
from PIL import Image, ImageDraw
from . import config, db, evidence

W, H, FPS = 1280, 720, 6
REELS_DIR = config.DATA_DIR / "reels"


def _card(lines: list[tuple[str, int, str]]) -> Image.Image:
    im = Image.new("RGB", (W, H), evidence.CREAM)
    d = ImageDraw.Draw(im)
    y = H // 2 - sum(s for _, s, _ in lines) // 2 - 20
    for text, size, colour in lines:
        f = evidence._font("NewYork.ttf", size)
        d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=colour)
        y += size + 24
    return im


def _frame(path: str, ts: float, label: str, note: str, corrected: bool) -> Image.Image:
    try:
        src = Image.open(path).convert("RGB")
    except OSError:
        src = Image.new("RGB", (512, 288), evidence.RULE)
    scale = max(W / src.width, H / src.height)
    src = src.resize((int(src.width * scale), int(src.height * scale)))
    left, top = (src.width - W) // 2, (src.height - H) // 2
    im = src.crop((left, top, left + W, top + H))
    d = ImageDraw.Draw(im, "RGBA")
    col = evidence.COLOURS.get(label, evidence.INK)
    d.rectangle([0, H - 14, W, H], fill=col)
    mono = evidence._font("Menlo.ttc", 26)
    tag = f"{dt.datetime.fromtimestamp(ts):%H:%M}  {label.replace('_', ' ')}" + ("  (corrected)" if corrected else "")
    tw = d.textlength(tag, font=mono)
    d.rounded_rectangle([28, H - 84, 28 + tw + 40, H - 34], radius=25, fill=(20, 20, 18, 190))
    d.ellipse([44, H - 66, 58, H - 52], fill=col)
    d.text((66, H - 75), tag, font=mono, fill="white")
    return im


def _session_frames(con, s) -> list[Image.Image]:
    from . import verifier
    labels = verifier.camera_labels(con, s)
    out = []
    ratio = s["on_task_ratio"]
    sub = (f"{s['verdict'].upper()} · {ratio:.0%} on task" if s["verdict"] else "in progress")
    card = _card([(config.display_name(s["habit"]), 84, evidence.INK),
                  (f"{dt.datetime.fromtimestamp(s['started_at']):%a %d %b, %H:%M} · {s['declared_min']} min", 30, evidence.MUTED),
                  (sub, 30, evidence.VERDICT_COLOUR.get(s["verdict"], evidence.MUTED))])
    out += [card] * (FPS * 2)
    for e in labels:
        p = e["payload"]
        if p.get("frame"):
            out.append(_frame(p["frame"], e["ts"], p["label"], p.get("note", ""), bool(p.get("corrected_from"))))
    return out


_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(name: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(name, threading.Lock())


def building(name: str) -> bool:
    return _lock_for(name).locked()


def _encode(frames: list[Image.Image], out_path) -> str:
    """One build per reel at a time (R3); write to .tmp then os.replace so nobody ever serves half a file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with _lock_for(out_path.stem):
        tmp = tempfile.mkdtemp(prefix="alibi-reel-")
        part = out_path.with_name(out_path.stem + ".part.mp4")
        try:
            for i, f in enumerate(frames):
                f.save(f"{tmp}/{i:05d}.jpg", quality=90)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{tmp}/%05d.jpg",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(part)],
                           check=True)
            os.replace(part, out_path)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            part.unlink(missing_ok=True)
    return str(out_path)


def session_reel(con, session_id: int) -> str | None:
    s = con.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not s:
        return None
    frames = _session_frames(con, s)
    if len(frames) <= FPS * 2:
        return None
    return _encode(frames + [frames[-1]] * FPS, REELS_DIR / f"session-{session_id}.mp4")


def day_reel(con, day: str) -> str | None:
    try:
        d0 = dt.datetime.strptime(day, "%Y-%m-%d").timestamp()
    except (TypeError, ValueError):
        raise ValueError("date must be YYYY-MM-DD")
    ss = con.execute("SELECT * FROM sessions WHERE started_at BETWEEN ? AND ? AND modality!='digital' ORDER BY started_at",
                     (d0, d0 + 86400)).fetchall()
    frames = [_card([(f"{dt.datetime.fromisoformat(day):%A %d %B}", 72, evidence.INK),
                     (f"{len(ss)} session{'s' * (len(ss) != 1)}, as the witness saw them", 30, evidence.MUTED)])] * (FPS * 2)
    for s in ss:
        frames += _session_frames(con, s)
    if len(frames) <= FPS * 2:
        return None
    return _encode(frames, REELS_DIR / f"day-{day}.mp4")


if __name__ == "__main__":
    con = db.connect()
    kind, arg = sys.argv[1], sys.argv[2]
    print(session_reel(con, int(arg)) if kind == "session" else day_reel(con, arg))
