from lib import paths, tui
from tests.tui_test_support import _stub_journal, fresh


def test_build_menu_frame_lists_all_items_and_marks_selection():
    frame = tui._build_menu_frame(tui.MENU, 0)
    for label, _ in tui.MENU:
        assert label in frame
    assert "▶" in frame  # selection cursor present
    assert "┌" in frame and "└" in frame
    assert "🔧  Settings" in frame
    assert "🏆  Showcase" in frame
    assert "team and active buddy" in frame


def test_status_lines_show_sprite_preview():
    s = fresh()
    lines = tui._status_lines(s)
    frame = "\n".join(lines)
    assert "Charmander" in frame
    assert "Tokens used" in frame
    assert "Pokédex" in frame
    assert "▀" in frame


def test_journal_lines_empty_is_graceful(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")
    lines = tui._journal_lines()
    assert lines and "No journal yet" in lines[0]


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
