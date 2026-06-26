#!/usr/bin/env python3
"""buddymon CLI — used by the /buddymon:* commands and direct play.

Usage:
  buddymon.py choose <starter>    pick your starter (one-time)
  buddymon.py status              compact status summary
  buddymon.py dex [--grid]        collection by rarity
  buddymon.py switch <name>       make a caught pokemon your active buddy
  buddymon.py preview             render every sprite (art QA; both frames for packs)
  buddymon.py export-chibi        archive the chibi pack to ~/Pictures/buddymon/
  buddymon.py collect             count tokens from other agent CLIs
  buddymon.py tiny [--collect]    one-line plain-text status (tmux status bar)
  buddymon.py menubar             SwiftBar plugin output (sprite icon + dropdown)
  buddymon.py menu                interactive terminal UI (party/dex/status/tokens)
  buddymon.py tokens              token usage report
  buddymon.py history [N]         the buddy's journey journal (default last 20)
  buddymon.py safari <action>     play a turn vs a pending wild (rock|bait|ball|run)
  buddymon.py battle <action>     battle-mode turn (attack|ball|run)
  buddymon.py mode [auto|battle]  toggle/show encounter mode
"""
import base64
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import (  # noqa: E402
    battle as bt, collectors, data, engine, favorites, journal, notify, packs,
    paths, pixels, png, render, safari as sf, scene, sprites, state,
    token_usage, tui,
)

EVOLUTION_NOTICE_COLOR = "#4c1d95"
EVENT_NOTICE_COLOR = "#1e3a8a"
DOT_SEP = " · "


def choose(args):
    name = (args[0] if args else "").capitalize()
    s = state.load()
    if s["pokemon"]:
        return f"You already have a buddy ({state.active_pokemon(s)['name']}). Use switch instead."
    buddy = engine.create_starter(s, name)
    if buddy is None:
        return "Pick one of: " + ", ".join(data.STARTERS)
    state.save(s)
    journal.append("starter", f"{buddy['emoji']} {buddy['name']} chose you",
                   {"name": buddy["name"]})
    grid, palette = sprites.sprite_for(buddy["name"], buddy["type"])
    art = "\n".join(pixels.render(grid, palette))
    return f"{art}\n\n{buddy['emoji']} {buddy['name']} chose YOU! Tokens from every Claude Code turn feed your buddy."


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


def switch_id(args):
    target = (args[0] if args else "").strip()
    if not target:
        return "Usage: switch-id <id>"
    s = state.load()
    match = next((p for p in s["pokemon"] if str(p["id"]) == target), None)
    if match is None:
        return "That buddy is no longer in your collection. See /buddymon:dex"
    s["active"] = match["id"]
    state.save(s)
    return f"{match['emoji']} {match['name']} (Lv.{match['level']}) is now your buddy!"


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
        return "anchored existing client logs — tokens start counting from now"
    tok = summary["tokens"]
    raw = summary.get("raw_tokens", sum(tok.values()))
    return detail or (f"{raw} tokens counted" if raw else "no new tokens")


def tiny(args):
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
    bits.append(f"🪙{render.compact_number(trainer.get('total_tokens', 0))}")
    event = state.read_event("cross")
    if event and event.get("detail") and time.time() - event.get("ts", 0) < 600:
        detail = engine.display_event_detail(event["detail"])
        if detail:
            bits.append(detail)
    return " ".join(bits)


def _buddy_frames(s):
    buddy = state.active_pokemon(s)
    if buddy is None:
        return None, []
    return buddy, packs.sprite_frames(buddy["name"], buddy["type"], buddy.get("shiny"))


def _wild_frames(entry):
    """Compact gen2 frames for the bar cutscene replay (2-frame bounce)."""
    wtype = data.WILDS.get(entry["name"], ("Normal",))[0]
    return packs.sprite_frames(entry["name"], wtype, entry.get("shiny"))


