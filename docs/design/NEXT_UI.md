# Next UI: design-session build plan (D1 + stretch)

Start after tonight's recording; nothing here ships before it.

**Sources.**
- [`NEXT_BOARDS.md`](NEXT_BOARDS.md): what each board shows, piece by piece (`docs/design/canvas/project/Next-*.dc.html`).
- The user's prototype, [Alibi Next Phase](https://claude.ai/artifact/NNipi7DhjVYKVTLzeAM3sn): "A day with Alibi" in 8 beats, from the 07:30 brief to the next
  morning's memory, each on the Mac, iPhone and notch island with a Spark online switch; then the week Gantt and where the data goes.
- The server contract (the backend owns it): `alibi/routes_digest.py` and `alibi/digest.py` (9516af5, f635c79), `signals.egress()` in `alibi/signals.py` (384516e,
  f635c79; table in `docs/SIGNALS.md`), `alibi/routes_plan.py`, `alibi/routes_calendar.py`.
- `docs/NEXT_PHASE.md` (§2 IA, §3 F2/F4b/F5/F6/F8/F1/F9, §4 formulas, §5 choreography, §8 owners), `docs/design/LANES.md` (lane ownership and rules, which still
  apply), the system docs (`docs/design/system/project/{README,Motion,Voice,Surfaces,Mascot}.md`).

**Precedence.** The server contract wins on words and data: every sentence it sends (`text`, `reply`, `why`, `result`, memory lines) is shown as sent, and every
number comes from a field. This plan wins on behaviour. The boards win on pixels, button labels included. The prototype is the narrative reference; where it
disagrees with the contract, the contract wins (its 07:30 brief already knows "22 of 25"; the server can't know that until the block has ended, §0).

## 0. Rules for every piece

**Stage fixtures.** Today `?stage=NAME` swaps only `/api/state` (`core.js` `pollState`, `STAGE`). `/api/report`, `/api/sessions` and `/api/calendar/plan` stay live, so
new endpoints can't be rendered without a server holding the right data. N0 (§1) makes `api()` stage-aware, and every piece then renders from `?stage=` alone:
- `alibi/web/fixtures/NAME.json` is the state, as today. New: `alibi/web/fixtures/NAME/index.json` lists the API files that stage overrides.
- File name = path without `/api/`, without the query, with `/` → `.`, plus `.json`. Example: `/api/digests?limit=10` → `digests.json`. Writes add the method:
  `POST /api/digests/2026-10-01-night/accept` → `digests.2026-10-01-night.accept.post.json`. In stage mode, writes never reach the server.
- A fixture of the form `{"$frames": [a, b, c]}` returns the next frame on each call and then holds the last one. Only Ask polling uses this.
- Paths not listed in `index.json` fall through to the live API, so a stage overrides only what it needs and existing stages behave as before.
- Clock: use `stageNow()` (N0; it generalises `week.js` `wkNow`). Never cache "now".

| Stage | Clock (BST) | `now` | Overrides |
|---|---|---|---|
| `plan-mixed` | Thu 1 Oct 20:00 | 1790881200 | `report.json` (all five `status3` values), `plan.overview.json` |
| `digest-night` | Thu 1 Oct 22:00 | 1790888400 | `digests.json`: a night row shaped like `tests/fixtures/digest_night.json`, slot `2026-10-01-night`, `accepted_at: null`, no `accepted_key`; `via:"llm:spark"`, 4 steps, `turns: 3`, proposal Drawing Fri 07:30 25 min. Plus `digests.2026-10-01-night.accept.post.json` and `….undo.post.json` |
| `digest-night-rules` | Thu 1 Oct 22:00 | 1790888400 | the same with `via:"rules"`, `turns: 0` and one `rules picker` step (Drawing Fri 07:00) |
| `digest-accepted` | Thu 1 Oct 22:06 | 1790888760 | `accepted_at` 22:06 (1790888760), as on the boards |
| `digest-morning` | Fri 2 Oct 07:30 | 1790922600 | the morning row, `json.memory.state:"now"`: "Last night you moved drawing to 07:30. It's on now." |
| `digest-kept` | Fri 2 Oct 12:00 | 1790938800 | newest first: the 12:00 checkpoint with `sent:false` (must not show), then a morning run by hand at 08:00 (`2026-10-02-morning-2`) with memory `kept`: "Last night you moved drawing to 07:30. You showed up for 22 of 25 minutes." A real checkpoint is only quiet when nothing changed and no block starts within 4 h, so in a dump this week's Fri 16:00 Math block would make the 12:00 one speak; leave it out of this stage's plan |
| `egress-up` / `egress-down` | Thu 1 Oct 20:00 | 1790881200 | `signals.egress.json`, the board's six rows: Habit names and minutes, Ask questions and Search questions `active` true / false, `summary.where` `tailnet:spark` / `mac`, Strava connected in both |
| `ask-stages` / `ask-done` / `ask-offline` | Thu 1 Oct 20:00 | 1790881200 | state with `capabilities.ask:true`, `ask.post.json` `{id:"a1"}`, `ask.a1.json` as `$frames` |

Persona everywhere: Harrish; Drawing 25 min, Building 45, Math 50, C++ 30, Internships 45; Running via Strava; Sleep via Health. Use the backend's golden dumps (§11 ask
1), not hand-typed JSON, once they exist.

**Motion.** Use the §5 numbers mapped to tokens. Animate `transform` and `opacity` only, plus colour on `ease`. Play entrances on first paint only: reuse
`wkPaint()`/`wkEnter()` from `week.js` (signature dedupe plus the in-view entrance). On a 15 s refresh, only changed values retarget. Exits run at 0.65× (260 → 170 ms).

| NEXT_PHASE §5 | Token |
|---|---|
| entrance 260 ms, 6 px, 40 ms stagger cap 6 | `--dur-medium` `--ease-out` |
| count-up 900 ms from +420 | `--dur-reveal` `--ease-out`, delay 420 ms |
| label blur 4→0, 220 ms | `--dur-medium` (nearest token) |
| dim 280 ms | `--dur-medium`, `ease` (colour) |
| press 0.97 | `--dur-micro`, release `--spring-micro` |
| content swap / docked action | `--spring-snappy` + `--spring-snappy-dur`; close `--spring-smooth` |
| drawer | `--dur-drawer` `--ease-drawer`, exit 270 ms |

- **Reduced motion.** tokens.css already drops the springs to 150 ms `ease`. In JS, check `wkReduced()`: count-ups jump to the final value, staggers go to 0 and blur is
  dropped. Pinch stays still (`{still:true}`), holding its end pose.
