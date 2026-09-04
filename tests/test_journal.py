"""Journal + notification gating tests."""
import shlex
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import journal


def _isolate(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")


def test_append_tail_roundtrip_and_corrupt_tolerance(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    journal.append("caught", "🎉 caught Pidgey", {"name": "Pidgey"})
    with open(tmp_path / "journal.jsonl", "a") as f:
        f.write("not json\n")
    journal.append("level", "⬆️ Lv.5")
    entries = journal.tail(10)
    assert [e["kind"] for e in entries] == ["caught", "level"]
    assert entries[0]["name"] == "Pidgey"
    newest = journal.tail(10, newest_first=True)
    assert [e["kind"] for e in newest] == ["level", "caught"]


def test_history_command_reads_journal_newest_first(monkeypatch):
    import buddymon

    calls = []

    def fake_tail(n, newest_first=False):
        calls.append((n, newest_first))
        return [
            {"ts": 2, "text": "new event"},
            {"ts": 1, "text": "old event"},
        ]

    monkeypatch.setattr(buddymon.journal, "tail", fake_tail)

    out = buddymon.history(["2"])

    assert calls == [(2, True)]
    assert out.index("new event") < out.index("old event")


def test_log_outcomes_kinds(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    result = {"xp": 50, "old_level": 15, "new_level": 16, "leveled": True,
              "evolved": "Charmeleon", "buddy": "Charmeleon"}
    encounter = {"name": "Mewtwo", "emoji": "🧬", "rarity": "legendary",
                 "shiny": False, "outcome": "fled"}
    written = journal.log_outcomes(result, encounter, "claude")
    assert [e["kind"] for e in written] == ["evolved", "fled"]
    assert "Lv.16" in written[0]["text"]
    assert written[1]["rarity"] == "legendary"

    written = journal.log_outcomes(
        {"xp": 5, "old_level": 3, "new_level": 3, "leveled": False,
         "evolved": None, "buddy": "Pikachu"},
        {"name": "Pidgey", "emoji": "🐦", "rarity": "common", "shiny": True,
         "level": 12, "outcome": "caught", "new_species": True}, "cross")
    assert [e["kind"] for e in written] == ["caught"]
    assert written[0]["shiny"] is True
    assert written[0]["level"] == 12
    assert "Lv.12" in written[0]["text"]


def test_is_rare_truth_table():
    assert journal.is_rare({"kind": "evolved"})
    assert journal.is_rare({"kind": "caught", "shiny": True, "rarity": "common"})
    assert journal.is_rare({"kind": "fled", "shiny": False, "rarity": "legendary"})
    assert journal.is_rare({"kind": "no_balls", "rarity": "legendary"})
    assert not journal.is_rare({"kind": "caught", "shiny": False, "rarity": "common"})
    assert not journal.is_rare({"kind": "level", "level": 30})
    assert not journal.is_rare({"kind": "fled", "rarity": "rare"})


def test_notify_fires_only_for_rare(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from lib import notify
    calls = []
    monkeypatch.setattr(notify, "notify", lambda title, text: calls.append(text))

    entries = journal.log_outcomes(
        {"xp": 9, "old_level": 2, "new_level": 2, "leveled": False,
         "evolved": None, "buddy": "Eevee"},
        {"name": "Articuno", "emoji": "🧊", "rarity": "legendary", "shiny": False,
         "outcome": "caught", "new_species": True}, "claude")
    for e in entries:
        if journal.is_rare(e):
            notify.notify("buddymon", e["text"])
    assert len(calls) == 1 and "Articuno" in calls[0]


def test_notify_off_suppresses_delivery(monkeypatch):
    from lib import notify

    calls = []
    monkeypatch.setattr(notify.shutil, "which", lambda _name: "/usr/local/bin/terminal-notifier")
    monkeypatch.setattr(notify.subprocess, "run", lambda *a, **k: calls.append((a, k)))

    notify.notify("buddymon", "rare catch", notifications="off")

    assert calls == []


def test_notify_silent_keeps_click_action_without_sound(monkeypatch):
    from lib import notify

    calls = []
    monkeypatch.setattr(notify.shutil, "which", lambda _name: "/usr/local/bin/terminal-notifier")
    monkeypatch.setattr(notify.subprocess, "run", lambda args, **_kwargs: calls.append(args))

    notify.notify("buddymon", "rare catch", notifications="silent")

    args = calls[0]
    assert "-execute" in args
    assert "-sound" not in args


def test_notify_on_keeps_glass_sound(monkeypatch):
    from lib import notify

    calls = []
    monkeypatch.setattr(notify.shutil, "which", lambda _name: "/usr/local/bin/terminal-notifier")
    monkeypatch.setattr(notify.subprocess, "run", lambda args, **_kwargs: calls.append(args))

    notify.notify("buddymon", "rare catch", notifications="on")

    assert calls[0][calls[0].index("-sound") + 1] == "Glass"


def test_notify_skips_delivery_without_safe_notifier(monkeypatch):
    from lib import notify

    calls = []
    monkeypatch.setattr(notify.shutil, "which", lambda _name: None)
    monkeypatch.setattr(notify.subprocess, "run", lambda args, **_kwargs: calls.append(args))

    notify.notify("buddymon", "rare catch", notifications="silent")

    assert calls == []


def test_notify_finds_homebrew_notifier_outside_gui_path(monkeypatch):
    from lib import notify

    calls = []

    def find_notifier(candidate):
        if candidate == "/opt/homebrew/bin/terminal-notifier":
            return candidate
        return None

    monkeypatch.setattr(notify.shutil, "which", find_notifier)
    monkeypatch.setattr(notify.subprocess, "run", lambda args, **_kwargs: calls.append(args))

    notify.notify("buddymon", "rare catch", notifications="silent")

    assert calls[0][0] == "/opt/homebrew/bin/terminal-notifier"


def test_banner_uses_safe_notification_without_click_action(monkeypatch):
    from lib import notify

    calls = []
    monkeypatch.setattr(
        notify.shutil,
        "which",
        lambda _name: "/usr/local/bin/terminal-notifier",
    )
    monkeypatch.setattr(notify.subprocess, "run", lambda args, **_kwargs: calls.append(args))

    notify.banner("BuddyMon Showcase", "Saved BuddyMon Showcase.png")

    assert calls[0][0] == "/usr/local/bin/terminal-notifier"
    assert "-execute" not in calls[0]
    assert calls[0][calls[0].index("-title") + 1] == "BuddyMon Showcase"
    assert calls[0][calls[0].index("-message") + 1] == (
        "Saved BuddyMon Showcase.png"
    )


def test_notification_delivery_never_invokes_applescript():
    from lib import notify

    source = Path(notify.__file__).read_text(encoding="utf-8")

    assert "osascript" not in source
    assert "display notification" not in source


def test_open_menu_cmd_runs_stateful_launcher():
    from lib import menu_launcher, notify

    cmd = notify.open_menu_cmd("tokens")

    assert cmd.startswith(shlex.quote(menu_launcher._python()) + " ")
    assert "buddymon.py open-menu tokens" in cmd


def test_open_menu_cmd_honors_python_override(monkeypatch):
    from lib import notify

    monkeypatch.setenv("BUDDYMON_PYTHON", "/tmp/BuddyMon.app/python/bin/python3")

    cmd = notify.open_menu_cmd("tokens")

    assert cmd.startswith("/tmp/BuddyMon.app/python/bin/python3 ")
    assert "buddymon.py open-menu tokens" in cmd


def test_open_menu_prefers_ghostty_and_replaces_owned_menu(monkeypatch):
    from lib import menu_launcher

    killed = []
    spawned = []
    buddy_script = menu_launcher._BUDDYMON
    ps = "\n".join([
        "  101 /Applications/Ghostty.app/Contents/MacOS/ghostty",
        f"  202 /Applications/Ghostty.app/Contents/MacOS/ghostty --command=/bin/zsh --input=raw:exec /usr/bin/python3 {buddy_script} menu\\n",
        f"  203 /Applications/Ghostty.app/Contents/MacOS/ghostty --window-width=88 --window-height=30 -e /usr/bin/python3 {buddy_script} menu tokens",
        "  303 /Applications/Ghostty.app/Contents/MacOS/ghostty --command=/bin/zsh --input=raw:exec /usr/bin/python3 /tmp/other/buddymon.py menu\\n",
        "  404 /Applications/Ghostty.app/Contents/MacOS/ghostty --command=/bin/zsh",
    ])
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: True)

    def fake_run(args, **_kwargs):
        if args[:3] == ["ps", "-ax", "-o"]:
            return type("Result", (), {"returncode": 0, "stdout": ps})()
        if args[0] == "kill":
            killed.append(int(args[1]))
            return type("Result", (), {"returncode": 0, "stdout": ""})()
        raise AssertionError(args)

    monkeypatch.setattr(menu_launcher.subprocess, "run", fake_run)
    monkeypatch.setattr(
        menu_launcher,
        "_request_launch",
        lambda args: (spawned.append(args) or True),
    )

    menu_launcher.open_menu("tokens")

    assert killed == [202, 203]
    assert len(spawned) == 1
    args = spawned[0]
    assert args[:4] == [
        "open",
        "-na",
        "Ghostty.app",
        "--args",
    ]
    for option in [
        "--title=BuddyMon Menu",
        "--window-save-state=never",
        "--fullscreen=false",
        "--maximize=false",
        "--confirm-close-surface=false",
        "--window-position-x=80",
        "--window-position-y=80",
        "--window-width=112",
        "--window-height=38",
        "--command=/bin/zsh",
    ]:
        assert option in args
    assert "-e" not in args
    assert (
        f"--input=raw:exec {menu_launcher._run_text('tokens')}\\n"
        in args
    )
    assert "osascript" not in args


def test_open_showcase_menu_uses_targeted_ghostty_window(monkeypatch):
    from lib import menu_launcher

    spawned = []
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_close_owned_ghostty_menus", lambda: None)
    monkeypatch.setattr(
        menu_launcher,
        "_request_launch",
        lambda args: (spawned.append(args) or True),
    )

    menu_launcher.open_menu("showcase")

    assert len(spawned) == 1
    args = spawned[0]
    assert args[:3] == ["open", "-na", "Ghostty.app"]
    assert "--command=/bin/zsh" in args
    assert (
        f"--input=raw:exec {menu_launcher._run_text('showcase')}\\n"
        in args
    )
    assert "osascript" not in args


def test_open_menu_can_keep_existing_owned_ghostty_menus(monkeypatch):
    from lib import menu_launcher

    killed = []
    spawned = []
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_close_owned_ghostty_menus", lambda: killed.append("closed"))
    monkeypatch.setattr(
        menu_launcher,
        "_request_launch",
        lambda args: (spawned.append(args) or True),
    )

    menu_launcher.open_menu("tokens", replace_owned=False)

    assert killed == []
    assert spawned and spawned[0][:2] == ["open", "-na"]


def test_open_menu_uses_iterm_when_ghostty_missing(monkeypatch):
    from lib import menu_launcher

    spawned = []
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: False)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: True)
    monkeypatch.setattr(menu_launcher.subprocess, "Popen", lambda args: spawned.append(args))

    menu_launcher.open_menu("tokens")

    assert spawned and spawned[0][0] == "osascript"
    assert "iTerm" in spawned[0][2]
    assert "buddymon.py menu tokens" in spawned[0][2]
    assert "set bounds of current window to {80, 80, 1120, 760}" in spawned[0][2]


def test_open_menu_uses_terminal_when_ghostty_and_iterm_missing(monkeypatch):
    from lib import menu_launcher

    spawned = []
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: False)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: False)
    monkeypatch.setattr(menu_launcher.subprocess, "Popen", lambda args: spawned.append(args))

    menu_launcher.open_menu("tokens")

    assert spawned and spawned[0][0] == "osascript"
    assert any("Terminal" in part for part in spawned[0])
    assert any("buddymon.py menu tokens" in part for part in spawned[0])
    assert any(
        "set bounds of front window to {80, 80, 1120, 760}" in part
        for part in spawned[0]
    )


