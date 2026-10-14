#!/usr/bin/env python3
"""Capture README art from BuddyMon's shipping render surfaces."""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
BUILD_DIR = ROOT / ".build" / "readme-screenshots"
SNAPSHOT = BUILD_DIR / "readme-screenshot"
TERMINAL_STATE = (
    ROOT / ".build" / "readme-ghostty" / "state" / "buddymon" / "state.json"
)
SOURCE_STATE_ROOT = Path(
    os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
)
SOURCE_PACKS = SOURCE_STATE_ROOT / "buddymon" / "packs"

DEMO_HOME_CONTEXT = tempfile.TemporaryDirectory(prefix="buddymon-readme-")
DEMO_HOME = Path(DEMO_HOME_CONTEXT.name)
DEMO_STATE_ROOT = DEMO_HOME / ".local" / "state"
os.environ["HOME"] = str(DEMO_HOME)
os.environ["XDG_STATE_HOME"] = str(DEMO_STATE_ROOT)
os.environ["USER"] = "HUNT"
sys.path.insert(0, str(ROOT))

from lib import assets, battle, data, engine, menu_bar, showcase_export, state, trainer_card  # noqa: E402
from lib.app_fixtures import _build_menu_panel_fixture_status  # noqa: E402
from lib.app_payloads import _build_encounter_result_payload  # noqa: E402
from lib.app_views import _build_encounter_view  # noqa: E402


FIXED_TIME = 1_787_020_800.0


def _mon(
    pid: str,
    name: str,
    level: int,
    *,
    shiny: bool = False,
    rarity: str | None = None,
    caught_offset: int = 0,
) -> dict:
    ptype, emoji = data.species_info(name)
    if name in data.WILDS:
        ptype, emoji, default_rarity = data.WILDS[name]
    else:
        default_rarity = "starter"
    floor = engine.xp_for_level(level)
    ceiling = engine.xp_for_level(min(engine.LEVEL_CAP, level + 1))
    return {
        "id": pid,
        "name": name,
        "type": ptype,
        "emoji": emoji,
        "rarity": rarity or default_rarity,
        "level": level,
        "xp": floor + int((ceiling - floor) * 0.72),
        "shiny": shiny,
        "caught_at": FIXED_TIME - caught_offset,
    }


def _install_local_art_fixture(destination_root: Path = DEMO_STATE_ROOT) -> None:
    """Use the player's installed local art when present, without mutating it."""
    if not SOURCE_PACKS.exists():
        return
    destination = destination_root / "buddymon" / "packs"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE_PACKS, destination, dirs_exist_ok=True)


def _showcase_team() -> list[dict]:
    return [
        _mon(
            "readme-mewtwo",
            "Mewtwo",
            82,
            shiny=True,
            rarity="legendary",
            caught_offset=3600,
        ),
        _mon(
            "readme-rayquaza",
            "Rayquaza",
            76,
            rarity="legendary",
            caught_offset=0,
        ),
        _mon("readme-dragonite-673", "Dragonite", 68, rarity="rare", caught_offset=7200),
        _mon("readme-gengar", "Gengar", 61, rarity="rare", caught_offset=10_800),
        _mon("readme-pikachu", "Pikachu", 54, rarity="starter", caught_offset=14_400),
        _mon("readme-staryu", "Staryu", 47, shiny=True, caught_offset=18_000),
    ]


def _menu_state() -> dict:
    demo = state.default_state()
    team = _showcase_team()
    demo["mode"] = "battle"
    demo["pokemon"] = team
    demo["active"] = team[0]["id"]
    demo["trainer"].update({
        "name": "HUNT",
        "id_no": 150,
        "streak": 42,
        "balls": 99,
        "total_xp": 8_424_200,
        "total_tokens": 2_451_900_000,
    })
    demo["showcase"] = {"slots": [pokemon["id"] for pokemon in team]}
    return demo


def _encounter_state() -> dict:
    demo = state.default_state()
    buddy = _mon("readme-charizard", "Charizard", 72, rarity="starter")
    demo["mode"] = "battle"
    demo["pokemon"] = [buddy]
    demo["active"] = buddy["id"]
    pending = battle.start({
        "name": "Mewtwo",
        "type": "Psychic",
        "emoji": "DNA",
        "rarity": "legendary",
        "shiny": True,
        "level": 78,
    }, buddy)
    pending["wild_hp"] = round(pending["wild_hp_max"] * 0.38)
    pending["buddy_hp"] = round(pending["buddy_hp_max"] * 0.74)
    pending["last_msg"] = "A shiny Mewtwo is testing your focus."
    demo["pending_battle"] = pending
    return demo


