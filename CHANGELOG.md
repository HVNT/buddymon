# Changelog

BuddyMon follows semantic versioning. Public releases use `vMAJOR.MINOR.PATCH`
git tags and matching plugin metadata versions.

## Unreleased

## [0.2.0] - unreleased

### Added

- Added Trainer Red as an optional local art pack. Explicit asset installation
  fetches one pinned, SHA-256-verified FireRed/LeafGreen portrait into BuddyMon's
  XDG state directory; it is never bundled, and the original two-tone
  silhouette remains the safe fallback.
- Added final-download verification for signed release ZIPs and a clean-user
  public-release QA checklist covering First Signal and optional macOS prompts.
- Added macOS pull-request CI, one canonical release version, immutable
  per-architecture Python/Pillow runtime locks, release metadata validation,
  and an explicit Developer ID signing/notarization/checksum packager.
- Added write-blocking recovery for corrupt, unreadable, structurally invalid,
  and newer-version state. Valid older state now preserves a pre-migration copy.
- Added a native 3:2 Trainer Card with NAME, TOKENS, POKÉDEX, CAUGHT, BuddyMon's
  original two-tone trainer silhouette, and collection-backed badges.
  Its former empty middle band now carries a compact live status rail for
  encounter mode, activity streak, available balls, and owned shiny count.
  That rail now spans the full card width so its surface and rules meet the
  black border while its four stat columns remain evenly centered.
  Shiny Legend is always
  represented; Shiny National stays completely hidden until National is earned.
  Badges are now larger circular medallions with centered equal-width alignment,
  a staggered entrance, gentle hover lift, and a subtle shiny-achievement glow.
  Their symbols now use true zero-offset vertical centering. Badge motion honors
  macOS Reduce Motion. The fact/value grid, portrait, and bottom rail now share
  deliberate columns. The four-star core-badge rank moved into the badge header;
  selecting a badge replaces the left-side heading with its name instead of
  repeating `EARNED`.
- Added a Python menu-bar demo runner that can play any canonical status-item
  state or a complete Charmander user story on the real native menu-bar buddy.
  Previews are local, temporary, do not mutate trainer state, and automatically
  return to live status.
- Added a canonical 23-state menu-bar buddy model covering baseline activity,
  progression, encounter attention, automatic battle, catching, results,
  evolution, fallbacks, and Reduce Motion representatives.
- Added an interactive developer menu-bar state harness plus a deterministic
  full contact-sheet capture for light, dark, selected, and reduced-motion QA.
- Added a compact native menu-bar panel with the active sprite, ASCII XP meter,
  trainer signal, encounter routing, a preserved gated expanded prototype, and
  an explicit Advanced terminal handoff.
- Expanded Token Usage into a supported-tool intelligence view: daily detail,
  per-tool rhythm, 28-day signal, weekly pace, and streak/range insights for
  Claude Code, Codex CLI, Auggie, and Gemini CLI only.
- Added **Back Up My Data** in App and Terminal Settings. Both use one shared
  command to make a manual, timestamped local copy of state, journal, and
  optional packs in Documents.
- Added native keyboard controls: WASD or arrow keys move between controls,
  Return or Space selects, and Escape returns Home from interactive screens.
- Added a native seven-day Token Usage dashboard in the Redline Mono brand
  system, with daily bars, source mix, prior-period comparison, and compact
  trend insights.
- Added native, on-demand pixel battle scenes with emoji identity and outcome
  cues for Safari and Battle encounters; resolved encounters hold a static
  caught or fled result until returning Home.
- Added the canonical Redline Mono Brand Styles system and a developer-only,
  scrollable living reference covering components, screen patterns, feedback,
  interactions, and accessibility states. Interleaved user-story bands show
  the same moment in the emoji statusline, macOS menu bar, and native app, with
  cute built-in pixel art beside optional local-pack PNG sprites.
- Kept the three earlier native visual explorations in a developer-only Style
  Archive that is explicitly historical and non-normative.
- Added a self-contained, menu-bar-only `BuddyMon.app` build with a
  private Python runtime.
- Added native Home, Encounter, and Showcase screens plus expanded-panel views
  for collections, journal, token usage, settings, Doctor, and waiting wilds.
- Added a manually curated Showcase with search, local PNG sharing, and
  responsive terminal trophy cards.
- Added Quick, Safari, and Battle encounter styles with local settings for
  notifications, launcher, graphics, and sharing feedback.
- Added an opt-in generated background collector with
  `collector install|status|uninstall`.

### Changed

- Clarified client support: Claude Code hooks award progress automatically,
  Codex CLI and Auggie use collection, and Gemini CLI is Token Usage only.
- Removed every AppleScript notification fallback. Finder-launched builds now
  find `terminal-notifier` in standard Homebrew locations or skip the optional
  banner, so BuddyMon can never open Script Editor from a notification.
