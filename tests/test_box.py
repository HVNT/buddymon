"""Box (PokéSprite 40x30 unique) pack: quantizer + loader fallback."""
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import packs, pixels


def test_quantizer_crops_and_maps_colors():
    from PIL import Image
    from tools import fetch_box
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    img.putpixel((2, 3), (255, 0, 0, 255))
    img.putpixel((3, 3), (0, 0, 255, 255))
    grid, palette = fetch_box.quantize(img)
    # cropped to the 2x1 content bbox
    assert len(grid) == 1 and len(grid[0]) == 2
    assert set(palette.values()) == {"#ff0000", "#0000ff"}
    chars = {c for row in grid for c in row} - {"."}
    assert chars <= set(palette)


def test_quantizer_transparent_is_dot():
    from PIL import Image
    from tools import fetch_box
    img = Image.new("RGBA", (3, 1), (0, 0, 0, 0))
    img.putpixel((0, 0), (10, 20, 30, 255))
    img.putpixel((2, 0), (10, 20, 30, 255))
    grid, _ = fetch_box.quantize(img)
    assert grid[0][1] == "."  # gap between the two opaque pixels stays transparent


def test_box_frames_prefers_box_then_falls_back(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    packs._cache.clear()
    # no box pack on disk -> falls through to gen2/chibi (non-empty frame)
    assert packs.box_frames("Pikachu", "Electric")

    (tmp_path / "packs").mkdir()
    entry = {"grid": ["ab", "ba"], "palette": {"a": "#111111", "b": "#222222"},
             "shiny_grid": ["aa", "bb"], "palette_shiny": {"a": "#aa0000", "b": "#00aa00"}}
    (tmp_path / "packs" / "box.json").write_text(json.dumps({"Gengar": entry}))
    packs._cache.clear()

    frames = packs.box_frames("Gengar", "Ghost")
    assert len(frames) == 1 and frames[0][1]["a"] == "#111111"
    shiny = packs.box_frames("Gengar", "Ghost", shiny=True)
    assert shiny[0][1]["a"] == "#aa0000"
    assert len(pixels.render(*frames[0])) == 1
    packs._cache.clear()
