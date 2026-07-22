"""Read-only Trainer Card identity and milestone projection.

The Trainer Card deliberately reports trainer-owned facts rather than
relabeling the active Pokémon's level. Badge rules live here so every client
can share the same local-only achievement contract.
"""

import getpass
import hashlib
import os

from . import data, journal, paths, render, showcase, state


CORE_BADGE_IDS = (
    "bond",
    "safari",
    "battle",
    "curator",
    "types",
    "shiny",
    "legend",
    "national",
)

BADGE_DEFINITIONS = (
    {
        "id": "bond",
        "label": "Bond Badge",
        "symbol": "♥",
        "description": "Witness a Pokémon evolution.",
    },
    {
        "id": "safari",
        "label": "Safari Badge",
        "symbol": "◎",
        "description": "Catch a Pokémon in Safari mode.",
    },
    {
        "id": "battle",
        "label": "Battle Badge",
        "symbol": "×",
        "description": "Catch a Pokémon in Battle mode.",
    },
    {
        "id": "curator",
        "label": "Curator Badge",
        "symbol": "▣",
        "description": "Fill every Showcase slot with a distinct Pokémon.",
    },
    {
        "id": "types",
        "label": "Type Badge",
        "symbol": "◇",
        "description": "Collect every supported primary type.",
    },
    {
        "id": "shiny",
        "label": "Shiny Badge",
        "symbol": "✦",
        "description": "Own a shiny Pokémon.",
    },
    {
        "id": "legend",
        "label": "Legend Badge",
        "symbol": "★",
        "description": "Own a legendary or mythical Pokémon.",
    },
    {
        "id": "national",
        "label": "National Badge",
        "symbol": "N",
        "description": "Complete the National Pokédex.",
    },
    {
        "id": "shiny_legend",
        "label": "Shiny Legend Badge",
        "symbol": "✶",
        "description": "Own a shiny legendary or mythical Pokémon.",
    },
    {
        "id": "shiny_national",
        "label": "Shiny National Badge",
        "symbol": "N✦",
        "description": "Own a shiny copy of every National Pokédex species.",
    },
)

NATIONAL_SPECIES = frozenset(data.DEX_NUMBERS)
SUPPORTED_TYPES = frozenset(
    ptype for ptype, _emoji, _rarity in data.WILDS.values()
)
MODE_LABELS = {
    "auto": "QUICK",
    "safari": "SAFARI",
    "battle": "BATTLE",
}


def _trainer_name(game_state, username=None):
    trainer = game_state.get("trainer", {})
    value = trainer.get("name")
    if not value:
        if username is None:
            username = os.environ.get("USER")
            if not username:
                try:
                    username = getpass.getuser()
                except OSError:
                    username = None
        value = username or "TRAINER"
    value = " ".join(str(value).strip().split()).upper()
    return (value or "TRAINER")[:10]


def _trainer_id(game_state, name):
    trainer = game_state.get("trainer", {})
    saved = trainer.get("id_no")
    if saved is not None:
        try:
            return f"{abs(int(saved)) % 100_000:05d}"
        except (TypeError, ValueError):
            pass

    pokemon = game_state.get("pokemon", [])
    first_id = pokemon[0].get("id") if pokemon else ""
    seed = f"{name}|{first_id}|{paths.STATE_FILE}"
    digest = hashlib.blake2s(seed.encode("utf-8"), digest_size=4).digest()
    return f"{int.from_bytes(digest, 'big') % 100_000:05d}"


def _nonnegative_int(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _earned_badges(game_state, entries):
    pokemon = game_state.get("pokemon", [])
    owned_species = {
        p.get("name") for p in pokemon if p.get("name") in NATIONAL_SPECIES
    }
    shiny_species = {
        p.get("name")
        for p in pokemon
        if p.get("shiny") and p.get("name") in NATIONAL_SPECIES
    }
    owned_types = {p.get("type") for p in pokemon if p.get("type")}
    valid_showcase = [
        entry["pokemon"]
        for entry in showcase.showcase_entries(game_state)
        if entry.get("pokemon") is not None and not entry.get("missing")
    ]
    showcase_species = {p.get("name") for p in valid_showcase if p.get("name")}

    national = NATIONAL_SPECIES.issubset(owned_species)
    return {
        "bond": any(entry.get("kind") == "evolved" for entry in entries),
        "safari": any(
            entry.get("kind") == "caught" and entry.get("source") == "safari"
            for entry in entries
        ),
        "battle": any(
            entry.get("kind") == "caught" and entry.get("source") == "battle"
            for entry in entries
        ),
        "curator": (
            len(valid_showcase) == showcase.DEFAULT_SLOT_COUNT
            and len(showcase_species) == showcase.DEFAULT_SLOT_COUNT
        ),
        "types": SUPPORTED_TYPES.issubset(owned_types),
        "shiny": bool(shiny_species),
        "legend": any(p.get("rarity") == "legendary" for p in pokemon),
        "national": national,
        "shiny_legend": any(
            p.get("shiny") and p.get("rarity") == "legendary"
            for p in pokemon
        ),
        "shiny_national": national and NATIONAL_SPECIES.issubset(shiny_species),
    }


def build(game_state, *, entries=None, username=None, portrait_base64=None):
    """Return the compact, non-mutating Trainer Card projection."""
    entries = journal.tail(None) if entries is None else list(entries)
    trainer = game_state.get("trainer", {})
    pokemon = game_state.get("pokemon", [])
    name = _trainer_name(game_state, username=username)
    earned = _earned_badges(game_state, entries)

    badges = []
    for definition in BADGE_DEFINITIONS:
        badge_id = definition["id"]
        if badge_id == "shiny_national" and not earned["national"]:
            continue
        badges.append({**definition, "earned": earned[badge_id]})

    core_earned = sum(1 for badge_id in CORE_BADGE_IDS if earned[badge_id])
    species_count = len({
        p.get("name") for p in pokemon if p.get("name") in NATIONAL_SPECIES
    })
    shiny_count = sum(1 for p in pokemon if p.get("shiny"))
    mode = game_state.get("mode")
    streak = render.compact_number(_nonnegative_int(trainer.get("streak")))
    balls = (
        "∞"
        if mode == "battle"
        else render.compact_number(_nonnegative_int(trainer.get("balls")))
    )
    return {
        "name": name,
        "id_no": _trainer_id(game_state, name),
        "portrait_base64": portrait_base64,
        "star_count": min(4, core_earned // 2),
        "facts": [
            {"id": "name", "label": "NAME", "value": name},
            {
                "id": "tokens",
                "label": "TOKENS",
                "value": render.compact_number(trainer.get("total_tokens", 0)),
            },
            {
                "id": "pokedex",
                "label": "POKÉDEX",
                "value": f"{species_count} / {len(NATIONAL_SPECIES)}",
            },
            {
                "id": "caught",
                "label": "CAUGHT",
                "value": render.compact_number(len(pokemon)),
            },
        ],
        "trainer_stats": [
            {
                "id": "mode",
                "label": "MODE",
                "value": MODE_LABELS.get(mode, MODE_LABELS[state.DEFAULT_MODE]),
            },
            {
                "id": "streak",
                "label": "STREAK",
                "value": f"{streak}D",
            },
            {
                "id": "balls",
                "label": "BALLS",
                "value": balls,
            },
            {
                "id": "shiny",
                "label": "SHINY",
                "value": render.compact_number(shiny_count),
            },
        ],
        "badges": badges,
        "core_badges_earned": core_earned,
        "national_complete": earned["national"],
    }
