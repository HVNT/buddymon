"""Party, Box, and Pokedex models and pure frame builders."""

import time

from . import box, data, iv, render
from . import tui_runtime as runtime
from .tui_layout import (
    BOX_LIST_W,
    CYAN,
    DEX_FILTER_LABEL,
    DEX_LIST_W,
    DIM,
    GREEN,
    MAGENTA,
    PARTY_LIST_W,
    PARTY_RARITY_ORDER,
    RESET,
    SELECT_ART_H,
    TWO_COL_MIN_WIDTH,
    YELLOW,
    _box_sort_label,
    _detail_action_line,
    _detail_two_col_min_width,
    _dex_sort_label,
    _filter_dex_query,
    _filter_pokemon_query,
    _fit_ansi,
    _footer,
    _header,
    _pad_ansi,
    _party_sort_label,
    _pokemon_detail_card_lines,
    _rarity_code,
    _search_hint,
    _search_status,
    _sprite_lines,
    _two_col,
)


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
    runtime.begin_frame()
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
    runtime.begin_frame()
    caught = s.get("pokemon", [])
    mons = _box_roster(s, sort_key, descending, fav_only=fav_only)
    if query:
        mons = _filter_pokemon_query(mons, query, include_iv=True)
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
        panel = [*_pokemon_detail_card_lines(
                     p, active, art_h, f"caught {when}{copy}", show_iv=True),
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
    runtime.begin_frame()
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
    if sort_key == "iv":
        # IV is the only field whose default presentation is highest-first.
        def key(p):
            total = iv.appraise(p["id"]).total
            caught = p.get("caught_at", 0)
            return (total if descending else -total, *name_key(p), -caught)
        return sorted(mons, key=key)
    # default / "name"
    return sorted(mons, key=name_key, reverse=descending)


def _sort_party_roster(mons, sort_key, descending):
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
    rest = _sort_party_roster(
        list(best.values()),
        sort_key, descending)
    return pinned, rest


def _party_roster(s, sort_key="name", descending=False):
    pinned, rest = _party_split(s, sort_key, descending)
    return pinned + rest


def _box_roster(s, sort_key="name", descending=False, fav_only=False):
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
