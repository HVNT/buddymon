"""Resumable first-launch art setup, separate from gameplay state.

Only the native setup command starts downloads. Status reads and ordinary game
commands remain local. Completed Gen 5 species become visible immediately;
the incomplete marker prevents a partial pack being mistaken for a full one.
"""

import fcntl
import json
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import assets, data, paths, species, state

STATUS_FILE = "art-setup.json"
LOCK_FILE = ".art-setup.lock"
COMPLETION_SCHEMA = 1  # Completion includes both regular and shiny Gen 5 art.


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".art-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _download_running():
    try:
        with (paths.STATE_DIR / LOCK_FILE).open("r+b") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(handle, fcntl.LOCK_UN)
    except OSError:
        pass
    return False


def _saved_status():
    try:
        saved = json.loads((paths.STATE_DIR / STATUS_FILE).read_text())
        if not isinstance(saved, dict):
            saved = {}
    except (OSError, ValueError):
        saved = {}
    return saved


def _complete(saved):
    return (
        saved.get("state") == "complete"
        and saved.get("schema_version") == COMPLETION_SCHEMA
        and all(assets.pack_ready(kind) for kind in assets.PACK_ORDER)
    )


def status():
    saved = _saved_status()
    if _complete(saved):
        return {"state": "complete", "message": "Pokémon art ready", "can_retry": False}
    if _download_running():
        return {
            "state": "downloading",
            "message": saved.get("message", "Downloading Pokémon art…"),
            "completed": saved.get("completed", 0),
            "total": saved.get("total", len(species.ALL_SPECIES)),
            "can_retry": False,
        }
    if saved and saved.get("state") != "complete":
        return {
            "state": "incomplete", "message": "Art download paused · Retry",
            "can_retry": True,
        }
    return {"state": "needed", "message": "Preparing Pokémon art…", "can_retry": False}


def _priority_names():
    try:
        game = state.load()
        active = state.active_pokemon(game) or {}
        owned = [pokemon.get("name") for pokemon in game.get("pokemon", [])]
        priority = [active.get("name"), *data.STARTERS, *owned]
    except state.StateLoadError:
        priority = list(data.STARTERS)
    return list(dict.fromkeys(name for name in priority if name in species.DEX_NUMBERS))


def _read_entry(path):
    try:
        entry = json.loads(path.read_text())
        return entry if isinstance(entry, dict) else {}
    except (OSError, ValueError):
        return {}


def _entry_ready(entry):
    return bool(entry.get("frames")) and bool(entry.get("shiny_frames"))


def _install_gen5(report):
    from tools.fetch_gen5 import IncompleteSpriteError, species_entry

    live_root = assets.pack_root()
    live_root.mkdir(parents=True, exist_ok=True)
    with assets._promotion_lock("gen5", live_root):
        destination = live_root / "gen5"
        destination.mkdir(exist_ok=True)
        marker = destination / ".downloading"
        marker.touch()
        priority = _priority_names()
        names = priority + [name for name in species.ALL_SPECIES if name not in priority]
        legacy = _read_entry(live_root / "gen5.json")
        missing = []
        for name in names:
            path = destination / f"{species.slug(name)}.json"
            entry = _read_entry(path)
            if not entry and isinstance(legacy.get(name), dict):
                entry = legacy[name]
                _write_json(path, entry)
            if not _entry_ready(entry):
                missing.append((name, entry))
        completed = len(names) - len(missing)
        report(f"Pokémon art {completed}/{len(names)}", completed, len(names))
        executor = ThreadPoolExecutor(max_workers=4)
        try:
            pending = {
                executor.submit(
                    species_entry, species.DEX_NUMBERS[name], name, existing=entry
                ): name
                for name, entry in missing
            }
            for future in as_completed(pending):
                name = pending[future]
                path = destination / f"{species.slug(name)}.json"
                try:
                    entry = future.result()
                except IncompleteSpriteError as exc:
                    _write_json(path, exc.entry)
                    raise
                _write_json(path, entry)
                completed += 1
                report(f"Pokémon art {completed}/{len(names)}", completed, len(names))
        finally:
            executor.shutdown(wait=True, cancel_futures=True)
        assets._validated_candidate("gen5", live_root)
        marker.unlink()


def install():
    """Download missing art once per user, preserving progress on interruption."""
    paths.STATE_DIR.mkdir(parents=True, exist_ok=True)
    with (paths.STATE_DIR / LOCK_FILE).open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"ok": True, "already_running": True}
        if _complete(_saved_status()):
            return {"ok": True, "already_complete": True}
        last_report = 0.0

        def report(message, completed=0, total=0, *, force=False):
            nonlocal last_report
            now = time.monotonic()
            if not force and now - last_report < 0.5:
                return
            last_report = now
            _write_json(paths.STATE_DIR / STATUS_FILE, {
                "state": "downloading", "message": message,
                "completed": completed, "total": total,
            })

        try:
            report("Downloading Pokémon art…", force=True)
            _install_gen5(report)
            for kind, label in (
                ("trainer", "Downloading Trainer Red…"),
                ("box", "Downloading small Pokémon sprites…"),
                ("gen2", "Finishing Pokémon art…"),
            ):
                if assets.pack_ready(kind):
                    continue
                report(label, force=True)
                result = assets.install(kinds=[kind])
                if not result["ok"]:
                    raise RuntimeError(result["results"][0]["message"])
            _write_json(paths.STATE_DIR / STATUS_FILE, {
                "state": "complete", "schema_version": COMPLETION_SCHEMA,
            })
            return {"ok": True}
        except Exception as exc:
            _write_json(paths.STATE_DIR / STATUS_FILE, {
                "state": "incomplete", "detail": str(exc),
            })
            return {"ok": False, "message": "Art download paused. Check your connection and retry."}
