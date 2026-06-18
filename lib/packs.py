"""Sprite pack loading. Packs are generated JSON under state (see
tools/fetch_official.py) — runtime stays stdlib-only and network-free."""
import json
import re

from . import paths, sprites

_cache = {}  # also holds gen5 lazy state under "__gen5_species__"/"__gen5_mono__"

# gen5 is large (~17MB/649 species); load it per-species on demand instead of
# holding the whole pack resident in the long-lived menu-bar stream.
_GEN5_CACHE_MAX = 8
_COMPACT_MAX_W = 16
_COMPACT_MAX_H = 16


def load(name="gen2"):
    if name not in _cache:
        try:
            _cache[name] = json.loads(
                (paths.STATE_DIR / "packs" / f"{name}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _cache[name] = {}
    return _cache[name]


def _gen5_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _gen5_entry(name):
    """One gen5 species entry, lazily. Split per-species files preferred;
    falls back to a one-time read of the legacy monolithic gen5.json."""
    species = _cache.setdefault("__gen5_species__", {})
    if name in species:
        return species[name]
    split = paths.STATE_DIR / "packs" / "gen5" / f"{_gen5_slug(name)}.json"
    if split.exists():
        try:
            entry = json.loads(split.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            entry = None
        if len(species) >= _GEN5_CACHE_MAX:
            species.pop(next(iter(species)))
        species[name] = entry
        return entry
    # legacy monolithic pack (un-resplit install): read once, keep resident
    if "__gen5_mono__" not in _cache:
        try:
            _cache["__gen5_mono__"] = json.loads(
                (paths.STATE_DIR / "packs" / "gen5.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _cache["__gen5_mono__"] = {}
    return _cache["__gen5_mono__"].get(name)


def _uniform_grid(grid):
    rows = list(grid) or ["."]
    width = max(len(row) for row in rows) or 1
    return [row.ljust(width, ".") for row in rows]


def _scale_grid(grid, factor):
    if factor == 1:
        return list(grid)
    src_h, src_w = len(grid), len(grid[0])
    dst_w = max(1, round(src_w * factor))
    dst_h = max(1, round(src_h * factor))
    out = []
    for y in range(dst_h):
        sy = min(src_h - 1, int(y / factor))
        row = []
        for x in range(dst_w):
            sx = min(src_w - 1, int(x / factor))
            row.append(grid[sy][sx])
        out.append("".join(row))
    return out


def _fit_compact(grid):
    grid = _uniform_grid(grid)
    scale = min(1.0, _COMPACT_MAX_W / len(grid[0]), _COMPACT_MAX_H / len(grid))
    return _scale_grid(grid, scale) if scale < 1.0 else grid


def sprite_frames(name, ptype="Normal", shiny=False):
    """Compact art for statusline/cutscenes:
    Gen 2 animation > scaled official box sprite > chibi > silhouette."""
    entry = load().get(name)
    if entry:
        palette = entry.get("palette_shiny") if shiny else None
        palette = palette or entry.get("palette", {})
        return [(grid, palette) for grid in entry["frames"]]
    box = load("box").get(name)
    if box:
        if shiny and box.get("shiny_grid"):
            return [(_fit_compact(box["shiny_grid"]), box["palette_shiny"])]
        return [(_fit_compact(box["grid"]), box["palette"])]
    return [sprites.sprite_for(name, ptype)]


def box_frames(name, ptype="Normal", shiny=False):
    """Unique per-species art for terminal stare-at surfaces (dex grid):
    PokéSprite 40x30 box pack > gen2 > chibi/silhouette. Always one frame."""
    entry = load("box").get(name)
    if entry:
        if shiny and entry.get("shiny_grid"):
            return [(entry["shiny_grid"], entry["palette_shiny"])]
        return [(entry["grid"], entry["palette"])]
    return sprite_frames(name, ptype, shiny)


def gen5_frames(name, ptype="Normal", shiny=False):
    """Animated Gen 5 (Black/White) art for the menu bar (PNG surfaces only).
    Lazy per-species load; falls back box > gen2 > silhouette."""
    entry = _gen5_entry(name)
    if entry:
        key = "shiny_frames" if shiny and entry.get("shiny_frames") else "frames"
        return [tuple(fr) for fr in entry[key]]
    return box_frames(name, ptype, shiny)
