"""Shared local side effects for saving Showcase images."""
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import notify, showcase_export, state


@dataclass(frozen=True)
class ShareResult:
    ok: bool
    message: str
    path: Optional[Path] = None
    short_message: Optional[str] = None


def reveal_file(path):
    try:
        subprocess.Popen(
            ["open", "-R", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def save_with_feedback(s=None, failure_prefix="share failed"):
    s = state.load() if s is None else s
    try:
        path = showcase_export.save_showcase_image(s)
    except OSError as exc:
        message = f"{failure_prefix}: {exc}"
        if state.preference(s, "share_banner") == "on":
            notify.banner("BuddyMon Showcase", message)
        return ShareResult(ok=False, message=message)

    short_message = f"Saved {path.name}"
    if state.preference(s, "share_reveal") == "on":
        reveal_file(path)
    if state.preference(s, "share_banner") == "on":
        notify.banner("BuddyMon Showcase", short_message)
    return ShareResult(
        ok=True,
        message=f"saved Showcase image to {path}",
        path=path,
        short_message=short_message,
    )