- **Status.** Always dot + shape + word: on track `#76B900` ●, at risk `#F2A900` ◐, off track `#E5484D` ✕/■, can't see grey ◌. Never use a red fill. Only the cause noun
  takes `warn-ink`. Use `wkDot`/`Alibi.StatusDot` marks; don't draw new glyphs.
- **Accessibility floors.** Web targets ≥ 28 px with `space-2` between them; default button 36 px. 2 px `focus-ring` on `:focus-visible`. Contrast 4.5:1 for text, 3:1
  for marks, in both themes. Polite announcements go through `role="status"`. Never animate the accessible name.
- **Lanes.** Commit by pathspec, never touch another lane's files, no AI trailers. Never run `./alibi.sh up|down|demo` or `build_native.sh`.

**DoD template.** Run from the repo root, with `S` set to your scratchpad:
```bash
LAB=$S/lab; PORT=8785   # a fresh seeded week; never copy data/demo (it collects test sessions)
[ -d $LAB ] || { mkdir -p $LAB && ALIBI_DATA_DIR=$LAB VISION_BACKEND=mock NVIDIA_API_KEY= LLM_MODEL= NOTIFY=print .venv/bin/python scripts/seed_demo.py >/dev/null; }
ALIBI_DATA_DIR=$LAB API_PORT=$PORT VISION_BACKEND=mock .venv/bin/python -c "from alibi import api; import time; api.serve_in_thread(); time.sleep(1e9)" > $S/lab.log 2>&1 & echo $! > $S/lab.pid
U="http://127.0.0.1:$PORT/?stage=STAGE"; mkdir -p $S/out
for t in dark light; do python3 docs/design/tools/render.py "$U" $S/out/STAGE-$t.png --w 1440 --h 1800 --wait 2500 --$t --full; done
python3 docs/design/tools/render.py "$U" $S/out/STAGE-rm.png --w 1440 --h 1800 --wait 600 --dark --reduced-motion --full
python3 docs/design/tools/render.py "$U" $S/out/STAGE-390.png --w 390 --h 1600 --wait 2500 --dark --full
python3 docs/design/tools/lint_design.py --paths <your files>   # must end: lint_design OK
./alibi.sh test                                                  # hermetic suite green
kill $(cat $S/lab.pid)
```
Read every PNG before you call a piece done. render.py prints console errors to stderr, and there must be none.

## 1. N0: wiring (prerequisite, lane W1, 20 min)

Files: `alibi/web/index.html`, `alibi/web/js/core.js`, `alibi/web/fixtures/**`. Land N0 alone, before any D1 lane starts, so that no other lane touches `index.html`.
- `core.js`: add `STAGE_FILES` (load `fixtures/STAGE/index.json` once, before the first `pollState`), `stageUrl(path, method)`, `stageNow()`, and teach `api()` and
  `postJSON()` the §0 rules. In `handleAlert`, after the `refreshSlow()` line, route digests to the card: `if ((kind === "digest" || (kind === "report" && a.slot))
  && window.AlibiDigest) { AlibiDigest.refresh(); return; }`. The 22:00 night digest arrives as `kind: "report"`; today it toasts with its Accept button, and the
  guard keeps that toast until D1b lands. `renderToastActs` honours an action's `variant` (the board's Undo is secondary). Ask reads `lastState.capabilities`
  (stored by `pollState` once the backend sends it).
- `index.html`: add `<link>` tags for `health.css`, `digest.css`, `gantt.css`, `ask.css`, and `<script>` tags for `health.js`, `digest.js`, `gantt.js`, `ask.js` after
  `sessions.js`. Add the empty hosts: `<div class="hs" id="healthStrip"></div>` between `.todayhead` and `#nextUp`; `<section class="block" id="briefBlock"
  aria-labelledby="briefH" hidden></section>` between `#nowBlock` and `#todayBlock`; `<div id="gantt"></div>` after `#wgrid`; `<span id="askSlot"></span>` first in
  `.hdr-r`. Each module must no-op while its host is empty or its data is missing.
- Fixtures: copy the §0 stage files from `docs/design/fixtures/api/` (backend dumps, §11 ask 1) into `alibi/web/fixtures/`. Until those exist, build the digest stages
  from `tests/fixtures/digest_night.json` (gitignored; `test_digest` rewrites it on every run) and the egress stages from the `docs/SIGNALS.md` table.
- DoD: `?stage=idle` renders pixel-identical to before (`python3 docs/design/tools/imgdiff.py before.png after.png`). `?stage=plan-mixed` loads `report.json` from the
  fixture: check in the Network log or with `--eval "lastReport.now"`. Then `./alibi.sh test` and lint_design OK.

## 2. D1a: health strip (lane W2, 60 min, never cut)

- **Files:** new `alibi/web/js/health.js`, `alibi/web/css/health.css`. Board: the health strip card in `Next-Today.dc.html` (NEXT_BOARDS §1).
- **Insert:** render into `#healthStrip` (top of Today) from a `document.addEventListener("alibi:report", …)` listener. `renderReport()` in `week.js` already dispatches
  this event, so `week.js` needs no edit. Sleep stays in `#hlines` (`renderHealthLines`), because health habits are excluded from formulas 1–6.
- **Data:** `/api/report` `rows[]` plus `report.running` (Running, with the same pace fields): `habit`, `label`, `status3` (on_track | at_risk | off_track | stale |
  done), `buffer_days`, `need_per_day_min`, `need_today_min`, `capacity_left_min`, `stale`, `unit`, and `reason` (one server sentence). Milestones come from
  `/api/plan/overview` `milestones[]`. Count the rollup from `status3`: `report.headline` is still the old D2 sentence. Keep reading `status` for compatibility. Sort:
  off_track, at_risk, stale, on_track, done (the board keeps config order; this plan wins on behaviour).
- **Layout** (as the board, NEXT_BOARDS §1): the rollup `h3`, the worst-two line under it and the week-left meta on the right. Then one row per habit (min-height
  48, hairline between, flex-wrap): icon and name, the status pill in a 104 px slot, `reason` as the main line (`ink`, or `ink-2` when on track), a 120 × 4
  neutral meter (`ink-2` fill to V/T, a 2 × 16 `ink` tick at P/T) and the value ("44 of 150", "2 of 3 runs"). No coloured fills: the pill carries the status. The
  milestone row is last: its label, the line from `due` ("Due tomorrow."), its status pill and the due date. A two-item legend closes the card.