def _trainer_payload(demo: dict) -> dict:
    entries = [
        {"kind": "evolved", "name": "Charizard"},
        {"kind": "caught", "name": "Rayquaza", "source": "battle"},
        {"kind": "caught", "name": "Staryu", "source": "safari"},
    ]
    payload = trainer_card.build(
        demo,
        entries=entries,
        username="HUNT",
        portrait_base64=assets.trainer_portrait_base64(),
    )
    payload["selected_badge_id"] = "shiny_legend"
    return payload


def _tokens_payload() -> dict:
    return {
        "summary": [
            {
                "id": "day",
                "label": "Today",
                "compact": "2.4M",
                "comparison_label": "Yesterday",
                "comparison_compact": "1.8M",
                "change": "+33%",
            },
            {
                "id": "week",
                "label": "This week",
                "compact": "12.8M",
                "comparison_label": "Last week",
                "comparison_compact": "10.1M",
                "change": "+27%",
            },
        ],
        "dashboard": {
            "daily": [
                {"label": "Mon", "date_label": "Aug 11", "tokens": 1_200_000, "compact": "1.2M"},
                {"label": "Tue", "date_label": "Aug 12", "tokens": 1_600_000, "compact": "1.6M"},
                {"label": "Wed", "date_label": "Aug 13", "tokens": 980_000, "compact": "980K"},
                {"label": "Thu", "date_label": "Aug 14", "tokens": 2_100_000, "compact": "2.1M"},
                {"label": "Fri", "date_label": "Aug 15", "tokens": 2_900_000, "compact": "2.9M"},
                {"label": "Sat", "date_label": "Aug 16", "tokens": 1_620_000, "compact": "1.6M"},
                {"label": "Sun", "date_label": "Aug 17", "tokens": 2_400_000, "compact": "2.4M", "is_today": True},
            ],
            "clients": [
                {"label": "Codex", "percent": 62},
                {"label": "Claude", "percent": 31},
                {"label": "Auggie", "percent": 7},
            ],
            "insights": [
                {"id": "average", "value": "1.8M"},
                {"id": "peak", "value": "Aug 15"},
                {"id": "active_streak", "value": "42 days"},
            ],
        },
    }


def _build_snapshot_tool(*, menu_bar_capture=False) -> Path:
    source = ROOT / "macos" / "BuddyMonApp" / "Sources" / "BuddyMonApp"
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    module_cache = BUILD_DIR / "module-cache"
    module_cache.mkdir(parents=True, exist_ok=True)
    sources = [
        "BrandStyle.swift",
        "MenuPanelController.swift",
        "MenuPanelSharedViews.swift",
        "CompactRootView.swift",
        "CompactTrainerCardView.swift",
        "CompactTokenUsageView.swift",
        "CompactSettingsView.swift",
        "CompactEncounterView.swift",
        "CompactSetupView.swift",
    ]
    tool = "ReadmeScreenshotSnapshot.swift"
    executable = SNAPSHOT
    if menu_bar_capture:
        sources.append("MenuBarBuddy.swift")
        tool = "ReadmeMenuBarCapture.swift"
        executable = BUILD_DIR / "readme-menu-bar"
    subprocess.run([
        "xcrun",
        "swiftc",
        "-module-cache-path",
        str(module_cache),
        "-framework",
        "AppKit",
        "-framework",
        "QuartzCore",
        *(str(source / name) for name in sources),
        str(ROOT / "tools" / tool),
        "-o",
        str(executable),
    ], check=True)
    return executable


def _capture(kind: str, payload: dict, filename: str) -> None:
    destination = OUT / filename
    subprocess.run(
        [str(SNAPSHOT), kind, str(destination)],
        input=json.dumps(payload, sort_keys=True).encode(),
        stdout=subprocess.PIPE,
        check=True,
    )


