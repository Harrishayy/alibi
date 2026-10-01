#!/usr/bin/env python3
"""Stand-in for bin/alibi-calendar: same commands, same JSON, but the "calendar" is a JSON file. Never touches EventKit.

  ALIBI_CALENDAR_BIN=tests/fake_calendar.py  FAKE_CALENDAR_STATE=/tmp/x.json
  FAKE_CALENDAR_AUTH=not_determined|full|denied|write_only   (initial permission; `request` grants unless DENY=1)
  FAKE_CALENDAR_DENY=1     the person clicks "Don't Allow"
  FAKE_CALENDAR_FAIL=apply a command that answers {"error": "..."} (simulates a flaky helper)
Every call is appended to state["calls"] so tests can assert exactly what Alibi asked for.
"""
import json, os, sys, time, uuid

PATH = os.environ.get("FAKE_CALENDAR_STATE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fake_calendar.json")


def load():
    try:
        with open(PATH) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {"auth": os.environ.get("FAKE_CALENDAR_AUTH", "not_determined"), "calendars": {}, "events": {},
                "calls": []}


def save(st):
    tmp = PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=1)
    os.replace(tmp, PATH)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    inp = json.loads(raw) if raw.strip() else {}
    st = load()
    st["calls"].append({"cmd": cmd, "input": inp, "ts": time.time()})
    out = None
    if os.environ.get("FAKE_CALENDAR_FAIL") == cmd:
        out = {"error": f"fake {cmd} failure"}
    elif cmd == "status":
        cal = next((c for c in st["calendars"].values() if c["title"] == "Alibi"), None) if st["auth"] == "full" else None
        out = {"auth": st["auth"], "calendar": cal}
    elif cmd == "request":
        if st["auth"] in ("not_determined", "write_only"):
            st["auth"] = "denied" if os.environ.get("FAKE_CALENDAR_DENY") == "1" else "full"
        out = {"auth": st["auth"], "granted": st["auth"] == "full"}
    elif st["auth"] != "full":
        out = {"error": "no_access"}
    elif cmd == "ensure":
        title = inp.get("title", "Alibi")
        cal = st["calendars"].get(inp.get("id") or "") or next(
            (c for c in st["calendars"].values() if c["title"] == title), None)
        if cal:
            out = {**cal, "created": False}
        else:
            cal = {"id": "cal-" + uuid.uuid4().hex[:8], "title": title, "source": "iCloud"}
            st["calendars"][cal["id"]] = cal
            out = {**cal, "created": True}
    elif cmd == "list":
        cid = inp.get("calendar_id")
        if cid not in st["calendars"]:
            out = {"error": "no_calendar"}
        else:
            t0, t1 = inp.get("from", 0), inp.get("to", 1e12)
            evs = [e for e in st["events"].values() if e["calendar_id"] == cid and e["end"] > t0 and e["start"] < t1]
            out = {"calendar_id": cid, "events": sorted(evs, key=lambda e: e["start"])}
    elif cmd == "apply":
        cid = inp.get("calendar_id")
        if cid not in st["calendars"]:
            out = {"error": "no_calendar"}
        else:
            res = []
            for op in inp.get("ops", []):
                eid = op.get("id")
                if op.get("op") == "delete":
                    st["events"].pop(eid, None)
                    res.append({"ref": op.get("ref", ""), "id": eid or "", "ok": True})
                    continue
                ev = st["events"].get(eid) if eid else None
                if ev is None or ev["calendar_id"] != cid:
                    ev = {"id": "ev-" + uuid.uuid4().hex[:10], "calendar_id": cid, "title": "", "start": 0, "end": 0,
                          "notes": "", "url": ""}
                for k in ("title", "start", "end", "notes", "url"):
                    if k in op:
                        ev[k] = op[k]
                st["events"][ev["id"]] = ev
                res.append({"ref": op.get("ref", ""), "id": ev["id"], "ok": True})
            out = {"results": res}
    else:
        print(json.dumps({"error": f"unknown command {cmd}"}))
        save(st)
        sys.exit(2)
    save(st)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
