"""Pack pipeline tests: asm parsing, grid conversion, loader fallback."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import data, packs, pixels, sprites
from tools import fetch_official as fo

ASM_FIXTURE = """
MonMenuIcons:
\ttable_width 1
\tdb ICON_BULBASAUR   ; BULBASAUR
\tdb ICON_BIGMON      ; CHARIZARD
\tdb ICON_HO_OH       ; HO_OH
\tdb ICON_FOX         ; EEVEE
"""


def test_parse_menu_icons():
    m = fo.parse_menu_icons(ASM_FIXTURE)
    assert m == {"BULBASAUR": "bulbasaur", "CHARIZARD": "bigmon",
                 "HO_OH": "ho_oh", "EEVEE": "fox"}


def test_asm_key_normalization():
    assert fo.asm_key("Ho-Oh") == "HO_OH"
    assert fo.asm_key("Pikachu") == "PIKACHU"


def test_resolve_icon_maps_via_asm_and_specials():
    assert fo.resolve_icon("Eevee", {"EEVEE": "fox"}) == "fox"
    assert fo.resolve_icon("Eevee", {}) is None
    # special-cased constants (♀/♂, Mr. Mime, Farfetch'd)
    assert fo.asm_key("Nidoran♀") == "NIDORAN_F"
    assert fo.asm_key("Mr. Mime") == "MR__MIME"
    assert fo.asm_key("Farfetch'd") == "FARFETCH_D"


def test_dex_species_includes_evolutions():
    species = fo.dex_species()
    assert {"Charizard", "Vaporeon", "Raichu", "Snorlax"} <= set(species)


def test_outside_white_keeps_enclosed_highlight():
    # 0=white. Border-connected white is background; the center 0 is enclosed.
    rows = [
        [0, 0, 0, 0, 0],
        [0, 3, 3, 3, 0],
        [0, 3, 0, 3, 0],
        [0, 3, 3, 3, 0],
        [0, 0, 0, 0, 0],
    ]
    grid = fo.frame_to_grid(rows)
    assert grid[0] == "....."
    assert grid[2] == ".cwc."


def test_crop_frames_drops_shared_blank_rows_even_height():
    f = ["....", ".cc.", ".cc.", "...."]
    out = fo.crop_frames([f, f])
    assert all(len(fr) % 2 == 0 for fr in out)
    assert ".cc." in out[0]


def test_pack_loader_and_fallback(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    packs._cache.clear()
    # no pack on disk -> chibi fallback, single frame
    frames = packs.sprite_frames("Pikachu")
    assert len(frames) == 1

    pack_dir = tmp_path / "packs"
    pack_dir.mkdir()
    entry = {"frames": [["cc", "cw"], ["cw", "cc"]],
             "palette": {"c": "#102030", "w": "#f8f8f8"},
             "palette_shiny": {"c": "#aa1100", "w": "#f8f8f8"}}
    (pack_dir / "gen2.json").write_text(json.dumps({"Pikachu": entry}))
    packs._cache.clear()

    frames = packs.sprite_frames("Pikachu")
    assert len(frames) == 2
    assert frames[0][1]["c"] == "#102030"
    shiny = packs.sprite_frames("Pikachu", shiny=True)
    assert shiny[0][1]["c"] == "#aa1100"
    # pack grids render through the normal pixel pipeline
    assert len(pixels.render(*frames[0])) == 1
    packs._cache.clear()


def test_sprite_frames_falls_back_to_scaled_box_art(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    pack_dir = tmp_path / "packs"
    pack_dir.mkdir()
    (pack_dir / "box.json").write_text(json.dumps({
        "Swellow": {
            "grid": ["X" * 24] * 20,
            "palette": {"X": "#112233"},
        },
    }))
    packs._cache.clear()

    (grid, palette), = packs.sprite_frames("Swellow", "Normal")

    assert len(grid) <= 16
    assert all(len(row) <= 16 for row in grid)
    assert palette["X"] == "#112233"
    packs._cache.clear()


def test_extract_ramp_orders_by_luminance():
    class FakeImg:
        width = 2

        def convert(self, _):
            return self

        def getdata(self):
            return [(250, 250, 250, 255), (250, 250, 250, 255),
                    (180, 40, 40, 255), (180, 40, 40, 255),
                    (180, 40, 40, 255), (20, 20, 30, 255)]
    ramp = fo.extract_ramp(FakeImg())
    assert ramp["c"] == "#14141e"
    assert ramp["b"] == "#b42828"


def test_png_encoder_produces_valid_png(tmp_path):
    from lib import png
    blob = png.grid_to_png(["cw", "wc"], {"c": "#102030", "w": "#ffffff"}, scale=3)
    assert blob[:8] == b"\x89PNG\r\n\x1a\n"
    p = tmp_path / "t.png"
    p.write_bytes(blob)
    import subprocess
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(p)],
                         capture_output=True, text=True).stdout
    assert "pixelWidth: 6" in out and "pixelHeight: 6" in out


def test_png_phys_chunk_written_for_dpi():
    from lib import png
    blob = png.grid_to_png(["c"], {"c": "#000000"}, scale=2, dpi=144)
    assert b"pHYs" in blob
    import struct
    idx = blob.index(b"pHYs") + 4
    ppm_x, ppm_y, unit = struct.unpack(">IIB", blob[idx:idx + 9])
    assert unit == 1 and ppm_x == ppm_y == round(144 / 0.0254)
    assert b"pHYs" not in png.grid_to_png(["c"], {"c": "#000000"})
