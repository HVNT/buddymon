"""Interactive terminal UI: arrow-key navigation of party, dex, journal, status.

Launched via `buddymon.py menu` (from the SwiftBar dropdown's "Open buddymon"
item, a shell alias, or a tmux popup). Raw-mode ANSI using only the stdlib, so
it stays responsive and readable in plain terminals. Sprite previews use compact
frames so the screens keep enough room for controls and scrolling.

The frame builders (`_menu_frame`, `_party_frame`, `_scroll_frame`) are pure
str-returning functions so they can be unit-tested without a terminal; the loop
and key reading are the only parts that touch the tty.
"""
import os
import random
import re
import select
import shutil
import sys

from . import battle as bt, journal, packs, pixels, render, safari as sf
from . import state as st

HIDE_CURSOR, SHOW_CURSOR = "\x1b[?25l", "\x1b[?25h"
ALT_SCREEN, MAIN_SCREEN = "\x1b[?1049h", "\x1b[?1049l"
HOME_CLEAR = "\x1b[H\x1b[2J"
MOUSE_ON, MOUSE_OFF = "\x1b[?1000h\x1b[?1006h", "\x1b[?1000l\x1b[?1006l"
DIM, BOLD, RESET = "\x1b[2m", "\x1b[1m", "\x1b[0m"
CYAN, GREEN = "\x1b[36m", "\x1b[32m"
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

MENU = [
    ("👫  Party", "party"),
    ("📖  Pokédex", "dex"),
    ("📜  Journal", "journal"),
    ("📊  Status", "status"),
    ("⚙️   Settings", "settings"),
    ("🚪  Quit", "quit"),
]

# Action options per encounter kind: (label shown, action verb passed to take_turn)
ENCOUNTER_OPTIONS = {
    "safari": [("Rock", "rock"), ("Bait", "bait"), ("Ball", "ball"), ("Run", "run")],
    "battle": [("Fight", "attack"), ("Ball", "ball"), ("Run", "run")],
}


def _encounter_kind(s):
    if s.get("pending_encounter"):
        return "safari"
    if s.get("pending_battle"):
        return "battle"
    return None


def _menu_items(s):
    """Static menu, with a 'fight' entry prepended when a wild is waiting."""
    items = list(MENU)
    kind = _encounter_kind(s)
    if kind:
        name = (s.get("pending_encounter") or s.get("pending_battle"))["name"]
        items.insert(0, (f"⚔️  Fight wild {name}!", "encounter"))
    return items


# ── pure frame builders (testable) ───────────────────────────────────────────

def _header(title):
    return f"{BOLD}{CYAN}buddymon{RESET} {DIM}·{RESET} {title}"


def _footer(hint):
    return f"{DIM}{hint}{RESET}"


def _visible_width(line):
    return len(ANSI_RE.sub("", line))


def _pad_ansi(line, width):
    return line + " " * max(0, width - _visible_width(line))


def _fit_ansi(line, width):
    if _visible_width(line) <= width:
        return line
    out = []
    visible = 0
    i = 0
    while i < len(line) and visible < width:
        if line[i] == "\x1b":
            match = ANSI_RE.match(line, i)
            if match:
                out.append(match.group(0))
                i = match.end()
                continue
        out.append(line[i])
        visible += 1
        i += 1
    fitted = "".join(out)
    return fitted + (RESET if "\x1b[" in fitted else "")


def _pair_line(left, right, width=31):
    return "  " + _pad_ansi(_fit_ansi(left, width), width) + "   " + right


def _pokemon_title(pokemon, with_level=False):
    shiny = "✨" if pokemon.get("shiny") else ""
    level = f" Lv.{pokemon.get('level')}" if with_level and pokemon.get("level") else ""
    return f"{shiny}{pokemon.get('emoji', '•')} {pokemon['name']}{level}"


def _pokemon_meta(pokemon):
    return " · ".join(x for x in (
        pokemon.get("type"),
        pokemon.get("rarity"),
    ) if x)


def _bar(frac, width=16):
    frac = max(0.0, min(1.0, frac))
    filled = round(frac * width)
    return f"{GREEN}{'▰' * filled}{RESET}{DIM}{'▱' * (width - filled)}{RESET} {int(frac * 100)}%"


