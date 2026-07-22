"""Showcase slot model: empty podiums with manual per-id assignment."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import showcase


def mon(id, name="Pidgey", level=1):
    return {
        "id": id,
        "name": name,
        "type": "Flying",
        "emoji": "🐦",
        "rarity": "common",
        "level": level,
        "xp": 0,
        "shiny": False,
    }


def test_missing_showcase_means_empty_slots():
    state = {"pokemon": []}

    assert showcase.showcase_slots(state, count=3) == [None, None, None]

    entries = showcase.showcase_entries(state, count=3)
    assert [entry["pokemon"] for entry in entries] == [None, None, None]
    assert [entry["missing"] for entry in entries] == [False, False, False]


def test_set_and_clear_slot_are_additive():
    state = {"pokemon": [mon("a")]}

    assert showcase.set_showcase_slot(state, 1, "a", count=3) is True
    assert state["showcase"]["slots"] == [None, "a", None]

    assert showcase.clear_showcase_slot(state, 1, count=3) is True
    assert state["showcase"]["slots"] == [None, None, None]


def test_rejects_out_of_range_slot():
    state = {"pokemon": [mon("a")]}

    assert showcase.set_showcase_slot(state, 3, "a", count=3) is False
    assert "showcase" not in state


def test_entries_resolve_individual_ids_and_stale_ids():
    pidgey = mon("pidgey-1", "Pidgey", 4)
    state = {
        "pokemon": [pidgey, mon("pidgey-2", "Pidgey", 9)],
        "showcase": {"slots": ["pidgey-1", "gone"]},
    }

    entries = showcase.showcase_entries(state, count=3)

    assert entries[0]["pokemon"] is pidgey
    assert entries[0]["missing"] is False
    assert entries[1]["pokemon"] is None
    assert entries[1]["missing"] is True
    assert entries[2]["pokemon"] is None
