# Architecture

BuddyMon is a local Python game with several small presentation shells.

## Components

- `hooks/stop.py` reads Claude Code activity.
- `lib/engine.py` owns progression, encounters, catches, and evolution.
- `lib/state.py` owns persisted game state and its cross-process lock.
- `lib/app_bridge.py` is the stable JSON facade for the native app.
  `lib/app_payloads.py` owns status and Pokémon payload primitives,
  `lib/app_views.py` owns read-only encounter, token, trainer, and settings
  views, `lib/app_actions.py` owns lock-aware mutations, and
  `lib/app_fixtures.py` owns deterministic visual-harness payloads.
- `lib/menu_panel.py` owns the compact panel's structure, labels, visibility,
  shortcuts, and stable action ids.
- `lib/trainer_card.py` projects local trainer facts, current gameplay stats,
  and badge eligibility into one non-mutating compact-card payload.
- `lib/menu_bar.py` owns the canonical menu-bar state catalog, event priority,
  stable sequence ids, timed PNG frames, and developer-harness fixtures.
- `lib/token_usage.py` reads only supported local AI-tool records (Claude Code,
  Codex CLI, Auggie, and Gemini CLI) into report and dashboard data; it never
  guesses unknown providers or model names.
- `lib/tui.py` coordinates terminal screens through focused layout,
  collection, Showcase, settings, and terminal-runtime modules. The runtime
  module is the sole owner of inline-image state and terminal I/O.
- `lib/swiftbar.py` owns the still-supported SwiftBar rendering and animation;
  `buddymon.py` remains the command adapter and CLI dispatcher.
- `statusline.py`, the terminal menu, SwiftBar, and tmux render the same state
  for different clients.
- `BuddyMon.app` is a thin menu-bar-only AppKit shell. Python remains the game
  brain.
- `MenuBarBuddy.swift` decodes and schedules Python-owned menu-bar sequences on
  the native status item. It contains no game or encounter rules.
- `MenuPanelController.swift` owns only the anchored compact `NSPanel`: its
  lifecycle, focus, dismissal, and locked screen-space anchor. Compact screen
  content lives in `CompactRootView.swift`, `CompactTrainerCardView.swift`,
  `CompactTokenUsageView.swift`, `CompactSettingsView.swift`, and
  `CompactEncounterView.swift`. `CompactSetupView.swift` owns compact first-run,
  loading, and diagnostic states; genuinely shared compact chrome lives in
  `MenuPanelSharedViews.swift`. There is no hidden titled window or generic
  expanded-content host.
- `BrandStyle.swift` is the only source of native colors, type, spacing,
  geometry, and shared control treatments. `BrandStylesPreview.swift` renders
  the shared living reference, while `MenuPanelStateHarnessView.swift` renders
  shipping compact components and their product states;
  `StyleArchivePreview.swift` is historical only.

The native shell holds a per-user advisory lock for its full lifetime, so app
copies from development previews and self-contained builds cannot create duplicate
menu-bar items, timers, or collection commands. The lock file rejects symbolic
links and is not inherited by child commands. A later launch notifies the
running copy to reopen its panel, then exits before it creates UI or starts
work.

Personal state, journal history, and optional packs live under
`$XDG_STATE_HOME/buddymon`, defaulting to
`~/.local/state/buddymon`.

Missing state creates a new in-memory default. An existing corrupt, unreadable,
structurally invalid, or future-version state raises a typed recovery error
instead; normal commands and hooks cannot save over it. Valid older state keeps
its source version outside the JSON payload so the first migrated save can
preserve the original under `recovery/`. State v5 treats preference and session
fields missing from historical v4 files as additive migration inputs, while
still rejecting malformed values that are present.

## Data Flow

Claude Code is the only plugin integration: its hooks collect new transcript
usage, apply game rules, and save the result automatically. Activity from Codex
CLI and Auggie is collected through `collect`, run manually or by the app and
optional service. Gemini CLI contributes to the read-only Token Usage report
only; it never awards progress. All state-changing paths hold the shared lock
across a fresh load, mutation, and save.

Interactive screens release the lock while waiting for input. After a keypress
they resolve the selected Pokémon against current state again, avoiding stale
overwrites from another client.

The native app calls:

- `app-status` for setup, summary state, queued menu-bar moments, persistent
  menu-bar attention, and declarative native-menu policy
