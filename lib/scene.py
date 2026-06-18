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
_BOX = "#3c3c44"
_HP = "#30d158"
_HP_EMPTY = "#5a5a62"
_PLATFORM = "#55555e"


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


def _hp_fill(c, x1, y1, x2, y2, frac):
    """Draw an HP bar: full empty track, then a green fill proportional to frac."""
    c.rect(x1, y1, x2, y2, _HP_EMPTY, fill=True)
    if frac > 0:
        end = x1 + max(1, round((x2 - x1) * max(0.0, min(1.0, frac))))
        c.rect(x1, y1, end, y2, _HP, fill=True)


def battle_screen(buddy_frame, wild_frame, outcome, wild_hp_frac=None, buddy_hp_frac=None):
    """Game Boy-style battle screen for the dropdown. Canvas sizes itself to the
    two sprites. HP fractions, when given (Battle Mode), fill the bars
    proportionally; otherwise the bars are cosmetic (Safari/last-encounter)."""
    buddy_grid, buddy_pal = buddy_frame
    wild_grid, wild_pal = wild_frame
    sw = max(len(buddy_grid[0]), len(wild_grid[0]))
    sh = max(len(buddy_grid), len(wild_grid))
    box_w = max(34, sw + 6)
    W = sw + box_w + 16          # sprite column + HP-box column + margins
    H = sh * 2 + 18              # stacked wild (top) + buddy (bottom) + bands
    c = Canvas(W, H)

    # wild: top-right on a platform, HP box top-left
    plat_y = sh + 4
    c.hline(W - sw - 8, W - 2, plat_y, _PLATFORM)
    if outcome == "caught":
        ball_grid, ball_pal = POKEBALL
        c.sprite(ball_grid, ball_pal, W - sw // 2 - 12, plat_y - 12)
        c.sparkles(W - sw // 2 - 8, plat_y - 14)
    else:
        c.sprite(wild_grid, wild_pal, W - len(wild_grid[0]) - 6, plat_y - len(wild_grid))
        if outcome == "fled":
            c.dust(W - sw - 14, plat_y - 6)
    c.rect(2, 3, box_w, 14, _BOX)
    wf = 0.0 if outcome == "caught" else (1.0 if wild_hp_frac is None else wild_hp_frac)
    _hp_fill(c, 6, 7, box_w - 4, 10, wf)

    # buddy: bottom-left (mirrored, facing the wild), HP box bottom-right
    buddy_plat = H - 4
    c.hline(2, sw + 8, buddy_plat, _PLATFORM)
    c.sprite(mirror(buddy_grid), buddy_pal, 6, buddy_plat - len(buddy_grid))
    c.rect(W - box_w, H - 18, W - 2, H - 7, _BOX)
    _hp_fill(c, W - box_w + 4, H - 14, W - 6, H - 11,
             1.0 if buddy_hp_frac is None else buddy_hp_frac)

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
