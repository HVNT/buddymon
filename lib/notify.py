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


def open_menu_cmd(initial_screen=None):
    """Shell command (run by terminal-notifier on click) that opens the menu in
    a terminal. Uses the menu launcher's Ghostty → iTerm2 → Terminal.app order."""
    return menu_launcher.open_menu_cmd(initial_screen)


def open_menu(initial_screen=None):
    try:
        menu_launcher.open_menu(initial_screen)
    except Exception:
        pass


def notify(title, text):
    tn = shutil.which("terminal-notifier")
    if tn:
        try:
            subprocess.run(
                [tn, "-title", title, "-message", text,
                 "-sound", "Glass", "-execute", open_menu_cmd()],
                capture_output=True, timeout=3)
            return
        except Exception:
            pass
    script = (f'display notification "{_esc(text)}" '
              f'with title "{_esc(title)}" sound name "Glass"')
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)
    except Exception:
        pass


def _esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')
