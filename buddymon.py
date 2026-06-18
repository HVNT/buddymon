#!/usr/bin/env python3
"""buddymon CLI — used by the /buddymon:* commands and direct play.

Usage:
  buddymon.py choose <starter>    pick your starter (one-time)
  buddymon.py status              status card
  buddymon.py dex                 collection by rarity
  buddymon.py switch <name>       make a caught pokemon your active buddy
  buddymon.py preview             render every sprite (art QA)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import data, pixels, render, sprites, state, engine  # noqa: E402


def choose(args):
    name = (args[0] if args else "").capitalize()
    s = state.load()
    if s["pokemon"]:
        return f"You already have a buddy ({state.active_pokemon(s)['name']}). Use switch instead."
    buddy = engine.create_starter(s, name)
    if buddy is None:
        return "Pick one of: " + ", ".join(data.STARTERS)
    state.save(s)
    grid, palette = sprites.sprite_for(buddy["name"], buddy["type"])
    art = "\n".join(pixels.render(grid, palette))
    return f"{art}\n\n{buddy['emoji']} {buddy['name']} chose YOU! XP flows from every Claude Code turn."


def switch(args):
    target = " ".join(args).strip().lower()
    if not target:
        return "Usage: switch <name>"
    s = state.load()
    matches = [p for p in s["pokemon"] if p["name"].lower() == target]
    if not matches:
        return f"No '{target}' in your collection. See /buddymon:dex"
    best = max(matches, key=lambda p: p["level"])
    s["active"] = best["id"]
    state.save(s)
    return f"{best['emoji']} {best['name']} (Lv.{best['level']}) is now your buddy!"


def preview(_args):
    out = []
    for name in sprites.SPRITES:
        grid, palette = sprites.SPRITES[name]
        out.append(name)
        out.extend(pixels.render(grid, palette))
    return "\n".join(out)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    args = sys.argv[2:]
    handlers = {
        "choose": choose,
        "switch": switch,
        "preview": preview,
        "status": lambda a: render.status_card(state.load()),
        "dex": lambda a: render.dex(state.load()),
    }
    handler = handlers.get(cmd)
    if handler is None:
        print(__doc__.strip())
        sys.exit(2)
    print(handler(args))


if __name__ == "__main__":
    main()
