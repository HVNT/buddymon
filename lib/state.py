"""Trainer state and per-session event files. One JSON file, atomic writes."""
import contextlib
import fcntl
import json
import os
import tempfile
import time

from . import paths


@contextlib.contextmanager
def lock():
    """Serialize read-modify-write cycles across hook, tmux, and launchd."""
    paths.ensure_dirs()
    with open(paths.STATE_DIR / ".lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _atomic_write_json(path, obj, indent=None):
    """Write JSON to path via a temp file + rename, so readers never see a
    partial write. Cleans up the temp file on any failure."""
    paths.ensure_dirs()
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.stem + "-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=indent)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


STATE_VERSION = 3


def default_state():
    return {
        "version": STATE_VERSION,
        "trainer": {
            "streak": 0,
            "last_day": None,
            "balls": 10,
            "total_xp": 0,
            "total_tokens": 0,
        },
        "active": None,  # pokemon id
        "pokemon": [],  # {id, name, emoji, type, rarity, level, xp, shiny, caught_at}
        "xp_sessions": {},  # session_id -> {"last_uuid": str, "updated": epoch}
        "mode": "auto",  # "auto" (Safari) or "battle" (weaken-then-catch)
    }


def _migrate(state):
    trainer = state.setdefault("trainer", {})
    trainer.setdefault("streak", 0)
    trainer.setdefault("last_day", None)
    trainer.setdefault("balls", 10)
    trainer.setdefault("total_xp", 0)
    trainer.setdefault("total_tokens", 0)
    version = state.get("version", STATE_VERSION)
    if state.get("version") == 1:
        # v2 moved to a cubic XP curve. Keep every pokemon's level and name;
        # snap xp up to the new curve's floor so nothing de-levels.
        from . import engine
        for p in state["pokemon"]:
            p["xp"] = max(p["xp"], engine.xp_for_level(p["level"]))
        state["version"] = 2
        version = 2
    if version < 3:
        # v3 made wild levels evolution-stage-aware. Existing caught evolved
        # forms may predate that and sit below the level their previous form
        # evolves into them. Raise only; never de-level older unevolved catches.
        from . import engine
        for p in state.get("pokemon", []):
            level = max(1, int(p.get("level") or 1))
            lower, _ = engine.evolution_level_bounds(p.get("name", ""))
            if level < lower:
                level = lower
                p["level"] = level
            p["xp"] = max(int(p.get("xp") or 0), engine.xp_for_level(level))
        state["version"] = 3
    return state


def load():
    if paths.STATE_FILE.exists():
        try:
            state = json.loads(paths.STATE_FILE.read_text(encoding="utf-8"))
            version = state.get("version")
            if isinstance(state, dict) and isinstance(version, int) and 1 <= version <= STATE_VERSION:
                return _migrate(state)
        except (json.JSONDecodeError, OSError):
            pass
    return default_state()


def save(state):
    _atomic_write_json(paths.STATE_FILE, state, indent=2)


def active_pokemon(state):
    for p in state["pokemon"]:
        if p["id"] == state["active"]:
            return p
    return state["pokemon"][0] if state["pokemon"] else None


def prune_sessions(state, keep=20):
    """Drop the oldest per-session XP anchors so the file never grows unbounded."""
    sessions = state.get("xp_sessions", {})
    if len(sessions) <= keep:
        return
    oldest = sorted(sessions, key=lambda k: sessions[k].get("updated", 0))
    for key in oldest[: len(sessions) - keep]:
        del sessions[key]


# ── Session event files (what the statusline mood reads) ────────────────────


def record_event(session_id, event, detail=""):
    """Write the latest session event. Must stay cheap: called from every hook."""
    if not session_id:
        return
    payload = {"event": event, "detail": detail, "ts": time.time()}
    _atomic_write_json(paths.SESSIONS_DIR / f"{session_id}.json", payload)


def read_event(session_id):
    if not session_id:
        return None
    try:
        return json.loads((paths.SESSIONS_DIR / f"{session_id}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def prune_session_files(max_age_secs=2 * 24 * 3600):
    """Delete stale event files. Called from SessionStart, never the hot path."""
    if not paths.SESSIONS_DIR.exists():
        return
    cutoff = time.time() - max_age_secs
    for f in paths.SESSIONS_DIR.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass
