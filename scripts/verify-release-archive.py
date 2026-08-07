#!/usr/bin/env python3
"""Verify the exact signed BuddyMon archive a user downloads."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CHECKSUM_LINE = re.compile(r"^([0-9a-f]{64})\s+\*?([^\s]+)$")


class ReleaseArchiveError(RuntimeError):
    """Raised when a release archive does not satisfy the public-release gate."""


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_checksum(path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ReleaseArchiveError(f"cannot read checksum: {path}") from exc
    if len(lines) != 1:
        raise ReleaseArchiveError("checksum must contain exactly one entry")
    match = CHECKSUM_LINE.fullmatch(lines[0])
    if not match:
        raise ReleaseArchiveError("checksum must contain one SHA-256 entry")
    return match.group(1), match.group(2)


def verify_checksum(archive, checksum):
    if not archive.is_file():
        raise ReleaseArchiveError(f"release archive is missing: {archive}")
    expected_digest, listed_name = read_checksum(checksum)
    if listed_name != archive.name:
        raise ReleaseArchiveError(
            "checksum archive name does not match the supplied archive: "
            f"{listed_name!r} != {archive.name!r}"
        )
    actual_digest = sha256(archive)
    if actual_digest != expected_digest:
        raise ReleaseArchiveError(
            "release archive checksum mismatch: "
            f"expected {expected_digest}, got {actual_digest}"
        )


def require_commands(commands):
    missing = [command for command in commands if shutil.which(command) is None]
    if missing:
        raise ReleaseArchiveError(
            "release archive verification requires: " + ", ".join(missing)
        )


def run(command, *, env=None, capture_output=False):
    result = subprocess.run(
        [str(item) for item in command],
        text=True,
        capture_output=capture_output,
        env=env,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() if capture_output else ""
        suffix = f": {detail}" if detail else ""
        raise ReleaseArchiveError(
            f"command failed ({result.returncode}): {' '.join(map(str, command))}"
            f"{suffix}"
        )
    return result


def extracted_app(archive, destination):
    run(["ditto", "-x", "-k", archive, destination])
    app = destination / "BuddyMon.app"
    entries = [entry for entry in destination.iterdir() if entry.name != "__MACOSX"]
    if entries != [app] or not app.is_dir():
        names = ", ".join(sorted(entry.name for entry in entries)) or "nothing"
        raise ReleaseArchiveError(
            "release archive must contain exactly BuddyMon.app; found " + names
        )
    return app


def verify_bundle(app, temporary_root):
    info = app / "Contents" / "Info.plist"
    runtime = app / "Contents" / "Resources" / "python"
    python = runtime / "bin" / "python3"
    entrypoint = app / "Contents" / "Resources" / "buddymon" / "buddymon.py"
    for path, label in (
        (info, "Info.plist"),
        (python, "embedded Python"),
        (entrypoint, "embedded BuddyMon entrypoint"),
    ):
        if not path.is_file():
            raise ReleaseArchiveError(f"release app is missing {label}: {path}")

    run(["plutil", "-lint", info])
    run(
        [
            sys.executable,
            ROOT / "scripts" / "validate-release-metadata.py",
            "--require-dated-changelog",
            "--app",
            app,
        ]
    )
    run([sys.executable, ROOT / "scripts" / "verify-python-runtime.py", runtime])
    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", app])
    run(["spctl", "--assess", "--type", "execute", "--verbose=2", app])

    state_home = temporary_root / "state"
    env = {**os.environ, "XDG_STATE_HOME": str(state_home)}
    result = run(
        [python, entrypoint, "app-status"],
        env=env,
        capture_output=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ReleaseArchiveError("embedded app-status did not return JSON") from exc
    if not isinstance(payload, dict):
        raise ReleaseArchiveError("embedded app-status did not return an object")


def verify(archive, checksum):
    archive = Path(archive).resolve()
    checksum = Path(checksum).resolve()
    verify_checksum(archive, checksum)
    require_commands(("ditto", "plutil", "codesign", "spctl"))
    with tempfile.TemporaryDirectory(prefix="buddymon-release-verify-") as raw_root:
        root = Path(raw_root)
        app = extracted_app(archive, root / "archive")
        verify_bundle(app, root)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify the exact signed BuddyMon release archive."
    )
    parser.add_argument("archive", type=Path)
    parser.add_argument("checksum", type=Path)
    args = parser.parse_args(argv)
    try:
        verify(args.archive, args.checksum)
    except ReleaseArchiveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"release archive verified: {args.archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
