"""Collector tests: codex cumulative deltas, augment timestamp dedupe, tiny."""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import collectors, engine, state


def codex_record(cum_output, cum_input, cum_cached):
    return json.dumps({
        "type": "event_msg",
        "payload": {"type": "token_count", "info": {"total_token_usage": {
            "input_tokens": cum_input, "cached_input_tokens": cum_cached,
            "output_tokens": cum_output, "reasoning_output_tokens": 0,
            "total_tokens": cum_input + cum_output}}},
    })


def write_rollout(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(records) + "\n", encoding="utf-8")


def setup_codex(tmp_path, monkeypatch):
    root = tmp_path / "codex"
    monkeypatch.setattr(collectors, "CODEX_ROOT", root)
    monkeypatch.setattr(collectors, "AUGMENT_ROOT", tmp_path / "none")
    return root / "2026" / "06" / "12" / "rollout-a.jsonl"


def test_codex_bootstrap_then_incremental(tmp_path, monkeypatch):
    rollout = setup_codex(tmp_path, monkeypatch)
    write_rollout(rollout, [codex_record(10_000, 50_000, 20_000)])
    s = state.default_state()
    engine.create_starter(s, "Pikachu")
    rng = random.Random(1)

    # first run: bootstrap, no award
    summary = collectors.collect(s, rng)
    assert summary["bootstrapped_now"] and summary["result"] is None

    # append usage: only the delta is awarded
    with open(rollout, "a") as f:
        f.write(codex_record(20_000, 80_000, 60_000) + "\n")
    import os
    os.utime(rollout, (rollout.stat().st_mtime + 5,) * 2)
    summary = collectors.collect(s, rng)
    # delta: output 10k -> 100xp; input (80k-60k)-(50k-20k)=... per-tier on cum:
    # input tier = (input - cached): 20k - 30k clamped >= 0 per _add max(0,..)
    assert summary["result"] is not None
    assert summary["tokens"]["output"] == 10_000
    assert summary["tokens"]["cache_read"] == 40_000

    # immediate re-run: nothing new
    summary = collectors.collect(s, rng)
    assert summary["result"] is None


def test_codex_new_file_after_bootstrap_counts_fully(tmp_path, monkeypatch):
    rollout = setup_codex(tmp_path, monkeypatch)
    write_rollout(rollout, [codex_record(1000, 0, 0)])
    s = state.default_state()
    engine.create_starter(s, "Eevee")
    rng = random.Random(2)
    collectors.collect(s, rng)  # bootstrap

    fresh = rollout.parent / "rollout-b.jsonl"
    write_rollout(fresh, [codex_record(5000, 0, 0)])
    summary = collectors.collect(s, rng)
    assert summary["tokens"]["output"] == 5000


def test_augment_timestamp_anchor(tmp_path, monkeypatch):
    root = tmp_path / "aug"
    root.mkdir()
    monkeypatch.setattr(collectors, "AUGMENT_ROOT", root)
    monkeypatch.setattr(collectors, "CODEX_ROOT", tmp_path / "none")
    session = root / "s.json"

    def node(ts, out):
        return {"timestamp_ms": ts, "token_usage": {"output_tokens": out,
                "input_tokens": 0, "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0}}
    session.write_text(json.dumps({"events": [node(1000, 2000)]}))

    s = state.default_state()
    engine.create_starter(s, "Squirtle")
    rng = random.Random(3)
    collectors.collect(s, rng)  # bootstrap anchors at ts=1000

    import os
    session.write_text(json.dumps({"events": [node(1000, 2000), node(2000, 3000)]}))
    os.utime(session, (session.stat().st_mtime + 5,) * 2)
    summary = collectors.collect(s, rng)
    assert summary["tokens"]["output"] == 3000  # only the new node

    summary = collectors.collect(s, rng)
    assert summary["result"] is None


def test_prune_anchors_drops_deleted_files():
    anchors = {"codex:/nope/gone.jsonl": {"offset": 1}, "_bootstrapped": True}
    collectors.prune_anchors(anchors)
    assert list(anchors) == ["_bootstrapped"]


def test_tiny_is_one_plain_line(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    state.save(s)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import buddymon
    out = buddymon.tiny([])
    assert "\n" not in out and "\x1b" not in out
    assert "Charmander" in out and "Lv.1" in out


def test_prune_anchors_drops_aged_out_files(tmp_path):
    import os, time
    old = tmp_path / "old.jsonl"
    fresh = tmp_path / "fresh.jsonl"
    old.write_text("x")
    fresh.write_text("x")
    stale = time.time() - (collectors.RECENT_WINDOW_DAYS + 1) * 86400
    os.utime(old, (stale, stale))
    anchors = {f"codex:{old}": {"offset": 1}, f"codex:{fresh}": {"offset": 1},
               "_bootstrapped": True}
    collectors.prune_anchors(anchors)
    assert f"codex:{fresh}" in anchors and f"codex:{old}" not in anchors


def test_huge_award_crosses_multiple_evolutions():
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    engine.award_xp(s, engine.xp_for_level(40), random.Random(1))
    assert state.active_pokemon(s)["name"] == "Charizard"
