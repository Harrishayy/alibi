"""P10 — memories reel: a session's (or a whole day's) frames as an H.264 timelapse.

  python -m alibi.reel session 12
  python -m alibi.reel day 2026-10-01
"""
import datetime as dt, os, shutil, subprocess, sys, tempfile, threading
from pathlib import Path
from PIL import Image, ImageDraw
from . import config, db, evidence

W, H, FPS = 1280, 720, 6
REELS_DIR = config.DATA_DIR / "reels"
PINCH_DIR = Path(__file__).resolve().parents[1] / "docs" / "design" / "demo" / "cards"
PINCH_FOR = {"done": "celebrate", "partial": "partial", "slacked": "supportive"}   # anything else: hello
BLACK = "#000000"                                     # the reel plays on the dark stage, like the island


def _pinch(clip: str, size: int) -> Image.Image | None:
    """A Pinch still (rendered from the rig by lane S, 512px RGBA). The title card is the one raster Pinch."""
    try:
        im = Image.open(PINCH_DIR / f"pinch-{clip}-512.png").convert("RGBA")
    except OSError:
        return None
    return im.resize((size, size), Image.LANCZOS)


def _card(lines: list[tuple[str, int, str]], clip: str = "hello", verdict: str | None = None,
          pill: str = "") -> Image.Image:
    """Title card: Pinch, a sans title, a meta line, then the verdict pill (black text on green for done)."""
    im = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(im, "RGBA")
    p, ps = _pinch(clip, 176), 176
    fonts = [evidence.sans(sz, 600 if i == 0 else 400) for i, (_, sz, _) in enumerate(lines)]
    block = (ps + 32 if p else 0) + sum(sz + 16 for _, sz, _ in lines) - 16 + (32 + 40 if pill else 0)
    y = (H - block) // 2
    if p:
        im.paste(p, ((W - ps) // 2, y), p)
        y += ps + 32
    for (text, size, colour), f in zip(lines, fonts):
        d.text((W / 2, y), text, font=f, fill=colour, anchor="mt")
        y += size + 16
    if pill:
        f = evidence.sans(17, 600)
        g = round(17 * 0.8)
        right = W / 2 + (16 + g + 8 + d.textlength(pill, font=f) + 18) / 2
        evidence.verdict_pill(d, right, y - 16 + 32 + 20, verdict or "", pill)
    return im


def _frame(path: str, ts: float, label: str, note: str, corrected: bool) -> Image.Image:
    try:
        src = Image.open(path).convert("RGB")
    except OSError:
        src = Image.new("RGB", (512, 288), evidence.SURFACE_2)
    scale = max(W / src.width, H / src.height)
    src = src.resize((int(src.width * scale), int(src.height * scale)))
    left, top = (src.width - W) // 2, (src.height - H) // 2
    im = src.crop((left, top, left + W, top + H))
    d = ImageDraw.Draw(im, "RGBA")
    # Bottom edge: the sample's status colour (off_task keeps its hatch). No Pinch on evidence frames.
    if label == "off_task":
        im.paste(evidence._hatch(W, 8, evidence.COLOURS["off_task"], evidence.WASH["off_task"], 12, 3), (0, H - 8))
    else:
        d.rectangle([0, H - 8, W, H], fill=evidence.COLOURS.get(label, evidence.INK_2))
    f, fw = evidence.sans(24, 600), evidence.sans(24)
    t, word = f"{dt.datetime.fromtimestamp(ts):%H:%M}", evidence.LABEL_WORD.get(label, label.replace("_", " "))
    word += "  ·  corrected" if corrected else ""
    tw = d.textlength(t, font=f) + 12 + d.textlength(word, font=fw)
    x0, y0, h = 32, H - 32 - 8 - 56, 56
    d.rounded_rectangle([x0, y0, x0 + 24 + 20 + 12 + tw + 24, y0 + h], radius=h / 2, fill=(0, 0, 0, 184))
    m = evidence.mark(label, 20)
    im.paste(m, (x0 + 24, y0 + (h - 20) // 2), m)
    d.text((x0 + 24 + 20 + 12, y0 + h / 2), t, font=f, fill=evidence.INK, anchor="lm")
    d.text((x0 + 24 + 20 + 12 + d.textlength(t, font=f) + 12, y0 + h / 2), word, font=fw, fill=evidence.INK_2,
           anchor="lm")
    return im


def _session_frames(con, s) -> list[Image.Image]:
    from . import verifier
    labels = verifier.camera_labels(con, s)
    out = []
    ratio = s["on_task_ratio"]
    v = s["verdict"]
    pill = f"{evidence.VERDICT_WORD.get(v, str(v).capitalize())} · {ratio:.0%} on task" if v else ""
    lines = [(config.display_name(s["habit"]), 64, evidence.INK),
             (f"{dt.datetime.fromtimestamp(s['started_at']):%a %d %b, %H:%M} · {s['declared_min']} min", 28, evidence.INK_2)]
    if not v:
        lines.append(("In progress", 28, evidence.INK_2))
    card = _card(lines, PINCH_FOR.get(v, "hello"), v, pill)
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
    frames = [_card([(f"{dt.datetime.fromisoformat(day):%A %d %B}", 64, evidence.INK),
                     (f"{len(ss)} session{'s' * (len(ss) != 1)}, as the witness saw them", 28, evidence.INK_2)],
                    "hello")] * (FPS * 2)
    for s in ss:
        frames += _session_frames(con, s)
    if len(frames) <= FPS * 2:
        return None
    return _encode(frames, REELS_DIR / f"day-{day}.mp4")


if __name__ == "__main__":
    con = db.connect()
    kind, arg = sys.argv[1], sys.argv[2]
    print(session_reel(con, int(arg)) if kind == "session" else day_reel(con, arg))
