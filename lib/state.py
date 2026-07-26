"""Trainer state and per-session event files. One JSON file, atomic writes."""
import contextlib
import fcntl
import json
import math
import os
import shutil
import tempfile
import time
from datetime import date

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


STATE_VERSION = 5
VALID_MODES = ("auto", "safari", "battle")
DEFAULT_MODE = "auto"
DEFAULT_PREFERENCES = {
    "notifications": "on",
    "menu_launcher": "auto",
    "terminal_graphics": "auto",
    "menu_replace": "on",
    "share_reveal": "on",
    "share_banner": "on",
}
PREFERENCE_VALUES = {
    "notifications": ("on", "silent", "off"),
    "menu_launcher": ("auto", "ghostty", "iterm", "terminal"),
    "terminal_graphics": ("auto", "off"),
    "menu_replace": ("on", "off"),
    "share_reveal": ("on", "off"),
    "share_banner": ("on", "off"),
}


class StateLoadError(RuntimeError):
    """Existing BuddyMon state cannot be used safely."""

    code = "state_unavailable"

    def __init__(self, message, *, path=None):
        super().__init__(message)
        self.path = path or paths.STATE_FILE


class InvalidStateError(StateLoadError):
    """Existing state is corrupt or does not match BuddyMon's state shape."""

    code = "invalid_state"


class UnsupportedStateVersionError(StateLoadError):
    """Existing state was written by a newer BuddyMon release."""

    code = "unsupported_state_version"

    def __init__(self, version):
        self.version = version
        super().__init__(
            "This BuddyMon data was written by a newer release "
            f"(state v{version}; this build supports through v{STATE_VERSION}). "
            "Update BuddyMon before changing anything. Your data was left untouched."
        )


class UnreadableStateError(StateLoadError):
    """Existing state could not be read from disk."""

    code = "unreadable_state"


class LoadedState(dict):
    """State loaded from disk, with migration provenance kept out of JSON."""

    def __init__(self, value, *, source_version=None, loaded_from_disk=False):
        super().__init__(value)
        self.source_version = source_version
        self.loaded_from_disk = loaded_from_disk
        self.migration_backup = None


def _invalid_state(message):
    return InvalidStateError(
        f"BuddyMon could not safely read state.json ({message}). "
        "Your data was left untouched. Restore a backup or move the file aside "
        "before starting over."
    )


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_text(value):
    return isinstance(value, str) and bool(value.strip())


def _require_fields(value, fields, label):
    missing = [field for field in fields if field not in value]
    if missing:
        raise _invalid_state(
            f"{label} is missing required field {missing[0]!r}"
        )


def _validate_trainer(value, *, require_all):
    if not isinstance(value, dict):
        raise _invalid_state("trainer data is invalid")
    validators = {
        "streak": lambda item: _is_int(item) and item >= 0,
        "last_day": lambda item: item is None or _is_text(item),
        "balls": lambda item: _is_int(item) and item >= 0,
        "total_xp": lambda item: _is_int(item) and item >= 0,
        "total_tokens": lambda item: _is_int(item) and item >= 0,
    }
    if require_all:
        _require_fields(value, validators, "trainer data")
    for field, validator in validators.items():
        if field in value and not validator(value[field]):
            raise _invalid_state(f"trainer field {field!r} is invalid")
    last_day = value.get("last_day")
    if last_day:
        try:
            date.fromisoformat(last_day)
        except ValueError as exc:
            raise _invalid_state("trainer field 'last_day' is invalid") from exc


