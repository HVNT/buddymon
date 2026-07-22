"""Developer playback and user stories for the real macOS menu-bar buddy."""

import argparse
import copy
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid

from . import menu_bar


TEMP_FILE_PREFIX = "buddymon-menu-bar-preview"


def _step(state_id, description, *, hold_ms=1_800, **fixtures):
    return {
        "state_id": state_id,
        "description": description,
        "hold_ms": hold_ms,
        **fixtures,
    }


STORY_CATALOG = (
    {
        "id": "starter-day",
        "label": "Charmander's first day",
        "steps": (
            _step("booting", "BuddyMon launches quietly", hold_ms=1_400),
            _step("needs_buddy", "The egg waits for a starter choice"),
            _step("idle", "Charmander joins the menu bar", hold_ms=2_400),
        ),
    },
    {
        "id": "focus-and-level",
        "label": "A productive focus session",
        "steps": (
            _step("idle", "Charmander is hanging out"),
            _step("working", "Local coding activity begins", hold_ms=2_400),
            _step("xp_gain", "The work earns XP"),
            _step("level_up", "Charmander levels up"),
            _step("idle", "Charmander settles back down"),
        ),
    },
    {
        "id": "evolution",
        "label": "Charmander evolves",
        "steps": (
            _step("working", "One more focused turn"),
            _step("xp_gain", "Charmander earns the needed XP"),
            _step("level_up", "Charmander reaches level 16"),
            _step("evolving", "Charmander evolves into Charmeleon"),
            _step(
                "idle",
                "Charmeleon takes over the menu bar",
                buddy_name="Charmeleon",
                evolved_name="Charizard",
                hold_ms=2_400,
            ),
        ),
    },
    {
        "id": "auto-catch",
        "label": "Automatic battle and catch",
        "steps": (
            _step("encounter_alert", "Charmander spots a wild Eevee"),
            _step("auto_battle", "Charmander handles the battle"),
            _step("catching", "A ball is thrown"),
            _step("result.caught", "Eevee is caught"),
            _step("idle", "Charmander returns to work"),
        ),
    },
    {
        "id": "interactive-retry",
        "label": "Interactive encounter with a retry",
        "steps": (
            _step("encounter_alert", "Charmander spots a wild Eevee"),
            _step("waiting_for_player", "The encounter waits for you", hold_ms=2_400),
            _step("catching", "The first ball is thrown"),
            _step("result.broke_free", "Eevee breaks free"),
            _step("waiting_for_player", "The encounter waits again"),
            _step("catching", "The second ball is thrown"),
            _step("result.new_species", "Eevee is a new species"),
            _step("idle", "Charmander returns to the baseline"),
        ),
    },
    {
        "id": "shiny-catch",
        "label": "A shiny encounter",
        "steps": (
            _step("encounter_alert", "A shiny Eevee appears", wild_shiny=True),
            _step(
                "waiting_for_player",
                "The shiny encounter waits for you",
                wild_shiny=True,
                hold_ms=2_400,
            ),
            _step("catching", "A ball is thrown", wild_shiny=True),
            _step("result.shiny_caught", "The shiny Eevee is caught", wild_shiny=True),
            _step("shiny_idle", "A shiny buddy sparkles in the menu bar", hold_ms=2_400),
        ),
    },
    {
        "id": "empty-bag",
        "label": "Encounter with no balls",
        "steps": (
            _step("encounter_alert", "A wild Eevee appears"),
            _step("waiting_for_player", "The encounter waits for you"),
            _step("result.no_balls", "There are no balls left"),
            _step("idle", "Charmander returns safely"),
        ),
    },
    {
        "id": "battle-loss",
        "label": "A difficult battle",
        "steps": (
            _step("encounter_alert", "A wild Eevee appears"),
            _step("auto_battle", "Charmander enters battle"),
            _step("result.buddy_fainted", "Charmander faints"),
            _step("resting", "Charmander rests", hold_ms=2_400),
        ),
    },
    {
        "id": "battle-win",
        "label": "A battle without a catch",
        "steps": (
            _step("encounter_alert", "A wild Eevee appears"),
            _step("auto_battle", "Charmander enters battle"),
            _step("result.wild_ko", "The wild Eevee faints"),
            _step("idle", "Charmander returns to the baseline"),
        ),
    },
    {
        "id": "encounter-exits",
        "label": "Ways an encounter can end",
        "steps": (
            _step("encounter_alert", "A wild Eevee appears"),
            _step("result.fled", "The wild Eevee flees"),
            _step("encounter_alert", "Another wild Eevee appears"),
            _step("waiting_for_player", "The encounter waits for you"),
            _step("result.ran", "You run safely"),
            _step("idle", "Charmander returns to the baseline"),
        ),
    },
    {
        "id": "service-recovery",
        "label": "Local service recovery",
        "steps": (
            _step("idle", "Charmander is available"),
            _step("unavailable", "Local status becomes unavailable"),
            _step("booting", "BuddyMon reconnects"),
            _step("idle", "Charmander returns to the baseline"),
        ),
    },
)


