"""CLI choices must preserve progress saved by competing writers."""

import fcntl
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import buddymon
from lib import engine, paths, state


@pytest.fixture
def game_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")
    return tmp_path


@pytest.mark.parametrize("command", ["choose", "switch", "switch_id"])
def test_choice_preserves_concurrent_progress(game_dir, monkeypatch, command):
    game = state.default_state()
    if command == "choose":
        args = ["Pikachu"]
        expected_id = None
    else:
        engine.create_starter(game, "Charmander")
        lower = engine.new_pokemon("Pikachu", "Electric", "⚡", "starter", level=2)
        higher = engine.new_pokemon("Pikachu", "Electric", "⚡", "starter", level=7)
        game["pokemon"].extend([lower, higher])
        args = ["pikachu"] if command == "switch" else [lower["id"]]
        expected_id = higher["id"] if command == "switch" else lower["id"]
    state.save(game)

    load = state.load
    loaded, resume = Event(), Event()

    def pause_after_read():
        snapshot = load()
        loaded.set()
        assert resume.wait(5), "test did not resume the choice command"
        return snapshot

    monkeypatch.setattr(state, "load", pause_after_read)
    with ThreadPoolExecutor(max_workers=1) as pool:
        choice = pool.submit(getattr(buddymon, command), args)
        try:
            assert loaded.wait(5), "choice did not read state"
            # A collector can save between an unlocked read and save. If the
            # command owns the real lock, let it finish before the writer runs.
            with (game_dir / ".lock").open("a+b") as writer:
                try:
                    fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    resume.set()
                    fcntl.flock(writer, fcntl.LOCK_EX)
                latest = load()
                latest["trainer"]["total_tokens"] += 250
                latest["trainer"]["balls"] += 1
                state.save(latest)
        finally:
            resume.set()
        choice.result(timeout=5)

    saved = load()
    assert saved["trainer"]["total_tokens"] == 250
    assert saved["trainer"]["balls"] == 11
    assert state.active_pokemon(saved)["name"] == "Pikachu"
    if expected_id is not None:
        assert saved["active"] == expected_id
    else:
        assert len(saved["pokemon"]) == 1
        assert len(paths.JOURNAL_FILE.read_text().splitlines()) == 1


@pytest.mark.parametrize("command,args,expected", [
    ("choose", ["Eevee"], "already have a buddy"),
    ("switch", ["Mewtwo"], "No 'mewtwo'"),
    ("switch_id", ["missing-copy"], "no longer in your collection"),
])
def test_rejected_choice_preserves_state_and_releases_lock(
    game_dir, command, args, expected,
):
    game = state.default_state()
    engine.create_starter(game, "Pikachu")
    state.save(game)
    before = paths.STATE_FILE.read_bytes()

    assert expected in getattr(buddymon, command)(args)
    assert paths.STATE_FILE.read_bytes() == before
    assert not paths.JOURNAL_FILE.exists()
    with (game_dir / ".lock").open("a+b") as writer:
        fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
