#!/usr/bin/env python3
"""Generate README screenshots from BuddyMon's actual render surfaces."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SOURCE_STATE_ROOT = Path(
    os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
)
SOURCE_PACKS = SOURCE_STATE_ROOT / "buddymon" / "packs"
DEMO_HOME_CONTEXT = tempfile.TemporaryDirectory(prefix="buddymon-readme-")
DEMO_HOME = Path(DEMO_HOME_CONTEXT.name)
DEMO_STATE_ROOT = DEMO_HOME / ".local" / "state"
os.environ["HOME"] = str(DEMO_HOME)
os.environ["XDG_STATE_HOME"] = str(DEMO_STATE_ROOT)

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from lib import (  # noqa: E402
    battle,
    data,
    engine,
    packs,
    png,
    render,
    scene,
    showcase_export,
    state,
    token_usage,
    tui,
)


OUT = ROOT / "docs" / "screenshots"
ANSI_RE = re.compile(r"\x1b\[([0-9;?;]*)[A-Za-z]")
INK = (236, 244, 255)
MUTED = (148, 163, 184)
TERM_BG = (12, 17, 28)
CYAN = (103, 232, 249)
GREEN = (83, 220, 155)
GOLD = (245, 196, 66)
RED = (248, 113, 113)


def _font(size: int, mono: bool = False):
    paths = (
        ("/System/Library/Fonts/Menlo.ttc", mono),
        ("/System/Library/Fonts/SFNSMono.ttf", mono),
        ("/System/Library/Fonts/Helvetica.ttc", not mono),
    )
    for path, matches in paths:
        if matches and Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


FONT = _font(15, mono=True)
FONT_SMALL = _font(13, mono=True)


def _usage_event(ts: datetime, tokens: int) -> dict:
    return {
        "timestamp": ts.isoformat(),
        "message": {
            "usage": {
                "input_tokens": tokens,
                "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }
        },
    }


def _write_fake_usage(home: Path) -> None:
    claude_dir = home / ".claude" / "projects" / "readme-demo"
    claude_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()
    rows = [
        _usage_event(now - timedelta(hours=2), 132_000_000),
        _usage_event(now - timedelta(hours=1), 78_000_000),
        _usage_event(now - timedelta(days=1, hours=1), 94_000_000),
        _usage_event(now - timedelta(days=2, hours=4), 116_000_000),
    ]
    (claude_dir / "session.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    now_path = now.strftime("%Y/%m/%d")
    codex_dir = home / ".codex" / "sessions" / now_path
    codex_dir.mkdir(parents=True, exist_ok=True)
    codex_rows = []
    running = 0
    for offset, tokens in enumerate((44_000_000, 52_000_000, 39_000_000)):
        running += tokens
        codex_rows.append({
            "timestamp": (now - timedelta(hours=3 - offset)).isoformat(),
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": running,
                        "output_tokens": 0,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                    }
                },
            },
        })
    (codex_dir / "rollout-readme-demo.jsonl").write_text(
        "\n".join(json.dumps(row) for row in codex_rows) + "\n",
        encoding="utf-8",
    )


def _mon(
    pid: str,
    name: str,
    level: int,
    shiny: bool = False,
    rarity: Optional[str] = None,
) -> dict:
    ptype, emoji = data.species_info(name)
    if name in data.WILDS:
        ptype, emoji, default_rarity = data.WILDS[name]
    else:
        default_rarity = "starter"
    return {
        "id": pid,
        "name": name,
        "type": ptype,
        "emoji": emoji,
        "rarity": rarity or default_rarity,
        "level": level,
        "xp": engine.xp_for_level(level),
        "shiny": shiny,
        "caught_at": time.time() - int(pid[-2:], 16) * 3600,
    }


def _seed_demo_state() -> dict:
    state_dir = DEMO_STATE_ROOT / "buddymon"
    team = [
        _mon("readme01", "Charizard", 72, rarity="starter"),
        _mon("readme02", "Mewtwo", 55, shiny=True, rarity="legendary"),
        _mon("readme03", "Dragonite", 55, rarity="rare"),
        _mon("readme04", "Gengar", 44, rarity="rare"),
        _mon("readme05", "Pikachu", 38, rarity="starter"),
        _mon("readme06", "Staryu", 28, shiny=True, rarity="common"),
    ]

    demo = state.default_state()
    demo["mode"] = "battle"
    demo["pokemon"] = team
    demo["active"] = team[0]["id"]
    demo["trainer"].update({
        "streak": 14,
        "balls": 37,
        "total_xp": 2_451_900,
        "total_tokens": 428_600_000,
    })
    demo["showcase"] = {"slots": [pokemon["id"] for pokemon in team]}

    pending = battle.start({
        "name": "Mewtwo",
        "type": "Psychic",
        "emoji": "DNA",
        "rarity": "legendary",
        "shiny": True,
        "level": 55,
    }, team[0])
    pending["wild_hp"] = round(pending["wild_hp_max"] * 0.34)
    pending["buddy_hp"] = round(pending["buddy_hp_max"] * 0.72)
    pending["last_msg"] = "A shiny Mewtwo is testing your focus."
    demo["pending_battle"] = pending

    state.save(demo)
    destination_packs = state_dir / "packs"
    if SOURCE_PACKS.exists():
        shutil.copytree(SOURCE_PACKS, destination_packs)
    else:
        (destination_packs / "gen5").mkdir(parents=True, exist_ok=True)
        (destination_packs / "gen2.json").write_text("{}", encoding="utf-8")
        (destination_packs / "box.json").write_text("{}", encoding="utf-8")
        (destination_packs / "gen5" / "installed.json").write_text(
            "{}", encoding="utf-8"
        )
    _write_fake_usage(DEMO_HOME)
    return demo


def _standard_color(code: int, dim: bool = False):
    table = {
        30: (30, 41, 59),
        31: RED,
        32: GREEN,
        33: GOLD,
        34: (96, 165, 250),
        35: (216, 180, 254),
        36: CYAN,
        37: INK,
        90: MUTED,
    }
    color = table.get(code, INK)
    return tuple(round(c * 0.68) for c in color) if dim else color


def _ansi_cells(line: str):
    fg, bg, dim = INK, None, False
    i = 0
    while i < len(line):
        if line[i] == "\x1b":
            match = ANSI_RE.match(line, i)
            if match:
                nums = [int(p) for p in match.group(1).split(";") if p.isdigit()]
                j = 0
                while j < len(nums):
                    code = nums[j]
                    if code == 0:
                        fg, bg, dim = INK, None, False
                    elif code == 2:
                        dim = True
                    elif code in (30, 31, 32, 33, 34, 35, 36, 37, 90):
                        fg = _standard_color(code, dim)
                    elif code == 38 and j + 4 < len(nums) and nums[j + 1] == 2:
                        fg = tuple(nums[j + 2:j + 5])
                        if dim:
                            fg = tuple(round(c * 0.68) for c in fg)
                        j += 4
                    elif code == 48 and j + 4 < len(nums) and nums[j + 1] == 2:
                        bg = tuple(nums[j + 2:j + 5])
                        j += 4
                    j += 1
                i = match.end()
                continue
        yield line[i], fg, bg
        i += 1


def _screenshot_line(line: str):
    replacements = {
        "\ufe0f": "",
        "⚾": "balls ",
        "🪙": "tokens ",
        "💰": "$",
        "✨": "*",
        "🔥": "streak ",
        "⚙": "",
        "⚔": "battle ",
        "🧬": "",
        "🐉": "",
        "📖": "dex ",
        "◓": "balls",
        "▱": "-",
        "·": "-",
        "—": "-",
    }
    for old, new in replacements.items():
        line = line.replace(old, new)
    return line


def _draw_ansi(draw, line: str, x: int, y: int, cell_w: int, cell_h: int, font, max_cols: int):
    col = 0
    for ch, fg, bg in _ansi_cells(_screenshot_line(line)):
        if col >= max_cols:
            break
        cx = x + col * cell_w
        if bg:
            draw.rectangle([cx, y, cx + cell_w, y + cell_h], fill=bg)
        if ch == "▀":
            draw.rectangle([cx, y, cx + cell_w, y + cell_h // 2], fill=fg)
            if bg:
                draw.rectangle([cx, y + cell_h // 2, cx + cell_w, y + cell_h], fill=bg)
        elif ch == "▄":
            if bg:
                draw.rectangle([cx, y, cx + cell_w, y + cell_h // 2], fill=bg)
            draw.rectangle([cx, y + cell_h // 2, cx + cell_w, y + cell_h], fill=fg)
        elif ch == "█":
            draw.rectangle([cx, y, cx + cell_w, y + cell_h], fill=fg)
        else:
            draw.text((cx, y - 1), ch, fill=fg, font=font)
        col += 1


def terminal_png(lines, path: Path, cols: int = 92, rows: int = 26, font=FONT) -> None:
    cell_w, cell_h = 9, 18
    pad_x, pad_y = 28, 24
    width = pad_x * 2 + cols * cell_w
    height = pad_y * 2 + rows * cell_h
    img = Image.new("RGB", (width, height), TERM_BG)
    draw = ImageDraw.Draw(img)
    for row, line in enumerate(lines[:rows]):
        _draw_ansi(draw, line, pad_x, pad_y + row * cell_h, cell_w, cell_h, font, cols)
    img.save(path)


def battle_png(s, path: Path) -> None:
    active = state.active_pokemon(s)
    pending = s.get("pending_battle")
    if not active or not pending:
        raise SystemExit("demo state needs an active pokemon and pending_battle")
    buddy = packs.gen5_frames(active["name"], active.get("type", "Normal"), active.get("shiny"))[0]
    wild = packs.gen5_frames(pending["name"], pending.get("type", "Normal"), pending.get("shiny"))[0]
    grid, palette = scene.battle_screen(
        buddy,
        wild,
        "active",
        wild_hp_frac=pending["wild_hp"] / max(1, pending["wild_hp_max"]),
        buddy_hp_frac=pending["buddy_hp"] / max(1, pending["buddy_hp_max"]),
        options=("FIGHT", "BALL", "RUN", "PACK"),
    )
    path.write_bytes(png.grid_to_png(grid, palette, scale=4))


def encounter_lines(s):
    return tui._encounter_frame(s, "battle", 0).splitlines()


def menu_lines(s):
    return tui._menu_frame(tui._menu_items(s), 0).splitlines()


def statusline_lines(s):
    old_load, old_event = render.st.load, render.st.read_event
    try:
        render.st.load = lambda: s
        render.st.read_event = lambda _sid: {
            "event": "tool",
            "detail": "coding",
            "ts": time.time(),
        }
        return render.statusline({
            "session_id": "readme",
            "context": {"used_percentage": 64},
        }).splitlines()
    finally:
        render.st.load, render.st.read_event = old_load, old_event


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    s = _seed_demo_state()

    battle_png(s, OUT / "buddymon-main.png")
    battle_png(s, OUT / "encounter.png")
    (OUT / "showcase.png").write_bytes(showcase_export.render_showcase_png(s))
    terminal_png(menu_lines(s), OUT / "terminal-menu.png")
    terminal_png(encounter_lines(s), OUT / "battle-terminal.png")
    terminal_png(statusline_lines(s), OUT / "statusline.png", cols=72, rows=10, font=FONT_SMALL)
    terminal_png(token_usage.report_lines(), OUT / "token-report.png", cols=96, rows=24, font=FONT_SMALL)

    for name in (
        "buddymon-main.png",
        "encounter.png",
        "showcase.png",
        "terminal-menu.png",
        "battle-terminal.png",
        "statusline.png",
        "token-report.png",
    ):
        print(OUT / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
