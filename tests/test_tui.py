"""TUI frame builders (pure, terminal-free) + non-tty guard."""
import copy
import contextlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import battle, data, engine, paths, render, state, tui


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def fresh():
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    return s


def _use_temp_state(monkeypatch, tmp_path, initial):
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    state.save(initial)


def _record_background_update():
    with state.lock():
        latest = state.load()
        latest["trainer"]["total_xp"] = 12345
        latest["trainer"]["balls"] = 17
        latest.setdefault("xp_sessions", {})["background"] = {
            "last_uuid": "turn-2",
            "updated": 2,
        }
        latest["pending_encounter"] = {
            "name": "Beldum",
            "type": "Steel",
            "rarity": "rare",
            "shiny": False,
        }
        latest["pokemon"].append(
            engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=5)
        )
        state.save(latest)
    return copy.deepcopy(latest)


def visible_width(line):
    return len(ANSI_RE.sub("", line))


def test_menu_frame_lists_all_items_and_marks_selection():
    frame = tui._menu_frame(tui.MENU, 0)
    for label, _ in tui.MENU:
        assert label in frame
    assert "▶" in frame  # selection cursor present
    assert "┌" in frame and "└" in frame
    assert "🔧  Settings" in frame
    assert "🏆  Showcase" in frame
    assert "team and active buddy" in frame


def test_settings_frame_lists_expanded_preferences_and_support(monkeypatch):
    s = state.default_state()
    s["mode"] = "battle"
    s["preferences"]["notifications"] = "silent"
    s["preferences"]["menu_launcher"] = "iterm"
    s["preferences"]["terminal_graphics"] = "off"
    s["preferences"]["menu_replace"] = "off"
    s["preferences"]["share_reveal"] = "off"
    s["preferences"]["share_banner"] = "off"
    monkeypatch.setenv("BUDDYMON_NO_GRAPHICS", "1")

    frame = tui._settings_frame(s, selected=0, width=80)
    plain = ANSI_RE.sub("", frame)

    assert "Gameplay" in plain
    assert "Encounter mode" in plain and "Battle" in plain
    assert "every wild: fight · ball · run" in plain
    assert "Notifications" in plain and "Silent" in plain
    assert "Menu launcher" in plain and "iTerm2" in plain
    assert "Replace menus" in plain and "Off" in plain
    assert "Terminal graphics" in plain and "Off" in plain
    assert "Terminal support" in plain and "off by env" in plain
    assert "Sharing" in plain
    assert "Reveal shares" in plain and "Share banners" in plain
    assert "Your data" in plain
    assert "Back up my data" in plain and "copy state, journal, and art" in plain
    assert "read-only" in plain
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_settings_selection_skips_read_only_rows():
    rows = [
        {"writable": True},
        {"writable": False},
        {"writable": True},
    ]

    assert tui._settings_select(rows, 0, 1) == 2
    assert tui._settings_select(rows, 2, 1) == 0
    assert tui._settings_select(rows, 1) == 0


def test_settings_cycle_keeps_mode_canonical_and_preferences_separate():
    s = state.default_state()

    tui._settings_cycle(s, "mode")
    assert s["mode"] == "safari"
    tui._settings_cycle(s, "mode")
    assert s["mode"] == "battle"
    tui._settings_cycle(s, "mode")
    assert s["mode"] == "auto"
    assert "mode" not in s["preferences"]

    tui._settings_cycle(s, "notifications")
    tui._settings_cycle(s, "menu_launcher")
    tui._settings_cycle(s, "terminal_graphics")
    tui._settings_cycle(s, "menu_replace")
    tui._settings_cycle(s, "share_reveal")
    tui._settings_cycle(s, "share_banner")

    assert s["preferences"]["notifications"] == "silent"
    assert s["preferences"]["menu_launcher"] == "ghostty"
    assert s["preferences"]["terminal_graphics"] == "off"
    assert s["preferences"]["menu_replace"] == "off"
    assert s["preferences"]["share_reveal"] == "off"
    assert s["preferences"]["share_banner"] == "off"


def test_settings_screen_preserves_state_written_while_waiting(
        tmp_path, monkeypatch):
    _use_temp_state(monkeypatch, tmp_path, fresh())
    expected = {}

    def read_key():
        if not expected:
            expected["state"] = _record_background_update()
            return "space"
        return "esc"

    monkeypatch.setattr(tui, "_draw", lambda _frame: None)
    monkeypatch.setattr(tui, "_read_key", read_key)
    monkeypatch.setattr(tui.kgp, "supported", lambda: False)

    tui._settings_screen()

    expected["state"]["mode"] = "safari"
    assert state.load() == expected["state"]


def test_settings_explains_each_encounter_mode():
    expected = {
        "auto": ("Quick", "common quick · rare Safari"),
        "safari": ("Safari", "every wild: rock · bait · ball"),
        "battle": ("Battle", "every wild: fight · ball · run"),
    }
    s = state.default_state()

    for mode, (label, help_text) in expected.items():
        s["mode"] = mode
        row = tui._settings_rows(s)[0]
        assert tui._settings_display_value(row) == label
        assert row["help"] == help_text


def test_graphics_enabled_honors_terminal_graphics_preference(monkeypatch):
    s = state.default_state()
    monkeypatch.setattr(tui.kgp, "supported", lambda: True)

    assert tui._graphics_enabled(s)

    s["preferences"]["terminal_graphics"] = "off"

    assert not tui._graphics_enabled(s)


