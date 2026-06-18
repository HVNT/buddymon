# Troubleshooting

## The statusline shows an egg

Pick a starter:

```
/buddymon:choose pikachu
```

If you already picked one, restart Claude Code or SwiftBar so it reloads the
plugin code.

## SwiftBar shows stale output

Restart SwiftBar:

```
osascript -e 'quit app "SwiftBar"' && open -a SwiftBar
```

The menu bar stream is long-lived, so it can keep old code in memory.

## SwiftBar's own icon is still visible

Enable Stealth Mode:

```
defaults write com.ameba.SwiftBar StealthMode -bool YES
osascript -e 'quit app "SwiftBar"' && open -a SwiftBar
```

## XP is not moving

Check the basics:

- A starter exists.
- Claude Code hooks are installed through the plugin.
- `~/.local/state/buddymon/state.json` is writable.
- If using Codex or Auggie XP, run `python3 buddymon.py collect` once.

## Sprites look plain

The built-in sprites are the fallback. Run `/buddymon:official` for Gen 2 menu
icons, or see [ASSETS.md](ASSETS.md) for the other local packs.

## A rare wild is waiting

Open the SwiftBar dropdown and use Safari or Battle actions. Rare encounters
wait for you instead of auto-resolving.
