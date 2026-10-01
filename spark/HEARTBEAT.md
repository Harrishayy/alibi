# Alibi check-in

Every heartbeat, use the `alibi` skill:

1. `curl -s {{RELAY_URL}}/status`. If the Mac is offline, note it once in `memory/alibi.md` (only if the last line
   isn't already an offline note) and stop.
2. Read the last timestamp you handled from `memory/alibi-cursor` (0 if missing) and fetch `/alerts?since=<that>`.
3. For each new `verdict` or `report` alert, append its line to `memory/alibi.md`.
4. For a new `nudge`, or if `/state` shows `session.drifting`, write one dry sentence to the user, quoting what the
   witness saw. At most one message per heartbeat.
5. If no session is running and today's tally is below target after 18:00 local, say which habit is still open
   for today, once per day.
6. Save the `now` value from `/alerts` to `memory/alibi-cursor`.

Reply HEARTBEAT_OK when there is nothing to say.
