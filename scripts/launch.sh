#!/usr/bin/env bash
# Foreground launcher used by Alibi.app and `./alibi.sh up`: daemon in the background, island in front.
# Quitting the island (or killing this script) stops the daemon and turns the camera off.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p data/logs
source .venv/bin/activate
python -m alibi.daemon >> data/logs/daemon.log 2>&1 &
DAEMON=$!
echo "$$ $DAEMON" > data/alibi.pid
cleanup() { kill $DAEMON ${ISLAND:-} 2>/dev/null; rm -f data/alibi.pid; }
trap cleanup EXIT INT TERM
sleep 1.5
bin/alibi-island >> data/logs/island.log 2>&1 &
ISLAND=$!
echo "$$ $DAEMON $ISLAND" > data/alibi.pid
wait $ISLAND
