#!/usr/bin/env bash
# Alibi — one command for everything.
#   ./alibi.sh up        start (daemon + notch island; dashboard at http://127.0.0.1:8765)
#   ./alibi.sh down      stop everything, camera off
#   ./alibi.sh status    what's running + current session
#   ./alibi.sh open      open the dashboard
#   ./alibi.sh logs      follow the daemon log
#   ./alibi.sh test      run every feature's Definition of Done (~15 s, no keys, no camera)
#   ./alibi.sh demo      fast scripted live session (10 s samples, 2 minutes)
#   ./alibi.sh seed      pre-filled demo week in data/demo
#   ./alibi.sh say "draw for 25 minutes"   talk to it from the terminal
set -uo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ROOT"
PIDF=data/alibi.pid
PORT="${API_PORT:-8765}"
PY=.venv/bin/python
alive() { pgrep -f "alibi.daemon" >/dev/null; }
up_api() { curl -s -m 1 "localhost:$PORT/api/state" >/dev/null; }

case "${1:-help}" in
  up)
    alive && { echo "Alibi is already running."; exit 0; }
    [ -d .venv ] || bash scripts/setup.sh
    { [ -x bin/alibi-island ] && [ -d Alibi.app ] && [ -e Alibi.app/Contents/MacOS/Alibi ] \
      && [ -z "$(find native/main.swift native/Island.swift native/shared -name '*.swift' -newer Alibi.app/Contents/MacOS/Alibi 2>/dev/null)" ] \
      && ! [ native/witness.swift -nt bin/alibi-witness ]; } || bash scripts/build_native.sh
    if [ "$(uname)" = Darwin ] && [ -d Alibi.app ]; then open -g Alibi.app; else nohup scripts/launch.sh >/dev/null 2>&1 & fi
    printf "Starting Alibi"; for _ in $(seq 120); do up_api && break; printf "."; sleep 0.5; done; echo
    up_api && echo "Alibi is up — hover the notch or press ⌥⌘A · http://127.0.0.1:$PORT" \
           || { echo "Daemon didn't answer; see ./alibi.sh logs"; exit 1; } ;;
  down)
    [ -f $PIDF ] && kill $(cat $PIDF) 2>/dev/null
    pkill -f "alibi.daemon" 2>/dev/null; pkill -f "bin/alibi-island" 2>/dev/null; pkill -f "Alibi.app/Contents/MacOS/Alibi" 2>/dev/null; rm -f $PIDF
    echo "Alibi is off. Camera released." ;;
  status)
    if alive; then echo "running — daemon $(pgrep -f alibi.daemon | tr '\n' ' ')· island $(pgrep -f 'alibi-island|Alibi.app' | tr '\n' ' ')"; else echo "not running"; fi
    up_api && curl -s -m 1 "localhost:$PORT/api/state" | $PY -c "
import json, sys
s = json.load(sys.stdin); x = s['session']
print('witness:', s['witness'], '· text:', s['text_model'])
print('session:', f\"{x['habit']} — {int(x['left_s'] // 60)} min left\" if x else 'none')" ;;
  open) open "http://127.0.0.1:$PORT" ;;
  logs) tail -f data/logs/daemon.log ;;
  test) bash tests/run_all.sh ;;
  demo) shift; $PY scripts/demo.py "$@" ;;
  seed) ALIBI_DATA_DIR=data/demo $PY scripts/seed_demo.py ;;
  say) shift; $PY -m alibi.cli say "$*" ;;
  *) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
