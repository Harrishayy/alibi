#!/usr/bin/env bash
# Every prototype's Definition of Done, in order, each in a fresh temp data dir. ~10 s total.
set -euo pipefail
cd "$(dirname "$0")"
source ../.venv/bin/activate
for t in test_p0 test_p1 test_p2 test_p3 test_p4 test_p5 test_p6 test_p9 test_p10_p11; do
  printf "%-8s " "$t"; python $t.py > /tmp/alibi_$t.log 2>&1 && tail -1 /tmp/alibi_$t.log || { echo FAILED; cat /tmp/alibi_$t.log; exit 1; }
done
