#!/usr/bin/env python3
"""buddymon CLI — used by the /buddymon:* commands and direct play.

Usage:
  buddymon.py choose <starter>    pick your starter (one-time)
  buddymon.py status              compact status summary
  buddymon.py dex [--grid]        collection by rarity
  buddymon.py switch <name>       make a caught pokemon your active buddy
  buddymon.py preview             render every sprite (art QA; both frames for packs)
  buddymon.py export-chibi        archive the chibi pack to ~/Pictures/buddymon/
  buddymon.py share-showcase      save a labeled Showcase PNG to ~/Desktop/
  buddymon.py collect             count tokens from other agent CLIs
  buddymon.py collector <action>  manage optional background collection
  buddymon.py app-status          JSON status for BuddyMon.app
  buddymon.py app-menu-bar-harness JSON state inventory for native menu-bar QA
  buddymon.py app-menu-panel-harness JSON state inventory for compact-panel QA
  buddymon.py app-view <screen>   JSON view payload for BuddyMon.app
  buddymon.py app-action <action> JSON mutation for BuddyMon.app
  buddymon.py install-assets      fetch nicer local sprite packs
  buddymon.py tiny [--collect]    one-line plain-text status (tmux status bar)
  buddymon.py menubar             SwiftBar plugin output (sprite icon + dropdown)
  buddymon.py menu                interactive terminal UI (party/dex/status/tokens)
  buddymon.py tokens              token usage report
  buddymon.py backup              make a local snapshot of BuddyMon data
  buddymon.py history [N]         the buddy's journey journal (default last 20)
  buddymon.py safari <action>     play a turn vs a pending wild (rock|bait|ball|run)
  buddymon.py battle <action>     battle-mode turn (attack|ball|run)
  buddymon.py mode [quick|auto|safari|battle]  cycle or set encounter mode
"""
import json
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import (  # noqa: E402
    app_bridge, backups, battle as bt, collector_service, collectors, data, engine,
    journal, menu_bar, menu_launcher, notify, packs, paths, pixels, render,
    safari as sf, showcase_share, sprites, state, swiftbar, token_usage, tui,
)

_OPEN_MENU_USAGE = (
    "Usage: open-menu [screen] "
    "[--launcher auto|ghostty|iterm|terminal] "
    "[--window-frame x,y,width,height]"
)


@dataclass(frozen=True)
class CommandResult:
    text: str
    exit_code: int = 0


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
    return (
        f"{art}\n\n{buddy['emoji']} {buddy['name']} chose YOU! Claude Code is "
        "automatic; collect adds Codex CLI and Auggie activity."
    )


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


def share_showcase(_args):
    return showcase_share.save_with_feedback().message


def collect(args, quiet=False):
    scheduled = "--scheduled" in args
    with state.lock():
        s = state.load()
        if not s["pokemon"]:
            return "" if quiet else "No buddy yet — nothing to collect for."
        started_at = time.time()
        if scheduled and not collector_service.collection_due(s, started_at):
            return "" if quiet else "scheduled collection not due"
        summary = collectors.collect(s, random.Random())
        for entry in journal.log_outcomes(summary["result"], summary["encounter"], "cross"):
            if journal.is_rare(entry):
                notify.notify("buddymon", entry["text"], state=s)
        if scheduled:
            collector_service.mark_collection(s, time.time())
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


def collector_service_command(args):
    if len(args) > 1:
        return CommandResult("Usage: collector install|uninstall|status", 2)
    action = args[0].lower() if args else "status"
    try:
        if action == "install":
            status = collector_service.install_service()
            return CommandResult(collector_service.format_status(status))
        if action == "uninstall":
            result = collector_service.uninstall_service()
            count = len(result["removed"])
            suffix = "s" if count != 1 else ""
            return CommandResult(
                f"collector service: uninstalled ({count} file{suffix} removed)"
            )
        if action == "status":
            status = collector_service.service_status()
            return CommandResult(collector_service.format_status(status))
    except (collector_service.CollectorServiceError, OSError) as exc:
        return CommandResult(f"collector service failed: {exc}", 1)
    return CommandResult("Usage: collector install|uninstall|status", 2)


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


def menubar(args):
    return swiftbar.run(args, collect_usage=collect)


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
    """Cycle or set Quick, Safari, or Battle encounter behavior."""
    aliases = {"quick": "auto"}
    labels = {"auto": "Quick", "safari": "Safari", "battle": "Battle"}
    descriptions = {
        "auto": (
            "common and uncommon catches resolve automatically; "
            "rare and legendary encounters use Safari"
        ),
        "safari": "every wild waits for Rock, Bait, Ball, or Run",
        "battle": "every wild waits for Fight, Ball, or Run",
    }
    with state.lock():
        s = state.load()
        cur = s.get("mode", state.DEFAULT_MODE)
        if cur not in state.VALID_MODES:
            cur = state.DEFAULT_MODE
        if args:
            requested = args[0].lower()
            target = aliases.get(requested, requested)
        else:
            index = state.VALID_MODES.index(cur)
            target = state.VALID_MODES[(index + 1) % len(state.VALID_MODES)]
        if target not in state.VALID_MODES:
            return "Usage: mode quick|auto|safari|battle"
        s["mode"] = target
        state.save(s)
    return f"encounter mode: {labels[target]} — {descriptions[target]}"


def menu(args):
    """Launch the interactive terminal UI."""
    tui.run(args[0] if args else None)
    return ""


