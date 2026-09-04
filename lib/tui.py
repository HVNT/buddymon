"""Interactive terminal UI: arrow-key navigation of party, dex, journal, status.

Launched via `buddymon.py menu` (from the SwiftBar dropdown's "Open buddymon"
item, a shell alias, or a tmux popup). Raw-mode ANSI using only the stdlib, so
it stays responsive and readable in plain terminals. Sprite previews use compact
frames so the screens keep enough room for controls and scrolling. Focused
modules own layout, collection, Showcase, settings, and terminal primitives;
this module coordinates screen loops and the public ``run`` entry point.
"""
import random
import select
import shutil
import sys

from . import backups, battle as bt, data, favorites, journal, render, safari as sf
from . import showcase, showcase_export
from . import state as st
from . import token_usage
from . import tui_collections as collections_ui
from . import tui_layout as layout
from . import tui_runtime as runtime
from . import tui_settings as settings_ui
from . import tui_showcase as showcase_ui
from .tui_layout import BOLD, CYAN, DIM, GREEN, RESET, YELLOW

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
# Action options per encounter kind: (label shown, action verb passed to take_turn)
ENCOUNTER_OPTIONS = {
    "safari": [("Rock", "rock"), ("Bait", "bait"), ("Ball", "ball"), ("Run", "run")],
    "battle": [("Fight", "attack"), ("Ball", "ball"), ("Run", "run")],
}
RESULT_FLASH_SECS = 0.8
_NAME_RARITY = None


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

def _build_menu_frame(items, selected):
    name_w = max(12, max(layout._visible_width(label) for label, _ in items))
    hint_w = max(18, max(layout._visible_width(MENU_HINT.get(action, "")) for _, action in items))
    inner_w = 3 + 2 + name_w + 3 + hint_w
    lines = [
        "",
        layout._header("main menu"),
        f"{DIM}┌{'─' * (inner_w + 2)}┐{RESET}",
    ]
    for i, (label, action) in enumerate(items):
        selected_row = i == selected
        cursor = f"{GREEN}▶{RESET}" if selected_row else " "
        icon = MENU_ICON.get(action, "•")
        hint = MENU_HINT.get(action, "")
        name = layout._pad_ansi(label, name_w)
        hint_text = layout._pad_ansi(f"{DIM}{hint}{RESET}", hint_w)
        row = f"{cursor} {icon}  {name}   {hint_text}"
        if selected_row:
            row = f"{BOLD}{row}{RESET}"
        lines.append(f"{DIM}│{RESET} {row} {DIM}│{RESET}")
    lines += [
        f"{DIM}└{'─' * (inner_w + 2)}┘{RESET}",
        layout._footer("↑/↓ move · ⏎ select · q quit"),
    ]
    return "\n".join(lines)


def render_menu_frame(s, selected=0):
    """Render the main menu from game state for screenshots and other callers."""
    return _build_menu_frame(_menu_items(s), selected)


def render_encounter_frame(s, kind, sel, width=80, height=24):
    """Terminal battle view: compact sprites, status, and the action row."""
    runtime.begin_frame()
    pending = s.get("pending_encounter") if kind == "safari" else s.get("pending_battle")
    buddy = st.active_pokemon(s)
    lines = ["", layout._header(f"wild {pending['name']}"), ""]
    lines.append(layout._pair_line(f"{BOLD}Active Buddy{RESET}", f"{BOLD}Wild Encounter{RESET}"))
    lines.append(layout._pair_line(
        layout._encounter_title(buddy, with_level=True),
        layout._encounter_title(pending, with_level=True),
    ))
    lines.append(layout._pair_line(layout._pokemon_meta(buddy), layout._pokemon_meta(pending)))
    art_w, art_h = layout.encounter_art_size(width, height)
    lines.extend(layout._paired_encounter_sprite_lines(
        buddy,
        pending,
        art_w=art_w,
        art_h=art_h,
    ))
    if kind == "battle":
        lines.append(layout._pair_line(f"HP {layout._bar(bt.buddy_hp_frac(pending))}",
                                f"HP {layout._bar(bt.wild_hp_frac(pending))}"))
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
    lines += ["", layout._footer("←/→ choose · ⏎/e act · esc leave")]
    return "\n".join(lines)


def _flash_result(msg, timeout=RESULT_FLASH_SECS):
    """Show a finished encounter briefly, without requiring an extra keypress."""
    runtime.draw_frame("\n".join(["", layout._header("encounter over"), "",
                     f"  {msg}", "", layout._footer("returning…")]))
    if select.select([0], [], [], timeout)[0]:
        runtime.read_key()  # absorb one impatient dismiss key without acting on it


