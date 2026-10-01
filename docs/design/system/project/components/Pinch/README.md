# Pinch

Pinch, Alibi's original green detective lobster, drawn live in SVG by the `AlibiPinch` engine; its magnifying lens doubles as the camera-on light.

**Use it for** the moments Alibi speaks: the dashboard hero (64px idle, then 96px in the Now card while live), the island (16px wings, 28px panel, 56px nudge, 64px verdict), iPhone Today (160px) and the big celebration (160px). One Pinch per view; a `PinchLine` avatar in a toast is the one allowed second.

**You provide** `mood` (held or looping: `idle`, `focused`, `listening`, `thinking`, `sleepy`, `reading`), `size` from the ladder (16, 20, 28, 32, 44, 56, 64, 96, 160), and optionally `play` (a one-shot clip: `hello`, `sideeye`, `nudge`, `celebrate`, `partial`, `supportive`, `surprise`, `connected`) with `playKey` to replay it. The engine enforces one clip per 90 s unless you pass `force`, which only verdicts and the `nudge` after a side-eye should. `still` (and `prefers-reduced-motion`) holds still frames. `theme` picks the outline for a dark or light ground; inside the island always pass `dark`.

It is decorative (`aria-hidden`); the line it speaks is real text beside it. Without the engine on the page it draws a still green disc.

- Do: match the clip to the verdict: `celebrate` for done, `partial` for partly, `supportive` for slacked.
- Do: keep it still while the person works; no one-shots during on-task focus except the verdict.
- Don't: recolour it for status, put it on evidence frames, in errors or consent copy, or inside a pill, meter or button.
