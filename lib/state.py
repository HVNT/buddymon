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

STATE_VERSION = 2


def default_state():
    return {
        "version": STATE_VERSION,
        "trainer": {
            "streak": 0,
            "last_day": None,
            "balls": 10,
            "total_xp": 0,
        },
        "active": None,  # pokemon id
        "pokemon": [],  # {id, name, emoji, type, rarity, level, xp, shiny, caught_at}
        "xp_sessions": {},  # session_id -> {"last_uuid": str, "updated": epoch}
    }


def _migrate(state):
    if state.get("version") == 1:
        # v2 moved to a cubic XP curve. Keep every pokemon's level and name;
        # snap xp up to the new curve's floor so nothing de-levels.
        from . import engine
        for p in state["pokemon"]:
            p["xp"] = max(p["xp"], engine.xp_for_level(p["level"]))
        state["version"] = 2
    return state


def load():
    if paths.STATE_FILE.exists():
        try:
            state = json.loads(paths.STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(state, dict) and state.get("version") in (1, STATE_VERSION):
                return _migrate(state)
        except (json.JSONDecodeError, OSError):
            pass
    return default_state()


def save(state):
    paths.ensure_dirs()
    fd, tmp = tempfile.mkstemp(dir=paths.STATE_DIR, prefix=".state-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, paths.STATE_FILE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
    paths.ensure_dirs()
    payload = {"event": event, "detail": detail, "ts": time.time()}
    fd, tmp = tempfile.mkstemp(dir=paths.SESSIONS_DIR, prefix=".evt-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp, paths.SESSIONS_DIR / f"{session_id}.json")
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
