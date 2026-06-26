"""TUI frame builders (pure, terminal-free) + non-tty guard."""
import contextlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import battle, data, engine, render, state, tui


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def fresh():
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    return s


def visible_width(line):
    return len(ANSI_RE.sub("", line))


def test_menu_frame_lists_all_items_and_marks_selection():
    frame = tui._menu_frame(tui.MENU, 0)
    for label, _ in tui.MENU:
        assert label in frame
    assert "▶" in frame  # selection cursor present
    assert "┌" in frame and "└" in frame
    assert "🔧  Settings" in frame
    assert "team and active buddy" in frame


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


def test_party_marks_favorites_and_filters_to_them():
    s = fresh()  # Charmander starter is auto-favorited
    plain = engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=5)
    s["pokemon"].append(plain)  # a non-favorite
    frame = tui._party_frame(s, 0, width=80)
    assert "♥" in frame  # favorite marker rendered for the starter

    fav = tui._party_frame(s, 0, width=80, fav_only=True)
    assert "Charmander" in fav      # the favorite shows
    assert "Pidgey" not in fav      # the non-favorite is filtered out


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
    monkeypatch.setattr(tui.journal, "tail", lambda n=200: entries)


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
