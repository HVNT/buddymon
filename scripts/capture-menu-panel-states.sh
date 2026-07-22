#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="${1:-${ROOT}/.build/menu-panel-states.png}"
BUILD_DIR="${ROOT}/.build/menu-panel-state-harness"
SOURCE_DIR="${ROOT}/macos/BuddyMonApp/Sources/BuddyMonApp"
EXECUTABLE="${BUILD_DIR}/menu-panel-state-harness"

mkdir -p "${BUILD_DIR}/module-cache" "$(dirname "${OUTPUT}")"

xcrun swiftc \
  -module-cache-path "${BUILD_DIR}/module-cache" \
  -framework AppKit \
  -framework QuartzCore \
  "${SOURCE_DIR}/BrandStyle.swift" \
  "${SOURCE_DIR}/MenuPanelController.swift" \
  "${SOURCE_DIR}/MenuPanelStateHarnessView.swift" \
  "${ROOT}/tools/MenuPanelStateHarness.swift" \
  -o "${EXECUTABLE}"

python3 "${ROOT}/buddymon.py" app-menu-panel-harness | "${EXECUTABLE}" "${OUTPUT}"
