"""Stateful terminal I/O and inline-image transport for the TUI."""

import os
import re
import select
import shutil
import sys

from . import kgp


HOME_CLEAR = "\x1b[H\x1b[2J"
HIDE_CURSOR, SHOW_CURSOR = "\x1b[?25l", "\x1b[?25h"
ALT_SCREEN, MAIN_SCREEN = "\x1b[?1049h", "\x1b[?1049l"
MOUSE_ON = "\x1b[?1000h\x1b[?1006h"
MOUSE_OFF = "\x1b[?1000l\x1b[?1006l"
IMAGE_RE = re.compile("\x01IMG(\\d+)\x02")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

_graphics_enabled = False
_cell_size = None
_frame_images = []


def configure_graphics(enabled):
    global _graphics_enabled
    _graphics_enabled = bool(enabled)


def graphics_enabled():
    return _graphics_enabled


def set_cell_size(size):
    global _cell_size
    _cell_size = size


def cell_size():
    return _cell_size


def begin_frame():
    _frame_images.clear()


def register_image(png_bytes, cols, rows):
    index = len(_frame_images)
    _frame_images.append((png_bytes, cols, rows))
    return index


def image_count():
    return len(_frame_images)


def image_at(index):
    return _frame_images[index]


def frame_images():
    """Expose the current frame registry for focused transport tests."""
    return _frame_images


def clear_images():
    return kgp.clear()


def _visible_width(line):
    return len(ANSI_RE.sub("", line))


def _marker_col(line, marker_start):
    prefix = IMAGE_RE.sub(lambda match: " " * len(match.group(0)), line[:marker_start])
    return _visible_width(prefix) + 1


def _term_report(query, pattern):
    """Write a terminal query and read back its reply, returning the two numeric
    capture groups (or None on timeout). Best-effort with a short timeout."""
    try:
        os.write(1, query)
        buf = bytearray()
        while len(buf) < 32:
            if not select.select([0], [], [], 0.12)[0]:
                break
            buf.extend(os.read(0, 1))
            if buf[-1:] == b"t":
                break
        m = re.search(pattern, bytes(buf))
        if m:
            return int(m.group(1)), int(m.group(2))
    except OSError:
        pass
    return None


def query_cell_size():
    """Cell size in pixels as (width, height), or None. Tries CSI 16 t directly,
    then derives it from the window size (CSI 14 t) divided by the grid."""
    cell = _term_report(b"\x1b[16t", rb"\x1b\[6;(\d+);(\d+)t")
    if cell:
        return cell[1], cell[0]  # reply is height;width
    win = _term_report(b"\x1b[14t", rb"\x1b\[4;(\d+);(\d+)t")
    if win:
        size = shutil.get_terminal_size((80, 24))
        if size.columns and size.lines:
            return max(1, win[1] // size.columns), max(1, win[0] // size.lines)
    return None


_CSI_KEYS = {
    b"[A": "up", b"[B": "down", b"[C": "right", b"[D": "left",
    b"OA": "up", b"OB": "down", b"OC": "right", b"OD": "left",
    b"[5~": "page_up", b"[6~": "page_down",
    b"[H": "home", b"[1~": "home", b"[7~": "home",
    b"[F": "end", b"[4~": "end", b"[8~": "end",
}


def _skip_terminal_string():
    """Consume an APC/DCS/OSC/PM/SOS reply (e.g. a kitty-graphics ack or a query
    response) up to its String Terminator (ESC \\) or BEL, so it never registers
    as a key or eats the keypress queued behind it."""
    prev = b""
    while select.select([0], [], [], 0.05)[0]:
        b = os.read(0, 1)
        if not b or b == b"\x07" or (prev == b"\x1b" and b == b"\\"):
            return
        prev = b


def _read_csi(intro):
    """Read a CSI ('[') or SS3 ('O') body through its final byte (0x40-0x7e)."""
    body = bytearray(intro)
    while select.select([0], [], [], 0.01)[0]:
        b = os.read(0, 1)
        if not b:
            break
        body += b
        if 0x40 <= b[0] <= 0x7e or len(body) >= 32:  # final byte (or runaway)
            break
    return bytes(body)


def read_key():
    """Block for one key. Arrow/SS3/wheel sequences map to names; a lone ESC is
    'esc'. Terminal *responses* (kitty graphics acks, query replies) are skipped
    rather than returned — otherwise a stray reply fires a phantom 'esc' and can
    swallow the real keypress queued behind it (the 'enter didn't register' bug)."""
    while True:
        ch = os.read(0, 1)
        if ch != b"\x1b":
            if ch in (b"\r", b"\n"):
                return "enter"
            if ch == b" ":
                return "space"
            try:
                return ch.decode()
            except UnicodeDecodeError:
                return ""
        # ESC: lone Escape, a key sequence, or a terminal reply to skip.
        if not select.select([0], [], [], 0.001)[0]:
            return "esc"
        intro = os.read(0, 1)
        if intro in (b"_", b"P", b"]", b"^", b"X"):  # APC/DCS/OSC/PM/SOS reply
            _skip_terminal_string()
            continue
        if intro not in (b"[", b"O"):
            return "esc"  # ESC + something else: treat as Escape
        seq = _read_csi(intro)
        if seq[:2] == b"[<":  # SGR mouse report
            try:
                button = int(seq[2:-1].split(b";", 1)[0])
            except ValueError:
                continue
            if button in (64, 65):
                return "wheel_up" if button == 64 else "wheel_down"
            continue  # other mouse events: ignore, keep waiting for a real key
        mapped = _CSI_KEYS.get(seq)
        if mapped:
            return mapped
        continue  # unrecognized CSI = a terminal response; skip it


def draw_frame(frame):
    if not _graphics_enabled:
        sys.stdout.write(HOME_CLEAR + frame.replace("\n", "\r\n"))
        sys.stdout.flush()
        return
    # Replace image markers with blanks (keeping the reserved cells) and collect
    # absolute positions, then paint the PNGs on top. Wipe prior images first so
    # the old selection doesn't linger.
    overlays = []
    rendered = []
    for row, line in enumerate(frame.split("\n"), start=1):
        for m in IMAGE_RE.finditer(line):
            png_bytes, cols, rows = _frame_images[int(m.group(1))]
            overlays.append((row, _marker_col(line, m.start()),
                             png_bytes, cols, rows, len(overlays) + 1))
        rendered.append(IMAGE_RE.sub(lambda m: " " * len(m.group(0)), line))
    out = [kgp.clear(), HOME_CLEAR, "\r\n".join(rendered)]
    for row, col, png_bytes, cols, rows, img_id in overlays:
        out.append("\x1b[%d;%dH" % (row, col) + kgp.place(png_bytes, cols, rows, img_id))
    sys.stdout.write("".join(out))
    sys.stdout.flush()
