# Alibi — Claude Code instructions

@AGENTS.md

Everything in AGENTS.md applies. Below are additions for Claude Code.

## Build discipline (from PLAN.md)

- Work prototype by prototype in PLAN.md order (P0–P6, then Phase 2 P7–P14 in §10). Don't start the next until the
  current one's DoD passes.
- On a pass: stage the changed files by pathspec, `git commit -m "pN works"`, `git tag pN`, then stop and tell the
  user which 10–15 s clip to record into `demo/clips/`.
- Respect timeboxes. If something fights past its box: hardcode, fake, or fall back (each P has an "If behind"), and
  say so. Cut order: P6 → P3 → P5 → P2 Path A. Never cut P0, P1, P4 or the demo.
- Pre-flight gate before model work: `scripts/smoke_test.py` must return JSON from both the text and vision model.

## Project skills (`.claude/skills/`)

| Skill | Use when |
|---|---|
| `verify` | before saying anything is done; runs the hermetic test suite and reads failures |
| `ship-prototype` | a PLAN.md prototype's DoD passes: commit, tag, name the demo clip |
| `native-build` | any change under `native/`; rebuild and snapshot-check the island |
| `alibi-ui` | any UI change (web dashboard, island, iPhone views, evidence images) |
| `safe-commit` | committing or pushing anything in this shared working tree |
| `add-signal` | adding a new evidence source / observer |

## Working style

- Several Claude sessions can run in this repo at once (e.g. a redesign session owning `alibi/web/**`, island views,
  `ios/AlibiPhone/Views/*`, `alibi/pinch.py`; a backend session owning the rest of `alibi/*.py`, `native/sense.swift`,
  the iOS data layer and `tests/*`). Check `git status` before editing; don't overwrite or commit another session's
  uncommitted work. Use SendMessage to coordinate when a change crosses the split.
- The user prefers being asked when information is missing, over guesses that bake in assumptions.
- Tests should be fast and prove the feature works; they are not heavy QA.
- Keep the tray of running processes clean: `./alibi.sh down` after a live run so the camera is released.
