"""Best-effort macOS notifications for rare moments.

AppleScript notification banners belong to Script Editor and can open it when
clicked, so BuddyMon never uses them. Finder-launched apps also have a minimal
PATH, so probe the common Homebrew locations before quietly skipping delivery.
Callers are hooks; notification failures must never escape.
"""
import shutil
import subprocess

from . import menu_launcher
from . import state as st

_TERMINAL_NOTIFIER_CANDIDATES = (
    "terminal-notifier",
    "/opt/homebrew/bin/terminal-notifier",
    "/usr/local/bin/terminal-notifier",
)


def open_menu_cmd(initial_screen=None):
    """Shell command (run by terminal-notifier on click) that opens the menu in
    a terminal. Uses the menu launcher's Ghostty → iTerm2 → Terminal.app order."""
    return menu_launcher.open_menu_cmd(initial_screen)


def open_menu(
    initial_screen=None,
    launcher="auto",
    replace_owned=True,
    window_frame=None,
):
    try:
        return bool(
            menu_launcher.open_menu(
                initial_screen,
                launcher=launcher,
                replace_owned=replace_owned,
                window_frame=window_frame,
            )
        )
    except Exception:
        return False


def _notification_mode(state=None, notifications=None):
    if notifications in st.PREFERENCE_VALUES["notifications"]:
        return notifications
    if isinstance(state, dict):
        return st.preference(state, "notifications")
    return st.DEFAULT_PREFERENCES["notifications"]


def _terminal_notifier():
    for candidate in _TERMINAL_NOTIFIER_CANDIDATES:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _deliver(title, text, *, sound=False, execute=None):
    notifier = _terminal_notifier()
    if not notifier:
        return False
    args = [notifier, "-title", title, "-message", text]
    if sound:
        args += ["-sound", "Glass"]
    if execute:
        args += ["-execute", execute]
    try:
        result = subprocess.run(args, capture_output=True, timeout=3)
        return result.returncode == 0
    except Exception:
        return False


def notify(title, text, state=None, notifications=None):
    mode = _notification_mode(state, notifications)
    if mode == "off":
        return
    _deliver(
        title,
        text,
        sound=mode == "on",
        execute=open_menu_cmd(),
    )


def banner(title, text, sound=False):
    """Best-effort one-way banner for explicit user actions."""
    _deliver(title, text, sound=sound)
