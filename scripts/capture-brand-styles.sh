#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="${1:-${ROOT}/.build/brand-styles.png}"
BUILD_DIR="${ROOT}/.build/brand-styles-snapshot"
SOURCE_DIR="${ROOT}/macos/BuddyMonApp/Sources/BuddyMonApp"
EXECUTABLE="${BUILD_DIR}/brand-styles-snapshot"

mkdir -p "${BUILD_DIR}/module-cache" "$(dirname "${OUTPUT}")"

xcrun swiftc \
  -module-cache-path "${BUILD_DIR}/module-cache" \
  -D BUDDYMON_DEVELOPMENT \
  -framework AppKit \
  -framework QuartzCore \
  "${SOURCE_DIR}/BrandStyle.swift" \
  "${SOURCE_DIR}/BrandStylesPreview.swift" \
  "${ROOT}/tools/BrandStylesSnapshot.swift" \
  -o "${EXECUTABLE}"

"${EXECUTABLE}" "${OUTPUT}"
