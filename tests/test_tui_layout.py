from lib import iv, state
from lib import tui_layout as layout
from tests.tui_test_support import ANSI_RE, fresh, visible_width


def test_search_key_edits_and_clears_query():
    query, active, handled = layout._search_key("/", "", False)
    assert (query, active, handled) == ("", True, True)

    query, active, handled = layout._search_key("a", query, active)
    assert (query, active, handled) == ("a", True, True)

    query, active, handled = layout._search_key("space", query, active)
    assert (query, active, handled) == ("a ", True, True)

    query, active, handled = layout._search_key("b", query, active)
    assert (query, active, handled) == ("a b", True, True)

    query, active, handled = layout._search_key("\x7f", query, active)
    assert (query, active, handled) == ("a ", True, True)

    query, active, handled = layout._search_key("enter", query, active)
    assert (query, active, handled) == ("a ", False, True)

    query, active, handled = layout._search_key("esc", query, active)
    assert (query, active, handled) == ("", False, True)


def test_query_matches_all_terms_case_insensitive():
    assert layout._query_matches("char fire", "Charmander", "Fire", "starter")
    assert not layout._query_matches("char water", "Charmander", "Fire", "starter")


def test_encounter_sprite_lines_use_fixed_portrait_box_roster(monkeypatch):
    def oversized_frames(_name, _ptype="Normal", _shiny=False):
        grid = ["X" * (layout.ENCOUNTER_ART_W + 12)] * (layout.ENCOUNTER_ART_H + 10)
        return [(grid, {"X": "#f08030"})]

    monkeypatch.setattr(layout.packs, "gen5_frames", oversized_frames)

    lines = layout._encounter_sprite_lines({
        "name": "Charizard", "type": "Fire", "emoji": "🐉", "shiny": False,
    })

    assert len(lines) == layout.ENCOUNTER_ART_H // 2
    assert all(visible_width(line) == layout.ENCOUNTER_ART_W for line in lines)


def test_roomy_terminal_unlocks_larger_sprite_budgets():
    assert layout.encounter_art_size(88, 30) == (28, 24)
    assert layout.encounter_art_size(100, 34) == (36, 30)
    assert layout.select_art_size(88, 30) == (36, 32)
    assert layout.select_art_size(112, 38) == (44, 40)


def test_sprite_card_centers_visible_pixels_not_source_padding(monkeypatch):
    def off_center_frame(_name, _ptype="Normal", _shiny=False):
        return [([
            ".........X",
            ".........X",
        ], {"X": "#f8d030"})]

    monkeypatch.setattr(layout.packs, "gen5_frames", off_center_frame)

    lines = layout._sprite_card_lines({"name": "Abra", "type": "Psychic", "shiny": False})
    bbox = layout._sprite_card_content_offset(lines)

    assert bbox is not None
    left, _, right, _ = bbox
    content_center = (left + right - 1) / 2
    card_center = (layout.SELECT_CARD_INNER_W - 1) / 2
    assert abs(content_center - card_center) <= 0.5


def test_sprite_card_uses_fixed_dimensions_for_different_species():
    species = [
        {"name": "Abra", "type": "Psychic", "shiny": False},
        {"name": "Audino", "type": "Normal", "shiny": False},
        {"name": "Baltoy", "type": "Ground", "shiny": False},
        {"name": "Blissey", "type": "Normal", "shiny": False},
    ]
    cards = [layout._sprite_card_lines(p) for p in species]
    visible_shapes = {
        (len(card), tuple(visible_width(line) for line in card))
        for card in cards
    }

    assert len(visible_shapes) == 1
    assert len(cards[0]) == layout.SELECT_CARD_INNER_ROWS + 2
    assert visible_width(cards[0][0]) == layout.SELECT_CARD_INNER_W + 4


def test_pokemon_detail_card_attaches_metadata_inside_one_border():
    s = fresh()
    p = state.active_pokemon(s)

    card = layout._pokemon_detail_card_lines(p, s["active"], art_h=24)
    plain = "\n".join(ANSI_RE.sub("", line) for line in card)

    assert all(line.startswith(("+", "|")) for line in card)
    assert all(visible_width(line) == visible_width(card[0]) for line in card)
    assert sum(1 for line in card if line.startswith("+")) == 3
    assert "+-- Charmander Lv.1" in plain
    assert "#004 · Fire · starter" in plain
    assert "XP " in plain
    assert "active buddy" not in plain
    assert "press enter to make active" not in plain


def test_appraisal_block_uses_inset_dots_and_fixed_width_for_every_value():
    appraisals = [
        iv.Appraisal(value, value, value, value * 3, (value * 300 + 22) // 45,
                     iv._stars_for_total(value * 3))
        for value in range(16)
    ] + [
        iv.Appraisal(0, 0, 0, total, (total * 100 + 22) // 45,
                     iv._stars_for_total(total))
        for total in range(46)
    ]

    for appraisal in appraisals:
        lines = layout._appraisal_lines(appraisal, layout.SELECT_CARD_INNER_W)
        plain = [ANSI_RE.sub("", line) for line in lines]
        assert all(visible_width(line) == layout.SELECT_CARD_INNER_W + 4 for line in lines)
        assert plain[0] == "|  " + "." * 40 + "  |"
        assert "Appraisal" not in "\n".join(plain)


def test_appraisal_block_renders_perfect_score_and_grouped_bars():
    lines = layout._appraisal_lines(
        iv.Appraisal(15, 15, 15, 45, 100, 4),
        layout.SELECT_CARD_INNER_W,
    )
    plain = "\n".join(ANSI_RE.sub("", line) for line in lines)

    assert "IV 100%" in plain
    assert "TOTAL 45/45" in plain
    assert "[****]" in plain
    assert "ATK 15 [#####|#####|#####]" in plain
    assert "DEF 15 [#####|#####|#####]" in plain
    assert "HP  15 [#####|#####|#####]" in plain


def test_box_detail_card_fits_longest_name_level_shiny_and_perfect_iv():
    pokemon = {
        "id": "perfect-16325",
        "name": "Hitmonchan",
        "type": "Fighting",
        "rarity": "rare",
        "level": 100,
        "xp": 0,
        "next_xp": 100,
        "shiny": True,
    }

    card = layout._pokemon_detail_card_lines(
        pokemon,
        active_id=None,
        art_h=24,
        caught_line="caught September 03, 2026 · copy 999/999",
        show_iv=True,
    )
    plain = "\n".join(ANSI_RE.sub("", line) for line in card)

    assert "+-- shiny Hitmonchan Lv.100" in plain
    assert "#107 · Fighting · rare" in plain
    assert "IV 100%" in plain and "[****]" in plain
    assert all(visible_width(line) == layout.SELECT_CARD_INNER_W + 4 for line in card)


def test_encounter_title_accepts_legacy_battle_wild_level():
    title = layout._encounter_title({"name": "Beldum", "wild_level": 19}, with_level=True)
    assert title == "Beldum Lv.19"
