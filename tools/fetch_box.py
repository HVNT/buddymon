#!/usr/bin/env python3
"""Fetch unique per-species PokéSprite box sprites (40x30, full color).

Dev tool, run manually (network):
    uv run --with pillow --no-project python3 tools/fetch_box.py

Unlike the Gen 2 menu icons (37 shared shapes), these are distinct per species.
Used on the surfaces you study — menu bar buddy, dex grid, battle screen — while
the compact statusline keeps the 16x16 Gen 2 pack. Output is local-only:
~/.local/state/buddymon/packs/box.json. Nintendo's pixels, preserved by
PokéSprite; never committed.
"""
import io
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import paths, scene  # noqa: E402
from tools.fetch_official import dex_species, pokesprite_slug, POKESPRITE_RAW  # noqa: E402

# Reuse the compositor's char pool; '.' stays reserved for transparency.
_POOL = scene._CHAR_POOL.replace(".", "")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "buddymon-box"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def quantize(img):
    """RGBA PokéSprite -> (grid, palette), cropped to content, '.' transparent."""
    from PIL import Image
    img = img.convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    px = img.load()
    w, h = img.size
    palette, by_color = {}, {}
    pool = iter(_POOL)
    grid = []
    for y in range(h):
        row = []
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 128:
                row.append(".")
                continue
            hexc = "#%02x%02x%02x" % (r, g, b)
            ch = by_color.get(hexc)
            if ch is None:
                ch = next(pool)
                by_color[hexc] = ch
                palette[ch] = hexc
            row.append(ch)
        grid.append("".join(row))
    return grid, palette


def main():
    from PIL import Image

    pack = {}
    for name in dex_species():
        slug = pokesprite_slug(name)
        entry = {}
        for kind, key in (("regular", "palette_grid"), ("shiny", "shiny")):
            try:
                png = fetch(f"{POKESPRITE_RAW}/icons/pokemon/{kind}/{slug}.png")
                grid, palette = quantize(Image.open(io.BytesIO(png)))
            except Exception as e:
                if kind == "regular":
                    print(f"  MISS {name} ({slug}): {e}")
                continue
            if kind == "regular":
                entry["grid"], entry["palette"] = grid, palette
            else:
                entry["shiny_grid"], entry["palette_shiny"] = grid, palette
        if "grid" in entry:
            pack[name] = entry
            print(f"  {name:14} {len(entry['grid'][0])}x{len(entry['grid'])}"
                  f"  {len(entry['palette'])} colors")

    out = paths.STATE_DIR / "packs"
    out.mkdir(parents=True, exist_ok=True)
    (out / "box.json").write_text(json.dumps(pack), encoding="utf-8")
    print(f"\nwrote {out / 'box.json'} — {len(pack)} species")


if __name__ == "__main__":
    main()
