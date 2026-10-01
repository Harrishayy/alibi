#!/usr/bin/env bash
# Build the on-device witness (Apple Vision) and the notch island (SwiftUI). macOS only.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p bin
swiftc -O native/witness.swift -o bin/alibi-witness
swiftc -O native/Island.swift -o bin/alibi-island
echo "Built bin/alibi-witness and bin/alibi-island"
