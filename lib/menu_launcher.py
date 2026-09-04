"""Launch the interactive menu from external click handlers.

Preference order is Ghostty, iTerm2, then Terminal.app. Ghostty launches one
isolated BuddyMon window directly and replaces prior BuddyMon-owned processes
without creating or closing provisional terminal surfaces.
"""
import os
import shlex
import subprocess
import sys
from pathlib import Path

_BUDDYMON = Path(__file__).resolve().parent.parent / "buddymon.py"
_GHOSTTY_APP = Path("/Applications/Ghostty.app")
_ITERM_APP = Path("/Applications/iTerm.app")
_GHOSTTY_TITLE = "BuddyMon Menu"
WINDOW_WIDTH = 1040
WINDOW_HEIGHT = 680
DEFAULT_WINDOW_FRAME = (80, 80, WINDOW_WIDTH, WINDOW_HEIGHT)
ROOMY_WINDOW_SIZE = (1040, 680)
MEDIUM_WINDOW_SIZE = (920, 600)
COMPACT_WINDOW_SIZE = (760, 520)
ROOMY_GHOSTTY_GRID = (112, 38)
MEDIUM_GHOSTTY_GRID = (100, 34)
COMPACT_GHOSTTY_GRID = (88, 30)
_GHOSTTY_LAUNCH_TIMEOUT = 5


def _python():
    return os.environ.get("BUDDYMON_PYTHON") or sys.executable or "/usr/bin/python3"


def open_menu_cmd(initial_screen=None):
    """Command for external click handlers to run the launcher."""
    args = [_python(), str(_BUDDYMON), "open-menu"]
    if initial_screen:
        args.append(initial_screen)
    return " ".join(shlex.quote(arg) for arg in args)


def open_menu(
    initial_screen=None,
    launcher="auto",
    replace_owned=True,
    window_frame=None,
):
    window_frame = normalize_window_frame(window_frame)
    for target in _launcher_order(launcher):
        if target == "ghostty" and _ghostty_available():
            try:
                if replace_owned:
                    _close_owned_ghostty_menus()
                if _open_ghostty_menu(initial_screen, window_frame):
                    return target
            except Exception:
                continue
        if target == "iterm" and _iterm_available():
            if _open_iterm_menu(initial_screen, window_frame):
                return target
        if target == "terminal":
            if _open_terminal_menu(initial_screen, window_frame):
                return target
    return None


def _launcher_order(launcher):
    if launcher == "iterm":
        return ("iterm", "terminal")
    if launcher == "terminal":
        return ("terminal",)
    return ("ghostty", "iterm", "terminal")


def _ghostty_available():
    return _GHOSTTY_APP.exists()


def _iterm_available():
    return _ITERM_APP.exists()


def _menu_args(initial_screen=None):
    args = [_python(), str(_BUDDYMON), "menu"]
    if initial_screen:
        args.append(initial_screen)
    return args


def _run_text(initial_screen=None):
    return " ".join(shlex.quote(arg) for arg in _menu_args(initial_screen))


def _ghostty_startup_input(initial_screen=None):
    return f"raw:exec {_run_text(initial_screen)}\\n"


def normalize_window_frame(window_frame=None):
    if window_frame is None:
        return DEFAULT_WINDOW_FRAME
    if isinstance(window_frame, str):
        parts = window_frame.split(",")
    else:
        parts = list(window_frame)
    if len(parts) != 4:
        raise ValueError("window frame must be x,y,width,height")
    try:
        x, y, width, height = (int(round(float(part))) for part in parts)
    except (TypeError, ValueError) as exc:
        raise ValueError("window frame must contain four numbers") from exc
    if width <= 0 or height <= 0:
        raise ValueError("window width and height must be positive")
    return x, y, width, height


def _applescript_bounds(window_frame):
    x, y, width, height = window_frame
    return f"{{{x}, {y}, {x + width}, {y + height}}}"


def _ghostty_args(initial_screen=None, window_frame=None):
    x, y, width, height = normalize_window_frame(window_frame)
    columns, rows = ghostty_grid_for_frame(width, height)
    return [
        "open",
        "-na",
        _GHOSTTY_APP.name,
        "--args",
        f"--title={_GHOSTTY_TITLE}",
        "--window-save-state=never",
        "--fullscreen=false",
        "--maximize=false",
        "--confirm-close-surface=false",
        f"--window-position-x={x}",
        f"--window-position-y={y}",
        f"--window-width={columns}",
        f"--window-height={rows}",
        "--command=/bin/zsh",
        f"--input={_ghostty_startup_input(initial_screen)}",
    ]


def ghostty_grid_for_frame(width, height):
    """Match a requested pixel footprint to a stable Ghostty cell profile."""
    if width >= ROOMY_WINDOW_SIZE[0] and height >= ROOMY_WINDOW_SIZE[1]:
        return ROOMY_GHOSTTY_GRID
    if width >= MEDIUM_WINDOW_SIZE[0] and height >= MEDIUM_WINDOW_SIZE[1]:
        return MEDIUM_GHOSTTY_GRID
    return COMPACT_GHOSTTY_GRID


def _iterm_args(initial_screen=None, window_frame=None):
    run = _run_text(initial_screen).replace("\\", "\\\\").replace('"', '\\"')
    bounds = _applescript_bounds(normalize_window_frame(window_frame))
    script = (
        'tell application "iTerm"\n'
        '  create window with default profile\n'
        f'  set bounds of current window to {bounds}\n'
        f'  tell current session of current window to write text "{run}"\n'
        '  activate\n'
        'end tell'
    )
    return ["osascript", "-e", script]


def _terminal_args(initial_screen=None, window_frame=None):
    run = _run_text(initial_screen).replace("\\", "\\\\").replace('"', '\\"')
    bounds = _applescript_bounds(normalize_window_frame(window_frame))
    script = (
        'tell application "Terminal"\n'
        f'  do script "{run}"\n'
        f'  set bounds of front window to {bounds}\n'
        '  activate\n'
        'end tell'
    )
    return [
        "osascript",
        "-e",
        script,
    ]


def _open_ghostty_menu(initial_screen=None, window_frame=None):
    return _request_launch(_ghostty_args(initial_screen, window_frame))


def _open_iterm_menu(initial_screen=None, window_frame=None):
    return _spawn(_iterm_args(initial_screen, window_frame))


def _open_terminal_menu(initial_screen=None, window_frame=None):
    return _spawn(_terminal_args(initial_screen, window_frame))


def _spawn(args):
    try:
        subprocess.Popen(args)
        return True
    except Exception:
        return False


def _request_launch(args):
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_GHOSTTY_LAUNCH_TIMEOUT,
        )
        return result.returncode == 0
    except Exception:
        return False


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
