"""Native status and Pokemon payload primitives."""

import base64
from pathlib import Path

from . import (
    assets,
    battle as battle_mode,
    collectors,
    data,
    engine,
    menu_bar,
    menu_panel,
    packs,
    paths,
    png,
    render,
    safari,
    scene,
    sprites,
    state,
    token_usage,
)

ENCOUNTER_ACTIONS = {
    "battle": (
        ("attack", "Fight", "⚔️"),
        ("ball", "Ball", "⚾"),
        ("run", "Run", "💨"),
    ),
    "safari": (
        ("rock", "Rock", "🪨"),
        ("bait", "Bait", "🍖"),
        ("ball", "Ball", "⚾"),
        ("run", "Run", "💨"),
    ),
}
ENCOUNTER_COMPACT_ACTIONS = {
    "attack": ("F", "Fight"),
    "rock": ("K", "Rock"),
    "bait": ("B", "Bait"),
    "ball": ("C", "Catch"),
    "run": ("R", "Run"),
}
ENCOUNTER_MODE_EMOJI = {"battle": "⚔️", "safari": "🌿"}
ENCOUNTER_OUTCOME_EMOJI = {
    "caught": "🎉",
    "fled": "💨",
    "ran": "💨",
    "ko": "💥",
    "buddy_faint": "😵",
}


def _path_exists(path):
    try:
        return Path(path).exists()
    except OSError:
        return False


def source_status():
    return {
        "claude_code": {
            "kind": "plugin",
            "automatic": True,
            "configured": "unknown",
            "log_root_exists": _path_exists(token_usage.CLAUDE_ROOT),
        },
        "codex": {
            "kind": "local_logs",
            "automatic": False,
            "log_root_exists": _path_exists(collectors.CODEX_ROOT),
        },
        "auggie": {
            "kind": "local_logs",
            "automatic": False,
            "log_root_exists": _path_exists(collectors.AUGMENT_ROOT),
        },
        "gemini": {
            "kind": "read_only_report",
            "automatic": False,
            "log_root_exists": _path_exists(token_usage.GEMINI_ROOT),
        },
        "native_desktop_apps": {
            "kind": "unsupported_v1",
            "automatic": False,
            "log_root_exists": False,
            "apps": ["ChatGPT", "Claude Desktop", "Cursor"],
        },
    }


def _dex_number(name):
    return data.DEX_NUMBERS.get(name)


def _build_pokemon_level_payload(pokemon):
    level = int(pokemon.get("level") or 1)
    xp = int(pokemon.get("xp") or 0)
    if level >= engine.LEVEL_CAP:
        return {
            "level": level,
            "xp": xp,
            "current": 0,
            "needed": 0,
            "percent": 100,
            "max_level": True,
        }
    floor = engine.xp_for_level(level)
    ceiling = engine.xp_for_level(level + 1)
    span = max(1, ceiling - floor)
    current = max(0, xp - floor)
    return {
        "level": level,
        "xp": xp,
        "current": current,
        "needed": max(0, ceiling - xp),
        "percent": min(100, int(current * 100 / span)),
        "max_level": False,
    }


def _render_sprite_base64(pokemon, source="gen5", scale=4):
    if not pokemon:
        return None
    try:
        if source == "box":
            grid, palette = packs.box_frames(
                pokemon["name"],
                pokemon.get("type", "Normal"),
                pokemon.get("shiny"),
            )[0]
        else:
            grid, palette = packs.gen5_frames(
                pokemon["name"],
                pokemon.get("type", "Normal"),
                pokemon.get("shiny"),
            )[0]
        blob = png.grid_to_png(grid, palette, scale, dpi=180)
    except Exception:
        return None
    return base64.b64encode(blob).decode()


def _render_brand_mark_base64():
    """Return the built-in chibi mark; native renders it as one-color art."""
    try:
        grid, palette = sprites.sprite_for("Charmander", "Fire")
        blob = png.grid_to_png(grid, palette, scale=2, dpi=180)
    except Exception:
        return None
    return base64.b64encode(blob).decode()


def _build_compact_token_summary():
    try:
        totals = token_usage.current_day_totals()
        error = None
    except Exception as exc:
        totals = {"today": 0, "yesterday": 0}
        error = str(exc)
    return {
        "today": {
            "label": "Today",
            "tokens": totals.get("today", 0),
            "compact": token_usage.compact_tokens(totals.get("today", 0)),
        },
        "yesterday": {
            "label": "Yesterday",
            "tokens": totals.get("yesterday", 0),
            "compact": token_usage.compact_tokens(totals.get("yesterday", 0)),
        },
        "error": error,
    }


