# Assets

BuddyMon has two kinds of art.

## Committed Art

The fallback chibi sprites in `lib/sprites.py` are original project art and are
safe to keep in git.

## Local-Only Packs

Optional packs are generated into:

```
~/.local/state/buddymon/packs/
```

They include:

- Gen 2 menu icons from `pret/pokecrystal`
- box icons/palettes from PokéSprite-derived sources
- Gen 5 animated sprites from PokeAPI sprite mirrors

These improve the look, but they are not repo assets. Do not commit generated
pack JSON.

## Rule

Runtime can use local packs if present. If a pack is missing, BuddyMon falls
back to committed art.
