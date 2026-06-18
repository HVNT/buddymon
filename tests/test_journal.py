"""Journal + notification gating tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import journal


def _isolate(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")


def test_append_tail_roundtrip_and_corrupt_tolerance(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    journal.append("caught", "🎉 caught Pidgey", {"name": "Pidgey"})
    with open(tmp_path / "journal.jsonl", "a") as f:
        f.write("not json\n")
    journal.append("level", "⬆️ Lv.5")
    entries = journal.tail(10)
    assert [e["kind"] for e in entries] == ["caught", "level"]
    assert entries[0]["name"] == "Pidgey"


def test_log_outcomes_kinds(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    result = {"xp": 50, "old_level": 15, "new_level": 16, "leveled": True,
              "evolved": "Charmeleon", "buddy": "Charmeleon"}
    encounter = {"name": "Mewtwo", "emoji": "🧬", "rarity": "legendary",
                 "shiny": False, "outcome": "fled"}
    written = journal.log_outcomes(result, encounter, "claude")
    assert [e["kind"] for e in written] == ["evolved", "fled"]
    assert written[1]["rarity"] == "legendary"

    written = journal.log_outcomes(
        {"xp": 5, "old_level": 3, "new_level": 3, "leveled": False,
         "evolved": None, "buddy": "Pikachu"},
        {"name": "Pidgey", "emoji": "🐦", "rarity": "common", "shiny": True,
         "outcome": "caught", "new_species": True}, "cross")
    assert [e["kind"] for e in written] == ["caught"]
    assert written[0]["shiny"] is True


def test_is_rare_truth_table():
    assert journal.is_rare({"kind": "evolved"})
    assert journal.is_rare({"kind": "caught", "shiny": True, "rarity": "common"})
    assert journal.is_rare({"kind": "fled", "shiny": False, "rarity": "legendary"})
    assert journal.is_rare({"kind": "no_balls", "rarity": "legendary"})
    assert not journal.is_rare({"kind": "caught", "shiny": False, "rarity": "common"})
    assert not journal.is_rare({"kind": "level", "level": 30})
    assert not journal.is_rare({"kind": "fled", "rarity": "rare"})


def test_notify_fires_only_for_rare(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from lib import notify
    calls = []
    monkeypatch.setattr(notify, "notify", lambda title, text: calls.append(text))

    entries = journal.log_outcomes(
        {"xp": 9, "old_level": 2, "new_level": 2, "leveled": False,
         "evolved": None, "buddy": "Eevee"},
        {"name": "Articuno", "emoji": "🧊", "rarity": "legendary", "shiny": False,
         "outcome": "caught", "new_species": True}, "claude")
    for e in entries:
        if journal.is_rare(e):
            notify.notify("buddymon", e["text"])
    assert len(calls) == 1 and "Articuno" in calls[0]
