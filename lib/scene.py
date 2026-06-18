"""Battle scene compositor: paints sprites and shapes onto one canvas grid.

Output is the same (grid, palette) shape the rest of the pipeline consumes
(pixels.render for terminals, png.grid_to_png for images). Each distinct
color gets its own palette char from a pool, so sprites with clashing
palette chars compose safely.
"""
import string

_CHAR_POOL = string.ascii_letters + string.digits + "#$%&*+-=?@^~"

CUTSCENE_SECS = 12

# phase windows within the cutscene (seconds since the encounter)
PHASE_ALERT = range(0, 2)
PHASE_VS = range(2, 4)
PHASE_WOBBLE = range(4, 7)
PHASE_RESULT = range(7, CUTSCENE_SECS)

POKEBALL = (
    [
        "..RRRRR..",
        ".RRRRRRR.",
        "RRRRRRRRR",
        "KKKKWKKKK",
        "WWWWWWWWW",
        ".WWWWWWW.",
        "..WWWWW..",
    ],
    {"R": "#ee1515", "K": "#222224", "W": "#f0f0f0"},
)

_SPARKLE = "#ffd700"
_DUST = "#9aa0a6"
_ALERT = "#ff3b30"
_BOX = "#2a2a32"               # HP-box interior (opaque GBC chrome)
_FRAME = "#12121a"             # near-black outer border of boxes
_FRAME_LIGHT = "#6a6a76"       # inner bevel highlight / double-border line
_MSG_BG = "#23232b"            # dialogue band interior
_HP_GREEN = "#58d058"          # >50% HP
_HP_YELLOW = "#f8d030"         # 20–50% HP
_HP_RED = "#f85038"            # ≤20% HP
_HP_EMPTY = "#444450"          # empty HP track
# Battle backdrop (GBA-style: sky over ground, with elliptical platform bases)
_SKY = "#bcd8f0"               # upper field
_SKY_HI = "#d6ebfb"            # light band just under the top border
_GROUND = "#a8cc82"            # lower field (grass)
_HORIZON = "#7d9e62"           # sky/ground divider
_PLAT_FILL = "#c2da98"         # platform disc
_PLAT_RIM = "#84a662"          # platform rim/shadow
_PLAT_HI = "#dceebc"           # platform lit top edge
_BORDER = "#20202a"            # screen edge (outer)
_BORDER_HI = "#707684"         # screen edge (inner bevel)
SCENE_ASPECT = 1.5             # battle screen min width:height (GBA-ish landscape)
WILD_SPRITE_SCALE = 0.875      # median Gen 3 front/back width ratio


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.grid = [["."] * w for _ in range(h)]
        self.palette = {}
        self._by_color = {}
        self._pool = iter(_CHAR_POOL)

    def _char(self, color):
        if color not in self._by_color:
            ch = next(self._pool)
            self._by_color[color] = ch
            self.palette[ch] = color
        return self._by_color[color]

    def put(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.grid[y][x] = self._char(color)

    def sprite(self, grid, palette, x, y):
        for dy, row in enumerate(grid):
            for dx, ch in enumerate(row):
                if ch in palette:
                    self.put(x + dx, y + dy, palette[ch])

    def hline(self, x1, x2, y, color):
        for x in range(x1, x2 + 1):
            self.put(x, y, color)

    def rect(self, x1, y1, x2, y2, color, fill=False):
        if fill:
            for y in range(y1, y2 + 1):
                self.hline(x1, x2, y, color)
        else:
            self.hline(x1, x2, y1, color)
            self.hline(x1, x2, y2, color)
            for y in range(y1, y2 + 1):
                self.put(x1, y, color)
                self.put(x2, y, color)

    def sparkles(self, cx, cy):
        for dx, dy in ((0, -3), (0, 3), (-3, 0), (3, 0), (-2, -2), (2, 2), (2, -2), (-2, 2)):
            self.put(cx + dx, cy + dy, _SPARKLE)

    def dust(self, cx, cy):
        for dx, dy in ((0, 0), (2, -1), (4, 1), (1, 2), (3, -2), (5, 0)):
            self.put(cx + dx, cy + dy, _DUST)

    def alert_mark(self, x, y):
        for dy in range(4):
            self.put(x, y + dy, _ALERT)
            self.put(x + 1, y + dy, _ALERT)
        self.put(x, y + 5, _ALERT)
        self.put(x + 1, y + 5, _ALERT)

    def result(self):
        return ["".join(row) for row in self.grid], dict(self.palette)


def mirror(grid):
    return [row[::-1] for row in grid]


def scale_grid(grid, factor):
    """Nearest-neighbor scale for pixel-art char grids."""
    if factor == 1:
        return list(grid)
    src_h, src_w = len(grid), len(grid[0])
    dst_w = max(1, round(src_w * factor))
    dst_h = max(1, round(src_h * factor))
    out = []
    for y in range(dst_h):
        sy = min(src_h - 1, int(y / factor))
        row = []
        for x in range(dst_w):
            sx = min(src_w - 1, int(x / factor))
            row.append(grid[sy][sx])
        out.append("".join(row))
    return out


def pad_vertical(grid, top=2, bottom=2):
    """Transparent breathing room: the menu bar scales images to fit its
    height, so padding shrinks the visible sprite proportionally."""
    blank = "." * len(grid[0])
    return [blank] * top + list(grid) + [blank] * bottom


THROW_SECS = 4  # phases 0..3: throw -> jiggle -> jiggle -> result


def throw_jiggle_bar(buddy_frame, wild_frame, phase, last_throw):
    """~44x16 bar composite for the pokéball throw: arc in, jiggle, then catch
    (sparkles) or break free (ball opens, wild returns)."""
    buddy_grid, buddy_pal = buddy_frame
    wild_grid, wild_pal = wild_frame
    ball_grid, ball_pal = POKEBALL
    caught = bool(last_throw and last_throw.get("caught"))
    c = Canvas(44, 16)
    c.sprite(mirror(buddy_grid), buddy_pal, 0, 16 - len(buddy_grid))

    if phase <= 0:  # the toss: ball arcs toward the wild, wild still out
        c.sprite(wild_grid, wild_pal, 30, 16 - len(wild_grid))
        c.sprite(ball_grid, ball_pal, 20, 2)
    elif phase < THROW_SECS - 1:  # jiggle: wild is in the ball, it wobbles
        c.sprite(ball_grid, ball_pal, 30 + (1 if phase % 2 else -1), 7)
    elif caught:  # caught: ball settles + sparkles
        c.sprite(ball_grid, ball_pal, 30, 6)
        c.sparkles(34, 8)
    else:  # broke free: wild pops back out
        c.sprite(wild_grid, wild_pal, 30, 16 - len(wild_grid))
        c.alert_mark(26, 3)
    return c.result()


def throw_phase_for(elapsed):
    phase = int(elapsed)
    return phase if 0 <= phase < THROW_SECS else None


def battle_bar(buddy_frame, wild_frame, phase, outcome):
    """~44x16 bar composite for one cutscene phase."""
    buddy_grid, buddy_pal = buddy_frame
    wild_grid, wild_pal = wild_frame
    c = Canvas(44, 16)
    c.sprite(mirror(buddy_grid), buddy_pal, 0, 16 - len(buddy_grid))

    if phase in PHASE_ALERT:
        c.alert_mark(24, 3)
    elif phase in PHASE_VS:
        c.sprite(wild_grid, wild_pal, 28, 16 - len(wild_grid))
    elif phase in PHASE_WOBBLE:
        if outcome == "caught":
            ball_grid, ball_pal = POKEBALL
            c.sprite(ball_grid, ball_pal, 30, 5 + (phase % 2))
        elif outcome == "fled":
            c.sprite(wild_grid, wild_pal, 30 + 2 * (phase % 2), 16 - len(wild_grid))
            c.dust(24, 10)
        else:  # no_balls: the wild just stares at you
            c.sprite(wild_grid, wild_pal, 28, 16 - len(wild_grid))
            c.alert_mark(22, 2)
    else:  # result
        if outcome == "caught":
            ball_grid, ball_pal = POKEBALL
            c.sprite(ball_grid, ball_pal, 30, 6)
            c.sparkles(34, 8)
        elif outcome == "fled":
            c.dust(30, 9)
        else:
            c.alert_mark(30, 4)
    return c.result()


def _hp_color(frac):
    """Green above 50%, yellow down to 20%, red below — the Gen-1 HP grade."""
    if frac > 0.5:
        return _HP_GREEN
    if frac > 0.2:
        return _HP_YELLOW
    return _HP_RED


def _hp_fill(c, x1, y1, x2, y2, frac):
    """Draw an HP bar: empty track, then a color-graded fill proportional to frac."""
    c.rect(x1, y1, x2, y2, _HP_EMPTY, fill=True)
    frac = max(0.0, min(1.0, frac))
    if frac > 0:
        end = x1 + max(1, round((x2 - x1) * frac))
        c.rect(x1, y1, end, y2, _hp_color(frac), fill=True)


def _backdrop(c, w, top, ground_y, bottom):
    """Sky over ground with a horizon line — the battle field behind the mons."""
    c.rect(0, top, w - 1, ground_y - 1, _SKY, fill=True)
    c.hline(0, w - 1, top, _SKY_HI)
    c.hline(0, w - 1, top + 1, _SKY_HI)
    c.rect(0, ground_y, w - 1, bottom, _GROUND, fill=True)
    c.hline(0, w - 1, ground_y, _HORIZON)


def _oval(c, cx, cy, rx, ry):
    """A flat elliptical platform base: filled disc, darker rim, lit top edge."""
    rx, ry = max(1, rx), max(1, ry)
    for dy in range(-ry, ry + 1):
        for dx in range(-rx, rx + 1):
            v = dx * dx / (rx * rx) + dy * dy / (ry * ry)
            if v <= 1.0:
                if v > 0.6:
                    c.put(cx + dx, cy + dy, _PLAT_HI if dy < 0 else _PLAT_RIM)
                else:
                    c.put(cx + dx, cy + dy, _PLAT_FILL)


def _hp_box(c, x1, y1, x2, y2, frac):
    """Framed, opaque Gen-style HP box: dark border, top bevel, graded bar."""
    c.rect(x1, y1, x2, y2, _BOX, fill=True)
    c.rect(x1, y1, x2, y2, _FRAME)
    c.hline(x1 + 1, x2 - 1, y1 + 1, _FRAME_LIGHT)
    _hp_fill(c, x1 + 3, y1 + 4, x2 - 3, y2 - 3, frac)


def _message_box(c, x1, y1, x2, y2):
    """The dialogue band: filled box with the classic double border."""
    c.rect(x1, y1, x2, y2, _MSG_BG, fill=True)
    c.rect(x1, y1, x2, y2, _FRAME)
    c.rect(x1 + 2, y1 + 2, x2 - 2, y2 - 2, _FRAME_LIGHT)


# ── tiny 5x7 bitmap font (uppercase letters used by the GB command box) ───────
# Our menu-bar runtime renders grids with the stdlib PNG encoder (no font lib),
# so the command-box lettering is hand-drawn. Only the glyphs the action labels
# use are defined; unknown chars render as blank cells.
_GLYPH_W = 5  # glyph cell width; height (7) is implicit in the row data below
_FONT = {
    " ": ("     ",) * 7,
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "N": ("#...#", "##..#", "#.#.#", "#.#.#", "#..##", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "\x10": ("#....", "##...", "###..", "####.", "###..", "##...", "#...."),  # ► cursor
}
_TEXT = "#1c1c24"        # GB command-box ink
_CMD_BG = "#f8f8f8"      # white command-box interior


def _text(c, x, y, s, color, scale=1, gap=1):
    """Blit an uppercase string with the bitmap font. Returns the next x."""
    cx = x
    for ch in s.upper():
        glyph = _FONT.get(ch)
        if glyph:
            for gy, row in enumerate(glyph):
                for gx, px in enumerate(row):
                    if px == "#":
                        for dy in range(scale):
                            for dx in range(scale):
                                c.put(cx + gx * scale + dx, y + gy * scale + dy, color)
        cx += (_GLYPH_W + gap) * scale
    return cx


def _command_box(c, x1, y1, x2, y2, options):
    """The classic Game Boy 2×2 command box: white panel, dark double border,
    a ► cursor on the first option, labels in the bitmap font. Display-only —
    the actual clickable actions live as menu rows beside this image."""
    c.rect(x1, y1, x2, y2, _CMD_BG, fill=True)
    c.rect(x1, y1, x2, y2, _FRAME)
    c.rect(x1 + 2, y1 + 2, x2 - 2, y2 - 2, _FRAME_LIGHT)
    midx = (x1 + x2) // 2
    col_x = (x1 + 7, midx + 5)
    row_y = (y1 + 5, y1 + 23)          # two text rows, 5x7 glyphs at scale 2
    cur = 12                            # cursor gutter (scale-2 ► + gap)
    for i, label in enumerate(options[:4]):
        r, cc = divmod(i, 2)            # 0=TL 1=TR 2=BL 3=BR (FIGHT/BAG/… order)
        ox, oy = col_x[cc], row_y[r]
        if i == 0:
            _text(c, ox, oy, "\x10", _TEXT, scale=2)   # selection cursor
        _text(c, ox + cur, oy, label, _TEXT, scale=2)


def battle_screen(buddy_frame, wild_frame, outcome, wild_hp_frac=None,
                  buddy_hp_frac=None, options=None):
    """Game Boy-style battle screen for the dropdown. Canvas sizes itself to the
    two sprites: wild top-right and buddy bottom-left on rounded platforms,
    framed HP boxes, and a band across the bottom. HP fractions, when given
    (Battle Mode), grade the bars green→yellow→red; otherwise full
    (Safari/last-encounter). When `options` is given, the bottom band is the
    classic 2×2 command box with those labels; otherwise a plain dialogue band."""
    buddy_grid, buddy_pal = buddy_frame
    wild_grid, wild_pal = wild_frame
    wild_grid = scale_grid(wild_grid, WILD_SPRITE_SCALE)
    sw = max(len(buddy_grid[0]), len(wild_grid[0]))
    sh = max(len(buddy_grid), len(wild_grid))
    box_w = max(34, sw + 6)
    bottom_h = 42 if options else 10
    H = sh * 2 + 22 + bottom_h   # stacked wild (top) + buddy (bottom) + band
    # widen to a landscape field (like the games' ~3:2 screen) so the mons sit
    # in opposite corners and the image fills the dropdown width
    W = max(sw + box_w + 16, round(H * SCENE_ASPECT))
    c = Canvas(W, H)
    field_bottom = H - bottom_h - 3
    plat_y = sh + 5
    bw, ww = len(buddy_grid[0]), len(wild_grid[0])

    # field backdrop: sky over ground, horizon at the wild's feet
    _backdrop(c, W, 0, plat_y, H - bottom_h - 1)
    # platform bases the mons stand on (wild near horizon, buddy in foreground)
    _oval(c, W - 6 - ww // 2, plat_y, ww // 2 + 3, max(3, (ww // 2 + 3) // 4))
    _oval(c, 6 + bw // 2, field_bottom, bw // 2 + 3, max(3, (bw // 2 + 3) // 4))

    # wild: top-right, HP box top-left
    if outcome == "caught":
        ball_grid, ball_pal = POKEBALL
        c.sprite(ball_grid, ball_pal, W - sw // 2 - 12, plat_y - 12)
        c.sparkles(W - sw // 2 - 8, plat_y - 14)
    else:
        c.sprite(wild_grid, wild_pal, W - ww - 6, plat_y - len(wild_grid))
        if outcome == "fled":
            c.dust(W - sw - 14, plat_y - 6)
    wf = 0.0 if outcome == "caught" else (1.0 if wild_hp_frac is None else wild_hp_frac)
    _hp_box(c, 2, 3, box_w, 15, wf)

    # buddy: bottom-left (mirrored, facing the wild), HP box right
    c.sprite(mirror(buddy_grid), buddy_pal, 6, field_bottom - len(buddy_grid))
    _hp_box(c, W - box_w, field_bottom - 14, W - 2, field_bottom - 2,
            1.0 if buddy_hp_frac is None else buddy_hp_frac)

    # bottom band: GB command box (with options) or a plain dialogue band
    if options:
        _command_box(c, 1, H - bottom_h, W - 2, H - 2, options)
    else:
        _message_box(c, 1, H - bottom_h, W - 2, H - 2)

    # screen edge: dark border with an inner bevel line
    c.rect(0, 0, W - 1, H - 1, _BORDER)
    c.rect(1, 1, W - 2, H - 2, _BORDER_HI)
    return c.result()


def phase_for(elapsed):
    """Map seconds-since-encounter to a cutscene phase, or None when over."""
    phase = int(elapsed)
    return phase if 0 <= phase < CUTSCENE_SECS else None


# ── evolution ceremony ───────────────────────────────────────────────────────

EVOLUTION_SECS = 16
EVO_SHOCK = range(0, 3)
EVO_FLASH = range(3, 6)
EVO_MORPH = range(6, 9)
EVO_REVEAL = range(9, 11)
EVO_CELEBRATE = range(11, EVOLUTION_SECS)


def silhouette(frame, color="#f8f8f8"):
    """The classic evolution white-out: shape only, transparency preserved."""
    grid, palette = frame
    return grid, {ch: color for ch in palette}


def evolution_bar(old_frame, new_frame, phase):
    """~44x16 bar composite for one ceremony phase."""
    c = Canvas(44, 16)

    def center(frame):
        grid, palette = frame
        c.sprite(grid, palette, (44 - len(grid[0])) // 2, 16 - len(grid))

    if phase in EVO_SHOCK:
        center(old_frame)
        c.alert_mark(33, 3)
    elif phase in EVO_FLASH:
        center(old_frame if phase % 2 else silhouette(old_frame))
    elif phase in EVO_MORPH:
        center(silhouette(old_frame if phase % 2 else new_frame))
    elif phase in EVO_REVEAL:
        center(new_frame)
        c.sparkles(8, 8)
        c.sparkles(36, 8)
    else:  # celebrate
        center(new_frame)
        c.sparkles(7, 5 + (phase % 2))
        c.sparkles(37, 6 - (phase % 2))
    return c.result()


def evolution_phase_for(elapsed):
    phase = int(elapsed)
    return phase if 0 <= phase < EVOLUTION_SECS else None
