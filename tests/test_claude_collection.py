"""App collection and the optional Claude plugin share one usage cursor."""

import importlib.util
import io
import json
import os
import random
import sys
import time
from pathlib import Path

import pytest

from lib import collectors, engine, paths, state


@pytest.fixture
def claude_game(tmp_path, monkeypatch):
    monkeypatch.setattr(collectors, "CLAUDE_ROOT", tmp_path / "claude" / "projects")
    monkeypatch.setattr(collectors, "CODEX_ROOT", tmp_path / "codex")
    monkeypatch.setattr(collectors, "AUGMENT_ROOT", tmp_path / "augment")
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(paths, "STATE_FILE", paths.STATE_DIR / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", paths.STATE_DIR / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", paths.STATE_DIR / "journal.jsonl")
    game = state.default_state()
    engine.create_starter(game, "Pikachu")
    state.save(game)
    return collectors.CLAUDE_ROOT / "project" / "session-1.jsonl"


def append_usage(path, uuid, output=100):
    path.parent.mkdir(parents=True, exist_ok=True)
    prior_mtime = path.stat().st_mtime if path.exists() else 0
    with path.open("a") as handle:
        handle.write(json.dumps({
            "type": "assistant", "uuid": uuid,
            "message": {"usage": {"output_tokens": output}},
        }) + "\n")
    os.utime(path, (max(path.stat().st_mtime, prior_mtime + 1),) * 2)


def collect():
    with state.lock():
        game = state.load()
        result = collectors.collect(game, random.Random(1))
        state.save(game)
    return result


def stop_hook(path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "test_claude_stop", Path(__file__).resolve().parents[1] / "hooks" / "stop.py"
    )
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    monkeypatch.setattr(hook.notify, "notify", lambda *args, **kwargs: None)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "session_id": path.stem, "transcript_path": str(path),
    })))
    hook.main()


def test_first_claude_scan_anchors_history_even_for_existing_codex_player(claude_game):
    append_usage(claude_game, "old", 500_000)
    game = state.load()
    game["collectors"] = {"_bootstrapped": True}
    state.save(game)
    assert collect()["raw_tokens"] == 0
    append_usage(claude_game, "new", 100)
    assert collect()["raw_tokens"] == 100
    assert collect()["raw_tokens"] == 0
    assert state.load()["trainer"]["total_tokens"] == 100


def test_new_claude_session_after_setup_counts_from_its_start(claude_game):
    assert collect()["raw_tokens"] == 0
    append_usage(claude_game, "new", 250)
    assert collect()["raw_tokens"] == 250


@pytest.mark.parametrize("first", ["app", "plugin"])
def test_app_and_plugin_do_not_double_count_in_either_order(
    claude_game, monkeypatch, first
):
    append_usage(claude_game, "history", 1_000)
    collect()
    append_usage(claude_game, "new", 250)
    if first == "app":
        assert collect()["raw_tokens"] == 250
        stop_hook(claude_game, monkeypatch)
    else:
        stop_hook(claude_game, monkeypatch)
        assert collect()["raw_tokens"] == 0
    assert state.load()["trainer"]["total_tokens"] == 250


def test_existing_plugin_cursor_migrates_without_replaying_history(claude_game):
    append_usage(claude_game, "old", 1_000)
    append_usage(claude_game, "new", 250)
    game = state.load()
    game["xp_sessions"][claude_game.stem] = {"last_uuid": "old", "updated": 1}
    state.save(game)
    assert collect()["raw_tokens"] == 250
    assert collect()["raw_tokens"] == 0


def test_pruned_plugin_cache_does_not_replay_counted_transcript(
    claude_game, monkeypatch
):
    append_usage(claude_game, "old", 1_000)
    collect()
    game = state.load()
    game["xp_sessions"] = {}
    state.save(game)
    append_usage(claude_game, "new", 250)
    stop_hook(claude_game, monkeypatch)
    assert state.load()["trainer"]["total_tokens"] == 250
    assert collect()["raw_tokens"] == 0


def test_compacted_transcript_reanchors_then_counts_new_activity(claude_game):
    append_usage(claude_game, "old", 1_000)
    collect()
    claude_game.write_text("")
    append_usage(claude_game, "compacted", 500_000)
    assert collect()["raw_tokens"] == 0
    append_usage(claude_game, "new", 250)
    assert collect()["raw_tokens"] == 250


@pytest.mark.parametrize("first", ["app", "plugin"])
def test_resumed_idle_transcript_keeps_cursor_after_legacy_cache_eviction(
    claude_game, monkeypatch, first
):
    append_usage(claude_game, "history", 1_000)
    collect()
    append_usage(claude_game, "first-new", 250)
    assert collect()["raw_tokens"] == 250

    game = state.load()
    for number in range(20):
        game["xp_sessions"][f"other-{number}"] = {
            "last_uuid": f"other-{number}", "updated": time.time() + number + 1,
        }
    state.prune_sessions(game)
    assert claude_game.stem not in game["xp_sessions"]
    stale = time.time() - (collectors.RECENT_WINDOW_DAYS + 1) * 86400
    os.utime(claude_game, (stale, stale))
    state.save(game)
    assert collect()["raw_tokens"] == 0  # Scheduled scan also prunes anchors.

    append_usage(claude_game, "resumed-new", 50)
    resumed_mtime = game["collectors"][f"claude:{claude_game.resolve()}"]["mtime"] + 1
    os.utime(claude_game, (resumed_mtime, resumed_mtime))
    if first == "app":
        assert collect()["raw_tokens"] == 50
        stop_hook(claude_game, monkeypatch)
    else:
        stop_hook(claude_game, monkeypatch)
        assert collect()["raw_tokens"] == 0
    assert state.load()["trainer"]["total_tokens"] == 300


def test_claude_cursor_survives_temporary_access_error_but_not_deletion(
    claude_game, monkeypatch
):
    append_usage(claude_game, "history")
    collect()
    anchors = state.load()["collectors"]
    key = f"claude:{claude_game.resolve()}"
    original_stat = Path.stat

    def denied(path, *args, **kwargs):
        if path == claude_game:
            raise PermissionError("temporarily unavailable")
        return original_stat(path, *args, **kwargs)

    with monkeypatch.context() as changes:
        changes.setattr(Path, "stat", denied)
        collectors.prune_anchors(anchors)
    assert key in anchors
    claude_game.unlink()
    collectors.prune_anchors(anchors)
    assert key not in anchors
