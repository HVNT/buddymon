# <img src="assets/brand/icons/brand.png" width="28" height="28" alt=""> Decisions

**What we chose, and why.** These are current product and engineering choices.
Implementation maps live in [Architecture](architecture.md), exact visual rules
in [Brand Styles](brand.md), and change history in [CHANGELOG](../CHANGELOG.md).

## Product: a small companion

| Decision | Why |
| --- | --- |
| The menu-bar buddy is the primary native surface. | Work, progress, encounters, and evolution should be recognizable at a glance. |
| One anchored compact panel contains setup, root, Tokens, Trainer, Settings, encounters, and results. | A dependable small companion fits the product better than a desktop dashboard. |
| Clicking the buddy always opens the root; a waiting wild becomes its first action. | Navigation stays predictable without hiding an encounter. |
| Party, Box, Pokédex, Activity, and Showcase remain terminal experiences. | Collection-heavy screens get room without maintaining duplicate native renderers. |
| New trainers see First Signal after a confirmed no-buddy status; returning trainers launch quietly. | Onboarding should be discoverable once, then stay out of the way. |
| Self-contained builds include Python and Pillow. | Players should not need a developer toolchain to run the app. |

The former expanded native graph and private routes are removed, not dormant
features. Historical work remains in Git, including
`archive/native-window-prototype-2026-07-16`.

The open panel captures its position once and keeps it through refreshes and
drill-ins. Closing releases that anchor. Menu-bar animation must not move an
already-open interface.

## Ownership: one Python game, several interfaces

**Decision:** Python owns rules, persistence, native-menu policy, and timed
menu-bar frames. Swift owns process execution, rendering, accessibility, and
native lifecycle. Terminal, statusline, SwiftBar, and tmux use the same core.

**Why:** Shared rules prevent clients from drifting. Structured JSON keeps the
native app independent of human-readable terminal output.

| Boundary | Contract |
| --- | --- |
| Menu policy | Python supplies labels, order, visibility, shortcuts, and stable action IDs. Swift routes known IDs. |
| Child commands | Run asynchronously; drain stdout/stderr and enforce timeout/cancellation. Slow work must not freeze the panel. |
| Detail navigation | Trainer and Settings responses expire on navigation, close, or a newer request. A late success or error must not undo the player's next action; requested preference saves still finish. |
| One native app per user | A kernel-backed advisory lock covers development and self-contained copies. Later launches signal the existing panel and exit. |
| Live state | Watch the directory for atomic saves, filter by state-file signature, debounce bursts, and combine passive refreshes. |
| Recovery refresh | Opening the panel reads fresh state; a 30-second poll covers missed events. |
| Menu-bar playback | Stable sequence IDs prevent refreshes from replaying moments. Attention persists; Reduce Motion uses a representative frame. |

A catch may show the wild during the action, then returns the status item to the
active buddy. The compact panel identifies the caught Pokémon. Installed Gen 5
art keeps the status item and panel species-specific; legacy category icons are fallback.

## Data: local, shared, and protected

**Decision:** Personal data lives under `$XDG_STATE_HOME/buddymon`, defaulting to
`~/.local/state/buddymon`. Normal play does not upload it or rewrite AI-tool settings.
Plugin wiring belongs in `.claude-plugin/plugin.json` and `hooks.json`.

**Why:** Repository updates should not lose progress, leak personal files into
commits, or quietly change another tool's configuration.

- Game mutations lock across **fresh load → change → atomic save**.
  This includes starter selection and CLI buddy switching, so these commands
  cannot overwrite progress from concurrent collection.
  Interactive screens wait outside the lock, then re-resolve their selection.
- Missing state is different from damaged state. Corrupt, unreadable, invalid,
  or future-version saves block normal writes and remain untouched.
- Valid older state keeps a recovery copy before its first migrated save.
  State v5 makes historical v4 preference/session additions explicit: absent
  fields can migrate; malformed present values still fail validation.
- Manual backup copies the active state directory to a timestamped folder in
  `~/Documents/BuddyMon Backups`. It respects XDG paths and leaves live data alone.

## Activity: count new work once

| Decision | Why |
| --- | --- |
| Claude Code, Codex CLI, and Auggie earn progress directly from local logs. | Opening the Mac app should be enough for supported activity collection. |
| Claude's plugin is optional, with immediate turn-end updates and a statusline. | Terminal integration is useful without becoming a native-app prerequisite. |
| Plugin and app share a durable Claude transcript cursor. | Using both must not double-award work. |
| Initial scans anchor existing history; Claude has a separate bootstrap marker. | New installs and existing Codex/Auggie players should not receive surprise historical progress. |
| Claude cursors survive idle scan cutoffs, session-cache pruning, and temporary access failures. | A resumed transcript must not look new and replay old tokens. Confirmed file deletion permits cleanup. |
| Gemini CLI is token-report-only. Unknown log shapes are ignored. | Support and model attribution must be backed by recognizable local records. |
| App and LaunchAgent share one locked five-minute schedule gate. Manual collection is immediate. | Overlapping schedules should not duplicate work or delay an explicit diagnostic run. |

