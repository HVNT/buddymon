"""Battle Mode: combat state machine, mode gating, scene HP + throw render."""
import base64
import random
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import battle, data, engine, packs, png, scene, state


class SeqRandom:
    def __init__(self, randoms=(), uniforms=()):
        self._r, self._u = list(randoms), list(uniforms)

    def random(self):
        return self._r.pop(0) if self._r else 0.5

    def uniform(self, a, b):
        return self._u.pop(0) if self._u else (a + b) / 2

    def randint(self, a, b):
        return a


def spawn(rarity="common", name="Pidgey", ptype="Flying"):
    return {"name": name, "type": ptype, "emoji": "🐦", "rarity": rarity, "shiny": False}


def fresh(level=20, starter="Charmander"):
    s = state.default_state()
    engine.create_starter(s, starter)
    state.active_pokemon(s)["level"] = level
    return s


def test_start_sets_hp_from_levels():
    buddy = {"level": 20}
    p = battle.start(spawn(), buddy)
    assert p["buddy_hp"] == p["buddy_hp_max"] > 0
    assert p["wild_hp"] == p["wild_hp_max"] > 0
    assert p["wild_level"] >= 1


def test_attack_lowers_wild_and_can_ko():
    buddy = {"level": 20}
    p = battle.start(spawn(), buddy)
    p["wild_hp"] = 3  # nearly dead
    out = battle.attack(p, buddy, {}, SeqRandom(uniforms=[1.5, 0.5]))
    assert out["done"] and out["outcome"] == "ko" and not out["caught"]


def test_buddy_faint_flees_and_full_revives():
    buddy = {"level": 20}
    p = battle.start(spawn(), buddy)
    p["buddy_hp"] = 1
    # attack doesn't KO wild (wild has full HP), then wild turn faints buddy
    out = battle.attack(p, buddy, {}, SeqRandom(uniforms=[0.8, 1.1]))
    assert out["done"] and out["outcome"] == "buddy_faint"
    assert p["buddy_hp"] == p["buddy_hp_max"]  # full revive


def test_catch_probability_rises_as_hp_drops():
    buddy = {"level": 20}
    p = battle.start(spawn("common"), buddy)
    full = battle.catch_probability(p)
    p["wild_hp"] = 1
    low = battle.catch_probability(p)
    assert low > full
    assert low <= data.BATTLE["catch_cap"]


def test_throw_catches_and_balls_are_infinite():
    buddy = {"level": 20}
    p = battle.start(spawn(), buddy)
    trainer = {"balls": 0}  # no balls — battle mode ignores supply
    out = battle.throw_ball(p, buddy, trainer, SeqRandom(randoms=[0.0]))  # 0.0 < prob -> catch
    assert out["caught"] and out["done"]
    assert trainer["balls"] == 0  # never decremented
    assert p["last_throw"]["caught"] is True


def test_throw_break_free_continues():
    buddy = {"level": 20}
    p = battle.start(spawn(), buddy)
    out = battle.throw_ball(p, buddy, {}, SeqRandom(randoms=[0.99, 0.5], uniforms=[0.5]))
    assert not out["caught"] and not out["done"]  # broke free, wild took its turn
    assert p["last_throw"]["caught"] is False


def test_run_ends():
    out = battle.run(battle.start(spawn(), {"level": 10}), {"level": 10}, {}, SeqRandom())
    assert out["done"] and out["outcome"] == "ran"


def test_roll_encounter_battle_mode_makes_any_wild_a_battle():
    import random as _r
    for seed in range(200):
        s = fresh()
        s["mode"] = "battle"
        res = engine.roll_encounter(s, _r.Random(seed))
        if res and res["outcome"] == "appeared":
            assert s.get("pending_battle") and not s.get("pending_encounter")
            # second spawn suppressed while one is pending
            assert engine.roll_encounter(s, _r.Random(seed)) is None
            return
    raise AssertionError("no battle spawn in 200 seeds")


