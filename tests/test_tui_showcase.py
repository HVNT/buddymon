from lib import engine, state
from lib import tui_collections as collections_ui
from lib import tui_layout as layout
from lib import tui_runtime as runtime
from lib import tui_showcase as showcase_ui
from tests.tui_test_support import (
    ANSI_RE,
    _with_pidgeys,
    fresh,
    visible_width,
)


def test_showcase_empty_without_catches_is_a_trophy_room():
    s = state.default_state()
    frame = showcase_ui._showcase_frame(s, selected=0, width=80, height=60)
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
    frame = showcase_ui._showcase_frame(s, selected=1, width=80, height=24)
    plain = ANSI_RE.sub("", frame)

    assert "0/6 podiums filled" in plain
    assert "showing 1-2 of 6" in plain
    assert plain.count("open slot") == 2
    assert "slot 2: empty podium" in plain
    assert "enter choose" in plain
    assert "s Share Showcase" in plain
    assert "choose from Box" in plain
    edge = "+" + "-" * (layout.SHOWCASE_CARD_INNER_W + 2) + "+"
    card_rows = [line for line in frame.splitlines() if edge in ANSI_RE.sub("", line)]
    assert card_rows[0].startswith("    +")
    assert len(frame.splitlines()) <= 24
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_showcase_row_indent_does_not_bias_odd_slack_right():
    row_w = layout.SHOWCASE_CARD_W * 2 + layout.SHOWCASE_GAP

    assert row_w == 71
    assert showcase_ui._showcase_row_indent(80, 2) == 4
    assert showcase_ui._showcase_row_indent(81, 2) == 5


def test_showcase_frame_vertically_centers_when_roomy():
    s = fresh()
    height = 64
    frame = showcase_ui._showcase_frame(s, selected=0, width=80, height=height)
    plain = [ANSI_RE.sub("", line) for line in frame.splitlines()]
    nonblank = [i for i, line in enumerate(plain) if line.strip()]

    top_margin = nonblank[0]
    bottom_margin = height - 1 - nonblank[-1]
    assert abs(top_margin - bottom_margin) <= 1


def test_showcase_frame_can_show_share_notice():
    s = fresh()
    frame = showcase_ui._showcase_frame(
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
        showcase_ui._showcase_card_lines({"slot": 0, "pokemon": pokemon}, selected=True),
        showcase_ui._showcase_card_lines({"slot": 1, "pokemon": None}),
        showcase_ui._showcase_card_lines({"slot": 2, "pokemon": None, "missing": True}),
    ]

    for card in cards:
        assert all(visible_width(line) == layout.SHOWCASE_CARD_W for line in card)

    selected_plain = [ANSI_RE.sub("", line) for line in cards[0]]
    assert selected_plain[-3:] == [
        f"| {layout._center_ansi('#263', layout.SHOWCASE_CARD_INNER_W)} |",
        f"| {layout._center_ansi('Zigzagoon · Lv.15', layout.SHOWCASE_CARD_INNER_W)} |",
        "+" + "-" * (layout.SHOWCASE_CARD_INNER_W + 2) + "+",
    ]
    assert "shiny" not in "\n".join(selected_plain)
    assert "#1" not in "\n".join(selected_plain)


