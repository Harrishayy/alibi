# Alibi, next phase: final product and engineering spec

Final version, Thu 1 Oct 2026, 19:20 BST. It merges four research briefs, a judge critique and an engineering critique, plus my own read-only checks of the repo. Nothing in the repo was changed.

**What the repo shows right now** (each item checked):
- **No LLM is on.** `TEXT_READY` (`alibi/config.py:39`) needs an `nvapi-` key and a real `LLM_MODEL`. The `.env` has neither: the key is too short and the model IDs are `<…>` placeholders. So the text model is rules and the witness is Apple Vision.
- **No timeouts.** `alibi/llm.py:6-7` builds module-level `OpenAI(...)` clients with no timeout and no `max_retries`. `chat_text` uses `max_tokens=300` (`llm.py:30`).
- **Test env gap.** `tests/harness.py:6-13` sets `ALIBI_DATA_DIR`, `ALIBI_HABITS`, `VISION_BACKEND`, `MAC_SIGNALS` and `PACE_HOURS`. It does not set `NVIDIA_API_KEY`, `LLM_BASE_URL` or `LLM_MODEL`, and `config.py:6` loads `.env`.
- **Daemon slots.** Pace nudges are keyed on `config.PACE_HOURS` (hour only) at `daemon.py:68-90`. The nightly report notifies `kind="report"` at `REPORT_HOUR` (`daemon.py:168-178`).
- **`calendar_sync.move(key, at)` only moves within the same day** (`calendar_sync.py:609`: "another time the same day"). **"Carry to tomorrow" does not exist yet.** This changes the night-review design (§3 F5).
- **No schedules and no history.** `habits.yaml` has no `schedule:` entries. `data/alibi.db` has 0 done sessions. `scripts/seed_demo.py:96-97` refuses to add schedules when `ALIBI_HABITS` is the real file.
- **Spark serves nothing yet.** It is on the tailnet (100.76.35.21), but ports 8000, 11434, 18789 and 8443 all refuse.
- **No `tailscale serve` on the Mac.** The phone reaches `:8766` over plain HTTP, LAN first (`ios/Generated/AlibiConfig.plist`).
- **Demo shot list.** `demo/shotlist.md` has a 75 s cut that uses only features that already work.

**Ground rules:**
- `db.py` stays frozen.
- Offline-first: every feature has a rules path that works with the Spark and NVIDIA Build both down.
- Never claim data Alibi doesn't have. Screen Time is an aggregate of the picked apps, and there is no Watch.
- Status, ETAs and colours are deterministic.
- The model may **choose and propose** (which block, which time, what to read), but it never **decides truth** (verdicts, status, milestone done).
- Every model output carries a truthful `via`. `llm:spark` is not `nemoclaw`.

---

## 0. Timeline reality (read this first)

It is 19:20 and recording is 21:30–22:45, which leaves about 2 h 10 m. **Nothing in T1 will be in tonight's video.**

- **Tonight's recording is the safety cut.** Use `docs/design/DEMO.md` (the redesign's 90 s plan, driven by `docs/design/demo/stage.py`; it supersedes `demo/shotlist.md`), plus whatever T0 lands. Record fully offline (rules plus Apple Vision). Do not switch on the Spark or a key tonight.
- **Strongly recommended: re-record tomorrow morning** with the agent beat (night replan, then the morning callback). That beat is the single biggest lever on criterion 1. Whether a re-record is possible is decision **D1** below.
- **The tiers are honest:**
  - **T0** (before 21:30): about 2 h.
  - **T1** (before submission): about 8–10 engineer-hours, split across the backend and design sessions.
  - **T2**: the booth on Oct 14.
  - The draft's T1 was about 50 h; most of it has moved to T2.

---

## 1. Pitch and the judging criteria

**One sentence (for the video and the form):** *Alibi only ticks a habit when your Mac and iPhone can prove it, and an agent on a DGX Spark replans your week when you slip.*

Use the second half only once the Spark beat is real. Until then: *"Alibi only ticks a habit when your Mac and iPhone can prove it."*

**Who it helps:** people who keep promising themselves "I'll do it this week" and lie to their own habit tracker.

| Criterion | Today | After T1 (if the re-record happens) |
|---|---|---|
| **1. Agent deployed** | A long-running daemon: witness, verifier, nudges, nightly report. Fully offline, all tests green. LLM use is one-shot and currently off. | **One visible, multi-step, tool-using decision with memory.** The 22:00 night review runs a bounded tool loop on the Spark model: it reads the week, today's plan and free gaps, then **proposes** a replan. One tap applies it. The 07:30 morning brief **quotes last night's promise and checks whether you kept it**, from `sessions`. Kill the Spark on camera and the rules version still arrives. |
| **2. Innovation** | Evidence-checked habits: Apple Vision plus window titles, Screen Time pickups and Strava, fused into one verdict. | The same, plus a local DGX Spark agent that is visibly doing work, and a Streams view whose egress row changes when the Spark goes away. |
| **3. Real-world value** | Weekly report and nudges. | One number you act on: **"Drawing: 40 min behind. 35 a day until Sunday."** Plus the night shutdown (carry, move or drop). |

**User override (19:30):** the Gantt stays in T1 in a deterministic form: weekly-target bars with the pace line, planned blocks, and challenge milestones (F4b). **Cut from the story** (it is still fine to build these later): the confidence cone, the 12-week grid, burn-up small multiples, the Alibi.app window, and phone habit editing. None of them adds judging value in a 90 s video.

---

## 2. Surfaces and information architecture

**One API, three shells.**
- The daemon's FastAPI on `127.0.0.1:8765` is the only source of truth.
- The phone reaches a curated subset on `:8766` (secret header).
- The Spark reaches a further-curated `/api/agent/*` subset on `:8766` with its own token (§6 and NEMOCLAW.md).
- Nothing opens 8765 off-box.

