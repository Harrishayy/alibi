#!/usr/bin/env bash
# Build the on-device witness (Apple Vision) and the notch island (SwiftUI). macOS only.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p bin
swiftc -O native/witness.swift -o bin/alibi-witness
swiftc -O native/Island.swift -o bin/alibi-island
echo "Built bin/alibi-witness and bin/alibi-island"

# Alibi.app — permissions (Camera, Accessibility) belong to "Alibi", and it can sit in Login Items.
APP=Alibi.app
rm -rf $APP && mkdir -p $APP/Contents/MacOS
cat > $APP/Contents/Info.plist <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Alibi</string>
  <key>CFBundleIdentifier</key><string>dev.alibi.app</string>
  <key>CFBundleExecutable</key><string>Alibi</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.7</string>
  <key>LSUIElement</key><true/>
  <key>NSCameraUsageDescription</key><string>Alibi samples your desk once a minute during a declared session to check your alibi.</string>
  <key>NSAppleEventsUsageDescription</key><string>Alibi reads the frontmost window title to verify digital sessions.</string>
</dict></plist>
PLIST
mkdir -p $APP/Contents/Resources
cp bin/alibi-island $APP/Contents/MacOS/Alibi
echo "$PWD" > $APP/Contents/Resources/root.txt
codesign --force -s - $APP >/dev/null 2>&1 || true
echo "Built $APP (double-click it, or ./alibi.sh up)"