def _battle_sprite(name, ptype, shiny):
    """First unique Gen 5 frame, for the dropdown battle-screen stills."""
    return packs.gen5_frames(name, ptype, shiny)[0]


BAR_POINT_HEIGHT = 20  # how tall the bar sprite displays, in points
ACTIVE_IMAGE_POINT_HEIGHT = 36
BATTLE_IMAGE_SCALE = 2
BATTLE_POINT_WIDTH = 240  # how wide the dropdown battle scene displays, in points


def _sprite_dpi(grid, scale=4, point_height=BAR_POINT_HEIGHT):
    """DPI that makes a scaled sprite render at a target point height."""
    return len(grid) * scale * 72 / point_height


def _bar_dpi(grid, scale=4):
    return _sprite_dpi(grid, scale, BAR_POINT_HEIGHT)


def _scene_dpi(grid, scale=2):
    """DPI that makes the battle scene render at BATTLE_POINT_WIDTH points wide,
    so it fills the dropdown's width instead of leaving a gap beside it."""
    return len(grid[0]) * scale * 72 / BATTLE_POINT_WIDTH


def _battle_scene_image(grid, palette):
    """Base64 PNG for SwiftBar battle rows.

    SwiftBar only exposes an image parameter, not a width parameter. Keep the
    pixel scale modest so the battle view stays readable without feeling huge.
    """
    return base64.b64encode(
        png.grid_to_png(
            grid, palette, BATTLE_IMAGE_SCALE,
            dpi=_scene_dpi(grid, BATTLE_IMAGE_SCALE),
        )
    ).decode()


_CUTSCENE_TEXT = {
    "caught": {"alert": "❗", "vs": "a wild {name}!", "wobble": "…", "result": "Caught {name}!"},
    "fled": {"alert": "❗", "vs": "a wild {name}!", "wobble": "wait—", "result": "it fled…"},
    "no_balls": {"alert": "❗", "vs": "a wild {name}!", "wobble": "😱", "result": "no balls!"},
}


def _evolution_line(entry, phase):
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


def _throw_line(pb, phase, frame_list):
    """Bar animation of a pokéball throw during a battle (arc → jiggle → result)."""
    wild = packs.sprite_frames(pb["name"], pb["type"], pb["shiny"])
    caught = pb["last_throw"].get("caught")
    if caught and (phase or 0) >= scene.THROW_SECS - 1:
        return _caught_line(pb["name"], pb["type"], pb["shiny"])
    grid, palette = scene.throw_jiggle_bar(frame_list[0], wild[0], phase or 0, pb["last_throw"])
    img = base64.b64encode(png.grid_to_png(grid, palette, 4, dpi=_bar_dpi(grid))).decode()
    return f"⚾ | image={img}"


def _caught_line(name, ptype, shiny=False):
    grid, palette = packs.gen5_frames(name, ptype, shiny)[0]
    img = base64.b64encode(png.grid_to_png(grid, palette, 4, dpi=_bar_dpi(grid))).decode()
    shiny_mark = "✨" if shiny else ""
    return f"🎉 Caught {shiny_mark}{name}! | image={img}"


def _cutscene_line(entry, phase, frame_list, frame_idx):
    wild = _wild_frames(entry)
    is_result_phase = not (
        phase in scene.PHASE_ALERT
        or phase in scene.PHASE_VS
        or phase in scene.PHASE_WOBBLE
    )
    if entry["kind"] == "caught" and is_result_phase:
        wtype = data.WILDS.get(entry["name"], ("Normal",))[0]
        return _caught_line(entry["name"], wtype, entry.get("shiny"))
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
        text = texts["result"].format(name=entry["name"])
    return f"{text} | image={img}"


SWITCH_SUBMENU_LIMIT = 20


