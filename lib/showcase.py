"""Showcase slots: curated podiums for displaying caught Pokemon.

The showcase is intentionally separate from favorites, Party, Box, and Pokedex.
Slots are empty by default and store individual Pokemon ids when assigned.
"""

DEFAULT_SLOT_COUNT = 6


def showcase_slots(state, count=DEFAULT_SLOT_COUNT):
    """Return exactly count slot values, padding missing state with None."""
    data = state.get("showcase") if isinstance(state, dict) else None
    raw = data.get("slots") if isinstance(data, dict) else []
    slots = list(raw) if isinstance(raw, list) else []
    if len(slots) < count:
        slots += [None] * (count - len(slots))
    return slots[:count]


def _ensure_showcase(state, count=DEFAULT_SLOT_COUNT):
    state.setdefault("showcase", {})
    slots = showcase_slots(state, count)
    state["showcase"]["slots"] = slots
    return slots


def set_showcase_slot(state, index, pokemon_id, count=DEFAULT_SLOT_COUNT):
    """Assign a Pokemon id to a slot. Returns True when index is valid."""
    if index < 0 or index >= count:
        return False
    slots = _ensure_showcase(state, count)
    slots[index] = pokemon_id
    return True


def clear_showcase_slot(state, index, count=DEFAULT_SLOT_COUNT):
    """Clear a slot back to an intentional empty podium."""
    return set_showcase_slot(state, index, None, count)


def _pokemon_by_id(state):
    return {p.get("id"): p for p in state.get("pokemon", [])}


def showcase_entries(state, count=DEFAULT_SLOT_COUNT):
    """Return display entries for every slot.

    Each entry contains:
    - slot: zero-based slot index
    - pokemon_id: assigned id or None
    - pokemon: matching Pokemon dict or None
    - missing: True when an assigned id no longer exists
    """
    by_id = _pokemon_by_id(state if isinstance(state, dict) else {})
    entries = []
    for index, pokemon_id in enumerate(showcase_slots(state or {}, count)):
        pokemon = by_id.get(pokemon_id)
        entries.append({
            "slot": index,
            "pokemon_id": pokemon_id,
            "pokemon": pokemon,
            "missing": pokemon_id is not None and pokemon is None,
        })
    return entries
