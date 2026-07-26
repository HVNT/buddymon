"""Showcase frames and selection helpers for the TUI."""

import os

from . import packs, pixels, showcase
from . import tui_runtime as runtime
from .tui_collections import _box_header_row, _box_roster, _box_row
from .tui_layout import (
    CYAN,
    DIM,
    GREEN,
    RESET,
    SHOWCASE_ART_W,
    SHOWCASE_CARD_BODY_ROWS,
    SHOWCASE_CARD_INNER_W,
    SHOWCASE_CARD_ROWS,
    SHOWCASE_CARD_W,
    SHOWCASE_GAP,
    SHOWCASE_MAX_COLUMNS,
    SHOWCASE_SPRITE_ROWS,
    SHOWCASE_SPRITE_W,
    _center_ansi,
    _crop_grid_to_content,
    _detail_title,
    _dex_label,
    _filter_pokemon_query,
    _fit_ansi,
    _fixed_image_block,
    _footer,
    _header,
    _pad_grid_alpha_center,
    _pokemon_meta,
    _search_hint,
    _search_status,
    _sprite_card_body_at,
    _visible_width,
)


def _showcase_card_art(pokemon):
    grid, palette = packs.gen5_frames(
        pokemon["name"], pokemon.get("type", "Normal"), pokemon.get("shiny"))[0]
    grid = _crop_grid_to_content(grid, palette)
    if runtime.graphics_enabled():
        img_idx = runtime.image_count()
        art = _fixed_image_block(
            grid,
            palette,
            SHOWCASE_ART_W,
            SHOWCASE_CARD_BODY_ROWS,
            SHOWCASE_SPRITE_W,
            SHOWCASE_SPRITE_ROWS,
        )
        _, art_w, art_rows = runtime.image_at(img_idx)
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
    cell_w, cell_h = runtime.cell_size() or (10, 20)
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
    runtime.begin_frame()
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
    runtime.begin_frame()
    mons = _box_roster(s, "name", False)
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
