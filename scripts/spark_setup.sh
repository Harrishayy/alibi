#!/usr/bin/env bash
# DGX Spark side of Alibi: relay service + NemoClaw sandbox wiring. Idempotent; rerun after any change.
#   bash scripts/spark_setup.sh [sandbox-name]       (default: alibi)
# Needs: NemoClaw installed and the sandbox onboarded (curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash).
# Secrets stay in .env (git-ignored) and are never printed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
SB="${1:-alibi}"
PORT="${RELAY_PORT:-8770}"
NC="${NEMOCLAW:-$HOME/.local/bin/nemoclaw}"
dk() { if docker info >/dev/null 2>&1; then docker "$@"; else sg docker -c "docker $(printf '%q ' "$@")"; fi; }

[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
touch .env
setkey() { grep -q "^$1=" .env || { echo "$1=$2" >> .env; echo "  .env: added $1"; }; }
setkey MAC_URL "http://${MAC_HOST:-harrishs-macbook-pro}:8765"
setkey ALIBI_REMOTE_TOKEN "$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(24))')"
setkey RELAY_TOKEN "$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(24))')"
setkey RELAY_PORT "$PORT"

# 1. relay as a user service (survives logout if lingering is on)
GW="$(dk network inspect openshell-docker -f '{{(index .IPAM.Config 0).Gateway}}' 2>/dev/null || true)"
[ -n "$GW" ] || { echo "No openshell-docker network yet. Finish 'nemoclaw onboard' first."; exit 1; }
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/alibi-relay.service <<EOF
[Unit]
Description=Alibi relay (NemoClaw sandbox <-> Mac over Tailscale)
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
for _ in $(seq 20); do curl -s -m 1 "http://$GW:$PORT/status" >/dev/null && break; sleep 0.5; done
echo "relay:   http://$GW:$PORT  ->  $(curl -s -m 2 "http://$GW:$PORT/status")"

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

echo
echo "Sandbox check (should print mac_online):"
"$NC" "$SB" exec -- curl -s -m 5 "http://$GW:$PORT/status" || true
echo
echo "On the Mac, add to .env (copy ALIBI_REMOTE_TOKEN from this Spark's .env), then ./alibi.sh down && ./alibi.sh up:"
echo "  API_HOST=0.0.0.0"
echo "  ALIBI_REMOTE_TOKEN=<same value as the Spark>"
echo "  ALIBI_ALLOWED_HOSTS=127.0.0.1,localhost,::1,$(echo "${MAC_HOST:-harrishs-macbook-pro}"),100.66.226.12"
