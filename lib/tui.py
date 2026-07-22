"""Interactive terminal UI: arrow-key navigation of party, dex, journal, status.

Launched via `buddymon.py menu` (from the SwiftBar dropdown's "Open buddymon"
item, a shell alias, or a tmux popup). Raw-mode ANSI using only the stdlib, so
it stays responsive and readable in plain terminals. Sprite previews use compact
frames so the screens keep enough room for controls and scrolling.

The frame builders (`_menu_frame`, `_party_frame`, `_scroll_frame`) are pure
str-returning functions so they can be unit-tested without a terminal; the loop
and key reading are the only parts that touch the tty.
"""
import os
import random
import re
import select
import shutil
import sys

from . import backups, battle as bt, box, data, favorites, journal, kgp, packs, pixels, png, render, safari as sf
from . import showcase, showcase_export
from . import state as st
from . import token_usage

HIDE_CURSOR, SHOW_CURSOR = "\x1b[?25l", "\x1b[?25h"
ALT_SCREEN, MAIN_SCREEN = "\x1b[?1049h", "\x1b[?1049l"
HOME_CLEAR = "\x1b[H\x1b[2J"
MOUSE_ON, MOUSE_OFF = "\x1b[?1000h\x1b[?1006h", "\x1b[?1000l\x1b[?1006l"
DIM, BOLD, RESET = "\x1b[2m", "\x1b[1m", "\x1b[0m"
CYAN, GREEN = "\x1b[36m", "\x1b[32m"
BLUE, YELLOW, MAGENTA = "\x1b[34m", "\x1b[33m", "\x1b[35m"
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
ENCOUNTER_ART_W = 28
ENCOUNTER_ART_H = 24
# Party/dex/status preview box. Art height is in source pixels for half-block
# scaling; framed cards reserve terminal rows so inline PNGs and text fallback
# get the same geometry.
SELECT_ART_W = 36
SELECT_ART_H = 32
SELECT_CARD_WIDTH_FACTOR = 3
SELECT_CARD_HEIGHT_FACTOR = 2
SELECT_POKEMON_MAX_COLS = 14
SELECT_POKEMON_MAX_ROWS = 7
SELECT_CARD_INNER_W = SELECT_POKEMON_MAX_COLS * SELECT_CARD_WIDTH_FACTOR
SELECT_CARD_INNER_ROWS = SELECT_POKEMON_MAX_ROWS * SELECT_CARD_HEIGHT_FACTOR
SHOWCASE_CARD_INNER_W = 30
SHOWCASE_CARD_BODY_ROWS = 10
SHOWCASE_CARD_W = SHOWCASE_CARD_INNER_W + 4
SHOWCASE_CARD_ROWS = SHOWCASE_CARD_BODY_ROWS + 5
SHOWCASE_GAP = 3
SHOWCASE_MAX_COLUMNS = 2
SHOWCASE_ART_W = 24
SHOWCASE_SPRITE_W = 22
SHOWCASE_SPRITE_ROWS = 8

# MTG-style one-letter rarity codes keep every list row a constant width, so the
# layout never reflows as the selection moves. starter→S; M reserved for mythic.
RARITY_CODE = {"common": "C", "uncommon": "U", "rare": "R",
               "legendary": "L", "mythic": "M", "starter": "S"}
RARITY_COLOR = {"C": DIM, "U": GREEN, "R": BLUE, "L": YELLOW, "M": MAGENTA, "S": CYAN}
PARTY_SORT_FIELDS = ("rarity", "name", "dex", "caught")
PARTY_SORT_LABEL = {
    "active": "active first",
    "rarity": "rarity",
    "name": "name",
    "dex": "dex #",
    "caught": "date caught",
}
BOX_SORT_FIELDS = PARTY_SORT_FIELDS
BOX_SORT_LABEL = PARTY_SORT_LABEL
PARTY_RARITY_ORDER = {
    "common": 0,
    "uncommon": 1,
    "rare": 2,
    "legendary": 3,
    "mythic": 4,
    "starter": 5,
}
DEX_SORT_FIELDS = ("dex", "name", "rarity", "caught")
DEX_SORT_LABEL = {
    "dex": "dex #",
    "name": "name",
    "rarity": "rarity",
}
DEX_FILTER_MODES = ("all", "caught", "missing")
DEX_FILTER_LABEL = {
    "all": "all species",
    "caught": "caught",
    "missing": "missing",
}
SEARCH_HINT = "/ search"

# Two-column screens (list left, sprite right) fall back to the old stacked
# layout below this terminal width. Left columns are fixed-width so the sprite
# panel keeps a constant left margin and nothing jumps while scrolling.
TWO_COL_MIN_WIDTH = 56
PARTY_LIST_W = 26  # +1 vs the old 25 for the favorite (♥) marker slot
DEX_LIST_W = 28
BOX_LIST_W = 32  # party row + favorite slot + a copy "n/m" slot
DEX_CHROME = 8  # header (6 lines) + blank + footer; rows shown = height - DEX_CHROME

# Inline-image rendering (Ghostty/iTerm2/kitty). When active, sprite "lines" are
# invisible markers that _draw replaces with real PNGs placed over the reserved
# cells; otherwise the same calls return half-block art. Set in run().
_GRAPHICS = False
_frame_images = []  # per-frame [(png_bytes, cols, rows)]; marker carries the index
_IMG_RE = re.compile("\x01IMG(\\d+)\x02")
_CELL_PX = None  # (width, height) of one terminal cell in pixels, queried at startup
_FALLBACK_BOX_PX = 768  # if the cell size is unknown, render big enough to force downscaling
PREVIEW_TARGET_PX = 210  # on-screen sprite height; letterboxed, never stretched
MIN_IMAGE_COLS = 6  # keep inline-image marker text narrower than its reserved cell

MENU = [
    ("Party", "party"),
    ("Pokédex", "dex"),
    ("Journal", "journal"),
    ("Status", "status"),
    ("Box", "box"),
    ("Showcase", "showcase"),
    ("Token Usage", "tokens"),
    ("Settings", "settings"),
    ("Quit", "quit"),
]
MENU_ICON = {
    "party": "👫",
    "dex": "📖",
    "journal": "📜",
    "status": "📊",
    "box": "📦",
    "showcase": "🏆",
    "tokens": "🪙",
    "settings": "🔧",
    "quit": "🚪",
    "encounter": "⚔️",
}
MENU_HINT = {
    "party": "team and active buddy",
    "dex": "species seen and caught",
    "journal": "recent journey log",
    "status": "progress and streaks",
    "box": "all catches",
    "showcase": "curated podium display",
    "tokens": "daily local usage",
    "settings": "preferences",
    "quit": "leave the menu",
    "encounter": "wild encounter waiting",
}
SETTINGS_CYCLES = {
    "mode": st.VALID_MODES,
    "notifications": st.PREFERENCE_VALUES["notifications"],
    "menu_launcher": st.PREFERENCE_VALUES["menu_launcher"],
    "terminal_graphics": st.PREFERENCE_VALUES["terminal_graphics"],
    "menu_replace": st.PREFERENCE_VALUES["menu_replace"],
    "share_reveal": st.PREFERENCE_VALUES["share_reveal"],
    "share_banner": st.PREFERENCE_VALUES["share_banner"],
}
SETTINGS_LABEL = {
    "mode": "Encounter mode",
    "notifications": "Notifications",
    "menu_launcher": "Menu launcher",
    "menu_replace": "Replace menus",
    "share_reveal": "Reveal shares",
    "share_banner": "Share banners",
    "terminal_graphics": "Terminal graphics",
    "terminal_support": "Terminal support",
}
SETTINGS_HELP = {
    "notifications": "rare-event banners",
    "menu_launcher": "menu app preference",
    "menu_replace": "close prior BuddyMon Ghostty menu",
    "share_reveal": "open Finder after export",
    "share_banner": "show share result banner",
    "terminal_graphics": "inline image preference",
    "terminal_support": "current terminal support",
}
ENCOUNTER_MODE_HELP = {
    "auto": "common quick · rare Safari",
    "safari": "every wild: rock · bait · ball",
    "battle": "every wild: fight · ball · run",
}
SETTINGS_VALUE_LABELS = {
    "mode": {
        "auto": "Quick",
        "safari": "Safari",
        "battle": "Battle",
    },
    "notifications": {
        "on": "On",
        "silent": "Silent",
        "off": "Off",
    },
    "menu_launcher": {
        "auto": "Auto",
        "ghostty": "Ghostty",
        "iterm": "iTerm2",
        "terminal": "Terminal.app",
    },
    "terminal_graphics": {
        "auto": "Auto",
        "off": "Off",
    },
    "menu_replace": {
        "on": "On",
        "off": "Off",
    },
    "share_reveal": {
        "on": "On",
        "off": "Off",
    },
    "share_banner": {
        "on": "On",
        "off": "Off",
    },
    "terminal_support": {
        "inline PNGs": "inline PNGs",
        "text fallback": "text fallback",
        "off by env": "off by env",
        "off": "off",
    },
}

# Action options per encounter kind: (label shown, action verb passed to take_turn)
ENCOUNTER_OPTIONS = {
    "safari": [("Rock", "rock"), ("Bait", "bait"), ("Ball", "ball"), ("Run", "run")],
    "battle": [("Fight", "attack"), ("Ball", "ball"), ("Run", "run")],
}
RESULT_FLASH_SECS = 0.8


def _encounter_kind(s):
    if s.get("pending_encounter"):
        return "safari"
    if s.get("pending_battle"):
        return "battle"
    return None


def _menu_items(s):
    """Static menu, with a 'fight' entry prepended when a wild is waiting."""
    items = list(MENU)
    kind = _encounter_kind(s)
    if kind:
        name = (s.get("pending_encounter") or s.get("pending_battle"))["name"]
        items.insert(0, (f"Fight wild {name}!", "encounter"))
    return items


# ── pure frame builders (testable) ───────────────────────────────────────────

def _header(title):
    return f"{BOLD}{CYAN}buddymon{RESET} {DIM}·{RESET} {title}"


def _footer(hint):
    return f"{DIM}{hint}{RESET}"


def _visible_width(line):
    return len(ANSI_RE.sub("", line))


def _pad_ansi(line, width):
    return line + " " * max(0, width - _visible_width(line))


def _center_ansi(line, width):
    visible = _visible_width(line)
    if visible >= width:
        return _fit_ansi(line, width)
    left = (width - visible) // 2
    right = width - visible - left
    return (" " * left) + line + (" " * right)


def _fit_ansi(line, width):
    if _visible_width(line) <= width:
        return line
    out = []
    visible = 0
    i = 0
    while i < len(line) and visible < width:
        if line[i] == "\x1b":
            match = ANSI_RE.match(line, i)
            if match:
                out.append(match.group(0))
                i = match.end()
                continue
        out.append(line[i])
        visible += 1
        i += 1
    fitted = "".join(out)
    return fitted + (RESET if "\x1b[" in fitted else "")


def _marker_col(line, marker_start):
    """Terminal column for an image marker. String indexes include invisible
    ANSI color escapes; terminal placement needs visible cells before marker.
    Earlier markers on the same row reserve blank cells, so keep their width."""
    prefix = _IMG_RE.sub(lambda m: " " * len(m.group(0)), line[:marker_start])
    return _visible_width(prefix) + 1


def _pair_line(left, right, width=31):
    return "  " + _pad_ansi(_fit_ansi(left, width), width) + "   " + right


def _rarity_code(rarity):
    """One colored letter (C/U/R/L/S/M) — fixed-width replacement for the rarity
    word, so list rows never change length as rarities vary."""
    code = RARITY_CODE.get(rarity, "?")
    return f"{RARITY_COLOR.get(code, '')}{code}{RESET}"


def _rarity_label(rarity):
    code = RARITY_CODE.get(rarity, "?")
    color = RARITY_COLOR.get(code, "")
    return f"{color}{rarity}{RESET}" if color else rarity


def _party_sort_label(sort_key, descending):
    label = PARTY_SORT_LABEL.get(sort_key, sort_key)
    if sort_key == "active":
        return label
    return f"{label} {'desc' if descending else 'asc'}"


