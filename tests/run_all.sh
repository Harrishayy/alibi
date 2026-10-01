#!/usr/bin/env bash
# Every prototype's Definition of Done, in order, each in a fresh temp data dir. ~15 s total.
set -euo pipefail
cd "$(dirname "$0")"
source ../.venv/bin/activate
for t in pinch_selftest test_p0 test_p1 test_p2 test_p3 test_p4 test_p5 test_p6 test_p9 test_p10_p11 test_robust test_features test_backend_fixes test_integrations test_calendar test_habits_onboarding test_nodata test_journey test_mac_signals test_ios_contract test_signals test_signals_ui test_signals_lanes test_signals_hardening test_screentime_replay test_llm_guard test_pace3 test_plan_overview; do
  printf "%-8s " "$t"
  [ "$t" = pinch_selftest ] && { (cd .. && python -m alibi.pinch --selftest) || { echo FAILED; exit 1; }; continue; }
  python $t.py > /tmp/alibi_$t.log 2>&1 && tail -1 /tmp/alibi_$t.log || { echo FAILED; cat /tmp/alibi_$t.log; exit 1; }
done
