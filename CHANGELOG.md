# Changelog

BuddyMon follows semantic versioning. Public releases use `vMAJOR.MINOR.PATCH`
git tags and matching plugin metadata versions.

## [0.1.0] - 2026-06-18

Initial public release.

### Added

- Local Claude Code plugin runtime with command wrappers, hook wiring,
  statusline rendering, local state, and deterministic engine tests.
- Token-based progress, streaks, milestone balls, evolutions, wild encounters,
  shiny catches, and a permanent journey journal.
- Cross-client token collection for Codex and Auggie, plus tmux status output.
- SwiftBar menu-bar companion with sprite rendering, dropdown controls,
  journey history, encounter alerts, and optional KeepAlive launch agent.
- Interactive Safari Zone encounters for rare and legendary spawns.
- Optional Battle Mode with attack, ball, and run actions.
- National Dex 1-649 support with generated evolution chains.
- Optional official Gen 2, box-art, and Gen 5 sprite-pack tooling that writes
  generated assets to local state instead of the repo.
- Project documentation for setup, architecture, decisions, assets,
  troubleshooting, development, and commands.

### Changed

- Tuned progress weights, leveling curve, and wild encounter cadence for a
  better first-release pace.
- Added raw tracked-token totals to the menu bar, tiny status, and status card.
- Kept recent evolutions visible after short animations so they are easier to
  notice.
- Improved the terminal UI with compact sprite previews on encounter, party,
  status, and Pokédex screens plus dense wheel, page, home, and end navigation.
- Switched statusline, terminal status, and cutscene fallback art to scaled
  local box sprites when Gen 2 sprites are missing.

### Fixed

- Bounded SwiftBar image generation and dropdown rendering to avoid excessive
  CPU and memory growth.
- Fixed terminal pokedex sprite cells so large local box-art sprites no longer
  clip and unknown entries stay readable.
- Darkened SwiftBar notice colors so evolution and progress rows stay readable
  on gray menu backgrounds.
