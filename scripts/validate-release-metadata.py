#!/usr/bin/env python3
"""Validate BuddyMon's tracked release identity and optional app bundle."""

import argparse
import json
import plistlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+){2}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
PRODUCTION_BUNDLE_ID = "com.hvnt.buddymon"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_version():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError("VERSION must contain a three-part numeric version")

    plugin = load_json(ROOT / ".claude-plugin" / "plugin.json")
    marketplace = load_json(ROOT / ".claude-plugin" / "marketplace.json")
    versions = {
        "VERSION": version,
        "plugin.json": plugin.get("version"),
        "marketplace metadata": marketplace.get("metadata", {}).get("version"),
        "marketplace plugin": marketplace.get("plugins", [{}])[0].get("version"),
    }
    mismatches = {
        source: value for source, value in versions.items() if value != version
    }
    if mismatches:
        detail = ", ".join(f"{source}={value!r}" for source, value in mismatches.items())
        raise ValueError(f"release version mismatch: {detail}")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    release_heading = re.compile(
        rf"^## \[{re.escape(version)}\] - [0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$",
        re.MULTILINE,
    )
    if not release_heading.search(changelog):
        raise ValueError(f"CHANGELOG.md is missing a dated {version} release heading")
    return version


def validate_runtime_lock():
    lock = load_json(ROOT / "scripts" / "runtime-lock.json")
    if lock.get("schema_version") != 1:
        raise ValueError("runtime lock schema_version must be 1")
    python = lock.get("python", {})
    if not VERSION_PATTERN.fullmatch(str(python.get("version", ""))):
        raise ValueError("runtime lock must pin an exact three-part Python version")
    platforms = python.get("platforms")
    if not isinstance(platforms, dict) or not platforms:
        raise ValueError("runtime lock must contain platform entries")
    for name, entry in platforms.items():
        for label, value in (
            ("runtime URL", entry.get("url")),
            ("Pillow URL", entry.get("pillow", {}).get("url")),
        ):
            if not isinstance(value, str) or not value.startswith("https://"):
                raise ValueError(f"{name} for {label} must be HTTPS")
        for label, value in (
            ("runtime", entry.get("sha256")),
            ("Pillow", entry.get("pillow", {}).get("sha256")),
        ):
            if not SHA256_PATTERN.fullmatch(str(value or "")):
                raise ValueError(f"{label} SHA-256 for {name} is invalid")
    return lock


def validate_app(app_path, version, bundle_id, build_number):
    plist_path = app_path / "Contents" / "Info.plist"
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    expected = {
        "CFBundleIdentifier": bundle_id,
        "CFBundleShortVersionString": version,
        "CFBundleVersion": build_number,
    }
    mismatches = {
        key: plist.get(key)
        for key, value in expected.items()
        if plist.get(key) != value
    }
    if mismatches:
        detail = ", ".join(f"{key}={value!r}" for key, value in mismatches.items())
        raise ValueError(f"app metadata mismatch: {detail}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path)
    parser.add_argument("--bundle-id", default=PRODUCTION_BUNDLE_ID)
    parser.add_argument("--build-number")
    args = parser.parse_args()
    version = validate_version()
    validate_runtime_lock()
    if args.app:
        validate_app(
            args.app,
            version,
            args.bundle_id,
            args.build_number or version,
        )
    print(f"release metadata ok: {version}")


if __name__ == "__main__":
    main()
