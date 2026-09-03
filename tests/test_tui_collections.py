from lib import data, engine, iv, render, state, tui
from lib import tui_collections as collections_ui
from lib import tui_layout as layout
from lib import tui_runtime as runtime
from tests.tui_test_support import (
    ANSI_RE,
    _record_background_update,
    _use_temp_state,
    _with_pidgeys,
    fresh,
    visible_width,
)


def test_box_lists_every_individual_including_duplicates():
    s = _with_pidgeys(fresh(), 3, [3, 1, 2])
    frame = collections_ui._box_frame(s, selected=0, top=0, list_height=20, width=80)
    # one starter + three Pidgey rows -> Pidgey appears 3x in the list (+detail)
    assert frame.count("Pidgey") >= 3
    assert "4 caught · 2 species" in frame  # Charmander + 3 Pidgey, 2 species
    for slot in ("1/3", "2/3", "3/3"):  # copy slots distinguish the duplicates
        assert slot in frame


def test_box_frame_stays_within_terminal_width():
    s = _with_pidgeys(fresh(), 4, [1, 2, 3, 4])
    frame = collections_ui._box_frame(s, selected=2, top=0, list_height=20, width=80)
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_box_detail_reflects_the_selected_copy():
    # Pidgeys sort level desc, so selected=1 (after Charmander) is the highest Pidgey
    s = _with_pidgeys(fresh(), 3, [3, 1, 2])
    expanded = collections_ui.box.expand(s["pokemon"])
    frame = collections_ui._box_frame(s, selected=2, top=0, list_height=20, width=80)
    chosen = expanded[2]
    plain = ANSI_RE.sub("", frame)
    assert f"copy {chosen['copy_index']}/{chosen['copy_total']}" in frame
    assert "#016 · Flying · common" in plain
    assert "| caught " in plain and "copy" in plain
    assert "+-" in frame and "-+" in frame
    assert "selected" not in frame


def test_box_detail_shows_copy_appraisal_but_party_does_not():
    s = fresh()
    pokemon = state.active_pokemon(s)
    appraisal = iv.appraise(pokemon["id"])

    box_frame = ANSI_RE.sub("", collections_ui._box_frame(s, 0, width=100))
    party_frame = ANSI_RE.sub("", collections_ui._party_frame(s, 0, width=100))

    assert f"IV {appraisal.percent:>3}%" in box_frame
    assert f"TOTAL {appraisal.total:>2}/45" in box_frame
    assert "ATK " in box_frame and "DEF " in box_frame and "HP  " in box_frame
    assert "IV " not in party_frame
    assert "ATK " not in party_frame


def test_box_narrow_terminal_stacks_without_overflow():
    s = _with_pidgeys(fresh(), 2, [1, 2])
    frame = collections_ui._box_frame(s, selected=0, top=0, list_height=20, width=50)
    # the footer hint is a fixed long string that wraps on narrow terminals
    # (true for every screen); the content/layout itself must fit
    body = [line for line in frame.splitlines() if "esc back" not in line]
    assert all(visible_width(line) <= 50 for line in body)
    assert "+-" in frame and "-+" in frame  # detail panel still present, just stacked
    assert "selected" not in frame


def test_box_empty_is_graceful():
    s = state.default_state()  # no starter, no catches
    frame = collections_ui._box_frame(s, selected=0, top=0, list_height=20, width=80)
    assert "box" in frame
    assert "0 caught" in frame


def test_party_marks_favorites_and_filters_to_them():
    s = fresh()  # Charmander starter is auto-favorited
    plain = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5)
    s["pokemon"].append(plain)  # a non-favorite
    frame = collections_ui._party_frame(s, 0, width=80)
    assert "♥" in frame  # favorite marker rendered for the starter

    fav = collections_ui._party_frame(s, 0, width=80, fav_only=True)
    assert "Charmander" in fav      # the favorite shows
    assert "Pidgey" not in fav      # the non-favorite is filtered out


