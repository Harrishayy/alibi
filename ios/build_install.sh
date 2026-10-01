#!/usr/bin/env bash
# Build the Alibi iPhone companion and install it over USB.
#   bash ios/build_install.sh            (iPhone connected + unlocked, Alibi running with phone sync on)
#   BUILD_ONLY=1 bash ios/build_install.sh   (compile + sign only; nothing touches the phone)
# Bakes this Mac's addresses + the phone key (from data/secrets.json via the running API) into the app.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"
PORT="${API_PORT:-8765}"

mkdir -p Generated
curl -s "localhost:$PORT/api/phone-sync" | "$ROOT/.venv/bin/python" -c '
import json, plistlib, subprocess, sys
d = json.load(sys.stdin)
if not d.get("secret"):
    sys.exit("Phone sync is off. Turn it on in Alibi (Setup → iPhone) first.")
eps = [u["ingest_url"] for u in d["urls"]]
name = subprocess.run(["scutil", "--get", "ComputerName"], capture_output=True, text=True).stdout.strip()
plistlib.dump({"endpoints": eps, "key": d["secret"], "mac_name": name or "your Mac"}, open("Generated/AlibiConfig.plist", "wb"))
print("endpoints:", *eps, sep="\n  ")'

lockf -k /tmp/alibi-ios.lock xcodegen generate --quiet
if [ -n "${BUILD_ONLY:-}" ]; then
  lockf -k /tmp/alibi-ios.lock xcodebuild -project AlibiPhone.xcodeproj -scheme AlibiPhone -configuration Debug -destination "generic/platform=iOS" \
    -derivedDataPath build -allowProvisioningUpdates -quiet build
  echo "Built build/Build/Products/Debug-iphoneos/AlibiPhone.app (not installed)."; exit 0
fi
DEVICE="${DEVICE:-$(xcrun devicectl list devices 2>/dev/null | awk '/available \(paired\)/ && /iPhone/ {print $3; exit}')}"
[ -n "$DEVICE" ] || { echo "No paired iPhone found. Connect it with USB and unlock it."; exit 1; }
lockf -k /tmp/alibi-ios.lock xcodebuild -project AlibiPhone.xcodeproj -scheme AlibiPhone -configuration Debug -destination "generic/platform=iOS" \
  -derivedDataPath build -allowProvisioningUpdates -quiet build
APP=build/Build/Products/Debug-iphoneos/AlibiPhone.app
xcrun devicectl device install app --device "$DEVICE" "$APP"
xcrun devicectl device process launch --device "$DEVICE" app.theultras.alibi || echo "Installed. Unlock the phone and open Alibi."
