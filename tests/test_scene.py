"""Compositor and cutscene-timing tests."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import journal, pixels, png, scene

RED_SQ = (["AA", "AA"], {"A": "#ff0000"})
BLUE_SQ = (["AA", "AA"], {"A": "#0000ff"})  # same char, different color: must not collide


def test_compose_keeps_clashing_palettes_apart():
    c = scene.Canvas(6, 2)
    c.sprite(*RED_SQ, 0, 0)
    c.sprite(*BLUE_SQ, 4, 0)
    grid, palette = c.result()
    colors = {palette[ch] for row in grid for ch in row if ch in palette}
    assert {"#ff0000", "#0000ff"} <= colors
    assert all(len(row) == 6 for row in grid)


def test_mirror_reverses_rows():
    assert scene.mirror(["ab", "cd"]) == ["ba", "dc"]
    assert scene.mirror(scene.mirror(["ab", "cd"])) == ["ab", "cd"]


def test_battle_scenes_render_for_all_outcomes():
    buddy = (["BB" * 8] * 14, {"B": "#f08030"})
    wild = (["WW" * 8] * 14, {"W": "#58a8e8"})
    for outcome in ("caught", "fled", "no_balls"):
        for phase in range(scene.CUTSCENE_SECS):
            grid, palette = scene.battle_bar(buddy, wild, phase, outcome)
            assert all(len(row) == 44 for row in grid)
            assert pixels.render(grid, palette)
            assert png.grid_to_png(grid, palette)[:4] == b"\x89PNG"[:4]
        grid, palette = scene.battle_screen(buddy, wild, outcome)
        w = len(grid[0])
        assert all(len(row) == w for row in grid)  # uniform rows
        assert png.grid_to_png(grid, palette, 2)
        # also works with large Gen-5-sized sprites
        big_b = (["B" * 60] * 56, {"B": "#f08030"})
        big_w = (["W" * 60] * 56, {"W": "#58a8e8"})
        bg, bp = scene.battle_screen(big_b, big_w, outcome)
        assert all(len(r) == len(bg[0]) for r in bg) and png.grid_to_png(bg, bp)


def test_phase_for_window():
    assert scene.phase_for(0) == 0
    assert scene.phase_for(11.9) == 11
    assert scene.phase_for(scene.CUTSCENE_SECS) is None
    assert scene.phase_for(-1) is None


def test_latest_encounter_window(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")
    now = time.time()
    journal.append("caught", "old", {"name": "Pidgey", "rarity": "common"})
    journal.append("level", "irrelevant kind", {})
    entries = journal.tail(5)
    assert journal.latest_encounter(60, now) is not None
    assert journal.latest_encounter(60, now + 120) is None
    assert journal.latest_encounter(60, now)["name"] == "Pidgey"
    assert entries[-1]["kind"] == "level"  # non-encounter newest doesn't block lookup


def test_pre_evolution_covers_every_evolved_form():
    from lib import data
    expected = {"Charmeleon": "Charmander", "Charizard": "Charmeleon",
                "Ivysaur": "Bulbasaur", "Venusaur": "Ivysaur",
                "Wartortle": "Squirtle", "Blastoise": "Wartortle",
                "Raichu": "Pikachu", "Vaporeon": "Eevee",
                "Jolteon": "Eevee", "Flareon": "Eevee"}
    assert data.PRE_EVOLUTION == expected


def test_silhouette_whites_out_palette_only():
    grid, palette = scene.silhouette((["ab", "b."], {"a": "#112233", "b": "#445566"}))
    assert grid == ["ab", "b."]
    assert set(palette.values()) == {"#f8f8f8"}


def test_evolution_bar_renders_all_phases():
    old = (["OO" * 8] * 14, {"O": "#e8443c"})
    new = (["NN" * 8] * 16, {"N": "#f08030"})
    for phase in range(scene.EVOLUTION_SECS):
        grid, palette = scene.evolution_bar(old, new, phase)
        assert all(len(row) == 44 for row in grid)
        assert png.grid_to_png(grid, palette)[:4] == b"\x89PNG"[:4]
    assert scene.evolution_phase_for(scene.EVOLUTION_SECS) is None
    assert scene.evolution_phase_for(2.5) == 2


def test_journal_latest_filters_kinds(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")
    now = time.time()
    journal.append("evolved", "evo", {"name": "Charizard"})
    journal.append("caught", "catch", {"name": "Pidgey", "rarity": "common"})
    assert journal.latest_evolution(60, now)["name"] == "Charizard"
    assert journal.latest_encounter(60, now)["name"] == "Pidgey"
    assert journal.latest_evolution(60, now + 120) is None


def test_evolution_line_survives_single_frame_fallback(tmp_path, monkeypatch):
    # no gen2 pack -> chibi fallback has one frame; odd phases must not crash
    from lib import paths, packs
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    packs._cache.clear()
    import buddymon
    entry = {"name": "Charizard", "ts": 0}
    for phase in range(scene.EVOLUTION_SECS):
        assert "image=" in buddymon._evolution_line(entry, phase)
    packs._cache.clear()