- **Copy:** rollup "4 of 6 habits on track", then the worst two: "Internships is off track: 78 min behind. Drawing is at risk: 40 min behind." (gap = `pace_min` −
  `verified_min`). The main line is `reason` as sent ("40 min behind. 34 a day until Sunday.", "78 min behind. Only 45 min planned.", "1.5 days of buffer.",
  "On pace.", "Done for the week.", "Can't see Strava. Nothing new in a day."; every form is in NEXT_BOARDS §1). Only the cause noun takes `warn-ink`, and `reason`
  doesn't mark one yet (§11 ask 2), so for now none does.
- **Motion:** first paint: rows enter with a 40 ms stagger (cap 6). The value and the meter fill share one clock: `--dur-reveal` `--ease-out` from +420 ms. Write a
  local rAF count-up that drives both, because `AlibiMoments.countUp` only rewrites text. On refresh, a changed meter retargets on `--spring-smooth`; a status
  change recolours the mark on `--spring-micro` and crossfades the word over 150 ms. Nothing replays on a poll.
- **Reduced motion · Pinch:** the final number and fill at once, with a 150 ms fade. Pinch: none. The hero already holds the view's Pinch (one Pinch per view).
- **A11y:** `<ul aria-label="Pace by habit">` of `<li>`. The visible word carries status. Each row gets an `aria-label` with the final sentence ("Drawing: at risk.
  40 min behind. 34 a day until Sunday."), never the counting digits. One hidden `role="status"` announces only `status3` transitions between reports ("Drawing is
  now at risk."). Rows are not interactive in T1.
- **DoD:** the §0 template with `STAGE=plan-mixed`. `--eval "document.querySelectorAll('#healthStrip li').length"` equals `rows.length` + 1 (Running) +
  `milestones.length` of the fixture (Sleep not counted). The rm render shows final values. At 390 px the rows wrap inside the card with no horizontal scroll.

## 3. D1b: digest card, confirm, trace, accept toast (lane M, 90 min, never cut)

- **Files:** new `alibi/web/js/digest.js` (`window.AlibiDigest = {refresh}`), `alibi/web/css/digest.css`; `alibi/pinch.py` (mood, below). Boards: `Next-Today.dc.html`
  (`state`: night, accepted, morning, rules) and `Next-Digest-Light.dc.html`. Their server strings are the code's; NEXT_BOARDS §2 lists what is example data.
- **Insert:** `#briefBlock` (between Now and Today). Load on boot, on `AlibiDigest.refresh()` (N0 routes digest and night-report alerts here) and on every
  `alibi:report`.
- **Which row:** `GET /api/digests?limit=10` (newest first); show the first row with `sent: true` while it is under 18 h old. Checkpoints with nothing new are stored
  with `sent: false` and never show. Don't call `/api/digests/latest` without `kind`: it returns those quiet rows too. "Hide" goes to sessionStorage by `slot`.
- **Row:** `{slot, kind: morning|checkpoint|night, ts, sent, via, text, json}`. Night rows add `proposal {habit, label, day, at, minutes, why, via}` (or null),
  `trace [{tool, args, ms, result, error?}]`, `turns`, `total_ms` and `accepted_at` (null until accepted). Morning `json` has `memory {state, text, seen_min, minutes,
  …}`, `blocks`, `first_gap`, `need_today`, `sleep_h`. Night `json` has `done`/`partial`/`slacked` (`{label, at, seen_min, declared_min}`), `missed` (blocks),
  `buffers`, `alibi_score`, `fix_tomorrow`, `tomorrow`. Checkpoint `json` has `changes`, `next_block`, `action`. Every `json` has `pinch`.
- **Words, as sent:** the Pinch line is `json.pinch` ("Closing the file on today."). The question is the last line of `text` on a night row with a proposal ("Move
  drawing to tomorrow 07:30, 25 min?") until `proposal.prompt` lands (§11 ask 4). The confirm meta is the date and times from `proposal`, then `proposal.why`. The
  morning callback is `json.memory.text`; the client never writes a memory sentence (the endings are listed in NEXT_BOARDS §2). Fact rows are data from the `json`
  lists, laid out as on the board. A checkpoint shows its `text` lines as they are, plus `json.action` as a secondary button: its `label` ("Start 25 min"), which
  sends `action.say` through the usual say path.
- **Morning rows:** the callback block comes first: `json.memory.text`, then "07:30 to 07:55 · added from last night's review" until the block ends and "Seen 22 of
  25 min" after. While `memory.state` is upcoming or now, it holds the view's one primary, "Start 25 min": `POST /api/calendar/plan/start {key}`, with the key of
  the `json.blocks` entry that has the memory's habit and `at`; once the block has ended, a pill from `memory.state` takes its place (NEXT_BOARDS §2). Then
  `json.first_gap`, the rest of `json.blocks` and `json.sleep_h`, and a secondary "See today's plan".
- **`via` tag:** `rules` → "via rules", `llm:spark` → "via Spark", `llm:build` → "via NVIDIA Build". Morning and checkpoint rows are always `rules`. No digest says
  NemoClaw: there is no such `via`.
- **Structure (sechead + one card):** title "Night review" / "Morning brief" / "Checkpoint, 16:00", with the time and the `via` tag in `secmeta`. Then the fact rows, a
  `PinchLine` (20 px still avatar), and, on a night row with a proposal and no `accepted_at`, the confirm card on `surface-2`: label "Proposed for tomorrow", the
  question, the meta line, primary "Move drawing to 07:30" (black on `#76B900`), quiet "Not now". Under it, the trace disclosure.
- **Trace:** the summary maps tools to labels in the client: `week_status` → "Checked week", `plan` → "plan tomorrow", `free_gaps` → "free gaps", `history` →
  "history", `propose` → "proposed HH:MM", `rules picker` → "rules picked HH:MM" (a rules row with no model steps reads "Rules picked 07:00"), `timeout` → "out of
  time". Meta on the right: "4 model turns · 3.1 s" from `turns` and `total_ms` ("No model turns · 40 ms" on a rules row). Open, one row per
  step: index, the call (`tool` + `args` in mono), `result` as sent (≤ 60 chars: "drawing −2 d behind most", "3 blocks tomorrow", "valid"), and `ms`. Step `ms` are
  in-process reads (0–2 ms), so the time shown is `total_ms`, never a sum. The foot line counts `turns`, never steps (the fixture has 3 turns and 4 steps: two calls
  can share a turn): "4 model turns on your Spark, 3.1 s in all. Alibi checked the slot itself. Nothing changes until you tap." ("on NVIDIA Build" for `llm:build`.)
  Show every step at once, never on a timer. Open by default on an unaccepted night row, closed after accept.
- **Rules rows:** `via: "rules"` with `turns: 0` means no model answered (none set up, or no reply): one step, `rules picker`, result "drawing tomorrow 07:00, 25 min".
  `via: "rules"` with `turns > 0` means the model answered but no valid plan came back (prose instead of tools, an invalid proposal, or out of time): keep any
  steps it made (an invalid one reads "invalid: …", a `timeout` step "time budget spent"), then the `rules picker` step. Foot line: "The rules on this Mac picked
  the slot. Same card, same accept. Nothing changes until you tap." The row doesn't say why no model answered (§11 ask 12).
- **Accept:** `POST /api/digests/{slot}/accept` → `{ok, reply, block}`. `digest.js` posts with its own `fetch` and reads the JSON on every status, because `postJSON`
  drops `reply` on an error status.
  - `ok: true`: the accepted state and the toast, both showing `reply` ("Done. Drawing tomorrow 07:30, 25 min. It's on the plan."). In the card, "Added at 22:06."
    (`accepted_at`) sits under it, with Undo; the trace closes to its one-line disclosure.
  - `ok: true, already: true`: accepting twice does nothing. Same accepted state, `reply` "Already on the plan: drawing tomorrow 07:30, 25 min.", no second toast.
  - `ok: false` (HTTP 200): `reply` ("That slot has passed.") replaces the confirm card, with no button.
  - Any error status (404: unknown slot, or no proposal) or no answer: the chrome error below, and the button re-enables.
- **Undo** (on the accepted row and in the toast): `POST /api/digests/{slot}/undo` → `{ok: true, reply: "Removed drawing from tomorrow 07:30."}`, and the confirm card
  comes back; accept works again. 409 `{ok: false, reply: "That proposal isn't on the plan."}`: show `reply`, then the confirm card. 404: the chrome error.
- **After a reload** (`accepted_at` set, no `reply` in hand): the proposal as data ("Drawing, Fri 2 Oct, 07:30 to 07:55."), "Added at 22:06." from `accepted_at`,
  and Undo.
- **Not now** is client-only, as on the island: "Not added. Tomorrow stays as planned." with "Show it again", hidden per `slot` in sessionStorage. Accept stays
  possible until the slot passes.

| t (ms) | Element | Change | Curve |
|---|---|---|---|
| 0 | card | translateY 6 → 0, opacity | `--dur-medium` `--ease-out` |
| 0–120 | fact rows | the same, 40 ms stagger | `--dur-medium` `--ease-out` |
| 1000 | PinchLine | opacity, translateY 4 → 0 | `--dur-medium` `--ease-out` |
| 1260 | confirm card + button (docked, enters last) | opacity, blur 8 → 0, scale 0.97 → 1 | `--spring-snappy` |
| tap | button | scale 0.97; label "Moving…", `aria-busy`, disabled until the reply (no spinner, no timer) | `--dur-micro` |
| `ok` | confirm area | old out (opacity, blur 4, 120 ms), then `reply` with ✓ in `accent-ink` | `--dur-medium` |
| `ok` | toast (existing `#toast`, top right) | `showToast("note", reply, null, [{label: "Undo", variant: "secondary", undo}], 6000)`; `undo` posts the Undo route | shell toast |
| `ok` | Pinch | `AlibiPinchWire.play("connected")` (priority 2; quiet lobster respected) | clip |

- **Disclosure and replay:** the trace disclosure toggles `hidden` (no height animation). Rows fade in with a 40 ms stagger; close is a 170 ms fade. The sequence plays
  once per new `slot`, and a refresh of the same slot never replays it.
- **Reduced motion · Pinch:** everything fades in together over 150 ms, the button is visible at once, and Pinch holds the `connected` end pose. Pinch: `pinch.py`
  already answers `reading` for 10 min after a `report` alert (the 22:00 night). Add the same for `digest` alerts with `digest_kind` morning, or night (a run by
  hand). No clip on arrival. `connected` plays on accept only.
- **Errors (chrome):** "That didn't save. Check Alibi is running, then try again." The button re-enables.
- **A11y:** the section is `aria-labelledby="briefH"`. The confirm card is `role="group"` with `aria-label` = the question. Focus order: facts (not focusable) → primary
  → Not now → disclosure (`aria-expanded`, `aria-controls`) → Hide. After accept, focus moves to the accepted line (`tabindex="-1"`). The toast announces through its
  existing `role="status"`.
- **DoD:** the §0 template for `digest-night`, `digest-night-rules`, `digest-accepted`, `digest-morning` and `digest-kept` (the 08:00 morning row shows, not the quiet
  12:00 checkpoint). Mid frame: `--wait 1100` shows the facts and the Pinch line without the button. Accept: `--eval
  "document.querySelector('#briefBlock .al-btn--primary').click()"` with `--wait 2500` shows the accepted row and the toast with the fixture's `reply`; clicking Undo
  brings the confirm card back. Once live on the lab server: `curl -s -X POST http://127.0.0.1:8785/api/digests/run -H 'Content-Type: application/json' -d
  '{"kind":"night"}'`, render with no `?stage`, accept, undo. `.venv/bin/python -m alibi.pinch --selftest` passes with a new digest → `reading` case.

## 4. D1c: egress block on /signals (lane W3, 45 min; chips are cuttable, the table is not)

- **Files:** `alibi/web/signals.html` (3 additions: `<link href="/web/css/egress.css">`, `<script src="/web/js/egress.js">`, and `<section id="egress">` + `<hr
  class="rule">` before `<section id="sources">`); new `alibi/web/js/egress.js`, `alibi/web/css/egress.css`. Board `Next-Signals-Egress.dc.html` (NEXT_BOARDS §4).
  `signals.html` has no `?stage` and no `wkPaint`, so `egress.js` carries a 10-line stage reader (same rules as §0) and its own signature dedupe.
- **Data:** `GET /api/signals/egress` → `{now, rows: [{what, where, active, host, why}], summary: {where, active, text, leaves_tailnet}}`. `where` ∈ `mac` |
  `tailnet:spark` | `nvidia_build` | `search_provider` | `strava`; `host` is a bare host name or null. Poll every 30 s, paused while `document.hidden`. The server
  caches each probe for 60 s, so a Spark that goes away shows within about 90 s. Key rows by `what` and patch them in place.
- **Rows:** render exactly what the server sends, in its order: Camera frames; Habit names and minutes; Ask questions and Search questions (only with `NEMOCLAW_URL`);
  Strava runs (only once Strava is set up; host `www.strava.com`); "Window titles, app names, coordinates, notification text" (always `mac`). Add nothing: the page's
  sources section already lists every Mac and iPhone source.
- **Groups by `where`, never by `what`:** This Mac = `mac`; Tailnet = `tailnet:spark`; Internet = `nvidia_build`, `search_provider`, `strava`. A row can move: Camera
  frames is `mac` with Apple Vision, mock or a loopback model, otherwise `tailnet:spark` or `nvidia_build`; Ask questions follows the `NEMOCLAW_URL` host. Each group
  header shows "N of M on" from `active`.
- **Each row:** `what`, then `why` as sent (the strings are in NEXT_BOARDS §4), `host` as meta when set, and a StatusDot + word: "On" (active, `mac`), "Sending"
  (active, elsewhere), "Off" (inactive; the row dims). No expander until rows carry `fields[]` and `last_ts` (§11 ask 6); then it shows field names and "Last sent
  HH:MM", never values.
- **Head:** the page header carries "Checked 22:04 · the Spark is checked at most once a minute" from `now`. The card's label is "Where your data goes". The count
  sentence is client arithmetic on `where` and `active`, "N of M" over every row sent: "4 of 6 leave this Mac." / "Nothing leaves this Mac right now." (the scope
  variants are in NEXT_BOARDS §4). Under it, `summary.text` as sent ("Summaries go to your Spark over Tailscale." / "Summaries stay on this Mac.") and nothing
  else. The chips group (`Alibi.Chip`, single-select, pressing the active chip clears it): All, This Mac, Tailnet, Internet.
- **Copy (AGENTS rule 5, exact):** the client writes no privacy sentence of its own. The frames claim is the Camera frames row's `why`, so "Frames never leave the Mac"
  appears only when the server sends it (`where: "mac"`).
- **Spark down (the kill-the-Spark beat):** the Habit names and minutes row stays in Tailnet with `active: false` and the server's longer `why` ("… It isn't answering,
  so the rules on this Mac write the summary instead."). `summary.where` turns `mac` and `summary.text` reads "Summaries stay on this Mac." With `NEMOCLAW_URL`
  set, Ask and Search questions go Off with it, so the board's count falls from "4 of 6 leave this Mac." to "1 of 6 leaves this Mac."
- **Motion:** pressing a scope dims out-of-scope rows (text → `ink-3`, icons and marks to opacity 0.4, `--dur-medium`) without removing them. The count sentence
  swaps: old out 120 ms, new in with blur 4 → 0 over `--dur-medium`. When a row goes Off between polls, its word crossfades the same way and the dot recolours on
  `--spring-micro`. That is the kill-the-Spark beat, so it must be legible at 1× speed.
- **Reduced motion · Pinch:** dim and swap become 150 ms fades. Pinch: none (the Signals page has no Pinch).
- **A11y:** the chips are `role="group" aria-label="Show where data goes"` with `aria-pressed`. Dimmed rows stay in reading and tab order. A hidden `role="status"`
  announces only a change of `summary.text`, read as sent ("Summaries stay on this Mac.").
- **DoD:** the §0 template against `/signals?stage=egress-up` and `?stage=egress-down`. The two renders differ only in the three Spark rows (Habit names, Ask
  questions, Search questions), the `summary.text` line and the count sentences; the Strava row sits under Internet in both. `--eval` clicks the "Tailnet" chip,
  and the render shows the Tailnet rows lit and the others dimmed. No frames sentence appears unless the Camera frames row is `mac`.

## 5. D1d: week Gantt (lane W2 after D1a, or a second W2 agent; 75 min)

- **Files:** new `alibi/web/js/gantt.js`, `alibi/web/css/gantt.css`. Board `Next-Gantt.dc.html`.
- **Insert:** `#gantt` (after `#wgrid` in This week), rendered on `alibi:report` once `week_start` is known. `#paceMore` stays as it is.
- **Data:** `GET /api/plan/overview?week=2026-09-28` → `{week_start, now, rows[{habit, label, unit, target_min, verified_min, pace_min, status3, buffer_days,
  need_per_day_min, reason, blocks[{start, end, state, key}], sessions[{id, start, end, verdict, ratio}]}], milestones[{key, label, due, done_at, status}]}`
  (shipped, `alibi/routes_plan.py`; Health habits are left out). Stage `plan-mixed`.
- **Layout** (as the board, NEXT_BOARDS §3): a `152px | 7 × 64px | 184px` grid. In each day cell, bars start 6 px in and scale 0.8 px per minute, 12 px tall.
  Planned blocks are hollow (1.5 px `hairline-strong`, min width 6 px). Sessions fill to their seen minutes: done `on-task-ink` with ●, partial `partial-ink`
  with ◐; slacked is a `warn-ink` outline with ✕, never filled red. A missed block keeps a dashed outline and a ◌. The status column holds the pill and "40 min
  behind · 34/day". The pace marker is a 2 × 14 `ink` tick at now + `buffer_days`, joined to the now-line (2 px `accent`, across all rows). Milestone rows go at
  the bottom: a diamond on its due day, and the pill for its `status` (◐ At risk within a day of `due`, ■ Off track once past due and not done, Done when
  `done_at` is set; pending shows only its due date). Running counts runs; Sleep is excluded.
- **Motion:** first paint: rows enter with a 40 ms stagger (cap 6) over `--dur-medium`. Bars scaleX 0 → 1 (`transform-origin:left`) on `--spring-smooth` from +240 ms,
  40 ms per row. The now-line fades in at +240. Each minute, the now-line moves by `transform` on `--dur-medium` `--ease-in-out`. On refresh, only changed bars
  retarget.
- **Reduced motion · Pinch:** bars and line appear in place with a 150 ms fade. Pinch: none.
- **A11y:** `role="table"` with day `columnheader`s that carry full names (as `renderGrid` does). Each row has a visually hidden summary: "Drawing: 2 of 4 blocks done,
  1 missed. At risk, 40 min behind." Bars are `aria-hidden`. A bar with a session is wrapped in `<a href="#session-ID">` with a ≥ 28 px hit area (an invisible padded
  `::before`). Tooltips appear only under hover-capable pointers.
- **DoD:** the §0 template with `STAGE=plan-mixed`. `--eval "document.querySelectorAll('#gantt [role=row]').length"` → 1 header + habits + milestones. At 390 px, the
  day columns scroll horizontally inside the card only, with the label column sticky; the page itself never scrolls sideways.

## 6. D1e: Ask drawer (lane W1, 60 min, gated: ships hidden unless one real call passes)

- **Files:** new `alibi/web/js/ask.js`, `alibi/web/css/ask.css`; `core.js` (Esc and `closeLayer` learn `askDrawer`). Board `Next-Ask.dc.html`.
- **Gate:** render the header button into `#askSlot` only when `lastState.capabilities.ask === true`. When the flag is off, the button isn't rendered at all; never show
  it disabled. It shows in stage mode only through a fixture that sets the flag.
- **Insert:** `ask.js` injects `<aside class="drawer askdrawer" id="askDrawer" role="dialog" aria-modal="true" aria-labelledby="askTitle">`, reusing the `.drawer`
  recipe and `openLayer`/`closeLayer`. The header button is secondary sm, "Ask".
- **Data:** `POST /api/ask {text, source:"web"}` → 202 `{id}`. Poll `GET /api/ask/{id}` every 500 ms until `state` is `done` or `error`, for at most 35 s → `{state,
  stage, facts, answer, links[{title,url,site}], links_checked, links_done, links_total, via, ms}`.
- **Order on screen:** the question; the stage label; the facts under "From Alibi, not the model" (rendered by Alibi as soon as `facts` exists, never a stage):
  "Running: 2 of 3 runs this week, 1 to go by Sunday", "Last run: today 07:30, 5.2 km in 28 min · Strava", "Next free 30 min: tomorrow 07:00, before drawing";
  the answer (≤ 80 words, plain 16 px body); the caption "From NemoClaw on your Spark · 6.2 s"; link cards.
- **Stages (server-driven only):** `contacting_spark` → "Contacting the Spark", `waiting` → "Waiting for NemoClaw", `checking_links` → "Checking links, 3 of 5",
  `done` → "Done in 7.4 s" (from `ms`). The label changes only when a polled value changes. No timers, no fake percentages.
- **Copy:** links head "3 of 5 links checked". Unchecked: "From NemoClaw, not checked". An answer with no links (its web search failed) leaves the Links section
  out. Off (the gateway doesn't answer): "NemoClaw isn't answering, so Ask is off.", the egress Ask row's `why`, with "Reviews and briefs don't need it, so they
  still arrive." Placeholder "Ask about a habit". Button "Ask".
- **Motion:** drawer per the §0 token table. Stage label swap: opacity + blur 4 → 0 on `--dur-medium`. Each link card enters (translateY 6, opacity) when its check
  lands: one card per real check, 40 ms stagger only when several arrive in one poll.
- **Reduced motion · Pinch:** label and cards fade over 150 ms. Pinch: `AlibiPinchWire.client("thinking")` once a request has been in flight for 600 ms (Mascot rule);
  `client(null)` on done or error.
- **A11y:** focus trapped in the drawer, starting in the field. Esc closes it and returns focus to the Ask button. A visible `role="status" aria-live="polite"` mirrors
  the stage label, plus a final "Answer ready, 3 links." Link cards are `<a target="_blank" rel="noopener">`, ≥ 44 px tall.
- **DoD:** the §0 template for `ask-stages` (render at `--wait 600`, `1200`, `2500`; each frame shows the next real stage), `ask-done` and `ask-offline`. The default
  `?stage=idle` render has no Ask button. Live: one real "tips for running" with ≥ 3 checked links, or Ask stays hidden and out of the video.

## 7. D1f: island night proposal (lane I, 45 min)

- **Why:** the 22:00 report already reaches the island with the server's actions, through the generic alert path (`alertView`, `alertButtons`): Accept (primary) and
  Not now (secondary). Three things break the prototype's 22:00 beat. The line is the whole digest `text` cut at 4 lines, so the question, always its last line, is
  usually hidden. The panel folds after 10 s (`dismissAfter` default). Pinch is hard-coded `idle` in `alertView`.
- **Files:** `native/Island.swift`; `docs/design/fixtures/island/all.json` (one `_alerts` entry, `report_proposal`, copied from a real `report` alert). No board: the
  reference is the prototype's 22:00 island (open, 400 pt: the question, Add, Not now).
- **Trigger:** an alert whose `actions` include a post to `/api/digests/{slot}/accept`: `kind: "report"` at 22:00, or `kind: "digest"` when a night is run by hand.
- **Layout:** the 400 pt alert frame. Header: ALIBI and "Night review · 22:00" (from `ts`). A 56 pt Pinch beside the question, at most 2 lines: `proposal.prompt`
  once it lands (§11 ask 4), until then the last line of `text` ("Move drawing to tomorrow 07:30, 25 min?"). Then primary "Add" (the server's Accept, relabelled in
  `alertButtons`; the payload is unchanged) and quiet "Not now" (dismiss). No trace and no Undo here: the web card keeps both.
- **Behaviour:** it stays until Add, Not now, Esc or 10 min, like `planned`, never on the 10 s timer. Add posts the action as it is, and the reply line shows the
  server's `reply` ("Done. Drawing tomorrow 07:30, 25 min. It's on the plan."); after an accept elsewhere, "Already on the plan: drawing tomorrow 07:30, 25 min.".
  Pinch plays `connected` on `ok`. The 07:30 brief needs no work: its `digest` alert opens the same frame, with the memory line first in its `text`.
- **Pinch:** the server's mood (`state.pinch.mood`, `reading` for 10 min after a report) mapped to `PinchMood`, instead of `idle`. The prototype draws `thinking`;
  Mascot.md keeps `thinking` for a call in flight over 600 ms, so here it shows only if the Add post takes that long.
- **Reduced motion · A11y:** as every island alert. The panel's accessibility label is the question; Esc is Not now.
- **DoD:** a temp build only: `swiftc -O native/main.swift native/Island.swift native/shared/*.swift -o $S/alibi-island`. Then `$S/alibi-island --snapshot $S/isl
  --state docs/design/fixtures/island/all.json` and Read `island_report_proposal.png`: the whole question, Add primary, Not now quiet. Every other render matches a
  baseline taken with the same command before the change (`imgdiff.py`). Live, on the §0 lab server: `curl -s -X POST http://127.0.0.1:8785/api/digests/run -H
  'Content-Type: application/json' -d '{"kind":"night"}'` (the lab week needs something behind, or `proposal` is null), then `ALIBI_API=http://127.0.0.1:8785
  $S/alibi-island --act Add` prints `reply=Done. …` and a second run prints `reply=Already on the plan: …`. lint_design OK on `native/Island.swift`.

## 8. D2 (stretch): inline habit edit with Undo (lane W3, 45 min, after backend B4)

- **Files:** `alibi/web/js/setup.js`, `alibi/web/css/setup.css`. No board yet.
- **Insert:** in `habCard()`, the `default_min` and `weekly_target_min` inputs of saved habits get `data-patch`. A `change` listener on `#habitsEd` (fires on Enter or
  blur) PATCHes those fields. They leave the dirty and Save-footer flow (`setMsg`); new habits keep the PUT path.
- **Data:** `PATCH /api/habits/{key} {fields:{default_min:30}, expect:{default_min:25}}` → 200 `{ok, reply, habit, rev}`, or 412 `{current, reply}`. On 200, write the
  new value into `habModel[i].h` and `habitsCfg`, so a later whole-map PUT (which sends `rev`) can't revert it.
- **Copy:** toast "Drawing: usual length 30 min." with Undo for 6 s. Undo re-PATCHes with `expect` set to the new value. 412: the field shows the current value, and
  `.herr` says "Changed elsewhere to 35 min. Kept that."
- **Motion:** a ✓ beside the field fades in over `--dur-micro` and out after 1.6 s. Toast as in the shell.
- **Reduced motion · Pinch:** the same, as fades. Pinch: none (this is chrome).
- **A11y:** existing labels. `.herr` is `role="alert"` and linked with `aria-describedby`. Undo is reachable by keyboard while the toast shows.
- **DoD:** on the lab server, `--eval` an async IIFE that sets Drawing's usual length to 30, dispatches `change`, then returns `(await (await
  fetch('/api/habits')).json()).habits.drawing.default_min` → 30. Next, `curl -X PATCH` with a wrong `expect` → 412. Finally, render the drawer with the toast showing.

## 9. D4 (stretch): Alibi.app window (lane I, 2 h; backend reviews; first to cut)

- **Files:** new `native/Window.swift` (`AlibiWindowController`: `NSWindow` + `WKWebView` on `http://127.0.0.1:8765/`); `native/Island.swift` (monitor fixes and an
  "Open Alibi" icon button in the panel header); `native/main.swift` (reopen handler and a `--window-snapshot FILE.png [--url U]` test seam); `scripts/build_native.sh`
  (add `native/Window.swift` to the island `swiftc` line only). No board yet.
