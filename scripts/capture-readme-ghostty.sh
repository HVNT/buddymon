#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BUILD_DIR="$ROOT/.build/readme-ghostty"
STATE_ROOT="$BUILD_DIR/state"
WINDOW_TOOL="$BUILD_DIR/readme-ghostty-window"
OUTPUT="$ROOT/docs/screenshots/terminal-box-ghostty.png"

if [[ ! -d /Applications/Ghostty.app ]]; then
  echo "Ghostty is required for the README terminal capture." >&2
  exit 1
fi

mkdir -p "$BUILD_DIR" "$(dirname "$OUTPUT")"
python3 "$ROOT/scripts/generate-readme-screenshots.py" --terminal-state-only
xcrun swiftc \
  -framework CoreGraphics \
  "$ROOT/tools/ReadmeGhosttyWindow.swift" \
  -o "$WINDOW_TOOL"

XDG_STATE_HOME="$STATE_ROOT" \
  python3 "$ROOT/buddymon.py" open-menu box --window-frame=80,80,1040,680

window_id=""
for _attempt in {1..40}; do
  if window_id="$($WINDOW_TOOL 2>/dev/null)"; then
    break
  fi
  sleep 0.25
done

if [[ -z "$window_id" ]]; then
  echo "Could not find the BuddyMon Ghostty window." >&2
  exit 1
fi

sleep 2
screencapture -x -o -l "$window_id" "$OUTPUT"
XDG_STATE_HOME="$STATE_ROOT" python3 -c \
  'from lib import menu_launcher; menu_launcher._close_owned_ghostty_menus()'
echo "$OUTPUT"