def test_search_key_edits_and_clears_query():
    query, active, handled = tui._search_key("/", "", False)
    assert (query, active, handled) == ("", True, True)

    query, active, handled = tui._search_key("a", query, active)
    assert (query, active, handled) == ("a", True, True)

    query, active, handled = tui._search_key("space", query, active)
    assert (query, active, handled) == ("a ", True, True)

    query, active, handled = tui._search_key("b", query, active)
    assert (query, active, handled) == ("a b", True, True)

    query, active, handled = tui._search_key("\x7f", query, active)
    assert (query, active, handled) == ("a ", True, True)

    query, active, handled = tui._search_key("enter", query, active)
    assert (query, active, handled) == ("a ", False, True)

    query, active, handled = tui._search_key("esc", query, active)
    assert (query, active, handled) == ("", False, True)


def test_query_matches_all_terms_case_insensitive():
    assert tui._query_matches("char fire", "Charmander", "Fire", "starter")
    assert not tui._query_matches("char water", "Charmander", "Fire", "starter")


def _with_pidgeys(s, n, levels):
    for lvl in levels[:n]:
        s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=lvl))
    return s


def test_box_lists_every_individual_including_duplicates():
    s = _with_pidgeys(fresh(), 3, [3, 1, 2])
    frame = tui._box_frame(s, selected=0, top=0, list_height=20, width=80)
    # one starter + three Pidgey rows -> Pidgey appears 3x in the list (+detail)
    assert frame.count("Pidgey") >= 3
    assert "4 caught · 2 species" in frame  # Charmander + 3 Pidgey, 2 species
    for slot in ("1/3", "2/3", "3/3"):  # copy slots distinguish the duplicates
        assert slot in frame


def test_box_frame_stays_within_terminal_width():
    s = _with_pidgeys(fresh(), 4, [1, 2, 3, 4])
    frame = tui._box_frame(s, selected=2, top=0, list_height=20, width=80)
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_box_detail_reflects_the_selected_copy():
    # Pidgeys sort level desc, so selected=1 (after Charmander) is the highest Pidgey
    s = _with_pidgeys(fresh(), 3, [3, 1, 2])
    expanded = tui.box.expand(s["pokemon"])
    frame = tui._box_frame(s, selected=2, top=0, list_height=20, width=80)
    chosen = expanded[2]
    plain = ANSI_RE.sub("", frame)
    assert f"copy {chosen['copy_index']}/{chosen['copy_total']}" in frame
    assert "#016 · Flying · common" in plain
    assert "| caught " in plain and "copy" in plain
    assert "+-" in frame and "-+" in frame
    assert "selected" not in frame


def test_box_narrow_terminal_stacks_without_overflow():
    s = _with_pidgeys(fresh(), 2, [1, 2])
    frame = tui._box_frame(s, selected=0, top=0, list_height=20, width=50)
    # the footer hint is a fixed long string that wraps on narrow terminals
    # (true for every screen); the content/layout itself must fit
    body = [line for line in frame.splitlines() if "esc back" not in line]
    assert all(visible_width(line) <= 50 for line in body)
    assert "+-" in frame and "-+" in frame  # detail panel still present, just stacked
    assert "selected" not in frame


def test_box_empty_is_graceful():
    s = state.default_state()  # no starter, no catches
    frame = tui._box_frame(s, selected=0, top=0, list_height=20, width=80)
    assert "box" in frame
    assert "0 caught" in frame


def test_showcase_empty_without_catches_is_a_trophy_room():
    s = state.default_state()
    frame = tui._showcase_frame(s, selected=0, width=80, height=60)
    plain = ANSI_RE.sub("", frame)

    assert "showcase" in plain
    assert "empty trophy room" in plain
    assert plain.count("open slot") == 6
    assert "catch Pokemon first" in plain
    assert "choose from Box" not in plain
    assert len(frame.splitlines()) <= 60
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_showcase_empty_slots_with_catches_are_selectable():
    s = fresh()
    frame = tui._showcase_frame(s, selected=1, width=80, height=24)
    plain = ANSI_RE.sub("", frame)

    assert "0/6 podiums filled" in plain
    assert "showing 1-2 of 6" in plain
    assert plain.count("open slot") == 2
    assert "slot 2: empty podium" in plain
    assert "enter choose" in plain
    assert "s Share Showcase" in plain
    assert "choose from Box" in plain
    edge = "+" + "-" * (tui.SHOWCASE_CARD_INNER_W + 2) + "+"
    card_rows = [line for line in frame.splitlines() if edge in ANSI_RE.sub("", line)]
    assert card_rows[0].startswith("    +")
    assert len(frame.splitlines()) <= 24
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_showcase_row_indent_does_not_bias_odd_slack_right():
    row_w = tui.SHOWCASE_CARD_W * 2 + tui.SHOWCASE_GAP

    assert row_w == 71
    assert tui._showcase_row_indent(80, 2) == 4
    assert tui._showcase_row_indent(81, 2) == 5


def test_showcase_frame_vertically_centers_when_roomy():
    s = fresh()
    height = 64
    frame = tui._showcase_frame(s, selected=0, width=80, height=height)
    plain = [ANSI_RE.sub("", line) for line in frame.splitlines()]
    nonblank = [i for i, line in enumerate(plain) if line.strip()]

    top_margin = nonblank[0]
    bottom_margin = height - 1 - nonblank[-1]
    assert abs(top_margin - bottom_margin) <= 1


def test_showcase_frame_can_show_share_notice():
    s = fresh()
    frame = tui._showcase_frame(
        s,
        selected=0,
        width=80,
        height=24,
        notice="saved to /tmp/BuddyMon Showcase.png",
    )
    plain = ANSI_RE.sub("", frame)

    assert "s Share Showcase" in plain
    assert "saved to /tmp/BuddyMon Showcase.png" in plain
    assert len(frame.splitlines()) <= 24


