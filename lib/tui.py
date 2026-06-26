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

from . import battle as bt, box, data, favorites, journal, kgp, packs, pixels, png, render, safari as sf
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
SELECT_CARD_INNER_H = SELECT_CARD_INNER_ROWS * 2

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
PARTY_RARITY_ORDER = {
    "common": 0,
    "uncommon": 1,
    "rare": 2,
    "legendary": 3,
    "mythic": 4,
    "starter": 5,
}

# Two-column screens (list left, sprite right) fall back to the old stacked
# layout below this terminal width. Left columns are fixed-width so the sprite
# panel keeps a constant left margin and nothing jumps while scrolling.
TWO_COL_MIN_WIDTH = 56
PARTY_LIST_W = 26  # +1 vs the old 25 for the favorite (♥) marker slot
DEX_LIST_W = 28
BOX_LIST_W = 32  # party row + favorite slot + a copy "n/m" slot
DEX_CHROME = 7  # header (5 lines) + blank + footer; rows shown = height - DEX_CHROME

# Inline-image rendering (Ghostty/kitty). When active, sprite "lines" are
# invisible markers that _draw replaces with real PNGs placed over the reserved
# cells; otherwise the same calls return half-block art. Set in run().
_GRAPHICS = False
_frame_images = []  # per-frame [(png_bytes, cols, rows)]; marker carries the index
_IMG_RE = re.compile("\x01IMG(\\d+)\x02")
_CELL_PX = None  # (width, height) of one terminal cell in pixels, queried at startup
_FALLBACK_BOX_PX = 768  # if the cell size is unknown, render big enough to force downscaling
PREVIEW_TARGET_PX = 210  # on-screen sprite height (Ghostty); letterboxed, never stretched
MIN_IMAGE_COLS = 6  # keep inline-image marker text narrower than its reserved cell