- First Signal, starter selection progress, and setup errors now stay inside the
  standard 304-by-210 Field Guide panel. The legacy hidden titled flow window,
  generic expanded-content host, and its special keyboard plumbing were
  removed.
- First launch now opens First Signal automatically after one confirmed
  no-buddy status. Existing trainers still launch quietly, and the published
  archive uses a stable Apple-silicon download name.
- Starter setup now requires one confirmed, internally consistent no-buddy
  status before it appears. State-recovery errors and active-buddy payloads
  cannot be mistaken for a new game.
- `--install` now stops the running BuddyMon process before replacing the app,
  preventing `--open` from signaling a stale in-memory build.
- Token Usage now compares This Week with the same elapsed weekdays from last
  week and names the cutoff in the prior-period label until Sunday.
- Self-contained runtime builds no longer query a mutable latest release,
  upgrade pip, or install a Pillow range. Every archive and wheel is exact and
  hash-verified. Managed runtimes must still match that lock before reuse;
  external development runtimes require an explicit opt-out.
- Release packaging now rejects bundle metadata overrides and validates the
  production identity before signing and archiving. CI uses the release Python
  and Pillow versions, checks committed whitespace, and builds the locked
  self-contained app.
- State validation now covers nested trainer, Pokémon, session, encounter, and
  preference records before migration and before every save. State v5 migrates
  additive preference and session fields missing from historical v4 files,
  preserving the v4 source before the first migrated save.
- Release checksum files now record only the archive basename, so verification
  remains portable after download.
- Removed the extracted Trainer Red portrait from the distributable app. The
  Trainer Card now always draws BuddyMon's original two-tone silhouette.
- Removed the final unreachable native confirmation builder and normalized the
  surviving compact-panel, Python bridge, and terminal helper names around
  `present`, `load`, `open`, `build`, `handle`, and `render` roles. Public CLI
  verbs, JSON keys, state, layout, and gameplay behavior are unchanged. The
  compact native views, JSON bridge, terminal features, SwiftBar renderer, and
  their tests now live in focused files behind the same public entry points.
- Made native status synchronization event driven. Atomic local `state.json`
  saves now trigger one debounced, coalesced refresh, opening the dropdown asks
  for fresh status immediately, and the existing 30-second poll remains only as
  recovery. Terminal-started battles no longer wait on the polling interval or
  the menu-bar animation queue before appearing in the native menu.
- Removed the hidden `B` shortcut from native back chevrons so the visible
  Safari `B / Bait` action receives the key instead of navigating away.
- Fixed repeated Ghostty confirmation prompts when Party, Box, Pokédex, or
  Activity launches from the installed app. Ghostty now starts a stable system
  shell and receives the safely quoted BuddyMon command as startup input instead
  of treating the app-bundled Python runtime as a file to open.
- Activity now scrolls through the complete local journey instead of silently
  stopping at the newest 200 entries while claiming to show everything.
- Removed compact view entrance animations. Home and every drill-in now render
  their complete shell and content immediately, with no row-count-dependent
  fade or stagger. The obsolete reveal stack, timing tokens, presentation gate,
  and preview specimen were deleted; regression coverage now keeps compact
  views static. Pokémon and control motion remain unchanged.
- Removed the unreachable expanded native dashboard graph, hidden expansion
  action, and obsolete Home snapshot tooling. The native bridge now exposes
  only Encounter, Token Usage, Trainer, and Settings plus encounter/preference
  actions. Party, Box, Pokédex, Activity, Showcase, favorites, and buddy
  switching remain in the Python terminal game instead of keeping duplicate
  private native routes.