def test_open_menu_normalizes_and_uses_requested_window_frame(monkeypatch):
    from lib import menu_launcher

    assert menu_launcher.normalize_window_frame() == (80, 80, 1040, 680)
    assert menu_launcher.normalize_window_frame("620,24,760,520") == (
        620,
        24,
        760,
        520,
    )

    spawned = []
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_close_owned_ghostty_menus", lambda: None)
    monkeypatch.setattr(
        menu_launcher,
        "_request_launch",
        lambda args: (spawned.append(args) or True),
    )

    menu_launcher.open_menu(
        "tokens",
        window_frame=(620, 24, 760, 520),
    )

    args = spawned[0]
    assert "--window-position-x=620" in args
    assert "--window-position-y=24" in args
    assert "--window-width=88" in args
    assert "--window-height=30" in args


def test_ghostty_grid_tracks_adaptive_window_profiles():
    from lib import menu_launcher

    assert menu_launcher.ghostty_grid_for_frame(1040, 680) == (112, 38)
    assert menu_launcher.ghostty_grid_for_frame(920, 600) == (100, 34)
    assert menu_launcher.ghostty_grid_for_frame(760, 520) == (88, 30)
    assert menu_launcher.ghostty_grid_for_frame(900, 680) == (88, 30)


def test_open_menu_rejects_invalid_window_frames():
    from lib import menu_launcher

    with pytest.raises(ValueError):
        menu_launcher.normalize_window_frame("80,80,760")
    with pytest.raises(ValueError):
        menu_launcher.normalize_window_frame("80,80,0,520")


