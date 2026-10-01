# Meter

A horizontal on-task meter with ticks at the verdict thresholds that fills in the verdict's colour.

**Use it for** the verdict card under the percentage, session rows, and the week's per-habit summary.

**You provide** `value` (0–1) and optional `partAt` (default 0.4) and `doneAt` (default 0.7), which place the two ticks and pick the fill: `done` at or above `doneAt`, `partly` from `partAt`, `slacked` below. Pass `label` to replace the default "On task N%".

On mount it fills from 0 over `dur-reveal` with `ease-out`, in step with a count-up; later changes, like a correction, retarget on `spring-smooth`. It moves by `transform` only, and the track is `ink` at 12% so it reads on every surface.

- Do: show the number beside it as a `Stat` or in text; the meter is never the only carrier.
- Don't: animate it on every poll; it moves when the value changes.