def _switch_submenu(s):
    script = Path(__file__).resolve()
    active_id = s.get("active")
    mons = [p for p in favorites.favorites(s) if p["id"] != active_id]
    lines = [f"Switch buddy | sfimage=arrow.triangle.2.circlepath"]
    if not mons:
        lines.append(f"--No favorites yet — open Party | sfimage=star "
                     f"bash=/usr/bin/python3 param1={script} param2=open-menu "
                     f"param3=party terminal=false")
        return lines
    for p in mons[:SWITCH_SUBMENU_LIMIT]:
        shiny = "✨" if p.get("shiny") else ""
        label = DOT_SEP.join((f"{shiny}{p['name']}", f"Lv.{p['level']}"))
        lines.append(f"--{label} | bash=/usr/bin/python3 "
                     f"param1={script} param2=switch-id param3={p['id']} terminal=false")
    if len(mons) > SWITCH_SUBMENU_LIMIT:
        more = len(mons) - SWITCH_SUBMENU_LIMIT
        lines.append(f"--More in menu... ({more} more) | sfimage=ellipsis.circle "
                     f"bash=/usr/bin/python3 param1={script} param2=open-menu "
                     f"param3=party terminal=false")
    return lines


def _last_encounter_section(_s, _now):
    """Do not keep catch/flee recap art in the SwiftBar dropdown.

    The top bar already runs the short encounter cutscene. A longer image-backed
    dropdown recap can leave SwiftBar doing expensive CoreAnimation work after
    the moment has passed.
    """
    return []


def _fight_launcher(script, name):
    """Open the TUI to fight — the dropdown is a native menu (closes on click),
    so turn-by-turn play lives in the TUI (arrow-keys + enter, stays open)."""
    return (f"⌨️ Fight {name} in buddymon | bash=/usr/bin/python3 "
            f"param1={script} param2=open-menu terminal=false")


def _safari_section(s):
    """Dropdown Safari glance: the GB battle scene + status, then a launcher into
    the TUI. No per-action rows (they'd duplicate the command box and the menu
    closes on every click anyway)."""
    pending = s.get("pending_encounter")
    if not pending:
        return []
    script = Path(__file__).resolve()
    buddy = state.active_pokemon(s)
    buddy_box = _battle_sprite(buddy["name"], buddy["type"], buddy.get("shiny"))
    wild_box = _battle_sprite(pending["name"], pending["type"], pending["shiny"])
    grid, palette = scene.battle_screen(buddy_box, wild_box, "fled")
    img = _battle_scene_image(grid, palette)
    return [
        "---",
        f"| image={img}",
        f"🌿 {sf.status_text(pending)}",
        pending["last_msg"],
        sf.odds_hint(pending),
        _fight_launcher(script, pending["name"]),
    ]


def _battle_section(s):
    """Dropdown Battle-Mode glance: the GB battle scene + status, then a launcher
    into the TUI (same reasoning as Safari)."""
    pending = s.get("pending_battle")
    if not pending:
        return []
    script = Path(__file__).resolve()
    buddy = state.active_pokemon(s)
    buddy_box = _battle_sprite(buddy["name"], buddy["type"], buddy.get("shiny"))
    wild_box = _battle_sprite(pending["name"], pending["type"], pending["shiny"])
    grid, palette = scene.battle_screen(
        buddy_box, wild_box, "active",
        wild_hp_frac=bt.wild_hp_frac(pending), buddy_hp_frac=bt.buddy_hp_frac(pending))
    img = _battle_scene_image(grid, palette)
    return [
        "---",
        f"| image={img}",
        f"⚔️ {bt.status_text(pending)}",
        pending["last_msg"],
        DOT_SEP.join((f"catch ~{round(bt.catch_probability(pending) * 100)}%", "⚾ ∞")),
        _fight_launcher(script, pending["name"]),
    ]


def _is_animating(s, now):
    """Only transient windows animate: evolution ceremony, encounter cutscene,
    and an in-flight pokéball throw. Idle and waiting render a static frame —
    emitting a fresh PNG every second otherwise balloons SwiftBar's cache."""
    pb = s.get("pending_battle")
    return bool(journal.latest_evolution(scene.EVOLUTION_SECS, now)
                or journal.latest_encounter(scene.CUTSCENE_SECS, now)
                or (pb and bt.throwing(pb, now)))


