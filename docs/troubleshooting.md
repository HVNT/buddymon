# <img src="assets/brand/icons/setup.png" width="28" height="28" alt=""> Troubleshooting

**Start with the symptom. Most Mac app fixes are available from its menu-bar panel.**
Commands below are for a source checkout unless they open an installed app.

| Problem | Go to |
| --- | --- |
| Can't find the app | [App visibility](#app-visibility) |
| Old setup screen or missing Python | [Installed build](#installed-build) |
| Save cannot be loaded | [State Needs Care](#state-needs-care) |
| Missing Pokémon artwork | [Artwork](#artwork) |
| Progress or token totals look stuck | [Activity and reports](#activity-and-reports) |
| Party or Box will not open | [Terminal handoffs](#terminal-handoffs) |
| Broken terminal images | [Terminal sprites](#terminal-sprites) |
| Egg or missing Python in Claude | [Claude plugin](#claude-plugin) |
| SwiftBar-specific problems | [SwiftBar](#swiftbar) |

## App visibility

BuddyMon has **no Dock icon**. Look in the macOS menu bar. Open
**Applications → BuddyMon**, or run:

```bash
open /Applications/BuddyMon.app
```

Opening it again asks the running copy to show its panel. To start at login,
add BuddyMon in **System Settings → General → Login Items**.

If it is not installed, follow [Build from source](../README.md#build-from-source).
`.build/macos/BuddyMon.app` is a development output, not the installed copy.

## Installed build

An old running build can show **First Signal even though a buddy exists** or
report **Python is missing**. Replace it with a current self-contained build:

```bash
scripts/build-macos-app.sh --friend --install --open
```

The installer stops the running app before replacing `/Applications/BuddyMon.app`.
A self-contained app includes Python and Pillow. If you are deliberately using
a prepared runtime, see [runtime options](development.md#runtime-options).

If First Signal still appears, check whether this launch uses a different
`XDG_STATE_HOME`; do not delete the existing save to fix a path mismatch.

## State Needs Care

**Keep the original save.** This message means BuddyMon cannot safely read
existing state; normal writes are blocked rather than replacing it with a new game.

1. Make a copy of `~/.local/state/buddymon/state.json`, or
   `$XDG_STATE_HOME/buddymon/state.json` if configured.
2. Follow the error: update BuddyMon for a newer-version save, check access for
   an unreadable file, or restore a known-good backup for damaged state.
3. Move the file aside only if you deliberately want to start a new game.

Valid older saves preserve their original under `recovery/` before migration.
Manual backups live in `~/Documents/BuddyMon Backups`.

## Artwork

The Mac app downloads art automatically. If **Art download paused · Retry**
appears, reconnect and click **Retry**, or reopen BuddyMon. Completed sprites
and progress stay saved; fallback art keeps the game usable.

For plugin-only play, run `/buddymon:official`. CLI equivalents:

```bash
python3 buddymon.py install-assets
python3 buddymon.py install-assets --refresh
```

The second command explicitly refreshes packs. A failed refresh preserves the
last working copy. See [Assets](assets.md) for pack-specific options and fallbacks.

## Activity and reports

### Progress is not moving

1. Choose a starter and keep BuddyMon open.
2. Create **new** Claude Code, Codex CLI, or Auggie activity after the first scan.
   The first scan anchors old logs; Gemini CLI only contributes to token reports.
3. Allow the five-minute collection interval, or run an immediate collection:

```bash
python3 buddymon.py collect
```

If it fails, check the reported error and that the state directory is writable.
The Claude plugin is optional. For collection after quitting the app, explicitly
install the [collection service](development.md#collection-service).

### Token Usage is loading

The first history scan runs in the background. Keep using Back or close the
panel; totals appear automatically when ready. Same-day refreshes keep the saved
report; a new day shows loading again. Use **Refresh** to retry a failed scan.

### The app shows old terminal state

Reopen the panel or use **⌘R / Refresh**. Saved terminal changes normally appear
automatically; a 30-second recovery refresh handles missed file events.

### A wild is waiting

Open the encounter and finish it. **Quick** pauses for every shiny and
legendary/mythical, but resolves non-shiny rare encounters automatically.
**Safari** and **Battle** wait for every wild.

## Terminal handoffs

Party, Box, Pokédex, and Activity open the terminal game. Trainer and Settings
stay native. First check the terminal game directly:

```bash
python3 buddymon.py menu
```

If one terminal fails, choose another installed **Menu launcher** in native
Settings, or try:

```bash
python3 buddymon.py open-menu settings --launcher iterm
python3 buddymon.py open-menu settings --launcher terminal
```

Record any Automation dialog and whether you allowed or denied it. A cancelled
handoff should leave the native app usable.

Ghostty uses one isolated BuddyMon window and a clean shell to avoid startup
prompts. It does not need Accessibility access or resize your existing windows.
If an older build creates extra windows, update BuddyMon and restart SwiftBar
if used. Close old extras manually; iTerm2 and Terminal.app open a new window
per click.

## Terminal sprites

Ghostty and iTerm2 support inline PNGs. Other terminals use text-safe art.
To disable inline images:

```bash
BUDDYMON_NO_GRAPHICS=1 python3 buddymon.py menu
```

## Claude plugin

| Symptom | Fix |
| --- | --- |
| Statusline shows an egg | Run `/buddymon:choose pikachu`. If a buddy already exists, restart Claude Code so it reloads the plugin. |
| `python3` not found | Run `python3 --version` in the environment Claude starts from. Install Python 3 if absent, then restart Claude Code. |

The source plugin needs Python on `PATH`; the self-contained Mac app carries
its own runtime. Plugin wiring must not rewrite `~/.claude/settings.json`.

## SwiftBar

**Stale output:** restart its long-lived menu stream:

```bash
osascript -e 'quit app "SwiftBar"'
open -a SwiftBar
```

**SwiftBar's own icon is visible:** enable Stealth Mode, then restart:

```bash
defaults write com.ameba.SwiftBar StealthMode -bool YES
osascript -e 'quit app "SwiftBar"'
open -a SwiftBar
```

**Unexpected Script Editor banners:** current BuddyMon never uses AppleScript
notifications. It uses `terminal-notifier` when installed and otherwise keeps
rare moments inside BuddyMon. Update old code if that behavior persists.

**Next:** [Mac app guide](macos-app.md) for normal use or
[Development](development.md) for build diagnostics.
