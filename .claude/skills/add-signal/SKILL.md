---
name: add-signal
description: Add a new evidence source to Alibi (an observer that writes events, e.g. a new Mac, phone or web signal) following the signals contract, without changing the DB schema. Use when the user wants Alibi to "see", "track" or "use" a new kind of evidence.
---

# Add a signal

The contract is `docs/SIGNALS.md`. Every data point is an `events` row (`source`, `kind`, `payload` JSON, `ts`).
**No SQL schema change**: `alibi/db.py` is frozen, so ask before touching it.

## Steps

1. **Contract first.** Add a row to the right table in `docs/SIGNALS.md`: `source | kind | payload | notes`.
   Prefer an existing `source` (`mac`, `phone`, `health`, `laptop`, …). Payload keys are snake_case with units in the
   name (`idle_s`, `distance_km`). Privacy: counts and states only, never message text, coordinates or raw content.
2. **Writer** (observer) only writes, via `db.add_event(con, source, kind, payload, ts=...)`. Pass `ts`; the store
   decides `session_id`. Mac signals go in `alibi/mac_signals.py` (native reads in `native/sense.swift`).
   Phone signals arrive through `POST /ingest` on :8766 (`X-Alibi-Secret`), in batches of ≤ 500 rows.
3. **Reader**: only the verifier side reads events. Add the mapping to `alibi/signals.py` `timeline()` with a
   `verdict_hint` (`on_task | off_task | absent | neutral`) and a short human `text`.
   Rule: signals may *lower* a score with a stated reason; they never *raise* one on their own.
4. **Offline and permission-safe**: no new permission prompts at startup and no network dependency. If the source is
   unavailable, write nothing and don't crash.
5. **Test**: extend `tests/test_signals.py`, or add a test that starts with `from harness import ...` (use
   `tests/fake_sense.py` / `tests/seed_signals.py` for fake inputs). Real Mac signals stay off in tests
   (`MAC_SIGNALS=0`). Then run the `verify` skill.
6. If the iPhone sends it, keep `ios/Shared` and `ios/AlibiPhone/Sync` payloads matching the doc;
   `tests/test_ios_contract.py` checks this.
