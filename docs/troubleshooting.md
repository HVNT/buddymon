# Troubleshooting

## The statusline shows an egg

Choose a starter:

```text
/buddymon:choose pikachu
```

If a starter already exists, restart Claude Code or SwiftBar so it reloads the
plugin.

## BuddyMon.app is missing

Open the installed app again:

```bash
open /Applications/BuddyMon.app
```

The app is intentionally visible only in the menu bar. Opening it again asks
the already-running copy to show its panel. Add BuddyMon in **System Settings >
General > Login Items** if you want it to reopen after login.

BuddyMon never uses Script Editor for notifications. Optional external banners
use `terminal-notifier` when it is already installed; without it, rare moments
remain visible in BuddyMon instead of falling back to an AppleScript banner.

If the installed app is missing, rebuild, install, and open a self-contained build:

```bash
scripts/build-macos-app.sh --friend --install --open
```

`.build/macos/BuddyMon.app` is the development build output; it is not the
installed copy.

## First Signal appears even though a buddy exists

The installed process is older than the state format it is reading. Trainer
state is not erased; quit the stale process and replace the installed app:

```bash
scripts/build-macos-app.sh --friend --install --open
```

The install command now stops the running BuddyMon process before replacing and
opening `/Applications/BuddyMon.app`, so the new binary—not an old in-memory
copy—handles the state.

## BuddyMon.app says Python is missing

Rebuild and replace the installed self-contained version:

```bash
scripts/build-macos-app.sh --friend --install --open
```

If you supply a prepared runtime, point the build at it:

```bash
BUDDYMON_PYTHON_RUNTIME=/path/to/runtime scripts/build-macos-app.sh --friend --install --open
```

A user should not need a separate Python or Pillow install.

## BuddyMon says State Needs Care

BuddyMon found an existing `state.json` that it cannot safely use. Corrupt,
unreadable, structurally invalid, and newer-version files block every normal
write; BuddyMon does not replace them with a new game.

First make a copy of
`$XDG_STATE_HOME/buddymon/state.json`, or
`~/.local/state/buddymon/state.json` by default. Restore a known-good backup or
update BuddyMon if the message says the state came from a newer release. Move
the file aside only when you deliberately want to start over. Valid older
states preserve a pre-migration copy under the local `recovery/` directory.

## Optional art is missing or failed

Plain fallback art is valid and never blocks the app. BuddyMon does not download
optional art automatically.

From the Claude Code plugin, run `/buddymon:official` and confirm the download.
From the CLI:

```bash
python3 buddymon.py install-assets
python3 buddymon.py install-assets --refresh
```

The result identifies each pack that succeeded, was skipped, or failed. A
failed refresh keeps the last working pack. See [Assets](assets.md) for details.

## XP is not moving

Run one immediate collection:

```bash
python3 buddymon.py collect
```

Then check that a starter exists, Claude hooks came from the plugin, and the
BuddyMon state directory is writable. State lives under
`$XDG_STATE_HOME/buddymon`, defaulting to
`~/.local/state/buddymon`.

For collection while the app is closed:

```bash
python3 buddymon.py collector status
python3 buddymon.py collector install
```

Install is explicit and safe to run again when runtime or repo paths changed.
Use `collector uninstall` to remove the generated LaunchAgent.

## BuddyMon.app shows old terminal state

Opening the dropdown requests fresh local status, and saved terminal changes
normally propagate automatically without waiting for a menu-bar animation. Use
the dropdown's **Refresh** command if a filesystem notification was missed. The
app also performs a recovery refresh every 30 seconds.

## SwiftBar shows stale output

Restart SwiftBar:

```bash
osascript -e 'quit app "SwiftBar"'
open -a SwiftBar
```

Its menu stream is long-lived and may still have old code loaded.

## Claude Code reports `python3` not found

The source plugin invokes `python3` for its status line and hooks. Confirm that
Python 3 is on the same `PATH` Claude Code receives:

```bash
python3 --version
```

If that command fails, install Python 3 and restart Claude Code before
reinstalling the plugin.

## A terminal shortcut does nothing

The native Party, Box, Pokédex, and Activity links hand off to the terminal UI.
Settings stays inside the compact native panel. SwiftBar actions use the same
launcher path.

Run the menu directly:

```bash
python3 buddymon.py menu
```

If Ghostty is the problem, try another launcher:

```bash
python3 buddymon.py open-menu settings --launcher iterm
python3 buddymon.py open-menu settings --launcher terminal
```

Then choose a permanent **Menu launcher** in native Settings.

Terminal handoffs request roughly a 760-by-520 footprint beside the open
BuddyMon panel. Ghostty receives one direct isolated-window request with an
88-by-30 grid, a fixed BuddyMon title, and saved-state/fullscreen behavior
disabled. That window starts the system shell and safely injects BuddyMon as its
startup command, so Ghostty does not treat the bundled Python runtime as a file
that needs confirmation. It does not need Accessibility access, create a
provisional window, or close a live window before falling back. iTerm2 and
Terminal.app apply exact bounds through their own scripting APIs.

## SwiftBar opens extra terminal windows

Update BuddyMon and restart SwiftBar. Current Ghostty handoffs launch exactly
one isolated BuddyMon window and replace only an earlier isolated BuddyMon
process. iTerm2 and Terminal.app open one new window per click. Close any
legacy extra once, or use `python3 buddymon.py menu` in an existing terminal.

## SwiftBar's own icon is visible

Enable SwiftBar Stealth Mode:

```bash
defaults write com.ameba.SwiftBar StealthMode -bool YES
osascript -e 'quit app "SwiftBar"'
open -a SwiftBar
```

## Terminal sprites look wrong

Ghostty and iTerm2 can show inline PNGs. Other terminals use text-safe pixel
art. Disable inline images when needed:

```bash
BUDDYMON_NO_GRAPHICS=1 python3 buddymon.py menu
```

## A wild is waiting

Open the app, SwiftBar menu, or terminal menu and finish the encounter. Quick
mode pauses only for rare and legendary encounters; Safari and Battle pause for
every wild.
