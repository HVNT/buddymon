"""Favorites data layer: per-individual stars for a curated team / switch list.

Pure and stdlib-only — no rendering, no state I/O, no engine — so it stays
testable and free of import cycles. A favorite is a boolean "favorite" flag on
an individual entry in state["pokemon"]; an absent flag means not favorited.
"""

AUTO_FAVORITE_RARITIES = {"legendary", "mythic", "starter"}


def _level(p):
    try:
        return int(p.get("level") or 0)
    except (TypeError, ValueError):
        return 0


def _name(p):
    return p.get("name") or ""


def is_favorite(pokemon):
    """Whether this individual is starred."""
    return bool(pokemon.get("favorite"))


def set_favorite(pokemon, value=True):
    """Star or unstar this individual in place."""
    pokemon["favorite"] = bool(value)


def toggle(state, copy_id):
    """Flip the favorite flag on the individual whose id == copy_id and return
    the new boolean. Return None if no such individual exists."""
    for p in (state or {}).get("pokemon", []) or []:
        if p.get("id") == copy_id:
            new_value = not is_favorite(p)
            set_favorite(p, new_value)
            return new_value
    return None


def _sort_key(p):
    """Level desc, then name case-insensitive, then str(id) for stability. id
    may be a str or int, so str(id) never raises on mixed types."""
    return (-_level(p), _name(p).lower(), str(p.get("id")))


def favorites(state):
    """The favorited individuals, sorted by level desc, name, then id."""
    starred = [p for p in (state or {}).get("pokemon", []) or [] if is_favorite(p)]
    return sorted(starred, key=_sort_key)


def count(state):
    """How many individuals are favorited."""
    return len(favorites(state))


def should_auto_favorite(pokemon):
    """True if shiny or its rarity is auto-favorited (legendary/mythic/starter).
    Used by the catch path to auto-star notable catches."""
    return bool(pokemon.get("shiny")) or pokemon.get("rarity") in AUTO_FAVORITE_RARITIES
