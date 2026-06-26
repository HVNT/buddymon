"""Box browser data-layer tests: grouping, expansion, and lookup (pure)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import box


def mon(id, name, level, caught_at=0, **extra):
    """Build a synthetic pokemon dict. Extra keys override/augment defaults."""
    d = {
        "id": id,
        "name": name,
        "level": level,
        "caught_at": caught_at,
        "type": "Normal",
        "rarity": "common",
        "emoji": "•",
    }
    d.update(extra)
    return d


# --- group_by_species --------------------------------------------------------

def test_group_by_species_keeps_duplicates():
    mons = [
        mon(1, "Gastly", 10, caught_at=100),
        mon(2, "Gastly", 12, caught_at=200),
        mon(3, "Pidgey", 5, caught_at=50),
    ]
    groups = box.group_by_species(mons)
    by_name = {g["name"]: g for g in groups}

    assert set(by_name) == {"Gastly", "Pidgey"}

    gastly = by_name["Gastly"]
    assert gastly["count"] == 2
    assert len(gastly["copies"]) == 2

    pidgey = by_name["Pidgey"]
    assert pidgey["count"] == 1
    assert len(pidgey["copies"]) == 1


def test_group_dict_has_expected_keys():
    groups = box.group_by_species([mon(1, "Gastly", 10, emoji="👻",
                                       type="Ghost", rarity="rare")])
    g = groups[0]
    assert set(g) >= {"name", "type", "rarity", "emoji", "count", "copies"}
    assert g["name"] == "Gastly"
    assert g["type"] == "Ghost"
    assert g["rarity"] == "rare"
    assert g["emoji"] == "👻"
    assert g["count"] == 1


def test_groups_sorted_by_name_case_insensitive():
    mons = [
        mon(1, "zubat", 5),
        mon(2, "Abra", 5),
        mon(3, "Machop", 5),
        mon(4, "bulbasaur", 5),
    ]
    names = [g["name"] for g in box.group_by_species(mons)]
    assert names == sorted(names, key=str.lower)
    assert names == ["Abra", "bulbasaur", "Machop", "zubat"]


def test_copies_sorted_level_desc_then_caught_at_desc():
    mons = [
        mon(1, "Gastly", 10, caught_at=100),
        mon(2, "Gastly", 30, caught_at=50),
        mon(3, "Gastly", 20, caught_at=400),
        mon(4, "Gastly", 20, caught_at=900),  # same level as #3, newer caught_at
    ]
    copies = box.group_by_species(mons)[0]["copies"]
    assert [c["id"] for c in copies] == [2, 4, 3, 1]


# --- expand ------------------------------------------------------------------

def test_expand_returns_one_item_per_individual():
    mons = [
        mon(1, "Gastly", 10),
        mon(2, "Gastly", 12),
        mon(3, "Pidgey", 5),
    ]
    expanded = box.expand(mons)
    assert len(expanded) == len(mons) == 3


def test_expand_annotates_copy_index_and_total():
    mons = [
        mon(1, "Gastly", 10, caught_at=100),
        mon(2, "Gastly", 12, caught_at=200),
        mon(3, "Pidgey", 5),
    ]
    expanded = box.expand(mons)
    gastly = [e for e in expanded if e["name"] == "Gastly"]
    pidgey = [e for e in expanded if e["name"] == "Pidgey"]

    # Higher level (id 2) comes first -> copy_index 1.
    assert [g["copy_index"] for g in gastly] == [1, 2]
    assert all(g["copy_total"] == 2 for g in gastly)
    assert gastly[0]["id"] == 2
    assert gastly[1]["id"] == 1

    assert pidgey[0]["copy_index"] == 1
    assert pidgey[0]["copy_total"] == 1


def test_expand_is_shallow_copy_not_aliasing_input():
    src = mon(1, "Gastly", 10)
    expanded = box.expand([src])
    item = expanded[0]
    assert item is not src
    item["level"] = 999
    item["copy_index"] = 42
    # Original untouched.
    assert src["level"] == 10
    assert "copy_index" not in src


def test_expand_overall_sort_order():
    mons = [
        mon(1, "Pidgey", 5),
        mon(2, "Gastly", 10, caught_at=100),
        mon(3, "Gastly", 20, caught_at=50),
        mon(4, "Gastly", 20, caught_at=300),  # tie level w/ #3, newer
        mon(5, "abra", 99),
    ]
    expanded = box.expand(mons)
    # name ci: abra, Gastly, Pidgey; within Gastly: level desc, caught_at desc.
    assert [e["id"] for e in expanded] == [5, 4, 3, 2, 1]


# --- total_copies ------------------------------------------------------------

def test_total_copies_equals_len_input():
    mons = [mon(i, "Gastly", 10) for i in range(7)]
    assert box.total_copies(mons) == 7


# --- find_copy ---------------------------------------------------------------

def test_find_copy_returns_matching_individual():
    mons = [
        mon(1, "Gastly", 10),
        mon(2, "Gastly", 12),
        mon(3, "Pidgey", 5),
    ]
    found = box.find_copy(mons, 2)
    assert found is not None
    assert found["id"] == 2
    assert found["name"] == "Gastly"


def test_find_copy_unknown_id_returns_none():
    mons = [mon(1, "Gastly", 10)]
    assert box.find_copy(mons, 999) is None


# --- empty input -------------------------------------------------------------

def test_empty_input_behavior():
    assert box.group_by_species([]) == []
    assert box.expand([]) == []
    assert box.total_copies([]) == 0
    assert box.find_copy([], "x") is None


# --- missing fields ----------------------------------------------------------

def test_missing_caught_at_and_level_treated_as_zero():
    a = {"id": 1, "name": "Gastly"}  # no level, no caught_at, no emoji
    b = {"id": 2, "name": "Gastly", "level": 5, "caught_at": 10}
    mons = [a, b]

    # group_by_species must not raise and orders the leveled one first.
    groups = box.group_by_species(mons)
    assert len(groups) == 1
    g = groups[0]
    assert g["count"] == 2
    assert [c["id"] for c in g["copies"]] == [2, 1]
    assert g["emoji"] == "•"  # default emoji for missing

    # expand must not raise either, same order.
    expanded = box.expand(mons)
    assert [e["id"] for e in expanded] == [2, 1]
    assert [e["copy_index"] for e in expanded] == [1, 2]
