"""macOS notifications for rare moments. Must never raise: callers are hooks."""
import subprocess


def notify(title, text):
    script = (f'display notification "{_esc(text)}" '
              f'with title "{_esc(title)}" sound name "Glass"')
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)
    except Exception:
        pass


def _esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')