def _validate_pokemon(value):
    if not isinstance(value, list):
        raise _invalid_state("the Pokemon collection is missing or invalid")
    validators = {
        "id": _is_text,
        "name": _is_text,
        "emoji": lambda item: isinstance(item, str),
        "type": _is_text,
        "rarity": _is_text,
        "level": lambda item: _is_int(item) and item >= 1,
        "xp": lambda item: _is_int(item) and item >= 0,
        "shiny": lambda item: isinstance(item, bool),
        "caught_at": lambda item: _is_number(item) and item >= 0,
    }
    ids = set()
    for index, pokemon in enumerate(value):
        label = f"Pokemon record {index}"
        if not isinstance(pokemon, dict):
            raise _invalid_state(f"{label} is not an object")
        _require_fields(pokemon, validators, label)
        for field, validator in validators.items():
            if not validator(pokemon[field]):
                raise _invalid_state(f"{label} field {field!r} is invalid")
        if "favorite" in pokemon and not isinstance(pokemon["favorite"], bool):
            raise _invalid_state(f"{label} field 'favorite' is invalid")
        if pokemon["id"] in ids:
            raise _invalid_state(f"{label} has a duplicate id")
        ids.add(pokemon["id"])
    return ids


def _validate_sessions(value, *, require_all):
    if not isinstance(value, dict):
        raise _invalid_state("session data is invalid")
    validators = {
        "last_uuid": lambda item: isinstance(item, str),
        "updated": _is_number,
    }
    for session_id, session in value.items():
        if not _is_text(session_id) or not isinstance(session, dict):
            raise _invalid_state("session data is invalid")
        label = f"session record {session_id!r}"
        if require_all:
            _require_fields(session, validators, label)
        for field, validator in validators.items():
            if field in session and not validator(session[field]):
                raise _invalid_state(f"{label} field {field!r} is invalid")


def _validate_preferences(
    value,
    *,
    require_all,
    allow_legacy_values=False,
    allow_unknown=False,
):
    if not isinstance(value, dict):
        raise _invalid_state("preferences are invalid")
    if require_all:
        _require_fields(value, PREFERENCE_VALUES, "preferences")
    if not allow_unknown:
        unknown = set(value) - set(PREFERENCE_VALUES)
        if unknown:
            raise _invalid_state(
                f"preference {sorted(unknown)[0]!r} is not supported"
            )
    if not allow_legacy_values:
        for key, allowed in PREFERENCE_VALUES.items():
            if key in value and value[key] not in allowed:
                raise _invalid_state(f"preference {key!r} is invalid")


def _validate_last_throw(value, *, battle):
    if value is None:
        return
    if not isinstance(value, dict):
        raise _invalid_state("encounter last throw is invalid")
    fields = {
        "caught": lambda item: isinstance(item, bool),
        "ts": _is_number,
    }
    if battle:
        fields["jiggles"] = lambda item: _is_int(item) and 0 <= item <= 3
    _require_fields(value, fields, "encounter last throw")
    for field, validator in fields.items():
        if not validator(value[field]):
            raise _invalid_state(f"encounter last throw field {field!r} is invalid")


def _validate_safari_encounter(value):
    if not isinstance(value, dict):
        raise _invalid_state("Safari encounter data is invalid")
    validators = {
        "name": _is_text,
        "type": _is_text,
        "emoji": lambda item: isinstance(item, str),
        "rarity": _is_text,
        "shiny": lambda item: isinstance(item, bool),
        "c": lambda item: _is_int(item) and item >= 0,
        "base_c": lambda item: _is_int(item) and item >= 0,
        "angry": lambda item: _is_int(item) and item >= 0,
        "eating": lambda item: _is_int(item) and item >= 0,
        "balls_thrown": lambda item: _is_int(item) and item >= 0,
        "moves": lambda item: _is_int(item) and item >= 0,
        "last_msg": lambda item: isinstance(item, str),
    }
    _require_fields(value, validators, "Safari encounter data")
    for field, validator in validators.items():
        if not validator(value[field]):
            raise _invalid_state(f"Safari encounter field {field!r} is invalid")
    if "level" in value and not (_is_int(value["level"]) and value["level"] >= 1):
        raise _invalid_state("Safari encounter field 'level' is invalid")
    if "created_ts" in value and not _is_number(value["created_ts"]):
        raise _invalid_state("Safari encounter field 'created_ts' is invalid")
    if "last_throw" in value:
        _validate_last_throw(value["last_throw"], battle=False)


