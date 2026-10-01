#!/usr/bin/env bash
# Start the long-running daemon (API + dashboard on :8765) and the notch island. Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
[ -x bin/alibi-island ] && [ -x bin/alibi-witness ] || bash scripts/build_native.sh
python -m alibi.daemon &
DAEMON=$!
trap 'kill $DAEMON $ISLAND 2>/dev/null' EXIT
sleep 2
bin/alibi-island &
ISLAND=$!
echo "Alibi running — hover the notch, or open http://127.0.0.1:8765"
wait $DAEMON