The LaunchAgent is installed only by `collector install`, with explicit
`status` and `uninstall` commands. Its runtime, script path, and XDG environment
come from the current installation.

**Token reports use saved snapshots.** Historical scanning runs in the background;
native reads never scan logs. Missing or previous-day reports show loading;
same-day refreshes retain the saved report. Late token results cannot undo navigation.
This keeps a slow history scan from blocking startup or exceeding a screen deadline.

Visible token totals make activity understandable. Weighted XP remains an
implementation detail so players do not need to optimize work around a formula.

## Artwork: automatic on Mac, resumable, local afterward

**Decision:** Native first launch downloads Pokémon packs while starter choice
and play remain available. Plugin-only setup and explicit refreshes use commands.

**Why:** Artwork is part of the intended Mac experience and should not require
a command. Download failure should never reset progress or remove working art.

- Gen 5 species appear progressively; retry reuses completed downloads.
- Regular **and** shiny frames are required for completion. Older receipts
  receive a background repair check, then successful validation is recorded once.
- Normal play and status reads use local copies. Setup owns network access.
- Trainer Card always has an original silhouette fallback. The downloaded
  Trainer Red portrait is pinned and checksum-verified; it is never bundled.
- Rich encounter art is rendered on demand. Idle UI does not continuously
  regenerate images; menu-bar and SwiftBar motion stays bounded.

Sources, commands, and fallback order are documented in [Assets](assets.md).

## Gameplay: calm by default, depth by choice

| Decision | Why |
| --- | --- |
| Quick is default; Safari and Battle are opt-in. | Players choose how much interaction they want. |
| Every shiny and legendary/mythical waits, including in Quick. Non-shiny rare Quick encounters may resolve automatically. | Exceptional finds deserve a deliberate choice without turning every rare encounter into an interruption. |
| Buddy progression has a high cap; random wilds have a lower cap, stage-aware levels, and fixed special-species levels. | The buddy remains worth growing for months while catches stay varied. Exact values belong in code. |
| IVs derive stable 0–15 Attack, Defense, and HP from each caught copy's immutable ID and a versioned hash namespace. | Duplicate catches gain collectible variation without a migration or hidden balance change. |
| Party and Box display IVs; only Box sorts/searches them. IVs never affect catch odds, XP, leveling, evolution, or battle. | Appraisal and gameplay balance stay separate. |
| Showcase starts with empty slots, stores chosen IDs, and exports a local PNG. | A trophy room should reflect deliberate choices, without accounts, uploads, or export history. |

## Interface: one visual system

**Decision:** `BuddyMonBrand` is the only native visual source. Field Guide is
the compact expression: warm off-white, neutral chrome, Pokémon identity, and
a clear current signal. Original Signal Buddy art owns the product identity.

**Why:** Shared tokens and shipping-component previews prevent competing local
palettes and spacing systems. A handheld guide makes the Pokémon prominent
without making the app look like a developer console.

- New tokens and treatments start in `BrandStyle.swift`, appear in the shared
  preview or shipping-component harness, and are documented in the same change.
- Compact screens and window chrome render immediately. No entrance fades,
  row staggers, or layout transitions delay content. Sprite, badge, and direct
  control feedback honor Reduce Motion.
- The Trainer Card derives facts and badge eligibility without mutating state.
  Rank is one star per two core badges, not a trainer level. Shiny National is
  hidden until National is earned; badge selection is temporary view state.
- Native Settings shows all seven validated preferences and sends exact values.
  Backup stays an explicit command; artwork progress/retry belongs in setup and root.
- Notification banners use `terminal-notifier` when available, otherwise they
  are skipped. AppleScript notification fallback is excluded because it can
  open Script Editor when clicked.

Exact geometry, color meanings, states, badge rules, and accessibility
requirements live in [Brand Styles](brand.md), rather than being repeated here.

### Terminal handoffs and visual previews

Terminal windows use the largest shared profile that fits the display, preferably
beside the open panel. Ghostty gets one isolated process with a fixed BuddyMon
title, saved-state/fullscreen behavior disabled, and a clean `zsh -df` startup.
The launcher never resizes unrelated windows or closes them during fallback;
it tries another terminal only if Ghostty rejects the launch before acceptance.

**Why:** Collection views need space, but handoffs must not disturb existing work.

Menu-bar demos use temporary local payloads and the existing native status item.
They never change trainer state or journal history, never open the dropdown,
and return to the latest live status. Previews stay out of the product's navigation.

**Why:** Visual QA should prove the real renderer without becoming gameplay.

## Releases: prove what people download

**Decision:** `VERSION` is canonical; Python archives and Pillow wheels are
locked by exact URL, version, platform, and SHA-256. The public packager enforces
metadata, signing, notarization, stapling, assessment, and checksums.

**Why:** A tag must identify rebuildable inputs, and a successful source build
must not be mistaken for a working download.

Publication requires verification of the **final artifact**, recorded fresh-user
acceptance, and passing CI. Local builds remain development artifacts until
those gates pass. The complete checklist is [Public Release QA](release-qa.md).
