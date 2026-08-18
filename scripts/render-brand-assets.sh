#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT}/.build/brand-assets"
EXECUTABLE="${BUILD_DIR}/render-brand-assets"
ICONSET="${BUILD_DIR}/AppIcon.iconset"

mkdir -p "${BUILD_DIR}/module-cache"
rm -rf "${ICONSET}"

xcrun swiftc \
  -module-cache-path "${BUILD_DIR}/module-cache" \
  -framework AppKit \
  "${ROOT}/scripts/render-brand-assets.swift" \
  -o "${EXECUTABLE}"

"${EXECUTABLE}" "${ROOT}" "${ICONSET}"
echo "${ROOT}/macos/BuddyMonApp/Resources/AppIcon.icns"
