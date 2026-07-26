from lib import state, tui
from lib import tui_runtime as runtime
from lib import tui_settings as settings_ui
from tests.tui_test_support import (
    ANSI_RE,
    _record_background_update,
    _use_temp_state,
    fresh,
    visible_width,
)


def test_settings_frame_lists_expanded_preferences_and_support(monkeypatch):
    s = state.default_state()
    s["mode"] = "battle"
    s["preferences"]["notifications"] = "silent"
    s["preferences"]["menu_launcher"] = "iterm"
    s["preferences"]["terminal_graphics"] = "off"
    s["preferences"]["menu_replace"] = "off"
    s["preferences"]["share_reveal"] = "off"
    s["preferences"]["share_banner"] = "off"
    monkeypatch.setenv("BUDDYMON_NO_GRAPHICS", "1")

    frame = settings_ui._settings_frame(s, selected=0, width=80)
    plain = ANSI_RE.sub("", frame)

    assert "Gameplay" in plain
    assert "Encounter mode" in plain and "Battle" in plain
    assert "every wild: fight · ball · run" in plain
    assert "Notifications" in plain and "Silent" in plain
    assert "Menu launcher" in plain and "iTerm2" in plain
    assert "Replace menus" in plain and "Off" in plain
    assert "Terminal graphics" in plain and "Off" in plain
    assert "Terminal support" in plain and "off by env" in plain
    assert "Sharing" in plain
    assert "Reveal shares" in plain and "Share banners" in plain
    assert "Your data" in plain
    assert "Back up my data" in plain and "copy state, journal, and art" in plain
    assert "read-only" in plain
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_settings_selection_skips_read_only_rows():
    rows = [
        {"writable": True},
        {"writable": False},
        {"writable": True},
    ]

    assert settings_ui._settings_select(rows, 0, 1) == 2
    assert settings_ui._settings_select(rows, 2, 1) == 0
    assert settings_ui._settings_select(rows, 1) == 0


def test_settings_cycle_keeps_mode_canonical_and_preferences_separate():
    s = state.default_state()

    settings_ui._settings_cycle(s, "mode")
    assert s["mode"] == "safari"
    settings_ui._settings_cycle(s, "mode")
    assert s["mode"] == "battle"
    settings_ui._settings_cycle(s, "mode")
    assert s["mode"] == "auto"
    assert "mode" not in s["preferences"]

    settings_ui._settings_cycle(s, "notifications")
    settings_ui._settings_cycle(s, "menu_launcher")
    settings_ui._settings_cycle(s, "terminal_graphics")
    settings_ui._settings_cycle(s, "menu_replace")
    settings_ui._settings_cycle(s, "share_reveal")
    settings_ui._settings_cycle(s, "share_banner")

    assert s["preferences"]["notifications"] == "silent"
    assert s["preferences"]["menu_launcher"] == "ghostty"
    assert s["preferences"]["terminal_graphics"] == "off"
    assert s["preferences"]["menu_replace"] == "off"
    assert s["preferences"]["share_reveal"] == "off"
    assert s["preferences"]["share_banner"] == "off"


def test_settings_screen_preserves_state_written_while_waiting(
        tmp_path, monkeypatch):
    _use_temp_state(monkeypatch, tmp_path, fresh())
    expected = {}

    def read_key():
        if not expected:
            expected["state"] = _record_background_update()
            return "space"
        return "esc"

    monkeypatch.setattr(runtime, "draw_frame", lambda _frame: None)
    monkeypatch.setattr(runtime, "read_key", read_key)
    monkeypatch.setattr(settings_ui.kgp, "supported", lambda: False)

    tui._settings_screen()

    expected["state"]["mode"] = "safari"
    assert state.load() == expected["state"]


def test_settings_explains_each_encounter_mode():
    expected = {
        "auto": ("Quick", "common quick · rare Safari"),
        "safari": ("Safari", "every wild: rock · bait · ball"),
        "battle": ("Battle", "every wild: fight · ball · run"),
    }
    s = state.default_state()

    for mode, (label, help_text) in expected.items():
        s["mode"] = mode
        row = settings_ui._settings_rows(s)[0]
        assert settings_ui._settings_display_value(row) == label
        assert row["help"] == help_text


def test_graphics_enabled_honors_terminal_graphics_preference(monkeypatch):
    s = state.default_state()
    monkeypatch.setattr(settings_ui.kgp, "supported", lambda: True)

    assert settings_ui._graphics_enabled(s)

    s["preferences"]["terminal_graphics"] = "off"

    assert not settings_ui._graphics_enabled(s)