def test_shiny_marker_sits_after_name_without_shifting_favorite_column():
    shiny = engine.new_pokemon("Staryu", "Water", "⭐", "common", level=1, shiny=True)
    plain = engine.new_pokemon("Staryu", "Water", "⭐", "common", level=1)
    tui.favorites.set_favorite(shiny, True)
    tui.favorites.set_favorite(plain, True)

    shiny_party = ANSI_RE.sub("", collections_ui._party_row(shiny, False, None))
    plain_party = ANSI_RE.sub("", collections_ui._party_row(plain, False, None))
    shiny_box = ANSI_RE.sub("", collections_ui._box_row(shiny, False, None))
    plain_box = ANSI_RE.sub("", collections_ui._box_row(plain, False, None))

    assert "♥*" not in shiny_party
    assert "♥ Staryu*" in shiny_party
    assert shiny_party.index("♥") == plain_party.index("♥")
    assert shiny_party.index("Staryu") == plain_party.index("Staryu")
    assert shiny_party.index("Lv.") == plain_party.index("Lv.")

    assert "♥*" not in shiny_box
    assert "♥ Staryu*" in shiny_box
    assert shiny_box.index("♥") == plain_box.index("♥")
    assert shiny_box.index("Staryu") == plain_box.index("Staryu")
    assert shiny_box.index("Lv.") == plain_box.index("Lv.")


def test_box_filters_to_favorites_and_shows_empty_state():
    s = state.default_state()  # no auto-favorited starter
    a = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5)
    b = engine.new_pokemon("Rattata", "Normal", "🐀", "common", level=3)
    s["pokemon"] += [a, b]
    tui.favorites.set_favorite(a, True)

    fav = collections_ui._box_frame(s, 0, top=0, list_height=20, width=80, fav_only=True)
    assert "Pidgey" in fav and "Rattata" not in fav

    s2 = state.default_state()
    s2["pokemon"].append(engine.new_pokemon("Rattata", "Normal", "🐀", "common", level=3))
    empty = collections_ui._box_frame(s2, 0, top=0, list_height=20, width=80, fav_only=True)
    assert "No favorites yet" in empty


def test_box_frame_shows_sort_controls_and_respects_sort():
    s = state.default_state()
    s["pokemon"] = [
        engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5),
        engine.new_pokemon("Zubat", "Poison", "🦇", "common", level=5),
        engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=5),
    ]

    frame = collections_ui._box_frame(s, 0, top=0, list_height=20, width=80,
                           sort_key="dex", descending=True)

    assert "by dex # desc" in frame
    assert "s sort" in frame and "r reverse" in frame
    assert [p["name"] for p in collections_ui._box_roster(s, "dex", True)] == ["Abra", "Zubat", "Pidgey"]


def test_box_iv_sort_is_best_first_and_reverses_to_worst_first():
    s = state.default_state()
    ids_and_names = [
        ("copy-001", "Pidgey"),        # 28/45
        ("stable-copy-id", "Abra"),   # 18/45
        ("hitmonchan-100", "Zubat"),  # 31/45
    ]
    for pokemon_id, name in ids_and_names:
        pokemon = engine.new_pokemon(name, "Normal", "•", "common", level=5)
        pokemon["id"] = pokemon_id
        s["pokemon"].append(pokemon)

    best = collections_ui._box_roster(s, "iv", False)
    worst = collections_ui._box_roster(s, "iv", True)

    assert [p["id"] for p in best] == ["hitmonchan-100", "copy-001", "stable-copy-id"]
    assert [p["id"] for p in worst] == ["stable-copy-id", "copy-001", "hitmonchan-100"]
    assert "by IV best first" in collections_ui._box_frame(
        s, 0, width=100, sort_key="iv", descending=False)
    assert "by IV worst first" in collections_ui._box_frame(
        s, 0, width=100, sort_key="iv", descending=True)
    assert layout._next_box_sort("caught") == "iv"
    assert layout._next_box_sort("iv") == "rarity"


