"""Dex-wide evolution table + engine integration."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import data, engine, state
from lib.evolutions import EVOLUTIONS


def test_table_spot_checks():
    assert EVOLUTIONS["Charmander"] == [("Charmeleon", 16)]
    assert EVOLUTIONS["Charmeleon"] == [("Charizard", 36)]
    assert EVOLUTIONS["Ivysaur"] == [("Venusaur", 32)]   # canonical (was 36 bug)
    assert EVOLUTIONS["Magikarp"] == [("Gyarados", 20)]
    assert EVOLUTIONS["Gastly"][0][0] == "Haunter"
    assert len(EVOLUTIONS["Eevee"]) >= 3                 # branches


def test_no_target_beyond_dex_649():
    roster = set(data.WILDS) | {n for n, _ in data.EEVEE_BRANCHES}
    roster |= set(data.STARTERS)
    for info in data.STARTERS.values():
        roster |= {n for n, _, _ in info["evolutions"]}
    for src, targets in EVOLUTIONS.items():
        for to_name, _ in targets:
            assert data.species_info(to_name) != ("Normal", "🔵") or to_name in roster, to_name


def test_check_evolution_threshold():
    mag = {"name": "Magikarp", "level": 19}
    assert engine.check_evolution(mag, random.Random(1)) is None
    mag["level"] = 20
    assert engine.check_evolution(mag, random.Random(1)) == ("Gyarados", data.species_info("Gyarados")[1])


def test_branch_picks_eligible_target():
    eevee = {"name": "Eevee", "level": 30}
    valid = {to for to, _ in EVOLUTIONS["Eevee"]}
    for seed in range(8):
        got = engine.check_evolution(eevee, random.Random(seed))
        assert got is not None and got[0] in valid


def test_wild_line_evolves_via_award_xp():
    s = state.default_state()
    p = engine.new_pokemon("Magikarp", "Water", "🐟", "common", level=1)
    s["pokemon"].append(p)
    s["active"] = p["id"]
    engine.award_xp(s, engine.xp_for_level(25), random.Random(3))
    assert state.active_pokemon(s)["name"] == "Gyarados"


def test_multi_stage_in_one_award():
    s = state.default_state()
    p = engine.new_pokemon("Caterpie", "Bug", "🐛", "common", level=1)
    s["pokemon"].append(p)
    s["active"] = p["id"]
    engine.award_xp(s, engine.xp_for_level(20), random.Random(1))
    # Caterpie(7)->Metapod(10)->Butterfree in a single big award
    assert state.active_pokemon(s)["name"] == "Butterfree"


def test_species_info_resolves_evolved_forms():
    assert data.species_info("Charizard")[1]  # emoji, not the fallback
    assert data.species_info("Raichu")[0] == "Electric"
    assert data.species_info("Gyarados")[0] == "Water"
