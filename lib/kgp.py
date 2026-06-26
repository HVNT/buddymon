"""Inline PNG sprites in terminals that can draw bitmaps — the same crisp art the
macOS menu bar shows. Two wire protocols are spoken behind one interface:

- **kitty** graphics protocol (Ghostty, kitty, WezTerm): an APC string
  ``ESC _ G <control> ; <base64> ESC \\``, chunked at 4096 base64 bytes, with
  ``q=2`` to silence acks and ``C=1`` so the image doesn't move the cursor. Stale
  images are deleted with ``a=d`` each redraw.
- **iterm** inline-image protocol (iTerm2): an OSC string
  ``ESC ] 1337 ; File=inline=1;width=<cols>;height=<rows>;preserveAspectRatio=1 :
  <base64> ESC \\``. Sizing is in cells (matches our cols/rows) and
  ``preserveAspectRatio=1`` letterboxes — no stretch. iTerm2 has no delete-all and
  the cursor advances after the image, but ED (the caller's screen clear) erases
  inline images and the caller repositions absolutely before each image, so a
  no-op clear() is correct.

Half-block art (lib/pixels) is the fallback for plain terminals. `protocol()` is
the single source of truth; `place()`/`clear()` branch on it.
"""
import base64
import os
import sys

_ESC = "\x1b"
_ST = "\x1b\\"


def protocol():
    """Which inline-image protocol this terminal speaks: 'kitty', 'iterm', or
    None. Kitty-family is checked first; iTerm2 only emits its own OSC 1337."""
    if os.environ.get("BUDDYMON_NO_GRAPHICS"):
        return None
    if not sys.stdout.isatty():
        return None
    if os.environ.get("KITTY_WINDOW_ID"):
        return "kitty"
    prog = os.environ.get("TERM_PROGRAM", "").lower()
    if prog in ("ghostty", "wezterm"):
        return "kitty"
    term = os.environ.get("TERM", "").lower()
    if "kitty" in term or "ghostty" in term:
        return "kitty"
    if prog == "iterm.app" or os.environ.get("LC_TERMINAL", "").lower() == "iterm2":
        return "iterm"
    return None


def supported():
    """True when stdout is an interactive terminal that can draw inline images."""
    return protocol() is not None


def _apc(png_bytes, ctrl):
    b64 = base64.b64encode(png_bytes)
    chunks = [b64[i:i + 4096] for i in range(0, len(b64), 4096)] or [b""]
    out = []
    for i, chunk in enumerate(chunks):
        more = 1 if i < len(chunks) - 1 else 0
        head = "%s,m=%d" % (ctrl, more) if i == 0 else "m=%d" % more
        out.append("%s_G%s;%s%s" % (_ESC, head, chunk.decode("ascii"), _ST))
    return "".join(out)


def _iterm_place(png_bytes, cols, rows):
    b64 = base64.b64encode(png_bytes).decode("ascii")
    args = "inline=1;width=%d;height=%d;preserveAspectRatio=1" % (cols, rows)
    return "%s]1337;File=%s:%s%s" % (_ESC, args, b64, _ST)


def place(png_bytes, cols, rows, img_id):
    """Display png_bytes scaled into a cols x rows cell box at the cursor. The
    caller positions the cursor absolutely; neither protocol disturbs layout
    (kitty C=1 / iterm cursor-advance is overridden by the next placement)."""
    if protocol() == "iterm":
        return _iterm_place(png_bytes, cols, rows)
    ctrl = "a=T,f=100,q=2,C=1,i=%d,c=%d,r=%d" % (img_id, cols, rows)
    return _apc(png_bytes, ctrl)


def clear():
    """Wipe stale images before a redraw. kitty needs an explicit delete-all;
    iTerm2 has none — its inline images are erased by the screen clear (ED), so
    this is a no-op there."""
    if protocol() == "iterm":
        return ""
    return "%s_Ga=d,q=2%s" % (_ESC, _ST)