def story_ids():
    return tuple(story["id"] for story in STORY_CATALOG) + (
        "all-stories",
        "all-states",
    )


def story_steps(story_id):
    if story_id == "all-stories":
        return tuple(
            {
                **step,
                "story_id": story["id"],
                "story_label": story["label"],
            }
            for story in STORY_CATALOG
            for step in story["steps"]
        )
    if story_id == "all-states":
        return tuple(
            _step(state_id, f"Catalog preview: {state_id}")
            for state_id in menu_bar.catalog_ids()
        )
    story = next((item for item in STORY_CATALOG if item["id"] == story_id), None)
    if story is None:
        raise ValueError(
            f"Unknown story {story_id!r}. Expected: {', '.join(story_ids())}"
        )
    return story["steps"]


def sequence_for_step(step):
    return menu_bar.preview_sequence(
        step["state_id"],
        buddy_name=step.get("buddy_name", "Charmander"),
        evolved_name=step.get("evolved_name"),
        wild_name=step.get("wild_name", "Eevee"),
        buddy_shiny=bool(step.get("buddy_shiny")),
        wild_shiny=bool(step.get("wild_shiny")),
    )


def scaled_sequence(sequence, speed):
    if speed <= 0:
        raise ValueError("Speed must be greater than zero")
    scaled = copy.deepcopy(sequence)
    for frame in scaled["frames"]:
        frame["duration_ms"] = max(80, round(frame["duration_ms"] / speed))
    scaled["duration_ms"] = sum(frame["duration_ms"] for frame in scaled["frames"])
    return scaled


def preview_envelope(sequence=None, *, hold_ms=0, cancel=False):
    payload = {
        "schema_version": menu_bar.SCHEMA_VERSION,
        "cancel": bool(cancel),
        "hold_ms": max(0, int(hold_ms)),
    }
    if sequence is not None:
        payload["sequence"] = sequence
    return payload


def post_preview(envelope):
    """Post a bounded preview payload to the running native BuddyMon app."""
    pids = app_pids()
    if not pids:
        raise RuntimeError("BuddyMon.app is not running")
    path = os.path.join(tempfile.gettempdir(), f"{TEMP_FILE_PREFIX}-{os.getuid()}.json")
    staging = f"{path}.{os.getpid()}-{uuid.uuid4().hex}.tmp"
    try:
        with open(staging, "w", encoding="utf-8") as handle:
            json.dump(envelope, handle, separators=(",", ":"), sort_keys=True)
        os.replace(staging, path)
        for pid in pids:
            os.kill(pid, signal.SIGWINCH)
    except Exception:
        for candidate in (staging, path):
            try:
                os.unlink(candidate)
            except OSError:
                pass
        raise


def app_pids():
    result = subprocess.run(
        ["/usr/bin/pgrep", "-x", "BuddyMon"],
        check=False,
        stdout=subprocess.PIPE,
        text=True,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return ()
    return tuple(
        int(line)
        for line in result.stdout.splitlines()
        if line.strip().isdigit()
    )


def app_is_running():
    return bool(app_pids())


def _require_running():
    if app_is_running():
        return True
    print(
        "BuddyMon.app is not running. Build and launch it first:\n"
        "  scripts/build-macos-app.sh\n"
        "  open .build/macos/BuddyMon.app",
        file=sys.stderr,
    )
    return False


def _default_hold_ms(sequence, speed=1.0):
    minimum = 2_400 if sequence["loop"] else 1_800
    scaled_minimum = max(600, round(minimum / speed))
    if sequence["loop"]:
        return max(scaled_minimum, sequence["duration_ms"] + 400)
    return max(scaled_minimum, sequence["duration_ms"] + 500)


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Play canonical Charmander states on the real BuddyMon menu-bar icon."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser("list", help="List states and user stories")
    listing.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    play = subparsers.add_parser("play", help="Play one canonical state")
    play.add_argument("state_id", choices=menu_bar.catalog_ids())
    play.add_argument("--seconds", type=float, help="How long to reserve the menu-bar preview")
    play.add_argument("--buddy", default="Charmander")
    play.add_argument("--evolved")
    play.add_argument("--wild", default="Eevee")
    play.add_argument("--buddy-shiny", action="store_true")
    play.add_argument("--wild-shiny", action="store_true")

    story = subparsers.add_parser("story", help="Play a complete user story")
    story.add_argument("story_id", choices=story_ids())
    story.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier (default: 1.0)",
    )

    subparsers.add_parser("reset", help="Stop a preview and restore live state")
    return parser