def _build_pokemon_payload(pokemon, active_id=None, include_sprite=False):
    if pokemon is None:
        return None
    payload = {
        "id": pokemon.get("id"),
        "name": pokemon.get("name"),
        "emoji": pokemon.get("emoji"),
        "type": pokemon.get("type"),
        "rarity": pokemon.get("rarity"),
        "level": pokemon.get("level"),
        "xp": pokemon.get("xp"),
        "level_progress": _build_pokemon_level_payload(pokemon),
        "shiny": bool(pokemon.get("shiny")),
        "favorite": bool(pokemon.get("favorite")),
        "active": pokemon.get("id") == active_id,
        "caught_at": pokemon.get("caught_at"),
        "dex_no": _dex_number(pokemon.get("name")),
    }
    if pokemon.get("copy_index") is not None:
        payload["copy_index"] = pokemon.get("copy_index")
        payload["copy_total"] = pokemon.get("copy_total")
    if include_sprite:
        payload["sprite_base64"] = _render_sprite_base64(pokemon)
    return payload


def _build_encounter_action_payloads(mode):
    actions = []
    for action_id, label, emoji in ENCOUNTER_ACTIONS[mode]:
        shortcut, compact_label = ENCOUNTER_COMPACT_ACTIONS[action_id]
        actions.append({
            "id": action_id,
            "label": label,
            "emoji": emoji,
            "compact_label": compact_label,
            "shortcut": shortcut.lower(),
        })
    return actions


def _render_encounter_scene_base64(buddy, wild, mode, outcome="active", hp=None, options=True):
    """Render one native-only encounter image; failures leave the UI usable."""
    if not buddy or not wild:
        return None
    try:
        buddy_frame = packs.gen5_frames(
            buddy["name"], buddy.get("type", "Normal"), buddy.get("shiny")
        )[0]
        wild_frame = packs.gen5_frames(
            wild["name"], wild.get("type", "Normal"), wild.get("shiny")
        )[0]
        hp = hp or {}
        grid, palette = scene.battle_screen(
            buddy_frame,
            wild_frame,
            "caught" if outcome == "caught" else ("fled" if outcome != "active" else "active"),
            wild_hp_frac=hp.get("wild"),
            buddy_hp_frac=hp.get("buddy"),
            options=[label.upper() for _, label, _ in ENCOUNTER_ACTIONS[mode]] if options else None,
        )
        return base64.b64encode(png.grid_to_png(grid, palette, 2)).decode()
    except Exception:
        return None


def _build_encounter_result_payload(buddy, wild, mode, outcome, message):
    outcome_name = outcome.get("outcome")
    if outcome.get("caught"):
        outcome_name = "caught"
    elif outcome.get("fled"):
        outcome_name = "fled"
    elif outcome.get("ran"):
        outcome_name = "ran"
    outcome_name = outcome_name or "fled"
    wild_name = wild.get("name", "Wild Pokemon")
    titles = {
        "caught": f"Caught {wild_name}!",
        "fled": f"{wild_name} fled",
        "ran": "Got away safely",
        "ko": f"{wild_name} got away",
        "buddy_faint": "Your buddy needs a breather",
    }
    wild_payload = _build_pokemon_payload(wild, include_sprite=True)
    if wild_payload is not None:
        wild_payload["wild_level"] = wild.get("wild_level") or wild.get("level")
    return {
        "mode": mode,
        "mode_emoji": ENCOUNTER_MODE_EMOJI[mode],
        "outcome": outcome_name,
        "outcome_emoji": ENCOUNTER_OUTCOME_EMOJI.get(outcome_name, "✨"),
        "title": titles.get(outcome_name, "Encounter complete"),
        "message": message,
        "buddy": _build_pokemon_payload(buddy, include_sprite=True),
        "wild": wild_payload,
        "scene_base64": _render_encounter_scene_base64(
            buddy, wild, mode, outcome=outcome_name, options=False
        ),
    }


def _build_active_pokemon_payload(s):
    buddy = state.active_pokemon(s)
    if buddy is None:
        return None
    return {
        "id": buddy.get("id"),
        "name": buddy.get("name"),
        "emoji": buddy.get("emoji"),
        "type": buddy.get("type"),
        "rarity": buddy.get("rarity"),
        "level": buddy.get("level"),
        "xp": buddy.get("xp"),
        "level_progress": _build_pokemon_level_payload(buddy),
        "sprite_base64": _render_sprite_base64(buddy),
        "shiny": bool(buddy.get("shiny")),
        "caught_at": buddy.get("caught_at"),
    }


def _build_pending_encounter_payload(s):
    pending = s.get("pending_battle") or s.get("pending_encounter")
    if not pending:
        return None
    return {
        "name": pending.get("name", "wild"),
        "type": pending.get("type"),
        "shiny": bool(pending.get("shiny")),
        "mode": "battle" if s.get("pending_battle") else "safari",
        "sprite_base64": _render_sprite_base64(pending, scale=2),
    }


