"""Lifecycle management for optional local art packs."""

import contextlib
import fcntl
import importlib
import io
import json
import os
import shutil
import tempfile
from pathlib import Path

from . import paths, species


INSTALL_MISSING = "install_missing"
REFRESH = "refresh"
OPERATIONS = (INSTALL_MISSING, REFRESH)
PACK_ORDER = ("gen2", "box", "gen5")
ASSET_INSTALLERS = {
    "gen2": "tools.fetch_official",
    "box": "tools.fetch_box",
    "gen5": "tools.fetch_gen5",
}
PACK_SPECIES = {
    "gen2": species.GEN2_SPECIES,
    "box": species.ALL_SPECIES,
    "gen5": species.ALL_SPECIES,
}


class AssetRecoveryError(RuntimeError):
    """Raised when automatic rollback leaves a preserved recovery backup."""

    def __init__(self, message, recovery_path):
        super().__init__(message)
        self.recovery_path = recovery_path


def pack_root():
    """Return the current XDG-aware art-pack directory."""
    return paths.STATE_DIR / "packs"


def _pack_candidates(kind, root=None):
    root = Path(root) if root is not None else pack_root()
    if kind == "gen5":
        return (root / "gen5", root / "gen5.json")
    return (root / f"{kind}.json",)


def _path_has_pack(kind, path):
    try:
        if kind == "gen5" and path.is_dir():
            return any(candidate.is_file() and candidate.stat().st_size > 0
                       for candidate in path.glob("*.json"))
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def pack_path(kind, root=None):
    """Return the installed path, or the preferred path when it is missing."""
    candidates = _pack_candidates(kind, root)
    return next((path for path in candidates if _path_has_pack(kind, path)), candidates[0])


def pack_installed(kind, root=None):
    return any(_path_has_pack(kind, path) for path in _pack_candidates(kind, root))


def pack_status():
    return {
        kind: {
            "installed": pack_installed(kind),
            "path": str(pack_path(kind)),
        }
        for kind in PACK_ORDER
    }


def _run_installer(installer, destination):
    try:
        if callable(installer):
            return installer(destination)
        module = importlib.import_module(installer)
        return module.main(pack_root=destination)
    except SystemExit as exc:
        if exc.code in (None, 0):
            return None
        raise RuntimeError(str(exc.code)) from exc


def _load_json_object(path):
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not payload:
        raise ValueError(f"asset output is empty or invalid: {path}")
    return payload


def _inventory_error(kind, actual, expected):
    missing = [item for item in expected if item not in actual]
    unexpected = sorted(actual - set(expected))
    if not missing and not unexpected:
        return

    details = []
    if missing:
        sample = ", ".join(missing[:5])
        details.append(f"missing {len(missing)} ({sample})")
    if unexpected:
        sample = ", ".join(unexpected[:5])
        details.append(f"unexpected {len(unexpected)} ({sample})")
    raise ValueError(f"{kind} pack inventory mismatch: " + "; ".join(details))


def _validate_entries(kind, entries, expected):
    _inventory_error(kind, set(entries), expected)
    invalid = [
        name for name in expected
        if not isinstance(entries[name], dict) or not entries[name]
    ]
    if invalid:
        sample = ", ".join(invalid[:5])
        raise ValueError(
            f"{kind} pack has {len(invalid)} invalid entries ({sample})"
        )


def _validated_candidate(kind, staging_root):
    candidate = pack_path(kind, staging_root)
    if not pack_installed(kind, staging_root):
        raise ValueError(f"installer did not create the {kind} pack")

    expected = PACK_SPECIES[kind]
    if candidate.is_dir():
        files = {path.stem: path for path in candidate.glob("*.json")}
        expected_slugs = tuple(species.slug(name) for name in expected)
        _inventory_error(kind, set(files), expected_slugs)
        for slug in expected_slugs:
            _load_json_object(files[slug])
    else:
        _validate_entries(kind, _load_json_object(candidate), expected)
    return candidate


