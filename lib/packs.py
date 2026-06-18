"""Sprite pack loading. Packs are generated JSON under state (see
tools/fetch_official.py) — runtime stays stdlib-only and network-free."""
import json

from . import paths, sprites

_cache = {}


def load(name="gen2"):
    if name not in _cache:
        try:
            _cache[name] = json.loads(
                (paths.STATE_DIR / "packs" / f"{name}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _cache[name] = {}
    return _cache[name]


def sprite_frames(name, ptype="Normal", shiny=False):
    """Compact art for the statusline/cutscenes: gen2 (2 frames) > chibi > silhouette."""
    entry = load().get(name)
    if entry:
        palette = entry.get("palette_shiny") if shiny else None
        palette = palette or entry.get("palette", {})
        return [(grid, palette) for grid in entry["frames"]]
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
    Multi-frame; falls back box > gen2 > silhouette. Frames stored as
    [grid, palette] pairs."""
    entry = load("gen5").get(name)
    if entry:
        key = "shiny_frames" if shiny and entry.get("shiny_frames") else "frames"
        return [tuple(fr) for fr in entry[key]]
    return box_frames(name, ptype, shiny)