def _next_party_sort(sort_key):
    if sort_key not in PARTY_SORT_FIELDS:
        return PARTY_SORT_FIELDS[0]
    return PARTY_SORT_FIELDS[(PARTY_SORT_FIELDS.index(sort_key) + 1) % len(PARTY_SORT_FIELDS)]


def _box_sort_label(sort_key, descending):
    label = BOX_SORT_LABEL.get(sort_key, sort_key)
    return f"{label} {'desc' if descending else 'asc'}"


def _next_box_sort(sort_key):
    if sort_key not in BOX_SORT_FIELDS:
        return BOX_SORT_FIELDS[0]
    return BOX_SORT_FIELDS[(BOX_SORT_FIELDS.index(sort_key) + 1) % len(BOX_SORT_FIELDS)]


def _dex_sort_label(sort_key, descending):
    if sort_key == "caught":
        return "caught first" if descending else "missing first"
    label = DEX_SORT_LABEL.get(sort_key, sort_key)
    return f"{label} {'desc' if descending else 'asc'}"


def _next_dex_sort(sort_key):
    if sort_key not in DEX_SORT_FIELDS:
        return DEX_SORT_FIELDS[0]
    return DEX_SORT_FIELDS[(DEX_SORT_FIELDS.index(sort_key) + 1) % len(DEX_SORT_FIELDS)]


def _next_dex_filter(filter_mode):
    if filter_mode not in DEX_FILTER_MODES:
        return DEX_FILTER_MODES[0]
    return DEX_FILTER_MODES[(DEX_FILTER_MODES.index(filter_mode) + 1) % len(DEX_FILTER_MODES)]


def _query_terms(query):
    return [term.casefold() for term in str(query or "").split() if term]


def _query_matches(query, *values):
    terms = _query_terms(query)
    if not terms:
        return True
    haystack = " ".join(str(value or "") for value in values).casefold()
    return all(term in haystack for term in terms)


def _pokemon_query_values(pokemon):
    values = [
        pokemon.get("name"),
        pokemon.get("type"),
        pokemon.get("rarity"),
        f"Lv.{pokemon.get('level')}" if pokemon.get("level") else "",
    ]
    if pokemon.get("name") in data.DEX_NUMBERS:
        number = data.DEX_NUMBERS[pokemon["name"]]
        values += [str(number), f"#{number:03d}", f"{number:03d}"]
    if pokemon.get("shiny"):
        values.append("shiny")
    if pokemon.get("favorite"):
        values.append("favorite")
    return values


def _filter_pokemon_query(mons, query):
    return [p for p in mons if _query_matches(query, *_pokemon_query_values(p))]


def _dex_query_values(entry):
    values = [
        entry.get("name"),
        entry.get("type"),
        entry.get("rarity"),
        "caught" if entry.get("caught") else "missing",
        str(entry.get("dex_no") or entry.get("idx") or ""),
        f"#{entry.get('dex_no', 0):03d}" if entry.get("dex_no") else "",
    ]
    pokemon = entry.get("pokemon")
    if pokemon:
        values += _pokemon_query_values(pokemon)
    return values


def _filter_dex_query(entries, query):
    return [e for e in entries if _query_matches(query, *_dex_query_values(e))]


def _journal_query_values(entry):
    return [
        entry.get("text"),
        entry.get("kind"),
        entry.get("name"),
        entry.get("rarity"),
        "shiny" if entry.get("shiny") else "",
    ]


def _filter_journal_query(entries, query):
    return [e for e in entries if _query_matches(query, *_journal_query_values(e))]


def _search_status(query, active=False):
    if query or active:
        cursor = "▌" if active else ""
        return f"search: {query}{cursor}"
    return SEARCH_HINT


def _search_hint(base_hint, query="", active=False):
    if active:
        return "type search · backspace edit · enter done · esc clear"
    if query:
        return f"{base_hint} · / edit search"
    return f"{base_hint} · {SEARCH_HINT}"


def _search_key(key, query, active):
    """Update transient search input. Returns (query, active, handled)."""
    if active:
        if key == "enter":
            return query, False, True
        if key == "esc":
            return "", False, True
        if key in ("\x7f", "\b", "delete"):
            return query[:-1], True, True
        if key == "space":
            return query + " ", True, True
        if len(key) == 1 and key.isprintable():
            return query + key, True, True
        return query, True, True
    if key == "/":
        return query, True, True
    if key == "esc" and query:
        return "", False, True
    return query, active, False


def _two_col(left_lines, right_lines, width):
    """Compose two columns line-by-line, padding the shorter to equal height. The
    left column is fixed-width (so the right sprite keeps a constant margin); the
    right side is appended raw, so image markers and color codes pass through."""
    height = max(len(left_lines), len(right_lines))
    left = list(left_lines) + [""] * (height - len(left_lines))
    right = list(right_lines) + [""] * (height - len(right_lines))
    return [
        _pair_line(left_line, right_line, width=width)
        for left_line, right_line in zip(left, right)
    ]


def _detail_two_col_min_width(left_width):
    return 2 + left_width + 3 + SELECT_CARD_INNER_W + 4


def _pokemon_title(pokemon, with_level=False):
    shiny = "✨" if pokemon.get("shiny") else ""
    level = f" Lv.{pokemon.get('level')}" if with_level and pokemon.get("level") else ""
    return f"{shiny}{pokemon.get('emoji', '•')} {pokemon['name']}{level}"


def _encounter_title(pokemon, with_level=False):
    shiny = "shiny " if pokemon.get("shiny") else ""
    value = pokemon.get("level") or pokemon.get("wild_level")
    level = f" Lv.{value}" if with_level and value else ""
    return f"{shiny}{pokemon['name']}{level}"


def _pokemon_meta(pokemon):
    return " · ".join(x for x in (
        pokemon.get("type"),
        pokemon.get("rarity"),
    ) if x)


def _bar(frac, width=16):
    frac = max(0.0, min(1.0, frac))
    filled = round(frac * width)
    return f"{GREEN}{'▰' * filled}{RESET}{DIM}{'▱' * (width - filled)}{RESET} {int(frac * 100)}%"


