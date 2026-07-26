#!/usr/bin/env python3
"""Verify that a managed Python runtime matches BuddyMon's lock."""

import argparse
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime", type=Path)
    args = parser.parse_args()

    lock = json.loads(
        (ROOT / "scripts" / "runtime-lock.json").read_text(encoding="utf-8")
    )
    metadata = json.loads(
        (args.runtime / "buddymon-runtime.json").read_text(encoding="utf-8")
    )
    platform = metadata.get("platform")
    entry = lock["python"]["platforms"].get(platform)
    if not entry:
        raise SystemExit(f"runtime platform is not locked: {platform}")

    expected = {
        "managed_by": "buddymon",
        "schema_version": 1,
        "python": lock["python"]["version"],
        "pillow": entry["pillow"]["version"],
        "source_url": entry["url"],
        "source_sha256": entry["sha256"],
        "pillow_url": entry["pillow"]["url"],
        "pillow_sha256": entry["pillow"]["sha256"],
    }
    mismatches = {
        key: (metadata.get(key), value)
        for key, value in expected.items()
        if metadata.get(key) != value
    }
    if mismatches:
        detail = ", ".join(
            f"{key}={actual!r} expected {wanted!r}"
            for key, (actual, wanted) in mismatches.items()
        )
        raise SystemExit(f"runtime metadata does not match lock: {detail}")

    python = args.runtime / "bin" / "python3"
    if not python.is_file():
        raise SystemExit("runtime is missing bin/python3")
    probe = subprocess.run(
        [
            str(python),
            "-c",
            "import PIL, platform; print(platform.python_version()); print(PIL.__version__)",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if probe.returncode != 0:
        raise SystemExit(probe.stderr.strip() or "runtime import probe failed")
    actual_python, actual_pillow = probe.stdout.splitlines()
    if actual_python != expected["python"] or actual_pillow != expected["pillow"]:
        raise SystemExit(
            "runtime imports do not match metadata: "
            f"Python {actual_python}, Pillow {actual_pillow}"
        )
    print(f"runtime lock ok: {platform}")


if __name__ == "__main__":
    main()