def test_ghostty_launch_never_creates_a_provisional_applescript_window():
    from lib import menu_launcher

    args = menu_launcher._ghostty_args(
        "party",
        window_frame=(420, 24, 760, 520),
    )

    assert "-e" not in args
    assert args[0] == "open"
    assert "osascript" not in args
    assert "--window-save-state=never" in args
    assert "--confirm-close-surface=false" in args
    assert "--command=/bin/zsh" in args
    assert (
        f"--input=raw:exec {menu_launcher._run_text('party')}\\n"
        in args
    )


def test_ghostty_launch_shell_quotes_bundled_runtime_paths(monkeypatch):
    from lib import menu_launcher

    python = "/Applications/BuddyMon Friend.app/Contents/Resources/python/bin/python3"
    monkeypatch.setenv("BUDDYMON_PYTHON", python)

    args = menu_launcher._ghostty_args("party")
    startup = next(arg for arg in args if arg.startswith("--input="))

    assert "-e" not in args
    assert f"'{python}'" in startup
    assert "buddymon.py menu party" in startup


def test_open_menu_falls_through_when_ghostty_launch_request_fails(monkeypatch):
    from lib import menu_launcher

    spawned = []
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_close_owned_ghostty_menus", lambda: None)

    monkeypatch.setattr(
        menu_launcher,
        "_request_launch",
        lambda args: (spawned.append(args) or False),
    )
    monkeypatch.setattr(menu_launcher.subprocess, "Popen", lambda args: spawned.append(args))

    target = menu_launcher.open_menu("tokens")

    assert target == "iterm"
    assert spawned[0][:2] == ["open", "-na"]
    assert "Ghostty.app" in spawned[0]
    assert spawned[1][0] == "osascript"
    assert "iTerm" in spawned[1][2]


