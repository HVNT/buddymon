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
    """Best available art: gen2 pack (2 frames) > chibi (1) > silhouette (1)."""
    entry = load().get(name)
    if entry:
        palette = entry.get("palette_shiny") if shiny else None
        palette = palette or entry.get("palette", {})
        return [(grid, palette) for grid in entry["frames"]]
    return [sprites.sprite_for(name, ptype)]
