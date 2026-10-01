#!/usr/bin/env bash
# Build the on-device witness (Apple Vision) and the notch island (SwiftUI). macOS only.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p bin
swiftc -O native/witness.swift -o bin/alibi-witness
swiftc -O native/Island.swift -o bin/alibi-island
# Presence/meeting/media/Focus snapshot for alibi/mac_signals.py. Permission-free reads; never prompts.
swiftc -O native/sense.swift -o bin/alibi-sense
# Calendar helper: a command-line tool needs its usage strings embedded, or macOS refuses (or kills) the request.
CAL_PLIST=$(mktemp -t alibi-calendar-plist)
cat > "$CAL_PLIST" <<CALPLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>dev.alibi.calendar</string>
  <key>CFBundleName</key><string>Alibi</string>
  <key>NSCalendarsFullAccessUsageDescription</key><string>Alibi puts your planned habit sessions in a calendar called “Alibi”, then marks each one with what actually happened. It never reads or changes your other calendars.</string>
  <key>NSCalendarsUsageDescription</key><string>Alibi puts your planned habit sessions in a calendar called “Alibi”, then marks each one with what actually happened.</string>
</dict></plist>
CALPLIST
swiftc -O native/calendar.swift -o bin/alibi-calendar -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker "$CAL_PLIST"
rm -f "$CAL_PLIST"
echo "Built bin/alibi-witness, bin/alibi-island, bin/alibi-sense and bin/alibi-calendar"

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
  <key>NSCalendarsFullAccessUsageDescription</key><string>Alibi puts your planned habit sessions in a calendar called “Alibi”, then marks each one with what actually happened. It never reads or changes your other calendars.</string>
  <key>NSCalendarsUsageDescription</key><string>Alibi puts your planned habit sessions in a calendar called “Alibi”, then marks each one with what actually happened.</string>
</dict></plist>
PLIST
mkdir -p $APP/Contents/Resources
cp bin/alibi-island $APP/Contents/MacOS/Alibi
cp bin/alibi-calendar $APP/Contents/MacOS/alibi-calendar   # calendar_sync prefers this copy: access belongs to "Alibi"
cp bin/alibi-sense $APP/Contents/MacOS/alibi-sense         # mac_signals prefers this copy (Full Disk Access → "Alibi")
echo "$PWD" > $APP/Contents/Resources/root.txt
codesign --force -s - $APP >/dev/null 2>&1 || true
echo "Built $APP (double-click it, or ./alibi.sh up)"
