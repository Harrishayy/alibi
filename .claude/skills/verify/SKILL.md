---
name: verify
description: Run Alibi's hermetic test suite (every prototype's Definition of Done) and diagnose failures. Use before claiming any change, fix or prototype is done, after editing anything in alibi/, tests/, habits.yaml or native/, and when the user asks "does it work" or "run the tests".
---

# Verify

"Code written" is not done. Done = the DoD command prints the expected output.

## Steps

1. Make sure the venv exists: `test -x .venv/bin/python || bash scripts/setup.sh`.
2. Run the full suite (~15 s, no keys, no camera, temp data dir + fake clock):
   ```bash
   ./alibi.sh test
   ```
   Each line is `test_name  <last line of output>`. On the first failure the script prints `FAILED` and the whole
   log, then stops.
3. Iterate on one test while fixing: `.venv/bin/python tests/test_pN.py` (full log also in `/tmp/alibi_test_pN.log`).
4. If you changed Swift under `native/`, also run the `native-build` skill.
5. Report honestly: paste the summary lines. If something fails and you can't fix it, say which test, the `FAIL`
   line, and what you tried. Never weaken an assertion just to get green; ask first.

## Reading failures

- `FAIL <message>` lines come from `harness.check()`; the message names the expectation.
- Import errors usually mean a new module or dependency: add it to `requirements.txt` and re-run `scripts/setup.sh`.
- Time-related flakes: code cached "now" at import, or used `datetime.now()`/`time.monotonic()` where the harness
  only patches `time.time()`. Read time at call time via `time.time()`.
- Anything reading `data/…` directly instead of `alibi.config` paths will leak into real data. Fix the path.

## Writing a new test

```python
from harness import Clock, check        # sets ALIBI_DATA_DIR/ALIBI_HABITS to temp copies, mock witness
...
check(cond, "what should be true")
print("test_x: all pass")               # last line = the summary run_all.sh shows
```
Then add the test name to the list in `tests/run_all.sh`. Tests must never touch the real `data/`, the real
camera, the user's Shortcuts or the network.
