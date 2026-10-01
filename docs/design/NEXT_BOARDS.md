# Next-phase UI: health strip, digest, Gantt, egress, Ask

Build plan: [`NEXT_UI.md`](NEXT_UI.md) says what to build, in what order, against which endpoints. Narrative reference: the user's prototype,
[Alibi Next Phase](https://claude.ai/artifact/NNipi7DhjVYKVTLzeAM3sn). The server contract wins on words and data, the boards win on pixels (NEXT_UI.md, Precedence).

Design-only prep for T1 (docs/NEXT_PHASE.md §3 F2, F4b, F5, F6, F8 and the §5 fluid spec). Nothing here changes product code. The boards sit in
`docs/design/canvas/project/` next to `Dashboard.dc.html` and reuse its column, type, spacing and components exactly. They are not registered in `canvas.json` yet.

| Board | Size | Interactive | What it shows |
|---|---|---|---|
| `Next-Today.dc.html` | 1440 × 2062 (fluid page; give it `expand: fill` when it goes into `canvas.json`) | yes | Dashboard top area: hero, Now, then **Today** with the health strip and the digest card. Tweaks `state`: `night` (proposal + trace) · `accepted` (toast + undo) · `morning` (memory callback) · `rules` (Spark down); `theme`: `dark` · `light` |
| `Next-Digest-Light.dc.html` | 976 × 992 | yes | The digest card alone in `light`, with the same `state` tweak |
| `Next-Gantt.dc.html` | 1440 × 936 | yes | Week Gantt (F4b) with Drawing selected; click any row. Tweak `selected` |
| `Next-Signals-Egress.dc.html` | 1280 × 900 | yes | Egress block at the top of `/signals`. Tweaks `spark` (`on`/`off`) and `scope` (`all`/`mac`/`tailnet`/`internet`) |
| `Next-Ask.dc.html` | 1440 × 900 | yes | Ask drawer over the dimmed dashboard. Tweak `stage`: `contacting` · `waiting` · `links` · `done` · `off`. Send replays the stages at 500 ms poll ticks |

Lint: `python3 -B docs/design/canvas/tools/lint_next.py` (static), or add `--render DIR` to render every enum tweak over a free loopback port (DIR holds `support.js`
and the component bundle). It runs every `lint_mac.py` check plus the 4/8 spacing ladder, motion properties and tokens, weights and tracking, no "!", Pinch lines of
12 words or fewer, and the four status words.

## Shared rules for every piece

- **Status = mark + shape + word.** The mark is 8 px and drawn in the `-ink` token, so it holds 3:1 in light too.

  | Status | Mark | Word | Pill fill |
  |---|---|---|---|
  | `on_track` | ● filled circle | On track | `surface-2`, word `ink-2` (good news stays quiet) |
  | `at_risk` | ◐ half-filled ring, `partial-ink` | At risk | `partial-wash`, word `partial-ink` |
  | `off_track` | ■ 2 px-radius square, `warn-ink` | Off track | `warn-wash`, word `warn-ink` |
  | `stale` | ◌ 1.5 px dashed ring, `absent-ink` | Can't see | `surface-2`, word `ink-2` |

  A milestone row carries an outlined ◇ diamond in `partial-ink`, then the pill for its `status`: At risk within a day of `due`, Off track once past due and not
  done, Done when `done_at` is set. A pending milestone shows only its due date.

  Pills are 24 px tall, `radius-pill`, padding `0 12px 0 8px`, gap 8, `label` type. There are no red bar fills anywhere. Bars and meters stay neutral, and the pill carries the status.
- **Numbers** use `tabular-nums` everywhere. Chrome says "min", Pinch says "minutes", and times are 24-hour.
- **One primary button per view**: black on `#76B900` (`Alibi.Button variant="primary"`). Everything else is secondary or quiet.
- **Motion**: transform and opacity only (plus colour crossfades), with tokens only. Entrances run `dur-medium`, `ease-out`, 6 px lift, a 40 ms stagger capped at 6, and play on first paint only. Swaps blur 8 → 0 (labels 4 → 0) over `dur-medium`. Exits run at 0.65×. Under reduced motion, keyframes collapse to 1 ms through `bundle.css`, springs become 150 ms ease, and count-ups jump to their final value (`matchMedia` check in the board logic). Checked with `render.py --reduced-motion`.
- **Server words are shown as sent:** `reply`, `why`, `result`, memory lines, `json.pinch`, `reason`, the proposal question, egress `why` and `summary.text`. On a
  board, those strings match the code word for word (checked against f635c79); any other text is client copy or example data. The numbers are hand-cut example
  data (§1 says how), so a golden dump (NEXT_UI ask 1) will move them.

## 1. Health strip (F2), top of Today

A `surface-1` card (`radius-md`, padding 24, gap 16) placed first inside the Today section, above the digest card and the existing timeline.

- **Head:** `h3` rollup, then a `small` line naming the worst two, then week-left meta on the right in `ink-3`.
  - Rollup: "4 of 6 habits on track", counted from `status3` over the six weekly habits (Running included; Sleep and the milestone don't count).
  - Worst two: "Internships is off track: 78 min behind. Drawing is at risk: 40 min behind."
  - Week left: "Week ends Sunday · 3 days left after tonight".
- **Rows** (min-height 48, hairline between, flex-wrap so 375 px works):
  - name: 16 px, with a 16 px `ink-3` icon;
  - status pill in a 104 px slot;
  - **the one actionable line** (`reason`) in `body` 16, `ink` (or `ink-2` when on track);
  - the meter;
  - a value in `small` `ink-2`, such as "44 of 150".
- **Meter:** a 120 × 4 track on `surface-3` with the fill in `ink-2`, drawn with `scaleX(V/T)`. A 2 × 16 `ink` tick marks `P(now)/T`, so the gap between the fill end and the tick *is* the buffer. A two-item legend sits under the rows.
- **Count-up synced to its shape (§5):** the number and `scaleX` read **one clock** in JS, 900 ms from +420 ms on first paint, eased by `cubic-bezier(.23,1,.32,1)`, which is solved in the board so the curves match exactly. Later value changes retarget from the shown value at once (no delay).
- **Copy per row.** A habit's line is the server's `reason`, as sent. These are the forms `report._reason()` writes, and the board uses the exact strings
  `report.pace3` gives for its numbers:

  | Case | `reason` | On the board (Thu 22:00) |
  |---|---|---|
  | behind, time to catch up | "{gap} min behind. {need_per_day_min} a day until Sunday." (rounded to the nearest minute) | Drawing "40 min behind. 34 a day until Sunday." |
  | behind, scheduled, can't catch up | "{gap} min behind. Only {left planned} min planned." | Internships "78 min behind. Only 45 min planned." |
  | behind, last day | "{gap} min behind. {left} min to go today." | none |
  | ahead | "{buffer_days} days of buffer." (half steps, "1 day of buffer.") | Building "1.5 days of buffer.", Running "1 day of buffer." |
  | on pace | "On pace." | C++ "On pace." |
  | done · new · stale | "Done for the week." · "New this week. No pace yet." · "Can't see Strava. Nothing new in a day." or "Can't see your phone. Nothing in 6 hours." | none |

  When a habit is at risk or off track but not behind pace yet, the first sentence is "{left} min to go." Count habits say runs and keep one decimal: "1 run
  behind. 0.3 a day until Sunday."

  Two rows aren't habits. The milestone (F3 T1) line comes from `due`: "Due tomorrow." (night), "Due today." (morning). `done_at` is set by hand in
  `goals.json` in T1, so the row offers no tick. Sleep is board only: "No sleep data until your iPhone syncs." with the value "Synced 15:40".

- **Sleep:** the board draws it as a strip row. The build keeps Sleep in the Health lines (NEXT_UI D1a), so the strip holds the six habits plus the milestone.
- **Data used** (Thu 1 Oct 22:00, 56% of the week gone, 3.08 days left; the same week as the Gantt, §3):

  | Habit | T | V | P | Status | `buffer_days` · `need_per_day_min` |
  |---|---|---|---|---|---|
  | Drawing | 150 | 44 | 84 | at risk | −2 · 34 |
  | Building | 180 | 134 | 101 | on | 1.5 · 15 |
  | Math | 200 | 125 | 112 | on | 0.5 · 24 |
  | C++ | 150 | 84 | 84 | on | 0 · 21 |
  | Internships (scheduled Mon/Wed/Fri) | 135 | 12 | 90 | off (T−V > 45 min planned) | −1.5 · 40 |
  | Running (count) | 3 | 2 | 1.68 | on | 1 · 0.3 |
  | Sleep (Health; board only) | — | — | — | stale (no phone row in 6 h) | — |

  The values are hand-cut. Internships is paced by its blocks; every other habit is paced in a straight line (P = T × share of the week gone), as if it had no
  schedule. In the product, a habit with a `schedule` is paced by its finished blocks (`report.pace3`), so a golden dump will move these numbers and may change
  statuses.

  Morning (Fri 07:30) values are in the board too. No session lands overnight, so Drawing turns off track: "48 min behind. 39 a day until Sunday."

## 2. Digest card (F5)

A `surface-1` card (`radius-md`, padding 24, gap 24) directly under the health strip. Data: one row from `GET /api/digests` (NEXT_UI D1b). **Head:** `h3` title
("Night review" / "Morning brief") with time meta in `ink-3`, and a `via` tag on the right (24 px, `radius-xs`, `surface-2`, `label`): "via Spark" for `llm:spark`,
"via NVIDIA Build" for `llm:build`, "via rules" for `rules`. Morning briefs are always "via rules". No digest says NemoClaw.

**Choreography (docked next action enters last):**

| t (ms) | Element |
|---|---|
| 0 | facts: the claimed vs seen sentence, then one row per session or block, staggered 40 ms |
| 1000 | Pinch line (`PinchLine` mood `reading`), opacity plus a 4 px lift |
| 1260 | confirm card, with blur 8 → 0 and scale 0.97 → 1 |
| — | the trace (when open) enters with the card. Its rows stagger 40 ms |

**Night facts** (from the row's `json`):
- the `h3` sentence "Claimed 2h 05m today. Seen 1h 42m.", summed from `declared_min` and `seen_min` over `json.done`, `partial` and `slacked`;
- rows of `time · VerdictPill · Habit, meta` from those lists ("44 of 45 min seen");
- a missed block from `json.missed` uses a neutral ◌ "Missed" pill and "planned for 25 min. Nothing claimed." (no red: nothing was claimed, so nothing was slacked).

Pinch: `json.pinch`, "Closing the file on today."

**Confirm card** (`surface-2`, `radius-sm`, padding 16), while the row has a `proposal` and no `accepted_at`:
- `label` "Proposed for tomorrow";
- `h3` the server's question, the last line of `text`: "Move drawing to tomorrow 07:30, 25 min?";
- `small` "Fri 2 Oct, 07:30 to 07:55 · " and then `proposal.why` as sent. The model writes `why` (200 characters at most): the board's is "Furthest behind, and
  free until Building at 10:00.", the test fixture's "Furthest behind; 07:30 is free after building.";
- **one** primary "Move drawing to 07:30" (calendar icon) and a quiet "Not now".

**Trace disclosure:** a full-width `<button aria-expanded>` (min 44 px) holds a chevron (rotates 90° on `spring-snappy`), the summary "Checked week → plan tomorrow →
free gaps → proposed 07:30" and, on the right, "4 model turns · 3.1 s" (`turns`, `total_ms`; the `via` tag is already in the head). Open, it shows an `<ol>`
with one row per `trace[]` step:
- the index;
- the call in `--font-mono` 12, from `tool` and `args` (`free_gaps(day="2026-10-02", min_minutes=25)`). A long string argument (the model's `why`) is cut at a
  word with "…", because the card above shows it in full;
- `result` in `small` `ink-2`, as sent (60 characters at most): "drawing −2 d behind most", "3 blocks tomorrow", "07:00–10:00, 10:45–16:00, 16:50–20:30,
  21:15–22:00", "valid";
- `ms` on the right: in-process reads, 0 to 2 ms each ("<1 ms" for 0).

The foot line reads "4 model turns on your Spark, 3.1 s in all. Alibi checked the slot itself. Nothing changes until you tap." The numbers are `turns` and
`total_ms`; count turns, never steps, because two calls can share a turn. The trace is open by default on the night card and closed after accept.

**States:**
- **accepted:**
  - The confirm card swaps (blur) to a `role=status` row with a ✓ in `accent-wash`: the accept `reply` as sent ("Done. Drawing tomorrow 07:30, 25 min. It's on the
    plan."), the meta "Added at 22:06." (`accepted_at`) and a quiet Undo. After a reload there is no `reply`, so the line is the proposal as data ("Drawing, Fri 2
    Oct, 07:30 to 07:55.") over the same meta. The trace stays below as a closed one-line disclosure, and its foot line drops "Nothing changes until you tap."
  - An `Alibi.Toast kind="info" icon="calendar"` appears top-right: title "Tomorrow · Fri 2 Oct" (from `block.date`), body the same `reply`, with a secondary Undo.
    It auto-dismisses after **6 s**.
  - Undo posts `POST /api/digests/{slot}/undo`, shows its `reply` ("Removed drawing from tomorrow 07:30.") and brings the confirm card back. Accepting an accepted
    proposal does nothing: "Already on the plan: drawing tomorrow 07:30, 25 min.", and no second toast.
- **dismissed** ("Not now", client-only; nothing is posted): "Not added. Tomorrow stays as planned." with a quiet "Show it again".
- **morning** (Fri 07:30, "via rules"):
  - The callback block (`surface-2`) comes first: `label` "Last night's plan", then `json.memory.text` as sent ("Last night you moved drawing to 07:30. It's on
    now."). Its meta is "07:30 to 07:55 · added from last night's review" (`memory.at`, `minutes`) until the block ends, then "Seen 22 of 25 min" (`seen_min`,
    `minutes`).
  - While `memory.state` is upcoming or now, the block holds the view's one primary, "Start 25 min": `POST /api/calendar/plan/start {key}`, with the key of the
    `json.blocks` entry that has the memory's habit and `at`. Once the block has ended, a pill from `memory.state` takes its place: kept → VerdictPill done,
    partial → VerdictPill partial, missed → the neutral ◌ "Missed" pill.
  - The server's lines: "Last night you moved drawing to 07:30." and then one of "It's on today's plan." (before the block), "It's on now." (in its window, no
    session yet), "You're on it now." (a session is running), "You showed up for 22 of 25 minutes." (kept at 80% of the minutes or more, partial below), or "You
    didn't make it." The day after the block, the lead is "You moved drawing to 07:30 yesterday." A session counts from 60 min before the block to 30 min after its
    end.
  - The line is frozen when the brief is built, so at 07:30 a 07:30 block reads "It's on now." "22 of 25" needs a brief built after the block (NEXT_UI §0
    `digest-kept`, ask 11).
  - Then today's rows from the `json`: the first free gap at 07:55 (`json.first_gap`: "First free gap, until 10:00"), the rest of `json.blocks` ("Building, 45
    min planned") and "Slept 7h 05m, from iPhone Health" (`json.sleep_h`).
  - Pinch: `json.pinch`, "Morning. I've got the plan. You've got the pen."
  - A secondary "See today's plan" closes the card.
- **rules:** the same layout with the "via rules" tag.
  - **The rules picker lands on 07:00, not 07:30** (first gap ≥ `default_min` from 07:00), so the button reads "Move drawing to 07:00". Its `why` is the habit's
    `reason`: "40 min behind. 34 a day until Sunday."
  - With the Spark down nothing answered (`turns: 0`), so the trace has one row: `rules picker`, "drawing tomorrow 07:00, 25 min". The summary reads "Rules picked
    07:00", with "No model turns · 40 ms" on the right. When the model answered but its plan failed, its rows stay (the failing one reads "invalid: …") and the
    `rules picker` row follows.
  - The foot line: "The rules on this Mac picked the slot. Same card, same accept. Nothing changes until you tap." It gives no reason, because the row has no field
    for one (NEXT_UI ask 12).
  - `total_ms` is example data. In a real fallback it includes the failed model call, which can run to the 45 s budget when a connection hangs (NEXT_UI ask 15).
  - The header's Ask button is hidden, because NemoClaw runs on the Spark (the product gates it on `capabilities.ask`, NEXT_UI D1e). The page footer keeps the
    Camera frames `why` and swaps "Habit names and minutes go to your Spark over Tailscale." for `summary.text`, "Summaries stay on this Mac."
- **light:** `Next-Digest-Light.dc.html`. The same tokens resolve to the light theme, and the marks use `-ink` tokens, so they pass on white.

**Example data on these boards** (Today and Light alike): the numbers (§1), the night row's 4 turns and 3.1 s (the test fixture has 3 turns), the model's `why`,
and the Sleep strip row. Every server string on them is the code's: `json.pinch`, `reason`, `result`, the question, `reply`, the memory line and the egress
copy in the footer. The night list holds sessions and missed blocks only, so Thursday's Strava run isn't in it (runs aren't sessions).

## 3. Week Gantt (F4b)

It sits in the This week section, inside the 880 column. The card has padding `16 24`, and its grid is `152px | 7 × 64px | 184px`. Data: `/api/plan/overview`
(NEXT_UI D1d).

- **Day header:** `label` "Mon 28" … "Sun 4". Today's column carries a `surface-2` band (`radius-xs`) behind every row, and its label is in `ink`.
- **Rows** are `<button aria-pressed>`, 56 px, `radius-sm`.
  - Selected: `surface-3` with the name at weight 600; the background crossfades over `dur-micro`.
  - Name and icon on the left, the week in the middle, the status pill and a short number on the right ("40 min behind · 34/day", from `pace_min` −
    `verified_min` and `need_per_day_min`).
  - Icons: camera for Drawing and Math, laptop for Building, C++ and Internships, run for Running.
- **Blocks:**
  - Per day, bars are scaled 0.8 px per minute (50 min = 40 px), 12 px tall, `radius` 3, starting 6 px into the cell.
  - Planned: hollow, a 1.5 px `hairline-strong` outline at the planned length.
  - Session: done and partial fill to their *seen* minutes in `on-task-ink` / `partial-ink`, followed by ● / ◐. Slacked is never filled: a 1.5 px `warn-ink`
    outline, then ✕.
  - Missed: the planned outline turns dashed, plus a ◌ in `absent-ink`.
  - Bars grow with `scaleX` on `spring-smooth` from +240 ms, staggered 40 ms.
- **Pace marker:** a 2 × 14 `ink` tick at **now + buffer_days**, with a 2 px connector to the now-line in the status ink (`ink-3` when on track).
  - `buffer_days = (V−P)/r` in half steps, with `r = T/7` for unscheduled habits.
  - For scheduled ones `r` is T over the number of days that have blocks, so a day of buffer is a day of the habit's own rate.
  - Left of now means behind.
- **Now-line:** 2 px `accent` with an 8 px head, at Thu 22:10 (drawn at 22:00: 10 minutes is under a pixel).
- **Milestones row:** an outlined ◇ "Submit, due Fri" in `partial-ink`, and the ◐ "At risk" pill with "Then the booth, 14 Oct" (off the chart, so it is stated, not drawn).
- **Legend:** Planned, Done, Partly ◐, Slacked ✕, Missed, "Where your minutes put you", Now.
- **Selection drives detail (§5):** the detail card swaps with blur 8 → 0 and a 4 px lift over `dur-medium` (260 ms). It holds:
  - the title, pill and target line ("150 min a week, 25 at a time · desk camera");
  - three `Alibi.Stat`s with sentence-case labels: "Seen" (of T), "Pace by now", and "Per day" or "Buffer" (Running: "Runs", "Pace by now", "To go");
  - a `PinchLine`;
  - a list of the week's sessions and blocks (VerdictPill / Missed / an outlined "Planned" pill). "Added at 22:06 from tonight's review" is a join:
    `/api/plan/overview` doesn't carry it, but the night digest row (`GET /api/digests?kind=night`) stores `accepted_key`, which equals the block's `key`, and
    `accepted_at`. Runs show minutes only ("28 min · Strava"): the overview's run sessions carry start and end, not distance.

  The board mounts two identical detail slots and alternates them so the entrance replays; in the product, re-key the element.

## 4. Egress block on /signals (F6)

The `/signals` column is 1088 px (it is denser than the dashboard). Data: `GET /api/signals/egress` (NEXT_UI D1c). The card holds:

- **Page header:** "Checked 22:04 · the Spark is checked at most once a minute" (`now`; the server caches each probe for 60 s). The intro under the title says the
  view is read from this Mac's settings plus a check that the Spark answers, and shows host names only.
- **Head:**
  - `label` "Where your data goes";
  - the **count sentence** in `h2` size, `role=status`, which rewrites with a blur-in when the scope or the Spark changes;
  - `summary.text` as sent, in `small`: "Summaries go to your Spark over Tailscale." or "Summaries stay on this Mac." Nothing else: no client sentence names the
    rows that "leave", because the Strava row sends a token and reads runs back, and only its `why` says which way;
  - the scope chips `Alibi.Chip` All / This Mac / Tailnet / Internet (`aria-pressed`).
- **Count sentences** ("N of M": M is every row the server sent, N the active rows in scope):

  | Scope | Counts | Spark on | Spark off |
  |---|---|---|---|
  | All | active rows whose `where` isn't `mac` | "4 of 6 leave this Mac." | "1 of 6 leaves this Mac." |
  | This Mac | active `mac` rows | "2 of 6 stay on this Mac." | the same |
  | Tailnet | active `tailnet:spark` rows | "2 of 6 go to your Spark over Tailscale." | "Nothing goes to your Spark right now." |
  | Internet | active `nvidia_build`, `search_provider`, `strava` rows | "2 of 6 leave the tailnet." | "1 of 6 leaves the tailnet." |

  With nothing to count, All reads "Nothing leaves this Mac right now." and Internet "Nothing leaves the tailnet."
- **Dim, don't delete:** out-of-scope rows set text to `ink-3`, and icons and marks to opacity 0.4, crossfading over `dur-medium`. The row count never changes.
- **Groups:** one list in three stacked groups, in this order: This Mac (`mac`), Tailnet · your Spark (`tailnet:spark`), Internet (`nvidia_build`,
  `search_provider`, `strava`). Each group header shows "N of M on". Group by `where`, never by `what`: Camera frames moves to Tailnet or Internet with a remote
  vision model.
- **Each row** holds an icon; `what` in `body` and `why` in `small`, both as sent; `host` in a 208 px mono column when set; and a `StatusDot` with "On" (active,
  `mac`), "Sending" (active, elsewhere) or "Off" (inactive; `what` drops to `ink-2`). Rows don't expand until they carry `fields[]` and `last_ts` (NEXT_UI ask 6).
  Then the expansion (`surface-2`, `radius-sm`) shows field names as mono chips plus "Last sent HH:MM", never values, one row open at a time.
- **The rows `egress()` sends**, in this order:

  | what | where | Sent when | why (exact) |
  |---|---|---|---|
  | Camera frames | `mac` | witness is Apple Vision | "Frames never leave the Mac. Apple Vision checks them on this Mac." |
  | Camera frames | `tailnet:spark` | a vision model on the Spark | "Frames go to your Spark over Tailscale to be checked." |
  | Habit names and minutes | `tailnet:spark` | a text model on the Spark | "Habit names and minutes go to your Spark over Tailscale." |
  | Habit names and minutes | `mac` | no model set up | "No model is set up, so the rules on this Mac write every summary." |
  | Ask questions | `tailnet:spark` (the `NEMOCLAW_URL` host) | `NEMOCLAW_URL` is set | "Your questions go to NemoClaw on your Spark over Tailscale." |
  | Search questions | `search_provider` | `NEMOCLAW_URL` is set | "Search questions go to the search provider." |
  | Strava runs | `strava`, host `www.strava.com` | Strava is set up; `active` = connected | "Alibi sends your Strava token to strava.com and reads your runs back." |
  | Window titles, app names, coordinates, notification text | `mac` | always | "Never sent. They are read on this Mac and stay here." |

  When a server isn't answering, its row goes Off and its `why` grows: frames add " It isn't answering, so Apple Vision on this Mac checks them instead.", habit
  names add " It isn't answering, so the rules on this Mac write the summary instead.", and Ask reads "NemoClaw isn't answering, so Ask is off." Other setups get
  their own exact strings from `signals.egress()`: mock frames ("Frames never leave the Mac. Test mode: nothing is checked."), a model server on this Mac, NVIDIA
  Build.
- **No client privacy sentence:** the frames claim is the Camera frames row's `why`, so "Frames never leave the Mac" appears only when the server sends it (AGENTS
  rule 5).
- **Spark off:** the Habit names and minutes row stays in Tailnet, goes Off and dims with its longer `why`, and `summary.text` turns "Summaries stay on this Mac."
  With `NEMOCLAW_URL` set, Ask and Search questions go Off with it, so on the board the All count falls from 4 of 6 to 1 of 6.

**The board** shows exactly the six rows `egress()` sends for one setup: Apple Vision witness, the summary model and NemoClaw on the Spark, Strava connected. The
`why` strings are the server's in both Spark states. The hosts are this tailnet's, from `docs/NEMOCLAW.md` (the model by IP, the NemoClaw gateway by its
`ts.net` name). No field chips or "Last sent" stamps until `fields[]` and `last_ts` exist.

## 5. Ask drawer (F8, gated)

A 480 px right drawer (`surface-1`, hairline left edge, `shadow-float`) over a `scrim`. It enters with translateX 100% → 0 over `dur-drawer`, `ease-drawer`; the scrim fades over `dur-medium`. Esc and ✕ close it.

- **Header:** `h2` "Ask", and the `small` line "Numbers come from Alibi. Answers come from NemoClaw on your Spark."
- **Composer:** `surface-2`, `radius-lg`, `hairline-strong`, 56 px. It holds:
  - a 40 px mic button (`surface-3`; there is no mic in the icon set, so it is an inline 1.5 px stroke SVG);
  - a 17 px input;
  - a 40 px `accent` send button with the `arrow-up` icon in `on-accent`.

  Real `<form role=search>` and `<label>`.
- **Staged narration (`role=status`):** a 3-segment progress (current `ink`, done `ink-2`, to come `surface-3`), then the label in 16/600, which swaps with blur 4 → 0 over `dur-medium` and is driven by `stage` polled every 500 ms. There are **no timers** in the product. A meta line with real timings sits under it.
  - Labels: "Contacting the Spark" → "Waiting for NemoClaw" → "Checking links, 3 of 5" → "Done in 7.4 s".
  - Alibi's facts take about 40 ms, so they are never a stage: they are on screen from the first poll.
- **Facts (receipts):** `label` "From Alibi, not the model", then three rows with icons:
  - "Running: 2 of 3 runs this week, 1 to go by Sunday";
  - "Last run: today 07:30, 5.2 km in 28 min · Strava";
  - "Next free 30 min: tomorrow 07:00, before drawing".

  These are rendered by Alibi, never by the model.
- **Answer:** plain body text (16 px, weight 400, at most 62ch and 80 words), without restating the numbers. Caption in `small` `ink-3`: "From NemoClaw on your Spark ·
  6.2 s".
- **Links:** "Links" with a live count ("3 of 5 links checked", then "5 of 5 checked · 3 open").
  - **One `<a>` card per completed HEAD check** that returned 2xx or 3xx: `surface-2`, `radius-sm`, 56 px, title, site, ✓ "Opens".
  - Foot line: "Checking 2 more. Only links that open are shown." / "2 didn't open and were left out."
  - With HEAD checks off, the cards say "from NemoClaw, not checked" instead of "Opens".
- **Off:** the composer dims (opacity 0.5, disabled), and a `surface-2` card shows ◌ "NemoClaw isn't answering, so Ask is off." (the egress Ask row's `why`) with "Last answer 21:58. Reviews and briefs don't need it, so they still arrive. Nothing you type here is queued for later." and a secondary "Check again". Ask isn't shipped, so its times are example data. In the product the Ask button is hidden while `capabilities.ask` is false; this state covers the drawer already being open, or the shortcut.

## Open with the backend

The numbered asks live in NEXT_UI.md §11. These change a board:
1. **Egress expander** (ask 6): `fields[]` and `last_ts` per row. Until then rows don't expand and carry no stamps.
2. **The proposal question** (ask 4): `proposal.prompt`. Until then the card and the island read the last line of `text`.
3. **Memory timing** (ask 11): should checkpoints carry `memory`, so a morning block's outcome shows the same day?
4. **Why rules** (ask 12, optional): a field that says why no model answered, for the rules foot line.
5. **Ask** (asks 7 and 8): the stage enum, `links_done` and `links_total`, `capabilities.ask`, and an egress row for the link checks.
6. **The reason's cause noun** (ask 2): without it, health-strip reasons stay in plain ink.
7. **Telegram:** no route exists in the code. If `NOTIFY` ever sends digests to Telegram, `egress()` needs a row for it before a board shows one.
8. **Pace for scheduled habits** (ask 13): with the Gantt's own blocks as schedules, `pace3` calls Building, Math and C++ off track at Thu 22:00 (Building: "1 min
   behind. Only 45 min planned."). The boards' "4 of 6 on track" only holds with straight-line pace.
9. **Egress `where` for other hosts** (ask 14): `_where()` files every non-NVIDIA host under `tailnet:spark`, so a cloud model run by anyone else would read
   "your Spark over Tailscale".

## Settled

- **Milestone tick:** none in T1. `done_at` is set by hand in `goals.json`, so the strip row says "Due tomorrow." and offers nothing to press.
- **Ask stages:** only real steps (contacting, waiting, links, done). Facts are on screen from the first poll, never a stage.
- **Strava egress:** `where: "strava"` shipped (f635c79); an active Strava row counts as leaving the tailnet.
- **Trace timing:** `turns`, `total_ms` and a `result` per step shipped (f635c79).
- **Kept:** the server decides: a session from 60 min before the block to 30 min after its end counts, and 80% of the minutes is kept. The pill says Done.
- **Pace marker:** drawn at now + `buffer_days`. `pace_min` and `verified_min` are in `/api/plan/overview` if the client prefers minutes.
- **Milestone word:** the pill says At risk (◐), like a habit; "Due soon" is gone.
- **Button length:** "Move drawing to 07:30" is 4 words, against Voice rule 8 (3 at most). It stays because it names the action exactly; "Move to 07:30" is the fallback.
- **280 ms:** §5's scope dimming uses the `dur-medium` token (260 ms), because no 280 token exists.

## Maintenance notes

- `Next-Digest-Light.dc.html` is the Today board's `<article>` and logic with `theme` fixed to light. Re-derive it if the digest markup changes.
- `Next-Gantt.dc.html` repeats its detail panel in two `<sc-if>` slots (A/B) so the blur entrance replays on every selection. Edit both slots together.
- Before a board shows a string the server sends, copy it from the code (`alibi/digest.py`, `alibi/report.py` `_reason()`, `signals.egress()`), not from this file.
