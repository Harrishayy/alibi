# Alibi demo plan: 90 seconds, three surfaces, one lobster

This plan replaces `demo/shotlist.md`. The schedule is:

| Time (BST) | Step |
|---|---|
| 21:30–21:45 | Pre-flight (§6) |
| 21:45–22:15 | Capture (§4) |
| 22:15–22:40 | Edit (§5) |
| 22:40–22:45 | Export and check |

The build behind it is [`IMPLEMENTATION.md`](IMPLEMENTATION.md). Recording uses whatever is tagged at 21:30 (`p16-design` to `p20-live-activity`).

**The story in one line.** You say what you'll do. Pinch watches the evidence on the Mac, the desk and the phone. It nudges you without shaming, and the verdict comes with proof you can correct. Every shot answers one of four things:
- *I said X.*
- *Alibi saw Y.*
- *Here's the proof.*
- *It was fair to me.*

---

## 1. Shot list (edit order, 90 s)

Captions have at most 8 words, are in sentence case and never use "!". Each stays on screen for at least 2 s and never covers the island or Pinch's own line. The trigger codes (M1, P1, …) are capture takes from §4.

| # | Timecode | Surface | What happens | Pinch | Caption (≤8 words) | Trigger | Framing |
|---|---|---|---|---|---|---|---|
| 0 | 0:00–0:04 | Title card | Black. "ALIBI" wordmark fades up. Pinch (160) pops in and waves. | `hello` | **The habit tracker that checks your alibi** | `cards/record.py` → `00-title.mp4` (K6) | Full frame, 1920×1080 |
| 1 | 0:04–0:10 | Mac notch | The pointer rests on the notch, and the island **blooms** to 400 pt (shape first, content blurs in by tier). The user types "draw for 25 min" while chips sit under the field. | 28 pt `listening`, eyes on the field | **Say what you're about to do.** | Take M1 | Notch crop: 1920×1080 at x=552, y=0 of the 3024-wide recording (native pixels, no upscale). Push in from 100% to 110% over the shot. |
| 2 | 0:10–0:15 | Mac notch | Enter. Text blurs out, the panel folds on a smooth close, **wings slide out**, and the right wing reads `25m` with a numeric roll. | 16 pt still `focused` in the left wing | **It watches quietly while you work.** | Take M1, continued | Same crop |
| 3 | 0:15–0:22 | Dashboard, Now card | Ring timer and on-task 100%. A new desk frame **develops** in the sample strip (grey/blur → sharp) and its dot pops. Pinch has its lens glowing. | 96 px `focused` | Witness line, §3 (e.g. **Judged on this Mac by Apple Vision.**) | Take M2 (live), first minute | Browser crop 1920×1080 centred on the Now card. The LIVE desk frame is visible. |
| 4 | 0:22–0:27 | iPhone Lock Screen | Lift the phone to wake it. The Live Activity shows Pinch 32, "Drawing", the countdown ticking and "On task 100%". | still `focused` | **Your Lock Screen keeps the time.** | Take M2, at 0:30 of the session (QuickTime on the iPhone) | Phone screen scaled to 1000 px tall, centred on `#000`. A 0.3 s whip from the Mac shot. |
| 5 | 0:27–0:31 | Dynamic Island (simulator) | Compact view: Pinch on the left, timer on the right. A long-press expands it: 44 pt Pinch, ring, drift line. | still `focused` | **And in the Dynamic Island.** | Take S1 | iPhone 17 Pro simulator recording, cropped to the top 40% and scaled to 1080 tall |
| 6 | 0:31–0:42 | Desk → notch | 1 s cutaway: the LIVE frame shows the phone in hand (sped 4×). Then the **nudge drops** out of the notch on a bouncy spring with one shake. The line reads: "You said drawing. I've seen your **phone** for 40 seconds." The user clicks **Back to it** and the alert folds. | 56 pt `sideeye` → `nudge` | **Drift gets a nudge, not a lecture.** | Take M2, at 1:00–1:35 of the session | Notch crop, with the LIVE frame as picture-in-picture bottom-right at 28% width, `radius-md` |
| 7 | 0:42–0:49 | Mac notch | The session ends. The **verdict alert** blooms to 440 pt: `✓ Done` in black on green, a 3-frame strip, [See proof] [Something's wrong?]. | 64 pt `celebrate` with bloom | **Done only when the evidence agrees.** | Take M2, at 3:00 | Notch crop |
| 8 | 0:49–0:57 | Dashboard, verdict | **Verdict reveal.** The card rises, the pill blurs in, the % counts up to 78 while the meter fills, claw confetti bursts, and the contact sheet sits below as the proof. | 96 px `celebrate` | **Every verdict comes with proof.** | Take M3: reload `http://127.0.0.1:8765/?moment=verdict` within 10 min of M2 | Browser crop on the Now card and contact sheet |
| 9 | 0:57–1:04 | Dashboard, contact sheet | Click a genuinely ambiguous frame (e.g. hand reaching for an eraser, labelled idle) and relabel it on task. The popover scales from the dot, the dot recolours and the % ticks up. Pinch says: "Fair. I've changed that one." | `surprise` → nod | **Wrong call? One click fixes it.** | Take M3, continued | Browser crop on the sheet. Cursor visible, moving slowly. |
| 10 | 1:04–1:12 | Dashboard, hero and week | Scroll up to the hero strip, which reads "You claimed 3h 10m. I saw 2h 52m." The streak pill rolls to "6 days · 1 freeze left". Scroll down to the week dots and the claimed/seen bars. | 64 px `reading` | **Claimed versus seen, every single night.** | Take M4 (seeded week) | Browser crop, one slow trackpad scroll |
| 11 | 1:12–1:19 | iPhone app | Today: Pinch 160 plus the verdict card. Swipe to Week (paired bars), then Health ("Synced 2 min ago"). | 160 pt `celebrate`, then `idle` | **Phone, laptop and desk: one honest record.** | Take P1 | Phone centred on `#000`, as in shot 4 |
| 12 | 1:19–1:24 | Two-up: web | Partial and slacked reveals side by side: shrug and "Partly. 17 of 25 minutes on task." next to supportive and "Slacked, by my count. Tap any frame if I got it wrong." | `partial` · `supportive` | **Bad days get honesty, never shame.** | Take W1 (fixtures, automated) | Two 960×1080 halves |
| 13 | 1:24–1:30 | End card | Pinch 160 breathing (`idle`). "Alibi" and "Built for the NVIDIA London Claw Agent Challenge" sit in `ink-2`, with the witness line from §3. | `idle` | **Say it. Do it. Alibi checks.** | `cards/record.py` → `99-end.mp4` | Full frame |

**Trim to 75 s by cutting, in this order:**
1. Shot 12 (−5 s)
2. Shot 5 (−4 s; the Lock Screen shot stays)
3. Shorten shot 10 to 4 s (−4 s)

Never cut shots 1, 6, 7, 8 or 9. They are the four signature moments plus the correction.

**If L5 was cut** (no Live Activity), replace shots 4–5 with shot 11's Today screen during the live session: Pinch 160 and a mirrored ring ticking. The caption becomes **Your phone mirrors the session live.**

---

## 2. Title and end cards

Both are rendered from `docs/design/demo/cards/*.html` (built in K6) on `#000` at 1920×1080, 4.0 s, 60 fps, using `tokens.css` and `pinch.js`. No other fonts are used.

- **Title (`00-title.mp4`):**
  - 0.0 s: black.
  - 0.3 s: "ALIBI" fades in, SF Pro heavy, 72 px, tracking 0.12em, `ink`.
  - 0.8 s: Pinch 160 pops in on `spring-celebrate` and plays `hello`.
  - 1.6 s: subtitle in the `voice` style, `ink-2`: "The habit tracker that checks your alibi."
  - Hold, then cut on a beat.
- **End (`99-end.mp4`):**
  - Pinch 160 `idle`, breathing.
  - "Alibi" in h1, 32/600.
  - "Built for the NVIDIA London Claw Agent Challenge" in body, `ink-2`.
  - The witness line from §3 in small, `ink-3`.
  - The repo or submission URL in small mono.
  - The green accent appears only on Pinch.

---

## 3. Honest witness wording (CLAUDE.md privacy rule)

At the start of pre-flight, run `./alibi.sh status`. It prints `witness: …`, and that decides which line to use in shot 3 and on the end card:

| `witness` / `.env` | Shot 3 caption | End card line |
|---|---|---|
| `apple` | **Judged on this Mac by Apple Vision.** | "Frames are judged on-device by Apple Vision." |
| `nvidia`, with `VLM_BASE_URL` pointing at a **local** server (e.g. the Spark on the LAN) | **An NVIDIA VLM judges every frame.** | "NVIDIA VLM on my own hardware. Frames never leave my network." |
| `nvidia` on NVIDIA Build (a cloud URL) | **An NVIDIA VLM judges every frame.** | "Frames are judged by an NVIDIA VLM on NVIDIA Build." (Never say they stay local.) |

---

## 4. Capture takes (record order)

The **stage driver** is `docs/design/demo/stage.py` (IMPLEMENTATION K4). All takes use port 8765 and a fresh copy of the seeded week:

```bash
rm -rf /tmp/alibi-demo && cp -R data/demo /tmp/alibi-demo
```

`--phone` copies the main phone key and enables the `:8766` listener, so the installed iPhone app connects without a rebuild.

| Take | Time | Command and actions | Covers shots | Retake rule |
|---|---|---|---|---|
| **M1 bloom** | 21:45–21:50 | `.venv/bin/python docs/design/demo/stage.py serve --port 8765 --data /tmp/alibi-demo --phone --island`. Start Cmd-Shift-5. Rest the pointer on the notch for 1 s → bloom. Type "draw for 25 min" slowly → Enter → wait 4 s for the wings. Then type `end` in the island, or press Ctrl-C and restart `serve`. | 1, 2 | Up to 3 attempts. Keep the one with the cleanest pointer path. |
| **M2 live session** | 21:50–22:00 | Ctrl-C the serve. Run `stage.py done --live --phone --island --port 8765 --data /tmp/alibi-demo --every 10 --say "draw for 3 minutes"`. Record the Mac screen and the iPhone (QuickTime) at the same time. Cues, which `stage.py` also prints:<br>**0:00** draw.<br>**0:20** open the Alibi app on the phone, tap "Show on Lock Screen", lock the phone and lay it face up on the stand.<br>**0:30** raise the phone to wake it (shot 4), then put it down.<br>**1:00** pick the phone up **in camera view**, screen towards you, and scroll for 40 s.<br>**~1:35** the nudge drops: click **Back to it**, put the phone face down and draw.<br>**3:00** verdict on the island. | 3, 4, 6, 7 | If no nudge fires by 1:50 (Apple Vision missed the phone), finish the take anyway. Then record **M2F**: `stage.py done --phone --island --port 8765 --data /tmp/alibi-demo --every 10` (mock witness, deterministic), using only its notch crops for shots 6–7. Never show its colour-coded frames. |
| **M3 proof** | 22:00–22:05 | Within 10 min of M2 ending (while `recent_verdict` holds), open `http://127.0.0.1:8765/?moment=verdict` in the Chrome app window. Let the reveal play, wait 2 s, then do the correction on an ambiguous frame. | 8, 9 | If no frame is genuinely ambiguous, relabel nothing. Use the Sessions row → "Fix a moment" on the seeded session with a known mislabel. Never fake a wrong label. |
| **M4 week** | 22:05–22:08 | Hard-reload `http://127.0.0.1:8765/`, scroll to the top, wait for the hero, then make one slow scroll to "This week". | 10 | Two attempts |
| **P1 phone app** | 22:08–22:12 | QuickTime on the iPhone, app in the foreground. Today shows the M2 verdict card: Pinch celebrates and the success haptic fires. Swipe to Week, then Health, then tap Sync now. | 11 | If Today shows "Can't reach your Mac", check Wi-Fi, then Tailscale (§6). |
| **S1 Dynamic Island** | 22:12–22:15 | Simulator (iPhone 17 Pro): first Ctrl-C any running stage, then start `stage.py done --phone --port 8765 --data /tmp/alibi-demo2 --every 10`. The simulator reaches `:8766` on this Mac directly. In the simulator app, tap "Show on Lock Screen", then press Cmd-Shift-H to go home. Run `xcrun simctl io booted recordVideo --codec=h264 --force demo/clips/raw/S1-di.mp4`. Long-press the island after 3 s. | 5 | Gated on `p20-live-activity`. Otherwise drop shot 5. |
| **W1 bad days** | automated, by L6 at 21:30 | `python3 docs/design/demo/cards/record.py --stage verdict_partial,verdict_slacked` records the two web reveals from the fixtures to `demo/clips/12a-partial.mp4` and `12b-slacked.mp4`, each 960×1080. | 12 | none |

**Camera rule.** M2 is the only take with the live camera. When it ends, `stage.py` releases the camera. After the last take, run `./alibi.sh down`; it must print `Alibi is off. Camera released.`, and the camera LED must be off.

---

## 5. Edit (iMovie or ffmpeg, 22:15–22:40)

### 5.1 Prepare clips with ffmpeg (native-pixel crops)

```bash
mkdir -p demo/clips/cut
# Notch close-up from a 14" recording (3024 wide). On a 16" (3456 wide) use x=768.
ffmpeg -i demo/clips/raw/M1.mov -vf "crop=1920:1080:552:0" -c:v libx264 -crf 16 -preset slow -an demo/clips/cut/01-bloom.mp4
# Dashboard: crop a 1920x1080 window around the Now card (adjust X,Y after a look at a frame grab).
ffmpeg -ss 00:00:05 -i demo/clips/raw/M2.mov -frames:v 1 /tmp/m2.png     # Read /tmp/m2.png to pick X,Y
ffmpeg -i demo/clips/raw/M2.mov -vf "crop=1920:1080:X:Y" -c:v libx264 -crf 16 -an demo/clips/cut/03-now.mp4
# Phone (QuickTime, 1170x2532 portrait) centred on black.
ffmpeg -i demo/clips/raw/P1.mov -vf "scale=-2:1000,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black" -c:v libx264 -crf 16 -an demo/clips/cut/11-phone.mp4
# Speed the phone-in-hand wait 4x.
ffmpeg -i demo/clips/cut/06-wait.mp4 -vf "setpts=PTS/4" -an demo/clips/cut/06-wait-4x.mp4
# Two-up for shot 12.
ffmpeg -i demo/clips/12a-partial.mp4 -i demo/clips/12b-slacked.mp4 -filter_complex hstack -c:v libx264 -crf 16 demo/clips/cut/12-baddays.mp4
```

### 5.2 Assemble in iMovie

1. Set up a 1080p project and drop in the clips in §1 order.
2. Add captions from the table (§5.4 style).
3. Lay the music under everything (§5.3).
4. Add the one SFX.

iMovie's "Lower third" title with a custom font can't carry the exact pill style. If you want the exact look, render the captions as PNG overlays with `render.py` from a 20-line caption HTML on a transparent page (`omitBackground`). Otherwise use iMovie's "Standard lower third" in SF Pro.

### 5.3 Music and sound

- **Track.** Calm, minimal electronic or lo-fi: 90–105 BPM, no vocals, a soft piano or synth lead. It must be royalty-free and cleared for contest and online use: YouTube Audio Library ("Attribution not required" filter), Pixabay Music or Uppbeat free (credit if required). Fade in over 1 s on the title and out over 2 s on the end card.
- **Cuts on the beat:** shot 1 (bloom), shot 6 (the nudge drop lands on a downbeat) and shot 7 (verdict).
- **Ducking.** The music sits at about −20 LUFS under everything. Duck it −6 dB for 1 s when the nudge lands, so the silence does the work. There is **no sound for bad news** (Mascot.md), so the nudge, partial and slacked moments get no SFX.
- **The only SFX** is the done chime (the app's spec: 660 Hz then 990 Hz, 80 ms each, 10 ms attack, 120 ms release). Place it on shot 7's pill and again on shot 8's confetti, quieter.
  ```bash
  ffmpeg -f lavfi -i "sine=f=660:d=0.08" -f lavfi -i "sine=f=990:d=0.13" -filter_complex \
    "[0][1]concat=n=2:v=0:a=1,afade=t=in:d=0.01,afade=t=out:st=0.09:d=0.12,volume=0.25" -ar 48000 demo/clips/chime.wav
  ```
- **No voiceover.** The captions and Pinch's lines carry the story.

### 5.4 Caption style

- **Type:** SF Pro Text Semibold, 44 px at 1080p, line-height 1.2, colour `#F2F2F2`.
- **Backing:** a pill of `rgba(0,0,0,0.64)` (`scrim`), radius 10, padding 12×20.
- **Position:** bottom-left, with 72 px margins. Move it bottom-right when the island or Pinch is at the bottom-left.
- **Timing:** fade in 180 ms and out 120 ms.
- **Colour:** no green, no emoji, no "!".

### 5.5 Export (22:40–22:45)

1. **Encode.** H.264 High, 1920×1080, 60 fps (30 fps is fine if iMovie insists), about 12 Mbps or CRF 18, AAC 192 kb/s at 48 kHz, `+faststart`. Integrated loudness −14 LUFS, true peak −1 dBTP:
   ```bash
   ffmpeg -i edit.mov -af loudnorm=I=-14:TP=-1 -c:v libx264 -crf 18 -preset slow -movflags +faststart -c:a aac -b:a 192k demo/alibi-demo.mp4
   ```
2. **Check.**
   - Duration: `ffprobe -v error -show_entries format=duration -of csv=p=0 demo/alibi-demo.mp4` must print between 75 and 90.
   - Watch it once at full screen with the sound on, and once muted. The captions alone must tell the story.
   - Look for a seam at the notch: the island must be pure `#000` against the hardware cut-out.

---

## 6. Pre-flight checklist (21:30–21:45)

**Code and build**
- [ ] Run `git tag | rg "p1[6-9]|p20"`. It lists the tags that exist. Write down which surfaces made it, then apply the trims in §1.
- [ ] Run `./alibi.sh test | rg -c FAILED`. It must print `0`.
- [ ] Run `bash scripts/build_native.sh | tail -1`. It must print `Built Alibi.app (…)`. Then `./alibi.sh down && ./alibi.sh up`, and click **Allow** when macOS asks once for Documents access (the app was re-signed). Without the click, the daemon hangs at startup.
- [ ] The other session has paused daemon work (ask A9). Run `pgrep -fl "alibi"`; it must show nothing, or only our processes. **Quit Alibi.app**: if it finds no daemon it starts one on the real data, and two islands would fight over the notch.
- [ ] Witness wording chosen (§3).

**Mac**
- [ ] Accessibility → Display → **Reduce motion off**. Check with `defaults read com.apple.universalaccess reduceMotion`, which must print `0` or "does not exist".
- [ ] Appearance Dark. Wallpaper: Colours → black. Desktop icons hidden: `defaults write com.apple.finder CreateDesktop false && killall Finder`. Restore afterwards with `true`.
- [ ] Dock set to auto-hide. Focus set to **Do Not Disturb**. Slack, Mail and Messages quit.
- [ ] Built-in display at "Default" scaled resolution. The external display is unplugged, or simply not recorded: Cmd-Shift-5 → Options → record the built-in display.
- [ ] Cmd-Shift-5 options: no microphone, **Show Mouse Clicks off**, save to `demo/clips/raw/`.
- [ ] Browser: `open -na "Google Chrome" --args --app=http://127.0.0.1:8765 --window-size=1512,920 --window-position=0,40`. Zoom 100%, hard reload (Cmd-Shift-R), Setup → Theme → System (dark).
- [ ] At least 10 GB free disk space. Laptop on power.

**Desk camera** (`CAMERA_INDEX` from `.env`)
- [ ] The camera looks down at the desk: sketchbook centred, both hands in view, and the phone's resting spot in frame, face down.
- [ ] Desk lamp on, no window behind the desk. Check the LIVE frame on the dashboard during the dry run.
- [ ] Rehearse holding the phone **face-on to the camera at chest height**. Apple Vision needs the phone's outline.

**iPhone 14 (iOS 26.3.1)**
- [ ] Latest build installed. While `stage.py serve --phone --port 8765` runs, run `bash ios/build_install.sh`. It bakes in this Mac's addresses and the key, then installs over USB.
- [ ] Settings → Alibi → **Live Activities on**. No other Live Activities are running. Focus is Do Not Disturb. Notification previews off. Brightness at maximum. Dark wallpaper.
- [ ] Same Wi-Fi as the Mac. Tailscale is up on both as a fallback (`tailscale status` lists the phone).
- [ ] Reachability (it must print JSON, not `401` or a timeout):
  ```bash
  curl -s -m 2 -H "X-Alibi-Secret: $(.venv/bin/python -c 'import json;print(json.load(open("/tmp/alibi-demo/secrets.json"))["phone_secret"])')" http://127.0.0.1:8766/api/phone/session | head -c 120
  ```
- [ ] QuickTime Player → File → New Movie Recording → ⌄ → Camera: **Harrish** (the iPhone), Quality: Maximum. Unlock the phone and trust the Mac. The preview mirrors the phone.

**Simulator** (Dynamic Island, shot 5)
- [ ] Boot it, set dark appearance and override the status bar:
  ```bash
  xcrun simctl boot "iPhone 17 Pro"; open -a Simulator; xcrun simctl ui booted appearance dark
  xcrun simctl status_bar booted override --time 9:41 --batteryState charged --batteryLevel 100 --cellularBars 4 --wifiBars 3
  ```
- [ ] L5's simulator build is installed, and Today shows a session during a stage run.

**Dry run** (no camera; about 100 s; can run on the lab port while you set up)
- [ ] Run `.venv/bin/python docs/design/demo/stage.py done --port 8775 --data /tmp/alibi-dry --every 5`. The last line must be `verdict done 7x%`.
- [ ] Glance at the island snapshots and `http://127.0.0.1:8775/?stage=verdict_done&moment=verdict` once.

**After recording**
- [ ] Run `./alibi.sh down`. It must print `Alibi is off. Camera released.`, and the camera LED must be off.
- [ ] Restore desktop icons and turn Do Not Disturb off.
- [ ] Move the keepers to `demo/clips/` (gitignored). `demo/alibi-demo.mp4` is the deliverable.
- [ ] Note in `submission.md` (the other session's file, via ask) the witness wording used, so the submission text matches the video.