def test_open_menu_iterm_preference_skips_ghostty(monkeypatch):
    from lib import menu_launcher

    spawned = []
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: True)
    monkeypatch.setattr(menu_launcher.subprocess, "Popen", lambda args: spawned.append(args))

    menu_launcher.open_menu("tokens", launcher="iterm")

    assert spawned and spawned[0][0] == "osascript"
    assert "iTerm" in spawned[0][2]


def test_open_menu_terminal_preference_uses_terminal_even_when_others_exist(monkeypatch):
    from lib import menu_launcher

    spawned = []
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: True)
    monkeypatch.setattr(menu_launcher.subprocess, "Popen", lambda args: spawned.append(args))

    menu_launcher.open_menu("tokens", launcher="terminal")

    assert spawned and spawned[0][0] == "osascript"
    assert any("Terminal" in part for part in spawned[0])


def test_open_menu_cli_accepts_launcher_override(monkeypatch):
    import buddymon
    from lib import state

    s = state.default_state()
    calls = []
    monkeypatch.setattr(buddymon.state, "load", lambda: s)
    monkeypatch.setattr(
        buddymon.notify,
        "open_menu",
        lambda screen, launcher="auto", replace_owned=True, window_frame=None: (
            calls.append((screen, launcher, replace_owned, window_frame)) or True
        ),
    )

    out = buddymon.open_menu(["settings", "--launcher", "iterm"])

    assert out == ""
    assert calls == [("settings", "iterm", True, None)]


