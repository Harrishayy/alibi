# RingTimer

The live session ring: an arc for elapsed time with the countdown in the centre.

**Use it for** the web Now card (160px), the iPhone Today screen, and the island session card (44px, with the time beside it).

**You provide** `progress` (0–1 elapsed), `value` (the formatted time, "24:07"), an optional `caption` ("of 25 min"), an optional `size` (default 160) and `tone`: `accent` while on task, `partial` on a break or while drifting, `warn` after an overrun. Under 88px the centre text is dropped, so set the value beside the ring in `Stat` or the island timer style.

The arc draws in from 0 on `spring-smooth`, then ticks once a second with a linear 1000ms transition as you update `progress`. The stroke is size ÷ 16 (10px at 160) on an `ink` 12% track, and the value is set in the rounded face at size × 0.24 with tabular figures.

- Do: update `progress` once a second; the transition fills the gap.
- Don't: show seconds below a minute in the centre unless the session is under 5 minutes.