- **Behaviour:** 1280×860 default size, 720×560 minimum, frame autosave name `AlibiWindow`. Transparent titlebar with full-size content. Window and web view background
  `#000`, so there's no white flash. `.regular` while open, `.accessory` on close. ⌘1–4 scroll to `#nowBlock`, `#todayBlock`, `#weekBlock`, `#sessBlock`. ⌘W closes.
  Off-origin links open in the browser. While `:8765` doesn't answer, show "Starting Alibi…" (Pinch `listening`, still) and retry every 2 s. ⌘Q closes the window and
  must not terminate: `DaemonOwner` stops the daemon on quit. Check ATS: if loopback HTTP is blocked, add `NSAllowsLocalNetworking`.
- **Island fixes (required):**
  1. The local `keyDown` monitor swallows Esc (keyCode 53) app-wide, which would stop Esc from closing the dashboard drawer. Scope it to `e.window === panel ||
     island.mode != .collapsed`.
  2. A click inside the focused window is a local event, so the global "click elsewhere folds" monitor never sees it. Add a local `leftMouseDown` branch: `e.window !==
     panel && island.pinned && mode == .expanded` → `collapse()`.
  3. `collapse()`/`giveBackFocus()`: when the previous app is Alibi itself, re-key the window instead of activating `previousApp`.