def _validate_battle_encounter(value):
    if not isinstance(value, dict):
        raise _invalid_state("battle encounter data is invalid")
    validators = {
        "name": _is_text,
        "type": _is_text,
        "emoji": lambda item: isinstance(item, str),
        "rarity": _is_text,
        "shiny": lambda item: isinstance(item, bool),
        "level": lambda item: _is_int(item) and item >= 1,
        "wild_level": lambda item: _is_int(item) and item >= 1,
        "wild_hp": lambda item: _is_int(item) and item >= 0,
        "wild_hp_max": lambda item: _is_int(item) and item > 0,
        "buddy_hp": lambda item: _is_int(item) and item >= 0,
        "buddy_hp_max": lambda item: _is_int(item) and item > 0,
        "balls_thrown": lambda item: _is_int(item) and item >= 0,
        "last_msg": lambda item: isinstance(item, str),
    }
    _require_fields(value, validators, "battle encounter data")
    for field, validator in validators.items():
        if not validator(value[field]):
            raise _invalid_state(f"battle encounter field {field!r} is invalid")
    if value["wild_hp"] > value["wild_hp_max"]:
        raise _invalid_state("battle encounter wild HP is invalid")
    if value["buddy_hp"] > value["buddy_hp_max"]:
        raise _invalid_state("battle encounter buddy HP is invalid")
    if "created_ts" in value and not _is_number(value["created_ts"]):
        raise _invalid_state("battle encounter field 'created_ts' is invalid")
    _validate_last_throw(value.get("last_throw"), battle=True)


def _validate_optional_state(value):
    if "pending_encounter" in value:
        _validate_safari_encounter(value["pending_encounter"])
    if "pending_battle" in value:
        _validate_battle_encounter(value["pending_battle"])
    if "pending_encounter" in value and "pending_battle" in value:
        raise _invalid_state("multiple encounters are active")
    if "collectors" in value and not isinstance(value["collectors"], dict):
        raise _invalid_state("collector data is invalid")
    if "showcase" in value:
        showcase = value["showcase"]
        if not isinstance(showcase, dict) or not isinstance(showcase.get("slots"), list):
            raise _invalid_state("Showcase data is invalid")
        if any(slot is not None and not _is_text(slot) for slot in showcase["slots"]):
            raise _invalid_state("Showcase slots are invalid")


def _validate_source_state(value):
    if not isinstance(value, dict):
        raise _invalid_state("the top level is not an object")
    version = value.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise _invalid_state("the state version is missing or invalid")
    if version > STATE_VERSION:
        raise UnsupportedStateVersionError(version)
    if version < 1:
        raise _invalid_state(f"state version {version} is not supported")
    _validate_pokemon(value.get("pokemon"))
    if version >= 4 and "active" not in value:
        raise _invalid_state("the active Pokemon id is missing")
    if "active" in value and value["active"] is not None and not _is_text(value["active"]):
        raise _invalid_state("the active Pokemon id is invalid")
    if version >= 4 or "trainer" in value:
        _validate_trainer(value.get("trainer"), require_all=version >= 4)
    if version >= 4 or "xp_sessions" in value:
        _validate_sessions(
            value.get("xp_sessions"),
            require_all=version >= STATE_VERSION,
        )
    if version >= 4 and "mode" not in value:
        raise _invalid_state("encounter mode is missing")
    if "mode" in value:
        mode = value["mode"]
        if not isinstance(mode, str) or (version >= 4 and mode not in VALID_MODES):
            raise _invalid_state("encounter mode is invalid")
    if version >= 4 or "preferences" in value:
        _validate_preferences(
            value.get("preferences"),
            require_all=version >= STATE_VERSION,
            allow_legacy_values=version < 4,
            allow_unknown=version < 4,
        )
    _validate_optional_state(value)
    return version