def _bar_line(s, buddy, frame_list, frame_idx):
    """The menu-bar item. Animates only during evolution/cutscene windows;
    idle + waiting-encounter are static (one repeated image)."""
    now = time.time()
    pending = s.get("pending_encounter")
    pb = s.get("pending_battle")

    evo = journal.latest_evolution(scene.EVOLUTION_SECS, now)
    if evo is not None:
        phase = scene.evolution_phase_for(now - evo["ts"])
        if phase is not None:
            return _evolution_line(evo, phase)
    if pb and bt.throwing(pb, now):  # pokéball mid-air: arc → jiggle → result
        phase = scene.throw_phase_for(now - pb["last_throw"]["ts"])
        return _throw_line(pb, phase, frame_list)
    entry = journal.latest_encounter(scene.CUTSCENE_SECS, now)
    if entry is not None:
        phase = scene.phase_for(now - entry["ts"])
        if phase is not None:
            return _cutscene_line(entry, phase, frame_list, frame_idx)
    if pending or pb:  # a wild is waiting — keep the buddy, flag it with ❗
        grid, palette = packs.gen5_frames(buddy["name"], buddy["type"], buddy.get("shiny"))[0]
        icon = base64.b64encode(png.grid_to_png(grid, palette, 4, dpi=_bar_dpi(grid))).decode()
        return f"❗ | image={icon}"
    evo_notice = journal.latest_evolution(EVOLUTION_BAR_NOTICE_SECS, now)
    if evo_notice is not None:
        grid, palette = packs.gen5_frames(buddy["name"], buddy["type"], buddy.get("shiny"))[0]
        icon = base64.b64encode(png.grid_to_png(grid, palette, 4, dpi=_bar_dpi(grid))).decode()
        return f"🎊 {evo_notice['name'].upper()}! | image={icon}"

    grid, palette = packs.gen5_frames(buddy["name"], buddy["type"], buddy.get("shiny"))[0]
    icon = base64.b64encode(png.grid_to_png(grid, palette, 4, dpi=_bar_dpi(grid))).decode()
    shiny = "✨" if buddy.get("shiny") else ""
    return f"{shiny} | image={icon}" if shiny else f"| image={icon}"


def _active_pokemon_section(buddy, gender, now):
    """Facebook-style media row: real sprite avatar plus identity/meta text."""
    grid, palette = packs.gen5_frames(buddy["name"], buddy["type"], buddy.get("shiny"))[0]
    img = base64.b64encode(
        png.grid_to_png(
            grid,
            palette,
            4,
            dpi=_sprite_dpi(grid, 4, ACTIVE_IMAGE_POINT_HEIGHT),
        )
    ).decode()
    name = f"✨ {buddy['name']}" if buddy.get("shiny") else buddy["name"]
    title = DOT_SEP.join(part for part in (name, f"Lv.{buddy['level']}", gender) if part)
    return [
        f"{title} | image={img}",
        f"{_caught_meta(buddy.get('caught_at'), now)} | color=#6b7280",
    ]


