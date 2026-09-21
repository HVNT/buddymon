import pytest

from lib import engine, iv, state


@pytest.mark.parametrize(("pokemon_id", "expected"), [
    ("copy-001", iv.Appraisal(15, 8, 5, 28, 62, 1)),
    ("00000000", iv.Appraisal(8, 4, 9, 21, 47, 0)),
    ("hitmonchan-100", iv.Appraisal(8, 9, 14, 31, 69, 2)),
    ("perfect-16325", iv.Appraisal(15, 15, 15, 45, 100, 4)),
])
def test_appraise_has_stable_hash_vectors(pokemon_id, expected):
    assert iv.appraise(pokemon_id) == expected


def test_appraisal_values_stay_in_pokemon_go_bounds():
    for index in range(10_000):
        appraisal = iv.appraise(f"copy-{index}")
        assert 0 <= appraisal.attack <= iv.STAT_MAX
        assert 0 <= appraisal.defense <= iv.STAT_MAX
        assert 0 <= appraisal.hp <= iv.STAT_MAX
        assert appraisal.total == appraisal.attack + appraisal.defense + appraisal.hp
        assert appraisal.percent == iv._percent_for_total(appraisal.total)
        assert 0 <= appraisal.stars <= iv.STAR_MAX


@pytest.mark.parametrize(("total", "stars"), [
    (0, 0), (22, 0),
    (23, 1), (29, 1),
    (30, 2), (36, 2),
    (37, 3), (44, 3),
    (45, 4),
])
def test_star_thresholds(total, stars):
    assert iv._stars_for_total(total) == stars


def test_perfect_appraisal_uses_the_total_limit():
    perfect = iv.appraise("perfect-16325")

    assert perfect.total == iv.TOTAL_MAX
    assert perfect.is_perfect
    assert not iv.appraise("copy-001").is_perfect


@pytest.mark.parametrize("pokemon_id", ["", "   ", None, 42])
def test_appraise_rejects_invalid_ids(pokemon_id):
    with pytest.raises(ValueError, match="pokemon_id"):
        iv.appraise(pokemon_id)


def test_appraisal_is_derived_without_mutating_persisted_state():
    game_state = state.default_state()
    pokemon = engine.new_pokemon("Hitmonchan", "Fighting", "🥊", "rare", level=100)
    pokemon["id"] = "hitmonchan-100"
    game_state["pokemon"].append(pokemon)
    before = {**pokemon}

    first = iv.appraise(pokemon["id"])
    assert pokemon == before
    changed = {
        **pokemon,
        "name": "Pikachu",
        "type": "Electric",
        "level": 1,
        "shiny": True,
    }
    second = iv.appraise(changed["id"])

    assert first == second
    assert "iv" not in pokemon
    assert game_state["version"] == state.STATE_VERSION == 5
