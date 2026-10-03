#!/usr/bin/env bash
# Every feature's Definition of Done, in order, each in a fresh temp data dir. About 3 min total.
set -euo pipefail
cd "$(dirname "$0")"
source ../.venv/bin/activate
for t in pinch_selftest test_p0 test_p1 test_p2 test_p3 test_p4 test_p5 test_p6 test_p9 test_p10_p11 test_robust test_features test_backend_fixes test_integrations test_calendar test_habits_onboarding test_nodata test_journey test_mac_signals test_ios_contract test_signals test_signals_ui test_signals_lanes test_signals_hardening test_screentime_replay test_llm_guard test_pace3 test_plan_overview test_egress test_phone_writes test_digest test_digest_off test_relay test_video_witness test_mesh test_run_intent test_night_order test_strava_live test_focus_guard test_away test_wave1_state test_wave1_offplan test_web_wave1 test_created_prompt test_plan_days test_wave3_cards test_focus; do
  printf "%-8s " "$t"
  [ "$t" = pinch_selftest ] && { (cd .. && python -m alibi.pinch --selftest) || { echo FAILED; exit 1; }; continue; }
  python $t.py > /tmp/alibi_$t.log 2>&1 && tail -1 /tmp/alibi_$t.log || { echo FAILED; cat /tmp/alibi_$t.log; exit 1; }
done
