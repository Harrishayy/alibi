# Voice

Alibi sounds like a dry, fair witness: it says what it saw, with a number, and then tells you how to fix the record. It never shames, never shouts and never guesses at motives.

## Who speaks

- **Pinch (Alibi's voice)** speaks in the first person: "I saw", "I've changed". It speaks in nudges, verdict sentences, the honesty line's follow-ups, the nightly report, celebrations and Pinch-led empty states. Set it in `voice` on the web (`island-voice` in the island, `ios-body` on the iPhone), usually in `Alibi.PinchLine`.
- **The chrome** speaks in neutral imperatives with no "I": buttons, labels, settings, errors and permission copy. Set it in `body`, `small` and `label`.

## Rules

1. **Sentence case everywhere**, including buttons, tabs, toasts and section titles. The only uppercase is the "ALIBI" wordmark.
2. **12 words or fewer** per Pinch line, and per sentence of the report.
3. **No "!" and no emoji**, ever, including on wins.
4. **Digits for numbers:** "3 minutes", "25 of 25", "92%".
   - Pinch says "minutes"; the chrome says "min" ("25 min").
   - Wings and compact slots say `24m`, and totals are `2h 10m`.
   - Times are 24-hour ("18:04").
5. **Facts before feelings.** Lead with what was seen. Don't use adjectives where a number will do.
6. **Name the cause, never the person.** Only the noun of a bad fact is set in `warn-ink` ("phone", "YouTube"). Avoid "you failed", "lazy", "caught", "busted", "cheat" and "are you even trying".
7. **Always offer the fix.** Every bad verdict and every error ends with the next step.
8. **Buttons are verbs, three words at most:** Back to it, This counts, Quiet 5 min, See proof, Fix a moment, Go again, Start 25 min.
9. **Contractions are fine** ("I've", "can't"). Write "Oops" and "Uh-oh" nowhere.
10. **British spelling** (colour, recognise), because Alibi is a London entry.
11. **Be honest about where frames go.**
    - With Apple Vision or a local `VLM_BASE_URL`: "Frames stay on this Mac."
    - With an NVIDIA Build endpoint: "Frames go to NVIDIA's endpoint to be judged."
    - Never claim "frames never leave my network" unless the vision model runs locally.

**Words we use:** claim, alibi, seen, on task, drift, nudge, verdict, Done, Partly, Slacked, proof, frame, streak, freeze, rest day, session, habit.
**Words we avoid:** fail, score, productivity, punish, lose, cheat, discipline.

## Nudges

Only the noun takes `warn-ink`. Each nudge offers Back to it, This counts and Quiet 5 min.

| Trigger | Line |
|---|---|
| `phone`, first nudge | "You said drawing. I've seen your phone for 3 minutes." |
| `phone`, second nudge | "Phone again, 4 minutes this time. Back to the sketchbook?" |
| `off_task` (window title) | "You said C++. That's been YouTube for 4 minutes." |
| `off_task` (desk) | "You said guitar. I've seen a laptop for 5 minutes." |
| `idle` | "You said writing. The page hasn't moved in 6 minutes." |
| `absent` | "Your desk's been empty for 5 minutes. Still drawing?" |
| back on task (recovery) | "Back on the sketchbook. Noted." |
| This counts | "Noted. Phone counts as part of drawing this session." |
| Quiet 5 min | "Quiet for 5 minutes. I'll keep watching." |

## Verdicts

The pill carries a glyph and a word (✓ Done, ◐ Partly, ✕ Slacked). The sentence beneath it states the count. The verdict card adds up to three sentences in `voice`.

| Outcome | Line |
|---|---|
| `done` | "Done. 25 of 25 minutes at the desk, pencil in hand." |
| `done`, finished early | "Done early. 20 minutes, every one of them on task." |
| `done`, from Strava | "Done. 5.2 km in 28 minutes. Strava has the receipts." |
| `partial` | "Partly. 17 of 25 minutes on task. The phone had the rest." |
| `partial`, kind follow-up | "Over 60%, so the streak holds." |
| `slacked` | "Slacked, by my count. 6 of 25 minutes on task." |
| `slacked`, kind follow-up | "Tap any frame if I got it wrong." |
| `slacked`, next step | "Tomorrow, 20 minutes? I'll be here." |
| missed planned block | "Drawing was planned for 19:00. Nothing claimed, so nothing to check." |

## Nightly report

Use three sentences of 12 words or fewer, each in `voice`, with Pinch `reading`:

> "You claimed three hours. I saw two and a half. Drawing carried the day."

> "Two sessions, both checked out. Guitar was the quiet win."

## Empty states

Each empty state is one sentence, one primary button and Pinch at rest.

| Where | Line | Button |
|---|---|---|
| Today, nothing claimed | "Nothing claimed yet. What are you about to do?" | (the composer is the action) |
| This week, first week | "A week from now, this will tell you something true." | Plan this week |
| Sessions | "No sessions yet. Your first alibi starts in the box above." | — |
| Contact sheet, camera was off | "No frames for this one. The camera was off." | See window titles |
| iPhone Week, no data | "Nothing to compare yet. Finish a session on your Mac." | — |
| Rest day | "Rest day. Nothing to check." | — |

## Onboarding

There are at most four steps and 60 seconds, ending in a 30-second practice session.

| Step | Line |
|---|---|
| Welcome (`hello`) | "I'm Pinch. You say what you'll do; I check." |
| Habits | "Pick up to three things you want to show up for." |
| Camera (chrome, Apple Vision) | "During a session, Alibi glances at your desk. Frames stay on this Mac." |
| Camera (chrome, NVIDIA endpoint) | "During a session, frames go to NVIDIA's endpoint to be judged." |
| Camera, outside sessions (chrome) | "The camera is off whenever no session is running." |
| Practice | "Let's try 30 seconds. Type what you're doing." |
| Practice done | "That one checks out. You're set." |

## Errors, with fixes

Errors are chrome copy, never Pinch. Each states what happened, then what to do.

| Problem | Line |
|---|---|
| Camera permission denied | "Alibi can't see the camera. Allow it in System Settings › Privacy & Security › Camera." |
| Camera busy | "Another app is using the camera. Close it, then press Retry." |
| Daemon offline (island) | "Alibi isn't running. Start it with ./alibi.sh up." |
| iPhone can't reach the Mac | "Can't reach your Mac. Check you're both on Tailscale, then pull to refresh." |
| Vision endpoint down | "The vision model didn't answer. Using Apple Vision for now." |
| Strava disconnected | "Strava disconnected. Reconnect it in Setup › Connections." |
| Health stale | "No Health data since yesterday. Open Alibi on your iPhone to sync." |
| Calendar unavailable | "Calendar access is off. Turn it on in Setup › Connections to see plan blocks." |
| Correction failed | "That change didn't save. Check Alibi is running, then try again." |

## Celebrations and streaks

| Moment | Line |
|---|---|
| First win ever (big celebration) | "First alibi checks out. I saw every minute." |
| Streak day 3 | "Three days in a row. That's how it starts." |
| Streak day 7 | "A week of alibis that checked out." |
| Streak day 14 | "Two weeks. I've stopped being surprised." |
| Every 7th day after | "Day 21. Showing up is starting to look like you." |
| Freeze used | "Missed yesterday. I used your freeze; the streak's intact." |
| Streak reset | "New streak, day 1. The last one ran 12 days." |
| Streak badge (chrome) | "6 days · 1 freeze left" |
| Integration connected (`connected`) | "Strava's connected. Your runs count as evidence now." |

## Corrections

| Moment | Line |
|---|---|
| Sample corrected (`surprise`) | "Fair. I've changed that one." |
| Correction changes the verdict | "Fair. That makes it done, 21 of 25 minutes." |
| Undo (chrome toast) | "Changed back." with an Undo button for 6s |
| Popover title (chrome) | "What was happening at 18:04?" |

## Live Activity strings

| Slot | String |
|---|---|
| Lock Screen title | "Drawing" (the habit, sentence case, 18 characters at most) |
| Lock Screen row 3, on task | "On task 92% · last seen 18:04" |
| Drifting | "Phone · 3 min" |
| Break | "On a break · back 18:20" |
| End: done | "✓ Done" over "25 of 25 min on task" |
| End: partial | "◐ Partly" over "17 of 25 min on task" |
| End: slacked | "✕ Slacked" over "6 of 25 min on task" |

## Island wing values

The trailing wing holds one short value in `island-wing` (13pt rounded semibold, monospaced digits). It fits in 46pt.

| State | Value | Ink |
|---|---|---|
| more than a minute left | `24m` (rounded up) | `accent-ink` |
| over an hour left | `1h 5m` | `accent-ink` |
| final minute | `45s` | `accent-ink` |
| planned block now | `now` | `ink` |
| drifting to the phone | ■ `phone` | `warn-ink` |
| absent | ◌ `away` | `absent-ink` |
| on a break | `cup` icon + `4m` | `partial-ink` |
| just finished (6s) | `✓`, `◐` or `✕` | its verdict ink |
