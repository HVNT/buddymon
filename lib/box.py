"""Box browser data layer: every individual caught pokemon, duplicates and all.

Pure and stdlib-only — no rendering, no state I/O — so it stays testable and
free of import cycles. Catches live in state["pokemon"] as a flat list with no
dedupe, so two entries can share the same species name.
"""


def _level(p):
    try:
        return int(p.get("level") or 0)
    except (TypeError, ValueError):
        return 0


def _caught_at(p):
    try:
        return float(p.get("caught_at") or 0)
    except (TypeError, ValueError):
        return 0.0


def _copy_key(p):
    """Sort key: level desc, caught_at desc, then id for stability. id may be a
    str or int, so str(id) is the final tiebreaker and never raises."""
    return (-_level(p), -_caught_at(p), str(p.get("id")))


def group_by_species(pokemon):
    """One group per distinct species name (no dedupe), sorted by name.

    Each group: {"name", "type", "rarity", "emoji", "count", "copies"} where the
    display fields come from the best copy and copies is the sorted individuals.
    """
    groups = {}
    for p in pokemon or []:
        groups.setdefault(p.get("name", ""), []).append(p)

    result = []
    for name, copies in groups.items():
        copies = sorted(copies, key=_copy_key)
        best = copies[0]
        result.append({
            "name": name,
            "type": best.get("type", ""),
            "rarity": best.get("rarity", ""),
            "emoji": best.get("emoji", "•"),
            "count": len(copies),
            "copies": copies,
        })
    result.sort(key=lambda g: g["name"].lower())
    return result


def expand(pokemon):
    """Flat list of every individual (no dedupe), each a shallow copy with
    copy_index (1-based within its species) and copy_total added. Sorted by
    name (case-insensitive), then level desc, caught_at desc, id."""
    out = []
    for group in group_by_species(pokemon):
        total = group["count"]
        for index, p in enumerate(group["copies"], start=1):
            item = dict(p)
            item["copy_index"] = index
            item["copy_total"] = total
            out.append(item)
    return out


def total_copies(pokemon):
    """Total individuals caught, duplicates included."""
    return len(pokemon or [])


def find_copy(pokemon, copy_id):
    """The individual whose id == copy_id, else None."""
    for p in pokemon or []:
        if p.get("id") == copy_id:
            return p
    return None
