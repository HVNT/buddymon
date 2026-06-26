"""Gen 1 Safari Zone state machine for rare/legendary encounters.

Faithful to the originals: a per-encounter catch rate C plus mutually-exclusive
angry/eating counters. Rock doubles C and angers (2x flee); bait halves C and
feeds (1/4 flee); when the angry counter expires, C snaps back to baseline. All
randomness is injected so turns are deterministic in tests.
"""
import time

from . import data, engine, journal, notify


def start(encounter):
    """Build a pending-encounter dict from a roll_encounter spawn."""
    base_c = data.SAFARI[encounter["rarity"]]["base_c"]
    return {
        "name": encounter["name"], "type": encounter["type"],
        "emoji": encounter["emoji"], "rarity": encounter["rarity"],
        "shiny": bool(encounter.get("shiny")),
        "level": int(encounter.get("level") or 1),
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


def _pct(probability):
    return int(probability * 100 + 0.5)


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
    label = _label(pending)
    if pending["angry"] > 0:
        return f"{label} is angry 🪨×{pending['angry']}"
    if pending["eating"] > 0:
        return f"{label} is eating 🍖×{pending['eating']}"
    return f"{label} is watching…"


def _label(pending):
    level = pending.get("level")
    return f"{pending['name']} Lv.{level}" if level else pending["name"]


def odds_hint(pending):
    catch = _pct(_catch_probability(pending))
    flee = _pct(_flee_probability(pending))
    if pending["moves"] == 0:
        return f"catch ~{catch}%  ·  flee next turn ~{flee}%  ·  first move safe"
    return f"catch ~{catch}%  ·  flee ~{flee}%"


def _resolve(s, pending, outcome):
    """Apply a finished Safari encounter to state: collect + journal + notify."""
    enc = {"name": pending["name"], "emoji": pending["emoji"],
           "rarity": pending["rarity"], "shiny": pending["shiny"],
           "level": pending.get("level")}
    if outcome["caught"]:
        already = any(p["name"] == pending["name"] for p in s["pokemon"])
        s["pokemon"].append(engine.new_pokemon(
            pending["name"], pending["type"], pending["emoji"],
            pending["rarity"], pending["shiny"],
            level=pending.get("level", 1)))
        enc.update(outcome="caught", new_species=not already)
    elif outcome.get("ran"):
        enc = None  # running away isn't worth a journal line
    else:  # fled (or expired)
        enc.update(outcome="fled")
    if enc:
        for entry in journal.log_outcomes(None, enc, "safari"):
            if journal.is_rare(entry):
                notify.notify("buddymon", entry["text"])
    s.pop("pending_encounter", None)


def take_turn(s, action, rng):
    """Run one Safari action against the pending encounter, resolving when the
    turn ends it. Mutates `s` in place; the caller owns load/lock/save. Returns
    (outcome, msg) — (None, msg) if nothing is pending or the action is unknown."""
    pending = s.get("pending_encounter")
    if not pending:
        return None, "No wild pokémon right now."
    if action not in ACTIONS:
        return None, "Usage: rock|bait|ball|run"
    outcome = ACTIONS[action](pending, s["trainer"], rng)
    msg = pending["last_msg"]
    if outcome["done"]:
        _resolve(s, pending, outcome)
    return outcome, msg
