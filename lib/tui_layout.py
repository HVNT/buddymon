"""Pure ANSI layout, search, and sprite-card composition for the TUI."""

import re

from . import data, packs, pixels, png, render
from . import tui_runtime as runtime


DIM, BOLD, RESET = "\x1b[2m", "\x1b[1m", "\x1b[0m"
CYAN, GREEN = "\x1b[36m", "\x1b[32m"
BLUE, YELLOW, MAGENTA = "\x1b[34m", "\x1b[33m", "\x1b[35m"
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
ENCOUNTER_ART_W = 28
ENCOUNTER_ART_H = 24
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
RARITY_CODE = {
    "common": "C", "uncommon": "U", "rare": "R",
    "legendary": "L", "mythic": "M", "starter": "S",
}
RARITY_COLOR = {
    "C": DIM, "U": GREEN, "R": BLUE,
    "L": YELLOW, "M": MAGENTA, "S": CYAN,
}
PARTY_SORT_FIELDS = ("rarity", "name", "dex", "caught")
PARTY_SORT_LABEL = {
    "active": "active first", "rarity": "rarity", "name": "name",
    "dex": "dex #", "caught": "date caught",
}
BOX_SORT_FIELDS = PARTY_SORT_FIELDS
BOX_SORT_LABEL = PARTY_SORT_LABEL
PARTY_RARITY_ORDER = {
    "common": 0, "uncommon": 1, "rare": 2,
    "legendary": 3, "mythic": 4, "starter": 5,
}
DEX_SORT_FIELDS = ("dex", "name", "rarity", "caught")
DEX_SORT_LABEL = {"dex": "dex #", "name": "name", "rarity": "rarity"}
DEX_FILTER_MODES = ("all", "caught", "missing")
DEX_FILTER_LABEL = {
    "all": "all species", "caught": "caught", "missing": "missing",
}
SEARCH_HINT = "/ search"
TWO_COL_MIN_WIDTH = 56
PARTY_LIST_W = 26
DEX_LIST_W = 28
BOX_LIST_W = 32
DEX_CHROME = 8
FALLBACK_BOX_PX = 768
PREVIEW_TARGET_PX = 210
MIN_IMAGE_COLS = 6


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
    cell_size = runtime.cell_size()
    if cell_size:
        cw, ch = cell_size
        box_h = min(max_rows * ch, PREVIEW_TARGET_PX)
        rows = max(1, round(box_h / ch))
        box_h = rows * ch
        cols = max(MIN_IMAGE_COLS, min(max_cols, round(box_h * src_w / src_h / cw)))
        return cols, rows, cols * cw, rows * ch
    cols = min(max_cols, max(MIN_IMAGE_COLS, round(2 * max_rows * src_w / src_h)))
    scale = max(2, -(-FALLBACK_BOX_PX // max(src_w, src_h)))
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
    """Register a sprite as a real PNG and return markers that the terminal drawer turns
    into an inline image. The sprite is *letterboxed* — scaled to fit its cell
    box preserving aspect, then padded transparent — so the terminal never
    stretches it, however large the box gets."""
    src_h, src_w = len(grid), len(grid[0])
    cols, rows, png_w, png_h = _image_geometry(src_w, src_h, max_cols, max_rows)
    if not runtime.cell_size():
        # fallback: oversized aspect-correct PNG; the terminal downscales it
        png_bytes = png.grid_to_png(grid, palette, max(1, png_w // src_w))
    else:
        scale = min(png_w / src_w, png_h / src_h)
        fit_w = max(1, round(src_w * scale))
        fit_h = max(1, round(src_h * scale))
        art = grid if (fit_w, fit_h) == (src_w, src_h) else pixels.nearest(grid, fit_w, fit_h)
        png_bytes = png.grid_to_png(_pad_grid_center(art, png_w, png_h), palette, 1)
    idx = runtime.register_image(png_bytes, cols, rows)
    token = "\x01IMG%d\x02" % idx
    blank = " " * cols
    return [token.ljust(cols)] + [blank] * (rows - 1)


def _fixed_image_block(grid, palette, cols, rows, max_sprite_cols=None,
                       max_sprite_rows=None):
    """Register a sprite centered inside an exact terminal-cell image box."""
    src_h, src_w = len(grid), len(grid[0])
    cell_size = runtime.cell_size()
    if cell_size:
        cw, ch = cell_size
        png_w, png_h = cols * cw, rows * ch
        max_sprite_w = (max_sprite_cols or cols) * cw
        max_sprite_h = (max_sprite_rows or rows) * ch
    else:
        scale = max(2, -(-FALLBACK_BOX_PX // max(src_w, src_h)))
        png_w, png_h = cols * scale, rows * scale * 2
        max_sprite_w = (max_sprite_cols or cols) * scale
        max_sprite_h = (max_sprite_rows or rows) * scale * 2
    scale = min(max_sprite_w / src_w, max_sprite_h / src_h)
    fit_w = max(1, round(src_w * scale))
    fit_h = max(1, round(src_h * scale))
    art = grid if (fit_w, fit_h) == (src_w, src_h) else pixels.nearest(grid, fit_w, fit_h)
    png_bytes = png.grid_to_png(_pad_grid_alpha_center(art, palette, png_w, png_h), palette, 1)
    idx = runtime.register_image(png_bytes, cols, rows)
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
    if runtime.graphics_enabled():
        return _image_block(grid, palette, SELECT_ART_W, max_h // 2)
    return pixels.render_scaled(grid, palette, SELECT_ART_W, max_h)


def _sprite_card_lines(pokemon, max_h=SELECT_ART_H):
    """Framed preview for selected Pokemon detail panels. Keep the frame ASCII
    and ANSI-free so inline image markers still resolve to the correct columns."""
    grid, palette = packs.gen5_frames(
        pokemon["name"], pokemon.get("type", "Normal"), pokemon.get("shiny"))[0]
    grid = _crop_grid_to_content(grid, palette)
    inner_w, inner_rows, sprite_w, sprite_rows = _sprite_card_geometry(max_h)
    if runtime.graphics_enabled():
        img_idx = runtime.image_count()
        art = _image_block(grid, palette, sprite_w, sprite_rows)
        _, art_w, art_rows = runtime.image_at(img_idx)
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
    if runtime.graphics_enabled():
        img_idx = runtime.image_count()
        art = _image_block(grid, palette, sprite_w, sprite_rows)
        _, art_w, art_rows = runtime.image_at(img_idx)
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
    if runtime.graphics_enabled():
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
