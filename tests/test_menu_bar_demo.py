"""Developer playback stories for the real native menu-bar buddy."""

import json
import signal
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import menu_bar, menu_bar_demo


def test_preview_sequence_renders_every_canonical_state_for_charmander():
    for state_id in menu_bar.catalog_ids():
        sequence = menu_bar.preview_sequence(state_id)
        assert sequence["state_id"] == state_id
        assert sequence["sequence_id"].startswith(f"preview:{state_id}:Charmander:")
        assert sequence["frames"]


def test_preview_sequence_uses_requested_buddy_evolution_and_wild():
    evolution = menu_bar.preview_sequence(
        "evolving",
        buddy_name="Charmander",
        evolved_name="Charmeleon",
        wild_name="Pikachu",
    )
    labels = [frame["accessibility_label"] for frame in evolution["frames"]]

    assert all("Charmander" in label for label in labels)
    assert all("Charmeleon" in label for label in labels)


def test_story_catalog_is_unique_valid_and_all_states_is_complete():
    assert len(menu_bar_demo.story_ids()) == len(set(menu_bar_demo.story_ids()))
    for story in menu_bar_demo.STORY_CATALOG:
        assert story["steps"]
        for step in story["steps"]:
            assert step["state_id"] in menu_bar.catalog_ids()
            assert step["hold_ms"] > 0
            assert step["description"]

    assert tuple(
        step["state_id"] for step in menu_bar_demo.story_steps("all-states")
    ) == menu_bar.catalog_ids()
    story_state_ids = {
        step["state_id"]
        for story in menu_bar_demo.STORY_CATALOG
        for step in story["steps"]
    }
    assert story_state_ids == set(menu_bar.catalog_ids())

    all_stories = menu_bar_demo.story_steps("all-stories")
    assert len(all_stories) == sum(
        len(story["steps"]) for story in menu_bar_demo.STORY_CATALOG
    )
    assert all(step["story_id"] for step in all_stories)


def test_scaled_sequence_preserves_shape_and_recalculates_duration():
    original = menu_bar.preview_sequence("evolving")
    scaled = menu_bar_demo.scaled_sequence(original, 2)

    assert scaled is not original
    assert len(scaled["frames"]) == len(original["frames"])
    assert scaled["duration_ms"] == sum(
        frame["duration_ms"] for frame in scaled["frames"]
    )
    assert scaled["duration_ms"] < original["duration_ms"]
    assert original["frames"][0]["duration_ms"] == 260


def test_post_preview_atomically_writes_payload_and_signals_running_app(
    tmp_path, monkeypatch
):
    sent = []
    monkeypatch.setattr(menu_bar_demo.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(menu_bar_demo, "app_pids", lambda: (111, 222))
    monkeypatch.setattr(
        menu_bar_demo.os,
        "kill",
        lambda pid, sent_signal: sent.append((pid, sent_signal)),
    )
    envelope = menu_bar_demo.preview_envelope(
        menu_bar.preview_sequence("working"),
        hold_ms=2_500,
    )

    menu_bar_demo.post_preview(envelope)

    path = tmp_path / f"buddymon-menu-bar-preview-{menu_bar_demo.os.getuid()}.json"
    assert json.loads(path.read_text(encoding="utf-8")) == envelope
    assert sent == [(111, signal.SIGWINCH), (222, signal.SIGWINCH)]
    assert not list(tmp_path.glob("*.tmp"))


def test_cli_can_play_one_state_and_a_complete_story(monkeypatch, capsys):
    envelopes = []
    sleeps = []
    monkeypatch.setattr(menu_bar_demo, "app_is_running", lambda: True)
    monkeypatch.setattr(menu_bar_demo, "post_preview", envelopes.append)
    monkeypatch.setattr(menu_bar_demo.time, "sleep", sleeps.append)

    assert menu_bar_demo.main(["play", "evolving"]) == 0
    assert envelopes[-1]["sequence"]["state_id"] == "evolving"

    envelopes.clear()
    assert menu_bar_demo.main(["story", "starter-day", "--speed", "2"]) == 0
    assert [item["sequence"]["state_id"] for item in envelopes[:-1]] == [
        "booting",
        "needs_buddy",
        "idle",
    ]
    assert envelopes[-1]["cancel"] is True
    assert len(sleeps) == 3
    assert "Story complete" in capsys.readouterr().out


def test_cli_refuses_to_signal_when_native_app_is_not_running(monkeypatch, capsys):
    monkeypatch.setattr(menu_bar_demo, "app_is_running", lambda: False)

    assert menu_bar_demo.main(["play", "idle"]) == 2
    assert "BuddyMon.app is not running" in capsys.readouterr().err