def _image_geometry(src_w, src_h, max_cols, max_rows):
    """Pick the sprite's on-screen size in (cols, rows, png_w, png_h). When the
    cell size is known we size it to PREVIEW_TARGET_PX tall and build a PNG that
    exactly matches the cell box, so the terminal resamples 0% — pixel-crisp,
    no blur. Without the cell size we fall back to filling the box from a
    deliberately oversized PNG (downscaling stays sharper than upscaling)."""
    if _CELL_PX:
        cw, ch = _CELL_PX
        box_h = min(max_rows * ch, PREVIEW_TARGET_PX)
        rows = max(1, round(box_h / ch))
        box_h = rows * ch
        cols = max(MIN_IMAGE_COLS, min(max_cols, round(box_h * src_w / src_h / cw)))
        return cols, rows, cols * cw, rows * ch
    cols = min(max_cols, max(MIN_IMAGE_COLS, round(2 * max_rows * src_w / src_h)))
    scale = max(2, -(-_FALLBACK_BOX_PX // max(src_w, src_h)))
    return cols, max_rows, src_w * scale, src_h * scale


def _pad_grid_center(grid, w, h, x_bias=0):
    """Center a char grid inside a w x h canvas, padding with transparent '.'
    (any char absent from the palette renders transparent in grid_to_png)."""
    cur_h = len(grid)
    cur_w = len(grid[0]) if grid else 0
    left = max(0, (w - cur_w) // 2 + x_bias)
    left = min(max(0, w - cur_w), left)
    top = max(0, (h - cur_h) // 2)
    blank = "." * w
    out = [blank] * h
    for i, row in enumerate(grid[:h]):
        seg = row[:w]
        out[top + i] = ("." * left + seg).ljust(w, ".")[:w]
    return out


def _pad_grid_alpha_center(grid, palette, w, h):
    """Center visible sprite bounds inside a fixed transparent grid."""
    xs = [
        x
        for row in grid
        for x, ch in enumerate(row)
        if ch in palette
    ]
    if not xs:
        return _pad_grid_center(grid, w, h)
    bounds_center = (min(xs) + max(xs)) / 2
    target = (w - 1) / 2
    left = round(target - bounds_center)
    left = max(0, min(max(0, w - (len(grid[0]) if grid else 0)), left))
    top = max(0, (h - len(grid)) // 2)
    blank = "." * w
    out = [blank] * h
    for i, row in enumerate(grid[:h]):
        target_row = top + i
        if target_row >= h:
            break
        seg = row[:w]
        out[target_row] = ("." * left + seg).ljust(w, ".")[:w]
    return out


def _image_block(grid, palette, max_cols, max_rows):
    """Register a sprite as a real PNG and return marker lines that _draw turns
    into an inline image. The sprite is *letterboxed* — scaled to fit its cell
    box preserving aspect, then padded transparent — so the terminal never
    stretches it, however large the box gets."""
    src_h, src_w = len(grid), len(grid[0])
    cols, rows, png_w, png_h = _image_geometry(src_w, src_h, max_cols, max_rows)
    if not _CELL_PX:
        # fallback: oversized aspect-correct PNG; the terminal downscales it
        png_bytes = png.grid_to_png(grid, palette, max(1, png_w // src_w))
    else:
        scale = min(png_w / src_w, png_h / src_h)
        fit_w = max(1, round(src_w * scale))
        fit_h = max(1, round(src_h * scale))
        art = grid if (fit_w, fit_h) == (src_w, src_h) else pixels.nearest(grid, fit_w, fit_h)
        png_bytes = png.grid_to_png(_pad_grid_center(art, png_w, png_h), palette, 1)
    idx = len(_frame_images)
    _frame_images.append((png_bytes, cols, rows))
    token = "\x01IMG%d\x02" % idx
    blank = " " * cols
    return [token.ljust(cols)] + [blank] * (rows - 1)


def _fixed_image_block(grid, palette, cols, rows, max_sprite_cols=None,
                       max_sprite_rows=None):
    """Register a sprite centered inside an exact terminal-cell image box."""
    src_h, src_w = len(grid), len(grid[0])
    if _CELL_PX:
        cw, ch = _CELL_PX
        png_w, png_h = cols * cw, rows * ch
        max_sprite_w = (max_sprite_cols or cols) * cw
        max_sprite_h = (max_sprite_rows or rows) * ch
    else:
        scale = max(2, -(-_FALLBACK_BOX_PX // max(src_w, src_h)))
        png_w, png_h = cols * scale, rows * scale * 2
        max_sprite_w = (max_sprite_cols or cols) * scale
        max_sprite_h = (max_sprite_rows or rows) * scale * 2
    scale = min(max_sprite_w / src_w, max_sprite_h / src_h)
    fit_w = max(1, round(src_w * scale))
    fit_h = max(1, round(src_h * scale))
    art = grid if (fit_w, fit_h) == (src_w, src_h) else pixels.nearest(grid, fit_w, fit_h)
    png_bytes = png.grid_to_png(_pad_grid_alpha_center(art, palette, png_w, png_h), palette, 1)
    idx = len(_frame_images)
    _frame_images.append((png_bytes, cols, rows))
    token = "\x01IMG%d\x02" % idx
    blank = " " * cols
    return [token.ljust(cols)] + [blank] * (rows - 1)


def _crop_grid_to_content(grid, palette):
    """Remove transparent source padding before centering a sprite in UI boxes."""
    xs, ys = [], []
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch in palette:
                xs.append(x)
                ys.append(y)
    if not xs or not ys:
        return grid
    left, right = min(xs), max(xs) + 1
    top, bottom = min(ys), max(ys) + 1
    return [row[left:right] for row in grid[top:bottom]]


def _sprite_card_geometry(max_h):
    requested_h = max_h if max_h % 2 == 0 else max_h + 1
    requested_rows = max(1, requested_h // 2)
    inner_rows = max(4, min(SELECT_CARD_INNER_ROWS, requested_rows))
    sprite_rows = max(1, min(SELECT_POKEMON_MAX_ROWS,
                             max(1, inner_rows // SELECT_CARD_HEIGHT_FACTOR)))
    return SELECT_CARD_INNER_W, inner_rows, SELECT_POKEMON_MAX_COLS, sprite_rows


def _sprite_card_body(art, art_w, art_rows, inner_w, inner_rows):
    blank = " " * inner_w
    left = max(0, (inner_w - art_w) // 2)
    top = max(0, (inner_rows - art_rows) // 2)
    body = [blank for _ in range(inner_rows)]
    for i, line in enumerate(art[:inner_rows]):
        row = top + i
        if row >= inner_rows:
            break
        segment = _pad_ansi(_fit_ansi(line, art_w), art_w)
        right = max(0, inner_w - left - _visible_width(segment))
        body[row] = " " * left + segment + " " * right
    return body


def _sprite_card_body_at(art, art_w, art_rows, inner_w, inner_rows, left):
    blank = " " * inner_w
    top = max(0, (inner_rows - art_rows) // 2)
    left = max(0, min(max(0, inner_w - art_w), left))
    body = [blank for _ in range(inner_rows)]
    for i, line in enumerate(art[:inner_rows]):
        row = top + i
        if row >= inner_rows:
            break
        segment = _pad_ansi(_fit_ansi(line, art_w), art_w)
        right = max(0, inner_w - left - _visible_width(segment))
        body[row] = " " * left + segment + " " * right
    return body


def _sprite_lines(pokemon, max_h=SELECT_ART_H, silhouette=False):
    """Preview art for party/dex/status. Uses the detailed Gen 5 source (same
    art the menu bar renders). On Ghostty/iTerm2/kitty it renders as a real PNG;
    on plain terminals it area-averages down to half blocks, so species stay
    distinct instead of collapsing into a ~16px blob. max_h lets crowded
    screens trade preview height for more list rows. silhouette recolors every
    pixel to one shade (transparency preserved) for the classic uncaught-dex
    shadow — works for both the PNG and the half-block path."""
    grid, palette = packs.gen5_frames(
        pokemon["name"], pokemon.get("type", "Normal"), pokemon.get("shiny"))[0]
    if silhouette:
        palette = {ch: render.DEX_UNKNOWN_COLOR for ch in palette}
    if _GRAPHICS:
        return _image_block(grid, palette, SELECT_ART_W, max_h // 2)
    return pixels.render_scaled(grid, palette, SELECT_ART_W, max_h)


def _sprite_card_lines(pokemon, max_h=SELECT_ART_H):
    """Framed preview for selected Pokemon detail panels. Keep the frame ASCII
    and ANSI-free so inline image markers still resolve to the correct columns."""
    grid, palette = packs.gen5_frames(
        pokemon["name"], pokemon.get("type", "Normal"), pokemon.get("shiny"))[0]
    grid = _crop_grid_to_content(grid, palette)
    inner_w, inner_rows, sprite_w, sprite_rows = _sprite_card_geometry(max_h)
    if _GRAPHICS:
        img_idx = len(_frame_images)
        art = _image_block(grid, palette, sprite_w, sprite_rows)
        _, art_w, art_rows = _frame_images[img_idx]
    else:
        art = pixels.render_scaled(grid, palette, sprite_w, sprite_rows * 2)
        art_w = max((_visible_width(line) for line in art), default=0)
        art_rows = len(art)
    body = _sprite_card_body(art, art_w, art_rows, inner_w, inner_rows)
    edge = "+" + "-" * (inner_w + 2) + "+"
    return [edge, *[f"| {line} |" for line in body], edge]


def _detail_card_line(text, inner_w):
    return f"| {_pad_ansi(_fit_ansi(text, inner_w), inner_w)} |"


def _detail_card_divider(title, inner_w):
    total_w = inner_w + 4
    prefix = "+-- "
    available = max(1, total_w - _visible_width(prefix) - 1)
    label = _fit_ansi(f"{title} ", available)
    dashes = "-" * max(0, total_w - _visible_width(prefix) - _visible_width(label) - 1)
    return f"{prefix}{label}{dashes}+"


def _dex_label(name):
    try:
        return f"#{render.dex_number(name):03d}"
    except KeyError:
        return "#???"


def _detail_title(pokemon):
    shiny = "shiny " if pokemon.get("shiny") else ""
    level = f" Lv.{pokemon.get('level')}" if pokemon.get("level") else ""
    return f"{shiny}{pokemon['name']}{level}"


def _pokemon_detail_card_lines(pokemon, active_id, art_h=SELECT_ART_H, caught_line=None):
    """Full right-side Party/Box detail card: centered sprite plus attached
    metadata. The card owns the border so details do not float below the art."""
    grid, palette = packs.gen5_frames(
        pokemon["name"], pokemon.get("type", "Normal"), pokemon.get("shiny"))[0]
    grid = _crop_grid_to_content(grid, palette)
    inner_w, inner_rows, sprite_w, sprite_rows = _sprite_card_geometry(art_h)
    if _GRAPHICS:
        img_idx = len(_frame_images)
        art = _image_block(grid, palette, sprite_w, sprite_rows)
        _, art_w, art_rows = _frame_images[img_idx]
    else:
        art = pixels.render_scaled(grid, palette, sprite_w, sprite_rows * 2)
        art_w = max((_visible_width(line) for line in art), default=0)
        art_rows = len(art)

    body = _sprite_card_body(art, art_w, art_rows, inner_w, inner_rows)
    edge = "+" + "-" * (inner_w + 2) + "+"
    meta = " · ".join(x for x in (
        _dex_label(pokemon["name"]),
        pokemon.get("type"),
        _rarity_label(pokemon.get("rarity", "?")),
        render.gender_symbol(pokemon),
    ) if x)
    lines = [
        edge,
        *[f"| {line} |" for line in body],
        _detail_card_divider(_detail_title(pokemon), inner_w),
        _detail_card_line(meta, inner_w),
    ]
    if caught_line:
        lines.append(_detail_card_line(f"{DIM}{caught_line}{RESET}", inner_w))
    lines += [
        _detail_card_line(f"XP {CYAN}{render.xp_bar(pokemon, 16)}{RESET}", inner_w),
        edge,
    ]
    return lines


def _detail_action_line(pokemon, active_id):
    return (f"{GREEN}active buddy{RESET}" if pokemon["id"] == active_id
            else "press enter to make active")


def _sprite_card_content_offset(lines):
    """Test helper: visible content bbox inside a framed sprite card."""
    rows = []
    for line in lines[1:-1]:
        plain = ANSI_RE.sub("", line)
        rows.append(plain[2:-2] if plain.startswith("| ") and plain.endswith(" |") else plain)
    xs = [x for row in rows for x, ch in enumerate(row) if ch.strip()]
    ys = [y for y, row in enumerate(rows) for ch in row if ch.strip()]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def _encounter_sprite_lines(pokemon):
    grid, palette = packs.gen5_frames(
        pokemon["name"], pokemon.get("type", "Normal"), pokemon.get("shiny"))[0]
    if _GRAPHICS:
        return _image_block(grid, palette, ENCOUNTER_ART_W, ENCOUNTER_ART_H // 2)
    return pixels.render_scaled(grid, palette, ENCOUNTER_ART_W, ENCOUNTER_ART_H,
                                pad_to=(ENCOUNTER_ART_W, ENCOUNTER_ART_H))


def _paired_encounter_sprite_lines(left_pokemon, right_pokemon, width=31):
    left = _encounter_sprite_lines(left_pokemon)
    right = _encounter_sprite_lines(right_pokemon)
    return [
        _pair_line(left_line, right_line, width=width)
        for left_line, right_line in zip(left, right)
    ]


def _menu_frame(items, selected):
    name_w = max(12, max(_visible_width(label) for label, _ in items))
    hint_w = max(18, max(_visible_width(MENU_HINT.get(action, "")) for _, action in items))
    inner_w = 3 + 2 + name_w + 3 + hint_w
    lines = [
        "",
        _header("main menu"),
        f"{DIM}┌{'─' * (inner_w + 2)}┐{RESET}",
    ]
    for i, (label, action) in enumerate(items):
        selected_row = i == selected
        cursor = f"{GREEN}▶{RESET}" if selected_row else " "
        icon = MENU_ICON.get(action, "•")
        hint = MENU_HINT.get(action, "")
        name = _pad_ansi(label, name_w)
        hint_text = _pad_ansi(f"{DIM}{hint}{RESET}", hint_w)
        row = f"{cursor} {icon}  {name}   {hint_text}"
        if selected_row:
            row = f"{BOLD}{row}{RESET}"
        lines.append(f"{DIM}│{RESET} {row} {DIM}│{RESET}")
    lines += [
        f"{DIM}└{'─' * (inner_w + 2)}┘{RESET}",
        _footer("↑/↓ move · ⏎ select · q quit"),
    ]
    return "\n".join(lines)


def _encounter_frame(s, kind, sel):
    """Terminal battle view: compact sprites, status, and the action row."""
    _frame_images.clear()
    pending = s.get("pending_encounter") if kind == "safari" else s.get("pending_battle")
    buddy = st.active_pokemon(s)
    lines = ["", _header(f"wild {pending['name']}"), ""]
    lines.append(_pair_line(f"{BOLD}Active Buddy{RESET}", f"{BOLD}Wild Encounter{RESET}"))
    lines.append(_pair_line(
        _encounter_title(buddy, with_level=True),
        _encounter_title(pending, with_level=True),
    ))
    lines.append(_pair_line(_pokemon_meta(buddy), _pokemon_meta(pending)))
    lines.extend(_paired_encounter_sprite_lines(buddy, pending))
    if kind == "battle":
        lines.append(_pair_line(f"HP {_bar(bt.buddy_hp_frac(pending))}",
                                f"HP {_bar(bt.wild_hp_frac(pending))}"))
    lines.append("")
    if kind == "safari":
        lines.append(f"  {sf.status_text(pending)}")
        lines.append(f"  {DIM}{sf.odds_hint(pending)}{RESET}")
    else:
        lines.append(f"  {bt.status_text(pending)}")
        lines.append(f"  {DIM}catch ~{round(bt.catch_probability(pending) * 100)}%  ·  ⚾ ∞{RESET}")
    lines.append(f"  {pending['last_msg']}")
    lines.append("")
    opts = ENCOUNTER_OPTIONS[kind]
    cells = [f"{GREEN}▶{label}{RESET}" if i == sel else f"  {label} "
             for i, (label, _) in enumerate(opts)]
    lines.append("  " + "    ".join(cells))
    lines += ["", _footer("←/→ choose · ⏎/e act · esc leave")]
    return "\n".join(lines)


def _flash_result(msg, timeout=RESULT_FLASH_SECS):
    """Show a finished encounter briefly, without requiring an extra keypress."""
    _draw("\n".join(["", _header("encounter over"), "",
                     f"  {msg}", "", _footer("returning…")]))
    if select.select([0], [], [], timeout)[0]:
        _read_key()  # absorb one impatient dismiss key without acting on it


def _fav_mark(p):
    """One-cell favorite marker: ♥ when starred, else blank."""
    return f"{MAGENTA}♥{RESET}" if p.get("favorite") else " "


def _list_name(p, width=12):
    name = p["name"][:width]
    if p.get("shiny"):
        name = p["name"][:max(0, width - 1)] + f"{YELLOW}*{RESET}"
    return _pad_ansi(name, width)


def _party_row(p, selected, active_id):
    """One fixed-width party row (no per-row emoji — the preview is the art)."""
    cursor = f"{GREEN}▶{RESET}" if selected else " "
    tag = f" {GREEN}●{RESET}" if p["id"] == active_id else "  "
    return (f"{cursor} {_fav_mark(p)} {_list_name(p)} Lv.{p['level']:<2} "
            f"{_rarity_code(p['rarity'])}{tag}")


def _party_divider():
    label = "─ the rest "
    return f"{DIM}{label}{'─' * max(0, PARTY_LIST_W - len(label))}{RESET}"


def _party_header_row():
    return f"{DIM}    {'Name':<12} Lv    R{RESET}"


def _party_frame(s, selected, top=0, list_height=None, art_h=SELECT_ART_H, width=80,
                 sort_key="name", descending=False, fav_only=False,
                 query="", search_active=False):
    _frame_images.clear()
    pinned, rest = _party_split(s, sort_key, descending)
    mons = pinned + rest
    boundary = len(pinned) if (pinned and rest) else None  # divider position
    if fav_only:
        mons = [p for p in mons if p.get("favorite")]
        boundary = None
    if query:
        mons = _filter_pokemon_query(mons, query)
        boundary = None
    selected = max(0, min(selected, len(mons) - 1)) if mons else 0
    active = s.get("active")
    scope = (f"{MAGENTA}♥ favorites{RESET}" if fav_only
             else f"team pinned · rest by {_party_sort_label(sort_key, descending)}")
    lines = ["", _header("party"),
             _fit_ansi(f"  {DIM}{scope} · {_search_status(query, search_active)}{RESET}", width),
             ""]
    if not mons:
        msg = (f"No Pokemon match '{query}'."
               if query else "No favorites yet — press f to ♥ one, or browse the Box."
               if fav_only else "No Pokemon to show.")
        lines += [f"  {DIM}{msg}{RESET}",
                  "", _fit_ansi(_footer(_search_hint("F all · ⏎ active · esc back",
                                                     query, search_active)), width)]
        return "\n".join(lines)
    if list_height is None:
        visible = list(enumerate(mons))
    else:
        top = max(0, min(top, max(0, len(mons) - list_height)))
        visible = list(enumerate(mons[top:top + list_height], start=top))
        if len(mons) > list_height:
            lines.append(f"  {DIM}showing {top + 1}-{top + len(visible)} of {len(mons)}{RESET}")
    rows = [_party_header_row()]
    for i, p in visible:
        if boundary is not None and i == boundary and top < boundary:
            rows.append(_party_divider())  # between your pinned team and the rest
        rows.append(_party_row(p, i == selected, active))
    panel = []
    if mons:
        p = mons[selected]
        panel = [*_pokemon_detail_card_lines(p, active, art_h), _detail_action_line(p, active)]
    if width >= _detail_two_col_min_width(PARTY_LIST_W):
        lines += _two_col(rows, panel, PARTY_LIST_W)
    else:  # narrow terminal: stack the list and the preview
        lines += ["  " + r for r in rows]
        if panel:
            lines += [""] + ["  " + r for r in panel]
    lines += ["", _fit_ansi(
        _footer(_search_hint("↑/↓ move · PgUp/PgDn · s sort · r reverse · ⏎ active · esc back",
                             query, search_active)),
        width,
    )]
    return "\n".join(lines)


def _box_row(p, selected, active_id):
    """One fixed-width box row: a single caught individual, with an n/m copy slot
    so duplicates of the same species are distinguishable in the list."""
    cursor = f"{GREEN}▶{RESET}" if selected else " "
    tag = f" {GREEN}●{RESET}" if p["id"] == active_id else "  "
    copy = (f"{p.get('copy_index', 1)}/{p.get('copy_total', 1)}"
            if p.get("copy_total", 1) > 1 else "")
    return (f"{cursor} {_fav_mark(p)} {_list_name(p)} Lv.{p['level']:<2} "
            f"{_rarity_code(p['rarity'])} {copy:>5}{tag}")


def _box_header_row():
    return f"{DIM}    {'Name':<12} Lv    R Copy{RESET}"


def _box_frame(s, selected, top=0, list_height=None, art_h=SELECT_ART_H, width=80,
               sort_key="name", descending=False, fav_only=False,
               query="", search_active=False):
    """Box browser: every caught individual (no per-species collapse), with a
    detail panel for the selected copy. Mirrors the two-column party layout."""
    import time
    _frame_images.clear()
    caught = s.get("pokemon", [])
    mons = _box(s, sort_key, descending, fav_only=fav_only)
    if query:
        mons = _filter_pokemon_query(mons, query)
    active = s.get("active")
    selected = max(0, min(selected, len(mons) - 1)) if mons else 0
    species = len(box.group_by_species(caught))
    if fav_only:
        scope = f"{MAGENTA}♥ favorites{RESET}"
    else:
        scope = (
            f"{box.total_copies(caught)} caught · {species} species · "
            f"by {_box_sort_label(sort_key, descending)}"
        )
    status = f"  {DIM}{scope} · {_search_status(query, search_active)}{RESET}"
    lines = ["", _header("box"),
             _fit_ansi(status, width),
             ""]
    if not mons:
        msg = (f"No Pokemon match '{query}'."
               if query else "No favorites yet — press f to ♥ one.")
        lines += [f"  {DIM}{msg}{RESET}",
                  "", _fit_ansi(
                      _footer(_search_hint("F all · s sort · r reverse · ⏎ active · esc back",
                                           query, search_active)),
                      width,
                  )]
        return "\n".join(lines)
    if list_height is None:
        visible = list(enumerate(mons))
    else:
        top = max(0, min(top, max(0, len(mons) - list_height)))
        visible = list(enumerate(mons[top:top + list_height], start=top))
        if len(mons) > list_height:
            lines.append(f"  {DIM}showing {top + 1}-{top + len(visible)} of {len(mons)}{RESET}")
    rows = [_box_header_row(), *[_box_row(p, i == selected, active) for i, p in visible]]
    panel = []
    if mons:
        p = mons[selected]
        when = (time.strftime("%b %d, %Y", time.localtime(p["caught_at"]))
                if p.get("caught_at") else "—")
        copy = (f" · copy {p['copy_index']}/{p['copy_total']}"
                if p.get("copy_total", 1) > 1 else "")
        panel = [*_pokemon_detail_card_lines(p, active, art_h, f"caught {when}{copy}"),
                 _detail_action_line(p, active)]
    if width >= _detail_two_col_min_width(BOX_LIST_W):
        lines += _two_col(rows, panel, BOX_LIST_W)
    else:  # narrow terminal: stack the list and the preview
        lines += ["  " + r for r in rows]
        if panel:
            lines += [""] + ["  " + r for r in panel]
    lines += ["", _fit_ansi(
        _footer(_search_hint("↑/↓ move · PgUp/PgDn · s sort · r reverse · ⏎ active · esc back",
                             query, search_active)),
        width,
    )]
    return "\n".join(lines)


def _showcase_card_art(pokemon):
    grid, palette = packs.gen5_frames(
        pokemon["name"], pokemon.get("type", "Normal"), pokemon.get("shiny"))[0]
    grid = _crop_grid_to_content(grid, palette)
    if _GRAPHICS:
        img_idx = len(_frame_images)
        art = _fixed_image_block(
            grid,
            palette,
            SHOWCASE_ART_W,
            SHOWCASE_CARD_BODY_ROWS,
            SHOWCASE_SPRITE_W,
            SHOWCASE_SPRITE_ROWS,
        )
        _, art_w, art_rows = _frame_images[img_idx]
        x_offset = 0
    else:
        art = pixels.render_scaled(
            grid,
            palette,
            SHOWCASE_SPRITE_W,
            SHOWCASE_SPRITE_ROWS * 2,
        )
        art_w = max((_visible_width(line) for line in art), default=0)
        art_rows = len(art)
        x_offset = 0
    left = (SHOWCASE_CARD_INNER_W - art_w) // 2 + x_offset
    return _sprite_card_body_at(
        art,
        art_w,
        art_rows,
        SHOWCASE_CARD_INNER_W,
        SHOWCASE_CARD_BODY_ROWS,
        left,
    )


def _showcase_debug_body(pokemon):
    grid, palette = packs.gen5_frames(
        pokemon["name"], pokemon.get("type", "Normal"), pokemon.get("shiny"))[0]
    grid = _crop_grid_to_content(grid, palette)
    src_h, src_w = len(grid), len(grid[0])
    cell_w, cell_h = _CELL_PX or (10, 20)
    canvas_w = SHOWCASE_ART_W * cell_w
    canvas_h = SHOWCASE_CARD_BODY_ROWS * cell_h
    max_sprite_w = SHOWCASE_SPRITE_W * cell_w
    max_sprite_h = SHOWCASE_SPRITE_ROWS * cell_h
    scale = min(max_sprite_w / src_w, max_sprite_h / src_h)
    fit_w = max(1, round(src_w * scale))
    fit_h = max(1, round(src_h * scale))
    art = grid if (fit_w, fit_h) == (src_w, src_h) else pixels.nearest(grid, fit_w, fit_h)
    centered = _pad_grid_alpha_center(art, palette, canvas_w, canvas_h)
    xs = [
        x
        for row in centered
        for x, ch in enumerate(row)
        if ch in palette
    ]
    center_col = SHOWCASE_CARD_INNER_W // 2
    art_left = (SHOWCASE_CARD_INNER_W - SHOWCASE_ART_W) // 2
    art_right = art_left + SHOWCASE_ART_W - 1
    if xs:
        bbox_left = art_left + round(min(xs) / cell_w)
        bbox_right = art_left + round(max(xs) / cell_w)
        centroid = art_left + round((sum(xs) / len(xs)) / cell_w)
    else:
        bbox_left = bbox_right = centroid = center_col

    rows = []
    ruler = ["·"] * SHOWCASE_CARD_INNER_W
    for i in range(0, SHOWCASE_CARD_INNER_W, 5):
        ruler[i] = "+"
    ruler[center_col] = "|"
    rows.append("".join(ruler))

    aperture = [" "] * SHOWCASE_CARD_INNER_W
    aperture[art_left] = "["
    aperture[art_right] = "]"
    aperture[center_col] = "|"
    rows.append("".join(aperture))

    bounds = [" "] * SHOWCASE_CARD_INNER_W
    for i in range(max(0, bbox_left), min(SHOWCASE_CARD_INNER_W, bbox_right + 1)):
        bounds[i] = "-"
    bounds[max(0, min(SHOWCASE_CARD_INNER_W - 1, bbox_left))] = "["
    bounds[max(0, min(SHOWCASE_CARD_INNER_W - 1, bbox_right))] = "]"
    bounds[max(0, min(SHOWCASE_CARD_INNER_W - 1, centroid))] = "C"
    bounds[center_col] = "|" if bounds[center_col] == " " else bounds[center_col]
    rows.append("".join(bounds))

    rows.extend([
        _center_ansi(f"src {src_w}x{src_h}", SHOWCASE_CARD_INNER_W),
        _center_ansi(f"fit {fit_w}x{fit_h}", SHOWCASE_CARD_INNER_W),
        _center_ansi(f"bbox {bbox_left}-{bbox_right}", SHOWCASE_CARD_INNER_W),
        _center_ansi(f"mass {centroid} center {center_col}", SHOWCASE_CARD_INNER_W),
    ])
    while len(rows) < SHOWCASE_CARD_BODY_ROWS:
        rows.append(" " * SHOWCASE_CARD_INNER_W)
    return rows[:SHOWCASE_CARD_BODY_ROWS]


def _showcase_empty_body(label="empty"):
    lines = [" " * SHOWCASE_CARD_INNER_W] * SHOWCASE_CARD_BODY_ROWS
    center = SHOWCASE_CARD_BODY_ROWS // 2
    lines[center - 1] = _center_ansi(f"{DIM}{label}{RESET}", SHOWCASE_CARD_INNER_W)
    lines[center] = _center_ansi(f"{DIM}podium{RESET}", SHOWCASE_CARD_INNER_W)
    return lines


def _showcase_card_lines(entry, selected=False, can_choose=True):
    pokemon = entry.get("pokemon")
    missing = entry.get("missing")
    edge = "+" + "-" * (SHOWCASE_CARD_INNER_W + 2) + "+"
    if pokemon:
        body = (_showcase_debug_body(pokemon)
                if os.environ.get("BUDDYMON_SHOWCASE_DEBUG")
                else _showcase_card_art(pokemon))
        title = _dex_label(pokemon["name"])
        meta = " · ".join(x for x in (
            pokemon["name"],
            f"Lv.{pokemon.get('level')}" if pokemon.get("level") else "",
        ) if x)
    else:
        body = _showcase_empty_body("missing" if missing else "empty")
        title = "open slot"
        if missing:
            meta = "replace or clear"
        elif can_choose:
            meta = "choose from Box"
        else:
            meta = "catch first"

    lines = [
        edge,
        *[f"| {line} |" for line in body],
        edge,
        f"| {_center_ansi(title, SHOWCASE_CARD_INNER_W)} |",
        f"| {_center_ansi(meta, SHOWCASE_CARD_INNER_W)} |",
        edge,
    ]
    if selected:
        return [f"{GREEN}{line}{RESET}" for line in lines]
    return lines


def _showcase_columns(width):
    return max(1, min(SHOWCASE_MAX_COLUMNS,
                      (max(1, width) + SHOWCASE_GAP) // (SHOWCASE_CARD_W + SHOWCASE_GAP)))


def _showcase_row_indent(width, columns):
    row_w = columns * SHOWCASE_CARD_W + max(0, columns - 1) * SHOWCASE_GAP
    return max(0, (width - row_w) // 2)


def _showcase_center_lines(lines, height):
    spare = height - len(lines)
    if spare <= 0:
        return lines
    return [""] * (spare // 2) + lines


def _showcase_page_window(total_slots, selected, columns, max_rows):
    total_rows = (total_slots + columns - 1) // columns if total_slots else 0
    if total_rows == 0:
        return 0, 0, 0, 0, 0
    max_rows = max(1, min(max_rows, total_rows))
    selected_row = max(0, min(selected, total_slots - 1)) // columns
    start_row = min(max(0, selected_row - max_rows + 1),
                    max(0, total_rows - max_rows))
    end_row = min(total_rows, start_row + max_rows)
    start = start_row * columns
    end = min(total_slots, end_row * columns)
    return start, end, start_row, end_row, total_rows


def _showcase_rows_that_fit(available, total_rows):
    if total_rows <= 0 or available < SHOWCASE_CARD_ROWS:
        return 0
    return min(total_rows, 1 + max(0, (available - SHOWCASE_CARD_ROWS) //
                                   (SHOWCASE_CARD_ROWS + 1)))


def _showcase_entry_detail(entry, selected, caught):
    if not caught:
        return "No Pokemon caught yet."
    if entry and entry.get("pokemon"):
        p = entry["pokemon"]
        return f"slot {selected + 1}: {_detail_title(p)} · {_pokemon_meta(p)}"
    if entry and entry.get("missing"):
        return f"slot {selected + 1}: assigned Pokemon is missing"
    return f"slot {selected + 1}: empty podium"


def _showcase_compact_label(entry, can_choose):
    slot = entry["slot"] + 1
    pokemon = entry.get("pokemon")
    if pokemon:
        return f"{slot}. {_detail_title(pokemon)} · {_pokemon_meta(pokemon)}"
    if entry.get("missing"):
        return f"{slot}. missing · replace or clear"
    action = "choose from Box" if can_choose else "catch first"
    return f"{slot}. empty podium · {action}"


def _showcase_compact_lines(entries, selected, width, max_lines, can_choose):
    if max_lines <= 0 or not entries:
        return []
    visible_count = min(len(entries), max_lines)
    start = min(max(0, selected - visible_count // 2),
                max(0, len(entries) - visible_count))
    out = []
    for index in range(start, start + visible_count):
        marker = ">" if index == selected else " "
        label = _showcase_compact_label(entries[index], can_choose)
        out.append(_fit_ansi(f"  {marker} {label}", width))
    return out


def _showcase_frame(s, selected=0, width=80, height=24,
                    slot_count=showcase.DEFAULT_SLOT_COUNT, notice=None):
    _frame_images.clear()
    entries = showcase.showcase_entries(s, slot_count)
    selected = max(0, min(selected, len(entries) - 1)) if entries else 0
    caught = len(s.get("pokemon", []))
    filled = sum(1 for e in entries if e.get("pokemon"))
    stale = sum(1 for e in entries if e.get("missing"))
    status = f"{filled}/{slot_count} podiums filled" if caught else "empty trophy room"
    if stale:
        status += f" · {stale} missing"
    hint = ("arrows move · enter choose · s Share Showcase · x clear · esc back"
            if caught else "s Share Showcase · catch Pokemon first · esc back")
    lines = [
        "",
        _header("showcase"),
    ]

    cols = _showcase_columns(width)
    cards = [_showcase_card_lines(entry, i == selected, can_choose=bool(caught))
             for i, entry in enumerate(entries)]
    grid_indent = _showcase_row_indent(width, min(cols, len(cards)))
    current = entries[selected] if entries else None
    detail = _showcase_entry_detail(current, selected, caught)
    footer_lines = 3 + (1 if notice else 0)
    available = max(0, height - len(lines) - 2 - footer_lines)
    total_rows = (len(entries) + cols - 1) // cols if entries else 0
    visible_rows = _showcase_rows_that_fit(available, total_rows)

    if visible_rows:
        start, end, _start_row, _end_row, _total_rows = _showcase_page_window(
            len(cards), selected, cols, visible_rows,
        )
        if start != 0 or end != len(cards):
            status += f" · showing {start + 1}-{end} of {len(cards)}"
        lines += [_fit_ansi(f"  {DIM}{status}{RESET}", width), ""]
        for row_start in range(start, end, cols):
            row_cards = cards[row_start:row_start + cols]
            indent = " " * _showcase_row_indent(width, len(row_cards))
            for parts in zip(*row_cards):
                lines.append(indent + (" " * SHOWCASE_GAP).join(parts))
            if row_start + cols < end:
                lines.append("")
    else:
        compact_height = max(0, height - len(lines) - 2 - footer_lines)
        status += " · compact view"
        lines += [_fit_ansi(f"  {DIM}{status}{RESET}", width), ""]
        compact = _showcase_compact_lines(
            entries, selected, width, compact_height, bool(caught),
        )
        if compact:
            lines += compact
        else:
            lines.append(_fit_ansi(f"  {DIM}{detail}{RESET}", width))

    lines.append(_fit_ansi((" " * grid_indent) + detail, width))
    if notice:
        lines.append(_fit_ansi((" " * grid_indent) + f"{GREEN}{notice}{RESET}", width))
    lines += ["", _fit_ansi((" " * grid_indent) + _footer(hint), width)]
    return "\n".join(_showcase_center_lines(lines, height))


def _showcase_choose_frame(s, selected=0, top=0, list_height=None, width=80,
                           current_id=None, query="", search_active=False):
    _frame_images.clear()
    mons = _box(s, "name", False)
    if query:
        mons = _filter_pokemon_query(mons, query)
    selected = max(0, min(selected, len(mons) - 1)) if mons else 0
    lines = [
        "",
        _header("choose display"),
        _fit_ansi(f"  {DIM}pick one caught Pokemon for this podium · "
                  f"{_search_status(query, search_active)}{RESET}", width),
        "",
    ]
    if not mons:
        msg = f"No Pokemon match '{query}'." if query else "No Pokemon caught yet."
        lines += [
            f"  {DIM}{msg}{RESET}",
            "",
            _fit_ansi(_footer(_search_hint("esc back", query, search_active)), width),
        ]
        return "\n".join(lines)
    if list_height is None:
        visible = list(enumerate(mons))
    else:
        top = max(0, min(top, max(0, len(mons) - list_height)))
        visible = list(enumerate(mons[top:top + list_height], start=top))
        if len(mons) > list_height:
            lines.append(f"  {DIM}showing {top + 1}-{top + len(visible)} of {len(mons)}{RESET}")
    rows = [_box_header_row()]
    for i, p in visible:
        row = _box_row(p, i == selected, s.get("active"))
        if p.get("id") == current_id:
            row = f"{CYAN}{row}{RESET}"
        rows.append(row)
    lines += ["  " + row for row in rows]
    lines += ["", _fit_ansi(
        _footer(_search_hint("↑/↓ move · PgUp/PgDn · ⏎ assign · esc cancel",
                             query, search_active)),
        width,
    )]
    return "\n".join(lines)


def _fresh_showcase_selection_id(mons, selected_id):
    if selected_id is None:
        return None
    for p in mons:
        if p.get("id") == selected_id:
            return p["id"]
    return None


def _status_lines(s):
    _frame_images.clear()
    buddy = st.active_pokemon(s)
    if buddy is None:
        return [f"{DIM}No buddy yet.{RESET}"]
    trainer = s["trainer"]
    species = {p["name"] for p in s["pokemon"]}
    lines = [
        *["   " + r for r in _sprite_lines(buddy)],
        f"  {BOLD}{_pokemon_title(buddy, with_level=True)}{RESET}",
        f"  {_pokemon_meta(buddy)} · {render.gender_symbol(buddy)}",
        f"  XP {CYAN}{render.xp_bar(buddy, 16)}{RESET}",
        "",
        f"  Tokens used {trainer.get('total_tokens', 0):,}",
        f"  Progress {trainer.get('total_xp', 0):,}",
        f"  Streak {trainer.get('streak', 0)}d",
        f"  Balls {trainer.get('balls', 0)}",
        f"  Pokédex {len(species)}/{len(render._dex_universe())} species",
    ]
    recent = sorted(s["pokemon"], key=lambda p: p.get("caught_at", 0), reverse=True)[:5]
    if recent:
        lines += [
            "",
            f"  {BOLD}recent{RESET}",
            *[f"  {_pokemon_title(p, with_level=True)} · {_pokemon_meta(p)}" for p in recent],
        ]
    return lines


def _scroll_frame(title, body_lines, top, height, hint="↑/↓ scroll · esc back"):
    view = body_lines[top:top + height]
    return "\n".join(["", _header(title), ""] + view + ["", _footer(hint)])


def _terminal_graphics_status(s=None):
    if os.environ.get("BUDDYMON_NO_GRAPHICS"):
        return "off by env"
    if s is not None and st.preference(s, "terminal_graphics") == "off":
        return "off"
    return "inline PNGs" if kgp.supported() else "text fallback"


def _graphics_enabled(s):
    return st.preference(s, "terminal_graphics") != "off" and kgp.supported()


def _settings_mode(s):
    mode = s.get("mode", st.DEFAULT_MODE)
    return mode if mode in st.VALID_MODES else st.DEFAULT_MODE


def _settings_rows(s):
    prefs = st.preferences(s)
    return [
        {
            "group": "Gameplay",
            "key": "mode",
            "label": SETTINGS_LABEL["mode"],
            "value": _settings_mode(s),
            "help": ENCOUNTER_MODE_HELP[_settings_mode(s)],
            "writable": True,
        },
        {
            "group": "Notifications",
            "key": "notifications",
            "label": SETTINGS_LABEL["notifications"],
            "value": prefs["notifications"],
            "help": SETTINGS_HELP["notifications"],
            "writable": True,
        },
        {
            "group": "Display",
            "key": "menu_launcher",
            "label": SETTINGS_LABEL["menu_launcher"],
            "value": prefs["menu_launcher"],
            "help": SETTINGS_HELP["menu_launcher"],
            "writable": True,
        },
        {
            "group": "Display",
            "key": "menu_replace",
            "label": SETTINGS_LABEL["menu_replace"],
            "value": prefs["menu_replace"],
            "help": SETTINGS_HELP["menu_replace"],
            "writable": True,
        },
        {
            "group": "Display",
            "key": "terminal_graphics",
            "label": SETTINGS_LABEL["terminal_graphics"],
            "value": prefs["terminal_graphics"],
            "help": SETTINGS_HELP["terminal_graphics"],
            "writable": True,
        },
        {
            "group": "Display",
            "key": "terminal_support",
            "label": SETTINGS_LABEL["terminal_support"],
            "value": _terminal_graphics_status(s),
            "help": SETTINGS_HELP["terminal_support"],
            "writable": False,
        },
        {
            "group": "Sharing",
            "key": "share_reveal",
            "label": SETTINGS_LABEL["share_reveal"],
            "value": prefs["share_reveal"],
            "help": SETTINGS_HELP["share_reveal"],
            "writable": True,
        },
        {
            "group": "Your data",
            "key": "backup",
            "label": "Back up my data",
            "value": "Now",
            "help": "copy state, journal, and art to Documents",
            "writable": True,
            "action": "backup",
        },
        {
            "group": "Sharing",
            "key": "share_banner",
            "label": SETTINGS_LABEL["share_banner"],
            "value": prefs["share_banner"],
            "help": SETTINGS_HELP["share_banner"],
            "writable": True,
        },
    ]


def _settings_selectable_indexes(rows):
    return [i for i, row in enumerate(rows) if row.get("writable")]


def _settings_select(rows, selected, delta=0):
    selectable = _settings_selectable_indexes(rows)
    if not selectable:
        return 0
    if selected not in selectable:
        return selectable[0]
    if not delta:
        return selected
    pos = selectable.index(selected)
    return selectable[(pos + delta) % len(selectable)]


def _settings_cycle(s, key):
    values = SETTINGS_CYCLES.get(key)
    if not values:
        return False
    if key == "mode":
        current = _settings_mode(s)
        s["mode"] = values[(values.index(current) + 1) % len(values)]
        return True
    prefs = st.preferences(s)
    current = prefs.get(key)
    if current not in values:
        current = values[0]
    prefs[key] = values[(values.index(current) + 1) % len(values)]
    return True


def _mutate_fresh_state(mutate, *args):
    """Apply one short TUI mutation to current state under the shared lock."""
    with st.lock():
        fresh = st.load()
        if not mutate(fresh, *args):
            return False
        st.save(fresh)
    return True


def _toggle_favorite(s, copy_id):
    return favorites.toggle(s, copy_id) is not None


def _activate_pokemon_copy(s, copy_id):
    for pokemon in s.get("pokemon", []):
        if pokemon.get("id") == copy_id:
            s["active"] = copy_id
            favorites.set_favorite(pokemon, True)
            return True
    return False


def _settings_display_value(row):
    value = str(row["value"])
    return SETTINGS_VALUE_LABELS.get(row["key"], {}).get(value, value)


def _settings_frame(s, selected=0, width=80, notice=None):
    _frame_images.clear()
    rows = _settings_rows(s)
    selected = _settings_select(rows, selected)
    lines = ["", _header("settings"), ""]
    group = None
    for i, row in enumerate(rows):
        if row["group"] != group:
            group = row["group"]
            lines.append(f"  {DIM}{group}{RESET}")
        cursor = f"{GREEN}▶{RESET}" if i == selected else " "
        value = _settings_display_value(row)
        if i == selected:
            value = f"{BOLD}{value}{RESET}"
        label = f"{row['label']:<18}"
        ro = f" {DIM}read-only{RESET}" if not row["writable"] else ""
        line = f"  {cursor} {label} {value:<14} {DIM}{row['help']}{RESET}{ro}"
        lines.append(_fit_ansi(line, width))
        lines.append("")
    if notice:
        lines.append(_fit_ansi(f"  {GREEN}✓{RESET} {notice}", width))
    hint = "↑/↓ move · ⏎/space change or back up · esc back"
    return "\n".join(lines + [_footer(hint)])


def _dex_entries(s):
    best = {}
    for p in s["pokemon"]:
        if p["name"] not in best or p["level"] > best[p["name"]]["level"]:
            best[p["name"]] = p

    entries = []
    seen = set()
    for name, ptype, rarity in render._dex_universe():
        if name in seen:
            continue
        seen.add(name)
        dex_no = render.dex_number(name)
        p = best.get(name)
        entries.append({
            "idx": dex_no,
            "dex_no": dex_no,
            "name": name,
            "type": ptype,
            "rarity": rarity,
            "pokemon": p,
            "caught": p is not None,
            "active": bool(p and p["id"] == s.get("active")),
        })
    return entries


def _dex_row(entry, selected, width):
    """Fixed-width dex row: number, name, one-letter rarity. No level — the dex
    registers a species, not an individual (level lives in party/box). Type is in
    the detail line above so the row stays narrow enough for the sprite column."""
    cursor = f"{GREEN}▶{RESET}" if selected else " "
    code = _rarity_code(entry["rarity"])
    p = entry["pokemon"]
    # Every column is fixed-width so caught (●) and uncaught (○) rows line up:
    # cursor(1) ' ' dot(1) ' ' idx(3) ' ' shiny(1) name(14) ' ' rarity.
    if p:
        star = f"{YELLOW}*{RESET}" if p.get("shiny") else " "
        active = f" {GREEN}●{RESET}" if entry["active"] else ""
        text = f"{cursor} ● {entry['idx']:03d} {star}{entry['name'][:14]:<14} {code}{active}"
        return _pad_ansi(_fit_ansi(text, width), width)

    text = f"{cursor} ○ {entry['idx']:03d}  {entry['name'][:14]:<14} {code}"
    return f"{DIM}{_pad_ansi(_fit_ansi(text, width), width)}{RESET}"


def _dex_frame(entries, selected, top, height, width, sort_key="dex",
               descending=False, filter_mode="all", total_entries=None,
               total_caught=None, query="", search_active=False):
    _frame_images.clear()
    total = total_entries if total_entries is not None else len(entries)
    caught = (
        total_caught if total_caught is not None
        else sum(1 for e in entries if e["caught"])
    )
    selected = max(0, min(selected, len(entries) - 1)) if entries else 0
    current = entries[selected] if entries else None
    if current:
        status = " · caught" if current["pokemon"] else " · not yet caught"
        detail = f"{current['name']} · {current['type']} · {current['rarity']}{status}"
    else:
        detail = "empty"
    bar_w = min(24, max(8, width - 32))
    filled = round(caught * bar_w / total) if total else 0
    controls = (
        f"  {DIM}{DEX_FILTER_LABEL.get(filter_mode, filter_mode)} · "
        f"by {_dex_sort_label(sort_key, descending)} · {_search_status(query, search_active)}{RESET}"
    )
    header = [
        "",
        _header("pokédex"),
        f"  {CYAN}{'▰' * filled}{'▱' * (bar_w - filled)}{RESET} {caught}/{total} species",
        controls,
        f"  {detail}",
        "",
    ]
    hint = _search_hint("↑/↓ move · PgUp/PgDn · s sort · r reverse · c filter · esc back",
                        query, search_active)
    body_h = max(1, height - len(header) - 2)
    rows = [_dex_row(e, top + i == selected, DEX_LIST_W)
            for i, e in enumerate(entries[top:top + body_h])]
    if not rows:
        empty = _pad_ansi(_fit_ansi("No matching species.", DEX_LIST_W), DEX_LIST_W)
        rows = [f"{DIM}{empty}{RESET}"]
    # Sprite sits to the right of the list, sized to the body height so the frame
    # never overflows. Uncaught species show the classic black-shadow silhouette
    # of their real shape (recolored PNG where supported, recolored half-blocks else).
    art_lines = min(SELECT_ART_H // 2, body_h)
    if current and current["pokemon"]:
        preview = _sprite_lines(current["pokemon"], art_lines * 2)
    elif current:
        preview = _sprite_lines(current, art_lines * 2, silhouette=True)
    else:
        preview = []
    if width >= TWO_COL_MIN_WIDTH:
        body = _two_col(rows, preview, DEX_LIST_W)
    else:  # narrow terminal: list only (detail/sprite already summarized above)
        body = ["  " + r for r in rows]
    return "\n".join(header + body + ["", _footer(hint)])


_NAME_RARITY = None


def _name_rarity():
    """Species name -> rarity, cached. Rarity is a fixed species property, so it
    resolves even for entries that never stored it (level-ups, evolutions)."""
    global _NAME_RARITY
    if _NAME_RARITY is None:
        _NAME_RARITY = {name: rarity for name, _t, rarity in render._dex_universe()}
    return _NAME_RARITY


def _evolution_line(name):
    """A species plus every form it can evolve into (branches included), so a
    shiny caught early still matches its later-form logs."""
    line, stack = {name}, [name]
    while stack:
        for nxt, _lvl in data.EVOLUTIONS.get(stack.pop(), []):
            if nxt not in line:
                line.add(nxt)
                stack.append(nxt)
    return line


def _journal_qualifier(entries, shiny_only, rare_only):
    """Return a predicate that passes any log about a qualifying pokemon — not
    just the encounter line, but its level-ups and evolutions too. Shiny is
    per-individual, so historical progression logs (which never stored it) are
    matched by evolution line of anything caught/seen shiny."""
    shiny_line = set()
    if shiny_only:
        for e in entries:
            if e.get("shiny"):
                shiny_line |= _evolution_line(e.get("name", ""))
    rarity = _name_rarity()

    def keep(e):
        if e.get("kind") == "level":  # level-ups aren't highlights
            return False
        name = e.get("name")
        if shiny_only:
            # exact when the entry recorded shininess (encounters, new progression
            # logs); fall back to evolution-line only for old logs that never did.
            shiny = e["shiny"] if "shiny" in e else bool(name and name in shiny_line)
            if shiny:
                return True
        if rare_only and (e.get("rarity") or rarity.get(name)) in ("legendary", "mythic"):
            return True
        return False
    return keep


def _journal_lines(limit=None, shiny_only=False, rare_only=False, newest_first=True, query=""):
    filtering = shiny_only or rare_only or bool(query)
    # Highlights are sparse, so when filtering we scan the whole journal, not a
    # recent window — "every log with any pokemon that qualifies".
    entries = journal.tail(None if filtering else limit, newest_first=newest_first)
    if shiny_only or rare_only:
        keep = _journal_qualifier(entries, shiny_only, rare_only)
        entries = [e for e in entries if keep(e)]
    if query:
        entries = _filter_journal_query(entries, query)
    if not entries:
        if query:
            msg = f"No journal logs match '{query}'."
        elif not filtering:
            msg = "No journal yet — your story starts with the next turn."
        else:
            what = ("shiny or legendary/mythic" if shiny_only and rare_only
                    else "shiny" if shiny_only else "legendary/mythic")
            msg = f"No {what} logs in the journal yet."
        return [f"{DIM}{msg}{RESET}"]
    import time
    out, day = [], None
    for e in entries:
        d = time.strftime("%b %d", time.localtime(e.get("ts", 0)))
        if d != day:
            day = d
            out.append(f"{BOLD}{d}{RESET}")
        # ⬆️ (U+2B06 + VS16) is measured as 1 cell but drawn as 2, so it overlaps
        # the following space and crams against the name; 🆙 is a clean wide emoji.
        text = e.get("text", "?").replace("⬆️", "🆙")
        out.append(f"  {text}")
    return out


def _journal_filter_status(shiny_only, rare_only, newest_first=True, query="", search_active=False):
    active = []
    if shiny_only:
        active.append(f"{YELLOW}✨ shiny{RESET}")
    if rare_only:
        active.append(f"{CYAN}legendary/mythic{RESET}")
    search = _search_status(query, search_active)
    order = "newest first" if newest_first else "oldest first"
    if active:
        filters = f" {DIM}+{RESET} ".join(active)
        return f"  {DIM}showing only:{RESET} {filters} {DIM}· {order} · {search}{RESET}"
    return f"  {DIM}showing all entries · {order} · {search}{RESET}"


def _sort_pokemon(mons, sort_key, descending):
    """Order pokemon rows by the chosen field, preserving input order for ties."""
    def name_key(pokemon):
        return pokemon["name"].casefold(), pokemon["name"]

    if sort_key == "rarity":
        def key(p):
            rank = PARTY_RARITY_ORDER.get(p.get("rarity"), len(PARTY_RARITY_ORDER))
            return (-rank if descending else rank, *name_key(p))
        return sorted(mons, key=key)
    if sort_key == "dex":
        def key(p):
            number = data.DEX_NUMBERS.get(p["name"], 9999)
            return (-number if descending else number, *name_key(p))
        return sorted(mons, key=key)
    if sort_key == "caught":
        def key(p):
            caught = p.get("caught_at", 0)
            return (-caught if descending else caught, *name_key(p))
        return sorted(mons, key=key)
    # default / "name"
    return sorted(mons, key=name_key, reverse=descending)


def _sort_party(mons, sort_key, descending):
    """Order a list of party rows by the chosen field (used for 'the rest')."""
    return _sort_pokemon(mons, sort_key, descending)


def _party_split(s, sort_key="name", descending=False):
    """Pinned individuals first, then best unpinned species as sortable rest.

    Favorites are per individual, so choose the pinned team before collapsing
    the rest to one row per species.
    """
    mons = list(s["pokemon"])
    active_id = s.get("active")
    active_row = [p for p in mons if p["id"] == active_id]
    favs = sorted([p for p in mons if p.get("favorite") and p["id"] != active_id],
                  key=lambda p: (-(p.get("level") or 0), p["name"].casefold()))
    pinned = active_row + favs
    pinned_species = {p["name"] for p in pinned}
    best = {}
    for p in mons:
        if p["name"] in pinned_species:
            continue
        if p["name"] not in best or p["level"] > best[p["name"]]["level"]:
            best[p["name"]] = p
    rest = _sort_party(
        list(best.values()),
        sort_key, descending)
    return pinned, rest


def _party(s, sort_key="name", descending=False):
    pinned, rest = _party_split(s, sort_key, descending)
    return pinned + rest


def _box(s, sort_key="name", descending=False, fav_only=False):
    mons = _sort_pokemon(box.expand(s.get("pokemon", [])), sort_key, descending)
    if fav_only:
        mons = [p for p in mons if p.get("favorite")]
    return mons


def _sort_dex_entries(entries, sort_key="dex", descending=False):
    if sort_key == "name":
        return sorted(entries, key=lambda e: (e["name"].casefold(), e["name"]), reverse=descending)
    if sort_key == "rarity":
        def key(e):
            rank = PARTY_RARITY_ORDER.get(e.get("rarity"), len(PARTY_RARITY_ORDER))
            return (-rank if descending else rank, e["dex_no"])
        return sorted(entries, key=key)
    if sort_key == "caught":
        def key(e):
            rank = 1 if e.get("caught") else 0
            return (-rank if descending else rank, e["dex_no"])
        return sorted(entries, key=key)
    # default / "dex"
    def key(e):
        number = e["dex_no"]
        return -number if descending else number
    return sorted(entries, key=key)


def _filter_dex_entries(entries, filter_mode="all"):
    if filter_mode == "caught":
        return [e for e in entries if e.get("caught")]
    if filter_mode == "missing":
        return [e for e in entries if not e.get("caught")]
    return list(entries)


def _dex_view_entries(entries, sort_key="dex", descending=False, filter_mode="all", query=""):
    filtered = _filter_dex_entries(_sort_dex_entries(entries, sort_key, descending), filter_mode)
    return _filter_dex_query(filtered, query)


# ── tty plumbing ─────────────────────────────────────────────────────────────

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


def _query_cell_px():
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


def _read_key():
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


def _draw(frame):
    if not _GRAPHICS:
        sys.stdout.write(HOME_CLEAR + frame.replace("\n", "\r\n"))
        sys.stdout.flush()
        return
    # Replace image markers with blanks (keeping the reserved cells) and collect
    # absolute positions, then paint the PNGs on top. Wipe prior images first so
    # the old selection doesn't linger.
    overlays = []
    rendered = []
    for row, line in enumerate(frame.split("\n"), start=1):
        for m in _IMG_RE.finditer(line):
            png_bytes, cols, rows = _frame_images[int(m.group(1))]
            overlays.append((row, _marker_col(line, m.start()),
                             png_bytes, cols, rows, len(overlays) + 1))
        rendered.append(_IMG_RE.sub(lambda m: " " * len(m.group(0)), line))
    out = [kgp.clear(), HOME_CLEAR, "\r\n".join(rendered)]
    for row, col, png_bytes, cols, rows, img_id in overlays:
        out.append("\x1b[%d;%dH" % (row, col) + kgp.place(png_bytes, cols, rows, img_id))
    sys.stdout.write("".join(out))
    sys.stdout.flush()


def _scroll_screen(title, lines):
    top = 0
    while True:
        height = max(4, shutil.get_terminal_size((80, 24)).lines - 5)
        top = max(0, min(top, max(0, len(lines) - height)))
        _draw(_scroll_frame(title, lines, top, height))
        key = _read_key()
        if key in ("esc", "q"):
            return
        if key in ("up", "k"):
            top -= 1
        elif key in ("down", "j"):
            top += 1
        elif key == "wheel_up":
            top -= 3
        elif key == "wheel_down":
            top += 3
        elif key in ("left", "page_up", "b"):
            top -= height
        elif key in ("right", "page_down", "space", "f"):
            top += height
        elif key in ("home", "g"):
            top = 0
        elif key in ("end", "G"):
            top = len(lines)


def _journal_screen():
    shiny_only = False
    rare_only = False
    newest_first = True
    query = ""
    search_active = False
    top = 0
    while True:
        # Activity is the permanent local journey, so every mode starts from the
        # complete journal. Filters and search must not silently narrow the
        # source window before applying their own criteria.
        lines = _journal_lines(
            shiny_only=shiny_only,
            rare_only=rare_only,
            newest_first=newest_first,
            query=query,
        )
        body = [
            _journal_filter_status(shiny_only, rare_only, newest_first, query, search_active),
            "",
        ] + lines
        height = max(4, shutil.get_terminal_size((80, 24)).lines - 5)
        top = max(0, min(top, max(0, len(body) - height)))
        hint = (
            "↑/↓ scroll · s shiny · l legendary/mythic · "
            "r reverse · a all · esc back"
        )
        _draw(_scroll_frame("journal", body, top, height, _search_hint(hint, query, search_active)))
        key = _read_key()
        query, search_active, handled = _search_key(key, query, search_active)
        if handled:
            top = 0
            continue
        if key in ("esc", "q"):
            return
        if key == "s":
            shiny_only = not shiny_only
            top = 0
        elif key == "l":
            rare_only = not rare_only
            top = 0
        elif key == "r":
            newest_first = not newest_first
            top = 0
        elif key == "a":
            shiny_only = rare_only = False
            top = 0
        elif key in ("up", "k"):
            top -= 1
        elif key in ("down", "j"):
            top += 1
        elif key == "wheel_up":
            top -= 3
        elif key == "wheel_down":
            top += 3
        elif key in ("left", "page_up", "b"):
            top -= height
        elif key in ("right", "page_down", "space", "f"):
            top += height
        elif key in ("home", "g"):
            top = 0
        elif key in ("end", "G"):
            top = len(body)


def _dex_screen():
    selected = None
    top = 0
    sort_key = "dex"
    descending = False
    filter_mode = "all"
    query = ""
    search_active = False
    while True:
        s = st.load()
        all_entries = _dex_entries(s)
        entries = _dex_view_entries(all_entries, sort_key, descending, filter_mode, query)
        if not all_entries:
            _scroll_screen("pokédex", [f"{DIM}No dex entries available.{RESET}"])
            return
        if selected is None and entries:
            selected = next((i for i, e in enumerate(entries) if e["active"]), None)
            if selected is None:
                selected = next((i for i, e in enumerate(entries) if e["caught"]), 0)
        height = max(8, shutil.get_terminal_size((80, 24)).lines - 1)
        width = shutil.get_terminal_size((80, 24)).columns
        body_h = max(1, height - DEX_CHROME)
        if entries:
            selected = max(0, min(selected or 0, len(entries) - 1))
            if selected < top:
                top = selected
            elif selected >= top + body_h:
                top = selected - body_h + 1
            top = max(0, min(top, max(0, len(entries) - body_h)))
        else:
            selected = 0
            top = 0
        _draw(_dex_frame(
            entries, selected, top, height, width,
            sort_key=sort_key,
            descending=descending,
            filter_mode=filter_mode,
            total_entries=len(all_entries),
            total_caught=sum(1 for e in all_entries if e["caught"]),
            query=query,
            search_active=search_active,
        ))
        key = _read_key()
        selected_name = entries[selected]["name"] if entries else None
        query, search_active, handled = _search_key(key, query, search_active)
        if handled:
            entries = _dex_view_entries(all_entries, sort_key, descending, filter_mode, query)
            selected = next((i for i, e in enumerate(entries) if e["name"] == selected_name), 0)
            top = 0
            continue
        if key in ("esc", "q"):
            return
        if key == "s":
            selected_name = entries[selected]["name"] if entries else None
            sort_key = _next_dex_sort(sort_key)
            entries = _dex_view_entries(all_entries, sort_key, descending, filter_mode, query)
            selected = next(
                (i for i, e in enumerate(entries) if e["name"] == selected_name),
                0,
            )
            top = 0
        elif key == "r":
            selected_name = entries[selected]["name"] if entries else None
            descending = not descending
            entries = _dex_view_entries(all_entries, sort_key, descending, filter_mode, query)
            selected = next(
                (i for i, e in enumerate(entries) if e["name"] == selected_name),
                0,
            )
            top = 0
        elif key == "c":
            selected_name = entries[selected]["name"] if entries else None
            filter_mode = _next_dex_filter(filter_mode)
            entries = _dex_view_entries(all_entries, sort_key, descending, filter_mode, query)
            selected = next(
                (i for i, e in enumerate(entries) if e["name"] == selected_name),
                0,
            )
            top = 0
        elif key in ("up", "k") and entries:
            selected -= 1
        elif key in ("down", "j") and entries:
            selected += 1
        elif key == "wheel_up" and entries:
            selected -= 3
        elif key == "wheel_down" and entries:
            selected += 3
        elif key in ("page_up", "left", "b") and entries:
            selected -= body_h
        elif key in ("page_down", "right", "space", "f") and entries:
            selected += body_h
        elif key in ("home", "g") and entries:
            selected = 0
        elif key in ("end", "G") and entries:
            selected = len(entries) - 1


def _party_screen():
    sel = 0
    top = 0
    sort_key = "name"
    descending = False
    fav_only = False
    query = ""
    search_active = False
    while True:
        s = st.load()
        base_mons = _party(s, sort_key, descending)
        mons = list(base_mons)
        if fav_only:
            mons = [p for p in mons if p.get("favorite")]
        if query:
            mons = _filter_pokemon_query(mons, query)
        if not base_mons:
            _scroll_screen("party", [f"{DIM}No pokémon yet.{RESET}"])
            return
        height = max(12, shutil.get_terminal_size((80, 24)).lines - 1)
        width = shutil.get_terminal_size((80, 24)).columns
        # List and sprite now sit side by side, so the list gets nearly the full
        # height; the sprite is capped so its rows don't push the frame past the
        # screen. ~6 lines go to fixed chrome (header, "showing", footer).
        art_rows = min(SELECT_ART_H // 2, max(6, height - 11))
        list_h = max(6, height - 7)
        sel = max(0, min(sel, len(mons) - 1)) if mons else 0
        if sel < top:
            top = sel
        elif sel >= top + list_h:
            top = sel - list_h + 1
        top = max(0, min(top, max(0, len(mons) - list_h)))
        _draw(_party_frame(
            s, sel, top, list_h, art_h=art_rows * 2, width=width,
            sort_key=sort_key, descending=descending, fav_only=fav_only,
            query=query, search_active=search_active))
        key = _read_key()
        selected_id = mons[sel]["id"] if mons else None
        query, search_active, handled = _search_key(key, query, search_active)
        if handled:
            mons = _party(s, sort_key, descending)
            if fav_only:
                mons = [p for p in mons if p.get("favorite")]
            if query:
                mons = _filter_pokemon_query(mons, query)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
            top = 0
            continue
        if key in ("esc", "q"):
            return
        if key in ("up", "k"):
            sel -= 1
        elif key in ("down", "j"):
            sel += 1
        elif key == "wheel_up":
            sel -= 3
        elif key == "wheel_down":
            sel += 3
        elif key in ("page_up", "left", "b"):
            sel -= list_h
        elif key in ("page_down", "right", "space"):
            sel += list_h
        elif key in ("home", "g"):
            sel = 0
        elif key in ("end", "G"):
            sel = len(mons) - 1
        elif key == "F":
            selected_id = mons[sel]["id"] if mons else None
            fav_only = not fav_only
            mons = _party(s, sort_key, descending)
            if fav_only:
                mons = [p for p in mons if p.get("favorite")]
            if query:
                mons = _filter_pokemon_query(mons, query)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
            top = 0
        elif key == "f" and mons:
            _mutate_fresh_state(_toggle_favorite, mons[sel]["id"])
        elif key == "s":
            selected_id = mons[sel]["id"] if mons else None
            sort_key = _next_party_sort(sort_key)
            mons = _party(s, sort_key, descending)
            if fav_only:
                mons = [p for p in mons if p.get("favorite")]
            if query:
                mons = _filter_pokemon_query(mons, query)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
        elif key == "r":
            selected_id = mons[sel]["id"] if mons else None
            if sort_key == "active":
                sort_key = PARTY_SORT_FIELDS[0]
            descending = not descending
            mons = _party(s, sort_key, descending)
            if fav_only:
                mons = [p for p in mons if p.get("favorite")]
            if query:
                mons = _filter_pokemon_query(mons, query)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
        elif key == "enter" and mons:
            _mutate_fresh_state(_activate_pokemon_copy, mons[sel]["id"])


def _box_screen():
    sel = 0
    top = 0
    sort_key = "name"
    descending = False
    fav_only = False
    query = ""
    search_active = False
    while True:
        s = st.load()
        base_mons = _box(s, sort_key, descending, fav_only=fav_only)
        mons = list(base_mons)
        if query:
            mons = _filter_pokemon_query(mons, query)
        if not s.get("pokemon") and not fav_only:
            _scroll_screen("box", [f"{DIM}No pokémon in your box yet.{RESET}"])
            return
        height = max(12, shutil.get_terminal_size((80, 24)).lines - 1)
        width = shutil.get_terminal_size((80, 24)).columns
        art_rows = min(SELECT_ART_H // 2, max(6, height - 11))
        list_h = max(6, height - 7)
        sel = max(0, min(sel, len(mons) - 1)) if mons else 0
        if sel < top:
            top = sel
        elif sel >= top + list_h:
            top = sel - list_h + 1
        top = max(0, min(top, max(0, len(mons) - list_h)))
        _draw(_box_frame(s, sel, top, list_h, art_h=art_rows * 2, width=width,
                         sort_key=sort_key, descending=descending, fav_only=fav_only,
                         query=query, search_active=search_active))
        key = _read_key()
        selected_id = mons[sel]["id"] if mons else None
        query, search_active, handled = _search_key(key, query, search_active)
        if handled:
            mons = _box(s, sort_key, descending, fav_only=fav_only)
            if query:
                mons = _filter_pokemon_query(mons, query)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
            top = 0
            continue
        if key in ("esc", "q"):
            return
        if key in ("up", "k"):
            sel -= 1
        elif key in ("down", "j"):
            sel += 1
        elif key == "wheel_up":
            sel -= 3
        elif key == "wheel_down":
            sel += 3
        elif key in ("page_up", "left", "b"):
            sel -= list_h
        elif key in ("page_down", "right", "space"):
            sel += list_h
        elif key in ("home", "g"):
            sel = 0
        elif key in ("end", "G"):
            sel = len(mons) - 1
        elif key == "F":
            selected_id = mons[sel]["id"] if mons else None
            fav_only = not fav_only
            mons = _box(s, sort_key, descending, fav_only=fav_only)
            if query:
                mons = _filter_pokemon_query(mons, query)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
            top = 0
        elif key == "f" and mons:
            _mutate_fresh_state(_toggle_favorite, mons[sel]["id"])
        elif key == "s":
            selected_id = mons[sel]["id"] if mons else None
            sort_key = _next_box_sort(sort_key)
            mons = _box(s, sort_key, descending, fav_only=fav_only)
            if query:
                mons = _filter_pokemon_query(mons, query)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
        elif key == "r":
            selected_id = mons[sel]["id"] if mons else None
            descending = not descending
            mons = _box(s, sort_key, descending, fav_only=fav_only)
            if query:
                mons = _filter_pokemon_query(mons, query)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
        elif key == "enter" and mons:
            cid = mons[sel]["id"]  # activate THIS specific copy
            _mutate_fresh_state(_activate_pokemon_copy, cid)


def _showcase_choose_screen(slot_index, current_id=None):
    sel = 0
    top = 0
    query = ""
    search_active = False
    while True:
        s = st.load()
        mons = _box(s, "name", False)
        if query:
            mons = _filter_pokemon_query(mons, query)
        if current_id is not None and mons:
            sel = next((i for i, p in enumerate(mons) if p.get("id") == current_id), sel)
            current_id = None
        height = max(10, shutil.get_terminal_size((80, 24)).lines - 1)
        width = shutil.get_terminal_size((80, 24)).columns
        list_h = max(4, height - 7)
        sel = max(0, min(sel, len(mons) - 1)) if mons else 0
        if sel < top:
            top = sel
        elif sel >= top + list_h:
            top = sel - list_h + 1
        top = max(0, min(top, max(0, len(mons) - list_h)))
        _draw(_showcase_choose_frame(
            s, sel, top, list_h, width=width,
            current_id=showcase.showcase_slots(s)[slot_index],
            query=query,
            search_active=search_active,
        ))
        key = _read_key()
        selected_id = mons[sel]["id"] if mons else None
        query, search_active, handled = _search_key(key, query, search_active)
        if handled:
            mons = _box(s, "name", False)
            if query:
                mons = _filter_pokemon_query(mons, query)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
            top = 0
            continue
        if key in ("esc", "q"):
            return False
        if key in ("up", "k"):
            sel -= 1
        elif key in ("down", "j"):
            sel += 1
        elif key == "wheel_up":
            sel -= 3
        elif key == "wheel_down":
            sel += 3
        elif key in ("page_up", "left", "b"):
            sel -= list_h
        elif key in ("page_down", "right", "space"):
            sel += list_h
        elif key in ("home", "g"):
            sel = 0
        elif key in ("end", "G"):
            sel = len(mons) - 1
        elif key == "enter" and mons:
            with st.lock():
                fresh = st.load()
                fresh_mons = _box(fresh, "name", False)
                if query:
                    fresh_mons = _filter_pokemon_query(fresh_mons, query)
                chosen_id = _fresh_showcase_selection_id(fresh_mons, selected_id)
                if chosen_id:
                    showcase.set_showcase_slot(fresh, slot_index, chosen_id)
                    st.save(fresh)
                    return True


def _showcase_screen():
    sel = 0
    notice = None
    while True:
        s = st.load()
        entries = showcase.showcase_entries(s)
        height = max(14, shutil.get_terminal_size((80, 24)).lines - 1)
        width = shutil.get_terminal_size((80, 24)).columns
        sel = max(0, min(sel, len(entries) - 1)) if entries else 0
        _draw(_showcase_frame(s, sel, width=width, height=height, notice=notice))
        key = _read_key()
        if key in ("esc", "q"):
            return
        cols = _showcase_columns(width)
        if key in ("left", "h"):
            sel -= 1
            notice = None
        elif key in ("right", "l"):
            sel += 1
            notice = None
        elif key in ("up", "k"):
            sel -= cols
            notice = None
        elif key in ("down", "j"):
            sel += cols
            notice = None
        elif key in ("home", "g"):
            sel = 0
            notice = None
        elif key in ("end", "G"):
            sel = len(entries) - 1
            notice = None
        elif key == "s":
            try:
                path = showcase_export.save_showcase_image(s)
                notice = f"saved to {path}"
            except OSError as exc:
                notice = f"share failed: {exc}"
        elif key == "x":
            with st.lock():
                fresh = st.load()
                showcase.clear_showcase_slot(fresh, sel)
                st.save(fresh)
            notice = None
        elif key == "enter" and s.get("pokemon"):
            current = entries[sel].get("pokemon_id") if entries else None
            _showcase_choose_screen(sel, current)
            notice = None


def _settings_screen():
    sel = 0
    notice = None
    while True:
        s = st.load()
        rows = _settings_rows(s)
        sel = _settings_select(rows, sel)
        width = shutil.get_terminal_size((80, 24)).columns
        _draw(_settings_frame(s, sel, width=width, notice=notice))
        key = _read_key()
        if key in ("esc", "q"):
            return
        if key in ("up", "k"):
            sel = _settings_select(rows, sel, -1)
            notice = None
        elif key in ("down", "j"):
            sel = _settings_select(rows, sel, 1)
            notice = None
        elif key in ("enter", "space") and rows[sel].get("writable"):
            if rows[sel].get("action") == "backup":
                try:
                    notice = f"backup saved to {backups.create_backup()}"
                except OSError as exc:
                    notice = f"backup failed: {exc}"
            else:
                _mutate_fresh_state(_settings_cycle, rows[sel]["key"])
                notice = None


def _encounter_screen():
    """Fight/Safari a pending wild with arrow-keys + enter — stays open across
    turns (unlike the SwiftBar dropdown, which closes on every action)."""
    sel = 0
    while True:
        s = st.load()
        kind = _encounter_kind(s)
        if kind is None:
            return  # resolved or expired — nothing to fight
        opts = ENCOUNTER_OPTIONS[kind]
        sel = max(0, min(sel, len(opts) - 1))
        _draw(_encounter_frame(s, kind, sel))
        key = _read_key()
        if key in ("esc", "q"):
            return
        if key in ("left", "up"):
            sel = (sel - 1) % len(opts)
        elif key in ("right", "down"):
            sel = (sel + 1) % len(opts)
        elif key in ("enter", "e"):
            action = opts[sel][1]
            turn = sf.take_turn if kind == "safari" else bt.take_turn
            with st.lock():
                fresh = st.load()
                outcome, msg = turn(fresh, action, random.Random())
                st.save(fresh)
            if outcome and outcome.get("done"):
                _flash_result(msg)
                return


def _open(screen):
    if screen == "encounter":
        _encounter_screen()
        return
    s = st.load()
    if screen == "party":
        _party_screen()
    elif screen == "dex":
        _dex_screen()
    elif screen == "box":
        _box_screen()
    elif screen == "showcase":
        _showcase_screen()
    elif screen == "journal":
        _journal_screen()
    elif screen == "status":
        _scroll_screen("status", _status_lines(s))
    elif screen == "tokens":
        _scroll_screen("token usage", token_usage.report_lines())
    elif screen == "settings":
        _settings_screen()


def run(initial_screen=None):
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("buddymon menu needs an interactive terminal "
              "(run it directly: python3 buddymon.py menu).")
        return
    if st.active_pokemon(st.load()) is None:
        print("No buddy yet — run /buddymon:choose <starter> first.")
        return
    import termios
    import tty
    global _GRAPHICS, _CELL_PX
    s = st.load()
    _GRAPHICS = _graphics_enabled(s)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    sel = 0
    try:
        tty.setcbreak(fd)
        if _GRAPHICS:
            _CELL_PX = _query_cell_px()  # size PNGs to the box so it downscales, not up
        sys.stdout.write(ALT_SCREEN + HIDE_CURSOR + MOUSE_ON)
        if initial_screen in {"party", "dex", "box", "showcase", "journal", "status", "tokens", "settings"}:
            _open(initial_screen)
            return
        if _encounter_kind(st.load()):  # a wild is waiting — jump straight in
            _encounter_screen()
        while True:
            items = _menu_items(st.load())
            sel %= len(items)
            _draw(_menu_frame(items, sel))
            key = _read_key()
            if key in ("q", "esc"):
                break
            if key == "up":
                sel = (sel - 1) % len(items)
            elif key == "down":
                sel = (sel + 1) % len(items)
            elif key in ("enter", "e"):
                choice = items[sel][1]
                if choice == "quit":
                    break
                _open(choice)
                sel = 0  # the menu may have changed (e.g. encounter resolved)
    finally:
        if _GRAPHICS:
            sys.stdout.write(kgp.clear())
        _GRAPHICS = False
        sys.stdout.write(MOUSE_OFF + SHOW_CURSOR + MAIN_SCREEN)
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
