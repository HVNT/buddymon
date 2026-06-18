"""TUI frame builders (pure, terminal-free) + non-tty guard."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import engine, render, state, tui


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def fresh():
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    return s


def visible_width(line):
    return len(ANSI_RE.sub("", line))


def test_menu_frame_lists_all_items_and_marks_selection():
    frame = tui._menu_frame(tui.MENU, 0)
    for label, _ in tui.MENU:
        assert label in frame
    assert "▶" in frame  # selection cursor present


def test_menu_gains_fight_entry_when_a_wild_is_pending():
    s = fresh()
    assert all(action != "encounter" for _, action in tui._menu_items(s))
    s["pending_encounter"] = {"name": "Beldum", "type": "Steel", "shiny": False}
    items = tui._menu_items(s)
    assert items[0][1] == "encounter" and "Beldum" in items[0][0]


def test_encounter_frame_shows_options_and_status():
    s = fresh()
    s["pending_encounter"] = {
        "name": "Beldum", "type": "Steel", "emoji": "⚙️", "rarity": "rare",
        "shiny": False, "c": 90, "base_c": 90, "angry": 0, "eating": 0,
        "balls_thrown": 0, "moves": 0, "last_msg": "A wild Beldum appeared!",
    }
    frame = tui._encounter_frame(s, "safari", 0)
    for label, _ in tui.ENCOUNTER_OPTIONS["safari"]:
        assert label in frame
    assert "Beldum" in frame and "▶" in frame
    assert "your buddy" in frame
    assert "wild encounter" in frame
    assert "▀" in frame


def test_party_frame_marks_active_and_shows_selected_sprite():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))
    frame = tui._party_frame(s, 0)
    assert "Charmander" in frame and "Pidgey" in frame
    assert "▶" in frame  # row cursor
    assert "selected" in frame
    assert "XP" in frame
    assert "▀" in frame


def test_status_lines_show_sprite_preview():
    s = fresh()
    lines = tui._status_lines(s)
    frame = "\n".join(lines)
    assert "Charmander" in frame
    assert "Tokens used" in frame
    assert "Pokédex" in frame
    assert "▀" in frame


def test_party_orders_active_first():
    s = fresh()
    p = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5)
    s["pokemon"].append(p)
    mons = tui._party(s)
    assert mons[0]["id"] == s["active"]  # active buddy first


def test_journal_lines_empty_is_graceful(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")
    lines = tui._journal_lines()
    assert lines and "No journal yet" in lines[0]


def test_scroll_frame_windows_the_body():
    body = [f"line{i}" for i in range(50)]
    frame = tui._scroll_frame("dex", body, top=10, height=5)
    assert "line10" in frame and "line14" in frame
    assert "line9" not in frame and "line15" not in frame


def test_dex_frame_is_dense_and_pageable():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))
    entries = tui._dex_entries(s)

    frame = tui._dex_frame(entries, selected=0, top=0, height=18, width=80)

    assert "pokédex" in frame
    assert "species" in frame
    assert "2/649 species" in frame
    assert "PgUp/PgDn" in frame
    assert "Charmander" in frame
    assert "▀" in frame  # selected preview, while the dex remains a list browser
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_dex_entries_mark_caught_species():
    s = fresh()
    entries = tui._dex_entries(s)
    charmander = next(e for e in entries if e["name"] == "Charmander")
    pidgey = next(e for e in entries if e["name"] == "Pidgey")

    assert charmander["caught"]
    assert charmander["active"]
    assert not pidgey["caught"]


def test_dex_cell_art_fits_oversized_box_sprite(monkeypatch):
    def oversized_box_frames(_name, _ptype="Normal", _shiny=False):
        grid = ["X" * (render.DEX_CELL_W + 8)] * (render.DEX_CELL_H + 4)
        return [(grid, {"X": "#f08030"})]

    monkeypatch.setattr(render.packs, "box_frames", oversized_box_frames)

    grid, palette = render._dex_cell_art("Charizard", "Fire", revealed=True)

    assert len(grid) == render.DEX_CELL_H
    assert all(len(row) == render.DEX_CELL_W for row in grid)
    assert palette["X"] == "#f08030"


def test_dex_cell_size_stays_compact_for_first_screen():
    assert render.DEX_CELL_W <= 28
    assert render.DEX_CELL_H <= 22


def test_dex_cell_art_uses_clear_silhouette_for_unknown(monkeypatch):
    def box_frames(_name, _ptype="Normal", _shiny=False):
        return [(["AB", "BA"], {"A": "#111111", "B": "#eeeeee"})]

    monkeypatch.setattr(render.packs, "box_frames", box_frames)

    _, palette = render._dex_cell_art("Charmander", "Fire", revealed=False)

    assert set(palette.values()) == {render.DEX_UNKNOWN_COLOR}


def test_dex_grid_rows_stay_within_terminal_width_with_oversized_art(monkeypatch):
    def box_frames(name, _ptype="Normal", _shiny=False):
        if name == "Charizard":
            grid = ["C" * (render.DEX_CELL_W + 10)] * (render.DEX_CELL_H + 3)
            return [(grid, {"C": "#f08030"})]
        return [(["A" * 16] * 16, {"A": "#777777"})]

    monkeypatch.setattr(render.packs, "box_frames", box_frames)
    s = state.default_state()
    s["pokemon"].append(engine.new_pokemon("Charizard", "Fire", "🐉", "starter", level=39))

    frame = render.dex_grid(s, columns=80)

    assert "Charizard" in frame
    assert "???" in frame
    assert all(visible_width(line) <= 80 for line in frame.splitlines())
