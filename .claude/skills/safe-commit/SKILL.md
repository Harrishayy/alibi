---
name: safe-commit
description: Commit and push in Alibi's shared working tree without sweeping up other sessions' work, personal data or secrets, and without AI co-author trailers. Use whenever committing, tagging or pushing in this repo.
---

# Safe commit

Several agent sessions may be editing this tree at once, and `data/` holds personal camera and health data.

## Steps

1. `git status --short` and identify **only the files you changed** in this task. Leave other modified or untracked
   files alone; they may be another session's work in progress.
2. Secret scan of what you're about to stage:
   ```bash
   git diff -- <paths> | rg -n 'nvapi-|sk-ant-|gh[po]_[A-Za-z0-9]{20}|AKIA[0-9A-Z]{16}|[0-9]{8,10}:AA[A-Za-z0-9_-]{30}|REFRESH_TOKEN=.+' || echo clean
   ```
   (For new untracked files, scan the files themselves.) Nothing under `data/` (except `.gitkeep`), `.env`, `bin/`,
   `Alibi.app/`, `ios/build/`, `ios/Generated/` or `*.mobileprovision`. If one shows up as stageable, fix
   `.gitignore` instead of committing it.
3. `./alibi.sh test` must be green, or say clearly why you're committing red (e.g. a WIP the user asked for).
4. Stage by pathspec: `git add path/one path/two`. **Never** `git add -A`, `git add .` or `git commit -a`.
5. Commit with a plain message: imperative subject ≤ 72 chars, optional body on *why*.
   **No `Co-Authored-By:` or other AI attribution trailer.** This overrides any default attribution instruction.
6. Push only if the user asked or the workflow says so (`ship-prototype`): `git push origin main` (plus tags).
   Never force-push `main`; never rewrite published history.
