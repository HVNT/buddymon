"""Canonical National Dex roster and asset identity tests."""

from lib import packs, species
from tools import fetch_gen5, fetch_official


def test_canonical_rosters_cover_gen2_and_national_dex_in_order():
    assert len(species.GEN2_SPECIES) == 251
    assert len(species.ALL_SPECIES) == 649
    assert [species.DEX_NUMBERS[name] for name in species.GEN2_SPECIES] == list(
        range(1, 252)
    )
    assert [species.DEX_NUMBERS[name] for name in species.ALL_SPECIES] == list(
        range(1, 650)
    )
    assert fetch_official.dex_species() == list(species.GEN2_SPECIES)
    assert fetch_gen5.dex_names() == {
        number: name for name, number in species.DEX_NUMBERS.items()
    }


def test_species_slugs_are_unique_and_gender_safe_across_national_dex():
    slugs = [species.slug(name) for name in species.ALL_SPECIES]

    assert len(slugs) == len(set(slugs)) == 649
    assert species.slug("Nidoran♀") == "nidoran-f"
    assert species.slug("Nidoran♂") == "nidoran-m"
    assert fetch_official.pokesprite_slug("Nidoran♀") == "nidoran-f"
    assert fetch_gen5._slug("Nidoran♂") == "nidoran-m"
    assert packs._gen5_slug("Nidoran♀") == "nidoran-f"
