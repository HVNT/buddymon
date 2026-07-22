from lib import data, state, trainer_card


def pokemon(name, *, ptype="Normal", rarity="common", shiny=False, pokemon_id=None):
    return {
        "id": pokemon_id or name.lower().replace(" ", "-"),
        "name": name,
        "type": ptype,
        "rarity": rarity,
        "shiny": shiny,
    }


def badge_map(card):
    return {badge["id"]: badge for badge in card["badges"]}


def national_state(*, shiny=False):
    game_state = state.default_state()
    for name in sorted(data.DEX_NUMBERS, key=data.DEX_NUMBERS.get):
        ptype, _emoji, rarity = data.WILDS.get(
            name,
            ("Normal", "", "starter" if name in data.STARTERS else "common"),
        )
        game_state["pokemon"].append(
            pokemon(
                name,
                ptype=ptype,
                rarity=rarity,
                shiny=shiny,
                pokemon_id=f"dex-{data.DEX_NUMBERS[name]}",
            )
        )
    game_state["active"] = game_state["pokemon"][0]["id"]
    return game_state


def test_trainer_card_uses_trainer_facts_without_inventing_a_level():
    game_state = state.default_state()
    game_state["trainer"]["total_tokens"] = 12_400_000_000
    game_state["pokemon"] = [
        pokemon("Pikachu", ptype="Electric"),
        pokemon("Pikachu", ptype="Electric", pokemon_id="pikachu-2"),
        pokemon("Eevee"),
    ]

    card = trainer_card.build(game_state, entries=[], username="hunt")

    assert card["name"] == "HUNT"
    assert len(card["id_no"]) == 5
    assert card["id_no"].isdigit()
    assert card["facts"] == [
        {"id": "name", "label": "NAME", "value": "HUNT"},
        {"id": "tokens", "label": "TOKENS", "value": "12.4B"},
        {"id": "pokedex", "label": "POKÉDEX", "value": "2 / 649"},
        {"id": "caught", "label": "CAUGHT", "value": "3"},
    ]
    assert card["trainer_stats"] == [
        {"id": "mode", "label": "MODE", "value": "QUICK"},
        {"id": "streak", "label": "STREAK", "value": "0D"},
        {"id": "balls", "label": "BALLS", "value": "10"},
        {"id": "shiny", "label": "SHINY", "value": "0"},
    ]
    assert "level" not in card
    assert "total_xp" not in card


def test_trainer_stats_summarize_gameplay_readiness_and_collection():
    game_state = state.default_state()
    game_state["mode"] = "safari"
    game_state["trainer"]["streak"] = 42
    game_state["trainer"]["balls"] = 1_200
    game_state["pokemon"] = [
        pokemon("Pikachu", ptype="Electric", shiny=True),
        pokemon("Eevee"),
        pokemon("Eevee", shiny=True, pokemon_id="shiny-eevee"),
    ]

    card = trainer_card.build(game_state, entries=[], username="hunt")

    assert card["trainer_stats"] == [
        {"id": "mode", "label": "MODE", "value": "SAFARI"},
        {"id": "streak", "label": "STREAK", "value": "42D"},
        {"id": "balls", "label": "BALLS", "value": "1.2K"},
        {"id": "shiny", "label": "SHINY", "value": "2"},
    ]

    game_state["mode"] = "battle"
    battle_card = trainer_card.build(game_state, entries=[], username="hunt")
    assert battle_card["trainer_stats"][2] == {
        "id": "balls",
        "label": "BALLS",
        "value": "∞",
    }


def test_trainer_card_id_is_stable_for_the_same_local_identity():
    game_state = state.default_state()
    game_state["pokemon"] = [pokemon("Eevee", pokemon_id="stable-first")]

    first = trainer_card.build(game_state, entries=[], username="hunt")
    second = trainer_card.build(game_state, entries=[], username="hunt")

    assert first["id_no"] == second["id_no"]


def test_feature_badges_use_collection_showcase_and_journal_evidence():
    game_state = state.default_state()
    by_type = {}
    for name, (ptype, _emoji, rarity) in data.WILDS.items():
        by_type.setdefault(ptype, (name, ptype, rarity))
    game_state["pokemon"] = [
        pokemon(name, ptype=ptype, rarity=rarity, pokemon_id=f"type-{index}")
        for index, (name, ptype, rarity) in enumerate(by_type.values())
    ]
    game_state["pokemon"].append(
        pokemon("Mewtwo", ptype="Psychic", rarity="legendary", shiny=True)
    )
    game_state["showcase"] = {
        "slots": [p["id"] for p in game_state["pokemon"][:6]],
    }
    entries = [
        {"kind": "evolved", "source": "claude"},
        {"kind": "caught", "source": "safari"},
        {"kind": "caught", "source": "battle"},
    ]

    badges = badge_map(trainer_card.build(game_state, entries=entries, username="hunt"))

    for badge_id in (
        "bond",
        "safari",
        "battle",
        "curator",
        "types",
        "shiny",
        "legend",
        "shiny_legend",
    ):
        assert badges[badge_id]["earned"] is True
    assert badges["national"]["earned"] is False


def test_shiny_national_is_absent_until_national_is_complete():
    incomplete = state.default_state()
    incomplete["pokemon"] = [
        pokemon("Mewtwo", ptype="Psychic", rarity="legendary", shiny=True)
    ]

    hidden = badge_map(trainer_card.build(incomplete, entries=[], username="hunt"))

    assert "shiny_legend" in hidden
    assert hidden["shiny_legend"]["earned"] is True
    assert "shiny_national" not in hidden
    assert len(hidden) == 9

    complete = badge_map(
        trainer_card.build(national_state(), entries=[], username="hunt")
    )
    assert complete["national"]["earned"] is True
    assert complete["shiny_national"]["earned"] is False
    assert len(complete) == 10

    shiny_complete = badge_map(
        trainer_card.build(national_state(shiny=True), entries=[], username="hunt")
    )
    assert shiny_complete["shiny_national"]["earned"] is True


def test_stars_only_summarize_the_eight_core_badges():
    game_state = national_state(shiny=True)
    type_examples = {}
    for p in game_state["pokemon"]:
        type_examples.setdefault(p["type"], p)
    game_state["showcase"] = {
        "slots": [p["id"] for p in list(type_examples.values())[:6]],
    }
    entries = [
        {"kind": "evolved", "source": "claude"},
        {"kind": "caught", "source": "safari"},
        {"kind": "caught", "source": "battle"},
    ]

    card = trainer_card.build(game_state, entries=entries, username="hunt")

    assert card["core_badges_earned"] == 8
    assert card["star_count"] == 4
    assert badge_map(card)["shiny_legend"]["earned"] is True
    assert badge_map(card)["shiny_national"]["earned"] is True