def _build_encounter_view_payload(s):
    pending = s.get("pending_battle")
    if pending:
        buddy = state.active_pokemon(s)
        wild = _build_pokemon_payload(pending, include_sprite=True)
        wild["wild_level"] = pending.get("wild_level") or pending.get("level")
        hp = {
            "wild": battle_mode.wild_hp_frac(pending),
            "buddy": battle_mode.buddy_hp_frac(pending),
        }
        return {
            "mode": "battle",
            "mode_emoji": ENCOUNTER_MODE_EMOJI["battle"],
            "state": "waiting",
            "title": f"Wild {pending.get('name', 'Pokemon')}",
            "wild": wild,
            "buddy": _build_pokemon_payload(buddy, s.get("active"), include_sprite=True),
            "status": battle_mode.status_text(pending),
            "message": pending.get("last_msg"),
            "scene_base64": _render_encounter_scene_base64(buddy, pending, "battle", hp=hp),
            "odds": {
                "catch_percent": int(battle_mode.catch_probability(pending) * 100 + 0.5),
            },
            "hp": {
                "wild_percent": int(battle_mode.wild_hp_frac(pending) * 100),
                "buddy_percent": int(battle_mode.buddy_hp_frac(pending) * 100),
            },
            "actions": _build_encounter_action_payloads("battle"),
        }
    pending = s.get("pending_encounter")
    if pending:
        buddy = state.active_pokemon(s)
        wild = _build_pokemon_payload(pending, include_sprite=True)
        wild["wild_level"] = pending.get("level")
        return {
            "mode": "safari",
            "mode_emoji": ENCOUNTER_MODE_EMOJI["safari"],
            "state": "waiting",
            "title": f"Wild {pending.get('name', 'Pokemon')}",
            "wild": wild,
            "buddy": _build_pokemon_payload(buddy, s.get("active"), include_sprite=True),
            "status": safari.status_text(pending),
            "message": pending.get("last_msg"),
            "scene_base64": _render_encounter_scene_base64(buddy, pending, "safari"),
            "odds": {
                "hint": safari.odds_hint(pending),
            },
            "balls": s.get("trainer", {}).get("balls", 0),
            "actions": _build_encounter_action_payloads("safari"),
        }
    return {
        "mode": None,
        "state": "empty",
        "title": "No wild encounter",
        "message": "No wild Pokemon is waiting.",
        "actions": [],
    }


def _render_menu_bar_icon_base64(s):
    buddy = state.active_pokemon(s)
    if buddy is None:
        return None
    try:
        grid, palette = packs.gen5_frames(
            buddy["name"],
            buddy.get("type", "Normal"),
            buddy.get("shiny"),
        )[0]
        blob = png.grid_to_png(grid, palette, 4, dpi=180)
    except Exception:
        return None
    return base64.b64encode(blob).decode()


def _build_recent_pokemon_payloads(s, limit=5, include_sprite=False):
    recent = sorted(
        s.get("pokemon", []),
        key=lambda pokemon: pokemon.get("caught_at", 0),
        reverse=True,
    )[:limit]
    return [
        _build_pokemon_payload(
            pokemon,
            s.get("active"),
            include_sprite=include_sprite,
        )
        for pokemon in recent
    ]


def app_status():
    s = state.load()
    trainer = s.get("trainer", {})
    pending = _build_pending_encounter_payload(s)
    packs_info = assets.pack_status()
    has_buddy = bool(s.get("pokemon"))
    needs_assets = any(
        not info.get("installed")
        for info in packs_info.values()
    )
    return {
        "schema_version": 1,
        "state_dir": str(paths.STATE_DIR),
        "state_file": str(paths.STATE_FILE),
        "state_file_exists": paths.STATE_FILE.exists(),
        "has_buddy": has_buddy,
        "active": _build_active_pokemon_payload(s),
        "pending": pending,
        "alert": pending is not None,
        "trainer": {
            "streak": trainer.get("streak", 0),
            "balls": trainer.get("balls", 0),
            "total_tokens": trainer.get("total_tokens", 0),
            "total_tokens_compact": render.compact_number(trainer.get("total_tokens", 0)),
            "caught_count": len(s.get("pokemon", [])),
            "species_count": len({p.get("name") for p in s.get("pokemon", [])}),
        },
        "packs": packs_info,
        "setup": {
            "needs_starter": not has_buddy,
            "needs_assets": needs_assets,
            "assets_optional": True,
            "ready": has_buddy,
            "asset_kinds": list(assets.PACK_ORDER),
        },
        "sources": source_status(),
        "recent": _build_recent_pokemon_payloads(s, limit=1, include_sprite=True),
        "tokens": _build_compact_token_summary(),
        "brand_mark_base64": _render_brand_mark_base64(),
        "menu_bar_icon_base64": _render_menu_bar_icon_base64(s),
        "menu_bar": menu_bar.runtime_payload(s),
        "native_menu": menu_panel.build_payload(pending),
    }
