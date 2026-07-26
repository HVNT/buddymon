"""TUI frame builders (pure, terminal-free) + non-tty guard."""
import copy
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import engine, paths, safari, state, tui
from lib import tui_runtime as runtime


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def fresh():
    s = state.default_state()
    engine.create_starter(s, "Charmander")
    return s


def _use_temp_state(monkeypatch, tmp_path, initial):
    monkeypatch.setattr(paths, "STATE_DIR", tmp_path)
    monkeypatch.setattr(paths, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", tmp_path / "sessions")
    state.save(initial)


def _record_background_update():
    with state.lock():
        latest = state.load()
        latest["trainer"]["total_xp"] = 12345
        latest["trainer"]["balls"] = 17
        latest.setdefault("xp_sessions", {})["background"] = {
            "last_uuid": "turn-2",
            "updated": 2,
        }
        latest["pending_encounter"] = safari.start({
            "name": "Beldum",
            "type": "Steel",
            "emoji": "🔩",
            "rarity": "rare",
            "shiny": False,
        })
        latest["pokemon"].append(
            engine.new_pokemon("Abra", "Psychic", "🔮", "common", level=5)
        )
        state.save(latest)
    return copy.deepcopy(latest)


def visible_width(line):
    return len(ANSI_RE.sub("", line))


def _with_pidgeys(s, n, levels):
    for lvl in levels[:n]:
        s["pokemon"].append(engine.new_pokemon("Pidgey", "Flying", "🐦", "common", level=lvl))
    return s


def _feed_keys(monkeypatch, key_bytes: bytes):
    """Drive the real _read_key parser from a fixed byte buffer."""
    buf = bytearray(key_bytes)

    def fake_read(_fd, n):
        if not buf:
            return b""
        chunk = bytes(buf[:n])
        del buf[:n]
        return chunk

    # bytes are already "available", so select always reports readable until drained
    def fake_select(rlist, _w, _x, _timeout=0):
        return ((rlist if buf else []), [], [])

    monkeypatch.setattr(runtime.os, "read", fake_read)
    monkeypatch.setattr(runtime.select, "select", fake_select)
    return buf


def _stub_journal(monkeypatch, entries):
    def fake_tail(n=200, newest_first=False):
        selected = list(entries if n is None else entries[-n:])
        return list(reversed(selected)) if newest_first else selected

    monkeypatch.setattr(tui.journal, "tail", fake_tail)