def test_open_menu_cli_passes_replace_owned_preference(monkeypatch):
    import buddymon
    from lib import state

    s = state.default_state()
    s["preferences"]["menu_replace"] = "off"
    calls = []
    monkeypatch.setattr(buddymon.state, "load", lambda: s)
    monkeypatch.setattr(
        buddymon.notify,
        "open_menu",
        lambda screen, launcher="auto", replace_owned=True, window_frame=None: (
            calls.append((screen, launcher, replace_owned, window_frame)) or True
        ),
    )

    out = buddymon.open_menu(["showcase"])

    assert out == ""
    assert calls == [("showcase", "auto", False, None)]


def test_open_menu_cli_forwards_window_frame(monkeypatch):
    import buddymon
    from lib import state

    s = state.default_state()
    calls = []
    monkeypatch.setattr(buddymon.state, "load", lambda: s)
    monkeypatch.setattr(
        buddymon.notify,
        "open_menu",
        lambda screen, launcher="auto", replace_owned=True, window_frame=None: (
            calls.append((screen, launcher, replace_owned, window_frame)) or True
        ),
    )

    out = buddymon.open_menu([
        "party",
        "--window-frame=420,24,760,520",
    ])

    assert out == ""
    assert calls == [("party", "auto", True, (420, 24, 760, 520))]


def test_open_menu_cli_reports_invalid_or_missing_window_frame():
    import buddymon

    assert "Usage: open-menu" in buddymon.open_menu([
        "party",
        "--window-frame=420,24,760",
    ])
    assert "Usage: open-menu" in buddymon.open_menu([
        "party",
        "--window-frame",
    ])
    assert "Usage: open-menu" in buddymon.open_menu([
        "party",
        "--launcher",
    ])


def test_open_menu_cli_reports_invalid_launcher():
    import buddymon

    out = buddymon.open_menu(["settings", "--launcher", "warp"])

    assert "Usage: open-menu" in out


def test_open_menu_iterm_preference_falls_back_to_terminal(monkeypatch):
    from lib import menu_launcher

    spawned = []
    monkeypatch.setattr(menu_launcher, "_ghostty_available", lambda: True)
    monkeypatch.setattr(menu_launcher, "_iterm_available", lambda: False)
    monkeypatch.setattr(menu_launcher.subprocess, "Popen", lambda args: spawned.append(args))

    menu_launcher.open_menu("tokens", launcher="iterm")

    assert spawned and spawned[0][0] == "osascript"
    assert any("Terminal" in part for part in spawned[0])
