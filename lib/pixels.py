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


# ── high-quality scaled rendering ─────────────────────────────────────────────
# render() maps each palette char straight to a half-block, so it only looks
# good at the sprite's native size. Shrinking a 96px sprite to a ~16-char grid
# with nearest-neighbor sampling (the old path) drops most pixels and crushes
# the palette — distinct species collapse into the same blob. render_scaled()
# instead rasterizes to RGB and area-averages, so every source pixel feeds the
# result and colors blend the way an image downscaler would.

def _grid_to_rgb(grid, palette):
    rgb = {ch: _hex_to_rgb(hx) for ch, hx in palette.items()}
    return [[rgb.get(ch) for ch in row] for row in grid]


def _resample(px, dst_w, dst_h, alpha_floor=0.42):
    """Area-average an RGB matrix (None = transparent) down to dst_w x dst_h.
    Each destination cell averages the source region it covers, weighted by
    sub-pixel overlap; it stays transparent unless opaque coverage clears
    alpha_floor, which keeps edges crisp without erasing thin features."""
    src_h, src_w = len(px), len(px[0])
    out = [[None] * dst_w for _ in range(dst_h)]
    for dy in range(dst_h):
        sy0, sy1 = dy * src_h / dst_h, (dy + 1) * src_h / dst_h
        for dx in range(dst_w):
            sx0, sx1 = dx * src_w / dst_w, (dx + 1) * src_w / dst_w
            r = g = b = opaque = total = 0.0
            y = int(sy0)
            while y < sy1:
                wy = min(sy1, y + 1) - max(sy0, y)
                x = int(sx0)
                while x < sx1:
                    w = wy * (min(sx1, x + 1) - max(sx0, x))
                    total += w
                    p = px[y][x]
                    if p is not None:
                        opaque += w
                        r += p[0] * w
                        g += p[1] * w
                        b += p[2] * w
                    x += 1
                y += 1
            if total and opaque >= alpha_floor * total:
                out[dy][dx] = (round(r / opaque), round(g / opaque), round(b / opaque))
    return out


def _pad_rgb(px, w, h):
    """Center an RGB matrix inside a fixed w x h transparent box."""
    cur_h = len(px)
    cur_w = len(px[0]) if px else 0
    left = max(0, (w - cur_w) // 2)
    top = max(0, (h - cur_h) // 2)
    out = [[None] * w for _ in range(h)]
    for y, row in enumerate(px[:h]):
        for x, p in enumerate(row[:w]):
            out[top + y][left + x] = p
    return out


def _render_rgb(px, dim=1.0):
    if len(px) % 2:
        px = px + [[None] * len(px[0])]
    lines = []
    for y in range(0, len(px), 2):
        parts = []
        for top, bot in zip(px[y], px[y + 1]):
            if top:
                top = _dim(top, dim)
            if bot:
                bot = _dim(bot, dim)
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


def nearest(grid, w, h):
    """Nearest-neighbor resample a char grid to exactly w x h cells. Sharp, no
    blending — used to build a PNG that matches its on-screen box pixel-for-pixel
    so the terminal does zero resampling (no blur, no smear)."""
    src_h, src_w = len(grid), len(grid[0])
    return ["".join(grid[y * src_h // h][x * src_w // w] for x in range(w))
            for y in range(h)]


def render_scaled(grid, palette, max_w, max_h, dim=1.0, pad_to=None):
    """Render a sprite to half-block lines, area-averaging it down to fit within
    (max_w, max_h) pixels. Optionally center it in a fixed pad_to=(w, h) box so
    stacked/paired sprites stay aligned. Use this for the larger "stare-at"
    surfaces (party/dex preview, battle portraits); render() stays for
    native-size statusline art."""
    px = _grid_to_rgb(grid, palette)
    src_h = len(px)
    src_w = len(px[0]) if px else 1
    scale = min(1.0, max_w / src_w, max_h / src_h)
    if scale < 1.0:
        px = _resample(px, max(1, round(src_w * scale)), max(1, round(src_h * scale)))
    if pad_to:
        px = _pad_rgb(px, *pad_to)
    return _render_rgb(px, dim)