def _caught_meta(caught_at, now):
    if not caught_at:
        return DOT_SEP.join(("Age unknown", "Caught unknown"))
    days = max(0, int((now - caught_at) // 86400))
    day_word = "day" if days == 1 else "days"
    caught = time.localtime(caught_at)
    caught_date = f"{caught.tm_mon}/{caught.tm_mday}/{caught.tm_year % 100:02d}"
    return DOT_SEP.join((f"{days} {day_word} old", f"Caught {caught_date}"))


def _level_progress_line(buddy):
    level = buddy.get("level", 1)
    if level >= engine.LEVEL_CAP:
        return f"Lv.{level} {render.xp_bar(buddy, 12)}{DOT_SEP}MAX | color=#1f2937"
    floor = engine.xp_for_level(level)
    ceiling = engine.xp_for_level(level + 1)
    current = max(0, int(buddy.get("xp", 0)) - floor)
    span = max(1, ceiling - floor)
    pct = min(100, int(current * 100 / span))
    remaining = max(0, ceiling - int(buddy.get("xp", 0)))
    bar = render.xp_bar(buddy, 12).split(" ", 1)[0]
    return (
        f"Lv.{level} {bar} {pct}%{DOT_SEP}{remaining:,} to Lv.{level + 1} "
        "| color=#1f2937"
    )


def _dropdown_stats_line(s):
    trainer = s["trainer"]
    species_n = len({p["name"] for p in s["pokemon"]})
    stats = DOT_SEP.join((
        f"streak {trainer.get('streak', 0)}d",
        f"◓ {trainer.get('balls', 0)}",
        f"📖 {species_n} species",
    ))
    return f"{stats} | sfimage=flame.fill color=#8e8e93"


def _event_time_label(ts):
    try:
        value = float(ts)
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    return time.strftime("%I:%M %p", time.localtime(value)).lstrip("0")


def _dropdown_event_detail(detail, latest_evolution=None, event_ts=None):
    text = engine.display_event_detail(detail)
    if latest_evolution and text.startswith("🎊 evolved into"):
        marker = "!  "
        text = text.split(marker, 1)[1].strip() if marker in text else ""
    label = _event_time_label(event_ts)
    if text and label:
        return DOT_SEP.join((text, label))
    return text


def _dropdown_lines(s, buddy):
    """The dropdown body (heavy: many sprite PNGs). Only visible on click, so
    the stream rebuilds it on a slow cadence, not every tick."""
    now = time.time()
    g = render.gender_symbol(buddy)
    active_lines = _active_pokemon_section(buddy, g, now)
    lines = ["---", active_lines[0], _level_progress_line(buddy)]
    lines.extend(active_lines[1:])
    evo = journal.latest_evolution(EVOLUTION_DROPDOWN_NOTICE_SECS, now)
    if evo is not None:
        lvl = f" Lv.{evo['level']}" if evo.get("level") else ""
        lines.append(
            f"🎊 evolved into {evo['name']}{lvl} | color={EVOLUTION_NOTICE_COLOR}"
        )
    event = state.read_event("cross") or {}
    if event.get("detail") and now - event.get("ts", 0) < 600:
        detail = _dropdown_event_detail(event["detail"], evo, event.get("ts"))
        if detail:
            lines.append(f"{detail} | color={EVENT_NOTICE_COLOR}")
    lines.extend(_safari_section(s))      # auto mode, rare/legendary
    lines.extend(_battle_section(s))      # battle mode, any wild
    lines.extend(_last_encounter_section(s, now))
    # The menu bar is the ambient glance; full browsing lives in the
    # launchable TUI to keep this uncluttered.
    script = Path(__file__).resolve()
    lines.append("---")
    lines.append(_dropdown_stats_line(s))
    lines.append(f"Open menu | sfimage=gearshape bash=/usr/bin/python3 "
                 f"param1={script} param2=open-menu terminal=false")
    lines.append(
        f"{_token_usage_menu_title()} | sfimage=chart.bar bash=/usr/bin/python3 "
        f"param1={script} param2=open-menu param3=tokens terminal=false"
    )
    lines.extend(_switch_submenu(s))
    return lines


def _token_usage_menu_title():
    try:
        totals = token_usage.current_day_totals()
    except Exception:
        return "Token Usage"
    today = token_usage.compact_tokens(totals.get("today", 0))
    yesterday = token_usage.compact_tokens(totals.get("yesterday", 0))
    return DOT_SEP.join(("Token Usage", f"Today {today}", f"Yesterday {yesterday}"))


def _menubar_lines(s, frame_idx):
    buddy, frame_list = _buddy_frames(s)
    if buddy is None:
        return ["🥚 | dropdown=false"]
    return [_bar_line(s, buddy, frame_list, frame_idx)] + _dropdown_lines(s, buddy)


IDLE_HEARTBEAT = 20  # when idle, re-emit at most this often (SwiftBar caches images)
DROPDOWN_EVERY = 10  # during animation, rebuild the heavy dropdown only every Nth frame
EVOLUTION_BAR_NOTICE_SECS = 2 * 60 * 60
EVOLUTION_DROPDOWN_NOTICE_SECS = 6 * 60 * 60


def menubar(args):
    """SwiftBar output. --stream: long-running. Emits a fresh frame every ~1s
    ONLY during the brief evolution/cutscene windows; when idle it re-emits at
    most every IDLE_HEARTBEAT seconds (or immediately on a state change), since
    feeding SwiftBar a new PNG every second balloons its image cache."""
    if "--stream" not in args:
        try:
            collect([], quiet=True)
        except Exception:
            pass
        return "\n".join(_menubar_lines(state.load(), int(time.time() / 15)))

    # Cross-client token collection is owned by the launchd agent (every 5 min);
    # the stream re-reads state only when state.json changes.
    frame_idx, dropdown, s, last_mtime, last_emit = 0, None, None, -1.0, 0.0
    while True:
        now = time.time()
        try:
            mtime = paths.STATE_FILE.stat().st_mtime
        except OSError:
            mtime = 0.0
        changed = mtime != last_mtime
        if s is None or changed:
            s = state.load()
            last_mtime = mtime
            dropdown = None  # state changed → dropdown stale

        buddy, frame_list = _buddy_frames(s)
        animating = buddy is not None and _is_animating(s, now)
        # emit only when it'll actually differ: animating, state changed, or the
        # idle heartbeat elapsed. Otherwise the menu already shows the right thing.
        if not (animating or changed or dropdown is None or now - last_emit >= IDLE_HEARTBEAT):
            time.sleep(1)
            continue

        if buddy is None:
            print("~~~\n🥚 | dropdown=false", flush=True)
        else:
            if dropdown is None or (animating and frame_idx % DROPDOWN_EVERY == 0):
                dropdown = _dropdown_lines(s, buddy)
            bar = _bar_line(s, buddy, frame_list, frame_idx)
            print("~~~")
            print("\n".join([bar] + dropdown), flush=True)
        last_emit = now
        if animating:
            frame_idx += 1
        time.sleep(1)


def safari(args):
    with state.lock():
        s = state.load()
        _, msg = sf.take_turn(s, args[0] if args else "", random.Random())
        state.save(s)
    return msg


def battle(args):
    with state.lock():
        s = state.load()
        _, msg = bt.take_turn(s, args[0] if args else "", random.Random())
        state.save(s)
    return msg


def mode(args):
    """Toggle/show the encounter mode: 'auto' (Safari) or 'battle'."""
    with state.lock():
        s = state.load()
        cur = s.get("mode", "auto")
        target = args[0] if args else ("battle" if cur == "auto" else "auto")
        if target not in ("auto", "battle"):
            return "Usage: mode auto|battle"
        s["mode"] = target
        state.save(s)
    return f"encounter mode: {target}" + (
        "  — wild spawns are now weaken-then-catch battles" if target == "battle"
        else "  — commons auto-catch, rare/legendary use Safari")


def menu(args):
    """Launch the interactive terminal UI."""
    tui.run(args[0] if args else None)
    return ""


def open_menu(args):
    """Open the interactive menu in Ghostty when available, else Terminal.app."""
    notify.open_menu(args[0] if args else None)
    return ""


def tokens(_args):
    return "\n".join(token_usage.report_lines())


def history(args):
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
        "switch-id": switch_id,
        "preview": preview,
        "export-chibi": export_chibi,
        "collect": collect,
        "tiny": tiny,
        "menubar": menubar,
        "menu": menu,
        "open-menu": open_menu,
        "tokens": tokens,
        "history": history,
        "safari": safari,
        "battle": battle,
        "mode": mode,
        "status": lambda a: render.status_summary(state.load()),
        "dex": lambda a: (render.dex_grid(state.load())
                          if "--grid" in a and "--list" not in a
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
