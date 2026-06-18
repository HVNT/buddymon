"""Static dex data: starters, evolution chains, and the wild encounter pool."""

# Starters. Evolution chain entries are (name, level, emoji).
STARTERS = {
    "Charmander": {"type": "Fire", "emoji": "🦎", "evolutions": [("Charmeleon", 16, "🔥"), ("Charizard", 36, "🐉")]},
    "Bulbasaur": {"type": "Grass", "emoji": "🌱", "evolutions": [("Ivysaur", 16, "🌿"), ("Venusaur", 36, "🌺")]},
    "Squirtle": {"type": "Water", "emoji": "🐢", "evolutions": [("Wartortle", 16, "💧"), ("Blastoise", 36, "🌊")]},
    "Pikachu": {"type": "Electric", "emoji": "⚡", "evolutions": [("Raichu", 30, "🟠")]},
    "Eevee": {"type": "Normal", "emoji": "🦊", "evolutions": []},  # evolves randomly, see engine
}

# Eevee branches at level 25: engine picks one at random.
EEVEE_BRANCHES = [("Vaporeon", "💧"), ("Jolteon", "⚡"), ("Flareon", "🔥")]
EEVEE_EVOLVE_LEVEL = 25

# Wild encounter pool: name -> (type, emoji, rarity). The full 649-species
# National Dex, generated from PokéAPI by tools/gen_dex.py.
from .dex_roster import WILDS  # noqa: E402
from .evolutions import EVOLUTIONS  # noqa: E402


def _species_index():
    """name -> (type, emoji) for every species, incl. starter-line forms that
    aren't in WILDS (Charmeleon, Raichu, …). Lets evolution targets resolve art."""
    idx = {n: (t, e) for n, (t, e, _) in WILDS.items()}
    for base, info in STARTERS.items():
        idx[base] = (info["type"], info["emoji"])
        for name, _, emoji in info["evolutions"]:
            idx[name] = (info["type"], emoji)
    for name, emoji in EEVEE_BRANCHES:
        idx.setdefault(name, ("Normal", emoji))
    return idx


_SPECIES = _species_index()


def species_info(name):
    """(type, emoji) for any species; falls back to a neutral default."""
    return _SPECIES.get(name, ("Normal", "🔵"))


def _pre_evolution():
    """evolved form -> the form it came from, dex-wide (from EVOLUTIONS)."""
    pre = {}
    for src, targets in EVOLUTIONS.items():
        for to_name, _ in targets:
            pre[to_name] = src
    return pre


PRE_EVOLUTION = _pre_evolution()

RARITY_WEIGHTS = [("common", 70), ("uncommon", 20), ("rare", 8), ("legendary", 2)]

# Safari Zone: rare/legendary spawns become interactive minigames instead of
# auto-resolving. Tuning per rarity — base_c is the starting catch rate (0-255,
# Gen 1 scale), flee_base the per-turn neutral flee probability.
INTERACTIVE_RARITIES = {"rare", "legendary"}
SAFARI = {
    "rare": {"base_c": 90, "flee_base": 0.10},
    "legendary": {"base_c": 45, "flee_base": 0.18},
}
CATCH_DIVISOR = 300.0   # ball catch prob = min(0.9, C / CATCH_DIVISOR)

# Auto-catch probability per rarity (one ball per attempt).
CATCH_RATES = {"common": 0.90, "uncommon": 0.70, "rare": 0.45, "legendary": 0.20}

SHINY_ODDS = 128  # 1 in N
ENCOUNTER_CHANCE = 0.18  # per XP-earning turn
LEGENDARY_MIN_LEVEL = 20  # buddy level required for legendary spawns

# Battle Mode (opt-in via state["mode"] == "battle"): wild encounters become a
# weaken-then-catch battle. Simple level-scaled damage, no type chart. HP is
# derived from level (we store no combat stats). All tunable.
BATTLE = {
    "buddy_hp_base": 30, "buddy_hp_per_level": 3,
    "wild_hp_base": 25, "wild_hp_per_level": 3,
    "atk_lo": 0.8, "atk_hi": 1.5,            # player dmg = buddy_level * U(lo,hi)
    "wild_atk_lo": 0.5, "wild_atk_hi": 1.1,  # wild dmg = wild_level * U(lo,hi)
    "wild_level_lo": -3, "wild_level_hi": 2,  # wild level offset from buddy
    # base catch prob at FULL wild HP; rises up to ~2.5x as HP drops to 0.
    "catch_base": {"common": 0.30, "uncommon": 0.22, "rare": 0.14, "legendary": 0.08},
    "catch_hp_bonus": 1.5,   # multiplier scaling: base * (1 + bonus*(1-hp_frac))
    "catch_cap": 0.95,
}