def _status_lines(s):
    runtime.begin_frame()
    buddy = st.active_pokemon(s)
    if buddy is None:
        return [f"{DIM}No buddy yet.{RESET}"]
    trainer = s["trainer"]
    species = {p["name"] for p in s["pokemon"]}
    lines = [
        *["   " + r for r in layout._sprite_lines(buddy)],
        f"  {BOLD}{layout._pokemon_title(buddy, with_level=True)}{RESET}",
        f"  {layout._pokemon_meta(buddy)} · {render.gender_symbol(buddy)}",
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
            *[f"  {layout._pokemon_title(p, with_level=True)} · {layout._pokemon_meta(p)}" for p in recent],
        ]
    return lines


def _scroll_frame(title, body_lines, top, height, hint="↑/↓ scroll · esc back"):
    view = body_lines[top:top + height]
    return "\n".join(["", layout._header(title), ""] + view + ["", layout._footer(hint)])


def _collection_view_budget(kind, width, height, item_count):
    """Return list rows, sprite height, and roomy state within one TUI frame."""
    if kind not in ("party", "box"):
        raise ValueError("collection budget kind must be party or box")
    _, max_art_h = layout.select_art_size(width, height)
    list_h = max(6, height - (9 if kind == "party" else 8))
    showing = item_count > list_h
    outer_chrome = 7 if showing else 6
    detail_chrome = 6 if kind == "party" else 13
    max_inner_rows = max(4, height - outer_chrome - detail_chrome)
    art_h = min(max_art_h // 2, max_inner_rows) * 2
    return list_h, art_h, layout.roomy_terminal(width, height)


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
        entries = layout._filter_journal_query(entries, query)
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
    search = layout._search_status(query, search_active)
    order = "newest first" if newest_first else "oldest first"
    if active:
        filters = f" {DIM}+{RESET} ".join(active)
        return f"  {DIM}showing only:{RESET} {filters} {DIM}· {order} · {search}{RESET}"
    return f"  {DIM}showing all entries · {order} · {search}{RESET}"


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


def _scroll_screen(title, lines):
    top = 0
    while True:
        height = max(4, shutil.get_terminal_size((80, 24)).lines - 5)
        top = max(0, min(top, max(0, len(lines) - height)))
        runtime.draw_frame(_scroll_frame(title, lines, top, height))
        key = runtime.read_key()
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
        runtime.draw_frame(_scroll_frame("journal", body, top, height, layout._search_hint(hint, query, search_active)))
        key = runtime.read_key()
        query, search_active, handled = layout._search_key(key, query, search_active)
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
        all_entries = collections_ui._dex_entries(s)
        entries = collections_ui._dex_view_entries(all_entries, sort_key, descending, filter_mode, query)
        if not all_entries:
            _scroll_screen("pokédex", [f"{DIM}No dex entries available.{RESET}"])
            return
        if selected is None and entries:
            selected = next((i for i, e in enumerate(entries) if e["active"]), None)
            if selected is None:
                selected = next((i for i, e in enumerate(entries) if e["caught"]), 0)
        height = max(8, shutil.get_terminal_size((80, 24)).lines - 1)
        width = shutil.get_terminal_size((80, 24)).columns
        body_h = max(1, height - layout.DEX_CHROME)
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
        runtime.draw_frame(collections_ui._dex_frame(
            entries, selected, top, height, width,
            sort_key=sort_key,
            descending=descending,
            filter_mode=filter_mode,
            total_entries=len(all_entries),
            total_caught=sum(1 for e in all_entries if e["caught"]),
            query=query,
            search_active=search_active,
        ))
        key = runtime.read_key()
        selected_name = entries[selected]["name"] if entries else None
        query, search_active, handled = layout._search_key(key, query, search_active)
        if handled:
            entries = collections_ui._dex_view_entries(all_entries, sort_key, descending, filter_mode, query)
            selected = next((i for i, e in enumerate(entries) if e["name"] == selected_name), 0)
            top = 0
            continue
        if key in ("esc", "q"):
            return
        if key == "s":
            selected_name = entries[selected]["name"] if entries else None
            sort_key = layout._next_dex_sort(sort_key)
            entries = collections_ui._dex_view_entries(all_entries, sort_key, descending, filter_mode, query)
            selected = next(
                (i for i, e in enumerate(entries) if e["name"] == selected_name),
                0,
            )
            top = 0
        elif key == "r":
            selected_name = entries[selected]["name"] if entries else None
            descending = not descending
            entries = collections_ui._dex_view_entries(all_entries, sort_key, descending, filter_mode, query)
            selected = next(
                (i for i, e in enumerate(entries) if e["name"] == selected_name),
                0,
            )
            top = 0
        elif key == "c":
            selected_name = entries[selected]["name"] if entries else None
            filter_mode = layout._next_dex_filter(filter_mode)
            entries = collections_ui._dex_view_entries(all_entries, sort_key, descending, filter_mode, query)
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
        base_mons = collections_ui._party_roster(s, sort_key, descending)
        mons = list(base_mons)
        if fav_only:
            mons = [p for p in mons if p.get("favorite")]
        if query:
            mons = layout._filter_pokemon_query(mons, query)
        if not base_mons:
            _scroll_screen("party", [f"{DIM}No pokémon yet.{RESET}"])
            return
        height = max(12, shutil.get_terminal_size((80, 24)).lines - 1)
        width = shutil.get_terminal_size((80, 24)).columns
        list_h, art_h, roomy = _collection_view_budget(
            "party", width, height, len(mons)
        )
        sel = max(0, min(sel, len(mons) - 1)) if mons else 0
        if sel < top:
            top = sel
        elif sel >= top + list_h:
            top = sel - list_h + 1
        top = max(0, min(top, max(0, len(mons) - list_h)))
        runtime.draw_frame(collections_ui._party_frame(
            s, sel, top, list_h, art_h=art_h, width=width,
            sort_key=sort_key, descending=descending, fav_only=fav_only,
            query=query, search_active=search_active, roomy=roomy))
        key = runtime.read_key()
        selected_id = mons[sel]["id"] if mons else None
        query, search_active, handled = layout._search_key(key, query, search_active)
        if handled:
            mons = collections_ui._party_roster(s, sort_key, descending)
            if fav_only:
                mons = [p for p in mons if p.get("favorite")]
            if query:
                mons = layout._filter_pokemon_query(mons, query)
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
            mons = collections_ui._party_roster(s, sort_key, descending)
            if fav_only:
                mons = [p for p in mons if p.get("favorite")]
            if query:
                mons = layout._filter_pokemon_query(mons, query)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
            top = 0
        elif key == "f" and mons:
            _mutate_fresh_state(_toggle_favorite, mons[sel]["id"])
        elif key == "s":
            selected_id = mons[sel]["id"] if mons else None
            sort_key = layout._next_party_sort(sort_key)
            mons = collections_ui._party_roster(s, sort_key, descending)
            if fav_only:
                mons = [p for p in mons if p.get("favorite")]
            if query:
                mons = layout._filter_pokemon_query(mons, query)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
        elif key == "r":
            selected_id = mons[sel]["id"] if mons else None
            if sort_key == "active":
                sort_key = layout.PARTY_SORT_FIELDS[0]
            descending = not descending
            mons = collections_ui._party_roster(s, sort_key, descending)
            if fav_only:
                mons = [p for p in mons if p.get("favorite")]
            if query:
                mons = layout._filter_pokemon_query(mons, query)
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
        base_mons = collections_ui._box_roster(s, sort_key, descending, fav_only=fav_only)
        mons = list(base_mons)
        if query:
            mons = layout._filter_pokemon_query(mons, query, include_iv=True)
        if not s.get("pokemon") and not fav_only:
            _scroll_screen("box", [f"{DIM}No pokémon in your box yet.{RESET}"])
            return
        height = max(12, shutil.get_terminal_size((80, 24)).lines - 1)
        width = shutil.get_terminal_size((80, 24)).columns
        list_h, art_h, roomy = _collection_view_budget(
            "box", width, height, len(mons)
        )
        sel = max(0, min(sel, len(mons) - 1)) if mons else 0
        if sel < top:
            top = sel
        elif sel >= top + list_h:
            top = sel - list_h + 1
        top = max(0, min(top, max(0, len(mons) - list_h)))
        runtime.draw_frame(collections_ui._box_frame(s, sel, top, list_h, art_h=art_h, width=width,
                         sort_key=sort_key, descending=descending, fav_only=fav_only,
                         query=query, search_active=search_active, roomy=roomy))
        key = runtime.read_key()
        selected_id = mons[sel]["id"] if mons else None
        query, search_active, handled = layout._search_key(key, query, search_active)
        if handled:
            mons = collections_ui._box_roster(s, sort_key, descending, fav_only=fav_only)
            if query:
                mons = layout._filter_pokemon_query(mons, query, include_iv=True)
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
            mons = collections_ui._box_roster(s, sort_key, descending, fav_only=fav_only)
            if query:
                mons = layout._filter_pokemon_query(mons, query, include_iv=True)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
            top = 0
        elif key == "f" and mons:
            _mutate_fresh_state(_toggle_favorite, mons[sel]["id"])
        elif key == "s":
            selected_id = mons[sel]["id"] if mons else None
            sort_key = layout._next_box_sort(sort_key)
            mons = collections_ui._box_roster(s, sort_key, descending, fav_only=fav_only)
            if query:
                mons = layout._filter_pokemon_query(mons, query, include_iv=True)
            sel = next((i for i, p in enumerate(mons) if p["id"] == selected_id), 0)
        elif key == "r":
            selected_id = mons[sel]["id"] if mons else None
            descending = not descending
            mons = collections_ui._box_roster(s, sort_key, descending, fav_only=fav_only)
            if query:
                mons = layout._filter_pokemon_query(mons, query, include_iv=True)
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
        mons = collections_ui._box_roster(s, "name", False)
        if query:
            mons = layout._filter_pokemon_query(mons, query)
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
        runtime.draw_frame(showcase_ui._showcase_choose_frame(
            s, sel, top, list_h, width=width,
            current_id=showcase.showcase_slots(s)[slot_index],
            query=query,
            search_active=search_active,
        ))
        key = runtime.read_key()
        selected_id = mons[sel]["id"] if mons else None
        query, search_active, handled = layout._search_key(key, query, search_active)
        if handled:
            mons = collections_ui._box_roster(s, "name", False)
            if query:
                mons = layout._filter_pokemon_query(mons, query)
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
                fresh_mons = collections_ui._box_roster(fresh, "name", False)
                if query:
                    fresh_mons = layout._filter_pokemon_query(fresh_mons, query)
                chosen_id = showcase_ui._fresh_showcase_selection_id(fresh_mons, selected_id)
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
        runtime.draw_frame(showcase_ui._showcase_frame(s, sel, width=width, height=height, notice=notice))
        key = runtime.read_key()
        if key in ("esc", "q"):
            return
        cols = showcase_ui._showcase_columns(width)
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
        rows = settings_ui._settings_rows(s)
        sel = settings_ui._settings_select(rows, sel)
        width = shutil.get_terminal_size((80, 24)).columns
        runtime.draw_frame(settings_ui._settings_frame(s, sel, width=width, notice=notice))
        key = runtime.read_key()
        if key in ("esc", "q"):
            return
        if key in ("up", "k"):
            sel = settings_ui._settings_select(rows, sel, -1)
            notice = None
        elif key in ("down", "j"):
            sel = settings_ui._settings_select(rows, sel, 1)
            notice = None
        elif key in ("enter", "space") and rows[sel].get("writable"):
            if rows[sel].get("action") == "backup":
                try:
                    notice = f"backup saved to {backups.create_backup()}"
                except OSError as exc:
                    notice = f"backup failed: {exc}"
            else:
                _mutate_fresh_state(settings_ui._settings_cycle, rows[sel]["key"])
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
        terminal = shutil.get_terminal_size((80, 24))
        runtime.draw_frame(render_encounter_frame(
            s,
            kind,
            sel,
            width=terminal.columns,
            height=terminal.lines,
        ))
        key = runtime.read_key()
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


def _open_screen(screen):
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
    s = st.load()
    runtime.configure_graphics(settings_ui._graphics_enabled(s))
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    sel = 0
    try:
        tty.setcbreak(fd)
        if runtime.graphics_enabled():
            runtime.set_cell_size(runtime.query_cell_size())
        sys.stdout.write(runtime.ALT_SCREEN + runtime.HIDE_CURSOR + runtime.MOUSE_ON)
        if initial_screen in {"party", "dex", "box", "showcase", "journal", "status", "tokens", "settings"}:
            _open_screen(initial_screen)
            return
        if _encounter_kind(st.load()):  # a wild is waiting — jump straight in
            _encounter_screen()
        while True:
            items = _menu_items(st.load())
            sel %= len(items)
            runtime.draw_frame(_build_menu_frame(items, sel))
            key = runtime.read_key()
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
                _open_screen(choice)
                sel = 0  # the menu may have changed (e.g. encounter resolved)
    finally:
        if runtime.graphics_enabled():
            sys.stdout.write(runtime.clear_images())
        runtime.configure_graphics(False)
        runtime.set_cell_size(None)
        sys.stdout.write(runtime.MOUSE_OFF + runtime.SHOW_CURSOR + runtime.MAIN_SCREEN)
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