def test_auto_mode_unchanged_by_battle_code():
    import random as _r
    for seed in range(200):
        s = fresh()  # default mode auto
        res = engine.roll_encounter(s, _r.Random(seed))
        if res and res["rarity"] in ("common", "uncommon"):
            assert res["outcome"] in ("caught", "fled", "no_balls")
            assert "pending_battle" not in s
            return
    raise AssertionError("no common encounter found")


def test_battle_screen_hp_bars_scale():
    buddy = (["BB" * 12] * 24, {"B": "#f08030"})
    wild = (["WW" * 12] * 24, {"W": "#58a8e8"})
    full = scene.battle_screen(buddy, wild, "active", wild_hp_frac=1.0, buddy_hp_frac=1.0)
    low = scene.battle_screen(buddy, wild, "active", wild_hp_frac=0.1, buddy_hp_frac=0.5)
    for g, pal in (full, low):
        assert png.grid_to_png(g, pal)[:1] == b"\x89"

    hp_colors = {scene._HP_GREEN, scene._HP_YELLOW, scene._HP_RED}

    def hp_cells(grid, palette):
        hp_chars = {ch for ch, hx in palette.items() if hx in hp_colors}
        return sum(row.count(ch) for row in grid for ch in hp_chars)

    assert hp_cells(*low) < hp_cells(*full)  # wild HP low → shorter fill


def test_throw_jiggle_bar_renders_all_phases():
    buddy = (["BB" * 8] * 14, {"B": "#f08030"})
    wild = (["WW" * 8] * 14, {"W": "#58a8e8"})
    for caught in (True, False):
        lt = {"jiggles": 3, "caught": caught, "ts": 0}
        for phase in range(scene.THROW_SECS):
            g, pal = scene.throw_jiggle_bar(buddy, wild, phase, lt)
            assert all(len(r) == 44 for r in g)
            assert png.grid_to_png(g, pal)[:1] == b"\x89"
    assert scene.throw_phase_for(scene.THROW_SECS) is None


def test_take_turn_resolves_safely(tmp_path, monkeypatch):
    # take_turn is the shared path for the dropdown commands AND the TUI; it must
    # apply the catch and clear pending without real journal writes / notifications.
    from lib import notify, paths, safari
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "j.jsonl")
    monkeypatch.setattr(notify, "notify", lambda *a, **k: None)

    # battle: a successful throw adds the wild and clears pending_battle
    s = fresh(level=20)
    s["pending_battle"] = battle.start(spawn("rare", "Beldum", "Steel"),
                                       state.active_pokemon(s))
    n = len(s["pokemon"])
    outcome, _ = battle.take_turn(s, "ball", SeqRandom(randoms=[0.0]))  # 0.0 < prob → catch
    assert outcome["caught"] and "pending_battle" not in s
    assert len(s["pokemon"]) == n + 1

    # safari: running clears pending_encounter without catching
    s2 = fresh()
    s2["pending_encounter"] = safari.start(
        {"name": "Beldum", "type": "Steel", "emoji": "⚙️", "rarity": "rare"})
    out2, _ = safari.take_turn(s2, "run", SeqRandom())
    assert out2["done"] and "pending_encounter" not in s2


def test_recent_encounter_recap_stays_out_of_swiftbar_dropdown(tmp_path, monkeypatch):
    """The top bar owns short encounter cutscenes; the dropdown skips recap art
    so SwiftBar does not keep re-rendering a heavy image after the event."""
    import time
    from lib import paths, journal
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")
    import buddymon
    now = time.time()
    journal.append("caught", "caught Mamoswine", {"name": "Mamoswine", "rarity": "rare"})
    s = fresh()

    # Recent encounters should not add a heavy dropdown image.
    recap = buddymon._last_encounter_section(s, now)
    assert recap == []

    # A live Safari encounter still does not get an extra recap stacked below it.
    s["pending_encounter"] = {"name": "Beldum", "type": "Steel", "shiny": False}
    assert buddymon._last_encounter_section(s, now) == []

    # Same for a live Battle-Mode encounter.
    del s["pending_encounter"]
    s["pending_battle"] = {"name": "Beldum", "type": "Steel", "shiny": False}
    assert buddymon._last_encounter_section(s, now) == []


