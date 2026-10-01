---
name: native-build
description: Rebuild and check Alibi's macOS Swift binaries (notch island, Apple Vision witness, sense, calendar, Alibi.app) and render the island offscreen to PNGs. Use after any edit under native/, when the island looks wrong, or when bin/ or Alibi.app is missing or stale.
---

# Native build

## Build

```bash
bash scripts/build_native.sh
```
Builds `bin/alibi-witness`, `bin/alibi-island`, `bin/alibi-sense`, `bin/alibi-calendar` and `Alibi.app`
(which hosts the island and owns the daemon, so macOS permissions belong to "Alibi"). These are single-file
`swiftc -O` builds; a compile error names the file and line. Fix it and rebuild; don't add an Xcode project.

## Check the island without screen recording

```bash
D=$(mktemp -d) && bin/alibi-island --snapshot "$D" && ls "$D"
# with a specific state:  bin/alibi-island --snapshot "$D" --state some_state.json --prefix live-
```
Open the PNGs with the Read tool and check them against the design rules (`alibi-ui` skill):
- idle/closed = exactly notch size, **no wings**;
- live = two compact 46 pt wings (glyph left, short value like `24m` right);
- open = 400 pt wide (verdict 440); the notch row holds only the wordmark and icon buttons.

Text fields render as a yellow placeholder in snapshots. That's the renderer, not a bug.

## Run for real

`./alibi.sh down && ./alibi.sh up` (`up` rebuilds automatically when `native/*.swift` is newer than the binaries).
Run `./alibi.sh down` when finished so the camera is released.

## Gotchas

- Island buttons must live in `FirstClickHostingView` (`acceptsFirstMouse = true`). Alibi is never the active app,
  so without it every click is dropped.
- Hover timing: open after 0.35 s dwell; fold after 0.8 s outside the margin (32 pt sides, 48 pt below).
- `bin/` and `Alibi.app/` are git-ignored build output. Never commit them.
