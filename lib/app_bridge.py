"""Stable JSON facade for the native BuddyMon app.

The human-facing CLI and SwiftBar output are intentionally separate. This
module keeps the native app's supported commands and JSON contracts in one
small boundary while focused modules own payloads, views, actions, and visual
fixtures.
"""

import json

from . import assets, state
from .app_actions import APP_ACTION_HANDLERS, app_action
from .app_fixtures import menu_panel_harness
from .app_payloads import (
    ENCOUNTER_ACTIONS,
    ENCOUNTER_COMPACT_ACTIONS,
    ENCOUNTER_MODE_EMOJI,
    ENCOUNTER_OUTCOME_EMOJI,
    app_status,
    source_status,
)
from .app_views import (
    APP_VIEW_BUILDERS,
    SCREEN_ALIASES,
    SETTING_GROUPS,
    SETTING_HELP,
    SETTING_LABELS,
    SETTING_VALUE_LABELS,
    app_view,
    normalize_screen,
)


__all__ = (
    "APP_ACTION_HANDLERS",
    "APP_VIEW_BUILDERS",
    "ENCOUNTER_ACTIONS",
    "ENCOUNTER_COMPACT_ACTIONS",
    "ENCOUNTER_MODE_EMOJI",
    "ENCOUNTER_OUTCOME_EMOJI",
    "SCREEN_ALIASES",
    "SETTING_GROUPS",
    "SETTING_HELP",
    "SETTING_LABELS",
    "SETTING_VALUE_LABELS",
    "app_action",
    "app_action_json",
    "app_status",
    "app_view",
    "app_view_json",
    "install_assets",
    "menu_panel_harness",
    "menu_panel_harness_json",
    "normalize_screen",
    "source_status",
    "status_json",
)


def status_json(indent=None):
    try:
        payload = app_status()
    except state.StateLoadError as exc:
        payload = {
            "schema_version": 1,
            "error": str(exc),
            "recovery_required": True,
            "recovery_code": exc.code,
            "recovery_summary": "File untouched. Restore or update BuddyMon.",
            "state_file_exists": True,
            "active": None,
            "pending": None,
            "alert": True,
            "native_menu": {
                "items": [],
                "footer_items": [],
            },
        }
    return json.dumps(payload, indent=indent, sort_keys=True)


def menu_panel_harness_json(indent=None):
    return json.dumps(menu_panel_harness(), indent=indent, sort_keys=True)


def app_view_json(screen, indent=None):
    return json.dumps(app_view(screen), indent=indent, sort_keys=True)


def app_action_json(action, args=None, indent=None):
    return json.dumps(app_action(action, args), indent=indent, sort_keys=True)


def install_assets(kinds=None, operation=assets.INSTALL_MISSING):
    return assets.install(operation=operation, kinds=kinds)
