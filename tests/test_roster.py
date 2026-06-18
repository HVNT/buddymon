"""Full 251 roster integrity tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import data, sprites
from tools import fetch_official as fo

STARTER_FORMS = set(data.STARTERS) | {
    e for i in data.STARTERS.values() for e, _, _ in i["evolutions"]
} | {n for n, _ in data.EEVEE_BRANCHES}


def test_total_is_649():
    assert len(data.WILDS) + len(STARTER_FORMS) == 649


def test_no_starter_line_in_wilds():
    assert STARTER_FORMS.isdisjoint(data.WILDS)


def test_every_entry_well_formed():
    for name, (ptype, emoji, rarity) in data.WILDS.items():
        assert ptype in sprites.TYPE_TINTS, f"{name}: bad type {ptype}"
        assert rarity in ("common", "uncommon", "rare", "legendary"), name
        assert emoji, f"{name}: empty emoji"


def test_legendaries_span_all_gens():
    legends = {n for n, v in data.WILDS.items() if v[2] == "legendary"}
    # PokéAPI flags legendary + mythical; 48 across Gen 1-5.
    assert len(legends) == 48
    # spot-check one legendary per generation
    for n in ("Mewtwo", "Lugia", "Rayquaza", "Dialga", "Reshiram"):
        assert n in legends, f"{n} should be legendary"


def test_authentic_types_spot_check():
    cases = {"Gyarados": "Water", "Gengar": "Ghost", "Lugia": "Psychic",
             "Umbreon": "Dark", "Tyranitar": "Rock", "Mareep": "Electric",
             "Lucario": "Fighting", "Garchomp": "Dragon", "Zoroark": "Dark"}
    for name, ptype in cases.items():
        assert data.WILDS[name][0] == ptype, f"{name} should be {ptype}"