def test_showcase_cards_keep_fixed_width_footer_rows():
    pokemon = engine.new_pokemon(
        "Zigzagoon", "Normal", "🐾", "common", level=15, shiny=True,
    )
    cards = [
        tui._showcase_card_lines({"slot": 0, "pokemon": pokemon}, selected=True),
        tui._showcase_card_lines({"slot": 1, "pokemon": None}),
        tui._showcase_card_lines({"slot": 2, "pokemon": None, "missing": True}),
    ]

    for card in cards:
        assert all(visible_width(line) == tui.SHOWCASE_CARD_W for line in card)

    selected_plain = [ANSI_RE.sub("", line) for line in cards[0]]
    assert selected_plain[-3:] == [
        f"| {tui._center_ansi('#263', tui.SHOWCASE_CARD_INNER_W)} |",
        f"| {tui._center_ansi('Zigzagoon · Lv.15', tui.SHOWCASE_CARD_INNER_W)} |",
        "+" + "-" * (tui.SHOWCASE_CARD_INNER_W + 2) + "+",
    ]
    assert "shiny" not in "\n".join(selected_plain)
    assert "#1" not in "\n".join(selected_plain)


def test_showcase_text_art_centers_visible_pixels_not_source_padding(monkeypatch):
    def off_center_frame(_name, _ptype="Normal", _shiny=False):
        return [([
            ".........X",
            ".........X",
        ], {"X": "#f8d030"})]

    monkeypatch.setattr(tui.packs, "gen5_frames", off_center_frame)
    monkeypatch.setattr(tui, "_GRAPHICS", False)

    body = tui._showcase_card_art({
        "name": "Abra", "type": "Psychic", "shiny": False,
    })
    rows = [ANSI_RE.sub("", line) for line in body]
    cols = [
        i
        for row in rows
        for i, ch in enumerate(row)
        if ch.strip()
    ]

    assert cols
    content_center = (min(cols) + max(cols)) / 2
    card_center = (tui.SHOWCASE_CARD_INNER_W - 1) / 2
    assert abs(content_center - card_center) <= 0.5


def test_showcase_graphics_art_uses_centered_fixed_aperture(monkeypatch):
    def narrow_frame(_name, _ptype="Normal", _shiny=False):
        return [([
            "X",
            "X",
        ], {"X": "#f8d030"})]

    monkeypatch.setattr(tui.packs, "gen5_frames", narrow_frame)
    monkeypatch.setattr(tui, "_GRAPHICS", True)
    monkeypatch.setattr(tui, "_CELL_PX", (10, 20))
    tui._frame_images.clear()

    body = tui._showcase_card_art({
        "name": "Abra", "type": "Psychic", "shiny": False,
    })

    assert tui._frame_images[0][1:] == (
        tui.SHOWCASE_ART_W,
        tui.SHOWCASE_CARD_BODY_ROWS,
    )
    assert body[0].startswith("   \x01IMG0\x02")
    assert all(visible_width(line) == tui.SHOWCASE_CARD_INNER_W for line in body)


def test_showcase_debug_body_replaces_art_with_measurement_grid(monkeypatch):
    pokemon = engine.new_pokemon("Caterpie", "Bug", "🐛", "common", level=1)
    monkeypatch.setenv("BUDDYMON_SHOWCASE_DEBUG", "1")

    card = "\n".join(ANSI_RE.sub("", line) for line in tui._showcase_card_lines({
        "slot": 0,
        "pokemon": pokemon,
    }))

    assert "src " in card
    assert "fit " in card
    assert "bbox " in card
    assert "mass " in card


def test_showcase_png_canvas_centers_visible_sprite_bounds(monkeypatch):
    monkeypatch.setattr(tui, "_GRAPHICS", True)
    monkeypatch.setattr(tui, "_CELL_PX", (10, 20))

    for name, ptype, shiny in (
        ("Caterpie", "Bug", False),
        ("Linoone", "Normal", False),
        ("Rhyperior", "Ground", False),
        ("Zigzagoon", "Normal", True),
        ("Staravia", "Flying", False),
        ("Staryu", "Water", True),
        ("Pidove", "Flying", True),
    ):
        grid, palette = tui.packs.gen5_frames(name, ptype, shiny)[0]
        grid = tui._crop_grid_to_content(grid, palette)
        src_h, src_w = len(grid), len(grid[0])
        png_w = tui.SHOWCASE_ART_W * 10
        png_h = tui.SHOWCASE_CARD_BODY_ROWS * 20
        max_sprite_w = tui.SHOWCASE_SPRITE_W * 10
        max_sprite_h = tui.SHOWCASE_SPRITE_ROWS * 20
        scale = min(max_sprite_w / src_w, max_sprite_h / src_h)
        art = tui.pixels.nearest(
            grid,
            max(1, round(src_w * scale)),
            max(1, round(src_h * scale)),
        )
        centered = tui._pad_grid_alpha_center(art, palette, png_w, png_h)
        xs = [
            x
            for row in centered
            for x, ch in enumerate(row)
            if ch in palette
        ]

        assert xs, name
        bounds_center = (min(xs) + max(xs)) / 2
        assert abs(bounds_center - ((png_w - 1) / 2)) <= 0.5, name


