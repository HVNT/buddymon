"""Structured bridge for the native BuddyMon app.

The existing CLI output is optimized for humans and SwiftBar. The macOS app
needs stable JSON so it can render state, run setup, and report repair steps
without parsing terminal text.
"""
import base64
import json
import random
import time
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
    trainer_card,
)


SCREEN_ALIASES = {
    "token-usage": "tokens",
    "token_usage": "tokens",
}
SETTING_LABELS = {
    "mode": "Encounter mode",
    "notifications": "Notifications",
    "menu_launcher": "Menu launcher",
    "menu_replace": "Replace menus",
    "terminal_graphics": "Terminal graphics",
    "share_reveal": "Reveal shares",
    "share_banner": "Share banners",
}
SETTING_HELP = {
    "mode": "Quick catches common wilds; Safari and Battle make every wild interactive.",
    "notifications": "Rare-event banner behavior.",
    "menu_launcher": "Preferred terminal app for deep BuddyMon screens.",
    "menu_replace": "Close the prior BuddyMon Ghostty menu before opening a new one.",
    "terminal_graphics": "Inline image behavior in terminal screens.",
    "share_reveal": "Reveal the exported Showcase PNG in Finder.",
    "share_banner": "Show a macOS banner after sharing Showcase.",
}
SETTING_VALUE_LABELS = {
    "mode": {
        "auto": "Quick",
        "safari": "Safari",
        "battle": "Battle",
    },
    "notifications": {
        "on": "On",
        "silent": "Silent",
        "off": "Off",
    },
    "menu_launcher": {
        "auto": "Auto",
        "ghostty": "Ghostty",
        "iterm": "iTerm2",
        "terminal": "Terminal.app",
    },
    "terminal_graphics": {
        "auto": "Auto",
        "off": "Off",
    },
    "menu_replace": {
        "on": "On",
        "off": "Off",
    },
    "share_reveal": {
        "on": "On",
        "off": "Off",
    },
    "share_banner": {
        "on": "On",
        "off": "Off",
    },
}
SETTING_GROUPS = {
    "mode": "Gameplay",
    "notifications": "Notifications",
    "menu_launcher": "Display",
    "menu_replace": "Display",
    "terminal_graphics": "Display",
    "share_reveal": "Sharing",
    "share_banner": "Sharing",
}
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


def _pokemon_level_payload(pokemon):
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


def _sprite_base64(pokemon, source="gen5", scale=4):
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


def _brand_mark_base64():
    """Return the built-in chibi mark; native renders it as one-color art."""
    try:
        grid, palette = sprites.sprite_for("Charmander", "Fire")
        blob = png.grid_to_png(grid, palette, scale=2, dpi=180)
    except Exception:
        return None
    return base64.b64encode(blob).decode()


def _compact_token_summary():
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


def _pokemon_payload(pokemon, active_id=None, include_sprite=False):
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
        "level_progress": _pokemon_level_payload(pokemon),
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
        payload["sprite_base64"] = _sprite_base64(pokemon)
    return payload


def _encounter_actions(mode):
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


def _encounter_scene_base64(buddy, wild, mode, outcome="active", hp=None, options=True):
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


def _encounter_result_payload(buddy, wild, mode, outcome, message):
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
    wild_payload = _pokemon_payload(wild, include_sprite=True)
    if wild_payload is not None:
        wild_payload["wild_level"] = wild.get("wild_level") or wild.get("level")
    return {
        "mode": mode,
        "mode_emoji": ENCOUNTER_MODE_EMOJI[mode],
        "outcome": outcome_name,
        "outcome_emoji": ENCOUNTER_OUTCOME_EMOJI.get(outcome_name, "✨"),
        "title": titles.get(outcome_name, "Encounter complete"),
        "message": message,
        "buddy": _pokemon_payload(buddy, include_sprite=True),
        "wild": wild_payload,
        "scene_base64": _encounter_scene_base64(
            buddy, wild, mode, outcome=outcome_name, options=False
        ),
    }


def _active_payload(s):
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
        "level_progress": _pokemon_level_payload(buddy),
        "sprite_base64": _sprite_base64(buddy),
        "shiny": bool(buddy.get("shiny")),
        "caught_at": buddy.get("caught_at"),
    }


def _pending_payload(s):
    pending = s.get("pending_battle") or s.get("pending_encounter")
    if not pending:
        return None
    return {
        "name": pending.get("name", "wild"),
        "type": pending.get("type"),
        "shiny": bool(pending.get("shiny")),
        "mode": "battle" if s.get("pending_battle") else "safari",
        "sprite_base64": _sprite_base64(pending, scale=2),
    }


