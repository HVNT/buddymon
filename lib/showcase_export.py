"""Local PNG export for the curated Showcase."""
from datetime import datetime
from pathlib import Path
import string
import unicodedata

from . import data, packs, png, showcase

WIDTH = 216
HEIGHT = 150
PNG_SCALE = 4
CARD_W = 64
CARD_H = 45
CARD_GAP = 6
CARD_X = 6
CARD_Y = 45
CARD_ROW_GAP = 7
SPRITE_W = 36
SPRITE_H = 23

_BG = "#eaf1f5"
_CARD = "#fffaf0"
_CARD_ALT = "#f5f7fb"
_INK = "#172033"
_MUTED = "#667085"
_BORDER = "#2a3242"
_SHADOW = "#c6d2dc"
_GOLD = "#f4c542"
_BLUE = "#3b82f6"
_GREEN = "#2f855a"
_RED = "#d92d20"
_PODIUM = "#d6a84f"
_PODIUM_DARK = "#8b6f2f"

_RARITY_COLOR = {
    "common": "#5b6b7a",
    "uncommon": "#2f855a",
    "rare": "#2563eb",
    "legendary": "#b7791f",
    "mythic": "#9333ea",
    "starter": "#0f766e",
}

_CHAR_POOL = (
    string.ascii_letters
    + string.digits
    + "!$%&()*+,-/:;<=>?@[]^_{|}~"
)

