#!/usr/bin/env python3
"""Stand-in for bin/alibi-sense. Reads its answer from $FAKE_SENSE_STATE (JSON) so tests can change the 'Mac'.
  state = {"snap": {...alibi-sense output...}, "installed": {bundle id: name}, "calls": n}"""
import json, os, sys

path = os.environ["FAKE_SENSE_STATE"]
st = json.load(open(path))
st["calls"] = st.get("calls", 0) + 1
st.setdefault("argv", []).append(sys.argv[1:])
json.dump(st, open(path, "w"))
if st.get("crash"):
    sys.exit(3)
if sys.argv[1:2] == ["--installed"]:
    print(json.dumps({i: st.get("installed", {}).get(i) for i in sys.argv[2:]}))
else:
    print(json.dumps(st.get("snap", {})))