MENU = [
    ("Party", "party"),
    ("Pokédex", "dex"),
    ("Journal", "journal"),
    ("Status", "status"),
    ("Box", "box"),
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
    "tokens": "daily local usage",
    "settings": "preferences",
    "quit": "leave the menu",
    "encounter": "wild encounter waiting",
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
    ANSI color escapes; terminal placement needs visible cells before marker."""
    return _visible_width(_IMG_RE.sub("", line[:marker_start])) + 1


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


def _two_col(left_lines, right_lines, width):
    """Compose two columns line-by-line, padding the shorter to equal height. The
    left column is fixed-width (so the right sprite keeps a constant margin); the
    right side is appended raw, so image markers and color codes pass through."""
    height = max(len(left_lines), len(right_lines))
    left = list(left_lines) + [""] * (height - len(left_lines))
    right = list(right_lines) + [""] * (height - len(right_lines))
    return [_pair_line(l, r, width=width) for l, r in zip(left, right)]


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


def _pad_grid_center(grid, w, h):
    """Center a char grid inside a w x h canvas, padding with transparent '.'
    (any char absent from the palette renders transparent in grid_to_png)."""
    cur_h = len(grid)
    cur_w = len(grid[0]) if grid else 0
    left = max(0, (w - cur_w) // 2)
    top = max(0, (h - cur_h) // 2)
    blank = "." * w
    out = [blank] * h
    for i, row in enumerate(grid[:h]):
        seg = row[:w]
        out[top + i] = ("." * left + seg).ljust(w, ".")[:w]
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


def _sprite_lines(pokemon, max_h=SELECT_ART_H, silhouette=False):
    """Preview art for party/dex/status. Uses the detailed Gen 5 source (same
    art the menu bar renders). On Ghostty/kitty it renders as a real PNG; on
    plain terminals it area-averages down to half blocks, so species stay
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


def _paired_sprite_lines(left_pokemon, right_pokemon, width=24):
    left = _sprite_lines(left_pokemon)
    right = _sprite_lines(right_pokemon)
    h = max(len(left), len(right))
    left += [""] * (h - len(left))
    right += [""] * (h - len(right))
    return [_pair_line(l, r, width=width) for l, r in zip(left, right)]


def _paired_encounter_sprite_lines(left_pokemon, right_pokemon, width=31):
    left = _encounter_sprite_lines(left_pokemon)
    right = _encounter_sprite_lines(right_pokemon)
    return [_pair_line(l, r, width=width) for l, r in zip(left, right)]


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


def _party_row(p, selected, active_id):
    """One fixed-width party row (no per-row emoji — the preview is the art)."""
    cursor = f"{GREEN}▶{RESET}" if selected else " "
    star = f"{YELLOW}*{RESET}" if p.get("shiny") else " "
    tag = f" {GREEN}●{RESET}" if p["id"] == active_id else "  "
    return (f"{cursor} {_fav_mark(p)}{star}{p['name'][:12]:<12} Lv.{p['level']:<2} "
            f"{_rarity_code(p['rarity'])}{tag}")


def _party_divider():
    label = "─ the rest "
    return f"{DIM}{label}{'─' * max(0, PARTY_LIST_W - len(label))}{RESET}"


def _party_header_row():
    return f"{DIM}    {'Name':<12} Lv    R{RESET}"


def _party_frame(s, selected, top=0, list_height=None, art_h=SELECT_ART_H, width=80,
                 sort_key="name", descending=False, fav_only=False):
    _frame_images.clear()
    pinned, rest = _party_split(s, sort_key, descending)
    mons = pinned + rest
    boundary = len(pinned) if (pinned and rest) else None  # divider position
    if fav_only:
        mons = [p for p in mons if p.get("favorite")]
        boundary = None
    selected = max(0, min(selected, len(mons) - 1)) if mons else 0
    active = s.get("active")
    scope = (f"{MAGENTA}♥ favorites{RESET}" if fav_only
             else f"team pinned · rest by {_party_sort_label(sort_key, descending)}")
    lines = ["", _header("party"),
             f"  {DIM}{scope} · s sort · r reverse · f ♥ · F faves{RESET}",
             ""]
    if fav_only and not mons:
        lines += [f"  {DIM}No favorites yet — press f to ♥ one, or browse the Box.{RESET}",
                  "", _footer("F all · ⏎ active · esc back")]
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
    lines += ["", _footer("↑/↓ or wheel move · PgUp/PgDn page · s sort · r reverse · ⏎ active · esc back")]
    return "\n".join(lines)


def _box_row(p, selected, active_id):
    """One fixed-width box row: a single caught individual, with an n/m copy slot
    so duplicates of the same species are distinguishable in the list."""
    cursor = f"{GREEN}▶{RESET}" if selected else " "
    star = f"{YELLOW}*{RESET}" if p.get("shiny") else " "
    tag = f" {GREEN}●{RESET}" if p["id"] == active_id else "  "
    copy = (f"{p.get('copy_index', 1)}/{p.get('copy_total', 1)}"
            if p.get("copy_total", 1) > 1 else "")
    return (f"{cursor} {_fav_mark(p)}{star}{p['name'][:12]:<12} Lv.{p['level']:<2} "
            f"{_rarity_code(p['rarity'])} {copy:>5}{tag}")


def _box_header_row():
    return f"{DIM}    {'Name':<12} Lv    R Copy{RESET}"


def _box_frame(s, selected, top=0, list_height=None, art_h=SELECT_ART_H, width=80,
               fav_only=False):
    """Box browser: every caught individual (no per-species collapse), with a
    detail panel for the selected copy. Mirrors the two-column party layout."""
    import time
    _frame_images.clear()
    caught = s.get("pokemon", [])
    mons = box.expand(caught)
    if fav_only:
        mons = [p for p in mons if p.get("favorite")]
    active = s.get("active")
    selected = max(0, min(selected, len(mons) - 1)) if mons else 0
    species = len(box.group_by_species(caught))
    scope = (f"{MAGENTA}♥ favorites{RESET}" if fav_only
             else f"{box.total_copies(caught)} caught · {species} species")
    lines = ["", _header("box"),
             f"  {DIM}{scope} · f ♥ · F faves{RESET}",
             ""]
    if fav_only and not mons:
        lines += [f"  {DIM}No favorites yet — press f to ♥ one.{RESET}",
                  "", _footer("F all · ⏎ active · esc back")]
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
    lines += ["", _footer("↑/↓ or wheel move · PgUp/PgDn page · ⏎ make active · esc back")]
    return "\n".join(lines)


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


def _dex_frame(entries, selected, top, height, width):
    _frame_images.clear()
    caught = sum(1 for e in entries if e["caught"])
    selected = max(0, min(selected, len(entries) - 1)) if entries else 0
    current = entries[selected] if entries else None
    if current:
        status = " · caught" if current["pokemon"] else " · not yet caught"
        detail = f"{current['name']} · {current['type']} · {current['rarity']}{status}"
    else:
        detail = "empty"
    bar_w = min(24, max(8, width - 32))
    filled = round(caught * bar_w / len(entries)) if entries else 0
    header = [
        "",
        _header("pokédex"),
        f"  {CYAN}{'▰' * filled}{'▱' * (bar_w - filled)}{RESET} {caught}/{len(entries)} species",
        f"  {detail}",
        "",
    ]
    hint = "↑/↓ or wheel move · PgUp/PgDn/space page · Home/End · esc back"
    body_h = max(1, height - len(header) - 2)
    rows = [_dex_row(e, top + i == selected, DEX_LIST_W)
            for i, e in enumerate(entries[top:top + body_h])]
    # Sprite sits to the right of the list, sized to the body height so the frame
    # never overflows. Uncaught species show the classic black-shadow silhouette
    # of their real shape (recolored PNG on Ghostty, recolored half-blocks else).
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


def _journal_lines(limit=200, shiny_only=False, rare_only=False):
    filtering = shiny_only or rare_only
    # Highlights are sparse, so when filtering we scan the whole journal, not a
    # recent window — "every log with any pokemon that qualifies".
    entries = journal.tail(None if filtering else limit)
    if filtering:
        keep = _journal_qualifier(entries, shiny_only, rare_only)
        entries = [e for e in entries if keep(e)]
    if not entries:
        if not filtering:
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


def _journal_filter_status(shiny_only, rare_only):
    active = []
    if shiny_only:
        active.append(f"{YELLOW}✨ shiny{RESET}")
    if rare_only:
        active.append(f"{CYAN}legendary/mythic{RESET}")
    if active:
        return f"  {DIM}showing only:{RESET} " + f" {DIM}+{RESET} ".join(active)
    return f"  {DIM}showing all entries{RESET}"


def _sort_party(mons, sort_key, descending):
    """Order a list of party rows by the chosen field (used for 'the rest')."""
    name_key = lambda p: (p["name"].casefold(), p["name"])
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


def _party_split(s, sort_key="name", descending=False):
    """Best (highest-level) instance per species, partitioned into a pinned block
    (active buddy first, then favorites) and the sortable rest. Only the rest
    responds to the sort controls — your team stays put at the top."""
    best = {}
    for p in s["pokemon"]:
        if p["name"] not in best or p["level"] > best[p["name"]]["level"]:
            best[p["name"]] = p
    mons = list(best.values())
    active_id = s.get("active")
    active_row = [p for p in mons if p["id"] == active_id]
    favs = sorted([p for p in mons if p.get("favorite") and p["id"] != active_id],
                  key=lambda p: (-(p.get("level") or 0), p["name"].casefold()))
    rest = _sort_party(
        [p for p in mons if not p.get("favorite") and p["id"] != active_id],
        sort_key, descending)
    return active_row + favs, rest


def _party(s, sort_key="name", descending=False):
    pinned, rest = _party_split(s, sort_key, descending)
    return pinned + rest


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
    top = 0
    while True:
        # Highlights (shiny/legendary) are sparse, so scan deeper when filtering.
        limit = 2000 if (shiny_only or rare_only) else 200
        lines = _journal_lines(limit=limit, shiny_only=shiny_only, rare_only=rare_only)
        body = [_journal_filter_status(shiny_only, rare_only), ""] + lines
        height = max(4, shutil.get_terminal_size((80, 24)).lines - 5)
        top = max(0, min(top, max(0, len(body) - height)))
        hint = "↑/↓ scroll · s shiny · l legendary/mythic · a all · esc back"
        _draw(_scroll_frame("journal", body, top, height, hint))
        key = _read_key()
        if key in ("esc", "q"):
            return
        if key == "s":
            shiny_only = not shiny_only
            top = 0
        elif key == "l":
            rare_only = not rare_only
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
    while True:
        s = st.load()
        entries = _dex_entries(s)
        if not entries:
            _scroll_screen("pokédex", [f"{DIM}No dex entries available.{RESET}"])
            return
        if selected is None:
            selected = next((i for i, e in enumerate(entries) if e["active"]), None)
            if selected is None:
                selected = next((i for i, e in enumerate(entries) if e["caught"]), 0)
        height = max(8, shutil.get_terminal_size((80, 24)).lines - 1)
        width = shutil.get_terminal_size((80, 24)).columns
        body_h = max(1, height - DEX_CHROME)
        selected = max(0, min(selected, len(entries) - 1))
        if selected < top:
            top = selected
        elif selected >= top + body_h:
            top = selected - body_h + 1
        top = max(0, min(top, max(0, len(entries) - body_h)))
        _draw(_dex_frame(entries, selected, top, height, width))
        key = _read_key()
        if key in ("esc", "q"):
            return
        if key in ("up", "k"):
            selected -= 1
        elif key in ("down", "j"):
            selected += 1
        elif key == "wheel_up":
            selected -= 3
        elif key == "wheel_down":
            selected += 3
        elif key in ("page_up", "left", "b"):
            selected -= body_h
        elif key in ("page_down", "right", "space", "f"):
            selected += body_h
        elif key in ("home", "g"):
            selected = 0
        elif key in ("end", "G"):
            selected = len(entries) - 1


def _party_screen():
    sel = 0
    top = 0
    sort_key = "name"
    descending = False
    fav_only = False
    while True:
        s = st.load()
        mons = _party(s, sort_key, descending)
        if fav_only:
            mons = [p for p in mons if p.get("favorite")]
        if not mons and not fav_only:
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
            sort_key=sort_key, descending=descending, fav_only=fav_only))
        key = _read_key()
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
            fav_only = not fav_only
            sel = top = 0
        elif key == "f" and mons:
            favorites.toggle(s, mons[sel]["id"])
            st.save(s)
        elif key == "s":
            selected_id = mons[sel]["id"] if mons else None
            sort_key = _next_party_sort(sort_key)
            mons = _party(s, sort_key, descending)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
        elif key == "r":
            selected_id = mons[sel]["id"] if mons else None
            if sort_key == "active":
                sort_key = PARTY_SORT_FIELDS[0]
            descending = not descending
            mons = _party(s, sort_key, descending)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
        elif key == "enter" and mons:
            s["active"] = mons[sel]["id"]
            favorites.set_favorite(mons[sel], True)  # your active buddy is always a favorite
            st.save(s)


