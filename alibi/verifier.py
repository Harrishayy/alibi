"""P1/P3 — turn a session's events into on_task_ratio + verdict + evidence."""
# TODO (P1):
#   finalise(con, session, artefact=None):
#     physical -> labels = camera label events; ratio = on_task / len(labels)
#     digital  -> P3: laptop window events -> classify_titles() -> time-weighted ratio
#     hybrid   -> per minute bucket: on_task if camera OR laptop says on_task
#     verdict from habits.yaml thresholds; evidence.contact_sheet(...) or evidence.title_summary(...)
#     db.finish_session(con, id, on_task_ratio=..., verdict=..., evidence_path=..., artefact=...)
#     return a one-line human summary for notify()
#
# TODO (P3):
#   classify_titles(con, habit, titles) -> {title: label}
#     look up title_cache first; send only uncached titles in ONE llm.chat_json batch call; write back to cache