def _validate_current_state(value):
    if not isinstance(value, dict) or value.get("version") != STATE_VERSION:
        raise _invalid_state("the current state version is invalid")
    _validate_trainer(value.get("trainer"), require_all=True)
    pokemon_ids = _validate_pokemon(value.get("pokemon"))
    active = value.get("active")
    if active is not None and (not _is_text(active) or active not in pokemon_ids):
        raise _invalid_state("the active Pokemon id is invalid")
    _validate_sessions(value.get("xp_sessions"), require_all=True)
    if value.get("mode") not in VALID_MODES:
        raise _invalid_state("encounter mode is invalid")
    _validate_preferences(value.get("preferences"), require_all=True)
    _validate_optional_state(value)


def _preserve_pre_migration_state(source_version):
    recovery_dir = paths.STATE_DIR / "recovery"
    recovery_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = recovery_dir / (
        f"state-v{source_version}-pre-migration-{time.time_ns()}.json"
    )
    shutil.copy2(paths.STATE_FILE, destination)
    return destination


def _validated_mode(value):
    return value if value in VALID_MODES else DEFAULT_MODE


def _validated_preferences(value):
    prefs = dict(value) if isinstance(value, dict) else {}
    out = dict(DEFAULT_PREFERENCES)
    for key, allowed in PREFERENCE_VALUES.items():
        if prefs.get(key) in allowed:
            out[key] = prefs[key]
    return out


def preferences(state):
    """Validated preference dict for an already-loaded state object."""
    if not isinstance(state, dict):
        return dict(DEFAULT_PREFERENCES)
    state["preferences"] = _validated_preferences(state.get("preferences"))
    return state["preferences"]


def preference(state, key):
    return preferences(state).get(key, DEFAULT_PREFERENCES.get(key))


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
        "mode": DEFAULT_MODE,  # "auto" (Quick), "safari", or "battle"
        "preferences": dict(DEFAULT_PREFERENCES),
    }


def _migrate(state):
    trainer = state.setdefault("trainer", {})
    state.setdefault("xp_sessions", {})
    state.setdefault("active", None)
    trainer.setdefault("streak", 0)
    trainer.setdefault("last_day", None)
    trainer.setdefault("balls", 10)
    trainer.setdefault("total_xp", 0)
    trainer.setdefault("total_tokens", 0)
    for session in state["xp_sessions"].values():
        session.setdefault("last_uuid", "")
        session.setdefault("updated", 0)
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
        version = 3
    state["mode"] = _validated_mode(state.get("mode"))
    state["preferences"] = _validated_preferences(state.get("preferences"))
    if version < 4:
        state["version"] = 4
        version = 4
    # v5 formalizes session and preference fields that were added
    # incrementally while older releases were still writing state v4.
    if version < 5:
        state["version"] = 5
    return state


def load():
    if not paths.STATE_FILE.exists():
        return LoadedState(default_state())
    try:
        raw = paths.STATE_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        raise UnreadableStateError(
            "BuddyMon could not read state.json. Check its permissions and try again. "
            "Your data was left untouched."
        ) from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _invalid_state("the file is not valid JSON") from exc

    source_version = _validate_source_state(value)
    try:
        migrated = _migrate(value)
        _validate_current_state(migrated)
    except StateLoadError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise _invalid_state("required fields are missing or invalid") from exc
    return LoadedState(
        migrated,
        source_version=source_version,
        loaded_from_disk=True,
    )


def save(state):
    _validate_current_state(state)
    if (
        isinstance(state, LoadedState)
        and state.loaded_from_disk
        and state.source_version is not None
        and state.source_version < STATE_VERSION
        and state.migration_backup is None
    ):
        state.migration_backup = _preserve_pre_migration_state(
            state.source_version
        )
    _atomic_write_json(paths.STATE_FILE, state, indent=2)
    if isinstance(state, LoadedState):
        state.loaded_from_disk = True
        state.source_version = STATE_VERSION


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
