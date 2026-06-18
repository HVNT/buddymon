"""Animated Gen 5 pack: GIF coalesce/subsample/quantize + loader fallback."""
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import packs, pixels


def _make_gif(frames_rgba, path):
    from PIL import Image
    imgs = []
    for grid in frames_rgba:
        im = Image.new("RGBA", (len(grid[0]), len(grid)), (0, 0, 0, 0))
        for y, row in enumerate(grid):
            for x, c in enumerate(row):
                im.putpixel((x, y), c)
        imgs.append(im.convert("P"))
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=100, loop=0)


def test_frames_pack_subsamples_and_aligns(tmp_path):
    from tools import fetch_gen5
    R = (255, 0, 0, 255)
    T = (0, 0, 0, 0)
    # two distinct 2x2 frames, opaque pixel in different corners
    f1 = [[R, T], [T, T]]
    f2 = [[T, T], [T, R]]
    gif = tmp_path / "x.gif"
    _make_gif([f1, f2, f1, f2], gif)
    frames = fetch_gen5.frames_pack(gif.read_bytes())
    assert 1 <= len(frames) <= fetch_gen5.KEYFRAMES
    widths = {len(g[0]) for g, _ in frames}
    heights = {len(g) for g, _ in frames}
    assert len(widths) == 1 and len(heights) == 1  # union bbox -> aligned
    for grid, palette in frames:
        chars = {c for row in grid for c in row} - {"."}
        assert chars <= set(palette)


def _entry(c="#111111"):
    return {"frames": [[["ab", "ba"], {"a": c, "b": "#222222"}],
                       [["ba", "ab"], {"a": c, "b": "#222222"}]]}


def test_gen5_lazy_per_species(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    packs._cache.clear()
    assert packs.gen5_frames("Pikachu", "Electric")  # no pack -> box/gen2 fallback

    d = tmp_path / "packs" / "gen5"
    d.mkdir(parents=True)
    (d / "reshiram.json").write_text(json.dumps(_entry()))
    packs._cache.clear()

    frames = packs.gen5_frames("Reshiram", "Dragon")
    assert len(frames) == 2 and frames[0][0] != frames[1][0]
    assert frames[0][1]["a"] == "#111111"
    assert len(pixels.render(*frames[0])) == 1
    packs._cache.clear()


def test_gen5_monolithic_fallback(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    packs._cache.clear()
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "gen5.json").write_text(json.dumps({"Zekrom": _entry("#0a0a0a")}))
    frames = packs.gen5_frames("Zekrom", "Dragon")
    assert frames[0][1]["a"] == "#0a0a0a"  # legacy single-file path still works
    packs._cache.clear()


def test_gen5_cache_is_bounded(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    packs._cache.clear()
    d = tmp_path / "packs" / "gen5"
    d.mkdir(parents=True)
    for i in range(packs._GEN5_CACHE_MAX + 5):
        (d / f"mon{i}.json").write_text(json.dumps(_entry()))
        packs.gen5_frames(f"Mon{i}", "Normal")
    assert len(packs._cache["__gen5_species__"]) <= packs._GEN5_CACHE_MAX
    packs._cache.clear()
