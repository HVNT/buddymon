"""Manual, local-only BuddyMon state backups shared by every surface."""
import shutil
import time
from pathlib import Path

from . import paths, state


class BackupError(OSError):
    """A backup could not be completed without touching live BuddyMon data."""


def create_backup(destination_root=None, now=None):
    """Copy the active BuddyMon state directory into a timestamped local folder.

    The state lock makes the state-file portion consistent with normal game
    writes. The source is always ``paths.STATE_DIR``, so XDG test profiles and
    the normal profile share exactly the same behavior.
    """
    source = paths.STATE_DIR
    if not source.is_dir() or not paths.STATE_FILE.is_file():
        raise BackupError(f"BuddyMon data was not found at {source}")

    root = Path(destination_root or Path.home() / "Documents" / "BuddyMon Backups")
    root.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(now))
    destination = _unique_destination(root, timestamp)
    staging = root / f".{destination.name}-in-progress"

    try:
        with state.lock():
            shutil.copytree(source, staging, ignore=shutil.ignore_patterns(".lock"))
        if not (staging / "state.json").is_file():
            raise BackupError(f"BuddyMon could not verify the backup at {staging}")
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return destination


def _unique_destination(root, timestamp):
    suffix = 0
    while True:
        name = timestamp if suffix == 0 else f"{timestamp}-{suffix}"
        candidate = root / name
        if not candidate.exists():
            return candidate
        suffix += 1
