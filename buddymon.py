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
    dest = Path.home() / "Pictures" / "buddymon"
    dest.mkdir(parents=True, exist_ok=True)
    payload = {name: {"grid": grid, "palette": palette}
               for name, (grid, palette) in sprites.SPRITES.items()}
    (dest / "chibi-pack.json").write_text(
        __import__("json").dumps(payload, indent=1), encoding="utf-8")
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
    from lib import collectors, engine
    with state.lock():
        s = state.load()
        if not s["pokemon"]:
            return "" if quiet else "No buddy yet — nothing to collect for."
        summary = collectors.collect(s, random.Random())
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
    from lib import engine, render, paths
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
    bar = render._xp_bar(buddy, 6).split(" ")[0]
    bits = [f"{shiny}{buddy['emoji']} {buddy['name']} Lv.{buddy['level']}", bar, mood]
    if trainer.get("streak", 0) >= 2:
        bits.append(f"🔥{trainer['streak']}")
    bits.append(f"⚾{trainer.get('balls', 0)}")
    event = state.read_event("cross")
    if event and event.get("detail") and time.time() - event.get("ts", 0) < 600:
        bits.append(event["detail"])
    return " ".join(bits)


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
