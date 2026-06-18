"""Minimal stdlib PNG writer — enough to emit sprite frames as RGBA PNGs
for the menu bar (SwiftBar) and floating buddy (Hammerspoon). No PIL."""
import struct
import zlib


def _chunk(tag, payload):
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))


def _hex_rgba(hx):
    hx = hx.lstrip("#")
    return bytes((int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16), 255))


def grid_to_png(grid, palette, scale=1, dpi=None):
    """Sprite grid + palette -> PNG bytes (transparent background).

    dpi sets the pHYs chunk: macOS sizes images in points from their DPI
    metadata, so this controls how large the image renders (e.g. in the
    menu bar) independent of its pixel resolution."""
    colors = {ch: _hex_rgba(hx) for ch, hx in palette.items()}
    clear = bytes((0, 0, 0, 0))
    width = len(grid[0]) * scale
    raw = bytearray()
    for row in grid:
        scanline = bytearray()
        for ch in row:
            scanline += colors.get(ch, clear) * scale
        for _ in range(scale):
            raw += b"\x00" + scanline  # filter byte 0 per scanline
    header = struct.pack(">IIBBBBB", width, len(grid) * scale, 8, 6, 0, 0, 0)
    phys = b""
    if dpi:
        ppm = round(dpi / 0.0254)  # pixels per meter
        phys = _chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", header)
            + phys
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b""))