def _pending_view_payload(s):
    pending = s.get("pending_battle")
    if pending:
        buddy = state.active_pokemon(s)
        wild = _pokemon_payload(pending, include_sprite=True)
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
            "buddy": _pokemon_payload(buddy, s.get("active"), include_sprite=True),
            "status": battle_mode.status_text(pending),
            "message": pending.get("last_msg"),
            "scene_base64": _encounter_scene_base64(buddy, pending, "battle", hp=hp),
            "odds": {
                "catch_percent": int(battle_mode.catch_probability(pending) * 100 + 0.5),
            },
            "hp": {
                "wild_percent": int(battle_mode.wild_hp_frac(pending) * 100),
                "buddy_percent": int(battle_mode.buddy_hp_frac(pending) * 100),
            },
            "actions": _encounter_actions("battle"),
        }
    pending = s.get("pending_encounter")
    if pending:
        buddy = state.active_pokemon(s)
        wild = _pokemon_payload(pending, include_sprite=True)
        wild["wild_level"] = pending.get("level")
        return {
            "mode": "safari",
            "mode_emoji": ENCOUNTER_MODE_EMOJI["safari"],
            "state": "waiting",
            "title": f"Wild {pending.get('name', 'Pokemon')}",
            "wild": wild,
            "buddy": _pokemon_payload(buddy, s.get("active"), include_sprite=True),
            "status": safari.status_text(pending),
            "message": pending.get("last_msg"),
            "scene_base64": _encounter_scene_base64(buddy, pending, "safari"),
            "odds": {
                "hint": safari.odds_hint(pending),
            },
            "balls": s.get("trainer", {}).get("balls", 0),
            "actions": _encounter_actions("safari"),
        }
    return {
        "mode": None,
        "state": "empty",
        "title": "No wild encounter",
        "message": "No wild Pokemon is waiting.",
        "actions": [],
    }


def _menu_bar_icon(s):
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


def app_status():
    s = state.load()
    trainer = s.get("trainer", {})
    pending = _pending_payload(s)
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
        "active": _active_payload(s),
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
        "recent": _recent_pokemon(s, limit=1, include_sprite=True),
        "tokens": _compact_token_summary(),
        "brand_mark_base64": _brand_mark_base64(),
        "menu_bar_icon_base64": _menu_bar_icon(s),
        "menu_bar": menu_bar.runtime_payload(s),
        "native_menu": menu_panel.build_payload(pending),
    }


def _menu_panel_fixture_status(s, *, recent=None, error=None):
    """Build deterministic compact-panel input without touching player state."""
    if error:
        return {"schema_version": 1, "error": error}
    trainer = s.get("trainer", {})
    pending = _pending_payload(s)
    return {
        "schema_version": 1,
        "has_buddy": bool(s.get("pokemon")),
        "active": _active_payload(s),
        "pending": pending,
        "trainer": {
            "streak": trainer.get("streak", 0),
            "balls": trainer.get("balls", 0),
            "caught_count": len(s.get("pokemon", [])),
            "species_count": len({p.get("name") for p in s.get("pokemon", [])}),
        },
        "recent": (
            _recent_pokemon(s, limit=1, include_sprite=True)
            if recent is None
            else recent
        ),
        "tokens": {
            "today": {"label": "Today", "tokens": 148_200, "compact": "148K"},
            "yesterday": {
                "label": "Yesterday",
                "tokens": 102_400,
                "compact": "102K",
            },
            "error": None,
        },
        "brand_mark_base64": _brand_mark_base64(),
        "native_menu": menu_panel.build_payload(pending),
    }