def test_battle_scene_image_uses_dropdown_scale():
    import buddymon
    buddy = buddymon._battle_sprite("Charmander", "Fire", False)
    wild = buddymon._battle_sprite("Beldum", "Steel", False)
    grid, palette = scene.battle_screen(
        buddy, wild, "active", options=["FIGHT", "BALL", "RUN"])

    raw = base64.b64decode(buddymon._battle_scene_image(grid, palette))
    width, height = struct.unpack(">II", raw[16:24])

    assert width == len(grid[0]) * buddymon.BATTLE_IMAGE_SCALE
    assert height == len(grid) * buddymon.BATTLE_IMAGE_SCALE
    assert buddymon.BATTLE_IMAGE_SCALE == 2


def test_recent_evolution_notice_persists_after_animation(tmp_path, monkeypatch):
    import buddymon
    from lib import journal, paths

    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")
    s = fresh(level=36)
    buddy = state.active_pokemon(s)
    buddy["name"], buddy["emoji"] = "Charizard", "🐉"
    entry = journal.append("evolved", "evolved into Charizard",
                           {"name": "Charizard", "level": 36, "source": "claude"})
    notice_ts = entry["ts"] + scene.EVOLUTION_SECS + 1
    monkeypatch.setattr(buddymon.time, "time",
                        lambda: notice_ts)
    monkeypatch.setattr(
        buddymon.state, "read_event",
        lambda name: (
            {"detail": "+11429 progress", "ts": notice_ts}
            if name == "cross" else {}
        ),
    )

    bar = buddymon._bar_line(s, buddy, [], 0)
    dropdown = buddymon._dropdown_lines(s, buddy, [])

    assert "🎊 CHARIZARD!" in bar
    assert any("evolved into Charizard Lv.36" in line for line in dropdown)
    assert any(f"color={buddymon.EVOLUTION_NOTICE_COLOR}" in line for line in dropdown)
    assert any("+11429 progress" in line for line in dropdown)
    assert any(f"color={buddymon.EVENT_NOTICE_COLOR}" in line for line in dropdown)
    assert buddymon.EVOLUTION_NOTICE_COLOR == "#4c1d95"
    assert buddymon.EVENT_NOTICE_COLOR == "#1e3a8a"


def test_switch_submenu_child_rows_carry_no_png():
    # Per-row base64 PNGs made SwiftBar hoard ~90 images and leak >1GB RAM, so
    # the child rows must stay PNG-free. A cheap SF Symbol (sfimage=) on the
    # parent is fine — it's a native glyph, not image data.
    import buddymon
    s = fresh()
    s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=4))

    lines = buddymon._switch_submenu(s, state.active_pokemon(s)["name"])

    assert lines[0].startswith("Switch buddy")
    child_rows = [ln for ln in lines if ln.startswith("--")]
    assert any("Pidgey" in ln and "Lv.4" in ln and "param2=switch" in ln
               for ln in child_rows)
    assert all("image=" not in ln for ln in child_rows)  # no PNG on the 1-per-species rows


def test_gender_symbol_is_binary_and_stable():
    from lib import render
    p = engine.new_pokemon("Charmeleon", "Fire", "🔥", "starter")
    g = render.gender_symbol(p)
    assert g in ("♂", "♀")
    assert render.gender_symbol(p) == g  # deterministic for the same id
    assert render.gender_symbol(engine.new_pokemon("Pidgey", "Flying", "🐦", "common")) in ("♂", "♀")
