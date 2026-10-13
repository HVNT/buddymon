#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${1:-${ROOT}/.build/macos/BuddyMon.app}"
OUTPUT="${2:-${ROOT}/.build/release/BuddyMon-macOS.dmg}"
if [[ ! -d "${APP}" || "${OUTPUT}" != *.dmg ]]; then
  echo "usage: scripts/create-macos-dmg.sh [BuddyMon.app] [output.dmg]" >&2
  exit 2
fi
mkdir -p "$(dirname "${OUTPUT}")"
STAGING="$(mktemp -d "${TMPDIR:-/tmp}/buddymon-dmg.XXXXXX")"
trap 'rm -rf "${STAGING}"' EXIT
ditto "${APP}" "${STAGING}/BuddyMon.app"
ln -s /Applications "${STAGING}/Applications"
cat > "${STAGING}/Start Here.txt" <<'TEXT'
Drag BuddyMon.app into Applications, then open it from Applications.

Choose your buddy. Pokémon artwork downloads in the background.
Keep BuddyMon open while you use Claude Code, Codex CLI, or Auggie.
Click your buddy in the menu bar to check in.

Requires macOS 13 or later. Supports Apple Silicon and Intel.
TEXT
hdiutil create -volname BuddyMon -srcfolder "${STAGING}" -format UDZO -ov "${OUTPUT}"
echo "disk image: ${OUTPUT}"