- Reskinned the compact dropdown with the light Field Guide system: a bordered
  trainer-card layout, real sprite art, visual XP meter, clearer stat rhythm,
  game-dialogue signal block, and calmer keyboard-first actions. All new color,
  spacing, geometry, progress, and action treatments live in
  `BuddyMonBrand.Menu`. The denser revision adds a local Refresh control, larger
  small labels, and a shared Refresh/Quit utility row.
  The default Home, Token Usage, Settings, Battle, and Battle Result stacks now share the
  Trainer Card's striped 288-point frame, warm surface, dark display masthead,
  border, and compact inner spacing without changing their content or actions.
  A further monochrome pass reduces the panel to warm Pokémon off-white and
  charcoal, removes the trainer-total strip, and removes repeated card, signal,
  sprite-well, and action borders. The buddy sprite now sits directly in the
  outer card with one padding layer instead of a nested rounded well. The
  active-buddy group now spans the full Field Guide width with square edges and
  super-subtle top and bottom rules instead of a rounded inset container. Its
  54-point sprite now sits inside one consistent six-point perimeter instead of
  letting minimum panel height create extra space below the content. The
  masthead now starts directly with `BUDDYMON` and a steady semantic status dot
  instead of a decorative silhouette and blinking block. Recent-catch spacing
  now uses explicit chevron, sprite, label, name, and rarity columns.
  Trainer, Token Usage, Battle, and Battle Result now share one back-chevron and
  title row, removing duplicate bottom Back, Home, and Return Home actions.
  Token Usage now keeps the standard 304-by-210 compact dimensions for loading,
  success, and failure, eliminating the brief oversized black Redline frame
  that previously appeared while its local report loaded. Its resolved compact
  view now uses the available height for a proportional seven-day pulse, daily
  average, peak day, active streak, and supported-tool share instead of empty
  vertical gaps. Three isolated headline cards are now two equal comparison
  cards: Today with Yesterday, and This Week with Last Week, each with its own
  percentage. The daily pulse now devotes 52 points to the chart, more than
  doubling the drawable bar height without changing the panel dimensions. Its
  irrelevant arrow/Return instruction footer is removed;
  supported-tool share now forms the report's clean bottom edge. Home now uses a square 3-by-2 grid of six 22-point links for
  Trainer, Party, Box, Pokédex, Activity, and Settings. Each link has a subtle
  one-pixel rule, no rounded button body, and a small Reduce-Motion-aware hover
  lift; primary and encounter actions retain their 32-point button treatment.
  Settings now opens as a fixed 304-by-210 native Field Guide view with all
  seven preferences directly visible. Every allowed value appears as its own
  native text control and applies immediately through the existing validated
  Python action path; operational setup and backup actions remain separate
  flows. The active option is darker, bold, underlined, and marked with a leading
  chevron. Compact 18-point rows keep the keyboard guide fully visible. Inactive
  options remain muted, while every option has a reliable
  pointing-hand hit target, transient hover wash, and explicit keyboard-focus
  outline.
- Fixed optional terminal handoffs around a 760-by-520 footprint beside the
  open menu-bar panel. The native dropdown stays open while Ghostty, iTerm2, or
  Terminal.app is in use. Ghostty now receives one direct isolated-window launch
  with saved state, fullscreen, maximize, and close confirmation disabled; it no
  longer opens a provisional window, closes it, shows a close alert, then falls
  through to a second terminal.
- Added a compact Token Usage drill-in and condensed Tokens, Terminal, Refresh,
  and Quit into one utility row. Opening or reopening BuddyMon now always
  returns to the compact dropdown, and the macOS build supports `--install` so
  `/Applications/BuddyMon.app` cannot silently remain on an older build.
- Added the latest Pokémon's actual tiny sprite to the recent-catch signal,
  made arrow/Return/Space navigation work across every compact panel, and moved
  waiting encounters, minimal move controls, and encounter results entirely
  into the same dropdown. The preserved wide encounter prototype remains in
  code but is no longer part of the normal route. A waiting wild now uses one
  dark sprite-and-action row instead of repeating its status above the action.
- Reworked compact-menu hierarchy with a
  FireRed/LeafGreen-inspired bitmap wordmark, a clickable Today/Yesterday
  masthead control instead of a second token row, and a balanced terminal
  shortcut grid for Trainer, Party, Box, Pokédex, Activity, and Settings.
  Trainer and Settings stay native while the other four retain their terminal
  destinations. Major
  labels and action copy now use the local pixel face with proportional spacing, light one-pixel
  strokes, and open tracking, while compact supporting data stays SF Mono. The
  token control is one right-aligned, backgroundless line with a smaller label.
  The final compact pass reduces the panel from 380 to 304 points, shrinks
  action-label type and insets, removes the token control's focus border, and
  gives every clickable compact control a pointing-hand cursor. The XP bar now
  flexes so its percentage aligns perfectly with the level column above.
  Refresh and Quit are now subtle footer commands using the macOS-standard
  `⌘R` and `⌘Q` shortcuts instead of raised buttons.
- Made the compact dropdown the only normal click destination: waiting wilds
  appear as its first action, the expanded native prototype is preserved but
  gated, Escape closes the panel, and initial keyboard focus lands on the first
  useful action.
- Polished menu-bar animation labels: catching relies on the rendered Poké Ball
  instead of a baseball emoji, level-up reads `Lvl!`, and every short label has
  deliberate space after the Pokémon sprite. Encounter attention now uses one
  integrated alert mark instead of rendering a second adjacent `!` label, and
  working state relies on the sprite bob instead of adding a white bullet.
- Kept the selected buddy as the status item's identity after automatic catches,
  while leaving the caught Pokémon beside Last Catch in the compact panel. The
  Last Catch label now stays directly beside that sprite instead of drifting to
  the far edge of the row. Its copy now uses neutral brand ink, its chevron sits
  at the content edge, and a single colored rarity letter follows the name.
