"""Deterministic payloads for compact-panel visual verification."""

from . import engine, menu_panel, state
from .app_payloads import (
    _build_active_pokemon_payload,
    _build_pending_encounter_payload,
    _build_recent_pokemon_payloads,
    _render_brand_mark_base64,
)


def _build_menu_panel_fixture_status(s, *, recent=None, error=None):
    """Build deterministic compact-panel input without touching player state."""
    if error:
        return {"schema_version": 1, "error": error}
    trainer = s.get("trainer", {})
    pending = _build_pending_encounter_payload(s)
    return {
        "schema_version": 1,
        "has_buddy": bool(s.get("pokemon")),
        "active": _build_active_pokemon_payload(s),
        "pending": pending,
        "trainer": {
            "streak": trainer.get("streak", 0),
            "balls": trainer.get("balls", 0),
            "caught_count": len(s.get("pokemon", [])),
            "species_count": len({p.get("name") for p in s.get("pokemon", [])}),
        },
        "recent": (
            _build_recent_pokemon_payloads(s, limit=1, include_sprite=True)
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
        "brand_mark_base64": _render_brand_mark_base64(),
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
        ("no_buddy", "NO STARTER", _build_menu_panel_fixture_status(empty, recent=[])),
        ("ready", "READY / NO RECENT SIGNAL", _build_menu_panel_fixture_status(ready, recent=[])),
        ("recent", "RECENT CATCH", _build_menu_panel_fixture_status(recent)),
        ("pending", "WAITING ENCOUNTER", _build_menu_panel_fixture_status(pending, recent=[])),
        ("shiny", "SHINY BUDDY", _build_menu_panel_fixture_status(shiny, recent=[])),
        ("long_values", "LONG VALUES / LEVEL CAP", _build_menu_panel_fixture_status(long_values, recent=[])),
        (
            "unavailable",
            "LOCAL STATUS UNAVAILABLE",
            _build_menu_panel_fixture_status(empty, error="fixture unavailable"),
        ),
        (
            "recovery_required",
            "STATE RECOVERY REQUIRED",
            {
                "schema_version": 1,
                "error": (
                    "BuddyMon could not safely read state.json. "
                    "Your data was left untouched."
                ),
                "recovery_required": True,
                "recovery_summary": "File untouched. Restore or update BuddyMon.",
                "native_menu": {"items": [], "footer_items": []},
            },
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
