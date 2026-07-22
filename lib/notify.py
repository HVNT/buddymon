"""macOS notifications for rare moments. Must never raise: callers are hooks.

Plain AppleScript `display notification` banners are owned by Script Editor, so
clicking one opens Script Editor instead of the game (AppleScript can't attach a
click action). When `terminal-notifier` is installed we post through it with
`-execute`, so a click opens the buddy's menu — which jumps straight into a
pending encounter. Fallback chain:

  terminal-notifier + launcher   → Ghostty, then iTerm2, then Terminal.app
  no terminal-notifier          → plain banner (shows, but isn't clickable)
"""
import shutil
import subprocess

from . import menu_launcher
from . import state as st


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


def notify(title, text, state=None, notifications=None):
    mode = _notification_mode(state, notifications)
    if mode == "off":
        return
    tn = shutil.which("terminal-notifier")
    if tn:
        try:
            args = [tn, "-title", title, "-message", text]
            if mode == "on":
                args += ["-sound", "Glass"]
            args += ["-execute", open_menu_cmd()]
            subprocess.run(
                args,
                capture_output=True, timeout=3)
            return
        except Exception:
            pass
    script = f'display notification "{_esc(text)}" with title "{_esc(title)}"'
    if mode == "on":
        script += ' sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)
    except Exception:
        pass


def banner(title, text, sound=False):
    """Best-effort one-way banner for explicit user actions."""
    script = f'display notification "{_esc(text)}" with title "{_esc(title)}"'
    if sound:
        script += ' sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)
    except Exception:
        pass


def _esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')