- Tightened the root Field Guide inset and reduced the buddy sprite to align
  with its three identity rows. Battle names and caught, fled, or ran-away
  result titles now use neutral ink with color isolated to one rarity letter.
- Replaced the native app's static sprite plus generic alert nudge with a thin
  sequence player. Python now supplies stable baseline, queued-moment, and
  persistent-attention payloads so short events play once without restarting on
  every status refresh.
- Made the menu-bar buddy the current native quality gate; further dropdown and
  expanded-surface work follows only after the status item is finalized.
- Made BuddyMon a true menu-bar companion again: returning trainers launch
  without opening UI, new trainers get the anchored First Signal panel, normal
  use creates no Dock icon or standalone product window, and a later launch
  signals the already-running copy to reopen its panel.
- Added quiet native-panel motion: a cursor blink, sprite bob, and encounter
  alert, all disabled by macOS Reduce Motion.
- Replaced the first-run starter alert with a native First Signal screen and
  added rare local-only Home moments for shiny, streak, Pokédex, and 11:11
  milestones.
- Promoted `BuddyMonBrand` to the single source of truth for shipping native
  colors, type, spacing, geometry, and shared treatments. Native views now use
  the monochrome Redline Mono foundation, left alignment, and shared spacing;
  color is reserved for Pokemon identity, rarity, brand focus, and select
  signals.
- Unified production and preview surfaces, buttons, fields, and terminal
  controls behind shared Brand Styles factories; split Pikachu-yellow XP from
  neutral data progress, raised key dark-surface contrast, and added
  deterministic full-page visual snapshots.
- Renamed the former ASCII and console labs to Brand Styles and Style Archive
  so their canonical and historical roles are unambiguous.
- Made the native app one coherent place: clicking the menu-bar buddy opens a
  compact view, expansion keeps every product destination in the same anchored
  panel, and Showcase selection stays in that panel.
- Moved compact native-menu labels, order, visibility, shortcuts, and action
  IDs into the Python bridge so the macOS shell renders one shared menu policy.
- Replaced the dropdown's terminal-green chrome with Pokémon red, blue, and
  Electric yellow; green now appears only when it belongs to a Grass Pokémon.
- Restyled the native app as a dark local console with monospaced readouts,
  status-color cues, bordered panels, and clearer game-action controls.
- Optional art is now installed or refreshed only after confirmation, never
  blocks readiness, preserves the last working pack on failure, and honors
  `XDG_STATE_HOME`.
- Native Python commands now run asynchronously with bounded execution;
  optional-art actions return structured per-pack results.
- App and background collection now share one locked five-minute schedule gate;
  manual collection remains immediate.
- Improved terminal browsing with search, sorting, filters, newest-first
  journal history, and clearer settings.
- Made ordinary token usage count sooner, raised the buddy level cap to 100,
  capped random wilds at level 55, and fixed special-Pokémon encounter levels.
- Reworked token reports with clearer calendar summaries and compact milestone
  markers.
- Hardened friend-runtime builds with managed destinations, staged validation,
  and safe replacement.

### Fixed

- Kept prerelease metadata truthful by allowing the current version to remain
  marked `unreleased` during development while requiring a real publication
  date before packaging or verifying a public archive.
- Stopped the open native dropdown from shifting as animated menu-bar frames
  changed width. Each closed-to-open session now locks one screen-space anchor
  until the panel closes.
- Fixed the native status item showing a shared Gen 2 category icon for some
  buddies—Charizard was rendered as `BIGMON`—while the panel showed the correct
  species. Runtime status frames now prioritize a compacted version of the same
  species-specific Gen 5 art used by the panel.
- Kept Quit directly in the compact panel now that the background accessory app
  intentionally has no Dock or standard app menu.
- Rebuilt expanded Home as a compact 900-by-640 landscape dashboard with one
  full-width content column, real app navigation, a first-class wild signal,
  intrinsic-height recent catches, demoted local diagnostics, real XP progress,
  sprite-first identity, scrolling, and red keyboard focus instead of stretched
  panels and the macOS blue ring.
- Prevented development previews and app copies from creating duplicate native
  BuddyMon processes, menu-bar items, timers, or collection calls.
- Replaced Token Usage's reused Terminal window with a native summary and
  report, and made Token Usage and Showcase always open at the top instead of
  inheriting an unpredictable scroll position.
- Prevented native child-process pipe deadlocks and UI freezes on large or slow
  responses.
- Prevented terminal actions from overwriting concurrent XP, session, or
  encounter updates.
- Fixed Showcase pagination, centering, and two-column image placement.
- Fixed duplicate-species Party ordering and Ghostty menu-window fan-out.

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
  with ASCII separators, and daily/weekly money markers.
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