- **DoD:** a temp build only: `swiftc -O native/main.swift native/Island.swift native/Window.swift native/shared/*.swift -o $S/alibi-island`. Then `$S/alibi-island
  --snapshot $S/isl` and compare with the baseline (imgdiff, unchanged). Then `$S/alibi-island --window-snapshot $S/win.png --url
  http://127.0.0.1:8785/?stage=plan-mixed` and Read the PNG. Live checklist, run once with the user at the Mac, after the orchestrator runs `build_native.sh`: with the
  window focused, hover opens at 0.35 s; click pins; Esc folds the island; Esc in the window closes Setup; a click in the window folds a pinned island; ⌥⌘A toggles; ⌘Q
  leaves the daemon up (`./alibi.sh status`).

## 10. Order and parallelism

| Step | Lane | Piece | Exclusive files | Needs | Runs alongside |
|---|---|---|---|---|---|
| 0 | W1 | N0 wiring | `index.html`, `core.js`, `fixtures/**` | stage fixtures (ask 1); digests from `tests/fixtures/digest_night.json`, the rest hand-made from §11 shapes if late | nothing (first, alone) |
| 1 | W2 | D1a health strip | `js/health.js`, `css/health.css` | N0, B1 fields (shipped) | 2, 3, 4, 6, 7 |
| 2 | M | D1b digest | `js/digest.js`, `css/digest.css`, `pinch.py` | N0, B2/B2b (shipped) | 1, 3, 4, 6, 7 |
| 3 | W3 | D1c egress | `signals.html`, `js/egress.js`, `css/egress.css` | B6 (shipped) | 1, 2, 4, 6, 7 |
| 4 | W2′ | D1d Gantt | `js/gantt.js`, `css/gantt.css` | N0, F4b endpoint (shipped) | 1, 2, 3 (a second W2 agent; otherwise after 1) |
| 5 | W1 | D1e Ask | `js/ask.js`, `css/ask.css`, `core.js` (Esc line) | N0, B8, one real call | 1–4 |
| 6 | I | D1f island night proposal | `native/Island.swift`, `docs/design/fixtures/island/all.json` | nothing new: the alert already carries the actions | anything (no web files) |
| 7 | I | D4 window | `native/Window.swift`, `Island.swift`, `main.swift`, `build_native.sh` line | D1f (same lane), backend review, user at the Mac | anything (no web files) |
| 8 | W3 | D2 inline edit | `setup.js`, `setup.css` | B4 | after 3 |