def test_showcase_filled_and_stale_slots_render_without_autofill():
    s = fresh()
    pidgey = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5)
    s["pokemon"].append(pidgey)
    s["showcase"] = {"slots": [None, pidgey["id"], "gone"]}

    frame = tui._showcase_frame(s, selected=1, width=80, height=24)
    plain = ANSI_RE.sub("", frame)

    assert "1/6 podiums filled · 1 missing" in plain
    assert "Pidgey Lv.5" in plain
    assert "#016" in plain
    assert "missing" in plain
    assert "slot 2: Pidgey Lv.5" in plain


def test_showcase_frame_stacks_on_narrow_terminal():
    s = fresh()
    frame = tui._showcase_frame(s, selected=0, width=40, height=24)
    body = [line for line in frame.splitlines() if "arrows move" not in line]
    plain = ANSI_RE.sub("", frame)

    assert "showing 1-1 of 6" in plain
    assert len(frame.splitlines()) <= 24
    assert all(visible_width(line) <= 40 for line in body)
    assert plain.count("open slot") == 1


def test_showcase_frame_pages_to_selected_row():
    s = fresh()
    frame = tui._showcase_frame(s, selected=5, width=80, height=24)
    plain = ANSI_RE.sub("", frame)

    assert "showing 5-6 of 6" in plain
    assert "slot 6: empty podium" in plain
    assert len(frame.splitlines()) <= 24
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_showcase_frame_uses_compact_rows_when_cards_cannot_fit():
    s = fresh()
    frame = tui._showcase_frame(s, selected=4, width=80, height=14)
    plain = ANSI_RE.sub("", frame)

    assert "compact view" in plain
    assert "> 5. empty podium" in plain
    assert len(frame.splitlines()) <= 14
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_showcase_choose_frame_lists_box_copies():
    s = _with_pidgeys(fresh(), 2, [3, 1])
    expanded = tui.box.expand(s["pokemon"])
    frame = tui._showcase_choose_frame(
        s,
        selected=1,
        top=0,
        list_height=20,
        width=80,
        current_id=expanded[1]["id"],
    )
    plain = ANSI_RE.sub("", frame)

    assert "choose display" in plain
    assert "Pidgey" in plain
    assert "1/2" in plain and "2/2" in plain
    assert "assign" in plain


def test_showcase_choose_frame_search_filters_picker():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))
    s["pokemon"].append(engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=5))

    frame = tui._showcase_choose_frame(s, selected=0, width=80, query="psychic")
    plain = ANSI_RE.sub("", frame)
    assert "search: psychic" in plain
    assert "Abra" in plain and "Pidgey" not in plain

    empty = tui._showcase_choose_frame(s, selected=0, width=80, query="water")
    assert "No Pokemon match 'water'" in ANSI_RE.sub("", empty)


def test_showcase_choose_save_uses_selected_id_after_fresh_list_shifts():
    abra = engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=5)
    pidgey = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5)
    zubat = engine.new_pokemon("Zubat", "Poison", "🦇", "common", level=5)
    selected_id = pidgey["id"]
    old_list = [abra, pidgey]
    fresh_list = [abra, zubat, pidgey]
    stale_index = old_list.index(pidgey)

    assert fresh_list[stale_index]["id"] != selected_id
    assert tui._fresh_showcase_selection_id(fresh_list, selected_id) == selected_id
    assert tui._fresh_showcase_selection_id(fresh_list, "gone") is None


def test_party_marks_favorites_and_filters_to_them():
    s = fresh()  # Charmander starter is auto-favorited
    plain = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5)
    s["pokemon"].append(plain)  # a non-favorite
    frame = tui._party_frame(s, 0, width=80)
    assert "♥" in frame  # favorite marker rendered for the starter

    fav = tui._party_frame(s, 0, width=80, fav_only=True)
    assert "Charmander" in fav      # the favorite shows
    assert "Pidgey" not in fav      # the non-favorite is filtered out


def test_shiny_marker_sits_after_name_without_shifting_favorite_column():
    shiny = engine.new_pokemon("Staryu", "Water", "⭐", "common", level=1, shiny=True)
    plain = engine.new_pokemon("Staryu", "Water", "⭐", "common", level=1)
    tui.favorites.set_favorite(shiny, True)
    tui.favorites.set_favorite(plain, True)

    shiny_party = ANSI_RE.sub("", tui._party_row(shiny, False, None))
    plain_party = ANSI_RE.sub("", tui._party_row(plain, False, None))
    shiny_box = ANSI_RE.sub("", tui._box_row(shiny, False, None))
    plain_box = ANSI_RE.sub("", tui._box_row(plain, False, None))

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

    fav = tui._box_frame(s, 0, top=0, list_height=20, width=80, fav_only=True)
    assert "Pidgey" in fav and "Rattata" not in fav

    s2 = state.default_state()
    s2["pokemon"].append(engine.new_pokemon("Rattata", "Normal", "🐀", "common", level=3))
    empty = tui._box_frame(s2, 0, top=0, list_height=20, width=80, fav_only=True)
    assert "No favorites yet" in empty


def test_box_frame_shows_sort_controls_and_respects_sort():
    s = state.default_state()
    s["pokemon"] = [
        engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5),
        engine.new_pokemon("Zubat", "Poison", "🦇", "common", level=5),
        engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=5),
    ]

    frame = tui._box_frame(s, 0, top=0, list_height=20, width=80,
                           sort_key="dex", descending=True)

    assert "by dex # desc" in frame
    assert "s sort" in frame and "r reverse" in frame
    assert [p["name"] for p in tui._box(s, "dex", True)] == ["Abra", "Zubat", "Pidgey"]


