#!/usr/bin/env bash
# Run on the Spark from this folder: installs the keep-alive and starts its timer. Needs `loginctl enable-linger $USER`
# (done by scripts/spark_setup.sh) so user services run without a login.
set -euo pipefail
cd "$(dirname "$0")"
install -m 755 alibi-keepalive "$HOME/.local/bin/alibi-keepalive"
mkdir -p "$HOME/.config/systemd/user"
install -m 644 alibi-keepalive.service alibi-keepalive.timer "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now alibi-keepalive.timer
systemctl --user start alibi-keepalive.service
systemctl --user list-timers alibi-keepalive.timer --no-pager
