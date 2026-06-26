"""Kitty graphics protocol escapes + the TUI inline-image draw path."""
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import engine, kgp, state, tui


def fresh():
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    return s


def test_place_chunks_large_payloads_and_silences_replies():
    png = b"\x89PNG" + b"\x00" * 9000  # forces >1 base64 chunk (4096 limit)
    esc = kgp.place(png, cols=20, rows=10, img_id=1)
    chunks = re.findall(r"\x1b_G([^;]*);", esc)
    assert len(chunks) >= 3
    assert "a=T" in chunks[0] and "c=20,r=10" in chunks[0] and "q=2" in chunks[0]
    assert "C=1" in chunks[0]  # cursor must not move; the caller positions it
    assert chunks[0].endswith("m=1") and chunks[-1].endswith("m=0")  # continuation flags


def test_clear_deletes_all_images_quietly():
    assert kgp.clear() == "\x1b_Ga=d,q=2\x1b\\"


def _force_tty(monkeypatch):
    monkeypatch.setattr(kgp.sys.stdout, "isatty", lambda: True, raising=False)
    for var in ("BUDDYMON_NO_GRAPHICS", "KITTY_WINDOW_ID", "TERM_PROGRAM",
                "TERM", "LC_TERMINAL"):
        monkeypatch.delenv(var, raising=False)


def test_protocol_detects_kitty_iterm_and_none(monkeypatch):
    _force_tty(monkeypatch)
    monkeypatch.setenv("TERM_PROGRAM", "ghostty")
    assert kgp.protocol() == "kitty" and kgp.supported()

    _force_tty(monkeypatch)
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    assert kgp.protocol() == "iterm" and kgp.supported()

    _force_tty(monkeypatch)
    monkeypatch.setenv("LC_TERMINAL", "iTerm2")
    assert kgp.protocol() == "iterm"

    _force_tty(monkeypatch)
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    assert kgp.protocol() is None and not kgp.supported()

    _force_tty(monkeypatch)
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    monkeypatch.setenv("BUDDYMON_NO_GRAPHICS", "1")
    assert kgp.protocol() is None  # opt-out wins


def test_iterm_place_emits_osc1337_inline_image(monkeypatch):
    monkeypatch.setattr(kgp, "protocol", lambda: "iterm")
    esc = kgp.place(b"\x89PNG\x00\x01\x02", cols=12, rows=6, img_id=1)
    assert esc.startswith("\x1b]1337;File=")
    assert esc.endswith("\x1b\\")
    assert "inline=1" in esc
    assert "width=12;height=6" in esc
    assert "preserveAspectRatio=1" in esc
    assert "\x1b_G" not in esc  # not the kitty protocol
    import base64
    payload = esc.split(":", 1)[1][:-2]  # between ':' and the ST terminator
    assert base64.b64decode(payload) == b"\x89PNG\x00\x01\x02"


def test_iterm_clear_is_noop(monkeypatch):
    monkeypatch.setattr(kgp, "protocol", lambda: "iterm")
    assert kgp.clear() == ""  # ED erases inline images; no delete-all needed


def test_kitty_place_path_unchanged(monkeypatch):
    monkeypatch.setattr(kgp, "protocol", lambda: "kitty")
    esc = kgp.place(b"\x89PNG", cols=8, rows=4, img_id=2)
    assert "\x1b_G" in esc and "a=T" in esc and "c=8,r=4" in esc
    assert "1337" not in esc


def test_supported_requires_a_tty(monkeypatch):
    monkeypatch.setattr(kgp.sys.stdout, "isatty", lambda: False, raising=False)
    assert not kgp.supported()


