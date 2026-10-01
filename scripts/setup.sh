#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
mkdir -p data/frames data/evidence demo/clips
[ -f .env ] || cp .env.example .env
[ -d .git ] || (git init -q && git add -A && git commit -qm "scaffold" && git tag p-scaffold || true)
[ "$(uname)" = "Darwin" ] && bash scripts/build_native.sh
python -c "from alibi import db; db.connect(); print('DB ready at', db.DB_PATH)"
echo "Next: edit .env, then python scripts/smoke_test.py"
