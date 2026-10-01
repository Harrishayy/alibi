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
   Never force-push `main`; never rewrite published history. **Squash first** (next section).

## Before every push: squash the local history

Local commits are fine for tracking each step, but the pushed history should be ~10–15 commits per push.

1. `git fetch origin && git log --oneline origin/main..main` — this range is the only history you may rewrite.
2. Propose groups (by feature / prototype, e.g. "P7 digests + replan agent", "Island redesign"), each with a
   subject line and the commits it absorbs. Show the user the plan and **wait for an OK**.
3. Make sure no other session is mid-commit (`git status`; ask over SendMessage if other sessions are live).
   Stash nothing of theirs: rewrite with a clean tree or `git rebase --autostash`.
4. Rebuild the range. Agents can't drive an interactive editor, so script the todo list:
   `GIT_SEQUENCE_EDITOR="cp todo.txt" git rebase -i origin/main` with a prepared `pick`/`fixup` list, or
   `git reset --soft` + re-commit by pathspec per group when the groups are contiguous.
   Keep messages plain, no AI trailers.
5. Before rewriting, note which tags sit in the range (`git tag --merged main --no-merged origin/main`); afterwards
   `git tag -f pN <new-sha>` each one onto the squashed commit that holds its work. Never move a tag that's
   already on `origin` (`git ls-remote --tags origin`).
6. `./alibi.sh test` on the result, confirm `git diff <old-head> HEAD` is empty, then push `main` and the tags.
