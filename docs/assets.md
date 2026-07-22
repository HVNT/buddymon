# Assets

Art packs are optional. BuddyMon uses its built-in sprites when they are not
installed.

By default, downloaded packs live in:

```
~/.local/state/buddymon/packs/
```

They include:

- Gen 2 menu icons from `pret/pokecrystal`
- box icons/palettes from PokéSprite-derived sources
- Gen 5 animated sprites from PokeAPI sprite mirrors

When `XDG_STATE_HOME` is set, BuddyMon uses
`$XDG_STATE_HOME/buddymon/packs/` instead. Packs are local-only; do not commit
their generated JSON.

The compact app never downloads art automatically. From the Claude Code plugin,
`/buddymon:official` asks before installing missing packs. From the CLI, install
only missing packs with:

```
python3 buddymon.py install-assets
```

Refresh every installed pack with:

```
python3 buddymon.py install-assets --refresh
```

`--force` remains an alias for `--refresh` for older scripts.

Both commands use the network. A failed install or refresh keeps the last
working copy of each pack.

Runtime uses local packs when present and otherwise falls back to the original
sprites in `lib/sprites.py`.

The native Trainer Card has one bounded bundled exception:
`macos/BuddyMonApp/Resources/TrainerRedFRLG.png`. It is the exact 64-by-64
Red Trainer Card pose from the FireRed/LeafGreen
[Player Sprites sheet](https://www.spriters-resource.com/game_boy_advance/pokemonfireredleafgreen/asset/52432/),
uploaded there by FrenchOrange. BuddyMon removes only the sheet's orange
background and preserves the game pixels. The extracted PNG SHA-256 is
`b9455d9dde99f00d1d93430b62ba320284f894fba315d02144c2b5a7163c61b3`.
It is copyrighted game art, not a freely licensed BuddyMon asset.

The native status item prioritizes compacted, species-specific Gen 5 frames so
its buddy matches the Pokémon shown in the native panel. If that pack is not
installed, it falls back through box art, Gen 2 menu icons, and built-in art.
Gen 2 menu icons are a legacy fallback because several species share category
icons such as `BIGMON`; they must not replace more recognizable per-species art.

Ghostty and iTerm2 can show inline PNG sprites in the terminal menu. Plain
terminals use terminal-safe pixel art.
