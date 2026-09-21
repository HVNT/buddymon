"""Deterministic collectible appraisals derived from a Pokemon copy id."""

import hashlib
from dataclasses import dataclass


_IV_NAMESPACE = b"buddymon-iv-v1\0"
STAT_MAX = 15
STAT_COUNT = 3
TOTAL_MAX = STAT_MAX * STAT_COUNT
STAR_MAX = 4


@dataclass(frozen=True)
class Appraisal:
    attack: int
    defense: int
    hp: int
    total: int
    percent: int
    stars: int

    @property
    def is_perfect(self):
        return self.total == TOTAL_MAX


def _stars_for_total(total):
    if total == TOTAL_MAX:
        return STAR_MAX
    if total >= 37:
        return 3
    if total >= 30:
        return 2
    if total >= 23:
        return 1
    return 0


def _percent_for_total(total):
    return (total * 100 + TOTAL_MAX // 2) // TOTAL_MAX


def appraise(pokemon_id: str) -> Appraisal:
    """Return stable Pokemon GO-style 0-15 values for one caught copy."""
    if not isinstance(pokemon_id, str) or not pokemon_id.strip():
        raise ValueError("pokemon_id must be non-empty text")

    digest = hashlib.sha256(_IV_NAMESPACE + pokemon_id.encode()).digest()
    attack, defense, hp = (digest[index] & STAT_MAX for index in range(STAT_COUNT))
    total = attack + defense + hp
    percent = _percent_for_total(total)
    return Appraisal(
        attack=attack,
        defense=defense,
        hp=hp,
        total=total,
        percent=percent,
        stars=_stars_for_total(total),
    )
