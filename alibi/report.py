"""P4 — weekly alignment table + 3 dry sentences. Fired nightly by the daemon (or OpenClaw cron)."""
# TODO (P4):
#   build() -> str
#     week_start = Monday 00:00 local
#     for each habit in habits.yaml:
#       verified_min = sum(declared_min * on_task_ratio) for done sessions this week
#       target = weekly_target_min; status = aligned if on pace for the weekday else "behind by X min"
#     running (P5): count strava activity events this week with distance >= min_km
#     table -> llm.chat_text(TONE, table) -> return table + summary
TONE = ("You are Alibi, a dry, honest witness. Given this week's verified habit table, write 3 short sentences: "
        "what was actually done, what was claimed but not seen, and the one thing to fix tomorrow. No cheerleading.")


def build() -> str:
    return "Report not implemented yet (P4)."
