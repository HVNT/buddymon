"""Launch the interactive menu from external click handlers.

Preference order is Ghostty, iTerm2, then Terminal.app. Ghostty launches replace
only existing Ghostty app processes that are explicitly running this repo's
`buddymon.py menu`, avoiding hidden stale menus and Dock growth without touching
unrelated Ghostty windows.
"""
import shlex
import subprocess
from pathlib import Path

_BUDDYMON = Path(__file__).resolve().parent.parent / "buddymon.py"
_GHOSTTY_APP = Path("/Applications/Ghostty.app")
_ITERM_APP = Path("/Applications/iTerm.app")
_PYTHON = "/usr/bin/python3"
_WINDOW_COLS = 88
_WINDOW_ROWS = 30


def open_menu_cmd(initial_screen=None):
    """Command for external click handlers to run the launcher."""
    args = [_PYTHON, str(_BUDDYMON), "open-menu"]
    if initial_screen:
        args.append(initial_screen)
    return " ".join(shlex.quote(arg) for arg in args)


def open_menu(initial_screen=None):
    if _ghostty_available():
        _close_owned_ghostty_menus()
        _open_ghostty_menu(initial_screen)
    elif _iterm_available():
        _open_iterm_menu(initial_screen)
    else:
        _open_terminal_menu(initial_screen)


def _ghostty_available():
    return _GHOSTTY_APP.exists()


def _iterm_available():
    return _ITERM_APP.exists()


def _menu_args(initial_screen=None):
    args = [_PYTHON, str(_BUDDYMON), "menu"]
    if initial_screen:
        args.append(initial_screen)
    return args


def _run_text(initial_screen=None):
    return " ".join(shlex.quote(arg) for arg in _menu_args(initial_screen))


def _ghostty_args(initial_screen=None):
    startup = "raw:exec " + _run_text(initial_screen) + "\\n"
    return [
        "open",
        "-na",
        "Ghostty",
        "--args",
        f"--window-width={_WINDOW_COLS}",
        f"--window-height={_WINDOW_ROWS}",
        "--command=/bin/zsh",
        f"--input={startup}",
    ]


def _iterm_args(initial_screen=None):
    run = _run_text(initial_screen).replace("\\", "\\\\").replace('"', '\\"')
    script = (
        'tell application "iTerm"\n'
        '  create window with default profile\n'
        f'  tell current session of current window to write text "{run}"\n'
        '  activate\n'
        'end tell'
    )
    return ["osascript", "-e", script]


def _terminal_args(initial_screen=None):
    run = _run_text(initial_screen).replace("\\", "\\\\").replace('"', '\\"')
    return [
        "osascript",
        "-e",
        f'tell application "Terminal" to do script "{run}"',
        "-e",
        'tell application "Terminal" to activate',
    ]


def _open_ghostty_menu(initial_screen=None):
    subprocess.Popen(_ghostty_args(initial_screen))


def _open_iterm_menu(initial_screen=None):
    subprocess.Popen(_iterm_args(initial_screen))


def _open_terminal_menu(initial_screen=None):
    subprocess.Popen(_terminal_args(initial_screen))


def _close_owned_ghostty_menus():
    for pid in _owned_ghostty_menu_pids():
        _terminate(pid)


def _owned_ghostty_menu_pids():
    try:
        result = subprocess.run(
            ["ps", "-ax", "-o", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    return [
        pid for pid, command in _parse_ps_lines(result.stdout)
        if _is_owned_ghostty_menu_command(command)
    ]


def _parse_ps_lines(text):
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, command = stripped.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        rows.append((pid, command.strip()))
    return rows


def _is_owned_ghostty_menu_command(command):
    return (
        command.startswith("/Applications/Ghostty.app/Contents/MacOS/ghostty")
        and f"{_BUDDYMON} menu" in command
    )


def _terminate(pid):
    try:
        subprocess.run(["kill", str(int(pid))], capture_output=True, timeout=1)
    except Exception:
        pass