Only N0 touches `index.html`. Nobody edits `week.js`, `now.js` or `moments.js`; the new modules hang off `alibi:report`, the hosts N0 adds, and the public
`AlibiPinchWire` API. The re-record needs 0 + 1 + 2 + 3 green (NEXT_PHASE §8 D1), plus 6 if the 22:00 beat shows the island. Cut order: D4 → D2 → D1e → egress
chips → D1f (then keep the island out of the 22:00 shot) → D1d. Never cut D1a, D1b or the egress table.

## 11. Asks to the backend (numbered; status as of f635c79)

1. **Fixtures. Open.** Dump golden JSON from `test_pace3`, `test_egress`, `test_plan_overview` and, later, `test_ask` (fake clock at the §0 stage times, persona
   habits) into `docs/design/fixtures/api/<stage>/<file>.json`, using the §0 file names, plus `index.json` per stage. Digests are covered for now: `test_digest`
   rewrites `tests/fixtures/digest_night.json` (gitignored) on every run with a full accepted night row.
2. **`build_json().rows[]`. Mostly answered.** Shipped: `status3` (with `done` and `stale`), `buffer_days` (half steps), `need_per_day_min`, `need_today_min`,
   `capacity_left_min`, `stale`, `unit`, `pace_min`, and `reason` as one sentence; Running has the same fields in `report.running`. Design counts the rollup from
   `status3` and reads milestones from `/api/plan/overview`, so a new `headline` and report `milestones[]` are no longer needed. Open: the cause noun for `warn-ink`
   (`reason_noun`, or `reason` as `{text, noun}`).
