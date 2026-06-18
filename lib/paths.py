"""Filesystem locations. All buddymon state lives under XDG state, never ~/.claude."""
import os
from pathlib import Path

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "buddymon"
STATE_FILE = STATE_DIR / "state.json"
SESSIONS_DIR = STATE_DIR / "sessions"
JOURNAL_FILE = STATE_DIR / "journal.jsonl"


def ensure_dirs():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
