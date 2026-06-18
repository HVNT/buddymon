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

# Wild pool: name -> (type, emoji, rarity)
WILDS = {
    # common
    "Pidgey": ("Flying", "🐦", "common"),
    "Rattata": ("Normal", "🐀", "common"),
    "Caterpie": ("Bug", "🐛", "common"),
    "Weedle": ("Bug", "🐝", "common"),
    "Zubat": ("Poison", "🦇", "common"),
    "Oddish": ("Grass", "🌿", "common"),
    "Poliwag": ("Water", "🌀", "common"),
    "Magikarp": ("Water", "🐟", "common"),
    "Sentret": ("Normal", "🐿️", "common"),
    "Hoothoot": ("Flying", "🦉", "common"),
    "Zigzagoon": ("Normal", "🦝", "common"),
    "Bidoof": ("Normal", "🦫", "common"),
    "Wooloo": ("Normal", "🐑", "common"),
    "Lechonk": ("Normal", "🐖", "common"),
    # uncommon
    "Sandshrew": ("Ground", "🦔", "uncommon"),
    "Vulpix": ("Fire", "🦊", "uncommon"),
    "Growlithe": ("Fire", "🐕", "uncommon"),
    "Abra": ("Psychic", "🥄", "uncommon"),
    "Machop": ("Fighting", "💪", "uncommon"),
    "Geodude": ("Rock", "🪨", "uncommon"),
    "Gastly": ("Ghost", "👻", "uncommon"),
    "Cubone": ("Ground", "🦴", "uncommon"),
    "Eevee": ("Normal", "🦊", "uncommon"),
    "Togepi": ("Fairy", "🥚", "uncommon"),
    "Mareep": ("Electric", "🐏", "uncommon"),
    "Riolu": ("Fighting", "🐺", "uncommon"),
    "Munchlax": ("Normal", "🍙", "uncommon"),
    # rare
    "Snorlax": ("Normal", "😴", "rare"),
    "Lapras": ("Water", "🦕", "rare"),
    "Aerodactyl": ("Rock", "🦖", "rare"),
    "Dratini": ("Dragon", "🐍", "rare"),
    "Larvitar": ("Rock", "🦎", "rare"),
    "Beldum": ("Steel", "🤖", "rare"),
    "Gible": ("Dragon", "🦈", "rare"),
    "Ditto": ("Normal", "🟣", "rare"),
    "Porygon": ("Normal", "🕹️", "rare"),
    "Scyther": ("Bug", "🗡️", "rare"),
    "Chansey": ("Normal", "🥚", "rare"),
    # legendary
    "Articuno": ("Ice", "🧊", "legendary"),
    "Zapdos": ("Electric", "🌩️", "legendary"),
    "Moltres": ("Fire", "☄️", "legendary"),
    "Mewtwo": ("Psychic", "🧬", "legendary"),
    "Mew": ("Psychic", "🩷", "legendary"),
    "Lugia": ("Psychic", "🌊", "legendary"),
    "Ho-Oh": ("Fire", "🌈", "legendary"),
    "Celebi": ("Grass", "🍀", "legendary"),
    "Rayquaza": ("Dragon", "🐉", "legendary"),
    "Jirachi": ("Steel", "🌠", "legendary"),
}

RARITY_WEIGHTS = [("common", 70), ("uncommon", 20), ("rare", 8), ("legendary", 2)]

# Auto-catch probability per rarity (one ball per attempt).
CATCH_RATES = {"common": 0.90, "uncommon": 0.70, "rare": 0.45, "legendary": 0.20}

SHINY_ODDS = 128  # 1 in N
ENCOUNTER_CHANCE = 0.18  # per XP-earning turn
LEGENDARY_MIN_LEVEL = 20  # buddy level required for legendary spawns
