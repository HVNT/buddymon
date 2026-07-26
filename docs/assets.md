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

The native Trainer Card draws BuddyMon's original two-tone trainer silhouette
with `BuddyMonBrand` colors. It does not bundle or fetch an external trainer
portrait.

The native status item prioritizes compacted, species-specific Gen 5 frames so
its buddy matches the Pokémon shown in the native panel. If that pack is not
installed, it falls back through box art, Gen 2 menu icons, and built-in art.
Gen 2 menu icons are a legacy fallback because several species share category
icons such as `BIGMON`; they must not replace more recognizable per-species art.

Ghostty and iTerm2 can show inline PNG sprites in the terminal menu. Plain
terminals use terminal-safe pixel art.
