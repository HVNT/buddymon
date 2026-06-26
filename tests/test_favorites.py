"""Favorites data layer: starring individuals, sorting, and auto-favorite."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import favorites


def mon(id, name, level=1, **extra):
    p = {"id": id, "name": name, "level": level, "rarity": "common", "shiny": False}
    p.update(extra)
    return p


def test_is_favorite_default_false():
    assert favorites.is_favorite(mon(1, "Rattata")) is False


def test_is_favorite_true():
    assert favorites.is_favorite(mon(1, "Rattata", favorite=True)) is True


def test_set_favorite_sets_bool():
    p = mon(1, "Rattata")
    favorites.set_favorite(p)
    assert p["favorite"] is True
    favorites.set_favorite(p, 0)
    assert p["favorite"] is False
    favorites.set_favorite(p, "yes")
    assert p["favorite"] is True


def test_toggle_flips_and_returns_new_value():
    state = {"pokemon": [mon(1, "Pidgey")]}
    assert favorites.toggle(state, 1) is True
    assert state["pokemon"][0]["favorite"] is True
    assert favorites.toggle(state, 1) is False
    assert state["pokemon"][0]["favorite"] is False


def test_toggle_unknown_id_returns_none():
    state = {"pokemon": [mon(1, "Pidgey")]}
    assert favorites.toggle(state, 99) is None


def test_toggle_persists_onto_entry():
    state = {"pokemon": [mon("a", "Abra")]}
    favorites.toggle(state, "a")
    assert favorites.is_favorite(state["pokemon"][0]) is True


def test_favorites_returns_only_starred_sorted():
    state = {"pokemon": [
        mon(1, "Zubat", level=5, favorite=True),
        mon(2, "Geodude", level=20),  # not favorited
        mon(3, "Charizard", level=36, favorite=True),
        mon(4, "Arbok", level=22, favorite=True),
    ]}
    result = favorites.favorites(state)
    assert [p["id"] for p in result] == [3, 4, 1]


def test_favorites_sorts_name_within_level_tie():
    state = {"pokemon": [
        mon(1, "zubat", level=10, favorite=True),
        mon(2, "Abra", level=10, favorite=True),
        mon(3, "Machop", level=10, favorite=True),
    ]}
    result = favorites.favorites(state)
    assert [p["name"] for p in result] == ["Abra", "Machop", "zubat"]


def test_favorites_tolerates_missing_level_and_name():
    state = {"pokemon": [
        {"id": 1, "favorite": True},
        mon(2, "Onix", level=30, favorite=True),
    ]}
    result = favorites.favorites(state)
    assert [p["id"] for p in result] == [2, 1]


def test_favorites_mixed_id_types_no_raise():
    state = {"pokemon": [
        mon(1, "Eevee", level=5, favorite=True),
        mon("b", "Eevee", level=5, favorite=True),
    ]}
    result = favorites.favorites(state)
    assert {p["id"] for p in result} == {1, "b"}


def test_count():
    state = {"pokemon": [
        mon(1, "Rattata", favorite=True),
        mon(2, "Pidgey"),
        mon(3, "Spearow", favorite=True),
    ]}
    assert favorites.count(state) == 2


def test_should_auto_favorite_shiny():
    assert favorites.should_auto_favorite(mon(1, "Magikarp", shiny=True)) is True


def test_should_auto_favorite_legendary():
    assert favorites.should_auto_favorite(mon(1, "Mewtwo", rarity="legendary")) is True


def test_should_auto_favorite_mythic():
    assert favorites.should_auto_favorite(mon(1, "Mew", rarity="mythic")) is True


def test_should_auto_favorite_starter():
    assert favorites.should_auto_favorite(mon(1, "Bulbasaur", rarity="starter")) is True


def test_should_auto_favorite_false_for_common():
    assert favorites.should_auto_favorite(mon(1, "Rattata", rarity="common")) is False


def test_none_state_handling():
    assert favorites.favorites(None) == []
    assert favorites.count(None) == 0
    assert favorites.toggle(None, 1) is None


def test_empty_state_handling():
    assert favorites.favorites({}) == []
    assert favorites.count({}) == 0
    assert favorites.toggle({}, 1) is None
