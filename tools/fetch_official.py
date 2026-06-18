#!/usr/bin/env python3
"""Fetch + convert official Gen 2 menu icons into a local buddymon pack.

Run manually, once (network!):  uv run --with pillow --no-project python3 tools/fetch_official.py

Sources (downloaded to ~/.local/state/buddymon/packs/, never committed —
these are Nintendo's sprites, preserved by the pret and PokéSprite projects):
  - pret/pokecrystal  gfx/icons/*.png           16x32 = two stacked 16x16 frames
  - pret/pokecrystal  data/pokemon/menu_icons.asm  species -> icon class
  - msikma/pokesprite icons/pokemon/{regular,shiny}/*.png  palette reference

The Game Boy icons are 4-shade grayscale; we recolor each species using a
ramp extracted from its modern PokéSprite box icon.
"""
import json
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import data, paths  # noqa: E402

CRYSTAL_RAW = "https://raw.githubusercontent.com/pret/pokecrystal/master"
POKESPRITE_RAW = "https://raw.githubusercontent.com/msikma/pokesprite/master"

# Post-Gen-2 dex species: hand-picked best-fit Crystal icon classes.
EXTRA_ICONS = {
    "Zigzagoon": "fox", "Bidoof": "fox", "Wooloo": "jigglypuff",
    "Lechonk": "monster", "Riolu": "fighter", "Lucario": "fighter",
    "Munchlax": "snorlax", "Beldum": "voltorb", "Gible": "monster",
    "Rayquaza": "gyarados", "Jirachi": "clefairy",
}

# Shade chars used in pack grids: '.'=transparent  w=interior white
# a=light gray  b=mid gray  c=black/outline
SHADE_CHARS = {0: "w", 1: "a", 2: "b", 3: "c"}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "buddymon-fetch"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def parse_menu_icons(asm_text):
    """menu_icons.asm -> {'BULBASAUR': 'bulbasaur', 'CHARIZARD': 'bigmon', ...}"""
    mapping = {}
    for m in re.finditer(r"db ICON_(\w+)\s*;\s*(\w+)", asm_text):
        icon, species = m.group(1).lower(), m.group(2)
        mapping[species] = icon
    return mapping


def dex_species():
    """Every name that can appear as a buddy or catch."""
    names = set(data.WILDS) | set(data.STARTERS)
    for info in data.STARTERS.values():
        names.update(n for n, _, _ in info["evolutions"])
    names.update(n for n, _ in data.EEVEE_BRANCHES)
    return sorted(names)


def asm_key(name):
    """'Ho-Oh' -> 'HO_OH', matching pokecrystal constants."""
    return name.upper().replace("-", "_").replace(" ", "_").replace(".", "").replace("'", "")


def resolve_icon(name, asm_map):
    if name in EXTRA_ICONS:
        return EXTRA_ICONS[name]
    return asm_map.get(asm_key(name))


def pokesprite_slug(name):
    return name.lower().replace(" ", "-").replace(".", "").replace("'", "")


# ── image -> grid conversion (pure-ish; PIL objects in, plain data out) ──────


