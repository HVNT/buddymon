"""Battle Mode state machine: weaken a wild, then throw to catch.

Sibling of safari.py. Two-sided but unpunishing — the wild attacks back and the
buddy has HP, but a buddy faint just lets the wild flee and revives the buddy to
full (no loss beyond the missed catch). Over-attacking can KO the wild (no
catch). Catch odds rise as the wild's HP drops. All randomness injected.
"""
import time

from . import data, engine, journal, notify
from . import state as st

ANIM_SECS = 4  # how long the throw/jiggle animation plays in the bar


def _hp_max(base_key, per_key, level):
    b = data.BATTLE
    return b[base_key] + b[per_key] * max(1, level)


def start(spawn, buddy):
    lvl = buddy["level"]
    b = data.BATTLE
    default_level = lvl + (b["wild_level_lo"] + b["wild_level_hi"]) // 2
    wild_level = engine.clamp_species_level(
        spawn["name"],
        spawn.get("level", default_level),
    )
    wild_hp = _hp_max("wild_hp_base", "wild_hp_per_level", wild_level)
    buddy_hp = _hp_max("buddy_hp_base", "buddy_hp_per_level", lvl)
    return {
        "name": spawn["name"], "type": spawn["type"], "emoji": spawn["emoji"],
        "rarity": spawn["rarity"], "shiny": bool(spawn.get("shiny")),
        "level": wild_level,
        "wild_level": wild_level, "wild_hp": wild_hp, "wild_hp_max": wild_hp,
        "buddy_hp": buddy_hp, "buddy_hp_max": buddy_hp,
        "balls_thrown": 0, "last_msg": f"A wild {spawn['name']} appeared!",
        "last_throw": None, "created_ts": time.time(),
    }


def wild_hp_frac(p):
    return p["wild_hp"] / p["wild_hp_max"] if p["wild_hp_max"] else 0.0


def buddy_hp_frac(p):
    return p["buddy_hp"] / p["buddy_hp_max"] if p["buddy_hp_max"] else 0.0


def catch_probability(p):
    b = data.BATTLE
    base = b["catch_base"].get(p["rarity"], 0.25)
    prob = base * (1 + b["catch_hp_bonus"] * (1 - wild_hp_frac(p)))
    return min(b["catch_cap"], prob)


def _buddy_level_from_hp_max(p):
    b = data.BATTLE
    return (p["buddy_hp_max"] - b["buddy_hp_base"]) // b["buddy_hp_per_level"]


def _wild_turn(p, rng):
    """Wild hits back. Returns True if the buddy faints (wild flees, full revive)."""
    b = data.BATTLE
    dmg = max(1, int(p["wild_level"] * rng.uniform(b["wild_atk_lo"], b["wild_atk_hi"])))
    p["buddy_hp"] = max(0, p["buddy_hp"] - dmg)
    if p["buddy_hp"] <= 0:
        p["buddy_hp"] = p["buddy_hp_max"]  # free revive
        p["last_msg"] = f"Your buddy fainted! {p['name']} slipped away."
        return True
    return False


def attack(p, buddy, trainer, rng):
    b = data.BATTLE
    lvl = _buddy_level_from_hp_max(p)
    dmg = max(1, int(lvl * rng.uniform(b["atk_lo"], b["atk_hi"])))
    p["wild_hp"] = max(0, p["wild_hp"] - dmg)
    if p["wild_hp"] <= 0:
        p["last_msg"] = f"{p['name']} fainted — it got away!"
        return {"done": True, "caught": False, "outcome": "ko"}
    if _wild_turn(p, rng):
        return {"done": True, "caught": False, "outcome": "buddy_faint"}
    p["last_msg"] = f"You hit {p['name']}!  (-{dmg} HP)"
    return {"done": False, "caught": False, "outcome": "hit"}


def throw_ball(p, buddy, trainer, rng):
    p["balls_thrown"] += 1  # infinite supply; counter is cosmetic
    prob = catch_probability(p)
    caught = rng.random() < prob
    # jiggles: how close it got (cosmetic). caught = 3 + click; break scales with prob.
    jiggles = 3 if caught else min(3, int(prob * 4) + (1 if rng.random() < prob else 0))
    p["last_throw"] = {"jiggles": jiggles, "caught": caught, "ts": time.time()}
    if caught:
        p["last_msg"] = f"Gotcha! {p['name']} was caught!"
        return {"done": True, "caught": True, "outcome": "caught"}
    if _wild_turn(p, rng):
        return {"done": True, "caught": False, "outcome": "buddy_faint"}
    p["last_msg"] = f"{p['name']} broke free!"
    return {"done": False, "caught": False, "outcome": "break"}


def run(p, buddy, trainer, rng):
    p["last_msg"] = f"Got away from {p['name']}."
    return {"done": True, "caught": False, "outcome": "ran"}


ACTIONS = {"attack": attack, "ball": throw_ball, "run": run}


def status_text(p):
    level = p.get("wild_level") or p.get("level")
    label = f"{p['name']} Lv.{level}" if level else p["name"]
    return (f"{label} HP {int(wild_hp_frac(p) * 100)}%  ·  "
            f"your buddy HP {int(buddy_hp_frac(p) * 100)}%")


def throwing(p, now=None):
    """True while a thrown ball is still animating (recent last_throw)."""
    lt = p.get("last_throw")
    return bool(lt and (now or time.time()) - lt["ts"] < ANIM_SECS)


def _resolve(s, pending, outcome):
    """Apply a finished Battle-Mode encounter to state: collect + journal + notify."""
    enc = {"name": pending["name"], "emoji": pending["emoji"],
           "rarity": pending["rarity"], "shiny": pending["shiny"],
           "level": pending.get("wild_level")}
    if outcome["caught"]:
        already = any(p["name"] == pending["name"] for p in s["pokemon"])
        s["pokemon"].append(engine.new_pokemon(
            pending["name"], pending["type"], pending["emoji"],
            pending["rarity"], pending["shiny"], level=pending["wild_level"]))
        enc.update(outcome="caught", new_species=not already)
    elif outcome["outcome"] == "ran":
        enc = None
    else:  # ko / buddy_faint
        enc.update(outcome=outcome["outcome"])
    if enc:
        for entry in journal.log_outcomes(None, enc, "battle"):
            if journal.is_rare(entry):
                notify.notify("buddymon", entry["text"])
    s.pop("pending_battle", None)


def take_turn(s, action, rng):
    """Run one Battle-Mode action against the pending battle, resolving when the
    turn ends it. Mutates `s` in place; the caller owns load/lock/save. Returns
    (outcome, msg) — (None, msg) if nothing is pending or the action is unknown."""
    pending = s.get("pending_battle")
    if not pending:
        return None, "No battle right now."
    if action not in ACTIONS:
        return None, "Usage: attack|ball|run"
    buddy = st.active_pokemon(s)
    outcome = ACTIONS[action](pending, buddy, s["trainer"], rng)
    msg = pending["last_msg"]
    if outcome["done"]:
        _resolve(s, pending, outcome)
    return outcome, msg
