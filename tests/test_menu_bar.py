"""Canonical menu-bar presentation tests."""

import base64
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import engine, journal, menu_bar, packs, paths, scene, state


EXPECTED_STATES = (
    "booting",
    "needs_buddy",
    "idle",
    "working",
    "resting",
    "shiny_idle",
    "unavailable",
    "xp_gain",
    "level_up",
    "evolving",
    "encounter_alert",
    "waiting_for_player",
    "auto_battle",
    "catching",
    "result.caught",
    "result.shiny_caught",
    "result.new_species",
    "result.broke_free",
    "result.fled",
    "result.no_balls",
    "result.wild_ko",
    "result.buddy_fainted",
    "result.ran",
)


def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")
    paths.ensure_dirs()
    packs._cache.clear()


def test_catalog_is_complete_unique_and_ordered():
    assert menu_bar.catalog_ids() == EXPECTED_STATES
    assert len(set(menu_bar.catalog_ids())) == len(EXPECTED_STATES)
    assert {entry["group"] for entry in menu_bar.STATE_CATALOG} == {
        "foundation",
        "progress",
        "encounters",
        "results",
    }
    assert {entry["coverage"] for entry in menu_bar.STATE_CATALOG} == {"automated"}
    assert {entry["id"] for entry in menu_bar.ENVIRONMENT_VARIANTS} == {
        "light",
        "dark",
        "selected",
        "reduce_motion",
        "fallback_art",
    }


def test_harness_renders_a_valid_sequence_for_every_state():
    payload = menu_bar.harness_payload()

    assert payload["schema_version"] == 1
    assert payload["kind"] == "menu_bar_harness"
    assert [sequence["state_id"] for sequence in payload["sequences"]] == list(
        EXPECTED_STATES
    )
    for sequence in payload["sequences"]:
        assert sequence["sequence_id"]
        assert sequence["frames"]
        assert sequence["duration_ms"] == sum(
            frame["duration_ms"] for frame in sequence["frames"]
        )
        assert 0 <= sequence["reduce_motion_frame"] < len(sequence["frames"])
        for frame in sequence["frames"]:
            assert frame["duration_ms"] > 0
            assert frame["accessibility_label"]
            assert frame["pixel_width"] > 0
            assert frame["pixel_height"] > 0
            assert base64.b64decode(frame["image_base64"]).startswith(
                b"\x89PNG\r\n\x1a\n"
            )


def test_runtime_without_buddy_uses_needs_buddy_baseline(tmp_path, monkeypatch):
    isolate(tmp_path, monkeypatch)

    payload = menu_bar.runtime_payload(state.default_state(), now=100)

    assert payload["baseline"]["state_id"] == "needs_buddy"
    assert payload["moments"] == []
    assert payload["persistent"] is None


def test_runtime_baseline_tracks_work_idle_and_rest(tmp_path, monkeypatch):
    isolate(tmp_path, monkeypatch)
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    event_file = paths.SESSIONS_DIR / "session.json"
    event_file.write_text(json.dumps({"event": "stop", "detail": "", "ts": 1_000}))

    working = menu_bar.runtime_payload(s, now=1_010)
    idle = menu_bar.runtime_payload(s, now=1_000 + menu_bar.WORKING_SECS + 1)
    resting = menu_bar.runtime_payload(s, now=1_000 + menu_bar.RESTING_SECS + 1)

    assert working["baseline"]["state_id"] == "working"
    assert idle["baseline"]["state_id"] == "idle"
    assert resting["baseline"]["state_id"] == "resting"
    assert working["moments"][0]["state_id"] == "xp_gain"
    assert working["moments"][0]["sequence_id"] == "activity:1000.000000"


def test_runtime_queues_journal_moments_in_order(tmp_path, monkeypatch):
    isolate(tmp_path, monkeypatch)
    s = state.default_state()
    buddy = engine.create_starter(s, "Charmander")
    buddy["name"] = "Charmeleon"
    now = time.time()
    stamps = iter([now - 2, now - 1])
    monkeypatch.setattr(journal.time, "time", lambda: next(stamps))
    journal.append(
        "evolved",
        "Charmeleon evolved",
        {"name": "Charmeleon", "level": 16, "shiny": False},
    )
    journal.append(
        "caught",
        "caught Eevee",
        {
            "name": "Eevee",
            "rarity": "common",
            "shiny": False,
            "new_species": True,
        },
    )

    payload = menu_bar.runtime_payload(s, now=now)

    assert [moment["state_id"] for moment in payload["moments"]] == [
        "evolving",
        "result.new_species",
    ]
    assert payload["moments"][0]["sequence_id"].startswith("journal:evolved:")
    assert payload["moments"][1]["sequence_id"].startswith("journal:caught:")
    assert len(payload["moments"][1]["frames"]) > 1
    assert payload["moments"][1]["frames"][-1]["accessibility_label"] == (
        "Charmeleon caught new species Eevee"
    )