def menu_panel_harness():
    """Return representative states rendered by the shipping compact panel."""
    def set_level_progress(pokemon, level, percent):
        pokemon["level"] = level
        floor = engine.xp_for_level(level)
        ceiling = engine.xp_for_level(min(engine.LEVEL_CAP, level + 1))
        pokemon["xp"] = floor + int((ceiling - floor) * percent / 100)

    empty = state.default_state()

    ready = state.default_state()
    ready_buddy = engine.create_starter(ready, "Charmander")
    set_level_progress(ready_buddy, 12, 64)
    ready["trainer"]["streak"] = 3

    recent = state.default_state()
    recent_buddy = engine.new_pokemon(
        "Charizard", "Fire", "🐉", "starter", level=80
    )
    recent["pokemon"].append(recent_buddy)
    recent["active"] = recent_buddy["id"]
    set_level_progress(recent_buddy, 80, 58)
    caught = engine.new_pokemon(
        "Trubbish", "Poison", "🗑️", "common", level=14
    )
    caught["caught_at"] = recent_buddy.get("caught_at", 0) + 1
    recent["pokemon"].append(caught)
    recent["trainer"]["streak"] = 7

    pending = state.default_state()
    engine.create_starter(pending, "Charmander")
    pending["pending_encounter"] = {
        "name": "Eevee",
        "type": "Normal",
        "rarity": "rare",
        "shiny": False,
        "created_ts": 1,
    }

    shiny = state.default_state()
    shiny_buddy = engine.create_starter(shiny, "Pikachu")
    shiny_buddy["shiny"] = True
    shiny_buddy["level"] = 30

    long_values = state.default_state()
    long_buddy = engine.new_pokemon(
        "Feraligatr", "Water", "🌊", "starter", level=100
    )
    long_values["pokemon"].append(long_buddy)
    long_values["active"] = long_buddy["id"]
    long_buddy["level"] = 100
    long_buddy["xp"] = engine.xp_for_level(engine.LEVEL_CAP)
    long_values["trainer"]["streak"] = 9_999
    long_values["pokemon"].extend([
        engine.new_pokemon(
            f"Fixture-{index}", "Normal", "", "common", level=1
        )
        for index in range(11)
    ])

    fixtures = (
        ("no_buddy", "NO STARTER", _menu_panel_fixture_status(empty, recent=[])),
        ("ready", "READY / NO RECENT SIGNAL", _menu_panel_fixture_status(ready, recent=[])),
        ("recent", "RECENT CATCH", _menu_panel_fixture_status(recent)),
        ("pending", "WAITING ENCOUNTER", _menu_panel_fixture_status(pending, recent=[])),
        ("shiny", "SHINY BUDDY", _menu_panel_fixture_status(shiny, recent=[])),
        ("long_values", "LONG VALUES / LEVEL CAP", _menu_panel_fixture_status(long_values, recent=[])),
        (
            "unavailable",
            "LOCAL STATUS UNAVAILABLE",
            _menu_panel_fixture_status(empty, error="fixture unavailable"),
        ),
    )
    return {
        "schema_version": 1,
        "kind": "menu_panel_harness",
        "fixtures": [
            {"id": fixture_id, "label": label, "status": status}
            for fixture_id, label, status in fixtures
        ],
    }


def menu_panel_harness_json(indent=None):
    return json.dumps(menu_panel_harness(), indent=indent, sort_keys=True)


def _base_view(screen, title, **payload):
    return {
        "schema_version": 1,
        "kind": "app_view",
        "screen": screen,
        "title": title,
        "generated_at": time.time(),
        **payload,
    }


def _recent_pokemon(s, limit=5, include_sprite=False):
    recent = sorted(
        s.get("pokemon", []),
        key=lambda p: p.get("caught_at", 0),
        reverse=True,
    )[:limit]
    return [
        _pokemon_payload(p, s.get("active"), include_sprite=include_sprite)
        for p in recent
    ]


def _trainer_view(s):
    return _base_view(
        "trainer",
        "Trainer Card",
        **trainer_card.build(s),
    )


def _encounter_view(s):
    return _base_view("encounter", "Wild Encounter", encounter=_pending_view_payload(s))


def _tokens_view(_s):
    try:
        dashboard = token_usage.dashboard()
        report = token_usage.report_lines()
        error = None
    except Exception as exc:
        dashboard = {
            "today": {"tokens": 0, "compact": "0"},
            "total": {"tokens": 0, "compact": "0"},
            "daily": [],
            "clients": [],
            "comparison": [],
            "trend": {
                "direction": "flat",
                "value": "0%",
                "detail": "vs prior 7 days",
            },
            "insights": [],
        }
        report = []
        error = str(exc)
    today = dashboard["today"]
    total = dashboard["total"]
    trend = dashboard["trend"]
    return _base_view(
        "tokens",
        "Token Usage",
        summary=[
            {
                "id": "today",
                "label": "Today",
                "tokens": today["tokens"],
                "compact": today["compact"],
                "detail": f"{today['tokens']:,} tokens",
            },
            {
                "id": "last_7_days",
                "label": "Last 7 days",
                "tokens": total["tokens"],
                "compact": total["compact"],
                "detail": f"{total['tokens']:,} tokens",
            },
            {
                "id": "trend",
                "label": "7-day trend",
                "compact": trend["value"],
                "detail": trend["detail"],
                "tone": trend["direction"],
            },
        ],
        dashboard=dashboard,
        report_lines=report,
        error=error,
        terminal_fallback_screen="tokens",
    )


def _setting_display_value(key, value):
    return SETTING_VALUE_LABELS.get(key, {}).get(value, value)