def test_box_iv_sort_ties_by_species_then_newest_copy(monkeypatch):
    s = state.default_state()
    older = engine.new_pokemon("Pidgey", "Flying", "🐦", "common")
    newer = engine.new_pokemon("Pidgey", "Flying", "🐦", "common")
    abra = engine.new_pokemon("Abra", "Psychic", "🔮", "common")
    older["caught_at"], newer["caught_at"], abra["caught_at"] = 1, 2, 3
    s["pokemon"] = [older, newer, abra]
    monkeypatch.setattr(
        collections_ui.iv,
        "appraise",
        lambda _pokemon_id: iv.Appraisal(10, 10, 10, 30, 67, 2),
    )

    ordered = collections_ui._box_roster(s, "iv", False)

    assert [p["name"] for p in ordered] == ["Abra", "Pidgey", "Pidgey"]
    assert [p["id"] for p in ordered[1:]] == [newer["id"], older["id"]]


def test_box_frame_search_filters_by_name_type_and_empty_state():
    s = state.default_state()
    s["pokemon"] = [
        engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5),
        engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=5),
    ]

    frame = collections_ui._box_frame(s, 0, top=0, list_height=20, width=80, query="psychic")
    plain = ANSI_RE.sub("", frame)
    assert "search: psychic" in plain
    assert "Abra" in plain and "Pidgey" not in plain

    empty = collections_ui._box_frame(s, 0, top=0, list_height=20, width=80, query="water")
    assert "No Pokemon match 'water'" in ANSI_RE.sub("", empty)


def test_box_search_supports_structured_iv_terms_without_leaking_to_party():
    s = state.default_state()
    perfect = engine.new_pokemon("Hitmonchan", "Fighting", "🥊", "rare", level=100)
    perfect["id"] = "perfect-16325"
    ordinary = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5)
    ordinary["id"] = "copy-001"
    s["pokemon"] = [ordinary, perfect]

    for query in ("perfect", "stars:4", "iv:100", "atk:15 def:15 hp:15"):
        frame = ANSI_RE.sub("", collections_ui._box_frame(s, 0, width=100, query=query))
        assert "Hitmonchan" in frame
        assert "Pidgey" not in frame

    frame = ANSI_RE.sub("", collections_ui._box_frame(s, 0, width=100, query="iv:62"))
    assert "Pidgey" in frame and "Hitmonchan" not in frame

    party = ANSI_RE.sub("", collections_ui._party_frame(s, 0, width=100, query="iv:62"))
    assert "No Pokemon match 'iv:62'" in party


def test_party_frame_search_filters_visible_rows():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))

    frame = collections_ui._party_frame(s, 0, width=80, query="flying")
    plain = ANSI_RE.sub("", frame)

    assert "search: flying" in plain
    assert "Pidgey" in plain
    assert "Charmander" not in plain


def test_engine_auto_favorites_standouts_not_commons():
    shiny = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", shiny=True)
    legendary = engine.new_pokemon("Mewtwo", "Psychic", "🧬", "legendary")
    starter = engine.new_pokemon("Bulbasaur", "Grass", "🌱", "starter")
    common = engine.new_pokemon("Rattata", "Normal", "🐀", "common")
    assert shiny["favorite"] and legendary["favorite"] and starter["favorite"]
    assert not common.get("favorite")


def test_party_frame_marks_active_and_shows_selected_sprite():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))
    frame = collections_ui._party_frame(s, 0)
    assert "Charmander" in frame and "Pidgey" in frame
    assert "Name" in frame and "Lv" in frame and "R" in frame
    assert "#004" in ANSI_RE.sub("", frame)
    assert "active buddy" in frame
    assert "▶" in frame  # row cursor
    assert "+-" in frame and "-+" in frame
    assert "selected" not in frame
    assert "XP" in frame
    assert "▀" in frame


def test_party_favorite_preserves_state_written_while_waiting(
        tmp_path, monkeypatch):
    initial = fresh()
    pidgey = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5)
    initial["pokemon"].append(pidgey)
    _use_temp_state(monkeypatch, tmp_path, initial)
    keys = ["down", "f", "q"]
    expected = {}

    def read_key():
        key = keys.pop(0)
        if key == "f":
            expected["state"] = _record_background_update()
        return key

    monkeypatch.setattr(runtime, "draw_frame", lambda _frame: None)
    monkeypatch.setattr(runtime, "read_key", read_key)

    tui._party_screen()

    assert keys == []
    assert tui.favorites.toggle(expected["state"], pidgey["id"]) is True
    assert state.load() == expected["state"]