def test_box_frame_search_filters_by_name_type_and_empty_state():
    s = state.default_state()
    s["pokemon"] = [
        engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5),
        engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=5),
    ]

    frame = tui._box_frame(s, 0, top=0, list_height=20, width=80, query="psychic")
    plain = ANSI_RE.sub("", frame)
    assert "search: psychic" in plain
    assert "Abra" in plain and "Pidgey" not in plain

    empty = tui._box_frame(s, 0, top=0, list_height=20, width=80, query="water")
    assert "No Pokemon match 'water'" in ANSI_RE.sub("", empty)


def test_party_frame_search_filters_visible_rows():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))

    frame = tui._party_frame(s, 0, width=80, query="flying")
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


def test_menu_gains_fight_entry_when_a_wild_is_pending():
    s = fresh()
    assert all(action != "encounter" for _, action in tui._menu_items(s))
    s["pending_encounter"] = {"name": "Beldum", "type": "Steel", "shiny": False}
    items = tui._menu_items(s)
    assert items[0][1] == "encounter" and "Beldum" in items[0][0]


def test_encounter_frame_shows_options_and_status():
    s = fresh()
    s["pending_encounter"] = {
        "name": "Beldum", "type": "Steel", "emoji": "⚙️", "rarity": "rare",
        "shiny": False, "level": 20, "c": 90, "base_c": 90,
        "angry": 0, "eating": 0,
        "balls_thrown": 0, "moves": 0, "last_msg": "A wild Beldum appeared!",
    }
    frame = tui._encounter_frame(s, "safari", 0)
    for label, _ in tui.ENCOUNTER_OPTIONS["safari"]:
        assert label in frame
    assert "Beldum" in frame and "▶" in frame
    assert "Beldum Lv.20" in frame
    assert "Active Buddy" in frame
    assert "Wild Encounter" in frame
    assert "🔥 Charmander" not in frame
    assert "⚙️ Beldum" not in frame
    assert "▀" in frame
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_encounter_sprite_lines_use_fixed_portrait_box(monkeypatch):
    def oversized_frames(_name, _ptype="Normal", _shiny=False):
        grid = ["X" * (tui.ENCOUNTER_ART_W + 12)] * (tui.ENCOUNTER_ART_H + 10)
        return [(grid, {"X": "#f08030"})]

    monkeypatch.setattr(tui.packs, "gen5_frames", oversized_frames)

    lines = tui._encounter_sprite_lines({
        "name": "Charizard", "type": "Fire", "emoji": "🐉", "shiny": False,
    })

    assert len(lines) == tui.ENCOUNTER_ART_H // 2
    assert all(visible_width(line) == tui.ENCOUNTER_ART_W for line in lines)


def test_sprite_card_centers_visible_pixels_not_source_padding(monkeypatch):
    def off_center_frame(_name, _ptype="Normal", _shiny=False):
        return [([
            ".........X",
            ".........X",
        ], {"X": "#f8d030"})]

    monkeypatch.setattr(tui.packs, "gen5_frames", off_center_frame)

    lines = tui._sprite_card_lines({"name": "Abra", "type": "Psychic", "shiny": False})
    bbox = tui._sprite_card_content_offset(lines)

    assert bbox is not None
    left, _, right, _ = bbox
    content_center = (left + right - 1) / 2
    card_center = (tui.SELECT_CARD_INNER_W - 1) / 2
    assert abs(content_center - card_center) <= 0.5


def test_sprite_card_uses_fixed_dimensions_for_different_species():
    species = [
        {"name": "Abra", "type": "Psychic", "shiny": False},
        {"name": "Audino", "type": "Normal", "shiny": False},
        {"name": "Baltoy", "type": "Ground", "shiny": False},
        {"name": "Blissey", "type": "Normal", "shiny": False},
    ]
    cards = [tui._sprite_card_lines(p) for p in species]
    visible_shapes = {
        (len(card), tuple(visible_width(line) for line in card))
        for card in cards
    }

    assert len(visible_shapes) == 1
    assert len(cards[0]) == tui.SELECT_CARD_INNER_ROWS + 2
    assert visible_width(cards[0][0]) == tui.SELECT_CARD_INNER_W + 4


def test_pokemon_detail_card_attaches_metadata_inside_one_border():
    s = fresh()
    p = state.active_pokemon(s)

    card = tui._pokemon_detail_card_lines(p, s["active"], art_h=24)
    plain = "\n".join(ANSI_RE.sub("", line) for line in card)

    assert all(line.startswith(("+", "|")) for line in card)
    assert all(visible_width(line) == visible_width(card[0]) for line in card)
    assert sum(1 for line in card if line.startswith("+")) == 3
    assert "+-- Charmander Lv.1" in plain
    assert "#004 · Fire · starter" in plain
    assert "XP " in plain
    assert "active buddy" not in plain
    assert "press enter to make active" not in plain


def test_encounter_title_accepts_legacy_battle_wild_level():
    title = tui._encounter_title({"name": "Beldum", "wild_level": 19}, with_level=True)
    assert title == "Beldum Lv.19"


def _feed_keys(monkeypatch, data: bytes):
    """Drive the real _read_key parser from a fixed byte buffer."""
    buf = bytearray(data)

    def fake_read(_fd, n):
        if not buf:
            return b""
        chunk = bytes(buf[:n])
        del buf[:n]
        return chunk

    # bytes are already "available", so select always reports readable until drained
    def fake_select(rlist, _w, _x, _timeout=0):
        return ((rlist if buf else []), [], [])

    monkeypatch.setattr(tui.os, "read", fake_read)
    monkeypatch.setattr(tui.select, "select", fake_select)
    return buf


