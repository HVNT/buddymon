import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import (
    app_bridge,
    assets,
    engine,
    packs,
    paths,
    safari,
    state,
    token_usage,
)


def use_temp_state(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setattr(paths, "STATE_DIR", state_dir)
    monkeypatch.setattr(paths, "STATE_FILE", state_dir / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", state_dir / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", state_dir / "journal.jsonl")
    packs._cache.clear()
    return state_dir


def test_app_status_reports_missing_buddy_and_pack_paths(tmp_path, monkeypatch):
    state_dir = use_temp_state(monkeypatch, tmp_path)

    status = app_bridge.app_status()

    assert status["schema_version"] == 1
    assert status["state_dir"] == str(state_dir)
    assert status["has_buddy"] is False
    assert status["active"] is None
    assert status["menu_bar_icon_base64"] is None
    assert status["menu_bar"]["baseline"]["state_id"] == "needs_buddy"
    assert status["packs"]["gen2"]["installed"] is False
    assert status["setup"]["needs_starter"] is True
    assert status["setup"]["needs_assets"] is True
    assert status["setup"]["assets_optional"] is True
    assert status["setup"]["ready"] is False
    assert status["setup"]["asset_kinds"] == [
        "gen2",
        "box",
        "gen5",
        "trainer",
    ]
    assert status["sources"]["native_desktop_apps"]["kind"] == "unsupported_v1"


def test_status_json_reports_recovery_without_overwriting_corrupt_state(
    tmp_path, monkeypatch
):
    use_temp_state(monkeypatch, tmp_path)
    original = b'{"version": 4, "pokemon": ['
    paths.STATE_DIR.mkdir(parents=True)
    paths.STATE_FILE.write_bytes(original)

    status = json.loads(app_bridge.status_json())

    assert status["recovery_required"] is True
    assert status["recovery_code"] == "invalid_state"
    assert status["recovery_summary"].startswith("File untouched.")
    assert "left untouched" in status["error"]
    assert status["native_menu"]["items"] == []
    assert paths.STATE_FILE.read_bytes() == original


def test_preference_action_refuses_to_overwrite_corrupt_state(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)
    original = b'{"version": 4, "pokemon": ['
    paths.STATE_DIR.mkdir(parents=True)
    paths.STATE_FILE.write_bytes(original)

    result = app_bridge.app_action("preference", ["notifications", "off"])

    assert result["ok"] is False
    assert "left untouched" in result["message"]
    assert paths.STATE_FILE.read_bytes() == original


def test_app_status_reports_active_buddy_and_icon(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)
    monkeypatch.setattr(
        token_usage,
        "current_day_totals",
        lambda: {"today": 148_200, "yesterday": 102_400},
    )
    s = state.default_state()
    engine.create_starter(s, "Pikachu")
    state.save(s)

    status = app_bridge.app_status()

    assert status["has_buddy"] is True
    assert status["active"]["name"] == "Pikachu"
    assert status["active"]["level_progress"]["percent"] >= 0
    assert status["active"]["level_progress"]["needed"] >= 0
    assert base64.b64decode(status["active"]["sprite_base64"]).startswith(b"\x89PNG")
    assert status["recent"][0]["name"] == "Pikachu"
    assert status["trainer"]["caught_count"] == 1
    assert status["alert"] is False
    assert status["setup"]["needs_starter"] is False
    assert status["setup"]["needs_assets"] is True
    assert status["setup"]["assets_optional"] is True
    assert status["setup"]["ready"] is True
    assert base64.b64decode(status["menu_bar_icon_base64"]).startswith(b"\x89PNG")
    assert base64.b64decode(status["brand_mark_base64"]).startswith(b"\x89PNG")
    assert status["tokens"]["today"]["compact"] == "148K"
    assert status["tokens"]["yesterday"]["compact"] == "102K"
    assert status["menu_bar"]["baseline"]["state_id"] in {
        "idle",
        "working",
        "resting",
    }


def test_app_status_reports_pending_alert(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    s["pending_encounter"] = safari.start({
        "name": "Haxorus",
        "type": "Dragon",
        "emoji": "🐉",
        "rarity": "rare",
        "shiny": False,
    })
    state.save(s)

    status = app_bridge.app_status()

    assert status["alert"] is True
    assert status["menu_bar"]["persistent"]["state_id"] == "waiting_for_player"
    pending = status["pending"]
    assert {key: pending[key] for key in ["name", "type", "shiny", "mode"]} == {
        "name": "Haxorus",
        "type": "Dragon",
        "shiny": False,
        "mode": "safari",
    }
    if pending.get("sprite_base64"):
        assert base64.b64decode(pending["sprite_base64"]).startswith(b"\x89PNG")


def test_status_json_is_valid_json(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)

    payload = json.loads(app_bridge.status_json(indent=2))

    assert payload["schema_version"] == 1


def test_native_menu_policy_is_compact_and_state_driven(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)
    s = state.default_state()
    engine.create_starter(s, "Pikachu")
    state.save(s)

    menu = app_bridge.app_status()["native_menu"]
    assert menu["layout"] == "compact"
    assert [item["id"] for item in menu["items"]] == [
        "trainer",
        "terminal_party",
        "terminal_box",
        "terminal_dex",
        "terminal_activity",
        "settings",
    ]
    assert [item.get("terminal_screen") for item in menu["items"]] == [
        None,
        "party",
        "box",
        "dex",
        "journal",
        None,
    ]
    assert menu["items"][0] == {
        "id": "trainer",
        "label": "Trainer",
        "shortcut": "t",
        "presentation": "utility",
    }
    assert menu["items"][-1] == {
        "id": "settings",
        "label": "Settings",
        "shortcut": "s",
        "presentation": "utility",
    }
    assert menu["token_action"] == {
        "id": "tokens",
        "label": "Open token detail",
        "shortcut": "u",
    }
    assert [item["id"] for item in menu["footer_items"]] == ["refresh", "quit"]
    assert all(item["modifiers"] == ["command"] for item in menu["footer_items"])
    assert all("children" not in item for item in menu["items"])

    s["pending_encounter"] = safari.start({
        "name": "Eevee",
        "type": "Normal",
        "emoji": "🦊",
        "rarity": "rare",
        "shiny": False,
    })
    state.save(s)
    pending_menu = app_bridge.app_status()["native_menu"]
    assert [item["id"] for item in pending_menu["items"]] == [
        "encounter",
        "trainer",
        "terminal_party",
        "terminal_box",
        "terminal_dex",
        "terminal_activity",
        "settings",
    ]
    assert pending_menu["items"][0] == {
        "id": "encounter",
        "label": "Wild Eevee is waiting",
        "shortcut": "e",
        "emphasis": "primary",
        "image_base64": pending_menu["items"][0]["image_base64"],
    }
    assert base64.b64decode(pending_menu["items"][0]["image_base64"]).startswith(b"\x89PNG")
    assert pending_menu["footer_items"][0] == {
        "id": "refresh",
        "label": "Refresh",
        "shortcut": "r",
        "modifiers": ["command"],
    }


def test_compact_menu_harness_covers_all_review_states_without_expansion():
    payload = app_bridge.menu_panel_harness()

    assert payload["schema_version"] == 1
    assert payload["kind"] == "menu_panel_harness"
    assert [fixture["id"] for fixture in payload["fixtures"]] == [
        "no_buddy",
        "ready",
        "recent",
        "pending",
        "shiny",
        "long_values",
        "unavailable",
        "recovery_required",
    ]
    for fixture in payload["fixtures"]:
        items = fixture["status"].get("native_menu", {}).get("items", [])
        assert "open_details" not in {item["id"] for item in items}

    pending = next(
        fixture for fixture in payload["fixtures"] if fixture["id"] == "pending"
    )
    assert pending["status"]["native_menu"]["items"][0]["id"] == "encounter"
    assert json.loads(app_bridge.menu_panel_harness_json())["kind"] == (
        "menu_panel_harness"
    )


def test_app_view_trainer_has_compact_card_contract(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)
    monkeypatch.setattr(
        assets,
        "trainer_portrait_base64",
        lambda: "local-trainer-red",
    )
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    s["trainer"]["total_tokens"] = 123456
    state.save(s)

    view = app_bridge.app_view("trainer")

    assert view["schema_version"] == 1
    assert view["kind"] == "app_view"
    assert view["screen"] == "trainer"
    assert view["title"] == "Trainer Card"
    assert view["portrait_base64"] == "local-trainer-red"
    assert [fact["id"] for fact in view["facts"]] == [
        "name",
        "tokens",
        "pokedex",
        "caught",
    ]
    assert view["facts"][1]["value"] == "123.5K"
    assert [stat["id"] for stat in view["trainer_stats"]] == [
        "mode",
        "streak",
        "balls",
        "shiny",
    ]
    assert [stat["value"] for stat in view["trainer_stats"]] == [
        "QUICK",
        "0D",
        "10",
        "0",
    ]
    assert [badge["id"] for badge in view["badges"]] == [
        "bond",
        "safari",
        "battle",
        "curator",
        "types",
        "shiny",
        "legend",
        "national",
        "shiny_legend",
    ]
    assert "shiny_national" not in {badge["id"] for badge in view["badges"]}
    assert "level" not in view


def test_app_view_encounter_reports_safari_actions(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)
    s = state.default_state()
    engine.create_starter(s, "Squirtle")
    s["pending_encounter"] = {
        "name": "Mewtwo",
        "type": "Psychic",
        "emoji": "🔮",
        "rarity": "legendary",
        "shiny": True,
        "level": 55,
        "c": 45,
        "base_c": 45,
        "angry": 0,
        "eating": 0,
        "balls_thrown": 0,
        "moves": 0,
        "last_msg": "A wild Mewtwo appeared!",
    }
    state.save(s)

    view = app_bridge.app_view("encounter")
    encounter = view["encounter"]

    assert encounter["mode"] == "safari"
    assert encounter["state"] == "waiting"
    assert encounter["mode_emoji"] == "🌿"
    assert encounter["wild"]["name"] == "Mewtwo"
    assert encounter["wild"]["wild_level"] == 55
    assert [action["id"] for action in encounter["actions"]] == ["rock", "bait", "ball", "run"]
    assert [action["emoji"] for action in encounter["actions"]] == ["🪨", "🍖", "⚾", "💨"]
    assert [action["compact_label"] for action in encounter["actions"]] == [
        "Rock",
        "Bait",
        "Catch",
        "Run",
    ]
    assert [action["shortcut"] for action in encounter["actions"]] == [
        "k",
        "b",
        "c",
        "r",
    ]
    assert base64.b64decode(encounter["scene_base64"]).startswith(b"\x89PNG")
    assert "catch" in encounter["odds"]["hint"]


def test_removed_native_app_views_are_rejected(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)

    for screen in ["home", "party", "box", "dex", "pokedex", "showcase", "journal"]:
        try:
            app_bridge.app_view(screen)
        except ValueError as exc:
            assert str(exc) == f"unknown app view: {screen}"
        else:
            raise AssertionError(f"removed native app view still reachable: {screen}")


def test_app_view_settings_and_tokens(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)
    state.save(state.default_state())
    monkeypatch.setattr(
        token_usage,
        "dashboard",
        lambda: {
            "today": {"tokens": 100, "compact": "100"},
            "headline": [
                {
                    "id": "day",
                    "label": "Today",
                    "tokens": 100,
                    "compact": "100",
                    "comparison_label": "Yesterday",
                    "comparison_tokens": 80,
                    "comparison_compact": "80",
                    "change": "+25%",
                    "tone": "up",
                },
                {
                    "id": "week",
                    "label": "This week",
                    "tokens": 300,
                    "compact": "300",
                    "comparison_label": "Last week",
                    "comparison_tokens": 200,
                    "comparison_compact": "200",
                    "change": "+50%",
                    "tone": "up",
                },
            ],
            "total": {"tokens": 450, "compact": "450"},
            "daily": [{"label": "Mon", "tokens": 100}],
            "clients": [{"label": "Codex", "tokens": 450, "percent": 100}],
            "comparison": [
                {"label": "Last 7 days", "tokens": 450, "compact": "450"},
                {"label": "Prior 7 days", "tokens": 300, "compact": "300"},
            ],
            "trend": {
                "direction": "up",
                "value": "+50%",
                "detail": "vs prior 7 days",
            },
            "insights": [{"label": "Busiest day", "value": "Today", "detail": "100 tokens"}],
        },
    )
    monkeypatch.setattr(
        token_usage,
        "report_lines",
        lambda: ["Token Usage", "Today 100"],
    )

    settings = app_bridge.app_view("settings")
    tokens = app_bridge.app_view("tokens")

    assert settings["rows"][0]["key"] == "mode"
    assert settings["rows"][0]["display_value"] == "Quick"
    assert [row["key"] for row in settings["rows"]] == [
        "mode",
        "notifications",
        "menu_launcher",
        "menu_replace",
        "terminal_graphics",
        "share_reveal",
        "share_banner",
    ]
    assert [row["group"] for row in settings["rows"]] == [
        "Gameplay",
        "Notifications",
        "Display",
        "Display",
        "Display",
        "Sharing",
        "Sharing",
    ]
    assert tokens["summary"][0]["comparison_label"] == "Yesterday"
    assert tokens["summary"][0]["change"] == "+25%"
    assert tokens["summary"][1]["comparison_label"] == "Last week"
    assert tokens["summary"][1]["change"] == "+50%"
    assert tokens["dashboard"]["daily"][0]["label"] == "Mon"
    assert tokens["report_lines"] == ["Token Usage", "Today 100"]


def test_app_view_json_and_cli_aliases(tmp_path, monkeypatch):
    import buddymon

    use_temp_state(monkeypatch, tmp_path)
    payload = json.loads(app_bridge.app_view_json("token-usage"))

    assert payload["screen"] == "tokens"
    assert buddymon.app_view([]) == "Usage: app-view <screen>"
    assert buddymon.app_view(["not-a-screen"]) == "unknown app view: not-a-screen"


def test_removed_native_app_actions_are_rejected_without_mutating_state(
    tmp_path,
    monkeypatch,
):
    use_temp_state(monkeypatch, tmp_path)
    s = state.default_state()
    engine.create_starter(s, "Pikachu")
    staryu = engine.new_pokemon("Staryu", "Water", "⭐", "uncommon", level=3)
    s["pokemon"].append(staryu)
    state.save(s)
    before = state.load()

    for action in [
        "switch-id",
        "favorite",
        "showcase-set",
        "showcase-clear",
        "showcase-share",
    ]:
        result = app_bridge.app_action(action, [str(staryu["id"])])
        assert result["ok"] is False
        assert result["message"] == "Unknown app action."

    assert state.load() == before


def test_handle_preference_action_sets_exact_value_and_cycles(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)
    state.save(state.default_state())

    exact = app_bridge.app_action("preference", ["menu_launcher", "iterm"])
    assert exact["ok"] is True
    assert exact["value"] == "iterm"
    assert state.load()["preferences"]["menu_launcher"] == "iterm"

    cycled = app_bridge.app_action("preference", ["menu_launcher"])
    bad = app_bridge.app_action("preference", ["menu_launcher", "warp"])

    assert cycled["ok"] is True
    assert cycled["value"] == "terminal"
    assert state.load()["preferences"]["menu_launcher"] == "terminal"
    assert bad["ok"] is False


def test_handle_encounter_action_resolves_run(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)
    s = state.default_state()
    engine.create_starter(s, "Squirtle")
    s["pending_encounter"] = {
        "name": "Mewtwo",
        "type": "Psychic",
        "emoji": "🔮",
        "rarity": "legendary",
        "shiny": False,
        "level": 55,
        "c": 45,
        "base_c": 45,
        "angry": 0,
        "eating": 0,
        "balls_thrown": 0,
        "moves": 0,
        "last_msg": "A wild Mewtwo appeared!",
    }
    state.save(s)

    result = app_bridge.app_action("encounter", ["run"])

    assert result["ok"] is True
    assert result["outcome"]["done"] is True
    assert state.load().get("pending_encounter") is None
    assert "view" not in result
    assert result["encounter_result"]["outcome"] == "ran"
    assert result["encounter_result"]["outcome_emoji"] == "💨"
    assert result["encounter_result"]["wild"]["name"] == "Mewtwo"
    assert base64.b64decode(result["encounter_result"]["scene_base64"]).startswith(b"\x89PNG")


def test_app_action_json_and_cli_errors(tmp_path, monkeypatch):
    import buddymon

    use_temp_state(monkeypatch, tmp_path)
    payload = json.loads(app_bridge.app_action_json("missing", []))
    cli_payload = json.loads(buddymon.app_action(["missing"]))

    assert payload["ok"] is False
    assert payload["kind"] == "app_action"
    assert cli_payload["message"] == "Unknown app action."
