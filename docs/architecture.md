# Architecture

BuddyMon is a tiny local game wrapped around Claude Code activity.

## Flow

1. Claude Code runs hooks from `hooks.json`.
2. `hooks/stop.py` reads the current transcript and turns token usage into XP.
3. Game rules in `lib/engine.py` update level, catches, evolutions, streaks,
   balls, and pending encounters.
4. `lib/state.py` saves everything to `~/.local/state/buddymon/state.json`.
5. Renderers show the same state in several places:
   - `statusline.py` for Claude Code
   - `buddymon.py menubar` for SwiftBar
   - `buddymon.py menu` for the interactive terminal UI
   - `buddymon.py tiny --collect` for tmux
   - `/buddymon:*` commands for direct actions
6. `lib/menu_launcher.py` opens that menu from SwiftBar, preferring Ghostty,
   then iTerm2, then Terminal.app.

## Boundaries

- Code lives in the repo.
- Personal state and downloaded sprite packs live in `~/.local/state/buddymon/`.
- Runtime code should stay stdlib-only where practical.
- Asset fetch tools may use Pillow and the network, but only when run manually.