3. **`/api/plan/overview`. Answered** (`alibi/routes_plan.py`): the F4b shape plus `unit`, `reason` and `blocks[].key`; block states planned | done | partial |
   slacked | missed (a skipped block counts as missed); milestone `status` done | pending | at_risk | off_track; Health habits are left out.
4. **Digests. Answered, with a different shape** (9516af5, f635c79): `text` instead of `lines[]`, `json.pinch` instead of `pinch_line`, `turns` and `total_ms` instead
   of `ms_total`, a `result` per trace step. Accept `{ok, reply, block}` is idempotent (`already: true`), a passed slot is HTTP 200 `ok: false`, and Undo is its own
   route (`POST /api/digests/{slot}/undo`, 409 when not accepted). Open: `proposal.prompt`, the `_ask()` question as a field, so the card and the island stop
   reading the last line of `text`.
5. **Alert. Answered.** Morning and checkpoint alerts are `kind: "digest"` with `slot`, `digest_kind` and `actions`; the 22:00 night is `kind: "report"` with `slot`,
   `proposal`, `via` and `actions` (Accept posts `/api/digests/{slot}/accept`, Not now dismisses). `/api/state.alert` passes every field. Design adds the `pinch.py`
   case (D1b).
6. **Egress. Partly answered** (384516e, f635c79): `{now, rows[{what, where, active, host, why}], summary{where, active, text, leaves_tailnet}}`. `now` stands in for
   `checked_at`, and the Habit names row plus `summary` carry the Spark's state. Open: `fields[]` (names only) and `last_ts` per row, for the row expander.
