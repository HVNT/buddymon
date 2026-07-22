"""Canonical National Dex identity shared by runtime and asset tools."""

import re

from .dex_roster import DEX_NUMBERS


NATIONAL_DEX_MAX = 649
GEN2_DEX_MAX = 251
ALL_SPECIES = tuple(sorted(DEX_NUMBERS, key=DEX_NUMBERS.__getitem__))
GEN2_SPECIES = tuple(
    name for name in ALL_SPECIES if DEX_NUMBERS[name] <= GEN2_DEX_MAX
)


def slug(name):
    """Return the stable filename slug for one canonical species name."""
    normalized = (
        name.lower()
        .replace("♀", "-f")
        .replace("♂", "-m")
        .replace("'", "")
        .replace(".", "")
    )
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
