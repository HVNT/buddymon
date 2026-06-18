"""Compose the statusline (sprite left, live info right) and CLI views."""
import time

from . import data, engine, packs, pixels, scene, sprites
from . import state as st

BOLD = "\x1b[1m"
RED = "\x1b[31m"
YELLOW = "\x1b[33m"
CYAN = "\x1b[36m"
GRAY = "\x1b[90m"
RESET = "\x1b[0m"

IDLE_AFTER_SECS = 90
ANNOUNCE_SECS = 300

RARITY_BADGE = {"rare": "💎", "legendary": "🌟"}
DEX_CELL_W = 28
DEX_CELL_H = 22
DEX_CELL_GAP = 3
DEX_UNKNOWN_COLOR = "#6b7a8c"


def compact_number(n):
    n = int(n or 0)
    for suffix, size in (("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
        if abs(n) >= size:
            value = n / size
            text = f"{value:.1f}".rstrip("0").rstrip(".")
            return f"{text}{suffix}"
    return str(n)


def gender_symbol(pokemon):
    """Stable ♂/♀ derived from the individual's id — cosmetic, no stored field
    and no migration. NOTE: genderless species (Beldum, most legendaries, …)
    aren't special-cased yet; correct handling needs PokéAPI gender_rate."""
    raw = str(pokemon.get("id") or "")
    try:
        parity = int(raw[:8] or "0", 16)
    except ValueError:
        parity = sum(map(ord, pokemon.get("name", "")))
    return "♂" if parity % 2 == 0 else "♀"


def xp_bar(buddy, width=10):
    floor = engine.xp_for_level(buddy["level"])
    if buddy["level"] >= engine.LEVEL_CAP:
        return "▰" * width + " MAX"
    ceil = engine.xp_for_level(buddy["level"] + 1)
    cur, span = buddy["xp"] - floor, ceil - floor
    filled = min(width, int(cur * width / span)) if span else width
    return "▰" * filled + "▱" * (width - filled) + f" {cur}/{span}"


def _mood(event, now):
    """Map the latest session event to (label, asleep)."""
    if event is None:
        return "😶 …", False
    age = now - event.get("ts", 0)
    kind = event.get("event")
    if kind == "working":
        frames = ("💭 thinking", "💭 thinking.", "💭 thinking..")
        return frames[int(now) % len(frames)], False
    if kind == "tool":
        tool = event.get("detail") or "working"
        return ("⚙️ " if int(now) % 2 else "🔧 ") + tool, False
    if kind == "tool_done":
        return "✨ on it", False
    if kind == "attention":
        return f"{YELLOW}❗ needs you{RESET}", False
    if kind == "session_start":
        return "👋 ready!", False
    # stop / unknown: rest, then sleep
    if age < IDLE_AFTER_SECS:
        return "😌 resting", False
    frames = ("💤 zzz", "💤 zZ…")
    return f"{GRAY}{frames[int(now // 2) % 2]}{RESET}", True


def _context_pct(payload):
    """Best-effort context usage percentage from the statusline payload."""
    ctx = payload.get("context") or {}
    for key in ("used_percentage", "used_percent", "percent_used"):
        if isinstance(ctx.get(key), (int, float)):
            return float(ctx[key])
    used, size = ctx.get("used_tokens"), ctx.get("context_window_size")
    if isinstance(used, (int, float)) and isinstance(size, (int, float)) and size:
        return 100.0 * used / size
    return None


def statusline(payload):
    state = st.load()
    buddy = st.active_pokemon(state)
    if buddy is None:
        return "🥚 no buddy yet — run /buddymon:choose to pick a starter"

    now = time.time()
    event = st.read_event(payload.get("session_id"))
    mood, asleep = _mood(event, now)

    frames = packs.sprite_frames(buddy["name"], buddy["type"], buddy.get("shiny"))
    if len(frames) > 1:  # official 2-frame icon: authentic party bounce
        grid, palette = frames[0] if asleep else frames[int(now) % len(frames)]
    elif buddy["name"] in sprites.SPRITES:  # chibi fallback: blink + bob
        grid, palette = frames[0]
        if asleep or int(now) % 5 == 0:
            grid = sprites.closed_eyes(grid)
        if not asleep and int(now) % 2:
            grid = pixels.bob(grid)
    else:
        grid, palette = frames[0]
    art = pixels.render(grid, palette, dim=0.55 if asleep else 1.0)

    shiny = "✨" if buddy.get("shiny") else ""
    badge = RARITY_BADGE.get(buddy.get("rarity"), "")
    trainer = state["trainer"]
    streak = trainer.get("streak", 0)
    species = {p["name"] for p in state["pokemon"]}

    tags = []
    if streak >= 2:
        tags.append(f"🔥{streak}")
    tags.append(f"⚾{trainer.get('balls', 0)}")
    tags.append(f"📖{len(species)}")
    tags.append(f"🪙{compact_number(trainer.get('total_tokens', 0))}")

    announce = ""
    if event and event.get("event") == "stop" and event.get("detail"):
        if now - event.get("ts", 0) < ANNOUNCE_SECS:
            announce = event["detail"]

    warn = ""
    pct = _context_pct(payload)
    if pct is not None and pct >= 90:
        warn = f"{RED}🆘 context {pct:.0f}%{RESET}"
    elif pct is not None and pct >= 75:
        warn = f"{YELLOW}🥵 context {pct:.0f}%{RESET}"

    info = [
        f"{BOLD}{shiny}{buddy['emoji']} {buddy['name']}{RESET} Lv.{buddy['level']} {badge}".rstrip(),
        f"{CYAN}{xp_bar(buddy)}{RESET}",
        mood,
        "  ".join(tags),
        announce or warn,
    ]
    lines = [f"{art_row}  {text}".rstrip() for art_row, text in zip(art, info)]
    if len(art) > len(info):
        lines += art[len(info):]
    return "\n".join(lines)


def status_card(state):
    buddy = st.active_pokemon(state)
    if buddy is None:
        return "No buddy yet. Run /buddymon:choose <starter> — options: " + ", ".join(data.STARTERS)

    grid, palette = packs.box_frames(buddy["name"], buddy["type"], buddy.get("shiny"))[0]
    art = pixels.render(grid, palette)
    trainer = state["trainer"]
    shiny = "✨ shiny " if buddy.get("shiny") else ""
    species = {p["name"] for p in state["pokemon"]}

    info = [
        f"{BOLD}{buddy['emoji']} {buddy['name']}{RESET} — {shiny}{buddy['type']} · Lv.{buddy['level']}",
        f"Tokens used {trainer.get('total_tokens', 0):,}",
        f"Level {xp_bar(buddy, 16)}",
        f"🔥 streak {trainer.get('streak', 0)}d   ⚾ balls {trainer.get('balls', 0)}",
        f"📖 dex {len(species)} species · {len(state['pokemon'])} caught",
    ]
    lines = [f"{a}  {b}" for a, b in zip(art, info + [""] * len(art))]
    recent = sorted(state["pokemon"], key=lambda p: p.get("caught_at", 0), reverse=True)[:5]
    if recent:
        lines.append("")
        lines.append("recent: " + "  ".join(
            f"{'✨' if p.get('shiny') else ''}{p['emoji']} {p['name']}" for p in recent))
    return "\n".join(lines)


def status_summary(state):
    buddy = st.active_pokemon(state)
    if buddy is None:
        return "No buddy yet. Run /buddymon:choose <starter> — options: " + ", ".join(data.STARTERS)

    trainer = state["trainer"]
    shiny = "✨ shiny " if buddy.get("shiny") else ""
    species = {p["name"] for p in state["pokemon"]}
    grid, palette = packs.sprite_frames(buddy["name"], buddy["type"], buddy.get("shiny"))[0]
    art = pixels.render(grid, palette)
    lines = [
        *art,
        f"{BOLD}{buddy['emoji']} {buddy['name']}{RESET} — {shiny}{buddy['type']} · Lv.{buddy['level']}",
        f"Tokens used {trainer.get('total_tokens', 0):,}",
        f"Level {xp_bar(buddy, 16)}",
        f"🔥 streak {trainer.get('streak', 0)}d   ⚾ balls {trainer.get('balls', 0)}",
        f"📖 dex {len(species)} species · {len(state['pokemon'])} caught",
    ]
    recent = sorted(state["pokemon"], key=lambda p: p.get("caught_at", 0), reverse=True)[:5]
    if recent:
        lines.append("")
        lines.append("recent: " + "  ".join(
            f"{'✨' if p.get('shiny') else ''}{p['emoji']} {p['name']}" for p in recent))
    return "\n".join(lines)


def _dex_universe():
    """All display species: full starter lines, then wilds by rarity."""
    order = {"legendary": 1, "rare": 2, "uncommon": 3, "common": 4}
    entries = []
    for name, info in data.STARTERS.items():  # base + every evolution form
        entries.append((name, info["type"], "starter"))
        entries += [(evo, info["type"], "starter") for evo, _, _ in info["evolutions"]]
    entries += [(name, data.STARTERS["Eevee"]["type"], "starter")
                for name, _ in data.EEVEE_BRANCHES]
    wilds = sorted(data.WILDS.items(), key=lambda kv: (order.get(kv[1][2], 9), kv[0]))
    entries += [(name, ptype, rarity) for name, (ptype, _, rarity) in wilds]
    return entries


def _uniform_grid(grid):
    rows = list(grid) or ["."]
    width = max(len(row) for row in rows) or 1
    return [row.ljust(width, ".") for row in rows]


def _fit_grid(grid, max_w, max_h):
    grid = _uniform_grid(grid)
    scale = min(1.0, max_w / len(grid[0]), max_h / len(grid))
    if scale < 1.0:
        grid = scene.scale_grid(grid, scale)
    return grid


def _pad_grid(grid, w, h):
    """Center a sprite grid in a w×h transparent box for uniform cells."""
    grid = _uniform_grid(grid)
    grid = grid[:h]
    left = max(0, (w - len(grid[0])) // 2)
    padded = [("." * left + row)[:w].ljust(w, ".") for row in grid]
    top = max(0, (h - len(padded)) // 2)
    blank = "." * w
    return [blank] * top + padded + [blank] * (h - top - len(padded))


def _dex_cell_art(name, ptype, shiny=False, revealed=True):
    grid, palette = packs.box_frames(name, ptype, shiny)[0]
    if not revealed:
        grid, palette = scene.silhouette((grid, palette), DEX_UNKNOWN_COLOR)
    grid = _fit_grid(grid, DEX_CELL_W, DEX_CELL_H)
    return _pad_grid(grid, DEX_CELL_W, DEX_CELL_H), palette


def dex_grid(state, columns=None):
    """Terminal pokédex: unique sprites, caught in color, uncaught as ??? shadows."""
    import shutil

    width = columns or shutil.get_terminal_size((80, 24)).columns
    cell_w, gap = DEX_CELL_W, DEX_CELL_GAP
    per_row = max(1, (width + gap) // (cell_w + gap))

    best = {}
    for p in state["pokemon"]:
        if p["name"] not in best or p["level"] > best[p["name"]]["level"]:
            best[p["name"]] = p

    universe = _dex_universe()
    caught_n = len([n for n, _, _ in universe if n in best])
    bar_w = 24
    filled = round(caught_n * bar_w / len(universe))
    out = [
        f"{BOLD}━━━ POKÉDEX ━━━{RESET}",
        f"{CYAN}{'▰' * filled}{'▱' * (bar_w - filled)}{RESET} {caught_n}/{len(universe)} species",
    ]

    def cell(name, ptype, rarity):
        p = best.get(name)
        grid, palette = _dex_cell_art(name, ptype, p.get("shiny") if p else False, bool(p))
        art = pixels.render(grid, palette)
        if p:
            label1 = f"{'✨' if p.get('shiny') else ''}{name}"
            plain2, label2 = f"Lv.{p['level']}", f"Lv.{p['level']}"
        else:
            label1, plain2, label2 = "???", rarity, f"{GRAY}{rarity}{RESET}"
        pad1 = max(0, (cell_w - len(label1)) // 2)
        pad2 = max(0, (cell_w - len(plain2)) // 2)
        return list(art) + [
            (" " * pad1 + label1[:cell_w]).ljust(cell_w),
            " " * pad2 + label2 + " " * (cell_w - pad2 - len(plain2)),
        ]

    by_rarity = {}
    for name, ptype, rarity in universe:
        by_rarity.setdefault(rarity, []).append((name, ptype, rarity))

    for rarity in ("starter", "legendary", "rare", "uncommon", "common"):
        group = by_rarity.get(rarity)
        if not group:
            continue
        out.append(f"\n{BOLD}{rarity.upper()}{RESET}")
        for i in range(0, len(group), per_row):
            cells = [cell(*entry) for entry in group[i:i + per_row]]
            for row_parts in zip(*cells):
                out.append((" " * gap).join(row_parts))
            out.append("")
    return "\n".join(out)


def dex(state):
    if not state["pokemon"]:
        return "Pokédex empty — your buddy will find wild pokémon while you code."
    by_rarity = {}
    for p in state["pokemon"]:
        by_rarity.setdefault(p["rarity"], {})[p["name"]] = p
    out = []
    for rarity in ("starter", "legendary", "rare", "uncommon", "common"):
        mons = by_rarity.get(rarity)
        if not mons:
            continue
        out.append(f"{BOLD}{rarity}{RESET}")
        for p in sorted(mons.values(), key=lambda q: -q["level"]):
            shiny = "✨" if p.get("shiny") else " "
            out.append(f"  {shiny}{p['emoji']} {p['name']:<12} Lv.{p['level']}")
    total = len(data.WILDS) + len(data.STARTERS)
    out.append(f"\n{len({p['name'] for p in state['pokemon']})}/{total} species")
    return "\n".join(out)
