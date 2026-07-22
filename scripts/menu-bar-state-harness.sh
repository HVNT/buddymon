#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT}/.build/menu-bar-state-harness"
SOURCE_DIR="${ROOT}/macos/BuddyMonApp/Sources/BuddyMonApp"
EXECUTABLE="${BUILD_DIR}/menu-bar-state-harness"

mkdir -p "${BUILD_DIR}/module-cache"

xcrun swiftc \
  -module-cache-path "${BUILD_DIR}/module-cache" \
  -framework AppKit \
  "${SOURCE_DIR}/BrandStyle.swift" \
  "${SOURCE_DIR}/MenuBarBuddy.swift" \
  "${SOURCE_DIR}/MenuBarStateHarnessView.swift" \
  "${ROOT}/tools/MenuBarStateHarness.swift" \
  -o "${EXECUTABLE}"

python3 "${ROOT}/buddymon.py" app-menu-bar-harness | "${EXECUTABLE}" "$@"
