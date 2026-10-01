---
name: ship-prototype
description: Close out an Alibi prototype from PLAN.md (P0–P14) once its Definition of Done passes. Verify, commit by pathspec, tag pN, and tell the user which demo clip to record. Use when a prototype's work looks complete, or the user says "ship it", "tag it", "pN done".
---

# Ship a prototype

## Steps

1. Find the prototype in `PLAN.md` (§5 for P0–P6, §10 for P7+). Copy its **Definition of Done** command and expected
   output.
2. Run that DoD command and confirm the output matches. Then run `./alibi.sh test` (whole suite stays green).
   If either fails, stop: fix it or apply the prototype's "If behind" fallback, and tell the user which.
3. Check the timebox / cut rules in PLAN.md §6. If over, say so plainly.
4. Commit with the `safe-commit` skill: stage only the files this prototype changed (pathspec), message `pN works`
   (add a short body if useful). No AI co-author trailer.
5. `git tag pN` (never move an existing tag; if `pN` exists, ask).
6. If `origin` exists: `git push origin main && git push origin pN`.
7. **Stop** and tell the user:
   - what now works (one or two sentences),
   - the exact 10–15 s clip to record into `demo/clips/pN-<slug>.mov` (what's on screen, what to say or type),
   - what the next prototype is.

Don't start the next prototype in the same turn.