_FONT = {
    " ": ("000", "000", "000", "000", "000"),
    "A": ("111", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("111", "100", "100", "100", "111"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("111", "100", "101", "101", "111"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "111"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("111", "101", "101", "101", "111"),
    "P": ("111", "101", "111", "100", "100"),
    "Q": ("111", "101", "101", "111", "001"),
    "R": ("111", "101", "111", "110", "101"),
    "S": ("111", "100", "111", "001", "111"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "#": ("010", "111", "010", "111", "010"),
    ".": ("000", "000", "000", "000", "010"),
    "-": ("000", "000", "111", "000", "000"),
    "/": ("001", "001", "010", "100", "100"),
    ":": ("000", "010", "000", "010", "000"),
    "'": ("010", "010", "000", "000", "000"),
    "*": ("101", "010", "111", "010", "101"),
    "?": ("111", "001", "011", "000", "010"),
}


class _Canvas:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.grid = [["."] * width for _ in range(height)]
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
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = self._char(color)

    def fill_rect(self, x, y, width, height, color):
        for yy in range(y, y + height):
            for xx in range(x, x + width):
                self.put(xx, yy, color)

    def rect(self, x, y, width, height, color):
        for xx in range(x, x + width):
            self.put(xx, y, color)
            self.put(xx, y + height - 1, color)
        for yy in range(y, y + height):
            self.put(x, yy, color)
            self.put(x + width - 1, yy, color)

    def paste_grid(self, grid, palette, x, y):
        for yy, row in enumerate(grid):
            for xx, ch in enumerate(row):
                if ch in palette:
                    self.put(x + xx, y + yy, palette[ch])

    def result(self):
        return ["".join(row) for row in self.grid], dict(self.palette)


def _safe_text(value):
    text = str(value or "").replace("♀", "F").replace("♂", "M")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(ch if ch.upper() in _FONT else "?" for ch in text.upper())


def _fit_text(text, max_chars):
    text = _safe_text(text).strip()
    if len(text) <= max_chars:
        return text
    return text[:max(0, max_chars - 1)] + "."


def _text_width(text, scale=1):
    text = _safe_text(text)
    if not text:
        return 0
    return (len(text) * 3 + max(0, len(text) - 1)) * scale


def _draw_text(canvas, x, y, text, color, scale=1):
    cursor = x
    for ch in _safe_text(text):
        glyph = _FONT.get(ch, _FONT["?"])
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    canvas.fill_rect(cursor + gx * scale, y + gy * scale, scale, scale, color)
        cursor += 4 * scale


def _draw_centered(canvas, cx, y, text, color, max_width, scale=1):
    max_chars = max(1, (max_width + scale) // (4 * scale))
    text = _fit_text(text, max_chars)
    x = cx - _text_width(text, scale) // 2
    _draw_text(canvas, x, y, text, color, scale)


def _crop_grid(grid, palette):
    points = [
        (x, y)
        for y, row in enumerate(grid)
        for x, ch in enumerate(row)
        if ch in palette
    ]
    if not points:
        return ["."]
    min_x = min(x for x, _y in points)
    max_x = max(x for x, _y in points)
    min_y = min(y for _x, y in points)
    max_y = max(y for _x, y in points)
    return [row[min_x:max_x + 1] for row in grid[min_y:max_y + 1]]


def _fit_sprite_grid(grid, palette, max_w=SPRITE_W, max_h=SPRITE_H):
    grid = _crop_grid(grid, palette)
    src_h = len(grid)
    src_w = len(grid[0])
    scale = min(max_w / src_w, max_h / src_h)
    dst_w = max(1, round(src_w * scale))
    dst_h = max(1, round(src_h * scale))
    out = []
    for y in range(dst_h):
        sy = min(src_h - 1, int(y / scale))
        row = []
        for x in range(dst_w):
            sx = min(src_w - 1, int(x / scale))
            row.append(grid[sy][sx])
        out.append("".join(row))
    return out


def _dex_label(name):
    number = data.DEX_NUMBERS.get(name)
    return f"#{number:03d}" if number else "#???"


def card_label_lines(entry, can_choose=True):
    """Return the two short labels drawn under one exported card."""
    pokemon = entry.get("pokemon")
    if pokemon:
        name = pokemon.get("name", "Pokemon")
        if pokemon.get("shiny"):
            name = f"{name}*"
        top = f"{_dex_label(pokemon.get('name'))} {name}"
        level = f"LV.{pokemon.get('level')}" if pokemon.get("level") else "LV.?"
        rarity = str(pokemon.get("rarity") or "").upper()
        return _fit_text(top, 14), _fit_text(f"{level} {rarity}", 14)
    if entry.get("missing"):
        return "MISSING SLOT", "REPLACE/CLEAR"
    return "EMPTY PODIUM", "CHOOSE FROM BOX" if can_choose else "CATCH FIRST"


def _draw_podium(canvas, x, y):
    canvas.fill_rect(x + 19, y + 18, 26, 5, _PODIUM)
    canvas.fill_rect(x + 16, y + 23, 32, 5, _PODIUM_DARK)
    canvas.fill_rect(x + 12, y + 28, 40, 5, _PODIUM)
    canvas.rect(x + 12, y + 18, 40, 15, _BORDER)


def _draw_card(canvas, entry, x, y, can_choose):
    pokemon = entry.get("pokemon")
    accent = _GREEN
    if pokemon:
        accent = _RARITY_COLOR.get(pokemon.get("rarity"), _BLUE)
        if pokemon.get("shiny"):
            accent = _GOLD
    elif entry.get("missing"):
        accent = _RED

    canvas.fill_rect(x + 2, y + 2, CARD_W, CARD_H, _SHADOW)
    canvas.fill_rect(x, y, CARD_W, CARD_H, _CARD if pokemon else _CARD_ALT)
    canvas.fill_rect(x + 1, y + 1, CARD_W - 2, 3, accent)
    canvas.rect(x, y, CARD_W, CARD_H, _BORDER)
    _draw_text(canvas, x + 4, y + 7, f"#{entry['slot'] + 1}", _MUTED)

    if pokemon:
        grid, palette = packs.gen5_frames(
            pokemon["name"],
            pokemon.get("type", "Normal"),
            pokemon.get("shiny"),
        )[0]
        sprite = _fit_sprite_grid(grid, palette)
        sx = x + (CARD_W - len(sprite[0])) // 2
        sy = y + 7 + (SPRITE_H - len(sprite)) // 2
        canvas.paste_grid(sprite, palette, sx, sy)
    else:
        _draw_podium(canvas, x, y)

    line1, line2 = card_label_lines(entry, can_choose=can_choose)
    _draw_centered(canvas, x + CARD_W // 2, y + 31, line1, _INK, CARD_W - 6)
    _draw_centered(canvas, x + CARD_W // 2, y + 38, line2, _MUTED, CARD_W - 6)


def showcase_filename(now=None):
    now = now or datetime.now()
    return f"BuddyMon Showcase - {now:%Y-%m-%d %H.%M.%S}.png"


def _available_path(path):
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem} ({index}){suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"too many existing Showcase exports in {path.parent}")


def render_showcase_grid(state, generated_at=None, slot_count=showcase.DEFAULT_SLOT_COUNT):
    generated_at = generated_at or datetime.now()
    entries = showcase.showcase_entries(state, slot_count)
    filled = sum(1 for entry in entries if entry.get("pokemon"))
    missing = sum(1 for entry in entries if entry.get("missing"))
    can_choose = bool((state or {}).get("pokemon"))

    canvas = _Canvas(WIDTH, HEIGHT)
    canvas.fill_rect(0, 0, WIDTH, HEIGHT, _BG)
    _draw_centered(canvas, WIDTH // 2, 8, "BUDDYMON SHOWCASE", _INK, WIDTH - 12, scale=3)
    _draw_text(canvas, 10, 29, generated_at.strftime("GENERATED %Y-%m-%d %H.%M"), _MUTED)
    _draw_text(canvas, 158, 29, f"FILLED {filled}/{slot_count}", _GREEN)
    if missing:
        _draw_text(canvas, 158, 36, f"MISSING {missing}", _RED)

    for index, entry in enumerate(entries):
        row = index // 3
        col = index % 3
        x = CARD_X + col * (CARD_W + CARD_GAP)
        y = CARD_Y + row * (CARD_H + CARD_ROW_GAP)
        _draw_card(canvas, entry, x, y, can_choose)
    return canvas.result()


def render_showcase_png(state, generated_at=None):
    grid, palette = render_showcase_grid(state, generated_at=generated_at)
    return png.grid_to_png(grid, palette, scale=PNG_SCALE, dpi=144)


def save_showcase_image(state, dest_dir=None, now=None):
    now = now or datetime.now()
    dest = Path(dest_dir).expanduser() if dest_dir else Path.home() / "Desktop"
    dest.mkdir(parents=True, exist_ok=True)
    path = _available_path(dest / showcase_filename(now))
    path.write_bytes(render_showcase_png(state, generated_at=now))
    return path