def test_caught_results_settle_on_the_active_buddy():
    buddy = menu_bar._pokemon("Charmander", "Fire", rarity="starter")
    wild = menu_bar._pokemon("Eevee", "Normal")
    expected_image = menu_bar._encoded_frame(
        menu_bar._canvas_frame(
            menu_bar._fixture_frames(buddy)[0],
            width=20,
            sparkles=True,
        ),
        accessibility_label="test",
    )["image_base64"]

    for state_id in ("result.caught", "result.shiny_caught", "result.new_species"):
        result = menu_bar._catalog_sequence(
            state_id,
            buddy=buddy,
            wild=wild,
        )
        assert result["frames"][-1]["image_base64"] == expected_image
        assert result["frames"][-1]["accessibility_label"].startswith(
            "Charmander caught"
        )


def test_runtime_frames_use_the_native_menu_bar_art_provider(monkeypatch):
    expected = [(["X"], {"X": "#f08030"})]
    calls = []

    def menu_bar_frames(name, ptype, shiny):
        calls.append((name, ptype, shiny))
        return expected

    monkeypatch.setattr(packs, "menu_bar_frames", menu_bar_frames)

    assert menu_bar._runtime_frames({
        "name": "Charizard",
        "type": "Fire",
        "shiny": False,
    }) == expected
    assert calls == [("Charizard", "Fire", False)]


def test_pending_encounter_is_stable_persistent_state(tmp_path, monkeypatch):
    isolate(tmp_path, monkeypatch)
    s = state.default_state()
    engine.create_starter(s, "Squirtle")
    s["pending_encounter"] = {
        "name": "Eevee",
        "type": "Normal",
        "shiny": False,
        "created_ts": 123.5,
    }

    first = menu_bar.runtime_payload(s, now=200)["persistent"]
    second = menu_bar.runtime_payload(s, now=230)["persistent"]

    assert first["state_id"] == "waiting_for_player"
    assert first["sequence_id"] == "pending:123.500000:Eevee"
    assert second["sequence_id"] == first["sequence_id"]
    assert {frame["title"] for frame in first["frames"]} == {""}


def test_pending_battle_throw_queues_catching_and_break_free(tmp_path, monkeypatch):
    isolate(tmp_path, monkeypatch)
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    s["pending_battle"] = {
        "name": "Eevee",
        "type": "Normal",
        "rarity": "common",
        "shiny": False,
        "created_ts": 1_000,
        "last_throw": {"caught": False, "ts": 1_010},
    }

    payload = menu_bar.runtime_payload(s, now=1_020)
    throw = next(moment for moment in payload["moments"] if moment["state_id"] == "catching")

    assert throw["sequence_id"] == "throw:1010.000000:Eevee"
    assert len(throw["frames"]) == scene.THROW_SECS + 1
    assert throw["reduce_motion_frame"] == len(throw["frames"]) - 1


def test_harness_json_round_trips():
    payload = json.loads(menu_bar.harness_json(indent=2))
    assert len(payload["sequences"]) == len(EXPECTED_STATES)


def test_compact_titles_use_menu_bar_copy_and_spacing_contract():
    working = menu_bar.preview_sequence("working")
    level_up = menu_bar.preview_sequence("level_up")
    catching = menu_bar.preview_sequence("catching")
    encounter_alert = menu_bar.preview_sequence("encounter_alert")
    waiting = menu_bar.preview_sequence("waiting_for_player")

    assert {frame["title"] for frame in working["frames"]} == {""}
    assert {frame["title"] for frame in level_up["frames"]} == {"Lvl!"}
    assert {frame["title"] for frame in catching["frames"]} == {""}
    assert {frame["title"] for frame in encounter_alert["frames"]} == {""}
    assert {frame["title"] for frame in waiting["frames"]} == {""}
    assert "⚾" not in json.dumps(menu_bar.harness_payload())
