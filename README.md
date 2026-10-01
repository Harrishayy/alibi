# nvidia_habits — Alibi

Habit tracker that checks your alibi. Entry for the NVIDIA London Claw Agent Challenge.

Start with **PLAN.md**. Build prototype by prototype; tag each one when its Definition of Done passes.

```bash
cp .env.example .env        # add NVIDIA key + model IDs
bash scripts/setup.sh
source .venv/bin/activate
python scripts/smoke_test.py   # must pass before P0

python -m alibi.daemon &        # long-running process (keep it in tmux)
python -m alibi.cli start "draw for 1 hour"
python -m alibi.cli status
python -m alibi.cli end
python -m alibi.cli report
```

Layout
```
alibi/       config, db (frozen contract), llm, and one module per prototype
data/        alibi.db, frames/, evidence/   (git-ignored)
demo/        shotlist.md, clips/
scripts/     setup.sh, smoke_test.py
habits.yaml  your habits, targets, what "on task" looks like
```
