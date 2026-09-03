"""Settings rows, selection, and pure frame rendering for the TUI."""

import os

from . import kgp
from . import state as st
from . import tui_runtime as runtime
from .tui_layout import BOLD, DIM, GREEN, RESET, _fit_ansi, _footer, _header


SETTINGS_CYCLES = {
    "mode": st.VALID_MODES,
    "notifications": st.PREFERENCE_VALUES["notifications"],
    "menu_launcher": st.PREFERENCE_VALUES["menu_launcher"],
    "terminal_graphics": st.PREFERENCE_VALUES["terminal_graphics"],
    "menu_replace": st.PREFERENCE_VALUES["menu_replace"],
    "share_reveal": st.PREFERENCE_VALUES["share_reveal"],
    "share_banner": st.PREFERENCE_VALUES["share_banner"],
}
SETTINGS_LABEL = {
    "mode": "Encounter mode",
    "notifications": "Notifications",
    "menu_launcher": "Menu launcher",
    "menu_replace": "Replace menus",
    "share_reveal": "Reveal shares",
    "share_banner": "Share banners",
    "terminal_graphics": "Terminal graphics",
    "terminal_support": "Terminal support",
}
SETTINGS_HELP = {
    "notifications": "rare-event banners",
    "menu_launcher": "menu app preference",
    "menu_replace": "close prior BuddyMon Ghostty menu",
    "share_reveal": "open Finder after export",
    "share_banner": "show share result banner",
    "terminal_graphics": "inline image preference",
    "terminal_support": "current terminal support",
}
ENCOUNTER_MODE_HELP = {
    "auto": "ordinary quick · shiny/legendary/mythic Safari",
    "safari": "every wild: rock · bait · ball",
    "battle": "every wild: fight · ball · run",
}
SETTINGS_VALUE_LABELS = {
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
    "terminal_support": {
        "inline PNGs": "inline PNGs",
        "text fallback": "text fallback",
        "off by env": "off by env",
        "off": "off",
    },
}


def _terminal_graphics_status(s=None):
    if os.environ.get("BUDDYMON_NO_GRAPHICS"):
        return "off by env"
    if s is not None and st.preference(s, "terminal_graphics") == "off":
        return "off"
    return "inline PNGs" if kgp.supported() else "text fallback"


def _graphics_enabled(s):
    return st.preference(s, "terminal_graphics") != "off" and kgp.supported()


def _settings_mode(s):
    mode = s.get("mode", st.DEFAULT_MODE)
    return mode if mode in st.VALID_MODES else st.DEFAULT_MODE


def _settings_rows(s):
    prefs = st.preferences(s)
    return [
        {
            "group": "Gameplay",
            "key": "mode",
            "label": SETTINGS_LABEL["mode"],
            "value": _settings_mode(s),
            "help": ENCOUNTER_MODE_HELP[_settings_mode(s)],
            "writable": True,
        },
        {
            "group": "Notifications",
            "key": "notifications",
            "label": SETTINGS_LABEL["notifications"],
            "value": prefs["notifications"],
            "help": SETTINGS_HELP["notifications"],
            "writable": True,
        },
        {
            "group": "Display",
            "key": "menu_launcher",
            "label": SETTINGS_LABEL["menu_launcher"],
            "value": prefs["menu_launcher"],
            "help": SETTINGS_HELP["menu_launcher"],
            "writable": True,
        },
        {
            "group": "Display",
            "key": "menu_replace",
            "label": SETTINGS_LABEL["menu_replace"],
            "value": prefs["menu_replace"],
            "help": SETTINGS_HELP["menu_replace"],
            "writable": True,
        },
        {
            "group": "Display",
            "key": "terminal_graphics",
            "label": SETTINGS_LABEL["terminal_graphics"],
            "value": prefs["terminal_graphics"],
            "help": SETTINGS_HELP["terminal_graphics"],
            "writable": True,
        },
        {
            "group": "Display",
            "key": "terminal_support",
            "label": SETTINGS_LABEL["terminal_support"],
            "value": _terminal_graphics_status(s),
            "help": SETTINGS_HELP["terminal_support"],
            "writable": False,
        },
        {
            "group": "Sharing",
            "key": "share_reveal",
            "label": SETTINGS_LABEL["share_reveal"],
            "value": prefs["share_reveal"],
            "help": SETTINGS_HELP["share_reveal"],
            "writable": True,
        },
        {
            "group": "Your data",
            "key": "backup",
            "label": "Back up my data",
            "value": "Now",
            "help": "copy state, journal, and art to Documents",
            "writable": True,
            "action": "backup",
        },
        {
            "group": "Sharing",
            "key": "share_banner",
            "label": SETTINGS_LABEL["share_banner"],
            "value": prefs["share_banner"],
            "help": SETTINGS_HELP["share_banner"],
            "writable": True,
        },
    ]


def _settings_selectable_indexes(rows):
    return [i for i, row in enumerate(rows) if row.get("writable")]


def _settings_select(rows, selected, delta=0):
    selectable = _settings_selectable_indexes(rows)
    if not selectable:
        return 0
    if selected not in selectable:
        return selectable[0]
    if not delta:
        return selected
    pos = selectable.index(selected)
    return selectable[(pos + delta) % len(selectable)]


def _settings_cycle(s, key):
    values = SETTINGS_CYCLES.get(key)
    if not values:
        return False
    if key == "mode":
        current = _settings_mode(s)
        s["mode"] = values[(values.index(current) + 1) % len(values)]
        return True
    prefs = st.preferences(s)
    current = prefs.get(key)
    if current not in values:
        current = values[0]
    prefs[key] = values[(values.index(current) + 1) % len(values)]
    return True


def _settings_display_value(row):
    value = str(row["value"])
    return SETTINGS_VALUE_LABELS.get(row["key"], {}).get(value, value)


def _settings_frame(s, selected=0, width=80, notice=None):
    runtime.begin_frame()
    rows = _settings_rows(s)
    selected = _settings_select(rows, selected)
    lines = ["", _header("settings"), ""]
    group = None
    for i, row in enumerate(rows):
        if row["group"] != group:
            group = row["group"]
            lines.append(f"  {DIM}{group}{RESET}")
        cursor = f"{GREEN}▶{RESET}" if i == selected else " "
        value = _settings_display_value(row)
        if i == selected:
            value = f"{BOLD}{value}{RESET}"
        label = f"{row['label']:<18}"
        ro = f" {DIM}read-only{RESET}" if not row["writable"] else ""
        line = f"  {cursor} {label} {value:<14} {DIM}{row['help']}{RESET}{ro}"
        lines.append(_fit_ansi(line, width))
        lines.append("")
    if notice:
        lines.append(_fit_ansi(f"  {GREEN}✓{RESET} {notice}", width))
    hint = "↑/↓ move · ⏎/space change or back up · esc back"
    return "\n".join(lines + [_footer(hint)])