def quantize_icon(img):
    """16x16 RGBA frame -> rows of shade indices 0..3 (0 = white)."""
    px = list(img.convert("RGBA").getdata())
    grays = sorted({(r + g + b) // 3 for r, g, b, _ in px}, reverse=True)
    # Lightest gray is "white"; map remaining light->dark onto 1..3.
    levels = {g: min(i, 3) for i, g in enumerate(grays)}
    w = img.width
    return [[levels[(r + g + b) // 3] for r, g, b, _ in px[y * w:(y + 1) * w]]
            for y in range(img.height)]


def outside_white(rows):
    """Flood fill from the border: white cells connected to the edge are
    background (transparent); enclosed white stays as highlight."""
    h, w = len(rows), len(rows[0])
    outside = [[False] * w for _ in range(h)]
    stack = [(x, y) for x in range(w) for y in (0, h - 1) if rows[y][x] == 0]
    stack += [(x, y) for y in range(h) for x in (0, w - 1) if rows[y][x] == 0]
    while stack:
        x, y = stack.pop()
        if not (0 <= x < w and 0 <= y < h) or outside[y][x] or rows[y][x] != 0:
            continue
        outside[y][x] = True
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return outside


def frame_to_grid(rows):
    outside = outside_white(rows)
    return ["".join("." if outside[y][x] else SHADE_CHARS[v]
                    for x, v in enumerate(row))
            for y, row in enumerate(rows)]


def crop_frames(frames):
    """Drop rows blank in every frame (top/bottom only, keep frames aligned).
    Prefer an even height for half-block pairing; pixels.render pads odd
    grids anyway, so this is cosmetic, not load-bearing."""
    blank = [all(set(f[y]) == {"."} for f in frames) for y in range(len(frames[0]))]
    top = next((i for i, b in enumerate(blank) if not b), 0)
    end = len(blank) - next((i for i, b in enumerate(reversed(blank)) if not b), 0)
    if (end - top) % 2 and top > 0:
        top -= 1
    return [f[top:end] for f in frames]


def luminance(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def extract_ramp(img):
    """PokéSprite icon -> {'a': light, 'b': body, 'c': dark} hex ramp."""
    counts = Counter(
        (r, g, b) for r, g, b, alpha in img.convert("RGBA").getdata() if alpha > 128
    )
    if not counts:
        return {"a": "#c0c0c0", "b": "#808080", "c": "#202020"}
    colors = sorted(counts, key=luminance)
    n = len(colors)
    dark = colors[0]
    # body = most frequent color in the middle luminance band
    mid_band = colors[max(0, n // 4): max(1, 3 * n // 4)] or colors
    body = max(mid_band, key=lambda c: counts[c])
    light_band = colors[3 * n // 4:] or colors
    light = max(light_band, key=lambda c: counts[c])

    def hx(c):
        return "#%02x%02x%02x" % c
    return {"a": hx(light), "b": hx(body), "c": hx(dark)}


def main():
    from PIL import Image
    import io

    asm_map = parse_menu_icons(
        fetch(f"{CRYSTAL_RAW}/data/pokemon/menu_icons.asm").decode())
    species = dex_species()

    unresolved = [n for n in species if not resolve_icon(n, asm_map)]
    if unresolved:
        sys.exit(f"no icon class for: {', '.join(unresolved)} — extend EXTRA_ICONS")

    icon_frames = {}  # class -> [grid, grid]
    pack = {}
    for name in species:
        icon = resolve_icon(name, asm_map)
        if icon not in icon_frames:
            png = fetch(f"{CRYSTAL_RAW}/gfx/icons/{icon}.png")
            img = Image.open(io.BytesIO(png))
            rows = quantize_icon(img)
            frames = [frame_to_grid(rows[:16]), frame_to_grid(rows[16:32])]
            icon_frames[icon] = crop_frames(frames)
            print(f"icon {icon}: {len(icon_frames[icon][0])} rows")

        slug = pokesprite_slug(name)
        entry = {"frames": icon_frames[icon], "palette": {"w": "#f8f8f8"}}
        try:
            img = Image.open(io.BytesIO(
                fetch(f"{POKESPRITE_RAW}/icons/pokemon/regular/{slug}.png")))
            entry["palette"].update(extract_ramp(img))
            shiny_img = Image.open(io.BytesIO(
                fetch(f"{POKESPRITE_RAW}/icons/pokemon/shiny/{slug}.png")))
            entry["palette_shiny"] = {"w": "#f8f8f8", **extract_ramp(shiny_img)}
        except Exception as e:
            print(f"  palette miss for {name} ({e}); type tint fallback")
            from lib.sprites import TYPE_TINTS
            ptype = data.WILDS.get(name, ("Normal",))[0]
            tint = TYPE_TINTS.get(ptype, "#a8a878")
            entry["palette"].update({"a": "#e8e8e8", "b": tint, "c": "#202030"})
        pack[name] = entry
        print(f"  {name} <- {icon}")

    paths.ensure_dirs()
    out = paths.STATE_DIR / "packs"
    out.mkdir(parents=True, exist_ok=True)
    (out / "gen2.json").write_text(json.dumps(pack), encoding="utf-8")
    print(f"\nwrote {out / 'gen2.json'} — {len(pack)} species, {len(icon_frames)} icon classes")


if __name__ == "__main__":
    main()