def test_draw_replaces_markers_with_positioned_images():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))
    try:
        tui._GRAPHICS = True
        frame = tui._party_frame(s, 0, art_h=24)
        assert "\x01IMG0\x02" in frame  # marker before draw
        assert tui._frame_images, "preview registered as a PNG"

        buf = io.StringIO()
        real = sys.stdout
        sys.stdout = buf
        try:
            tui._draw(frame)
        finally:
            sys.stdout = real
        out = buf.getvalue()
    finally:
        tui._GRAPHICS = False
        tui._frame_images.clear()

    assert "\x01IMG" not in out          # marker never leaks to the terminal
    assert "\x1b_Ga=d" in out            # stale images wiped first
    assert out.count("\x1b_Ga=T") == 1   # exactly one image placed
    assert re.search(r"\x1b\[\d+;\d+H\x1b_Ga=T", out)  # cursor-positioned, then drawn


def test_draw_places_images_by_visible_column_not_ansi_string_index():
    try:
        tui._GRAPHICS = True
        tui._frame_images[:] = [(b"\x89PNG\r\n\x1a\n", 4, 2)]
        frame = f"{tui.GREEN}▶{tui.RESET} abc \x01IMG0\x02"

        buf = io.StringIO()
        real = sys.stdout
        sys.stdout = buf
        try:
            tui._draw(frame)
        finally:
            sys.stdout = real
        out = buf.getvalue()
    finally:
        tui._GRAPHICS = False
        tui._frame_images.clear()

    # Visible prefix is "▶ abc " => image starts at terminal column 7.
    assert "\x1b[1;7H\x1b_Ga=T" in out


def test_sprite_card_graphics_mode_uses_terminal_row_budget():
    old_cell = tui._CELL_PX
    try:
        tui._GRAPHICS = True
        tui._CELL_PX = (10, 20)
        tui._frame_images.clear()

        lines = tui._sprite_card_lines({
            "name": "Beheeyem", "type": "Psychic", "shiny": False,
        }, max_h=64)

        _, cols, rows = tui._frame_images[0]
    finally:
        tui._GRAPHICS = False
        tui._CELL_PX = old_cell
        tui._frame_images.clear()

    assert len(lines) == tui.SELECT_CARD_INNER_ROWS + 2
    assert cols <= tui.SELECT_CARD_INNER_W
    assert rows <= tui.SELECT_CARD_INNER_ROWS
    marker_rows = [i for i, line in enumerate(lines) if "\x01IMG0\x02" in line]
    assert marker_rows and 1 <= marker_rows[0] < len(lines) - 1
    assert marker_rows[0] - 1 == (tui.SELECT_CARD_INNER_ROWS - rows) // 2
    assert lines[marker_rows[0]].index("\x01IMG0\x02") - 2 == (
        tui.SELECT_CARD_INNER_W - cols) // 2


def test_paired_battle_view_places_two_non_overlapping_images():
    s = fresh()
    s["pending_battle"] = {
        "name": "Muk", "type": "Poison", "emoji": "🟣", "rarity": "uncommon",
        "shiny": False, "c": 90, "base_c": 90, "angry": 0, "eating": 0,
        "balls_thrown": 0, "moves": 0, "last_msg": "A wild Muk appeared!",
        "wild_hp": 30, "wild_hp_max": 30, "buddy_hp": 40, "buddy_hp_max": 40,
    }
    try:
        tui._GRAPHICS = True
        frame = tui._encounter_frame(s, "battle", 0)
        buf = io.StringIO()
        real = sys.stdout
        sys.stdout = buf
        try:
            tui._draw(frame)
        finally:
            sys.stdout = real
        out = buf.getvalue()
    finally:
        tui._GRAPHICS = False
        tui._frame_images.clear()

    spans = []
    for m in re.finditer(r"\x1b\[(\d+);(\d+)H\x1b_Ga=T[^;]*c=(\d+),r=(\d+)", out):
        row, col, cols, _ = map(int, m.groups())
        spans.append((row, col, col + cols))
    assert len(spans) == 2
    (r1, a1, b1), (r2, a2, b2) = spans
    assert r1 == r2            # buddy and wild sit on the same band
    assert b1 <= a2 or b2 <= a1  # their cell boxes do not overlap
