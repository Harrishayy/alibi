#!/usr/bin/env bash
# Push the agent's instructions from this checkout to the NemoClaw sandbox on the DGX Spark: the `alibi` skill, the
# heartbeat checklist and the brief jobs' messages and times (spark/briefs.json). Run on the Mac after editing spark/.
#   bash spark/deploy_skill.sh [--dry-run] [sandbox-name]      (default sandbox: alibi)
#   SPARK_HOST=spark [SPARK_USER=name]                         (an ssh host; SPARK_HOST may also be user@host)
# Idempotent: the skill and heartbeat are installed only when they differ from the sandbox's copies, and a cron job is
# edited only when its message or schedule differs, so a rerun changes nothing. Same nemoclaw/openclaw commands as
# scripts/spark_setup.sh, minus the relay service, .env and egress policy (run that for a first install). Files go to a
# temp dir on the Spark, never into its checkout; no secret is read or printed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY=0; SB=alibi
for a in "$@"; do                     # any order: a misplaced --dry-run must never turn into a real deploy
  case "$a" in
    --dry-run|-n) DRY=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    -*) echo "Unknown option: $a (try --help)"; exit 1 ;;
    *) SB="$a" ;;
  esac
done
[[ "$SB" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "Bad sandbox name: $SB"; exit 1; }
HOST="${SPARK_HOST:-spark}"
[[ "$HOST" == *@* || -z "${SPARK_USER:-}" ]] || HOST="$SPARK_USER@$HOST"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3

# 1. check the files here first, so a typo never reaches the agent
"$PY" - "$ROOT/spark" <<'PY'
import json, pathlib, re, sys
d = pathlib.Path(sys.argv[1])
try:
    jobs = json.loads((d / "briefs.json").read_text())
except ValueError as e:
    sys.exit(f"spark/briefs.json isn't JSON: {e}")
keys = [j.get("key") for j in jobs] if isinstance(jobs, list) else []
if not keys or len(set(keys)) != len(keys) or not all(isinstance(k, str) and k.startswith("alibi-") for k in keys):
    sys.exit(f"spark/briefs.json: job keys must be unique and start with alibi- (got {keys})")
for j in jobs:
    if not str(j.get("cron") or "").strip() or not str(j.get("message") or "").strip():
        sys.exit(f"spark/briefs.json: {j['key']} needs a cron and a message")
skill = (d / "skills/alibi/SKILL.md").read_text()
if not re.match(r'---\s*\nname:\s*"?alibi"?\s*\n', skill) or "{{RELAY_URL}}" not in skill:
    sys.exit("spark/skills/alibi/SKILL.md: expected the alibi front matter and the {{RELAY_URL}} placeholder")
PY

# 2. stage the skill, the heartbeat, the jobs and the Spark-side script; ship them in one ssh call
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/alibi-skill.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$ROOT/spark/skills/alibi" "$STAGE/alibi"
cp "$ROOT/spark/HEARTBEAT.md" "$ROOT/spark/briefs.json" "$STAGE/"
cat > "$STAGE/remote.sh" <<'REMOTE'
#!/usr/bin/env bash
# Runs on the Spark from the temp dir deploy_skill.sh unpacked, and removes it on exit.
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
case "$D" in /tmp/alibi-skill.*) trap 'rm -rf "$D"' EXIT ;; esac
SB="$1"; DRY="${2:-0}"
export PATH="$HOME/.local/bin:$PATH"
NC="${NEMOCLAW:-$HOME/.local/bin/nemoclaw}"
WS=/sandbox/.openclaw/workspace
die() { echo "  !! $*" >&2; exit 1; }
dk() { if docker info >/dev/null 2>&1; then docker "$@"; else sg docker -c "docker $(printf '%q ' "$@")"; fi; }
nemo() { "$NC" "$SB" "$@" </dev/null; }
quiet() { "$@" >/dev/null 2>"$D/err" || { cat "$D/err" >&2; return 1; }; }   # nemoclaw's chatter only on failure

# The relay URL as scripts/spark_setup.sh renders it: the sandbox's Docker bridge gateway + the relay's RELAY_PORT.
GW="$(dk network inspect openshell-docker -f '{{(index .IPAM.Config 0).Gateway}}' 2>/dev/null || true)"
[ -n "$GW" ] || die "No openshell-docker network. Finish 'nemoclaw onboard' and scripts/spark_setup.sh first."
REPO="$(systemctl --user show alibi-relay -p WorkingDirectory --value 2>/dev/null || true)"
PORT="$(sed -n 's/^RELAY_PORT=//p' "${REPO:-.}/.env" 2>/dev/null | tail -n 1 | tr -d "\"' \r" || true)"
[[ "$PORT" =~ ^[0-9]+$ ]] || PORT=8770
URL="http://$GW:$PORT"

# A skill pointing at a relay the sandbox can't reach is worse than the old one: check before changing anything.
code="$(nemo exec --timeout 60 -- curl -s -m 5 -o /dev/null -w '%{http_code}' "$URL/status" 2>/dev/null || true)"
[[ "$code" == *200 ]] || die "The sandbox can't reach the relay at $URL (HTTP ${code:-none}). Check: systemctl --user status alibi-relay"
echo "  relay: $URL answers from the sandbox"

for f in "$D/alibi/SKILL.md" "$D/HEARTBEAT.md"; do sed "s#{{RELAY_URL}}#$URL#g" "$f" > "$f.new" && mv "$f.new" "$f"; done
if grep -qE '\{\{[A-Z_]+\}\}' "$D/alibi/SKILL.md" "$D/HEARTBEAT.md"; then die "A {{PLACEHOLDER}} is left after rendering."; fi