| Surface | Role | Change this phase |
|---|---|---|
| **Notch island** | Glanceable state and the composer | **Idle stays exactly the notch, with no wings** (AGENTS.md). The buffer value ("−40m drawing") shows **inside the open panel only**. The composer already does "add habit guitar 20 min" (`cli.py:365`). No habit editing on the island. |
| **Web dashboard** | The full client | Health strip at the top of Today. Digest card (latest brief, with the agent's proposal as a confirm card). Streams egress block on `/signals`. Habits keep the existing Setup editor. |
| **iPhone** | Sensor and mirror; adds a "Say" write in T1 if time allows | T1: backend `POST /api/phone/say` plus `end`. iOS UI (composer, End button) only if the morning has time **after** a backup build. Tabs, habit editor and Streams tab are T2. |
| **Alibi.app window** | The user's chosen "real app" | T1-stretch / T2 (§3 F9). The browser keeps working. Never shown in the video as a feature. |

**Shared contract:**
- Every write returns `{ok, reply, session}`. All copy comes from the server, so every surface uses the same words.
- The phone hides any feature whose `capabilities.*` flag is false.

---

## 3. Feature list

Tiers:
- **T0**: before 21:30.
- **T1**: before submission.
- **T1s**: T1 stretch, only after the T1 items are green.
- **T2**: booth.
- **CUT**: dropped.

Robustness is scored 1–5; 5 means pure arithmetic over existing data, with tests.

### F0. Hardening. **T0.** Robustness 5. About 1 h.
Prerequisite for anything that touches an LLM or the Spark.

1. **Hermetic tests first.** In `tests/harness.py`, set:
   - `NVIDIA_API_KEY=""`
   - `LLM_MODEL=""`
   - `LLM_BASE_URL="http://127.0.0.1:9/v1"`
   - `VLM_MODEL=""`

   Use plain assignment, not `setdefault`. Without this, the moment `.env` gets a key or a Spark URL, every test that reaches `report.build_json` calls the network.
2. **Request paths never call the LLM.**
   - Add `report.build_json(now, prose=False)` and default to rules (`_dry`) on every request path:
     - phone mirror (`integrations.py:772`)
     - `/api/report` (`api.py:296`)
     - `cli.end` (`cli.py:254`) and `cli.py:106`
     - `strava.py:307`
     - the pace nudge (`daemon.py:76`)
   - LLM prose is generated **only in a background worker** for digests and the nightly report. It is cached by `(kind, slot)` and shown when ready. The rules text shows until then.
   - This replaces the draft's `max(ended_at)` cache key, which missed corrections made through `/api/sessions/{sid}/correct`.
3. **Client settings.** `llm.py`:
   - `timeout=45, max_retries=0` for background calls, and `timeout=8` for anything interactive (Ask's first token).
   - Disable thinking. For Qwen3 on vLLM, pass `extra_body={"chat_template_kwargs":{"enable_thinking":false}}`. For Nemotron, a `/no_think` system line; **verify this per model**.
   - `max_tokens` 300 → 600 for prose.
4. **Keyless Spark gate.** `TEXT_READY = (valid nvapi key and LLM_MODEL) or (LLM_BASE_URL host is not *.nvidia.com and LLM_MODEL set)`.
5. **Vision stays local.** `VISION_BACKEND` defaults to `apple` **unless `VISION_BACKEND` is set explicitly**. Today `config.py:40-41` flips it to `nvidia` when `TEXT_READY` and `VLM_MODEL` are set, and `VLM_BASE_URL` defaults to `LLM_BASE_URL` (`:16`). Under the new gate that would silently send camera frames to the Spark or to Build, which breaks rule 5.
6. *(Dropped from the draft: `ALIBI_APPLE_WATCH=0` is already handled at `signals.py:496-504` and `integrations_state.json`.)*

**DoD:** `tests/test_llm_guard.py`. Each case runs in a **subprocess**, because `config` and `llm` are module-level.
- With a stub server that sleeps 60 s, `chat_text` returns the fallback in under 10 s (8 s interactive timeout).
- `build_json()` called 50 times makes 0 LLM calls (monkeypatched counter).
- `TEXT_READY` is true with `LLM_BASE_URL=http://100.76.35.21:8000/v1`, `LLM_MODEL=x` and no key.
- `VISION_BACKEND == "apple"` with `VLM_MODEL` set and `VISION_BACKEND` unset.
- `./alibi.sh test` is green with a fake key and a Spark URL in the environment.

### F2. Pace v2: three states plus buffer days. **T0** backend if B0 is green by 20:15, otherwise **T1**. Health-strip UI **T1**. Robustness 5. Backend about 1–1.5 h.
- **Story.** One honest number per habit: days of buffer, or minutes per day needed.
- **Computation.** §4, formulas 1–6. This version fixes: status order, at_risk that can actually be reached for unscheduled habits, the stale rule, and the Sunday-night edge case.
- **Change.** `_pace(h, t0, now)` already takes `now` (`report.py:40`), so no refactor is needed. Add these to each `build_json().rows[]`:
  - `status3`
  - `buffer_days`
  - `need_per_day_min`
  - `need_today_min`
  - `capacity_left_min`
  - `stale`
  - `reason`

  Keep the existing `status` for compatibility.
- **Screens (T1, design).**
  - **Health strip:** one pill per habit with dot, shape and word ("On track", "At risk", "Off track", "Can't see"), the buffer value and a reason chip. No red bar fills.
  - **Island:** the open panel only.
- **DoD.** `tests/test_pace3.py` with the fake clock:
  1. Mon 09:00, target 300, verified 0: on_track. Note this is because of the 0.1T band; `_pace`'s grace doesn't apply, since no habit has `created_at`.
  2. Thu 20:00, verified 60, no schedule: off_track, `need_per_day_min` correct to ±1.
  3. Unscheduled, gap 0.2T: at_risk (the band rule).
  4. Scheduled, with 240 min of blocks left covering the gap: at_risk, not off_track.
  5. Running at 1 of 3 runs on Sat: off_track.
  6. Running with no `strava` event in 24 h and Strava configured: stale. Drawing (camera) is never stale.
  7. Sun 20:00, gap 10 min: at_risk, not off_track (the `days_left ≥ 1` gate).

### F5. Checkpoints with an agent night review and a remembering morning brief. **T1, the core of the re-record.**
- **Story.**
  - **07:30:** what today needs, plus whether you kept last night's promise.
  - **12, 16 and 20:** a brief only if something changed.
  - **22:00:** close the day; the agent proposes how to recover missed time, and you tap to accept.
- **Generator.** A new `alibi/digest.py`:
  - `build(kind, now) -> dict`: pure, over `report.build_json(prose=False)`, `calendar_sync.plan` and `signals.day_summary`.
  - `text(d)`: rules always first. LLM prose is added by the background worker when `TEXT_READY`.
- **Schedule.**
  - Add `_digest(con, now)` **alongside** `_pace_nudge`. Leave `PACE_HOURS` and its tests alone.
  - Slots: `MORNING_AT=07:30` (minute-aware), `CHECK_HOURS=12,16,20`, and night at `REPORT_HOUR`.
  - The night digest **replaces the text** of `_nightly`'s notify. It keeps one notification and the existing dedupe; it never adds a second one.
  - Each slot is deduplicated by `slot_id="YYYY-MM-DD-kind[-HH]"`. On wake, only the most recent missed slot runs.
- **Content.**
  - **Morning:**
    - today's blocks;
    - `need_today_min` per habit;
    - the first free gap ≥ `default_min`;
    - **memory callback**: read the last `night` row in `digests.jsonl`. If it holds an *accepted* proposal, check `sessions` for that habit inside the proposed window, e.g. "Last night you moved drawing to 07:30. You showed up for 22 of 25 minutes." (Robustness 5: a JSONL read plus SQL.)
    - last night's sleep, as a fact, if `health.samples` has it.
  - **Checkpoint:**
    - the diff against the previous slot's stored JSON: verified minutes, verdicts, blocks missed, picked-app minutes, `status3` changes;
    - **suppressed** (`sent:false`, no notify) unless something changed or a block starts within 4 h;
    - one action button.
  - **Night:**
    - done, partial, slacked and missed lists;
    - buffer per habit;
    - `alibi_score`;
    - **the replan proposal** (below);
    - "one thing to fix tomorrow".
- **Replan: a bounded tool loop. T1, the agent beat.**
  - **Loop.** At most 4 model turns, OpenAI `tools=` against `LLM_BASE_URL` (vLLM on the Spark). It runs in the background worker with a 45 s total budget.
  - **Read tools** (in-process functions, no HTTP):

    | Tool | Backed by |
    |---|---|
    | `week_status()` | `build_json` rows with `status3` / `buffer_days` |
    | `plan(day)` | `calendar_sync.plan` |
    | `free_gaps(day, min_minutes)` | gaps between planned blocks and sessions, 07:00–22:00 |
    | `history(habit, days=14)` | daily verified minutes |
  - **Proposal tool:** `propose(habit, day, at, minutes, why)`. It is validated by code: the habit exists, the slot is free, minutes ≤ `MAX_SESSION_MIN`, and the day is today+1 or today+2. An invalid proposal is dropped and the rules picker is used.
  - **Never auto-applied.** The proposal is stored in the night digest and shown as a confirm card ("Move drawing to tomorrow 07:30, 25 min?").
  - **Accept** calls `POST /api/digests/{slot}/accept`, which applies it through calendar code. **New capability needed:** `calendar_sync.add_once(habit, date, at, min)`, an extra one-off block. Today `move` is same-day only (`calendar_sync.py:609`) and only for scheduled occurrences. If `add_once` slips: when the habit has a block tomorrow, use `move` on tomorrow's key, and skip tonight's missed key.
  - **The tool trace is stored** (`trace:[{tool,args,ms}]`) and shown as a disclosure under the card: "Checked week → plan tomorrow → free gaps → proposed 07:30." This is the visible multi-step beat. It is **real**, never timed.
  - **Rules fallback** (Spark down, no tool support, timeout or invalid output): the most-behind habit goes to the first free gap ≥ `default_min` tomorrow, with `via:"rules"`. Same card, same accept path.
- **Delivery.**
  - Append to `DATA_DIR/digests.jsonl`.
  - `notify(kind="digest")`.
  - Also Telegram if `NOTIFY` is configured for it; `.env` has a bot token, so the morning brief still lands with the Mac lid shut.
- **API.**
  - `GET /api/digests?limit=20`
  - `GET /api/digests/latest`
  - `POST /api/digests/run {kind}` (demo and tests)
  - `POST /api/digests/{slot}/accept`
  - `digest_latest` in the phone mirror
- **Robustness.** 5 for the JSON and rules; 4 for the tool loop, which depends on Spark tool-calling. **Effort:** about 4 h backend (digest 2 h, loop 1.5 h, `add_once` 0.5 h) and 1.5 h for the web card.
- **DoD.** `tests/test_digest.py`, fake clock, no network:
  - a 07:30 tick writes exactly one morning row; a second tick writes none;
  - a 12:00 tick with no change since morning stores `sent:false` and notifies nothing;
  - a session ending between 12:00 and 16:00 gives a non-empty 16:00 slot with the right delta;
  - **memory:** an accepted night proposal for drawing at 07:30, plus a 22-min drawing session at 07:31, makes the next morning text include "22 of 25";
  - **tool loop** against a local stub server that returns scripted `tool_calls`: the trace has 3 or more steps and the proposal validates; a stub returning an invalid slot falls back to `via:"rules"`; the stub down gives `via:"rules"` in under 2 s;
  - accept creates the block, and `plan(tomorrow)` shows it.

### F6. Streams: what is taken and what leaves. **T1** backend; web block **T1**; phone tab **T2**. Robustness 5.
- **Base.** `/api/signals/status` (`signals.py:508-588`) and `/signals` (`web/signals.html`) already exist.
- **Add (backend):**
  - **`signals.egress()`**: rows `{what, where:"mac"|"tailnet:spark"|"nvidia_build"|"search_provider", active, why}`, derived at call time from the config and a cached Spark probe (60 s). The `active` flag flips when the Spark goes down, which is the "kill the Spark" beat.
  - **`signals.hourly(con, keys, hours=24)`** beside `live()`. It is a stated reporting read, like `live()`.
  - **The git row reads `waiting`**: "No commits in the last N h", not `missing`.
- **Wording** follows AGENTS.md rule 5 exactly:
  - "Frames never leave the Mac" only for `apple` / `mock` or a local VLM.
  - "Habit names and minutes go to your Spark over Tailscale."
  - "Search questions go to the search provider."
- **Web (design).** An egress block at the top of `/signals` with three scope chips (Stays on Mac / Over tailnet / Leaves the tailnet) that dim, not delete. Rows expand to **field names** plus a timestamp, never values.
- **DoD.** `tests/test_egress.py`:
  - `apple` gives frames `mac`;
  - explicit `VISION_BACKEND=nvidia` gives `nvidia_build`;
  - a Spark `LLM_BASE_URL` with the probe up gives summary `tailnet:spark` active; with the probe down, it is inactive and the summary is `mac`;
  - `hourly()` returns 24 ints;
  - a planted secret string never appears in the JSON.

### F7. Phone "Say" and End (writes from the phone). **T1** backend minimal; iOS UI **T1s**; the rest **T2**.
- **Story.** Say "draw for 25" on the phone, and the Mac island goes live.
- **Backend:** a new `alibi/routes_phone.py`, mounted in `phone_app()`. T1 has only:
  - `POST /api/phone/say {op_id, client_ts, text}` → `cli.say`. Returns `409 stale_start` if `now − client_ts > 120 s` and the text parses as a start.
  - `POST /api/phone/session/end {op_id, client_ts, session_id, artefact?}`, with a `session_id` guard (`409 already_ended`). Sets `ended_at = clamp(client_ts, started_at, now)` when more than 30 s late (`cli.end(..., ended_at=)` exists at `cli.py:200`).
  - `/api/phone/session` gains `capabilities:{say, end, ask:false}`.
- **Security (corrected).**
  - The header `X-Alibi-Secret` is required; `?key=` is refused on writes.
  - **Writes are accepted only when the client IP is loopback or the Mac's own tailnet peer range *and* the request arrives on the tailnet interface.** Practical rule: refuse writes from `192.168.*` / `10.*`, because the phone's first endpoint today is cleartext LAN (`http://192.168.1.148:8766`), where the header can be sniffed. The phone must try its **tailnet** endpoint (`100.66.226.12`) first for writes; that is a change to the iOS endpoint order (B7).
  - The CGNAT check is defence in depth, not access control: `thomas-laptop` and `spark` are also on 100.64/10.
  - Body ≤ 16 KB; 30 writes a minute.
  - **`op_id` dedupe holds a lock across check → execute → record**, keeping the last 500 in `integrations.state()`.
- **Not in T1:** break, extend, cancel, plan actions, phone habit CRUD, the CommandQueue (start is never queued; when T2 adds the queue, break and extend TTL is **2 min** and end is 6 h).
- **Effort:** 2 h backend; iOS composer and End button about 2 h, only after a known-good backup build.
- **DoD.** `tests/test_phone_writes.py`:
  - the same `op_id` twice, including concurrently from 2 threads, gives the same reply and one session;
  - a stale `session_id` gives 409;
  - a stale start gives 409;
  - `?key=` gives 401;
  - a LAN source IP gives 403.

  On device (T1s): "draw for 25" goes live in `/api/state` within 3 s.

### F8. Ask: voice to NemoClaw, grounded in Alibi's data. **T1, gated**; ships hidden unless real.
- **Story.** "Tips for running" →
  - "You've run 1 of 3 this week. Your next free 30 min is tomorrow 07:00." (computed by Alibi, rules)
  - plus a ≤80-word answer and 3–5 links from NemoClaw's `web_search`.
- **Grounding without inbound tools.** Alibi computes a small context (habit, this week's count or minutes, the next free gap) and **sends it in the prompt** to NemoClaw. NemoClaw's own multi-step tool use is `web_search` (and optionally `web_fetch`). Alibi's facts line is rendered by Alibi, not by the model.
- **API.**
  - `POST /api/ask {text, source}` → `202 {id}`, run in a worker.
  - `GET /api/ask/{id}` → `{state, stage, facts, answer, links:[{title,url,site}], links_checked:bool, via:"nemoclaw"|"llm:spark"|"offline", ms}`.
  - Phone mirror `/api/phone/ask` (T2 UI).
- **Upstream.** See NEMOCLAW.md §4. Connect 3 s, total 30 s.
- **Links honesty.**
  - Alibi cannot see tool output through chat completions, so it **HEAD-checks each URL from the Mac** (2 s each, in parallel; the HEAD request appears in the egress manifest as "link checks").
  - It keeps only 2xx/3xx responses and sets `links_checked:true`.
  - If HEAD checks are off, links are labelled "from NemoClaw, not checked".
- **Stages come from real steps only:** `contacting spark → waiting for answer → checking links (n of m) → done`.
- **Down:** `/v1/models` probe cached 60 s, then `llm:spark` plain answer (no links, labelled "No web results: NemoClaw is offline"), then `offline` "NemoClaw is offline." **No replay queue** (cut: it replays stale questions).
- **Capability.** `capabilities.ask` is true only after a successful probe **and** one successful grounded call.
- **Robustness.** 3, depending on the Spark (chat completions must be enabled on the gateway). The Alibi side is 5.
- **Effort.** Backend 2 h, web drawer 1.5 h.
- **DoD.** `tests/test_ask.py` with a local stub:
  - stub up gives `via:nemoclaw`, `facts` present, and links filtered by a stub HEAD server;
  - stub down gives `offline` in under 4 s.

  On device: one real "tips for running" returns ≥3 checked links, **or Ask stays hidden and out of the video.**

### F1. Habit quick add, edit and remove. **T1s** (web minimal); phone **T2**.
- **Already exists:**
  - island and chat "add habit guitar 20 min" (`cli.py:365`, `routes_onboarding.py:118`);
  - the Setup editor with whole-map PUT and delete by omission (`web/js/setup.js:144`, `api.py:333`).
- **Corrections to the draft:**
  - `GET /api/habits` already returns raw config (`api.py:324`); **add a top-level `rev`**, don't change the shape (`setup.js:134-138` reads `habitsCfg.habits`).
  - Conflicts use a **per-field compare-and-swap**: `PATCH /api/habits/{key} {fields, expect:{field: old}}` → 412 if the current value ≠ `expect`. The draft's "same field changed since base_rev" needs history that a single `.bak` doesn't keep.
  - The **lock is `fcntl.flock` on `habits.yaml.lock` inside `save_habits`**, because writers include separate CLI processes (`./alibi.sh say "add habit…"` → `onboarding.add`).
  - **Archive is CUT to T2.** `save_habits` drops unknown keys (`EXTRA_KEYS`, `health.py:177`; `_common` at `:227-250`). Honouring `archived` needs a `config.active_habits()` helper threaded through `cli.say` alias matching, `calendar_sync`, `mac_signals.repos`, onboarding, the island chips, `_mirror` and pinch. For T1, delete-with-confirm stays as it is today.
- **T1s web:** inline edit of `default_min` / `weekly_target_min` on Habits through PATCH, plus a toast with Undo (6 s) that re-PATCHes the old value.
- **DoD.** `tests/test_habits_rev.py`:
  - PATCH with a matching `expect` gives 200;
  - a mismatched `expect` gives 412 with the current value;
  - two processes saving at once both land (flock), and `.bak` exists;
  - `repos`, `schedule` and `phone_shield` survive.

### F3. Goals and challenge milestones. **T2**, except one static **T1** row.
- **T1:** the health strip shows one manual milestone row, "Submit Claw challenge, due 2 Oct", read from `DATA_DIR/goals.json` (manual `done_at` only). No ETA. Effort 30 min.
- **T2:** the full store (`goals.json` with `rev`; atomic write plus `.bak`), formulas 7–10, and the goal form.
- **Corrected `git_commit` semantics:**
  - match `events(source='mac', kind='git')` on **`payload.path`** (not the habit key; `repo` is `"c++"`, not `cpp`);
  - require **`payload.commits > 0`**: rows are also written for uncommitted diffs (`mac_signals.py:288-333`).
- **History reality.** The real DB has 0 sessions and the seed covers 4 days, so ETAs read "needs more history" until about Oct 8 of real use. That is honest, and fine.

### F4. Monitors. **T1:** health strip (F2) and the existing today timeline with plan data. **T2:** the rest.
- **T1:**
  - The health strip.
  - The existing Today timeline (`week.js:193-274`) already draws planned vs seen once schedules exist.
  - Add the phone lane as **one aggregate "picked apps" lane** with a "phone last synced HH:MM" stamp. A gap is drawn as a gap, never as zero. Expect it to be sparse: 2 Screen Time rows in 7 days.
- **T2:**
  - burn-ups (one "claimed vs seen" pair already exists in the Week view; that is enough for the video);
  - Gantt ETA bars for goals once there is history (the week Gantt itself is F4b, T1);
  - the cone and slider (only with 10+ days);
  - the 12-week grid;
  - `GET /api/plan/overview`.

### F4b. Week Gantt and deadline monitors. **T1** (user override). Robustness 5 (pure arithmetic, no LLM).
- **Rows:** one per habit, plus the challenge milestones (submit 2 Oct, booth 14 Oct) from `goals.json` (manual `done_at`).
- **Per habit row (Mon–Sun):** planned blocks as hollow bars, verified sessions as filled bars (verdict colour plus shape), the pace marker `P(now)` vs `V(now)` and the formula 4 status pill on the right ("40 min behind · 35/day").
- **Now-line:** 2px `accent`. Milestones are diamonds; past-due and not done = `warn` dot plus word.
- **API:** `GET /api/plan/overview?week=YYYY-MM-DD` → `{week_start, now, rows:[{habit,label,target_min,verified_min,pace_min,status3,buffer_days,need_per_day_min,blocks:[{start,end,state:planned|done|partial|slacked|missed}],sessions:[{id,start,end,verdict,ratio}]}], milestones:[{key,label,due,done_at,status}]}`.
- **DoD:** `tests/test_plan_overview.py`, fake clock and seeded week: one row per habit, blocks inside the week, a missed block marked `missed`, a milestone past due and not done is `off_track`.

### F9. Alibi.app window. **T1s / T2.** Robustness 4. 2 h.
- `NSWindow` plus `WKWebView` on `http://127.0.0.1:8765/`.
- `.regular` while open, `.accessory` on close.
- ⌘1–4 navigation; external links open in the browser; a "Starting Alibi…" retry placeholder.
- **The DoD adds the island checks:** with the window open and focused, the island's hover, click-to-pin, Esc and click-elsewhere fold all still work (`FirstClickHostingView` assumes Alibi is never the active app).
- `native/main.swift` is the daemon host, so the design session builds it and the backend session reviews it.

### F10. NemoClaw as author of the briefs. **T1s** (REST, read only plus `post_brief`); MCP is **T2**.
- See NEMOCLAW.md.
- **Alibi side.** `/api/agent/context` (GET) and `/api/agent/brief` (POST) on `:8766`, with a separate `nemoclaw_token` (header only), the same IP and interface rule as F7, and a rate limit. About 1.5 h.
- **Display.** An agent brief for a slot shows above Alibi's rules brief (folded under it), tagged `via: nemoclaw`.
- **Gate.** NemoClaw must be able to reach the Mac: either from inside the sandbox (unverified, because the SSRF guard blocks CGNAT), or from a Spark host-side job (NEMOCLAW.md §6, plan B).
- **No write tools for the agent** apart from `post_brief` and proposals. This avoids prompt injection from web pages.

### Explicit cuts
| Item | Why |
|---|---|
| Per-app phone minutes ("24 m on Instagram") | Screen Time is one `pickedLabel` aggregate (`ios/Shared/AlibiShared.swift:59-67`). The wording is always "picked apps (YouTube, Instagram)". |
| Habit edit or remove inside the island | Fragile focus in a non-active app. |
| Island wings when idle | AGENTS.md: idle = exactly the notch. |
| LLM-decided status, ETA, verdict or milestone | It makes the core claim unverifiable. |
| Auto-applied agent actions; MCP write tools | Prompt injection via web content. Proposals plus one tap only. |
| Ask offline replay queue | It answers stale questions hours later. |
| "Checking links" without actually checking | Dishonest. HEAD-check, or label them unchecked. |
| Faked staged progress, timed narration | Dishonest; it hurts criterion 1. |
| APNs Live Activity, iOS 18 Controls, interactive widgets | Push key or entitlements plus a reinstall. T2 at best. |
| Readiness or HRV scores | No Watch. |
| Monte Carlo before 10 days of history | Infinite cones. |
| Turning on the Spark or a key tonight | An unknown model and latency mid-recording. Record offline. |

---

## 4. Deterministic formulas (corrected)

**Notation.**
- Week = Mon 00:00 to Sun 24:00 local time; every per-day query uses `'localtime'`, as `_streak` does.
- `now` = `time.time()` at call time.
- `T` = the effective weekly target (pro-rated as in `_pace`).
- `T_s` = the count target (running, `weekly_sessions`).
- Daily health habits are excluded from 1–6.

1. **Verified:** `V(t) = Σ declared_min × on_task_ratio`, over done sessions ended ≤ t this week (`report.py:93`). **Claimed:** `D(t) = Σ declared_min`. Count habits: `V` = the number of qualifying sessions.
2. **Pace:**
   - With a schedule: `P(t) = T × M_ended(week_start, t) / M_week`, using block minutes from `_blocks()`.
   - Without one: `P(t) = T × clamp((t − a)/(week_end − a), 0, 1)`.
3. **Gap and capacity:**
   - `gap = P(now) − V(now)`.
   - `days_left = (week_end − now)/86400`.
   - `capacity_left` = the remaining block minutes when scheduled; otherwise `days_left × max(r, Q90_28d)`.
4. **Status, evaluated in this order:**
   1. **stale** (grey, "Can't see"): only for habits whose primary evidence is **Strava** (no `strava` event in 24 h while Strava is configured) or **phone/health** (no phone row in 6 h). Camera and screen habits are never stale; a broken witness shows in Streams instead.
   2. **done:** `V ≥ T`.
   3. **off_track:** `T − V > capacity_left` (scheduled), or `need_per_day > 2r and days_left ≥ 1`, or `gap > 0.3T` (unscheduled).
   4. **at_risk:** `gap > 0.1T`.
   5. **on_track:** otherwise.

   The unscheduled 0.1T–0.3T band is what makes at_risk reachable at all. With no schedule, the capacity rule collapses to `V ≥ P`.
5. **Rate and buffer:**
   - `r = T / active_days`, where `active_days` = the scheduled days, or 7. Count habits: `r = T_s/7`.
   - `buffer_days = round_half((V − P)/r)`.
   - `need_per_day = max(0, T − V)/max(days_left, 0.5)`.
   - Copy: "1.5 days of buffer" or "40 min behind. 35 a day until Sunday."
6. **Today:** `need_today = max(0, P(end_of_today) − V(now))`. Copy: "Drawing needs 25 minutes today to stay on pace."
7. **(T2) Goal rate:** an EWMA over 14 days, `0.9^i` weights, zero days included. Fewer than 5 active days gives `eta:null`, "needs more history".
8. **(T2) ETA** `= max(ETA_pace, ETA_plan)`:
   - `ETA_pace = today + ceil(remaining/rate)`;
   - `ETA_plan` = the first day the cumulative planned × `hit_rate` (`V_28/planned_28`, capped at 1) ≥ remaining.
   - Beyond due + 30 days: show "not at this rate".
9. **(T2) Goal status:**
   - done if `remaining ≤ 0`;
   - off if `ETA > due` or `required_rate > Q90`;
   - at risk if `due−1 < ETA ≤ due`;
   - otherwise on.
10. **Milestones:**
    - `git_commit`: any `mac/git` event with `payload.path == repo_path` and `payload.commits > 0` since `since`.
    - `sessions`: count ≥ N.
    - `manual`: `done_at` is set.

    Not done: off if `today > due`, at risk if ≤ 1 day remains, otherwise pending. No `done_when`: grey, "can't verify".

**Rollup:** worst-of; stale doesn't outrank off_track. Headline: "3 of 5 on track. Drawing is at risk: 40 min behind."

**Replan validator (F5):**
- the proposed `(day, at, minutes)` must lie within 07:00–22:00;
- it must not overlap a planned block or a session;
- `minutes ≤ min(MAX_SESSION_MIN, 2 × default_min)`;
- the day is today+1 or today+2.

**Rules picker:** the habit with max `−buffer_days` (ties → larger `need_per_day`) goes to the first gap ≥ `default_min` tomorrow.

---

## 5. Fluid interaction spec (tiramisu choreography, Alibi system)

The curves already match tiramisu (`ease-out .23,1,.32,1`, `ease-drawer .32,.72,0,1`). Port the **choreography**, not the identity.

**Global:**
- Entrances: 260 ms, 6 px lift, 40 ms stagger capped at 6, **first paint only** (`week.js:76-82`).
- Only `transform` and `opacity` animate.
- Exits run at 0.65×.
- Retriggerable changes use transitions or springs.
- Press scale 0.97 at 120 ms.
- Hover only inside `(hover:hover) and (pointer:fine)`.
- A reduced-motion block on every page.

| Pattern | Where (T1 first) | Spec |
|---|---|---|
| Docked next action, enters last | **Digest card** (T1) | Facts, then the Pinch line (+1000 ms), then one primary button ("Move drawing to 07:30"), black on `#76B900`. |
| Receipts / "not counted, with reasons" | **Agent trace under the proposal** (T1); verdicts; Streams rows | Disclosure: "Checked week → plan tomorrow → free gaps → proposed 07:30 (via spark, 3.1 s)." |
| Count-up synced to its shape | Health-strip buffer (T1) | Number and meter on one clock, 900 ms from +420 ms, tabular figures. |
| Dim, don't delete | Streams egress scope (T1) | Out-of-scope rows fade to `ink-3` over 280 ms; the count sentence rewrites ("2 sources send anything off this Mac"). |
| Real staged narration | Ask drawer (T1, gated) | `stage` polled every 500 ms drives the label (blur 4→0, 220 ms), mirrored to `role="status"`. **No timers.** |
| Per-item render with a count | Ask links | "3 of 5 links checked", one card per real check. |
| Micro-confirmation | Accept proposal, habit edit (T1s) | Top-right `Alibi.Toast` on `surface-2` with Undo (6 s). |
| Selection drives detail | Gantt / burn-up (T2) | `aria-pressed` on `surface-3`; the detail swaps over 260 ms with blur. |
| In-place view swap | Window tabs (T2) | `view-in` 240 ms; `@view-transition{navigation:auto}` where supported. |
| Recording replay | `?stage=` fixtures only | Remove the gate class, force a reflow, add it back. Never in the shipped UI. |

**Status visuals:** dot plus shape plus word.
- `#76B900`: on track
- `#F2A900`: at risk or partial
- `#E5484D`: off track or slacked
- grey: can't see

No red fills. Only the cause noun is set in `warn-ink`.

**Don't copy from tiramisu:** the cream or caramel palette, serif type, uppercase eyebrows, gradients and grain, shadow on every card, 24 px radii, glass tab bars on the web, shimmer skeletons, tilts and bobs, 480 ms or 55 ms timings, emoji or exclamation marks, timed fake progress.

---

## 6. NemoClaw integration (summary; the full contract is NEMOCLAW.md)

**Principle.** Alibi owns the clock and the truth, and always writes the rules version first. The Spark adds to it. With the Spark off, everything still runs, and the egress row says so.

| # | Direction | What | Tier | Depends on |
|---|---|---|---|---|
| 1 | Mac → Spark | **Raw model** (vLLM `:8000` or Ollama `:11434`) for digest prose **and the night tool loop** | **T1** | The model serves on the tailnet **with tool calling** (vLLM `--enable-auto-tool-choice --tool-call-parser <parser>`; unverified per model) |
| 2 | Mac → Spark | **OpenClaw gateway** `/v1/chat/completions` (`openclaw/default`) for grounded Ask with `web_search` | **T1 gated** | `chatCompletions` enabled (the config may be read-only), a web search provider, `tailscale serve` on the Spark |
| 3 | Spark → Mac | NemoClaw-authored briefs via `GET /api/agent/context` plus `POST /api/agent/brief` | **T1s** | Reachability from the sandbox (SSRF guard), or plan B: a Spark host-side job |
| 4 | Spark → Mac | MCP read tools plus `post_brief` | **T2** | `mcp add --trusted-private-host`, HTTPS on the Mac (`tailscale serve`) |

**`via` values are exact:**
- `rules`: Alibi's code
- `llm:spark`: row 1, a raw model on the Spark (not NemoClaw)
- `nemoclaw`: an OpenClaw agent produced it (rows 2–4)
- `llm:build`: NVIDIA Build

**Pitch wording, by what is actually working:**
- Row 1 working: "a model on my DGX Spark replans my week."
- Rows 2–3 working: "a NemoClaw agent on my DGX Spark."
- Neither working: the Spark isn't mentioned.

---

## 7. Data model (`sessions` and `events` unchanged)

| State | Where | Why |
|---|---|---|
| Habits (+ `schedule`) | `habits.yaml` via `save_habits`; `rev` = sha1[:12]; `fcntl.flock`; `.bak` | Existing contract. It is git-tracked, so keep `repos`, `schedule`, `phone_shield`. |
| Digests, including the proposal, trace and accept state | `DATA_DIR/digests.jsonl`: `{slot, kind, ts, sent, json, text, via, proposal?, trace?, accepted_at?, agent_brief?}` | Derived output, not evidence. Keeping it out of `events` stops the verifier reading its own conclusions (rule 1). Mirrors the `alerts.jsonl` pattern. |
| One-off planned blocks (`add_once`) | `calendar_sync` state file (alongside `moved`/`skipped`) | Same store as the existing plan overrides. |
| Asks | `DATA_DIR/asks.jsonl` | History. No replay queue. |
| Goals and milestones | `DATA_DIR/goals.json` (T1: one manual row) | Personal, so not in tracked `habits.yaml`; hermetic in tests. |
| `op_id` dedupe, agent liveness, probe cache | `integrations.state()` | Small mutable state. |

`goals.py`, `signals.hourly` and the digest memory read `events` or `sessions` outside the verifier. This is stated as a **reporting read**, with the same precedent as `signals.live` and `report.py`.

---

## 8. Build plan by owner

Ownership:
- **Backend:** `alibi/*.py` (not `pinch.py`), `tests/*`, the iOS data layer, `native/sense.swift`.
- **Design:** `alibi/web/**`, island views, `ios/AlibiPhone/Views/*`, `native/main.swift` and `Window.swift` (coordinate first), the design system.

Every task ends with `./alibi.sh test` green. New tests use `harness` and `check()` and are added to `tests/run_all.sh`.

### Tonight (T0), now until 21:30
| # | Owner | Task | Time | DoD |
|---|---|---|---|---|
| B0 | backend | F0: harness env, `prose=False` on request paths, timeouts, no-think, keyless gate, vision stays apple | 1 h | `test_llm_guard.py`; suite green with a fake key in the environment |
| B1 | backend | F2 pace v2, **only if B0 is green by 20:15** | 1 h | `test_pace3.py` (7 cases) |
| R0 | user + backend | Recording data: `cp habits.yaml data/demo/habits.yaml`, add schedules there, then `ALIBI_HABITS=data/demo/habits.yaml ./alibi.sh seed`. Run the demo daemon with the **same** `ALIBI_HABITS` and `ALIBI_DATA_DIR=data/demo`. Caption seeded charts "seeded". | 20 min | The Today timeline shows planned blocks |
| R1 | user | Record the safety cut from `docs/design/DEMO.md` (takes via `docs/design/demo/stage.py`), fully offline. Keep the live session, nudge and verdict **live** (not seeded). After recording: `./alibi.sh down`. | — | Clips in `demo/clips/` |

No UI, iOS or Spark work before recording.

### By submission (T1), in priority order (about 8–10 h total)
| # | Owner | Task | Time | DoD |
|---|---|---|---|---|
| B2 | backend | F5 digests: rules for morning, checkpoint and night, slots, `/api/digests*`, memory callback, Telegram routing | 2 h | `test_digest.py` (slots, suppression, memory) |
| B2b | backend | F5 replan: the tool loop against `LLM_BASE_URL`, validator, rules picker, `add_once`, accept route, trace | 2 h | `test_digest.py` (stub tool loop, fallback, accept) |
| B6 | backend | F6 `egress()` with a probe, `hourly()`, git copy | 1 h | `test_egress.py` |
| D1 | design | Health strip, digest card with confirm card and trace disclosure, egress block on `/signals` | 3 h | `?stage=digest-night` and `?stage=plan-mixed` snapshots; reduced motion checked |
| S1 | Spark | NEMOCLAW.md §3 step 1: raw model on the tailnet with tool calling | — | `curl` tool-call test passes from the Mac |
| B3 | backend | F7 minimal: phone `say` and `end`, guard, `op_id` lock | 1.5 h | `test_phone_writes.py` |
| B8 | backend | F8 Ask: worker, grounding facts, HEAD checks, probe | 2 h | `test_ask.py`; shown only if one real call passes |
| — | user | **Re-record** the agent beats (storyline below) once B2, B2b, D1 and S1 pass | 1 h | — |

### T1 stretch (only after the above)
- B4: habits `rev`, PATCH with CAS, flock.
- D2: inline edit with Undo.
- D3: iOS Say composer and End (after a backup build).
- D4: F9 window.
- B9: `/api/agent/*` REST for NemoClaw briefs.

### Booth (T2)
- Archive with `active_habits()`.
- Goals store and Gantt.
- Burn-ups, cone and grid.
- iOS tabs (Plan, Habits, Streams, Ask) and the CommandQueue.
- App Intents (`TellAlibiIntent`, `StartHabitIntent`).
- MCP read tools plus `post_brief`.
- NemoClaw cron.
- Push-to-talk.
- Widgets.
- Keychain/QR key provisioning.
- Goal drafting by the LLM (confirm card).

---

## 9. Demo storylines

### A. Tonight's safety cut — superseded: record from `docs/design/DEMO.md`. The table below is the old 75 s `demo/shotlist.md` cut, kept for reference
| s | Shot |
|---|---|
| 0–5 | Title: "Alibi only ticks a habit when your Mac and iPhone can prove it." |
| 5–12 | ⌥⌘A, the island drops from the notch, "drawing for 25". |
| 12–26 | Desk cam sees drawing. The phone is picked up and the nudge drops: "You said drawing. I've seen your phone for 3 minutes." |
| 26–38 | Verdict with contact sheet: claimed 25, seen 17. Relabel one sample, and it re-scores. |
| 38–48 | "learn C++ for 30 min": title breakdown (VS Code / cppreference vs YouTube). |
| 48–62 | This week: claimed vs seen bars plus the three dry sentences (rules). Health strip if B1 landed. Seeded data is captioned "seeded". |
| 62–70 | `/signals`: what is flowing; "Frames never leave the Mac (Apple Vision)", which is true in this config. |
| 70–75 | End card. |

### B. Re-record for submission (88 s; only if T1 lands and S1 is real)
| s | Beat | Uses | If missing |
|---|---|---|---|
| 0–6 | **Hook.** Health strip close-up: "Drawing: 40 min behind. 35 a day until Sunday." Caption: "I said I'd draw 3 hours this week. Alibi checks." | F2, D1 | Use the week bars |
| 6–14 | **Start.** Phone: "draw for 25". The Mac island goes live. | F7 (+ D3) | Island composer |
| 14–26 | **Witness.** Phone pickup, then the nudge. | existing | — |
| 26–36 | **Verdict with receipts.** Claimed 25, seen 17, "not counted, with reasons". | existing | — |
| 36–54 | **Agent.** "22:00", `POST /api/digests/run night`. The card shows the trace "week → plan tomorrow → free gaps → proposed 07:30" and "via spark". Tap Accept; tomorrow's plan shows the block. | F5 B2b, S1 | `via: rules` (still a valid beat; drop "agent" from the caption) |
| 54–62 | **Memory.** "07:30" morning brief: "Last night you moved drawing to 07:30. You showed up: 22 of 25 min. Today needs 25 min." | F5 memory | Must be real: a real 07:30 session tomorrow, or the fake clock captioned "simulated morning" |
| 62–72 | **Ask (only if real).** Dictate "tips for running". Stages show, then "1 of 3 runs. Free 30 min tomorrow 07:00" plus 3 checked links, tagged "via nemoclaw". | F8 | Drop it; give the time to 72–82 |
| 72–82 | **Kill the Spark.** Stop vLLM. The `/signals` egress row flips to "stays on Mac". Run a checkpoint: it arrives, `via: rules`. Caption: "Offline-first. Nothing breaks." | F6, F5 | — |
| 82–88 | **End card.** "Alibi: no tick without proof. Mac + iPhone evidence, an agent on DGX Spark." | — | — |

Rule for B: no on-screen "NemoClaw" unless `via:"nemoclaw"` really appears.

---

## 10. Risks (ranked) and cut order

| # | Risk | Mitigation |
|---|---|---|
| 1 | **No agent in the video.** The Spark serves nothing yet, and tonight is the only recording. | Record the safety cut tonight. Re-record tomorrow with the F5 tool loop (needs only a raw model with tool calling, not OpenClaw config). Everything has a `rules` path. |
| 2 | **Spark tool calling or latency fails** (a reasoning model burns tokens, a parser isn't enabled, more than 45 s) | No-think, a 45 s budget, a validator, and the rules picker. The beat survives as `via: rules`. Test with the stub plus one real `curl`. |
| 3 | **Tests or the daemon hit the network** once `.env` gets a URL (harness gap; request-path LLM calls; daemon tick) | B0 first: harness env plus `prose=False` on every request path. |
| 4 | **Camera frames leak** under the keyless gate | Vision stays `apple` unless set explicitly (B0, tested). |
| 5 | **Phone writes on cleartext LAN** `:8766` | Writes are tailnet or loopback only, header only, `op_id` with a lock. The phone uses its tailnet endpoint first for writes. |
| 6 | **Empty plan or thin history in the video** | Seed with an `ALIBI_HABITS` copy that has schedules (R0). Caption "seeded". Keep the live beats live. Goals ETAs are T2. |
| 7 | **Strava not connected.** Running reads off or "can't see". | Either connect it (D4) or keep running off screen. The stale rule shows "Can't see" honestly. |
| 8 | **Carry-to-tomorrow isn't supported** (`move` is same-day only) | `add_once` (0.5 h), or fall back to moving tomorrow's scheduled key. |
| 9 | **Session collisions** (`main.swift`, `integrations.py`) | `routes_phone.py` and `digest.py` are new files. SendMessage before touching the other session's files. Never SendMessage a running workflow lane. |
| 10 | **iOS rebuild bricks the demo phone** | No iOS changes before submission unless a backup build exists; iOS is T1s. |

**Cut order if behind** (first to go → last):
1. F9 window.
2. F1 inline edit.
3. iOS composer.
4. F8 Ask.
5. B3 phone say.
6. Egress scope chips (keep the table).
7. Telegram routing.

**Never cut:** F0, the F5 rules digests plus memory, the replan card (even `via: rules`), the health strip, the kill-the-Spark beat, and tonight's safety recording.

---

## 11. Decisions the user must make (short)

1. **D1. Re-record tomorrow morning?** Yes means the agent beat goes in the video; no means T1 is for the description or link and the booth only.
2. **D2. Recording data tonight.** Seed a habits copy with schedules (recommended; captioned "seeded"), or add real `schedule:` entries to `habits.yaml` now?
3. **D3. Spark model.** Which model and server is the Spark session standing up (Qwen on vLLM `:8000`, or Nemotron on Ollama `:11434`), and does it have tool calling enabled? Nemotron reads better for the challenge if it's fast enough.
4. **D4. Strava.** Connect it before recording, or keep running off screen?
5. **D5. Mac `tailscale serve`.** May Alibi's `:8766` be fronted by `tailscale serve` (HTTPS on the tailnet)? It's needed for MCP (T2) and makes phone writes safer. This is a Mac network config change, so it's your call.
