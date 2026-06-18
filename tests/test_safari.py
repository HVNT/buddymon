"""Safari Zone state machine + interactive encounter integration tests."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import data, engine, safari, state


class SeqRandom:
    """Deterministic rng: random() pops from a queue; randint returns fixed."""
    def __init__(self, randoms, ints=None):
        self._r = list(randoms)
        self._i = list(ints or [])

    def random(self):
        return self._r.pop(0)

    def randint(self, a, b):
        return self._i.pop(0) if self._i else a


def spawn(rarity="rare", name="Snorlax"):
    return {"name": name, "type": "Normal", "emoji": "😴",
            "rarity": rarity, "shiny": False}


def test_rock_doubles_c_angers_clears_eating():
    p = safari.start(spawn())
    p["eating"] = 3
    base = p["c"]
    safari.throw_rock(p, {"balls": 5}, SeqRandom([0.99], [2]))  # no flee
    assert p["c"] == base * 2
    assert p["angry"] == 2 - 1  # +2 then end-of-turn decrement
    assert p["eating"] == 0


def test_bait_halves_c_feeds_clears_angry():
    p = safari.start(spawn())
    p["angry"] = 4
    base = p["c"]
    safari.throw_bait(p, {"balls": 5}, SeqRandom([0.99], [3]))
    assert p["c"] == base // 2
    assert p["eating"] == 3 - 1
    assert p["angry"] == 0


def test_angry_expiry_resets_catch_rate():
    p = safari.start(spawn())
    base = p["c"]
    # rock with +1 anger; end-of-turn decrements to 0 -> C resets to base
    safari.throw_rock(p, {"balls": 5}, SeqRandom([0.99], [1]))
    assert p["angry"] == 0
    assert p["c"] == base  # snapped back even though rock doubled it


def test_eating_lowers_flee_angry_raises_it():
    rare = data.SAFARI["rare"]["flee_base"]
    neutral = safari._flee_probability(safari.start(spawn()))
    angry = safari._flee_probability({**safari.start(spawn()), "angry": 2, "eating": 0})
    eating = safari._flee_probability({**safari.start(spawn()), "angry": 0, "eating": 2})
    assert eating < neutral < angry
    assert neutral == rare


def test_ball_consumes_inventory_and_guards_zero():
    p = safari.start(spawn())
    trainer = {"balls": 1}
    safari.throw_ball(p, trainer, SeqRandom([0.99, 0.99]))  # miss, no flee
    assert trainer["balls"] == 0
    out = safari.throw_ball(p, trainer, SeqRandom([0.0]))  # would catch, but no balls
    assert out.get("no_balls") and not out["caught"]


def test_ball_catches_on_low_roll():
    p = safari.start(spawn())
    out = safari.throw_ball(p, {"balls": 3}, SeqRandom([0.0]))
    assert out["caught"] and out["done"]


def test_run_ends_without_catch():
    p = safari.start(spawn())
    out = safari.run(p, {"balls": 3}, SeqRandom([]))
    assert out["done"] and out.get("ran") and not out["caught"]


def test_roll_encounter_creates_pending_for_rare(monkeypatch):
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    state.active_pokemon(s)["level"] = 25
    # force a legendary-tier roll
    rng = SeqRandom(
        randoms=[0.0,        # spawn passes ENCOUNTER_CHANCE
                 ],
    )
    # easier: monkeypatch rarity path via a real Random seed that yields rare/legendary
    import random as _r
    found = False
    for seed in range(200):
        s2 = state.default_state()
        engine.create_starter(s2, "Charmander")
        state.active_pokemon(s2)["level"] = 25
        res = engine.roll_encounter(s2, _r.Random(seed))
        if res and res.get("outcome") == "appeared":
            assert s2.get("pending_encounter")
            assert s2["pending_encounter"]["rarity"] in data.INTERACTIVE_RARITIES
            # second roll must not overwrite the pending one
            res2 = engine.roll_encounter(s2, _r.Random(seed))
            assert res2 is None
            found = True
            break
    assert found, "no interactive spawn in 200 seeds"


def test_roll_encounter_auto_resolves_common():
    import random as _r
    for seed in range(200):
        s = state.default_state()
        engine.create_starter(s, "Charmander")
        res = engine.roll_encounter(s, _r.Random(seed))
        if res and res["rarity"] in ("common", "uncommon"):
            assert res["outcome"] in ("caught", "fled", "no_balls")
            assert "pending_encounter" not in s
            return
    raise AssertionError("no common encounter found")


def test_first_move_never_flees():
    # even with a guaranteed-flee rng roll, the opening move is safe
    p = safari.start(spawn(rarity="legendary"))
    out = safari.throw_rock(p, {"balls": 5}, SeqRandom([0.0], [3]))
    assert not out["fled"] and not out["done"]
    assert p["moves"] == 1


def test_second_move_can_flee():
    p = safari.start(spawn(rarity="legendary"))
    safari.throw_rock(p, {"balls": 5}, SeqRandom([0.0], [5]))  # move 1, safe
    out = safari.throw_rock(p, {"balls": 5}, SeqRandom([0.0], [5]))  # move 2, flees
    assert out["fled"] and out["done"]


def test_status_text_states():
    p = safari.start(spawn())
    assert "watching" in safari.status_text(p)
    p["angry"] = 2
    assert "angry" in safari.status_text(p)
    p["angry"], p["eating"] = 0, 3
    assert "eating" in safari.status_text(p)


def test_safari_cli_full_battle(tmp_path, monkeypatch):
    from lib import paths
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", tmp_path / "journal.jsonl")
    import buddymon

    s = state.default_state()
    engine.create_starter(s, "Charmander")
    s["trainer"]["balls"] = 10
    s["pending_encounter"] = safari.start(spawn(rarity="legendary", name="Mewtwo"))
    state.save(s)

    # a rock then balls until resolved; just assert the CLI never errors and
    # eventually clears the pending encounter
    buddymon.safari(["rock"])
    for _ in range(50):
        out = buddymon.safari(["ball"])
        if state.load().get("pending_encounter") is None:
            break
    assert state.load().get("pending_encounter") is None
    assert isinstance(out, str)
