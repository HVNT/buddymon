#!/usr/bin/env python3
"""Fetch animated Gen 5 (Black/White) sprites into a multi-frame pack.

Dev tool, run manually (network):
    uv run --with pillow --no-project python3 tools/fetch_gen5.py

The BW idle animations (~50 frames, 96x96) are subsampled to a few keyframes
that flip on the menu bar's ~1s stream tick. Image surfaces only (the menu bar
compresses them); terminal surfaces keep the compact box/gen2 packs. Output is
local-only: ~/.local/state/buddymon/packs/gen5.json. Nintendo's pixels,
preserved by PokeAPI; never committed.
"""
import io
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import scene  # noqa: E402

SPRITES = ("https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/"
           "pokemon/versions/generation-v/black-white/animated")
CSV = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"
MAX_DEX = 649
KEYFRAMES = 3
MAX_COLORS = 32
_POOL = scene._CHAR_POOL.replace(".", "")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "buddymon-gen5"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def dex_names():
    """id -> display name, 1..MAX_DEX, via gen_dex's naming."""
    import csv
    from tools.gen_dex import display_name
    rows = list(csv.reader(io.StringIO(fetch(f"{CSV}/pokemon_species.csv").decode())))
    return {int(r[0]): display_name(r[1]) for r in rows[1:] if int(r[0]) <= MAX_DEX}


def coalesce_frames(gif):
    """Composite GIF frames over each other (resolve disposal) -> list[RGBA]."""
    from PIL import Image, ImageSequence
    frames, base = [], None
    for fr in ImageSequence.Iterator(gif):
        rgba = fr.convert("RGBA")
        if base is None:
            base = rgba.copy()
        else:
            base = base.copy()
            base.alpha_composite(rgba)
        frames.append(base.copy())
    return frames


def pick_keyframes(frames):
    n = len(frames)
    if n <= KEYFRAMES:
        return frames
    return [frames[round(i * (n - 1) / (KEYFRAMES - 1))] for i in range(KEYFRAMES)]


def union_bbox(frames):
    boxes = [f.getbbox() for f in frames if f.getbbox()]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def to_grid(img):
    """Cropped+reduced RGBA frame -> (grid, palette); transparent = '.'."""
    if img.getcolors(maxcolors=1 << 24) and len(img.getcolors(1 << 24)) > MAX_COLORS:
        img = img.quantize(colors=MAX_COLORS).convert("RGBA")
    px = img.load()
    w, h = img.size
    palette, by_color, pool, grid = {}, {}, iter(_POOL), []
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


def frames_pack(gif_bytes):
    from PIL import Image
    frames = coalesce_frames(Image.open(io.BytesIO(gif_bytes)))
    keys = pick_keyframes(frames)
    bbox = union_bbox(keys)
    keys = [f.crop(bbox) for f in keys] if bbox else keys
    return [to_grid(f) for f in keys]


def _slug(name):
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
    names = dex_names()
    out = Path.home() / ".local" / "state" / "buddymon" / "packs" / "gen5"
    out.mkdir(parents=True, exist_ok=True)
    written = 0
    for sid in range(1, MAX_DEX + 1):
        name = names.get(sid)
        if not name:
            continue
        entry = {}
        try:
            entry["frames"] = frames_pack(fetch(f"{SPRITES}/{sid}.gif"))
        except Exception as e:
            print(f"  MISS {sid} {name}: {e}")
            continue
        try:
            entry["shiny_frames"] = frames_pack(fetch(f"{SPRITES}/shiny/{sid}.gif"))
        except Exception:
            pass
        # one file per species so the runtime loads only what it shows
        (out / f"{_slug(name)}.json").write_text(json.dumps(entry), encoding="utf-8")
        written += 1
        print(f"  #{sid:<3} {name:14} {len(entry['frames'])} frames "
              f"{len(entry['frames'][0][0][0])}x{len(entry['frames'][0][0])}")

    # retire the legacy monolithic pack so packs.py uses the split layout
    mono = out.parent / "gen5.json"
    if mono.exists():
        mono.unlink()
    total_mb = sum(f.stat().st_size for f in out.glob("*.json")) / 1e6
    print(f"\nwrote {written} files to {out} — {total_mb:.1f} MB total "
          f"(loaded per-species at runtime, not all at once)")


if __name__ == "__main__":
    main()