def test_box_activation_uses_selected_id_with_fresh_state(
        tmp_path, monkeypatch):
    initial = fresh()
    pidgey = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5)
    initial["pokemon"].append(pidgey)
    _use_temp_state(monkeypatch, tmp_path, initial)
    keys = ["end", "enter", "q"]
    expected = {}

    def read_key():
        key = keys.pop(0)
        if key == "enter":
            expected["state"] = _record_background_update()
        return key

    monkeypatch.setattr(runtime, "draw_frame", lambda _frame: None)
    monkeypatch.setattr(runtime, "read_key", read_key)

    tui._box_screen()

    assert keys == []
    expected["state"]["active"] = pidgey["id"]
    selected = next(
        p for p in expected["state"]["pokemon"] if p["id"] == pidgey["id"]
    )
    tui.favorites.set_favorite(selected, True)
    assert state.load() == expected["state"]


def test_party_inactive_action_hint_sits_outside_detail_card():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))

    lines = collections_ui._party_frame(s, 1, width=100).splitlines()
    hint_line = next(line for line in lines if "press enter to make active" in line)

    assert not hint_line.lstrip().startswith("|")


def test_party_frame_windows_large_collection():
    s = fresh()
    for i in range(30):
        s["pokemon"].append(engine.new_pokemon(f"Mon{i:02d}", "Normal", "•", "common", level=1))

    frame = collections_ui._party_frame(s, selected=12, top=10, list_height=5)

    assert "showing 11-15 of 31" in frame
    assert "Mon08" not in frame
    assert "Mon09" in frame
    assert "Mon13" in frame
    assert "Mon14" not in frame


def test_party_orders_active_first():
    s = fresh()
    p = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5)
    s["pokemon"].append(p)
    mons = collections_ui._party_roster(s)
    assert mons[0]["id"] == s["active"]  # active buddy first


def test_party_pins_active_and_favorites_then_sorts_the_rest():
    s = state.default_state()
    active = engine.new_pokemon("Gastly", "Ghost", "👻", "rare", level=8)
    fav = engine.new_pokemon("Arceus", "Normal", "🐾", "legendary", level=50)  # auto-favorited
    abra = engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=2)
    zubat = engine.new_pokemon("Zubat", "Poison", "🦇", "common", level=9)
    s["pokemon"] = [active, fav, abra, zubat]
    s["active"] = active["id"]

    # active in slot 1, favorites pinned next, then the rest (name-sorted)
    order = [p["name"] for p in collections_ui._party_roster(s, "name")]
    assert order[0] == "Gastly"             # active first
    assert order[1] == "Arceus"             # favorite pinned
    assert order[2:] == ["Abra", "Zubat"]   # the rest, sorted

    # only the rest responds to sort direction; the pinned team stays put
    desc = [p["name"] for p in collections_ui._party_roster(s, "name", descending=True)]
    assert desc[:2] == ["Gastly", "Arceus"]
    assert desc[2:] == ["Zubat", "Abra"]

    # _party_split exposes the boundary used for the divider
    pinned, rest = collections_ui._party_split(s, "name")
    assert [p["name"] for p in pinned] == ["Gastly", "Arceus"]
    assert [p["name"] for p in rest] == ["Abra", "Zubat"]


def test_party_keeps_favorited_duplicate_before_best_species_copy():
    s = state.default_state()
    shiny = engine.new_pokemon("Staryu", "Water", "⭐", "common", level=1, shiny=True)
    normal = engine.new_pokemon("Staryu", "Water", "⭐", "common", level=12)
    abra = engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=2)
    tui.favorites.set_favorite(shiny, True)
    s["pokemon"] = [normal, shiny, abra]

    pinned, rest = collections_ui._party_split(s, "name")
    mons = collections_ui._party_roster(s, "name")

    assert pinned == [shiny]
    assert mons[0]["id"] == shiny["id"]
    assert normal["id"] not in [p["id"] for p in mons]
    assert [p["name"] for p in rest] == ["Abra"]