def _settings_view(s):
    prefs = state.preferences(s)
    rows = []
    values = {"mode": s.get("mode", state.DEFAULT_MODE), **prefs}
    allowed = {"mode": state.VALID_MODES, **state.PREFERENCE_VALUES}
    for key in (
        "mode",
        "notifications",
        "menu_launcher",
        "menu_replace",
        "terminal_graphics",
        "share_reveal",
        "share_banner",
    ):
        value = values[key]
        rows.append({
            "group": SETTING_GROUPS[key],
            "key": key,
            "label": SETTING_LABELS[key],
            "value": value,
            "display_value": _setting_display_value(key, value),
            "allowed_values": list(allowed[key]),
            "allowed_display_values": [
                _setting_display_value(key, option)
                for option in allowed[key]
            ],
            "help": SETTING_HELP[key],
            "writable": True,
        })
    return _base_view(
        "settings",
        "Settings",
        rows=rows,
        terminal_fallback_screen="settings",
    )


APP_VIEW_HANDLERS = {
    "trainer": _trainer_view,
    "encounter": _encounter_view,
    "tokens": _tokens_view,
    "settings": _settings_view,
}


def normalize_screen(screen):
    value = (screen or "").strip().lower()
    return SCREEN_ALIASES.get(value, value)


def app_view(screen):
    screen = normalize_screen(screen)
    handler = APP_VIEW_HANDLERS.get(screen)
    if handler is None:
        raise ValueError("unknown app view: " + screen)
    return handler(state.load())


def status_json(indent=None):
    return json.dumps(app_status(), indent=indent, sort_keys=True)


def app_view_json(screen, indent=None):
    return json.dumps(app_view(screen), indent=indent, sort_keys=True)


def _action_response(action, ok=True, message="", screen=None, **extra):
    payload = {
        "schema_version": 1,
        "kind": "app_action",
        "action": action,
        "ok": bool(ok),
        "message": message,
        "generated_at": time.time(),
        **extra,
    }
    if screen:
        try:
            payload["view"] = app_view(screen)
        except Exception as exc:
            payload["view_error"] = str(exc)
    return payload


def _action_error(action, message, screen=None):
    return _action_response(action, ok=False, message=message, screen=screen)


def _app_action_encounter(args):
    requested = args[0] if args else ""
    result_context = None
    with state.lock():
        s = state.load()
        if s.get("pending_battle"):
            mode = "battle"
            pending = s["pending_battle"]
            if requested == "fight":
                requested = "attack"
            outcome, message = battle_mode.take_turn(s, requested, random.Random())
        elif s.get("pending_encounter"):
            mode = "safari"
            pending = s["pending_encounter"]
            outcome, message = safari.take_turn(s, requested, random.Random())
        else:
            return _action_error("encounter", "No wild Pokemon is waiting.", screen="encounter")
        if outcome is None:
            return _action_error("encounter", message, screen="encounter")
        if outcome.get("done"):
            result_context = (dict(state.active_pokemon(s) or {}), dict(pending), mode, dict(outcome), message)
        state.save(s)
    if result_context:
        buddy, wild, mode, outcome, message = result_context
        return _action_response(
            "encounter",
            ok=True,
            message=message,
            screen=None,
            outcome=outcome,
            encounter_result=_encounter_result_payload(buddy, wild, mode, outcome, message),
        )
    return _action_response(
        "encounter",
        ok=True,
        message=message,
        screen="encounter",
        outcome=outcome,
    )


def _next_value(values, current):
    values = tuple(values)
    if current not in values:
        return values[0]
    return values[(values.index(current) + 1) % len(values)]


def _app_action_preference(args):
    key = args[0] if args else ""
    requested = args[1] if len(args) > 1 else None
    allowed = {"mode": state.VALID_MODES, **state.PREFERENCE_VALUES}
    if key not in allowed:
        return _action_error("preference", "Unknown preference.", screen="settings")
    with state.lock():
        s = state.load()
        prefs = state.preferences(s)
        current = s.get("mode", state.DEFAULT_MODE) if key == "mode" else prefs.get(key)
        target = requested if requested is not None else _next_value(allowed[key], current)
        if target not in allowed[key]:
            return _action_error("preference", "Invalid preference value.", screen="settings")
        if key == "mode":
            s["mode"] = target
        else:
            prefs[key] = target
        state.save(s)
    return _action_response(
        "preference",
        ok=True,
        message=f"{SETTING_LABELS[key]} set to {_setting_display_value(key, target)}.",
        screen="settings",
        key=key,
        value=target,
    )


APP_ACTION_HANDLERS = {
    "encounter": _app_action_encounter,
    "preference": _app_action_preference,
}


def app_action(action, args=None):
    action = (action or "").strip().lower()
    handler = APP_ACTION_HANDLERS.get(action)
    if handler is None:
        return _action_error(action or "unknown", "Unknown app action.")
    try:
        return handler(list(args or []))
    except Exception as exc:
        return _action_error(action, str(exc))


def app_action_json(action, args=None, indent=None):
    return json.dumps(app_action(action, args), indent=indent, sort_keys=True)


def install_assets(kinds=None, operation=assets.INSTALL_MISSING):
    return assets.install(operation=operation, kinds=kinds)