def test_read_key_decodes_enter_arrows_and_lone_esc(monkeypatch):
    _feed_keys(monkeypatch, b"\r")
    assert tui._read_key() == "enter"
    _feed_keys(monkeypatch, b"\x1b[A")
    assert tui._read_key() == "up"
    _feed_keys(monkeypatch, b"\x1bOB")  # SS3 arrow
    assert tui._read_key() == "down"
    _feed_keys(monkeypatch, b"\x1b")    # lone Escape (nothing queued behind)
    assert tui._read_key() == "esc"


def test_read_key_skips_kitty_ack_then_returns_enter(monkeypatch):
    # The regression: a kitty graphics ack queued just before the user's Enter
    # must be skipped, not misread as 'esc' or allowed to swallow the Enter.
    _feed_keys(monkeypatch, b"\x1b_Gi=1;OK\x1b\\\r")
    assert tui._read_key() == "enter"


def test_read_key_skips_query_response_then_returns_enter(monkeypatch):
    # A late cell-size / cursor-position style CSI reply must not register.
    _feed_keys(monkeypatch, b"\x1b[6;34;16t\r")
    assert tui._read_key() == "enter"
    _feed_keys(monkeypatch, b"\x1b[24;80R\r")
    assert tui._read_key() == "enter"


def test_read_key_ignores_mouse_move_but_keeps_wheel(monkeypatch):
    _feed_keys(monkeypatch, b"\x1b[<35;10;20M\r")  # plain move -> skipped
    assert tui._read_key() == "enter"
    _feed_keys(monkeypatch, b"\x1b[<64;10;20M")    # wheel up
    assert tui._read_key() == "wheel_up"


def test_finished_encounter_screen_does_not_require_second_key(monkeypatch):
    s = fresh()
    s["pending_battle"] = battle.start({
        "name": "Pidgey", "type": "Flying", "emoji": "🐦",
        "rarity": "common", "shiny": False,
    }, state.active_pokemon(s))
    keys = ["right", "enter"]
    drawn = []

    @contextlib.contextmanager
    def unlocked():
        yield

    def read_key():
        if not keys:
            raise AssertionError("unexpected extra blocking key read")
        return keys.pop(0)

    monkeypatch.setattr(tui, "_draw", drawn.append)
    monkeypatch.setattr(tui, "_read_key", read_key)
    monkeypatch.setattr(tui.st, "load", lambda: s)
    monkeypatch.setattr(tui.st, "save", lambda _s: None)
    monkeypatch.setattr(tui.st, "lock", unlocked)
    monkeypatch.setattr(
        tui.bt,
        "take_turn",
        lambda _s, action, _rng: (
            {"done": True, "caught": True, "outcome": "caught"},
            f"{action} resolved",
        ),
    )
    monkeypatch.setattr(tui, "_flash_result", lambda msg: drawn.append(f"flash:{msg}"))

    tui._encounter_screen()

    assert keys == []
    assert "flash:ball resolved" in drawn


def test_result_flash_times_out_without_key(monkeypatch):
    drawn = []
    monkeypatch.setattr(tui, "_draw", drawn.append)
    monkeypatch.setattr(tui.select, "select", lambda *_args: ([], [], []))
    monkeypatch.setattr(
        tui,
        "_read_key",
        lambda: (_ for _ in ()).throw(AssertionError("should not require a key")),
    )

    tui._flash_result("Done", timeout=0)

    assert any("Done" in frame for frame in drawn)


def test_party_frame_marks_active_and_shows_selected_sprite():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))
    frame = tui._party_frame(s, 0)
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

    monkeypatch.setattr(tui, "_draw", lambda _frame: None)
    monkeypatch.setattr(tui, "_read_key", read_key)

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

    monkeypatch.setattr(tui, "_draw", lambda _frame: None)
    monkeypatch.setattr(tui, "_read_key", read_key)

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

    lines = tui._party_frame(s, 1, width=100).splitlines()
    hint_line = next(line for line in lines if "press enter to make active" in line)

    assert not hint_line.lstrip().startswith("|")


def test_party_frame_windows_large_collection():
    s = fresh()
    for i in range(30):
        s["pokemon"].append(engine.new_pokemon(f"Mon{i:02d}", "Normal", "•", "common", level=1))

    frame = tui._party_frame(s, selected=12, top=10, list_height=5)

    assert "showing 11-15 of 31" in frame
    assert "Mon08" not in frame
    assert "Mon09" in frame
    assert "Mon13" in frame
    assert "Mon14" not in frame


def test_status_lines_show_sprite_preview():
    s = fresh()
    lines = tui._status_lines(s)
    frame = "\n".join(lines)
    assert "Charmander" in frame
    assert "Tokens used" in frame
    assert "Pokédex" in frame
    assert "▀" in frame


def test_party_orders_active_first():
    s = fresh()
    p = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5)
    s["pokemon"].append(p)
    mons = tui._party(s)
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
    order = [p["name"] for p in tui._party(s, "name")]
    assert order[0] == "Gastly"             # active first
    assert order[1] == "Arceus"             # favorite pinned
    assert order[2:] == ["Abra", "Zubat"]   # the rest, sorted

    # only the rest responds to sort direction; the pinned team stays put
    desc = [p["name"] for p in tui._party(s, "name", descending=True)]
    assert desc[:2] == ["Gastly", "Arceus"]
    assert desc[2:] == ["Zubat", "Abra"]

    # _party_split exposes the boundary used for the divider
    pinned, rest = tui._party_split(s, "name")
    assert [p["name"] for p in pinned] == ["Gastly", "Arceus"]
    assert [p["name"] for p in rest] == ["Abra", "Zubat"]