def test_party_keeps_active_duplicate_before_best_species_copy():
    s = state.default_state()
    active = engine.new_pokemon("Staryu", "Water", "⭐", "common", level=1)
    normal = engine.new_pokemon("Staryu", "Water", "⭐", "common", level=12)
    zubat = engine.new_pokemon("Zubat", "Poison", "🦇", "common", level=9)
    s["pokemon"] = [normal, active, zubat]
    s["active"] = active["id"]

    mons = collections_ui._party_roster(s, "name")

    assert mons[0]["id"] == active["id"]
    assert normal["id"] not in [p["id"] for p in mons]
    assert [p["name"] for p in mons[1:]] == ["Zubat"]


def test_party_frame_shows_sort_controls_and_divider():
    s = state.default_state()
    s["pokemon"].append(engine.new_pokemon("Gastly", "Ghost", "👻", "rare", level=8))
    s["pokemon"].append(engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=2))
    s["active"] = s["pokemon"][0]["id"]  # Gastly pinned; Abra is the rest
    frame = collections_ui._party_frame(s, 0, sort_key="dex", descending=True)

    assert "rest by dex # desc" in frame
    assert "s sort" in frame and "r reverse" in frame
    assert "the rest" in frame  # divider between the pinned team and the rest


def test_dex_frame_is_dense_and_pageable():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))
    entries = collections_ui._dex_entries(s)
    selected = next(i for i, e in enumerate(entries) if e["name"] == "Charmander")

    frame = collections_ui._dex_frame(entries, selected=selected, top=0, height=18, width=80)

    assert "pokédex" in frame
    assert "species" in frame
    assert "2/649 species" in frame
    assert "PgUp/PgDn" in frame
    assert "Charmander" in frame
    assert "▀" in frame  # selected preview, while the dex remains a list browser
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_dex_view_entries_filter_and_sort():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))
    s["pokemon"].append(engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=5))
    entries = collections_ui._dex_entries(s)

    caught = collections_ui._dex_view_entries(entries, "dex", False, "caught")
    missing = collections_ui._dex_view_entries(entries, "dex", False, "missing")
    caught_name_desc = collections_ui._dex_view_entries(entries, "name", True, "caught")

    assert [e["name"] for e in caught] == ["Charmander", "Pidgey", "Abra"]
    assert "Charmander" not in {e["name"] for e in missing}
    assert [e["name"] for e in caught_name_desc] == ["Pidgey", "Charmander", "Abra"]

    psychic = collections_ui._dex_view_entries(entries, "dex", False, "caught", query="psychic")
    assert [e["name"] for e in psychic] == ["Abra"]


def test_dex_frame_shows_filter_and_sort_controls():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))
    all_entries = collections_ui._dex_entries(s)
    entries = collections_ui._dex_view_entries(all_entries, "name", True, "caught")

    frame = collections_ui._dex_frame(
        entries,
        selected=0,
        top=0,
        height=18,
        width=80,
        sort_key="name",
        descending=True,
        filter_mode="caught",
        total_entries=len(all_entries),
        total_caught=sum(1 for e in all_entries if e["caught"]),
    )

    assert "2/649 species" in frame
    assert "caught" in frame and "by name desc" in frame
    assert "s sort" in frame and "r reverse" in frame and "c filter" in frame

    searched = collections_ui._dex_frame(
        entries,
        selected=0,
        top=0,
        height=18,
        width=80,
        sort_key="name",
        descending=True,
        filter_mode="caught",
        total_entries=len(all_entries),
        total_caught=sum(1 for e in all_entries if e["caught"]),
        query="pidgey",
    )
    assert "search: pidgey" in ANSI_RE.sub("", searched)


