# Alibi check-in

Briefs run on their own cron jobs; the heartbeat only keeps watch. Every heartbeat, use the `alibi` skill:

1. `curl -s {{RELAY_URL}}/status`. If the Mac is offline, add one line to `memory/alibi.md` (only if the last line
   isn't already an offline note) and stop.
2. `curl -s {{RELAY_URL}}/context`. If a habit's `status3` is `off_track` and your memory has no risk note for it
   today, post one `risk` brief (slot = `slot_hint.risk` from `/context`) and note it in `memory/alibi.md`.

Reply HEARTBEAT_OK when there is nothing to say.