def test_party_keeps_favorited_duplicate_before_best_species_copy():
    s = state.default_state()
    shiny = engine.new_pokemon("Staryu", "Water", "⭐", "common", level=1, shiny=True)
    normal = engine.new_pokemon("Staryu", "Water", "⭐", "common", level=12)
    abra = engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=2)
    tui.favorites.set_favorite(shiny, True)
    s["pokemon"] = [normal, shiny, abra]

    pinned, rest = tui._party_split(s, "name")
    mons = tui._party(s, "name")

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

    mons = tui._party(s, "name")

    assert mons[0]["id"] == active["id"]
    assert normal["id"] not in [p["id"] for p in mons]
    assert [p["name"] for p in mons[1:]] == ["Zubat"]


def test_party_frame_shows_sort_controls_and_divider():
    s = state.default_state()
    s["pokemon"].append(engine.new_pokemon("Gastly", "Ghost", "👻", "rare", level=8))
    s["pokemon"].append(engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=2))
    s["active"] = s["pokemon"][0]["id"]  # Gastly pinned; Abra is the rest
    frame = tui._party_frame(s, 0, sort_key="dex", descending=True)

    assert "rest by dex # desc" in frame
    assert "s sort" in frame and "r reverse" in frame
    assert "the rest" in frame  # divider between the pinned team and the rest


def test_journal_lines_empty_is_graceful(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")
    lines = tui._journal_lines()
    assert lines and "No journal yet" in lines[0]


def _stub_journal(monkeypatch, entries):
    def fake_tail(n=200, newest_first=False):
        selected = list(entries if n is None else entries[-n:])
        return list(reversed(selected)) if newest_first else selected

    monkeypatch.setattr(tui.journal, "tail", fake_tail)


def test_journal_lines_show_newest_first_by_default(monkeypatch):
    _stub_journal(monkeypatch, [
        {"ts": 1, "kind": "caught", "text": "old catch"},
        {"ts": 2, "kind": "caught", "text": "new catch"},
    ])

    newest = "\n".join(tui._journal_lines())
    oldest = "\n".join(tui._journal_lines(newest_first=False))

    assert newest.index("new catch") < newest.index("old catch")
    assert oldest.index("old catch") < oldest.index("new catch")


def test_journal_lines_include_the_complete_activity_history(monkeypatch):
    _stub_journal(monkeypatch, [
        {"ts": index, "kind": "caught", "text": f"activity {index}"}
        for index in range(250)
    ])

    activity = "\n".join(tui._journal_lines())

    assert "activity 0" in activity
    assert "activity 249" in activity


def test_journal_filter_shiny_and_legendary(monkeypatch):
    _stub_journal(monkeypatch, [
        {"ts": 0, "kind": "caught", "text": "🎉 caught Pidgey", "rarity": "common", "shiny": False},
        {"ts": 0, "kind": "caught", "text": "🎉 caught ✨ Gastly", "rarity": "uncommon", "shiny": True},
        {"ts": 0, "kind": "appeared", "text": "👀 a wild Mewtwo appeared!", "rarity": "legendary", "shiny": False},
        {"ts": 0, "kind": "level", "text": "🆙 Pidgey reached Lv.5"},
    ])

    full = "\n".join(tui._journal_lines())
    assert "Pidgey" in full and "Gastly" in full and "Mewtwo" in full

    shiny = "\n".join(tui._journal_lines(shiny_only=True))
    assert "Gastly" in shiny
    assert "Mewtwo" not in shiny and "reached Lv.5" not in shiny

    rare = "\n".join(tui._journal_lines(rare_only=True))
    assert "Mewtwo" in rare
    assert "Gastly" not in rare and "reached Lv.5" not in rare

    both = "\n".join(tui._journal_lines(shiny_only=True, rare_only=True))  # union
    assert "Gastly" in both and "Mewtwo" in both
    assert "reached Lv.5" not in both


def test_journal_filter_empty_message_names_the_filter(monkeypatch):
    _stub_journal(monkeypatch, [
        {"ts": 0, "kind": "caught", "text": "🎉 caught Pidgey", "rarity": "common", "shiny": False},
    ])
    lines = tui._journal_lines(shiny_only=True)
    assert len(lines) == 1 and "No shiny" in lines[0]
    lines = tui._journal_lines(rare_only=True)
    assert "legendary/mythic" in lines[0]


def test_journal_query_filters_log_text(monkeypatch):
    _stub_journal(monkeypatch, [
        {"ts": 1, "kind": "caught", "text": "🎉 caught Pidgey", "name": "Pidgey"},
        {"ts": 2, "kind": "caught", "text": "🎉 caught Abra", "name": "Abra"},
    ])

    lines = "\n".join(tui._journal_lines(query="abra"))

    assert "Abra" in lines
    assert "Pidgey" not in lines


def test_journal_query_empty_message(monkeypatch):
    _stub_journal(monkeypatch, [
        {"ts": 1, "kind": "caught", "text": "🎉 caught Pidgey", "name": "Pidgey"},
    ])

    lines = tui._journal_lines(query="abra")

    assert len(lines) == 1
    assert "No journal logs match 'abra'" in lines[0]


def test_journal_filter_drops_level_ups_keeps_milestones(monkeypatch):
    _stub_journal(monkeypatch, [
        {"ts": 0, "kind": "caught", "text": "🎉 caught ✨ Rhyperior",
         "name": "Rhyperior", "rarity": "rare", "shiny": True},
        {"ts": 0, "kind": "level", "text": "🆙 Rhyperior reached Lv.5",
         "name": "Rhyperior", "shiny": True},
        {"ts": 0, "kind": "evolved", "text": "🎊 evolved into Rhyperior Lv.42",
         "name": "Rhyperior", "shiny": True},
    ])
    shiny = "\n".join(tui._journal_lines(shiny_only=True))
    assert "caught ✨ Rhyperior" in shiny
    assert "evolved into Rhyperior" in shiny   # evolutions are milestones, kept
    assert "reached Lv.5" not in shiny         # level-ups dropped


def test_journal_shiny_filter_excludes_nonshiny_dupes(monkeypatch):
    _stub_journal(monkeypatch, [
        {"ts": 0, "kind": "caught", "text": "🎉 caught ✨ Rhyperior",
         "name": "Rhyperior", "rarity": "rare", "shiny": True},
        {"ts": 0, "kind": "caught", "text": "🎉 caught Staryu",  # a different, non-shiny catch
         "name": "Staryu", "rarity": "uncommon", "shiny": False},
    ])
    shiny = "\n".join(tui._journal_lines(shiny_only=True))
    assert "caught ✨ Rhyperior" in shiny
    assert "Staryu" not in shiny        # explicit non-shiny entry stays out


def test_journal_shiny_filter_follows_evolution_line(monkeypatch):
    # caught a shiny Charmander; its later Charizard evolution should still qualify
    _stub_journal(monkeypatch, [
        {"ts": 0, "kind": "caught", "text": "🎉 caught ✨ Charmander",
         "name": "Charmander", "rarity": "starter", "shiny": True},
        {"ts": 0, "kind": "evolved", "text": "🎊 evolved into Charizard Lv.36",
         "name": "Charizard"},  # legacy: no shiny field
    ])
    shiny = "\n".join(tui._journal_lines(shiny_only=True))
    assert "Charizard" in shiny


def test_journal_legendary_filter_keeps_encounters_drops_level_ups(monkeypatch):
    _stub_journal(monkeypatch, [
        {"ts": 0, "kind": "appeared", "text": "👀 a wild Mewtwo appeared!",
         "name": "Mewtwo", "rarity": "legendary", "shiny": False},
        {"ts": 0, "kind": "level", "text": "🆙 Mewtwo reached Lv.70", "name": "Mewtwo"},
        {"ts": 0, "kind": "caught", "text": "🎉 caught Pidgey",
         "name": "Pidgey", "rarity": "common", "shiny": False},
    ])
    rare = "\n".join(tui._journal_lines(rare_only=True))
    assert "Mewtwo appeared" in rare
    assert "reached Lv.70" not in rare   # level-ups dropped
    assert "Pidgey" not in rare


def test_scroll_frame_windows_the_body():
    body = [f"line{i}" for i in range(50)]
    frame = tui._scroll_frame("dex", body, top=10, height=5)
    assert "line10" in frame and "line14" in frame
    assert "line9" not in frame and "line15" not in frame


def test_dex_frame_is_dense_and_pageable():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))
    entries = tui._dex_entries(s)
    selected = next(i for i, e in enumerate(entries) if e["name"] == "Charmander")

    frame = tui._dex_frame(entries, selected=selected, top=0, height=18, width=80)

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
    entries = tui._dex_entries(s)

    caught = tui._dex_view_entries(entries, "dex", False, "caught")
    missing = tui._dex_view_entries(entries, "dex", False, "missing")
    caught_name_desc = tui._dex_view_entries(entries, "name", True, "caught")

    assert [e["name"] for e in caught] == ["Charmander", "Pidgey", "Abra"]
    assert "Charmander" not in {e["name"] for e in missing}
    assert [e["name"] for e in caught_name_desc] == ["Pidgey", "Charmander", "Abra"]

    psychic = tui._dex_view_entries(entries, "dex", False, "caught", query="psychic")
    assert [e["name"] for e in psychic] == ["Abra"]