def _open_menu_args(args):
    screen = None
    launcher = None
    window_frame = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--launcher":
            if i + 1 >= len(args):
                raise ValueError("--launcher requires a value")
            launcher = args[i + 1]
            i += 2
            continue
        if arg.startswith("--launcher="):
            launcher = arg.split("=", 1)[1]
            i += 1
            continue
        if arg == "--window-frame":
            if i + 1 >= len(args):
                raise ValueError("--window-frame requires x,y,width,height")
            window_frame = menu_launcher.normalize_window_frame(args[i + 1])
            i += 2
            continue
        if arg.startswith("--window-frame="):
            window_frame = menu_launcher.normalize_window_frame(
                arg.split("=", 1)[1]
            )
            i += 1
            continue
        if screen is None:
            screen = arg
        i += 1
    return screen, launcher, window_frame


def open_menu(args):
    """Open the interactive menu in Ghostty, iTerm2, or Terminal.app."""
    try:
        screen, launcher, window_frame = _open_menu_args(args)
    except ValueError:
        return _OPEN_MENU_USAGE
    if launcher and launcher not in state.PREFERENCE_VALUES["menu_launcher"]:
        return _OPEN_MENU_USAGE
    s = state.load()
    launcher = launcher or state.preference(s, "menu_launcher")
    replace_owned = state.preference(s, "menu_replace") == "on"
    opened = notify.open_menu(
        screen,
        launcher=launcher,
        replace_owned=replace_owned,
        window_frame=window_frame,
    )
    if opened:
        return ""
    return "Could not open BuddyMon menu. Try: python3 buddymon.py menu"


def tokens(_args):
    return "\n".join(token_usage.report_lines())


def backup(_args):
    """Create a manual local snapshot for App and Terminal Settings."""
    return str(backups.create_backup())


def app_status(args):
    return app_bridge.status_json(indent=2 if "--pretty" in args else None)


def app_menu_bar_harness(args):
    return menu_bar.harness_json(indent=2 if "--pretty" in args else None)


def app_menu_panel_harness(args):
    return app_bridge.menu_panel_harness_json(
        indent=2 if "--pretty" in args else None
    )


def app_view(args):
    pretty = "--pretty" in args
    screens = [arg for arg in args if not arg.startswith("--")]
    if not screens:
        return "Usage: app-view <screen>"
    screen = screens[0]
    try:
        return app_bridge.app_view_json(screen, indent=2 if pretty else None)
    except ValueError as exc:
        return str(exc)


def app_action(args):
    pretty = "--pretty" in args
    clean = [arg for arg in args if arg != "--pretty"]
    action = clean[0] if clean else ""
    action_args = clean[1:] if len(clean) > 1 else []
    return app_bridge.app_action_json(action, action_args, indent=2 if pretty else None)


def install_assets(args):
    json_out = "--json" in args
    refresh = "--refresh" in args or "--force" in args
    operation = "refresh" if refresh else "install_missing"
    kinds = None
    only_args = [arg for arg in args if arg.startswith("--only=")]
    unsupported = [
        arg for arg in args
        if arg not in {"--json", "--refresh", "--force"}
        and not arg.startswith("--only=")
    ]
    usage_error = None
    if unsupported:
        usage_error = "unsupported asset option: " + ", ".join(unsupported)
    elif len(only_args) > 1:
        usage_error = "--only may be specified once"
    elif only_args:
        parts = [part.strip() for part in only_args[0].split("=", 1)[1].split(",")]
        if not parts or any(not part for part in parts):
            usage_error = "--only requires one or more pack names"
        else:
            kinds = parts

    exit_code = 2 if usage_error else None
    if usage_error:
        result = {
            "operation": operation,
            "ok": False,
            "error": usage_error,
            "results": [],
            "packs": {},
        }
    else:
        try:
            result = app_bridge.install_assets(kinds=kinds, operation=operation)
        except Exception as exc:
            result = {
                "operation": operation,
                "ok": False,
                "error": str(exc),
                "results": [],
                "packs": {},
            }
    if exit_code is None:
        exit_code = 0 if result["ok"] else 1
    if json_out:
        return CommandResult(json.dumps(result, sort_keys=True), exit_code)
    lines = []
    if result.get("error"):
        lines.append(f"asset install failed: {result['error']}")
    for entry in result["results"]:
        lines.append(f"{entry['kind']}: {entry['status']} - {entry['message']}")
    if not result["ok"]:
        lines.append(
            "Some asset downloads failed; prior working packs were kept, "
            "and fallback art is used where needed."
        )
    return CommandResult("\n".join(lines), exit_code)


def history(args):
    n = int(args[0]) if args and args[0].isdigit() else 20
    entries = journal.tail(n, newest_first=True)
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
        "share-showcase": share_showcase,
        "collect": collect,
        "collector": collector_service_command,
        "tiny": tiny,
        "menubar": menubar,
        "menu": menu,
        "open-menu": open_menu,
        "tokens": tokens,
        "backup": backup,
        "app-status": app_status,
        "app-menu-bar-harness": app_menu_bar_harness,
        "app-menu-panel-harness": app_menu_panel_harness,
        "app-view": app_view,
        "app-action": app_action,
        "install-assets": install_assets,
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
        return 2
    try:
        result = handler(args)
        if isinstance(result, CommandResult):
            print(result.text)
            return result.exit_code
        print(result)
        return 0
    except state.StateLoadError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except BrokenPipeError:  # piped into head etc.
        return 0


if __name__ == "__main__":
    sys.exit(main())
