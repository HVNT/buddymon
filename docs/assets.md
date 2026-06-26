# Assets

Optional packs are generated into:

```
~/.local/state/buddymon/packs/
```

They include:

- Gen 2 menu icons from `pret/pokecrystal`
- box icons/palettes from PokéSprite-derived sources
- Gen 5 animated sprites from PokeAPI sprite mirrors

They are local-only. Do not commit generated pack JSON.

Runtime uses local packs when present. If a pack is missing, BuddyMon falls
back to the original sprites in `lib/sprites.py`.

Ghostty and iTerm2 can show inline PNG sprites in the terminal menu. Plain
terminals use terminal-safe pixel art.