# Install only what differs from the sandbox's copy, then read it back.
same() { nemo exec --timeout 60 -- cat "$2" 2>/dev/null | cmp -s - "$1"; }
if same "$D/alibi/SKILL.md" "$WS/skills/alibi/SKILL.md"; then
  echo "  skill: unchanged"
elif [ "$DRY" = 1 ]; then
  echo "  skill: differs (dry run: not installed)"
else
  quiet nemo skill install "$D/alibi" || die "nemoclaw $SB skill install failed."
  same "$D/alibi/SKILL.md" "$WS/skills/alibi/SKILL.md" \
    || die "Installed, but $WS/skills/alibi/SKILL.md doesn't match. Look at: nemoclaw $SB skill list"
  echo "  skill: installed"
fi
if same "$D/HEARTBEAT.md" "$WS/HEARTBEAT.md"; then
  echo "  heartbeat: unchanged"
elif [ "$DRY" = 1 ]; then
  echo "  heartbeat: differs (dry run: not uploaded)"
else
  quiet nemo upload "$D/HEARTBEAT.md" "$WS/HEARTBEAT.md" || die "nemoclaw $SB upload failed."
  echo "  heartbeat: uploaded"
fi
[ "$DRY" = 1 ] || quiet nemo exec --timeout 60 -- mkdir -p "$WS/memory" || die "Couldn't create $WS/memory."

# Brief jobs: patch message and schedule in place; add a missing one with scripts/spark_setup.sh's flags.
python3 -u - "$NC" "$SB" "$D/briefs.json" "$DRY" <<'PY'
import json, subprocess, sys
nc, sb, path, dry = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
TZ = "Europe/London"
ADD = ["--tz", TZ, "--exact", "--agent", "main", "--session", "isolated", "--no-deliver",
       "--timeout-seconds", "240", "--tools", "exec,read,write"]


def cron(*args) -> str:
    r = subprocess.run([nc, sb, "exec", "--timeout", "90", "--", "openclaw", "cron", *args],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True)
    if r.returncode:
        tail = " / ".join((r.stderr or r.stdout).strip().splitlines()[-3:])
        sys.exit(f"  !! openclaw cron {args[0]} failed: {tail}\n     If it asks for a scope, approve it with "
                 f"'nemoclaw {sb} exec -- openclaw devices approve <requestId>' and rerun.")
    return r.stdout


def jobs() -> dict:
    out = cron("list", "--all", "--json")
    try:
        data = json.JSONDecoder().raw_decode(out, out.index("{"))[0]
    except ValueError:
        sys.exit("  !! openclaw cron list --json didn't print JSON")
    found = {}
    for j in data.get("jobs") or []:
        found.setdefault(j.get("declarationKey") or j.get("name"), j)
    return found


want, have = json.load(open(path)), jobs()
for w in want:
    j = have.get(w["key"])
    sched = (j or {}).get("schedule") or {}
    if j is None:
        what = "missing (dry run: not added)" if dry else "added"
        if not dry:
            cron("add", "--name", w["key"], "--declaration-key", w["key"], "--cron", w["cron"], *ADD,
                 "--message", w["message"])
    elif ((j.get("payload") or {}).get("message"), sched.get("expr"), sched.get("tz")) == (w["message"], w["cron"], TZ):
        what = "unchanged"
    else:
        what = "differs (dry run: not edited)" if dry else "updated"
        if not dry:
            cron("edit", j["id"], "--cron", w["cron"], "--tz", TZ, "--exact", "--message", w["message"])
    print(f"  {w['key']}: {what}" + (" (disabled, left that way)" if j and j.get("enabled") is False else ""))

if not dry:
    have = jobs()
    old = [w["key"] for w in want if ((have.get(w["key"]) or {}).get("payload") or {}).get("message") != w["message"]]
    if old:
        sys.exit("  !! not on the new message after the change: " + ", ".join(old))
print(f"  night job id: {(have.get('alibi-night') or {}).get('id')}")
PY

# Does the Mac already send focus numbers? Read-only, through the relay on this host.
python3 - "http://127.0.0.1:$PORT/context" <<'PY' || true
import json, sys, urllib.request
try:
    ctx = json.load(urllib.request.urlopen(sys.argv[1], timeout=15))
except Exception as e:
    sys.exit(f"  Mac context: not readable right now ({type(e).__name__})")
f = ctx.get("focus")
note = " (last copy; the Mac is offline)" if ctx.get("stale") else ""
if isinstance(f, dict) and f.get("today_so_far") is not None:
    print("  Mac context: focus numbers present" + note)
else:
    print("  Mac context: no focus numbers yet" + note + ". Briefs leave the phone out until Alibi on the Mac sends them.")
PY
REMOTE

TARX=(--exclude .DS_Store --exclude '._*')
if tar --version 2>/dev/null | grep -q bsdtar; then TARX+=(--no-xattrs --no-mac-metadata); fi   # no macOS metadata
echo "Alibi skill -> sandbox $SB on $HOST$([ "$DRY" = 1 ] && echo ' (dry run)')"
COPYFILE_DISABLE=1 tar -c -f - "${TARX[@]}" -C "$STAGE" alibi HEARTBEAT.md briefs.json remote.sh \
  | ssh -o ConnectTimeout=10 "$HOST" \
      'd="$(mktemp -d /tmp/alibi-skill.XXXXXX)" && tar -xmf - -C "$d" && bash "$d/remote.sh" '"$SB $DRY"
[ "$DRY" = 1 ] && exit 0
echo "Done. Each cron run starts a fresh session, so the next one reads the new skill. To try the night brief now"
echo "(it posts tonight's slot, and the 22:05 run then gets that copy back):"
echo "  ssh $HOST '~/.local/bin/nemoclaw $SB exec -- openclaw cron run <night job id>'"
