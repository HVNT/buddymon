"""Deterministic collectible appraisals derived from a Pokemon copy id."""

import hashlib
from dataclasses import dataclass


_IV_NAMESPACE = b"buddymon-iv-v1\0"


@dataclass(frozen=True)
class Appraisal:
    attack: int
    defense: int
    hp: int
    total: int
    percent: int
    stars: int


def _stars_for_total(total):
    if total == 45:
        return 4
    if total >= 37:
        return 3
    if total >= 30:
        return 2
    if total >= 23:
        return 1
    return 0


def appraise(pokemon_id: str) -> Appraisal:
    """Return stable Pokemon GO-style 0-15 values for one caught copy."""
    if not isinstance(pokemon_id, str) or not pokemon_id.strip():
        raise ValueError("pokemon_id must be non-empty text")

    digest = hashlib.sha256(_IV_NAMESPACE + pokemon_id.encode()).digest()
    attack, defense, hp = (digest[index] & 0x0F for index in range(3))
    total = attack + defense + hp
    percent = (total * 100 + 22) // 45
    return Appraisal(
        attack=attack,
        defense=defense,
        hp=hp,
        total=total,
        percent=percent,
        stars=_stars_for_total(total),
    )