def _box_screen():
    sel = 0
    top = 0
    fav_only = False
    while True:
        s = st.load()
        mons = box.expand(s.get("pokemon", []))
        if fav_only:
            mons = [p for p in mons if p.get("favorite")]
        if not mons and not fav_only:
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
                         fav_only=fav_only))
        key = _read_key()
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
            fav_only = not fav_only
            sel = top = 0
        elif key == "f" and mons:
            favorites.toggle(s, mons[sel]["id"])  # toggle on the real entry by id
            st.save(s)
        elif key == "enter" and mons:
            cid = mons[sel]["id"]  # activate THIS specific copy
            s["active"] = cid
            for p in s["pokemon"]:
                if p["id"] == cid:
                    favorites.set_favorite(p, True)  # active buddy is always a favorite
            st.save(s)


def _settings_screen():
    while True:
        s = st.load()
        mode = s.get("mode", "auto")
        on = mode == "battle"
        body = [
            f"  Encounter mode: {BOLD}{'BATTLE' if on else 'AUTO'}{RESET}",
            "",
            f"  {DIM}AUTO{RESET}   commons auto-catch; rare/legendary use Safari",
            f"  {DIM}BATTLE{RESET} every wild is a weaken-then-catch fight",
        ]
        _draw(_scroll_frame("settings", body, 0, 12, "⏎ toggle mode · esc back"))
        key = _read_key()
        if key in ("esc", "q"):
            return
        if key == "enter":
            s["mode"] = "auto" if on else "battle"
            st.save(s)


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
    _GRAPHICS = kgp.supported()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    sel = 0
    try:
        tty.setcbreak(fd)
        if _GRAPHICS:
            _CELL_PX = _query_cell_px()  # size PNGs to the box so it downscales, not up
        sys.stdout.write(ALT_SCREEN + HIDE_CURSOR + MOUSE_ON)
        if initial_screen in {"party", "dex", "box", "journal", "status", "tokens", "settings"}:
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
