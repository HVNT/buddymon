"""Gen 1 Safari Zone state machine for rare/legendary encounters.

Faithful to the originals: a per-encounter catch rate C plus mutually-exclusive
angry/eating counters. Rock doubles C and angers (2x flee); bait halves C and
feeds (1/4 flee); when the angry counter expires, C snaps back to baseline. All
randomness is injected so turns are deterministic in tests.
"""
import time

from . import data


def start(encounter):
    """Build a pending-encounter dict from a roll_encounter spawn."""
    base_c = data.SAFARI[encounter["rarity"]]["base_c"]
    return {
        "name": encounter["name"], "type": encounter["type"],
        "emoji": encounter["emoji"], "rarity": encounter["rarity"],
        "shiny": bool(encounter.get("shiny")),
        "c": base_c, "base_c": base_c,
        "angry": 0, "eating": 0, "balls_thrown": 0, "moves": 0,
        "last_msg": f"A wild {encounter['name']} appeared!",
        "created_ts": time.time(),
    }


def _flee_probability(pending):
    base = data.SAFARI[pending["rarity"]]["flee_base"]
    if pending["angry"] > 0:
        return min(0.95, base * 2)
    if pending["eating"] > 0:
        return base * 0.25
    return base


def _catch_probability(pending):
    return min(0.9, pending["c"] / data.CATCH_DIVISOR)


def _end_turn(pending, rng):
    """Flee check, then decrement the active counter (anger expiry resets C).

    The wild never flees on the trainer's first move — you always get to start
    the fight; normal flee odds apply from the second move onward."""
    pending["moves"] += 1
    if pending["moves"] > 1 and rng.random() < _flee_probability(pending):
        return True  # fled
    if pending["angry"] > 0:
        pending["angry"] -= 1
        if pending["angry"] == 0:
            pending["c"] = pending["base_c"]
    elif pending["eating"] > 0:
        pending["eating"] -= 1
    return False


def throw_rock(pending, trainer, rng):
    pending["c"] = min(255, pending["c"] * 2)
    pending["angry"] += rng.randint(1, 5)
    pending["eating"] = 0
    fled = _end_turn(pending, rng)
    pending["last_msg"] = (f"{pending['name']} fled!" if fled
                           else f"You threw a Rock! {pending['name']} is angry!")
    return {"done": fled, "caught": False, "fled": fled}


def throw_bait(pending, trainer, rng):
    pending["c"] = pending["c"] // 2
    pending["eating"] += rng.randint(1, 5)
    pending["angry"] = 0
    fled = _end_turn(pending, rng)
    pending["last_msg"] = (f"{pending['name']} fled!" if fled
                           else f"You threw Bait! {pending['name']} is eating!")
    return {"done": fled, "caught": False, "fled": fled}


def throw_ball(pending, trainer, rng):
    if trainer.get("balls", 0) <= 0:
        pending["last_msg"] = "Out of balls!"
        return {"done": False, "caught": False, "fled": False, "no_balls": True}
    trainer["balls"] -= 1
    pending["balls_thrown"] += 1
    if rng.random() < _catch_probability(pending):
        pending["last_msg"] = f"Gotcha! {pending['name']} was caught!"
        return {"done": True, "caught": True, "fled": False}
    fled = _end_turn(pending, rng)
    pending["last_msg"] = (f"Oh no! {pending['name']} fled!" if fled
                           else f"{pending['name']} broke free!")
    return {"done": fled, "caught": False, "fled": fled}


def run(pending, trainer, rng):
    pending["last_msg"] = f"Got away from {pending['name']}."
    return {"done": True, "caught": False, "fled": False, "ran": True}


ACTIONS = {"rock": throw_rock, "bait": throw_bait, "ball": throw_ball, "run": run}


def status_text(pending):
    if pending["angry"] > 0:
        return f"{pending['name']} is angry 🪨×{pending['angry']}"
    if pending["eating"] > 0:
        return f"{pending['name']} is eating 🍖×{pending['eating']}"
    return f"{pending['name']} is watching…"


def odds_hint(pending):
    if pending["moves"] == 0:
        return f"catch ~{round(_catch_probability(pending) * 100)}%  ·  won't flee yet"
    return (f"catch ~{round(_catch_probability(pending) * 100)}%  ·  "
            f"flee ~{round(_flee_probability(pending) * 100)}%")