def test_dex_rows_align_columns_across_caught_uncaught_and_gender(monkeypatch):
    s = fresh()
    for nm, lvl in [("Nidorino", 16), ("Nidoking", 30), ("Vulpix", 1), ("Paras", 9)]:
        s["pokemon"].append(engine.new_pokemon(nm, "Normal", "•", "common", level=lvl))
    entries = collections_ui._dex_entries(s)
    # include the ♀/♂ gendered species (uncaught) plus caught/uncaught mix
    names = {"Nidoran♀", "Nidoran♂", "Nidorino", "Nidoking", "Clefairy", "Vulpix", "Paras"}
    # The dex registers a species, so rows carry no level — only the fixed name
    # field and the one-letter rarity code, which must line up across every row.
    name_starts, code_cols = set(), set()
    for e in entries:
        if e["name"] not in names:
            continue
        visible = ANSI_RE.sub("", collections_ui._dex_row(e, False, layout.DEX_LIST_W))
        assert visible[9:23].rstrip() == e["name"][:14]  # name field starts at a fixed column
        assert visible[24] == layout.RARITY_CODE[e["rarity"]]  # rarity code at a fixed column
        name_starts.add(9)
        code_cols.add(24)
    assert "Lv." not in visible  # no per-individual level in a species registry
    assert len(name_starts) == 1 and len(code_cols) == 1


def test_dex_entries_mark_caught_species():
    s = fresh()
    entries = collections_ui._dex_entries(s)
    charmander = next(e for e in entries if e["name"] == "Charmander")
    pidgey = next(e for e in entries if e["name"] == "Pidgey")

    assert charmander["caught"]
    assert charmander["active"]
    assert not pidgey["caught"]


def test_dex_entries_use_national_dex_numbers():
    entries = collections_ui._dex_entries(fresh())
    dex = {e["name"]: e["dex_no"] for e in entries}

    assert len(data.DEX_NUMBERS) == 649
    assert [e["name"] for e in entries[:9]] == [
        "Bulbasaur", "Ivysaur", "Venusaur",
        "Charmander", "Charmeleon", "Charizard",
        "Squirtle", "Wartortle", "Blastoise",
    ]
    assert {name: dex[name] for name in (
        "Bulbasaur", "Charmander", "Pikachu", "Gastly",
        "Haunter", "Eevee", "Arceus",
    )} == {
        "Bulbasaur": 1,
        "Charmander": 4,
        "Pikachu": 25,
        "Gastly": 92,
        "Haunter": 93,
        "Eevee": 133,
        "Arceus": 493,
    }


def test_dex_cell_art_fits_oversized_box_sprite(monkeypatch):
    def oversized_box_frames(_name, _ptype="Normal", _shiny=False):
        grid = ["X" * (render.DEX_CELL_W + 8)] * (render.DEX_CELL_H + 4)
        return [(grid, {"X": "#f08030"})]

    monkeypatch.setattr(render.packs, "box_frames", oversized_box_frames)

    grid, palette = render._dex_cell_art("Charizard", "Fire", revealed=True)

    assert len(grid) == render.DEX_CELL_H
    assert all(len(row) == render.DEX_CELL_W for row in grid)
    assert palette["X"] == "#f08030"


def test_dex_cell_size_stays_compact_for_first_screen():
    assert render.DEX_CELL_W <= 28
    assert render.DEX_CELL_H <= 22


def test_dex_cell_art_uses_clear_silhouette_for_unknown(monkeypatch):
    def box_frames(_name, _ptype="Normal", _shiny=False):
        return [(["AB", "BA"], {"A": "#111111", "B": "#eeeeee"})]

    monkeypatch.setattr(render.packs, "box_frames", box_frames)

    _, palette = render._dex_cell_art("Charmander", "Fire", revealed=False)

    assert set(palette.values()) == {render.DEX_UNKNOWN_COLOR}


def test_dex_grid_rows_stay_within_terminal_width_with_oversized_art(monkeypatch):
    def box_frames(name, _ptype="Normal", _shiny=False):
        if name == "Charizard":
            grid = ["C" * (render.DEX_CELL_W + 10)] * (render.DEX_CELL_H + 3)
            return [(grid, {"C": "#f08030"})]
        return [(["A" * 16] * 16, {"A": "#777777"})]

    monkeypatch.setattr(render.packs, "box_frames", box_frames)
    s = state.default_state()
    s["pokemon"].append(engine.new_pokemon("Charizard", "Fire", "🐉", "starter", level=39))

    frame = render.dex_grid(s, columns=80)

    assert "Charizard" in frame
    assert "???" in frame
    assert all(visible_width(line) <= 80 for line in frame.splitlines())