def _write_demo_state(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(_menu_state(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _install_local_art_fixture(destination.parent.parent)


def _battle_frames() -> list[tuple[str, dict, int]]:
    """Advance the shipping battle engine, with no player state or notifications."""
    demo = _encounter_state()
    demo["preferences"]["notifications"] = "off"
    pending = demo["pending_battle"]
    pending["wild_hp"] = pending["wild_hp_max"]
    pending["buddy_hp"] = pending["buddy_hp_max"]
    pending["last_msg"] = f"A wild {pending['name']} appeared!"
    frames = [("encounter", _build_encounter_view(demo), 2000)]
    rng = random.Random(7)
    while battle.wild_hp_frac(pending) > 0.4:
        frames.append(("encounter", {**_build_encounter_view(demo), "capture_action": "fight"}, 500))
        outcome, _ = battle.take_turn(demo, "attack", rng)
        if outcome["done"]:
            raise RuntimeError("README demo battle ended before its catch")
        frames.append(("encounter", _build_encounter_view(demo), 1800))
    frames.append(("encounter", {**_build_encounter_view(demo), "capture_action": "ball"}, 700))
    buddy = dict(state.active_pokemon(demo))
    wild = dict(pending)
    outcome, message = battle.take_turn(demo, "ball", random.Random(1))
    if not outcome["caught"]:
        raise RuntimeError("README demo catch failed")
    frames.append(("result", _build_encounter_result_payload(
        buddy, wild, "battle", outcome, message,
    ), 3000))
    return frames


def _capture_battle_frames() -> None:
    directory = BUILD_DIR / "battle-frames"
    directory.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, (kind, payload, duration) in enumerate(_battle_frames()):
        destination = directory / f"{index:02d}.png"
        _capture(kind, payload, destination)
        manifest.append({"file": destination.name, "duration_ms": duration, "kind": kind})
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def _encode_battle_gif() -> Path:
    directory = BUILD_DIR / "battle-frames"
    manifest = json.loads((directory / "manifest.json").read_text())
    first_png = (directory / manifest[0]["file"]).read_bytes()
    width, height = struct.unpack(">II", first_png[16:24])
    destination = OUT / "battle-sequence.gif"
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    filters = []
    for index, frame in enumerate(manifest):
        command.extend([
            "-loop", "1", "-t", str(frame["duration_ms"] / 1000),
            "-i", str(directory / frame["file"]),
        ])
        filters.append(
            f"[{index}:v]pad={width}:{height}:0:0:color=0xF4F1E7,"
            f"setsar=1,fps=10[v{index}]"
        )
    inputs = "".join(f"[v{index}]" for index in range(len(manifest)))
    filters.extend([
        f"{inputs}concat=n={len(manifest)}:v=1:a=0,split[frames][palette_source]",
        "[palette_source]palettegen=stats_mode=diff[palette]",
        "[frames][palette]paletteuse=dither=none[out]",
    ])
    command.extend([
        "-filter_complex", ";".join(filters), "-map", "[out]",
        "-loop", "0", str(destination),
    ])
    subprocess.run(command, check=True)
    return destination


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate README images or an isolated terminal demo state."
    )
    parser.add_argument(
        "--terminal-state-only",
        action="store_true",
        help="write the deterministic Ghostty demo state without rendering images",
    )
    parser.add_argument(
        "--menu-bar", action="store_true",
        help="also capture a temporary real macOS status item and open panel",
    )
    parser.add_argument(
        "--battle-gif", action="store_true",
        help="also encode the battle sequence as a looping GIF (requires ffmpeg)",
    )
    args = parser.parse_args(argv)
    if args.terminal_state_only:
        _write_demo_state(TERMINAL_STATE)
        print(TERMINAL_STATE)
        return 0
    if args.battle_gif and shutil.which("ffmpeg") is None:
        parser.error("--battle-gif requires ffmpeg on PATH")

    OUT.mkdir(parents=True, exist_ok=True)
    _install_local_art_fixture()
    _build_snapshot_tool()

    menu = _menu_state()
    encounter = _encounter_state()
    _capture("menu", _build_menu_panel_fixture_status(menu), "buddymon-main.png")
    _capture("encounter", _build_encounter_view(encounter), "encounter.png")
    _capture("trainer", _trainer_payload(menu), "trainer-card.png")
    _capture("tokens", _tokens_payload(), "token-usage.png")
    _capture_battle_frames()
    if args.battle_gif:
        print(_encode_battle_gif())
    if args.menu_bar:
        executable = _build_snapshot_tool(menu_bar_capture=True)
        status = _build_menu_panel_fixture_status(menu)
        status["menu_bar"] = menu_bar.runtime_payload(menu, now=FIXED_TIME)
        subprocess.run(
            [str(executable), str(OUT)],
            input=json.dumps(status, sort_keys=True).encode(), check=True,
        )
    (OUT / "showcase-export.png").write_bytes(showcase_export.render_showcase_png(
        menu,
        generated_at=datetime(2026, 8, 17, 13, 42),
    ))

    for name in (
        "buddymon-main.png",
        "encounter.png",
        "trainer-card.png",
        "token-usage.png",
        "showcase-export.png",
    ):
        print(OUT / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