def _sprite_lines(pokemon):
    grid, palette = packs.sprite_frames(
        pokemon["name"], pokemon.get("type", "Normal"), pokemon.get("shiny"))[0]
    return pixels.render(grid, palette)


def _paired_sprite_lines(left_pokemon, right_pokemon, width=24):
    left = _sprite_lines(left_pokemon)
    right = _sprite_lines(right_pokemon)
    h = max(len(left), len(right))
    left += [""] * (h - len(left))
    right += [""] * (h - len(right))
    return [_pair_line(l, r, width=width) for l, r in zip(left, right)]


def _menu_frame(items, selected):
    lines = ["", _header("main menu"), ""]
    for i, (label, _) in enumerate(items):
        cursor = f"{GREEN}▶{RESET}" if i == selected else " "
        row = f"  {cursor} {label}"
        lines.append(f"{BOLD}{row}{RESET}" if i == selected else row)
    lines += ["", _footer("↑/↓ move · ⏎ select · q quit")]
    return "\n".join(lines)


def _encounter_frame(s, kind, sel):
    """Terminal battle view: compact sprites, status, and the action row."""
    pending = s.get("pending_encounter") if kind == "safari" else s.get("pending_battle")
    buddy = st.active_pokemon(s)
    lines = ["", _header(f"wild {pending['name']}"), ""]
    lines.append(_pair_line(f"{BOLD}your buddy{RESET}", f"{BOLD}wild encounter{RESET}"))
    lines.append(_pair_line(_pokemon_title(buddy, with_level=True), _pokemon_title(pending)))
    lines.append(_pair_line(_pokemon_meta(buddy), _pokemon_meta(pending)))
    lines.extend(_paired_sprite_lines(buddy, pending))
    if kind == "battle":
        lines.append(_pair_line(f"HP {_bar(bt.buddy_hp_frac(pending))}",
                                f"HP {_bar(bt.wild_hp_frac(pending))}"))
    lines.append("")
    if kind == "safari":
        lines.append(f"  {sf.status_text(pending)}")
        lines.append(f"  {DIM}{sf.odds_hint(pending)}{RESET}")
    else:
        lines.append(f"  {bt.status_text(pending)}")
        lines.append(f"  {DIM}catch ~{round(bt.catch_probability(pending) * 100)}%  ·  ⚾ ∞{RESET}")
    lines.append(f"  {pending['last_msg']}")
    lines.append("")
    opts = ENCOUNTER_OPTIONS[kind]
    cells = [f"{GREEN}▶{label}{RESET}" if i == sel else f"  {label} "
             for i, (label, _) in enumerate(opts)]
    lines.append("  " + "    ".join(cells))
    lines += ["", _footer("←/→ choose · ⏎/e act · esc leave")]
    return "\n".join(lines)


def _party_frame(s, selected):
    mons = _party(s)
    active = s.get("active")
    lines = ["", _header("party"), ""]
    for i, p in enumerate(mons):
        cursor = f"{GREEN}▶{RESET}" if i == selected else " "
        star = "✨" if p.get("shiny") else "  "
        tag = f" {GREEN}●{RESET}" if p["id"] == active else ""
        row = f"  {cursor} {star}{p['emoji']} {p['name']:<12} Lv.{p['level']:<3} {DIM}{p['rarity']}{RESET}{tag}"
        lines.append(row)
    lines.append("")
    if mons:
        p = mons[selected]
        lines += [
            f"  {BOLD}selected{RESET}",
            *["   " + r for r in _sprite_lines(p)],
            f"  {_pokemon_title(p, with_level=True)}",
            f"  {_pokemon_meta(p)} · {render.gender_symbol(p)}",
            f"  XP {CYAN}{render.xp_bar(p, 16)}{RESET}",
            f"  {GREEN}active buddy{RESET}" if p["id"] == active else "  press enter to make active",
        ]
    lines += ["", _footer("↑/↓ move · ⏎ make active · esc back")]
    return "\n".join(lines)


