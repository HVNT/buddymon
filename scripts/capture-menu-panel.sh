#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="${1:-${ROOT}/.build/menu-panel.png}"
BUILD_DIR="${ROOT}/.build/menu-panel-snapshot"
SOURCE_DIR="${ROOT}/macos/BuddyMonApp/Sources/BuddyMonApp"
EXECUTABLE="${BUILD_DIR}/menu-panel-snapshot"

mkdir -p "${BUILD_DIR}/module-cache" "$(dirname "${OUTPUT}")"

xcrun swiftc \
  -module-cache-path "${BUILD_DIR}/module-cache" \
  -framework AppKit \
  -framework QuartzCore \
  "${SOURCE_DIR}/BrandStyle.swift" \
  "${SOURCE_DIR}/MenuPanelController.swift" \
  "${SOURCE_DIR}/MenuPanelSharedViews.swift" \
  "${SOURCE_DIR}/CompactRootView.swift" \
  "${SOURCE_DIR}/CompactTrainerCardView.swift" \
  "${SOURCE_DIR}/CompactTokenUsageView.swift" \
  "${SOURCE_DIR}/CompactSettingsView.swift" \
  "${SOURCE_DIR}/CompactEncounterView.swift" \
  "${SOURCE_DIR}/CompactSetupView.swift" \
  "${ROOT}/tools/MenuPanelSnapshot.swift" \
  -o "${EXECUTABLE}"

python3 "${ROOT}/buddymon.py" app-status | "${EXECUTABLE}" "${OUTPUT}"
