"""Read-only native view builders."""

import time

from . import state, token_usage, trainer_card
from .app_payloads import _build_encounter_view_payload


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
    "mode": {"auto": "Quick", "safari": "Safari", "battle": "Battle"},
    "notifications": {"on": "On", "silent": "Silent", "off": "Off"},
    "menu_launcher": {
        "auto": "Auto",
        "ghostty": "Ghostty",
        "iterm": "iTerm2",
        "terminal": "Terminal.app",
    },
    "terminal_graphics": {"auto": "Auto", "off": "Off"},
    "menu_replace": {"on": "On", "off": "Off"},
    "share_reveal": {"on": "On", "off": "Off"},
    "share_banner": {"on": "On", "off": "Off"},
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


def _build_view_payload(screen, title, **payload):
    return {
        "schema_version": 1,
        "kind": "app_view",
        "screen": screen,
        "title": title,
        "generated_at": time.time(),
        **payload,
    }


def _build_trainer_view(s):
    return _build_view_payload(
        "trainer",
        "Trainer Card",
        **trainer_card.build(s),
    )


def _build_encounter_view(s):
    return _build_view_payload(
        "encounter",
        "Wild Encounter",
        encounter=_build_encounter_view_payload(s),
    )


def _build_token_usage_view(_s):
    try:
        dashboard = token_usage.dashboard()
        report = token_usage.report_lines()
        error = None
    except Exception as exc:
        dashboard = {
            "today": {"tokens": 0, "compact": "0"},
            "headline": [
                {
                    "id": "day",
                    "label": "Today",
                    "tokens": 0,
                    "compact": "0",
                    "comparison_label": "Yesterday",
                    "comparison_tokens": 0,
                    "comparison_compact": "0",
                    "change": "0%",
                    "tone": "flat",
                },
                {
                    "id": "week",
                    "label": "This week",
                    "tokens": 0,
                    "compact": "0",
                    "comparison_label": "Last week",
                    "comparison_tokens": 0,
                    "comparison_compact": "0",
                    "change": "0%",
                    "tone": "flat",
                },
            ],
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
    return _build_view_payload(
        "tokens",
        "Token Usage",
        summary=dashboard["headline"],
        dashboard=dashboard,
        report_lines=report,
        error=error,
        terminal_fallback_screen="tokens",
    )


def _setting_display_value(key, value):
    return SETTING_VALUE_LABELS.get(key, {}).get(value, value)


def _build_settings_view(s):
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
    return _build_view_payload(
        "settings",
        "Settings",
        rows=rows,
        terminal_fallback_screen="settings",
    )


APP_VIEW_BUILDERS = {
    "trainer": _build_trainer_view,
    "encounter": _build_encounter_view,
    "tokens": _build_token_usage_view,
    "settings": _build_settings_view,
}


def normalize_screen(screen):
    value = (screen or "").strip().lower()
    return SCREEN_ALIASES.get(value, value)


def app_view(screen):
    screen = normalize_screen(screen)
    builder = APP_VIEW_BUILDERS.get(screen)
    if builder is None:
        raise ValueError("unknown app view: " + screen)
    return builder(state.load())