def _status_lines(s):
    buddy = st.active_pokemon(s)
    if buddy is None:
        return [f"{DIM}No buddy yet.{RESET}"]
    trainer = s["trainer"]
    species = {p["name"] for p in s["pokemon"]}
    lines = [
        *["   " + r for r in _sprite_lines(buddy)],
        f"  {BOLD}{_pokemon_title(buddy, with_level=True)}{RESET}",
        f"  {_pokemon_meta(buddy)} · {render.gender_symbol(buddy)}",
        f"  XP {CYAN}{render.xp_bar(buddy, 16)}{RESET}",
        "",
        f"  Tokens used {trainer.get('total_tokens', 0):,}",
        f"  Progress {trainer.get('total_xp', 0):,}",
        f"  Streak {trainer.get('streak', 0)}d",
        f"  Balls {trainer.get('balls', 0)}",
        f"  Pokédex {len(species)}/{len(render._dex_universe())} species",
    ]
    recent = sorted(s["pokemon"], key=lambda p: p.get("caught_at", 0), reverse=True)[:5]
    if recent:
        lines += [
            "",
            f"  {BOLD}recent{RESET}",
            *[f"  {_pokemon_title(p, with_level=True)} · {_pokemon_meta(p)}" for p in recent],
        ]
    return lines


def _scroll_frame(title, body_lines, top, height, hint="↑/↓ scroll · esc back"):
    view = body_lines[top:top + height]
    return "\n".join(["", _header(title), ""] + view + ["", _footer(hint)])


def _dex_entries(s):
    best = {}
    for p in s["pokemon"]:
        if p["name"] not in best or p["level"] > best[p["name"]]["level"]:
            best[p["name"]] = p

    entries = []
    seen = set()
    for idx, (name, ptype, rarity) in enumerate(render._dex_universe(), 1):
        if name in seen:
            continue
        seen.add(name)
        p = best.get(name)
        entries.append({
            "idx": idx,
            "name": name,
            "type": ptype,
            "rarity": rarity,
            "pokemon": p,
            "caught": p is not None,
            "active": bool(p and p["id"] == s.get("active")),
        })
    return entries


def _dex_row(entry, selected, width):
    cursor = f"{GREEN}▶{RESET}" if selected else " "
    p = entry["pokemon"]
    if p:
        shiny = "✨" if p.get("shiny") else " "
        active = f" {GREEN}●{RESET}" if entry["active"] else "  "
        text = (f"{cursor} ● {entry['idx']:03d} {shiny}{entry['name']:<14} "
                f"Lv.{p['level']:<3} {entry['type']:<9} {entry['rarity']}{active}")
        return _pad_ansi(_fit_ansi(text, width), width)

    text = (f"{cursor} ○ {entry['idx']:03d}  {entry['name']:<14} "
            f"--    {entry['type']:<9} {entry['rarity']}")
    return f"{DIM}{_pad_ansi(_fit_ansi(text, width), width)}{RESET}"


def _dex_frame(entries, selected, top, height, width):
    caught = sum(1 for e in entries if e["caught"])
    selected = max(0, min(selected, len(entries) - 1)) if entries else 0
    current = entries[selected] if entries else None
    if current:
        p = current["pokemon"]
        detail = (f"{current['name']} · {current['type']} · {current['rarity']}"
                  + (f" · Lv.{p['level']}" if p else " · uncaught"))
    else:
        detail = "empty"
    bar_w = min(24, max(8, width - 32))
    filled = round(caught * bar_w / len(entries)) if entries else 0
    header = [
        "",
        _header("pokédex"),
        f"  {CYAN}{'▰' * filled}{'▱' * (bar_w - filled)}{RESET} {caught}/{len(entries)} species",
        f"  {detail}",
    ]
    if current and current["pokemon"]:
        header += ["", *["  " + r for r in _sprite_lines(current["pokemon"])]]
    header.append("")
    body_h = max(1, height - len(header) - 1)
    rows = [_dex_row(e, top + i == selected, width - 2)
            for i, e in enumerate(entries[top:top + body_h])]
    hint = "↑/↓ or wheel move · PgUp/PgDn/space page · Home/End · esc back"
    return "\n".join(header + ["  " + r for r in rows] + ["", _footer(hint)])


