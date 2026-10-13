"""Release-download verifier tests."""

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
VERIFIER_PATH = ROOT / "scripts" / "verify-release-archive.py"
SPEC = importlib.util.spec_from_file_location("release_archive_verifier", VERIFIER_PATH)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def write_checksum(path, archive_name, payload):
    digest = hashlib.sha256(payload).hexdigest()
    path.write_text(f"{digest}  {archive_name}\n", encoding="utf-8")


def test_release_archive_verifier_accepts_matching_checksum(tmp_path):
    archive = tmp_path / "BuddyMon-macOS-arm64.zip"
    payload = b"release archive"
    archive.write_bytes(payload)
    checksum = tmp_path / "BuddyMon-macOS-arm64.zip.sha256"
    write_checksum(checksum, archive.name, payload)

    verifier.verify_checksum(archive, checksum)


def test_release_archive_verifier_rejects_mismatched_checksum_name(tmp_path):
    archive = tmp_path / "BuddyMon-macOS-arm64.zip"
    archive.write_bytes(b"release archive")
    checksum = tmp_path / "BuddyMon-macOS-arm64.zip.sha256"
    write_checksum(checksum, "other.zip", archive.read_bytes())

    with pytest.raises(verifier.ReleaseArchiveError, match="does not match"):
        verifier.verify_checksum(archive, checksum)


def test_release_archive_verifier_rejects_changed_archive_bytes(tmp_path):
    archive = tmp_path / "BuddyMon-macOS-arm64.zip"
    archive.write_bytes(b"release archive")
    checksum = tmp_path / "BuddyMon-macOS-arm64.zip.sha256"
    write_checksum(checksum, archive.name, archive.read_bytes())
    archive.write_bytes(b"changed archive")

    with pytest.raises(verifier.ReleaseArchiveError, match="checksum mismatch"):
        verifier.verify_checksum(archive, checksum)


def test_release_archive_verifier_requires_archive_and_checksum_arguments():
    result = subprocess.run(
        [sys.executable, str(VERIFIER_PATH)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "archive" in result.stderr
    assert "checksum" in result.stderr


def test_release_archive_verifier_checks_downloaded_bundle_integrity():
    source = VERIFIER_PATH.read_text(encoding="utf-8")

    for token in (
        '"ditto", "-x", "-k"',
        '"plutil", "-lint"',
        "validate-release-metadata.py",
        "verify-python-runtime.py",
        '"codesign", "--verify", "--deep", "--strict"',
        '"spctl", "--assess", "--type", "execute"',
        '"app-status"',
    ):
        assert token in source
    assert '"--require-dated-changelog"' in source


@pytest.mark.parametrize("valid_shortcut", [True, False])
def test_dmg_layout_is_checked_and_always_detached(tmp_path, monkeypatch, valid_shortcut):
    calls = []
    def run(command, **_):
        calls.append(command)
        if command[:2] == ["hdiutil", "attach"]:
            mount = Path(command[-2])
            runtime = mount / "BuddyMon.app/Contents/Resources/python/arm64/bin/python3"
            runtime.parent.mkdir(parents=True)
            runtime.touch()
            (mount / "Applications").symlink_to("/Applications" if valid_shortcut else "/tmp")
    monkeypatch.setattr(verifier, "run", run)
    if valid_shortcut:
        with verifier.mounted_disk_image(tmp_path / "test.dmg", tmp_path / "mount") as app:
            assert app.name == "BuddyMon.app"
    else:
        with pytest.raises(verifier.ReleaseArchiveError, match="Applications shortcut"):
            with verifier.mounted_disk_image(tmp_path / "test.dmg", tmp_path / "mount"):
                pytest.fail("invalid shortcut accepted")
    assert calls[-1][:2] == ["hdiutil", "detach"]
