#!/usr/bin/env bash
# DGX Spark side of Alibi (docs/SPARK.md, contract docs/NEMOCLAW.md): relay service + NemoClaw sandbox wiring.
# Idempotent; rerun after any change to spark/ or the relay.
#   bash scripts/spark_setup.sh [sandbox-name]       (default: alibi)
# Needs: the sandbox onboarded, and ALIBI_AGENT_TOKEN in .env (the Mac's `nemoclaw_token` from its data/secrets.json,
# handed over out of band). Secrets stay in .env (git-ignored) and are never printed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
SB="${1:-alibi}"
PORT="${RELAY_PORT:-8770}"
NC="${NEMOCLAW:-$HOME/.local/bin/nemoclaw}"
dk() { if docker info >/dev/null 2>&1; then docker "$@"; else sg docker -c "docker $(printf '%q ' "$@")"; fi; }

[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
touch .env && chmod 600 .env
setkey() { grep -q "^$1=" .env || { echo "$1=$2" >> .env; echo "  .env: added $1"; }; }
setkey MAC_URL "http://${MAC_HOST:-100.66.226.12}:8766"
setkey RELAY_PORT "$PORT"
grep -q '^ALIBI_AGENT_TOKEN=.\+' .env || echo "  !! ALIBI_AGENT_TOKEN missing: copy nemoclaw_token from the Mac's data/secrets.json into this .env"

# 1. relay as a user service (survives logout if lingering is on)
GW="$(dk network inspect openshell-docker -f '{{(index .IPAM.Config 0).Gateway}}' 2>/dev/null || true)"
[ -n "$GW" ] || { echo "No openshell-docker network yet. Finish 'nemoclaw onboard' first."; exit 1; }
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/alibi-relay.service <<EOF
[Unit]
Description=Alibi relay (NemoClaw sandbox <-> Mac agent API over Tailscale)
After=network-online.target

[Service]
WorkingDirectory=$ROOT
ExecStart=$ROOT/.venv/bin/python -m alibi.relay
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now alibi-relay.service
systemctl --user restart alibi-relay.service
loginctl enable-linger "$USER" 2>/dev/null || echo "  (run 'sudo loginctl enable-linger $USER' so the relay runs while logged out)"
sleep 2

# 2. render the skill, heartbeat and policy with the bridge address
OUT="$(mktemp -d)"; trap 'rm -rf "$OUT"' EXIT
cp -r spark/skills/alibi "$OUT/alibi"
sed -i "s#{{RELAY_URL}}#http://$GW:$PORT#g" "$OUT/alibi/SKILL.md"
sed "s#{{RELAY_URL}}#http://$GW:$PORT#g" spark/HEARTBEAT.md > "$OUT/HEARTBEAT.md"
sed -e "s#{{RELAY_HOST}}#$GW#" -e "s#{{RELAY_PORT}}#$PORT#" spark/policy-alibi-relay.yaml > "$OUT/policy.yaml"

# 3. sandbox: egress to the relay only, the skill, the heartbeat checklist
"$NC" "$SB" policy add --from-file "$OUT/policy.yaml" --trusted-private-host "$GW" --yes 2>/dev/null \
  || "$NC" "$SB" policy add --from-file "$OUT/policy.yaml" --trusted-private-host "$GW"
"$NC" "$SB" skill install "$OUT/alibi"
"$NC" "$SB" upload "$OUT/HEARTBEAT.md" /sandbox/.openclaw/workspace/HEARTBEAT.md
"$NC" "$SB" exec -- mkdir -p /sandbox/.openclaw/workspace/memory

# 4. brief jobs on OpenClaw cron (docs/NEMOCLAW.md §6), offset after Alibi's own slots; declaration keys keep reruns idempotent
.venv/bin/python - "$NC" "$SB" <<'PY'
import json, subprocess, sys
nc, sb = sys.argv[1], sys.argv[2]
for j in json.load(open("spark/briefs.json")):
    subprocess.run([nc, sb, "exec", "--", "openclaw", "cron", "add", "--name", j["key"], "--declaration-key", j["key"],
                    "--cron", j["cron"], "--tz", "Europe/London", "--exact", "--agent", "main", "--session", "isolated",
                    "--no-deliver", "--timeout-seconds", "240", "--tools", "exec,read,write", "--message", j["message"]],
                   check=False, stdout=subprocess.DEVNULL)
PY
"$NC" "$SB" exec -- openclaw cron list 2>/dev/null | grep -E "alibi-|Name" || true

echo
echo "Sandbox check (should print mac_online):"
"$NC" "$SB" exec -- curl -s -m 5 "http://$GW:$PORT/status" || true
echo