def test_showcase_text_art_centers_visible_pixels_not_source_padding(monkeypatch):
    def off_center_frame(_name, _ptype="Normal", _shiny=False):
        return [([
            ".........X",
            ".........X",
        ], {"X": "#f8d030"})]

    monkeypatch.setattr(showcase_ui.packs, "gen5_frames", off_center_frame)
    monkeypatch.setattr(runtime, "_graphics_enabled", False)

    body = showcase_ui._showcase_card_art({
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
    card_center = (layout.SHOWCASE_CARD_INNER_W - 1) / 2
    assert abs(content_center - card_center) <= 0.5


def test_showcase_graphics_art_uses_centered_fixed_aperture(monkeypatch):
    def narrow_frame(_name, _ptype="Normal", _shiny=False):
        return [([
            "X",
            "X",
        ], {"X": "#f8d030"})]

    monkeypatch.setattr(showcase_ui.packs, "gen5_frames", narrow_frame)
    monkeypatch.setattr(runtime, "_graphics_enabled", True)
    monkeypatch.setattr(runtime, "_cell_size", (10, 20))
    runtime.frame_images().clear()

    body = showcase_ui._showcase_card_art({
        "name": "Abra", "type": "Psychic", "shiny": False,
    })

    assert runtime.frame_images()[0][1:] == (
        layout.SHOWCASE_ART_W,
        layout.SHOWCASE_CARD_BODY_ROWS,
    )
    assert body[0].startswith("   \x01IMG0\x02")
    assert all(visible_width(line) == layout.SHOWCASE_CARD_INNER_W for line in body)


def test_showcase_debug_body_replaces_art_with_measurement_grid(monkeypatch):
    pokemon = engine.new_pokemon("Caterpie", "Bug", "🐛", "common", level=1)
    monkeypatch.setenv("BUDDYMON_SHOWCASE_DEBUG", "1")

    card = "\n".join(ANSI_RE.sub("", line) for line in showcase_ui._showcase_card_lines({
        "slot": 0,
        "pokemon": pokemon,
    }))

    assert "src " in card
    assert "fit " in card
    assert "bbox " in card
    assert "mass " in card


def test_showcase_png_canvas_centers_visible_sprite_bounds(monkeypatch):
    monkeypatch.setattr(runtime, "_graphics_enabled", True)
    monkeypatch.setattr(runtime, "_cell_size", (10, 20))

    for name, ptype, shiny in (
        ("Caterpie", "Bug", False),
        ("Linoone", "Normal", False),
        ("Rhyperior", "Ground", False),
        ("Zigzagoon", "Normal", True),
        ("Staravia", "Flying", False),
        ("Staryu", "Water", True),
        ("Pidove", "Flying", True),
    ):
        grid, palette = showcase_ui.packs.gen5_frames(name, ptype, shiny)[0]
        grid = layout._crop_grid_to_content(grid, palette)
        src_h, src_w = len(grid), len(grid[0])
        png_w = layout.SHOWCASE_ART_W * 10
        png_h = layout.SHOWCASE_CARD_BODY_ROWS * 20
        max_sprite_w = layout.SHOWCASE_SPRITE_W * 10
        max_sprite_h = layout.SHOWCASE_SPRITE_ROWS * 20
        scale = min(max_sprite_w / src_w, max_sprite_h / src_h)
        art = showcase_ui.pixels.nearest(
            grid,
            max(1, round(src_w * scale)),
            max(1, round(src_h * scale)),
        )
        centered = layout._pad_grid_alpha_center(art, palette, png_w, png_h)
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

    frame = showcase_ui._showcase_frame(s, selected=1, width=80, height=24)
    plain = ANSI_RE.sub("", frame)

    assert "1/6 podiums filled · 1 missing" in plain
    assert "Pidgey Lv.5" in plain
    assert "#016" in plain
    assert "missing" in plain
    assert "slot 2: Pidgey Lv.5" in plain


def test_showcase_frame_stacks_on_narrow_terminal():
    s = fresh()
    frame = showcase_ui._showcase_frame(s, selected=0, width=40, height=24)
    body = [line for line in frame.splitlines() if "arrows move" not in line]
    plain = ANSI_RE.sub("", frame)

    assert "showing 1-1 of 6" in plain
    assert len(frame.splitlines()) <= 24
    assert all(visible_width(line) <= 40 for line in body)
    assert plain.count("open slot") == 1


def test_showcase_frame_pages_to_selected_row():
    s = fresh()
    frame = showcase_ui._showcase_frame(s, selected=5, width=80, height=24)
    plain = ANSI_RE.sub("", frame)

    assert "showing 5-6 of 6" in plain
    assert "slot 6: empty podium" in plain
    assert len(frame.splitlines()) <= 24
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_showcase_frame_uses_compact_rows_when_cards_cannot_fit():
    s = fresh()
    frame = showcase_ui._showcase_frame(s, selected=4, width=80, height=14)
    plain = ANSI_RE.sub("", frame)

    assert "compact view" in plain
    assert "> 5. empty podium" in plain
    assert len(frame.splitlines()) <= 14
    assert all(visible_width(line) <= 80 for line in frame.splitlines())


def test_showcase_choose_frame_lists_box_copies():
    s = _with_pidgeys(fresh(), 2, [3, 1])
    expanded = collections_ui.box.expand(s["pokemon"])
    frame = showcase_ui._showcase_choose_frame(
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

    frame = showcase_ui._showcase_choose_frame(s, selected=0, width=80, query="psychic")
    plain = ANSI_RE.sub("", frame)
    assert "search: psychic" in plain
    assert "Abra" in plain and "Pidgey" not in plain

    empty = showcase_ui._showcase_choose_frame(s, selected=0, width=80, query="water")
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
    assert showcase_ui._fresh_showcase_selection_id(fresh_list, selected_id) == selected_id
    assert showcase_ui._fresh_showcase_selection_id(fresh_list, "gone") is None
