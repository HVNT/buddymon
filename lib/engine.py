"""Game rules: XP curve, levels, evolution, streaks, wild encounters.

All randomness flows through an injected random.Random so tests are
deterministic. XP comes from real token usage (see hooks/stop.py).
"""
import time
import uuid
from datetime import date

from . import data

# Tokens per 1 XP, by usage tier.
XP_TIERS = {"output": 100, "input": 1000, "cache_write": 500, "cache_read": 5000}

LEVEL_CAP = 60
BALLS_PER_LEVEL = 3
BALL_MILESTONE_XP = 5000  # +1 ball per this much lifetime XP
STREAK_STEP = 0.02  # +2% XP per consecutive day, capped at 30 days


def xp_for_level(level):
    """Total XP required to reach a level. Cubic, like the real games'
    growth curves: at heavy daily use (~20k XP/day), first evolution lands
    after ~a week, Lv.36 after ~3 months, the cap after a year-plus."""
    return 40 * (level - 1) ** 3


def level_from_xp(xp):
    level = 1
    while level < LEVEL_CAP and xp >= xp_for_level(level + 1):
        level += 1
    return level


def xp_from_tokens(totals):
    return sum(totals.get(tier, 0) // divisor for tier, divisor in XP_TIERS.items())


def streak_multiplier(streak):
    return 1.0 + min(streak, 30) * STREAK_STEP


def update_streak(trainer, today=None):
    """Bump the daily streak on the first XP award of each day."""
    today = today or date.today().isoformat()
    last = trainer.get("last_day")
    if last == today:
        return
    if last is not None:
        prev = date.fromisoformat(last)
        gap = (date.fromisoformat(today) - prev).days
        trainer["streak"] = trainer.get("streak", 0) + 1 if gap == 1 else 1
    else:
        trainer["streak"] = 1
    trainer["last_day"] = today


def new_pokemon(name, ptype, emoji, rarity, shiny=False, level=1):
    return {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "type": ptype,
        "emoji": emoji,
        "rarity": rarity,
        "level": level,
        "xp": xp_for_level(level),
        "shiny": shiny,
        "caught_at": time.time(),
    }


def check_evolution(pokemon, rng):
    """Return (new_name, new_emoji) if the pokemon evolves at its level."""
    if pokemon["name"] == "Eevee" and pokemon["level"] >= data.EEVEE_EVOLVE_LEVEL:
        return rng.choice(data.EEVEE_BRANCHES)
    for starter, info in data.STARTERS.items():
        chain = [(starter, 1, info["emoji"])] + info["evolutions"]
        names = [c[0] for c in chain]
        if pokemon["name"] in names[:-1]:
            idx = names.index(pokemon["name"])
            next_name, next_level, next_emoji = chain[idx + 1]
            if pokemon["level"] >= next_level:
                return next_name, next_emoji
    return None


def award_xp(state, base_xp, rng):
    """Apply XP to the active buddy. Returns a result dict describing what happened."""
    from . import state as st  # local import to avoid cycle

    buddy = st.active_pokemon(state)
    if buddy is None or base_xp <= 0:
        return None

    trainer = state["trainer"]
    update_streak(trainer)
    xp = int(base_xp * streak_multiplier(trainer.get("streak", 0)))

    old_level = buddy["level"]
    buddy["xp"] = min(buddy["xp"] + xp, xp_for_level(LEVEL_CAP))
    buddy["level"] = level_from_xp(buddy["xp"])
    old_total = trainer.get("total_xp", 0)
    trainer["total_xp"] = old_total + xp

    leveled = buddy["level"] - old_level
    if leveled > 0:
        trainer["balls"] = trainer.get("balls", 0) + BALLS_PER_LEVEL * leveled
    # milestone balls keep catching viable on the slow cubic curve
    milestones = trainer["total_xp"] // BALL_MILESTONE_XP - old_total // BALL_MILESTONE_XP
    if milestones > 0:
        trainer["balls"] = trainer.get("balls", 0) + milestones

    evolved = None
    while True:  # a huge award can cross multiple evolution thresholds
        evo = check_evolution(buddy, rng)
        if not evo:
            break
        evolved = evo[0]
        buddy["name"], buddy["emoji"] = evo

    return {
        "xp": xp,
        "old_level": old_level,
        "new_level": buddy["level"],
        "leveled": leveled > 0,
        "evolved": evolved,
        "buddy": buddy["name"],
    }


def roll_encounter(state, rng):
    """Maybe spawn and auto-catch a wild pokemon. Returns a result dict or None."""
    from . import state as st

    buddy = st.active_pokemon(state)
    if buddy is None or rng.random() > data.ENCOUNTER_CHANCE:
        return None

    roll = rng.uniform(0, 100)
    acc = 0
    rarity = "common"
    for tier, weight in data.RARITY_WEIGHTS:
        acc += weight
        if roll <= acc:
            rarity = tier
            break
    if rarity == "legendary" and buddy["level"] < data.LEGENDARY_MIN_LEVEL:
        rarity = "rare"

    pool = [(n, *v) for n, v in data.WILDS.items() if v[2] == rarity]
    name, ptype, emoji, _ = pool[rng.randrange(len(pool))]
    shiny = rng.randrange(data.SHINY_ODDS) == 0

    trainer = state["trainer"]
    if trainer.get("balls", 0) <= 0:
        return {"name": name, "emoji": emoji, "rarity": rarity, "shiny": shiny,
                "outcome": "no_balls"}

    trainer["balls"] -= 1
    if rng.random() <= data.CATCH_RATES[rarity]:
        already_owned = any(p["name"] == name for p in state["pokemon"])
        state["pokemon"].append(new_pokemon(name, ptype, emoji, rarity, shiny))
        return {"name": name, "emoji": emoji, "rarity": rarity, "shiny": shiny,
                "outcome": "caught", "new_species": not already_owned}
    return {"name": name, "emoji": emoji, "rarity": rarity, "shiny": shiny,
            "outcome": "fled"}


def summarize_events(result, encounter):
    """One-line announcement for displays (statusline, tmux, hooks)."""
    parts = []
    if result:
        if result["evolved"]:
            parts.append(f"🎊 evolved into {result['evolved']}!")
        elif result["leveled"]:
            parts.append(f"⬆️ Lv.{result['new_level']}!")
        else:
            parts.append(f"+{result['xp']} XP")
    if encounter:
        shiny = "✨" if encounter["shiny"] else ""
        wild = f"{shiny}{encounter['emoji']} {encounter['name']}"
        if encounter["outcome"] == "caught":
            tag = " (new!)" if encounter.get("new_species") else ""
            parts.append(f"🎉 caught {wild}{tag}")
        elif encounter["outcome"] == "fled":
            parts.append(f"💨 {wild} fled")
        else:
            parts.append(f"😱 {wild} appeared — no balls left!")
    return "  ".join(parts)


def create_starter(state, starter_name):
    """Initialize state with a chosen starter. Returns the new buddy or None."""
    info = data.STARTERS.get(starter_name)
    if info is None:
        return None
    buddy = new_pokemon(starter_name, info["type"], info["emoji"], "starter")
    state["pokemon"].append(buddy)
    state["active"] = buddy["id"]
    return buddy