7. **`/api/state.capabilities{ask}`. Open.** Only the phone's `/api/phone/session` has `capabilities {say, end, ask: false}`.
8. **Ask. Open** (no `/api/ask` yet): `stage` ∈ contacting_spark | waiting | checking_links | done | error, plus `links_done` and `links_total`. When HEAD link checks
   ship, `egress()` needs a row for them: the Mac contacts each link's site.
9. **Habits. Open.** PATCH returns `{ok, reply, habit, rev}`; 412 returns `{current, reply}`. PUT accepts `rev` and answers 409 when it's stale.
10. **D4 review. Open.** Confirm the ⌘Q policy (close, don't quit) and that `DaemonOwner` keeps running across window open and close.
11. **Memory timing. Open, a decision.** A memory line is frozen when its morning row is built. For a 07:30 block, the 07:30 brief says "It's on now."; "You showed
    up for 22 of 25 minutes." needs a morning row built after the block (a run by hand, as in `digest-kept`, or the next day's brief, which starts "You moved
    drawing to 07:30 yesterday."). Should checkpoints carry `memory` too, so the 12:00 checkpoint reports a morning block's outcome the same day?
12. **Why rules. Open, optional.** A `via: "rules"` row doesn't say why no model answered: none set up, no reply, or out of time. A short field (for example
    `fallback: "no_model" | "unreachable" | "timeout" | "invalid"`) would let the rules foot line say so. Until then it says only "The rules on this Mac picked the
    slot."
13. **Pace for scheduled habits. Open, a decision with the user.** `report.pace3` paces a habit with a `schedule` by its finished blocks and calls it off track as
    soon as what's left exceeds what's planned. With the Gantt board's blocks as schedules, Thu 22:00 gives Building "1 min behind. Only 45 min planned.", Math
    "25 min behind. Only 50 min planned." and C++ "6 min behind. Only 60 min planned.", all off track. The boards are cut with straight-line pace ("4 of 6 on
    track"). Is one minute short with one block left meant to be off track? Either way, the golden dump (ask 1) should use the persona's real schedules.
14. **Egress `where` for other hosts. Open.** `signals._where()` files every host that isn't loopback or `*.nvidia.com` under `tailnet:spark` (via
    `config._local_llm`), so a model on any other cloud would read "your Spark over Tailscale". Ask for a fourth value (or `other`) before anyone points
    `LLM_BASE_URL` elsewhere.
15. **Fast fallback. Open, optional.** `llm.chat_tools` gets the whole remaining budget as its timeout (45 s, no retries) and nothing probes first, so a Spark that
    doesn't answer can hold the 22:00 report for up to 45 s before the rules step in. In the kill-the-Spark beat that is dead air. `signals.probe()` (2 s, cached
    60 s) before the loop would make the fallback near-instant.

## 12. Risks

| Risk | Guard |
|---|---|
| Ask visible or recorded without a real grounded call | Capability-gated render. Not in any default stage. Out of the video unless one real call passes. |
| Fake progress: timed stages, replayed trace, invented "thinking" steps | Labels come from the polled `stage` only. The trace renders from stored data in one paint. The only delay is Pinch's 600 ms mood guard. |
| Dishonest `via` or privacy wording | `via` and `where` maps (§3, §4); `why`, `reply`, `result` and memory lines shown as sent; rule 5 via the Camera frames row only. No digest says NemoClaw. |
| A memory line shown before it's true | The client never writes one. "You showed up for…" only comes from a morning row built after the block (§0 `digest-kept`, ask 11). |
| Fixtures drift from the real shapes | Backend golden dumps (ask 1); digests from `tests/fixtures/digest_night.json`. Re-render against the lab server with no `?stage` before the re-record. |
| The kill-the-Spark flip lags on camera | Probes are cached 60 s and the block polls every 30 s: allow up to 90 s, and cut the wait in the edit. |
| The 22:00 island hides the question | D1f; if it's cut, keep the island out of the 22:00 shot. |
| 15 s polls replay entrances or stack announcements | `wkPaint` signatures. Announce only on transitions. Count-ups only on first paint or a value change. |
| Esc swallowed / clicks not folding the island with the window focused (D4) | The three island fixes in §9 are part of D4's DoD, not follow-ups. |
| ⌘Q in `.regular` mode kills the daemon | `applicationShouldTerminate` closes the window instead. Checked live with `./alibi.sh status`. |
| Page length grows (brief + strip + Gantt) | Brief hidden when stale or dismissed. Strip only on Today. Gantt below the week grid. Ask the user before replacing `#wgrid` with the Gantt (open question). |
| Red creeping into fills | Meters stay neutral (`ink-2` fill, the pill carries the status); slacked bars are outlined. lint_design and a look at every render. |