def _journal_lines(limit=200):
    entries = journal.tail(limit)
    if not entries:
        return [f"{DIM}No journal yet — your story starts with the next turn.{RESET}"]
    import time
    out, day = [], None
    for e in entries:
        d = time.strftime("%b %d", time.localtime(e.get("ts", 0)))
        if d != day:
            day = d
            out.append(f"{BOLD}{d}{RESET}")
        out.append(f"  {e.get('text', '?')}")
    return out


def _party(s):
    """Best (highest-level) instance per species, active buddy first."""
    best = {}
    for p in s["pokemon"]:
        if p["name"] not in best or p["level"] > best[p["name"]]["level"]:
            best[p["name"]] = p
    mons = sorted(best.values(), key=lambda p: (p["id"] != s.get("active"), p["name"]))
    return mons


# ── tty plumbing ─────────────────────────────────────────────────────────────

def _read_key():
    ch = os.read(0, 1)
    if ch == b"\x1b":  # escape — alone, or the start of an arrow sequence
        ready, _, _ = select.select([0], [], [], 0.0009)
        if not ready:
            return "esc"
        rest = bytearray()
        while True:
            ready, _, _ = select.select([0], [], [], 0.004)
            if not ready:
                break
            rest.extend(os.read(0, 1))
            if rest.startswith(b"[<") and rest[-1:] in (b"M", b"m"):
                break
            if rest.startswith(b"[") and rest[-1:] in b"ABCDFH~":
                break
            if len(rest) >= 24:
                break
        seq = bytes(rest)
        if seq.startswith(b"[<"):
            try:
                button = int(seq[2:].split(b";", 1)[0])
            except ValueError:
                return "esc"
            return {64: "wheel_up", 65: "wheel_down"}.get(button, "mouse")
        return {
            b"[A": "up", b"[B": "down", b"[C": "right", b"[D": "left",
            b"[5~": "page_up", b"[6~": "page_down",
            b"[H": "home", b"[1~": "home", b"[7~": "home",
            b"[F": "end", b"[4~": "end", b"[8~": "end",
        }.get(seq, "esc")
    if ch in (b"\r", b"\n"):
        return "enter"
    if ch == b" ":
        return "space"
    try:
        return ch.decode()
    except UnicodeDecodeError:
        return ""


def _draw(frame):
    sys.stdout.write(HOME_CLEAR + frame.replace("\n", "\r\n"))
    sys.stdout.flush()


def _scroll_screen(title, lines):
    top = 0
    while True:
        height = max(4, shutil.get_terminal_size((80, 24)).lines - 5)
        top = max(0, min(top, max(0, len(lines) - height)))
        _draw(_scroll_frame(title, lines, top, height))
        key = _read_key()
        if key in ("esc", "q"):
            return
        if key in ("up", "k"):
            top -= 1
        elif key in ("down", "j"):
            top += 1
        elif key == "wheel_up":
            top -= 3
        elif key == "wheel_down":
            top += 3
        elif key in ("left", "page_up", "b"):
            top -= height
        elif key in ("right", "page_down", "space", "f"):
            top += height
        elif key in ("home", "g"):
            top = 0
        elif key in ("end", "G"):
            top = len(lines)


def _dex_screen():
    selected = None
    top = 0
    while True:
        s = st.load()
        entries = _dex_entries(s)
        if not entries:
            _scroll_screen("pokédex", [f"{DIM}No dex entries available.{RESET}"])
            return
        if selected is None:
            selected = next((i for i, e in enumerate(entries) if e["active"]), None)
            if selected is None:
                selected = next((i for i, e in enumerate(entries) if e["caught"]), 0)
        height = max(8, shutil.get_terminal_size((80, 24)).lines - 1)
        width = shutil.get_terminal_size((80, 24)).columns
        body_h = max(1, height - 6)
        selected = max(0, min(selected, len(entries) - 1))
        if selected < top:
            top = selected
        elif selected >= top + body_h:
            top = selected - body_h + 1
        top = max(0, min(top, max(0, len(entries) - body_h)))
        _draw(_dex_frame(entries, selected, top, height, width))
        key = _read_key()
        if key in ("esc", "q"):
            return
        if key in ("up", "k"):
            selected -= 1
        elif key in ("down", "j"):
            selected += 1
        elif key == "wheel_up":
            selected -= 3
        elif key == "wheel_down":
            selected += 3
        elif key in ("page_up", "left", "b"):
            selected -= body_h
        elif key in ("page_down", "right", "space", "f"):
            selected += body_h
        elif key in ("home", "g"):
            selected = 0
        elif key in ("end", "G"):
            selected = len(entries) - 1