def _list_catalog(as_json):
    stories = [
        {
            "id": story["id"],
            "label": story["label"],
            "states": [step["state_id"] for step in story["steps"]],
        }
        for story in STORY_CATALOG
    ]
    stories.append({
        "id": "all-stories",
        "label": "Every complete user story",
        "states": [
            step["state_id"]
            for story in STORY_CATALOG
            for step in story["steps"]
        ],
    })
    stories.append({
        "id": "all-states",
        "label": "Every canonical state",
        "states": list(menu_bar.catalog_ids()),
    })
    payload = {
        "states": [dict(entry) for entry in menu_bar.STATE_CATALOG],
        "stories": stories,
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print("STATES")
    for entry in payload["states"]:
        print(f"  {entry['id']:<24} {entry['label']}")
    print("\nUSER STORIES")
    for story in stories:
        print(f"  {story['id']:<24} {story['label']}")


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.command == "list":
        _list_catalog(args.json)
        return 0

    if not _require_running():
        return 2

    if args.command == "reset":
        try:
            post_preview(preview_envelope(cancel=True))
        except (OSError, RuntimeError) as exc:
            print(f"Could not signal BuddyMon.app: {exc}", file=sys.stderr)
            return 1
        print("Restored the live BuddyMon menu-bar state.")
        return 0

    if args.command == "play":
        sequence = menu_bar.preview_sequence(
            args.state_id,
            buddy_name=args.buddy,
            evolved_name=args.evolved,
            wild_name=args.wild,
            buddy_shiny=args.buddy_shiny,
            wild_shiny=args.wild_shiny,
        )
        hold_ms = (
            max(100, round(args.seconds * 1_000))
            if args.seconds is not None
            else _default_hold_ms(sequence)
        )
        try:
            post_preview(preview_envelope(sequence, hold_ms=hold_ms))
        except (OSError, RuntimeError) as exc:
            print(f"Could not signal BuddyMon.app: {exc}", file=sys.stderr)
            return 1
        print(
            f"Playing {args.state_id} for {hold_ms / 1_000:.1f}s. "
            "Watch Charmander in the macOS menu bar."
        )
        return 0

    try:
        steps = story_steps(args.story_id)
        if args.speed <= 0:
            raise ValueError("Speed must be greater than zero")
        total = len(steps)
        print(
            f"Playing {args.story_id}: {total} steps. Press Control-C to stop.",
            flush=True,
        )
        active_story_id = None
        for index, step in enumerate(steps, start=1):
            if step.get("story_id") != active_story_id:
                active_story_id = step.get("story_id")
                if active_story_id:
                    print(f"\n  -- {step['story_label']} --", flush=True)
            sequence = scaled_sequence(sequence_for_step(step), args.speed)
            requested_hold = round(step["hold_ms"] / args.speed)
            hold_ms = max(
                requested_hold,
                _default_hold_ms(sequence, speed=args.speed),
            )
            post_preview(preview_envelope(sequence, hold_ms=hold_ms + 400))
            print(
                f"  [{index:02d}/{total:02d}] {step['state_id']:<24} "
                f"{step['description']}",
                flush=True,
            )
            time.sleep(hold_ms / 1_000)
        post_preview(preview_envelope(cancel=True))
    except KeyboardInterrupt:
        post_preview(preview_envelope(cancel=True))
        print("\nPreview stopped; restored the live state.", flush=True)
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("Story complete; the live menu-bar state has been restored.", flush=True)
    return 0
