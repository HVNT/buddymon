"""Hook tests: Claude Code Stop path token accounting."""
import importlib.util
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import engine, paths, state


def _load_stop_hook():
    hook = Path(__file__).resolve().parent.parent / "hooks" / "stop.py"
    spec = importlib.util.spec_from_file_location("buddymon_stop_hook", hook)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stop_hook_tracks_raw_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")

    s = state.default_state()
    engine.create_starter(s, "Pikachu")
    state.save(s)

    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(json.dumps({
        "type": "assistant",
        "uuid": "a",
        "message": {"usage": {
            "output_tokens": 1000,
            "input_tokens": 2000,
            "cache_creation_input_tokens": 3000,
            "cache_read_input_tokens": 4000,
        }},
    }) + "\n", encoding="utf-8")

    stop = _load_stop_hook()
    monkeypatch.setattr(stop.notify, "notify", lambda *a, **k: None)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "session_id": "s1",
        "transcript_path": str(transcript),
    })))

    stop.main()

    loaded = state.load()
    assert loaded["trainer"]["total_tokens"] == 10_000
    assert loaded["xp_sessions"]["s1"]["last_uuid"] == "a"
