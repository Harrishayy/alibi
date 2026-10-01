#!/usr/bin/env bash
# Copy the SwiftUI files shared with the island (native/shared/*.swift) into the iPhone app.
# native/shared/ is the source of truth; ios/AlibiPhone/Views/Shared/ holds copies (see native/shared/README.md).
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=ios/AlibiPhone/Views/Shared
mkdir -p "$DEST"
n=0
for f in native/shared/*.swift; do
  [ -e "$f" ] || continue
  cp "$f" "$DEST/"
  n=$((n + 1))
done
echo "Synced $n file(s) from native/shared to $DEST"
