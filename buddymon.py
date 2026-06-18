#!/usr/bin/env python3
"""buddymon CLI — used by the /buddymon:* commands and direct play.

Usage:
  buddymon.py choose <starter>    pick your starter (one-time)
  buddymon.py status              status card
  buddymon.py dex                 collection by rarity
  buddymon.py switch <name>       make a caught pokemon your active buddy
  buddymon.py preview             render every sprite (art QA; both frames for packs)
  buddymon.py export-chibi        archive the chibi pack to ~/Pictures/buddymon/
  buddymon.py collect             award XP from other agent CLIs' token logs
  buddymon.py tiny [--collect]    one-line plain-text status (tmux status bar)
  buddymon.py frames [--scale N]  write current buddy frame PNGs + meta (hammerspoon)
  buddymon.py menubar             SwiftBar plugin output (sprite icon + dropdown)
  buddymon.py history [N]         the buddy's journey journal (default last 20)
  buddymon.py safari <action>     play a turn vs a pending wild (rock|bait|ball|run)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import data, packs, pixels, render, sprites, state, engine  # noqa: E402


def choose(args):
    name = (args[0] if args else "").capitalize()
    s = state.load()
    if s["pokemon"]:
        return f"You already have a buddy ({state.active_pokemon(s)['name']}). Use switch instead."
    buddy = engine.create_starter(s, name)
    if buddy is None:
        return "Pick one of: " + ", ".join(data.STARTERS)
    state.save(s)
    from lib import journal
    journal.append("starter", f"{buddy['emoji']} {buddy['name']} chose you",
                   {"name": buddy["name"]})
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
    pack = packs.load()
    names = sorted(set(pack) | set(sprites.SPRITES) - {"_silhouette"})
    for name in names:
        frames = packs.sprite_frames(name, data.WILDS.get(name, ("Normal",))[0])
        tag = " (gen2, 2 frames)" if len(frames) > 1 else " (chibi)"
        out.append(name + tag)
        rendered = [pixels.render(g, p) for g, p in frames]
        for rows in zip(*rendered):
            out.append("   ".join(rows))
    return "\n".join(out)


def export_chibi(_args):
    """Archive the hand-drawn chibi pack outside the repo (Hunter's keepsake)."""
    import json
    dest = Path.home() / "Pictures" / "buddymon"
    dest.mkdir(parents=True, exist_ok=True)
    payload = {name: {"grid": grid, "palette": palette}
               for name, (grid, palette) in sprites.SPRITES.items()}
    (dest / "chibi-pack.json").write_text(
        json.dumps(payload, indent=1), encoding="utf-8")
    msgs = [f"wrote {dest / 'chibi-pack.json'}"]
    try:
        from PIL import Image, ImageDraw
        scale, label_h, pad, cols = 14, 22, 10, 4
        names = [n for n in sprites.SPRITES if n != "_silhouette"] + ["_silhouette"]
        w, h = sprites.W_PX, sprites.H_PX
        cell_w, cell_h = w * scale + pad * 2, h * scale + label_h + pad * 2
        rows_n = (len(names) + cols - 1) // cols
        img = Image.new("RGB", (cols * cell_w, rows_n * cell_h), "#1e1e2e")
        draw = ImageDraw.Draw(img)
        for i, name in enumerate(names):
            grid, pal = sprites.SPRITES[name]
            ox, oy = (i % cols) * cell_w + pad, (i // cols) * cell_h + pad
            for y, row in enumerate(grid):
                for x, ch in enumerate(row):
                    if ch in pal:
                        hx = pal[ch].lstrip("#")
                        rgb = tuple(int(hx[j:j + 2], 16) for j in (0, 2, 4))
                        draw.rectangle([ox + x * scale, oy + y * scale,
                                        ox + (x + 1) * scale - 1, oy + (y + 1) * scale - 1], fill=rgb)
            draw.text((ox + w * scale // 2, oy + h * scale + 6),
                      "wild fallback" if name == "_silhouette" else name,
                      fill="#cdd6f4", anchor="ma")
        img.save(dest / "chibi-pack.png")
        msgs.append(f"wrote {dest / 'chibi-pack.png'}")
    except ImportError:
        msgs.append("PIL unavailable — for the PNG sheet run: "
                    "uv run --with pillow --no-project python3 buddymon.py export-chibi")
    return "\n".join(msgs)


def collect(_args, quiet=False):
    import random
    from lib import collectors, engine, journal, notify
    with state.lock():
        s = state.load()
        if not s["pokemon"]:
            return "" if quiet else "No buddy yet — nothing to collect for."
        summary = collectors.collect(s, random.Random())
        for entry in journal.log_outcomes(summary["result"], summary["encounter"], "cross"):
            if journal.is_rare(entry):
                notify.notify("buddymon", entry["text"])
        state.save(s)
    detail = engine.summarize_events(summary["result"], summary["encounter"])
    if detail:
        state.record_event("cross", "stop", detail)
    if quiet:
        return detail
    if summary["bootstrapped_now"]:
        return "anchored existing client logs — XP starts counting from now"
    tok = summary["tokens"]
    return detail or f"no new tokens ({sum(tok.values())} counted)"


def tiny(args):
    from lib import render, paths
    import time
    if "--collect" in args:
        try:
            collect([], quiet=True)
        except Exception:
            pass
    s = state.load()
    buddy = state.active_pokemon(s)
    if buddy is None:
        return "🥚 no buddy"
    newest = 0
    try:
        newest = max((f.stat().st_mtime for f in paths.SESSIONS_DIR.glob("*.json")), default=0)
    except OSError:
        pass
    mood = "⚙" if time.time() - newest < 180 else "💤"
    shiny = "✨" if buddy.get("shiny") else ""
    trainer = s["trainer"]
    bar = render.xp_bar(buddy, 6).split(" ")[0]
    bits = [f"{shiny}{buddy['emoji']} {buddy['name']} Lv.{buddy['level']}", bar, mood]
    if trainer.get("streak", 0) >= 2:
        bits.append(f"🔥{trainer['streak']}")
    bits.append(f"⚾{trainer.get('balls', 0)}")
    event = state.read_event("cross")
    if event and event.get("detail") and time.time() - event.get("ts", 0) < 600:
        bits.append(event["detail"])
    return " ".join(bits)


def _buddy_frames(s):
    from lib import packs
    buddy = state.active_pokemon(s)
    if buddy is None:
        return None, []
    return buddy, packs.sprite_frames(buddy["name"], buddy["type"], buddy.get("shiny"))


def frames(args):
    """Write frame PNGs + meta.json for external displays (Hammerspoon)."""
    import json, time
    from lib import paths, png
    scale = int(args[args.index("--scale") + 1]) if "--scale" in args else 6
    s = state.load()
    buddy, frame_list = _buddy_frames(s)
    if buddy is None:
        return "no buddy yet"
    out = paths.STATE_DIR / "frames"
    out.mkdir(parents=True, exist_ok=True)
    for i, (grid, palette) in enumerate(frame_list):
        (out / f"frame{i}.png").write_bytes(png.grid_to_png(grid, palette, scale))
    if len(frame_list) == 1:  # chibi: synthesize frame1 as blink
        from lib import sprites
        grid, palette = frame_list[0]
        (out / "frame1.png").write_bytes(
            png.grid_to_png(sprites.closed_eyes(grid), palette, scale))
    event = state.read_event("cross") or {}
    announce = event.get("detail", "") if time.time() - event.get("ts", 0) < 600 else ""
    (out / "meta.json").write_text(json.dumps({
        "name": buddy["name"], "level": buddy["level"],
        "shiny": bool(buddy.get("shiny")), "announce": announce,
        "balls": s["trainer"].get("balls", 0), "streak": s["trainer"].get("streak", 0),
    }), encoding="utf-8")
    return str(out)


def _wild_frames(entry):
    from lib import data, packs
    wtype = data.WILDS.get(entry["name"], ("Normal",))[0]
    return packs.sprite_frames(entry["name"], wtype, entry.get("shiny"))


def _box_frame(name, ptype, shiny):
    """First Gen 5 frame for menu-bar battle-screen stills (PNG surface)."""
    from lib import packs
    return packs.gen5_frames(name, ptype, shiny)[0]


BAR_POINT_HEIGHT = 20  # how tall the bar sprite displays, in points


def _bar_dpi(grid, scale=4):
    """DPI that makes a scaled sprite render at BAR_POINT_HEIGHT points."""
    return len(grid) * scale * 72 / BAR_POINT_HEIGHT


_CUTSCENE_TEXT = {
    "caught": {"alert": "❗", "vs": "a wild {name}!", "wobble": "…", "result": "GOTCHA!"},
    "fled": {"alert": "❗", "vs": "a wild {name}!", "wobble": "wait—", "result": "it fled…"},
    "no_balls": {"alert": "❗", "vs": "a wild {name}!", "wobble": "😱", "result": "no balls!"},
}


def _evolution_line(entry, phase):
    import base64
    from lib import data, packs, png, scene
    new_name = entry["name"]
    old_name = data.PRE_EVOLUTION.get(new_name, new_name)
    # type only matters for the silhouette-tint fallback; walk to the chain root
    root = old_name
    while root in data.PRE_EVOLUTION:
        root = data.PRE_EVOLUTION[root]
    ptype = data.STARTERS.get(root, {}).get("type") or data.WILDS.get(root, ("Normal",))[0]
    new_frames = packs.sprite_frames(new_name, ptype)
    old_frames = packs.sprite_frames(old_name, ptype)
    new_frame = new_frames[phase % len(new_frames)]
    old_frame = old_frames[phase % len(old_frames)]
    grid, palette = scene.evolution_bar(old_frame, new_frame, phase)
    img = base64.b64encode(
        png.grid_to_png(grid, palette, 4, dpi=_bar_dpi(grid))).decode()
    if phase in scene.EVO_SHOCK:
        text = "What?"
    elif phase in scene.EVO_FLASH:
        text = f"{old_name.upper()} is evolving!"
    elif phase in scene.EVO_MORPH:
        text = "…"
    elif phase in scene.EVO_REVEAL:
        text = f"{new_name.upper()}!"
    else:
        text = f"evolved into {new_name.upper()}!"
    return f"{text} | image={img}"


def _cutscene_line(entry, phase, frame_list, frame_idx):
    import base64
    from lib import png, scene
    wild = _wild_frames(entry)
    grid, palette = scene.battle_bar(
        frame_list[frame_idx % len(frame_list)],
        wild[frame_idx % len(wild)], phase, entry["kind"])
    img = base64.b64encode(
        png.grid_to_png(grid, palette, 4, dpi=_bar_dpi(grid))).decode()
    texts = _CUTSCENE_TEXT[entry["kind"]]
    if phase in scene.PHASE_ALERT:
        text = texts["alert"]
    elif phase in scene.PHASE_VS:
        text = texts["vs"].format(name=entry["name"])
    elif phase in scene.PHASE_WOBBLE:
        text = texts["wobble"]
    else:
        text = texts["result"]
    return f"{text} | image={img}"


_RARITY_ORDER = {"starter": 0, "legendary": 1, "rare": 2, "uncommon": 3, "common": 4}


def _dex_icon(p):
    import base64
    from lib import packs, png
    grid, palette = packs.gen5_frames(p["name"], p["type"], p.get("shiny"))[0]
    dpi = len(grid) * 2 * 72 / 16  # ~16pt submenu icons
    return base64.b64encode(png.grid_to_png(grid, palette, 2, dpi=dpi)).decode()


def _dex_submenu(s):
    from lib import render
    total = len(render._dex_universe())
    species = {}
    for p in s["pokemon"]:
        best = species.get(p["name"])
        if best is None or p["level"] > best["level"]:
            species[p["name"]] = p
    mons = sorted(species.values(),
                  key=lambda p: (_RARITY_ORDER.get(p["rarity"], 9), -p["level"], p["name"]))
    lines = [f"📖 Pokédex  {len(species)}/{total}"]
    for p in mons:
        shiny = "✨" if p.get("shiny") else ""
        lines.append(f"--{shiny}{p['name']}  Lv.{p['level']}  ·  {p['rarity']}"
                     f" | image={_dex_icon(p)}")
    return lines


def _switch_submenu(s, active_name):
    script = Path(__file__).resolve()
    names = sorted({p["name"] for p in s["pokemon"]} - {active_name})
    if not names:
        return []
    lines = ["🔄 Switch buddy"]
    for name in names:
        lines.append(f"--{name} | bash=/usr/bin/python3 param1={script} "
                     f"param2=switch param3={name} terminal=false")
    return lines


def _last_encounter_section(now, frame_list):
    import base64
    from lib import journal, png, scene
    entry = journal.latest_encounter(600, now)
    if entry is None:
        return []
    from lib import data, state as st
    buddy = st.active_pokemon(st.load())
    buddy_box = _box_frame(buddy["name"], buddy["type"], buddy.get("shiny"))
    wtype = data.WILDS.get(entry["name"], ("Normal",))[0]
    wild_box = _box_frame(entry["name"], wtype, entry.get("shiny"))
    grid, palette = scene.battle_screen(buddy_box, wild_box, entry["kind"])
    img = base64.b64encode(png.grid_to_png(grid, palette, 2)).decode()
    dialogue = {"caught": f"You caught {entry['name'].upper()}!",
                "fled": f"Wild {entry['name'].upper()} fled!",
                "no_balls": f"Wild {entry['name'].upper()} appeared — no balls!"}[entry["kind"]]
    return ["---", f"{dialogue} | image={img}"]


def _safari_section(s):
    """Dropdown battle UI for a pending encounter: scene image + action buttons."""
    import base64
    from lib import data, packs, png, safari as sf, scene
    pending = s.get("pending_encounter")
    if not pending:
        return []
    script = Path(__file__).resolve()
    buddy = state.active_pokemon(s)
    buddy_box = _box_frame(buddy["name"], buddy["type"], buddy.get("shiny"))
    wild_box = _box_frame(pending["name"], pending["type"], pending["shiny"])
    grid, palette = scene.battle_screen(buddy_box, wild_box, "fled")
    img = base64.b64encode(png.grid_to_png(grid, palette, 2)).decode()
    balls = s["trainer"].get("balls", 0)

    def action(label, name):
        return (f"--{label} | bash=/usr/bin/python3 param1={script} "
                f"param2=safari param3={name} terminal=false refresh=true")

    lines = [
        "---",
        f"🌿 SAFARI — {sf.status_text(pending)} | image={img}",
        f"--{pending['last_msg']}",
        f"--{sf.odds_hint(pending)}",
        action("🪨 Throw Rock", "rock"),
        action("🍖 Throw Bait", "bait"),
        action(f"⚾ Throw Ball ({balls})" if balls else "⚾ Out of balls", "ball"),
        action("🏃 Run away", "run"),
    ]
    return lines


def _menubar_lines(s, frame_idx):
    import base64, time
    from lib import journal, png, render, safari as sf, scene
    buddy, frame_list = _buddy_frames(s)
    if buddy is None:
        return ["🥚 | dropdown=false"]
    now = time.time()

    bar_line = None
    pending = s.get("pending_encounter")
    evo = journal.latest_evolution(scene.EVOLUTION_SECS, now)
    if evo is not None:  # evolution ceremony (transient) outranks everything
        phase = scene.evolution_phase_for(now - evo["ts"])
        if phase is not None:
            bar_line = _evolution_line(evo, phase)
    if bar_line is None and pending:
        # a wild is waiting: show it in the bar with an alert
        wild = packs.sprite_frames(pending["name"], pending["type"], pending["shiny"])
        grid, palette = wild[frame_idx % len(wild)]
        icon = base64.b64encode(
            png.grid_to_png(grid, palette, 4, dpi=_bar_dpi(grid))).decode()
        bar_line = f"❗ | image={icon}"
    if bar_line is None:
        entry = journal.latest_encounter(scene.CUTSCENE_SECS, now)
        if entry is not None:
            phase = scene.phase_for(now - entry["ts"])
            if phase is not None:
                bar_line = _cutscene_line(entry, phase, frame_list, frame_idx)

    if bar_line is None:
        from lib import packs
        frames = packs.gen5_frames(buddy["name"], buddy["type"], buddy.get("shiny"))
        grid, palette = frames[frame_idx % len(frames)]  # animate the BW idle
        icon = base64.b64encode(
            png.grid_to_png(grid, palette, 4, dpi=_bar_dpi(grid))).decode()
        shiny = "✨" if buddy.get("shiny") else ""
        bar_line = f"{shiny} | image={icon}" if shiny else f"| image={icon}"

    trainer = s["trainer"]
    lines = [
        bar_line,
        "---",
        f"{buddy['emoji']} {buddy['name']} — {buddy['type']} · Lv.{buddy['level']}",
        f"XP {render.xp_bar(buddy, 12)}",
        f"🔥 streak {trainer.get('streak', 0)}d   ⚾ {trainer.get('balls', 0)}   "
        f"📖 {len({p['name'] for p in s['pokemon']})} species",
    ]
    event = state.read_event("cross") or {}
    if event.get("detail") and time.time() - event.get("ts", 0) < 600:
        lines.append(event["detail"])
    lines.extend(_safari_section(s))
    lines.extend(_last_encounter_section(now, frame_list))
    recent = journal.tail(3)
    if recent:
        lines.append("---")
        lines.extend(e.get("text", "?") for e in reversed(recent))
    script = Path(__file__).resolve()
    lines.append("---")
    lines.extend(_dex_submenu(s))
    lines.extend(_switch_submenu(s, buddy["name"]))
    lines.append(f"📜 Open journal | bash=/usr/bin/python3 param1={script} "
                 "param2=history param3=100 terminal=true")
    lines.append(f"Open status card | bash=/usr/bin/python3 param1={script} "
                 "param2=status terminal=true")
    return lines


def menubar(args):
    """SwiftBar output. --stream: long-running, 1s frame flips (streamable plugin)."""
    import time
    if "--stream" not in args:
        try:
            collect([], quiet=True)
        except Exception:
            pass
        return "\n".join(_menubar_lines(state.load(), int(time.time() / 15)))

    frame_idx = 0
    while True:
        if frame_idx % 60 == 0:  # collect cross-client XP once a minute
            try:
                collect([], quiet=True)
            except Exception:
                pass
        print("~~~")
        print("\n".join(_menubar_lines(state.load(), frame_idx)), flush=True)
        frame_idx += 1
        time.sleep(1)


def _resolve_safari(s, pending, outcome):
    """Translate a finished Safari encounter into collection + journal effects."""
    from lib import engine, journal, notify
    enc = {"name": pending["name"], "emoji": pending["emoji"],
           "rarity": pending["rarity"], "shiny": pending["shiny"]}
    if outcome["caught"]:
        already = any(p["name"] == pending["name"] for p in s["pokemon"])
        s["pokemon"].append(engine.new_pokemon(
            pending["name"], pending["type"], pending["emoji"],
            pending["rarity"], pending["shiny"]))
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


def safari(args):
    from lib import safari as sf
    import random
    action = args[0] if args else ""
    if action not in sf.ACTIONS:
        return "Usage: safari rock|bait|ball|run"
    with state.lock():
        s = state.load()
        pending = s.get("pending_encounter")
        if not pending:
            return "No wild pokémon right now."
        outcome = sf.ACTIONS[action](pending, s["trainer"], random.Random())
        msg = pending["last_msg"]
        if outcome["done"]:
            _resolve_safari(s, pending, outcome)
        state.save(s)
    return msg


def history(args):
    import time
    from lib import journal
    n = int(args[0]) if args and args[0].isdigit() else 20
    entries = journal.tail(n)
    if not entries:
        return "No journal yet — the story starts with your next turn."
    out, day = [], None
    for e in entries:
        d = time.strftime("%b %d", time.localtime(e.get("ts", 0)))
        if d != day:
            day = d
            out.append(f"\n{day}")
        out.append(f"  {e.get('text', '?')}")
    return "\n".join(out).lstrip("\n")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    args = sys.argv[2:]
    handlers = {
        "choose": choose,
        "switch": switch,
        "preview": preview,
        "export-chibi": export_chibi,
        "collect": collect,
        "tiny": tiny,
        "frames": frames,
        "menubar": menubar,
        "history": history,
        "safari": safari,
        "status": lambda a: render.status_card(state.load()),
        "dex": lambda a: (render.dex_grid(state.load())
                          if (sys.stdout.isatty() or "--grid" in a) and "--list" not in a
                          else render.dex(state.load())),
    }
    handler = handlers.get(cmd)
    if handler is None:
        print(__doc__.strip())
        sys.exit(2)
    try:
        print(handler(args))
    except BrokenPipeError:  # piped into head etc.
        sys.exit(0)


if __name__ == "__main__":
    main()