- `app-view encounter|tokens|trainer|settings` for read-only native payloads
- `app-action encounter|preference` for native mutations

Native child processes run asynchronously. The process executor drains both
output streams and enforces timeout and cancellation behavior, so a slow or
large Python response does not block the UI.

The native shell watches the local state directory for `state.json` changes.
It watches the directory because Python commits state with an atomic rename,
then compares the state file's inode, size, and modification time so journal
and lock traffic does not launch redundant status reads. A short debounce
coalesces each save burst, and refresh requests share one passive task. Opening
the dropdown requests fresh status immediately; the 30-second timer remains a
recovery fallback rather than the normal synchronization path.

The menu-bar payload has three layers: a looping baseline, unseen moment
sequences, and one persistent attention state. Python returns stable sequence
ids so the Swift player does not restart an animation every time status is
refreshed. Moment retention lets a short catch or evolution survive the normal
status polling interval; the player queues unseen moments and renders them once.
Reduce Motion selects the sequence's representative frame.

Developer story playback uses the same sequence model. The Python runner
atomically writes one bounded payload in the current user's temporary directory
and signals the single BuddyMon process. AppKit temporarily plays that sequence
on the real status item, continues accepting fresh live status behind it, and
restores the newest baseline or queued moment afterward. This is local QA
transport only: it does not mutate trainer state or create another status item.

The native-menu policy owns the compact panel's labels, ordering, visibility,
shortcuts, and stable action IDs in Python. AppKit renders that model with
`BuddyMonBrand`. Clicking the status item opens the compact view; a waiting wild
becomes its first action. Trainer Card data is served through `app-view trainer`;
it reads state and journal evidence without mutating either. Badge selection is
ephemeral native view state: it replaces the badge heading with the selected
name while medallion styling carries earned or locked state and the tooltip
retains the requirement. It never writes game state. Settings reads `app-view
settings` and writes through the validated
`app-action preference <key> <value>` contract inside the compact panel, so each
visible native option sets an exact value instead of relying on client-side
cycling. Party, Box, Pokédex, and Activity invoke the existing `open-menu`
client as explicit terminal handoffs.

Native encounter payloads can include one locally rendered pixel battle PNG.
The bridge produces it only when the native screen or an encounter action is
requested; SwiftBar keeps its lightweight static and transient-art behavior.

## Scheduled Collection

The app timer and generated LaunchAgent both run `collect --scheduled`. That
command checks one timestamp while holding the state lock and allows at most one
scheduled collection every five minutes across all processes. Manual
`collect` stays immediate.

The LaunchAgent is never installed automatically. `collector install`
generates it from the current Python runtime, repo or bundled script path, and
`XDG_STATE_HOME`. `collector status` and `collector uninstall` provide the
rest of its lifecycle.

## Assets

Built-in fallback art is sufficient for every screen and for app readiness.
Optional packs are installed or refreshed only after an explicit user action.
Downloads are staged and validated before replacement; a failure leaves the
last working pack in place.

The native Trainer Card reads an optional Trainer Red portrait from the local
trainer pack. Without it, the card draws BuddyMon's original two-tone silhouette
with `BuddyMonBrand` colors. The portrait is never bundled and is fetched only
by an explicit asset command.

Showcase selection stores only Pokémon ids in normal state. PNG export reads
those ids and writes a local file on demand without storing export history.

## Boundaries

- Code lives in this repository.
- Self-contained builds copy code and a private Python runtime into the app bundle.
- Personal state and generated packs stay outside the repository.
- Normal play is local-only and does not rewrite AI-tool settings.
- Runtime code stays stdlib-only where practical; tooling may use Pillow.
- Shipping native views always consume `BuddyMonBrand`; visual tokens are not
  duplicated in individual screens.
- `capture-brand-styles.sh` renders the complete developer reference and
  `capture-menu-bar-states.sh` renders every status-item state at light, dark,
  selected, and reduced-motion settings. `capture-menu-panel.sh` renders the
  shipping compact view, while `capture-menu-panel-states.sh` renders root,
  first-run setup, flow loading/error, token, all-preferences Settings, Settings
  loading, encounter, result, and both Trainer Card states. All use stable sizes
  for visual review and deterministic native tests.

See [Development](development.md) for build and test commands and
[Brand Styles](brand.md) for the native visual contract, and [BuddyMon.app,
ELI5](macos-app.md) for the user-facing app flow.
