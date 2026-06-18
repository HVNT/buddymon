"""Compose the statusline (sprite left, live info right) and CLI views."""
import time

from . import data, engine, packs, pixels, sprites
from . import state as st

DIM = "\x1b[2m"
BOLD = "\x1b[1m"
RED = "\x1b[31m"
YELLOW = "\x1b[33m"
CYAN = "\x1b[36m"
GRAY = "\x1b[90m"
RESET = "\x1b[0m"

IDLE_AFTER_SECS = 90
ANNOUNCE_SECS = 300

RARITY_BADGE = {"rare": "💎", "legendary": "🌟"}


def _xp_bar(buddy, width=10):
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
    else:  # chibi fallback: blink + bob
        grid, palette = frames[0]
        if asleep or int(now) % 5 == 0:
            grid = sprites.closed_eyes(grid)
        if not asleep and int(now) % 2:
            grid = pixels.bob(grid)
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
        f"{CYAN}{_xp_bar(buddy)}{RESET}",
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

    grid, palette = packs.sprite_frames(buddy["name"], buddy["type"], buddy.get("shiny"))[0]
    art = pixels.render(grid, palette)
    trainer = state["trainer"]
    shiny = "✨ shiny " if buddy.get("shiny") else ""
    species = {p["name"] for p in state["pokemon"]}

    info = [
        f"{BOLD}{buddy['emoji']} {buddy['name']}{RESET} — {shiny}{buddy['type']} · Lv.{buddy['level']}",
        f"XP   {_xp_bar(buddy, 16)}",
        f"🔥 streak {trainer.get('streak', 0)}d   ⚾ balls {trainer.get('balls', 0)}",
        f"📖 dex {len(species)} species · {len(state['pokemon'])} caught",
        f"Σ trainer XP {trainer.get('total_xp', 0):,}",
    ]
    lines = [f"{a}  {b}" for a, b in zip(art, info + [""] * len(art))]
    recent = sorted(state["pokemon"], key=lambda p: p.get("caught_at", 0), reverse=True)[:5]
    if recent:
        lines.append("")
        lines.append("recent: " + "  ".join(
            f"{'✨' if p.get('shiny') else ''}{p['emoji']}{p['name']}" for p in recent))
    return "\n".join(lines)


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
