"""Game rules: XP curve, levels, evolution, streaks, wild encounters.

All randomness flows through an injected random.Random so tests are
deterministic. XP comes from real token usage (see hooks/stop.py).
"""
import time
import uuid
from datetime import date

from . import data, favorites

# Tokens per 1 progress point, by usage tier.
XP_TIERS = {"output": 75, "input": 500, "cache_write": 250, "cache_read": 1000}

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


def token_total(totals):
    return sum(max(0, int(totals.get(tier, 0))) for tier in XP_TIERS)


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
    p = {
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
    # Seed the favorites shortlist with the standouts so it's never cold:
    # shinies, legendaries/mythics, and starters auto-favorite on catch.
    if favorites.should_auto_favorite(p):
        favorites.set_favorite(p, True)
    return p


def evolution_level_bounds(name):
    """Legal wild-level band for this evolution stage.

    A species starts at the level its previous form evolves into it, and stops
    one level before it would evolve onward. Standalone species use the full
    playable level range.
    """
    lower = 1
    prev = data.PRE_EVOLUTION.get(name)
    if prev:
        into_levels = [level for to_name, level in data.EVOLUTIONS.get(prev, [])
                       if to_name == name]
        if into_levels:
            lower = max(lower, min(int(level) for level in into_levels))

    next_levels = [int(level) for _, level in data.EVOLUTIONS.get(name, [])]
    upper = min(next_levels) - 1 if next_levels else LEVEL_CAP
    lower = max(1, min(LEVEL_CAP, lower))
    upper = max(lower, min(LEVEL_CAP, upper))
    return lower, upper


def clamp_species_level(name, level):
    lower, upper = evolution_level_bounds(name)
    return max(lower, min(upper, int(level)))


def _normal_level_between(lower, upper, rng):
    lower, upper = int(lower), int(upper)
    if lower >= upper:
        return lower
    gauss = getattr(rng, "gauss", None)
    if gauss is None:
        return rng.randint(lower, upper)

    mean = (lower + upper) / 2
    sigma = max(1.0, (upper - lower + 1) / 6)
    sample = mean
    for _ in range(8):
        sample = gauss(mean, sigma)
        rounded = int(round(sample))
        if lower <= rounded <= upper:
            return rounded
    return max(lower, min(upper, int(round(sample))))


def wild_level_for(name, rng):
    lower, upper = evolution_level_bounds(name)
    return _normal_level_between(lower, upper, rng)


def check_evolution(pokemon, rng):
    """Return (new_name, new_emoji) if the pokemon evolves at its level, else
    None. Table-driven across the whole dex; branches (Eevee, Poliwhirl, …)
    pick randomly among the eligible targets."""
    targets = data.EVOLUTIONS.get(pokemon["name"], [])
    eligible = [to for to, level in targets if pokemon["level"] >= level]
    if not eligible:
        return None
    new_name = rng.choice(eligible)
    return new_name, data.species_info(new_name)[1]


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
        "buddy_shiny": bool(buddy.get("shiny")),
        "buddy_rarity": buddy.get("rarity"),
    }


def roll_encounter(state, rng):
    """Maybe spawn a wild pokemon. Common/uncommon auto-resolve (caught/fled/
    no_balls); rare/legendary become an interactive Safari encounter
    ("appeared"). Returns a result dict or None."""
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
    level = wild_level_for(name, rng)
    spawn = {
        "name": name, "type": ptype, "emoji": emoji, "rarity": rarity,
        "shiny": shiny, "level": level,
    }

    # Battle Mode: EVERY wild becomes a weaken-then-catch battle (one at a time).
    if state.get("mode") == "battle":
        if state.get("pending_battle"):
            return None
        from . import battle
        state["pending_battle"] = battle.start(spawn, buddy)
        return {**spawn, "outcome": "appeared"}

    # Auto Mode: rare/legendary become interactive Safari encounters.
    if rarity in data.INTERACTIVE_RARITIES:
        if state.get("pending_encounter"):
            return None  # already one in front of you
        from . import safari
        state["pending_encounter"] = safari.start(spawn)
        return {**spawn, "outcome": "appeared"}

    trainer = state["trainer"]
    if trainer.get("balls", 0) <= 0:
        return {**spawn, "outcome": "no_balls"}

    trainer["balls"] -= 1
    if rng.random() <= data.CATCH_RATES[rarity]:
        already_owned = any(p["name"] == name for p in state["pokemon"])
        state["pokemon"].append(new_pokemon(
            name, ptype, emoji, rarity, shiny, level=level))
        return {**spawn, "outcome": "caught", "new_species": not already_owned}
    return {**spawn, "outcome": "fled"}


def summarize_events(result, encounter):
    """One-line announcement for displays (statusline, tmux, hooks)."""
    parts = []
    if result:
        if result["evolved"]:
            level = f" Lv.{result['new_level']}" if result.get("new_level") else ""
            parts.append(f"🎊 evolved into {result['evolved']}{level}!")
        elif result["leveled"]:
            parts.append(f"🆙 Lv.{result['new_level']}!")
    if encounter:
        shiny = "✨" if encounter["shiny"] else ""
        level = f" Lv.{encounter['level']}" if encounter.get("level") else ""
        wild = f"{shiny}{encounter['emoji']} {encounter['name']}{level}"
        if encounter["outcome"] == "caught":
            tag = " (new!)" if encounter.get("new_species") else ""
            parts.append(f"🎉 caught {wild}{tag}")
        elif encounter["outcome"] == "fled":
            parts.append(f"💨 {wild} fled")
        elif encounter["outcome"] == "appeared":
            parts.append(f"👀 a wild {wild} appeared!")
        elif encounter["outcome"] == "no_balls":
            parts.append(f"😱 {wild} appeared — no balls left!")
        elif encounter["outcome"] == "ko":
            parts.append(f"💥 {wild} fainted — it got away")
        elif encounter["outcome"] == "buddy_faint":
            parts.append(f"😵 your buddy fainted; {wild} slipped away")
    return "  ".join(parts)


def display_event_detail(detail):
    """Hide old internal progress prefixes from user-facing event surfaces."""
    text = str(detail or "").strip()
    if not text.startswith("+"):
        return text
    parts = text.split(None, 2)
    if len(parts) >= 2 and parts[0][1:].isdigit() and parts[1] == "progress":
        return parts[2].strip() if len(parts) > 2 else ""
    return text


def create_starter(state, starter_name):
    """Initialize state with a chosen starter. Returns the new buddy or None."""
    info = data.STARTERS.get(starter_name)
    if info is None:
        return None
    buddy = new_pokemon(starter_name, info["type"], info["emoji"], "starter")
    state["pokemon"].append(buddy)
    state["active"] = buddy["id"]
    return buddy