def _party_screen():
    sel = 0
    while True:
        s = st.load()
        mons = _party(s)
        if not mons:
            _scroll_screen("party", [f"{DIM}No pokémon yet.{RESET}"])
            return
        sel = max(0, min(sel, len(mons) - 1))
        _draw(_party_frame(s, sel))
        key = _read_key()
        if key in ("esc", "q"):
            return
        if key == "up":
            sel -= 1
        elif key == "down":
            sel += 1
        elif key == "enter":
            s["active"] = mons[sel]["id"]
            st.save(s)


def _settings_screen():
    while True:
        s = st.load()
        mode = s.get("mode", "auto")
        on = mode == "battle"
        body = [
            f"  Encounter mode: {BOLD}{'BATTLE' if on else 'AUTO'}{RESET}",
            "",
            f"  {DIM}AUTO{RESET}   commons auto-catch; rare/legendary use Safari",
            f"  {DIM}BATTLE{RESET} every wild is a weaken-then-catch fight",
        ]
        _draw(_scroll_frame("settings", body, 0, 12, "⏎ toggle mode · esc back"))
        key = _read_key()
        if key in ("esc", "q"):
            return
        if key == "enter":
            s["mode"] = "auto" if on else "battle"
            st.save(s)


def _encounter_screen():
    """Fight/Safari a pending wild with arrow-keys + enter — stays open across
    turns (unlike the SwiftBar dropdown, which closes on every action)."""
    sel = 0
    while True:
        s = st.load()
        kind = _encounter_kind(s)
        if kind is None:
            return  # resolved or expired — nothing to fight
        opts = ENCOUNTER_OPTIONS[kind]
        sel = max(0, min(sel, len(opts) - 1))
        _draw(_encounter_frame(s, kind, sel))
        key = _read_key()
        if key in ("esc", "q"):
            return
        if key in ("left", "up"):
            sel = (sel - 1) % len(opts)
        elif key in ("right", "down"):
            sel = (sel + 1) % len(opts)
        elif key in ("enter", "e"):
            action = opts[sel][1]
            turn = sf.take_turn if kind == "safari" else bt.take_turn
            with st.lock():
                fresh = st.load()
                outcome, msg = turn(fresh, action, random.Random())
                st.save(fresh)
            if outcome and outcome.get("done"):
                _draw("\n".join(["", _header("encounter over"), "",
                                 f"  {msg}", "", _footer("press any key…")]))
                _read_key()
                return


def _open(screen):
    if screen == "encounter":
        _encounter_screen()
        return
    s = st.load()
    if screen == "party":
        _party_screen()
    elif screen == "dex":
        _dex_screen()
    elif screen == "journal":
        _scroll_screen("journal", _journal_lines())
    elif screen == "status":
        _scroll_screen("status", _status_lines(s))
    elif screen == "settings":
        _settings_screen()


def run():
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("buddymon menu needs an interactive terminal "
              "(run it directly: python3 buddymon.py menu).")
        return
    if st.active_pokemon(st.load()) is None:
        print("No buddy yet — run /buddymon:choose <starter> first.")
        return
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    sel = 0
    try:
        tty.setcbreak(fd)
        sys.stdout.write(ALT_SCREEN + HIDE_CURSOR + MOUSE_ON)
        if _encounter_kind(st.load()):  # a wild is waiting — jump straight in
            _encounter_screen()
        while True:
            items = _menu_items(st.load())
            sel %= len(items)
            _draw(_menu_frame(items, sel))
            key = _read_key()
            if key in ("q", "esc"):
                break
            if key == "up":
                sel = (sel - 1) % len(items)
            elif key == "down":
                sel = (sel + 1) % len(items)
            elif key in ("enter", "e"):
                choice = items[sel][1]
                if choice == "quit":
                    break
                _open(choice)
                sel = 0  # the menu may have changed (e.g. encounter resolved)
    finally:
        sys.stdout.write(MOUSE_OFF + SHOW_CURSOR + MAIN_SCREEN)
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
