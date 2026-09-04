import contextlib

from lib import battle, state, tui
from lib import tui_runtime as runtime
from tests.tui_test_support import fresh, visible_width


def test_menu_gains_fight_entry_when_a_wild_is_pending():
    s = fresh()
    assert all(action != "encounter" for _, action in tui._menu_items(s))
    s["pending_encounter"] = {"name": "Beldum", "type": "Steel", "shiny": False}
    items = tui._menu_items(s)
    assert items[0][1] == "encounter" and "Beldum" in items[0][0]


def test_render_encounter_frame_shows_options_and_status():
    s = fresh()
    s["pending_encounter"] = {
        "name": "Beldum", "type": "Steel", "emoji": "⚙️", "rarity": "rare",
        "shiny": False, "level": 20, "c": 90, "base_c": 90,
        "angry": 0, "eating": 0,
        "balls_thrown": 0, "moves": 0, "last_msg": "A wild Beldum appeared!",
    }
    frame = tui.render_encounter_frame(s, "safari", 0)
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


def test_roomy_encounter_uses_more_art_without_overflow():
    s = fresh()
    s["pending_encounter"] = {
        "name": "Beldum", "type": "Steel", "emoji": "⚙️", "rarity": "rare",
        "shiny": False, "level": 20, "c": 90, "base_c": 90,
        "angry": 0, "eating": 0, "balls_thrown": 0, "moves": 0,
        "last_msg": "A wild Beldum appeared!",
    }

    compact = tui.render_encounter_frame(s, "safari", 0, width=88, height=30)
    roomy = tui.render_encounter_frame(s, "safari", 0, width=112, height=38)

    assert len(roomy.splitlines()) > len(compact.splitlines())
    assert len(roomy.splitlines()) <= 38
    assert all(visible_width(line) <= 112 for line in roomy.splitlines())


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

    monkeypatch.setattr(runtime, "draw_frame", drawn.append)
    monkeypatch.setattr(runtime, "read_key", read_key)
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
    monkeypatch.setattr(runtime, "draw_frame", drawn.append)
    monkeypatch.setattr(tui.select, "select", lambda *_args: ([], [], []))
    monkeypatch.setattr(
        runtime,
        "read_key",
        lambda: (_ for _ in ()).throw(AssertionError("should not require a key")),
    )

    tui._flash_result("Done", timeout=0)

    assert any("Done" in frame for frame in drawn)