@contextlib.contextmanager
def _promotion_lock(kind, live_root):
    """Serialize one pack's live-path changes across BuddyMon processes."""
    lock_path = live_root / f".{kind}.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _restore_backups(moved):
    errors = []
    for live_path, backup_path in reversed(moved):
        try:
            os.replace(backup_path, live_path)
        except OSError as exc:
            errors.append(str(exc))
    if errors:
        raise OSError("could not restore the previous asset pack: " + "; ".join(errors))


def _promote(kind, candidate, staging_root, live_root):
    backup_root = staging_root / ".previous"
    backup_root.mkdir()
    moved = []

    try:
        for live_path in _pack_candidates(kind, live_root):
            if not live_path.exists() and not live_path.is_symlink():
                continue
            backup_path = backup_root / live_path.name
            os.replace(live_path, backup_path)
            moved.append((live_path, backup_path))

        promoted_path = live_root / candidate.name
        os.replace(candidate, promoted_path)
        return promoted_path
    except Exception as exc:
        try:
            _restore_backups(moved)
        except OSError as restore_exc:
            raise AssetRecoveryError(
                f"{exc}; {restore_exc}; recovery backup preserved at "
                f"{backup_root}",
                backup_root,
            ) from restore_exc
        raise


def install(operation=INSTALL_MISSING, kinds=None):
    """Install or refresh selected packs and return a structured result."""
    if operation not in OPERATIONS:
        raise ValueError(f"unknown asset operation: {operation}")

    selected = list(PACK_ORDER) if kinds is None else list(dict.fromkeys(kinds))
    invalid = [kind for kind in selected if kind not in ASSET_INSTALLERS]
    if invalid:
        raise ValueError("unknown asset pack: " + ", ".join(invalid))

    live_root = pack_root()
    live_root.mkdir(parents=True, exist_ok=True)
    results = []

    for kind in selected:
        if operation == INSTALL_MISSING and pack_installed(kind, live_root):
            results.append({
                "kind": kind,
                "status": "skipped",
                "path": str(pack_path(kind, live_root)),
                "message": "already installed",
            })
            continue

        staging_root = Path(tempfile.mkdtemp(prefix=f".{kind}-", dir=live_root))
        output = io.StringIO()
        preserve_staging = False
        try:
            with contextlib.redirect_stdout(output):
                _run_installer(ASSET_INSTALLERS[kind], staging_root)
            candidate = _validated_candidate(kind, staging_root)
            with _promotion_lock(kind, live_root):
                if (
                    operation == INSTALL_MISSING
                    and pack_installed(kind, live_root)
                ):
                    results.append({
                        "kind": kind,
                        "status": "skipped",
                        "path": str(pack_path(kind, live_root)),
                        "message": "installed by another process",
                        "output": output.getvalue()[-4000:],
                    })
                    continue
                promoted_path = _promote(
                    kind, candidate, staging_root, live_root
                )
        except Exception as exc:
            entry = {
                "kind": kind,
                "status": "failed",
                "path": str(pack_path(kind, live_root)),
                "message": str(exc),
                "output": output.getvalue()[-4000:],
            }
            if isinstance(exc, AssetRecoveryError):
                preserve_staging = True
                entry["recovery_path"] = str(exc.recovery_path)
            results.append(entry)
        else:
            status = "installed" if operation == INSTALL_MISSING else "refreshed"
            results.append({
                "kind": kind,
                "status": status,
                "path": str(promoted_path),
                "message": status,
                "output": output.getvalue()[-4000:],
            })
        finally:
            if not preserve_staging:
                shutil.rmtree(staging_root, ignore_errors=True)

    successful = {"installed", "refreshed", "skipped"}
    return {
        "operation": operation,
        "ok": all(result["status"] in successful for result in results),
        "results": results,
        "packs": pack_status(),
    }


def installer_cli(kind):
    """Run a direct asset tool through the same staged refresh lifecycle."""
    result = install(operation=REFRESH, kinds=[kind])
    entry = result["results"][0]
    output = entry.get("output", "").rstrip()
    if output:
        print(output)
    print(f"{kind}: {entry['status']} - {entry['message']}")
    return 0 if result["ok"] else 1
