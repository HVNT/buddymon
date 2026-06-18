"""Battle Mode: combat state machine, mode gating, scene HP + throw render."""
import random
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

    def green_cells(grid, palette):
        hp_chars = {ch for ch, hx in palette.items() if hx == scene._HP}
        return sum(row.count(ch) for row in grid for ch in hp_chars)

    assert green_cells(*low) < green_cells(*full)  # wild HP low → less green


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
