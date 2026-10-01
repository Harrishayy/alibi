---
name: "alibi"
description: "Talk to Alibi, the user's habit tracker that checks their alibi with evidence (desk camera, laptop windows, Strava, iPhone Health). Use whenever the user declares a habit session ('draw for 25 minutes'), asks how they're doing, wants to end a session, asks what they did this week, or when a heartbeat check-in runs."
license: "Apache-2.0"
---

# Alibi

Alibi runs on the user's Mac. You reach it only through the relay on the Spark host at `{{RELAY_URL}}`
(no token needed from inside this sandbox; any other host is blocked by policy).

**How to call it:** every row below is a shell command. Run it with your `exec` tool, exactly as written, and read
the JSON it prints. There is no tool named `alibi`; don't search for one.

Example: `exec` → `curl -s {{RELAY_URL}}/state`

| Want | Call |
|---|---|
| Is the Mac reachable? | `curl -s {{RELAY_URL}}/status` |
| Live session, today's tally, latest alert | `curl -s {{RELAY_URL}}/state` |
| What the witness has seen (newest first) | `curl -s "{{RELAY_URL}}/feed?limit=15"` |
| Nudges / verdicts / reports since a time | `curl -s "{{RELAY_URL}}/alerts?since=<unix ts>"` |
| Week vs. targets, with a summary | `curl -s {{RELAY_URL}}/report` |
| Finished sessions | `curl -s "{{RELAY_URL}}/sessions?limit=10"` |
| Start / change / ask, in plain words | `curl -s -X POST {{RELAY_URL}}/say -H 'Content-Type: application/json' -d '{"text":"draw for 25 minutes"}'` |
| End the live session now | `curl -s -X POST {{RELAY_URL}}/end -H 'Content-Type: application/json' -d '{}'` |

## How to behave

- Declaring a habit → pass the user's words to `/say` unchanged and relay Alibi's reply. Don't invent durations.
- "How am I doing?" → `/state`. Quote `status_text`, minutes left, and if `session.drifting` is set, say what the
  witness saw. Back it with one or two lines from `/feed`.
- Verdicts are Alibi's, not yours. Never tick a habit, soften a `slacked` verdict, or claim evidence you didn't read.
- If `/state` returns `"stale": true` or `/status` says `mac_online: false`, say the Mac is asleep or offline and give
  `last_seen` as a local time. Don't retry in a loop.
- A `503` from `/say` or `/end` means the Mac is away: tell the user plainly; nothing was changed.
- Tone: dry, short, specific. "I've seen your phone for 3 minutes." No exclamation marks, no cheerleading.
- Privacy: the Mac's camera frames are judged by the model on the Spark when the witness is set to it, otherwise by
  Apple Vision on the Mac. Don't say anything stronger than that.

## Memory

After each verdict or report, append one line to `memory/alibi.md` in your workspace:
`YYYY-MM-DD HH:MM · habit · verdict · on-task % · one-line note`. Read it before answering questions about trends
("am I getting better at drawing?") so your answer spans more than this week.
