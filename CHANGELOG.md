# Changelog

BuddyMon follows semantic versioning. Public releases use `vMAJOR.MINOR.PATCH`
git tags and matching plugin metadata versions.

## [0.1.0] - 2026-06-26

Initial public release.

### Changed

- Reordered the SwiftBar dropdown so the active buddy media row leads, level
  progress stays directly underneath, and the stats summary (`streak`, balls,
  species) sits above `Open menu` with its icon in the native menu column.
- SwiftBar menu launchers now prefer Ghostty, then iTerm2, then Terminal.app;
  Ghostty opens replace only BuddyMon-owned Ghostty menu windows to avoid Dock
  growth.
- Reworked the SwiftBar dropdown header into an active Pokémon media block that
  uses the real sprite, level, gender, age, and caught date instead of an emoji
  summary row.
- Removed the SwiftBar Pokédex submenu from the dropdown while keeping Pokédex
  browsing in the terminal menu.
- Capped the SwiftBar Switch buddy submenu and routed overflow switching to the
  scrollable terminal Party menu.
- Moved level progress to the top of the SwiftBar dropdown and split token
  usage into a dedicated terminal report with local calendar summaries,
  compact B/M/K formatting, cached daily source-file totals, weekly total rows
  with ASCII separators, and daily/weekly money markers where `🤑` means a
  whole billion tokens and `💰` means each remaining 100M tokens.
- Wild encounters now get a bounded random level from their evolution-stage
  range, carry that level through Auto, Safari, and Battle catches, and show it
  in encounter UI and journal text.
- Migrated older caught evolved forms up to their minimum legal evolution-stage
  level, and removed plain `+N progress` noise from event notices.
- Switched terminal Pokédex row numbers to real National Dex IDs instead of
  display-order indexes.
- Added terminal Party sorting by rarity, name, National Dex number, and caught
  date, with ascending/descending direction controls.
- Fixed encounter notices so ordinary wild appearances no longer say
  `no balls left` unless the encounter actually hit an empty inventory.
- Fixed terminal Battle Mode results so a finished ball throw flashes the
  outcome and returns instead of waiting on a second keypress.
- Added local timestamps to recent SwiftBar encounter notices, including
  caught Pokémon rows.
- Normalized multi-fact SwiftBar dropdown rows to use `·` separators instead
  of mixed spacing.
- Framed selected Pokemon previews in terminal Party and Box views and removed
  the redundant `selected` label from the detail panel.
- Centered terminal Party and Box preview sprites by their visible pixels, not
  by transparent source-art padding, and fixed framed-card row sizing for
  inline PNG previews.
- Fixed terminal inline PNG placement so invisible ANSI color escapes in Party
  and Box list rows no longer shift selected sprites to the right.
- Reworked terminal Party and Box detail panels into one bordered card with
  attached metadata, National Dex numbers, quiet list headers, and larger
  centered sprites, keeping the active/action hint just below the card.
- Reworked the terminal main menu into a bordered, two-column action list and
  fixed the Settings row alignment.

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
