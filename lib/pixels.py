"""Half-block ANSI renderer: char grid + palette -> terminal lines.

Each text row packs two pixel rows using '▀' (fg=top, bg=bottom). Transparent
pixels get no color, so sprites sit cleanly on any terminal background.
"""

RESET = "\x1b[0m"


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _dim(rgb, factor):
    return tuple(max(0, int(c * factor)) for c in rgb)


def render(grid, palette, dim=1.0):
    """grid: list of equal-length strings, '.' = transparent.
    palette: char -> '#rrggbb'. Returns list of ANSI strings (one per 2 pixel rows).
    """
    rgb = {ch: _dim(_hex_to_rgb(hx), dim) for ch, hx in palette.items()}
    if len(grid) % 2:
        grid = grid + ["." * len(grid[0])]
    lines = []
    for y in range(0, len(grid), 2):
        top_row, bot_row = grid[y], grid[y + 1]
        parts = []
        for top_ch, bot_ch in zip(top_row, bot_row):
            top, bot = rgb.get(top_ch), rgb.get(bot_ch)
            if top and bot:
                parts.append("\x1b[38;2;%d;%d;%d;48;2;%d;%d;%dm▀" % (*top, *bot))
            elif top:
                parts.append("\x1b[38;2;%d;%d;%dm▀" % top)
            elif bot:
                parts.append("\x1b[38;2;%d;%d;%dm▄" % bot)
            else:
                parts.append(RESET + " ")
        lines.append("".join(parts) + RESET)
    return lines


def bob(grid, down=True):
    """Shift the sprite one pixel vertically for a two-frame idle animation."""
    blank = "." * len(grid[0])
    return [blank] + grid[:-1] if down else grid[1:] + [blank]