def test_dex_frame_shows_filter_and_sort_controls():
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5))
    all_entries = tui._dex_entries(s)
    entries = tui._dex_view_entries(all_entries, "name", True, "caught")

    frame = tui._dex_frame(
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

    searched = tui._dex_frame(
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
    entries = tui._dex_entries(s)
    # include the ♀/♂ gendered species (uncaught) plus caught/uncaught mix
    names = {"Nidoran♀", "Nidoran♂", "Nidorino", "Nidoking", "Clefairy", "Vulpix", "Paras"}
    # The dex registers a species, so rows carry no level — only the fixed name
    # field and the one-letter rarity code, which must line up across every row.
    name_starts, code_cols = set(), set()
    for e in entries:
        if e["name"] not in names:
            continue
        visible = ANSI_RE.sub("", tui._dex_row(e, False, tui.DEX_LIST_W))
        assert visible[9:23].rstrip() == e["name"][:14]  # name field starts at a fixed column
        assert visible[24] == tui.RARITY_CODE[e["rarity"]]  # rarity code at a fixed column
        name_starts.add(9)
        code_cols.add(24)
    assert "Lv." not in visible  # no per-individual level in a species registry
    assert len(name_starts) == 1 and len(code_cols) == 1


def test_dex_entries_mark_caught_species():
    s = fresh()
    entries = tui._dex_entries(s)
    charmander = next(e for e in entries if e["name"] == "Charmander")
    pidgey = next(e for e in entries if e["name"] == "Pidgey")

    assert charmander["caught"]
    assert charmander["active"]
    assert not pidgey["caught"]


def test_dex_entries_use_national_dex_numbers():
    entries = tui._dex_entries(fresh())
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
