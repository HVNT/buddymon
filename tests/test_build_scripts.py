import hashlib
import json
import os
import subprocess
import struct
import tarfile
from pathlib import Path
from typing import Optional

import pytest


ROOT = Path(__file__).resolve().parent.parent
APP_BUILDER = ROOT / "scripts" / "build-macos-app.sh"
RUNTIME_BUILDER = ROOT / "scripts" / "build-python-runtime.sh"


def test_native_app_has_a_packaged_pixel_icon_source():
    source = APP_BUILDER.read_text(encoding="utf-8")
    png = ROOT / "macos" / "BuddyMonApp" / "Resources" / "AppIcon.png"
    icon = ROOT / "macos" / "BuddyMonApp" / "Resources" / "AppIcon.icns"
    trainer = (
        ROOT
        / "macos"
        / "BuddyMonApp"
        / "Resources"
        / "TrainerRedFRLG.png"
    )

    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert icon.read_bytes().startswith(b"icns")
    trainer_bytes = trainer.read_bytes()
    assert trainer_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert struct.unpack(">II", trainer_bytes[16:24]) == (64, 64)
    assert trainer_bytes[25] == 6
    assert hashlib.sha256(trainer_bytes).hexdigest() == (
        "b9455d9dde99f00d1d93430b62ba320284f894fba315d02144c2b5a7163c61b3"
    )
    assert "ICON_SOURCE=" in source
    assert 'cp "${ICON_SOURCE}" "${RESOURCES}/AppIcon.icns"' in source
    assert (
        'cp "${TRAINER_PORTRAIT_SOURCE}" '
        '"${RESOURCES}/TrainerRedFRLG.png"'
    ) in source
    assert "CFBundleIconFile" in source
    assert "--install" in source
    assert 'rsync -a --delete "${APP}/" "${INSTALLED_APP}/"' in source
    assert 'open "${OPEN_TARGET}"' in source


def write_python_stub(path: Path, *, succeeds: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if succeeds:
        script = """#!/bin/sh
if [ -n "${BUDDYMON_RUNTIME_PLATFORM:-}" ]; then
  cat <<'JSON'
{
  "schema_version": 1,
  "managed_by": "buddymon",
  "built_at": "2026-07-13T00:00:00+00:00",
  "platform": "test-apple-darwin",
  "python": "3.12.0",
  "pillow": "12.0.0",
  "source_url": ""
}
JSON
fi
exit 0
"""
    else:
        script = "#!/bin/sh\nexit 1\n"
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def runtime_archive(tmp_path: Path, *, succeeds: bool = True) -> Path:
    fixture_root = tmp_path / ("good-fixture" if succeeds else "bad-fixture")
    write_python_stub(fixture_root / "python" / "bin" / "python3", succeeds=succeeds)
    archive = tmp_path / ("good-runtime.tar.gz" if succeeds else "bad-runtime.tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(fixture_root / "python", arcname="python")
    return archive


def run_builder(
    *args: object, env: Optional[dict] = None
) -> subprocess.CompletedProcess:
    command = ["bash", str(RUNTIME_BUILDER), *(str(arg) for arg in args)]
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def run_script(script: Path, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(script), *(str(arg) for arg in args)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("script", "option", "message"),
    [
        (APP_BUILDER, "--runtime-dir", "requires a directory"),
        (APP_BUILDER, "--python-version", "requires a version"),
        (RUNTIME_BUILDER, "--runtime-dir", "requires a directory"),
        (RUNTIME_BUILDER, "--python-version", "requires a version"),
        (RUNTIME_BUILDER, "--url", "requires a URL"),
        (RUNTIME_BUILDER, "--tarball", "requires a path"),
    ],
)
@pytest.mark.parametrize("equals_form", [False, True])
def test_value_options_reject_missing_or_empty_values(
    script, option, message, equals_form
):
    argument = f"{option}=" if equals_form else option

    result = run_script(script, argument)

    assert result.returncode == 2
    assert message in result.stderr


def test_runtime_builder_creates_marked_runtime_and_replaces_it_with_force(tmp_path):
    archive = runtime_archive(tmp_path)
    runtime = tmp_path / "runtime"

    first = run_builder("--tarball", archive, "--runtime-dir", runtime)

    assert first.returncode == 0, first.stderr
    metadata = json.loads((runtime / "buddymon-runtime.json").read_text())
    assert metadata["managed_by"] == "buddymon"
    assert metadata["schema_version"] == 1

    sentinel = runtime / "old-runtime-sentinel"
    sentinel.write_text("preserve only until replacement", encoding="utf-8")

    replaced = run_builder(
        "--force", "--tarball", archive, "--runtime-dir", runtime
    )

    assert replaced.returncode == 0, replaced.stderr
    assert not sentinel.exists()
    assert (runtime / "bin" / "python3").is_file()


def test_runtime_builder_reuses_valid_unmanaged_runtime_without_modifying_it(tmp_path):
    runtime = tmp_path / "external-runtime"
    write_python_stub(runtime / "bin" / "python3")
    sentinel = runtime / "external-sentinel"
    sentinel.write_text("keep", encoding="utf-8")

    result = run_builder("--runtime-dir", runtime)

    assert result.returncode == 0, result.stderr
    assert "runtime already valid" in result.stdout
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert not (runtime / "buddymon-runtime.json").exists()


@pytest.mark.parametrize("valid_runtime", [False, True])
def test_force_refuses_unmanaged_nonempty_runtime(tmp_path, valid_runtime):
    runtime = tmp_path / "unmanaged-runtime"
    runtime.mkdir()
    sentinel = runtime / "sentinel"
    sentinel.write_text("do not delete", encoding="utf-8")
    if valid_runtime:
        write_python_stub(runtime / "bin" / "python3")

    result = run_builder("--force", "--runtime-dir", runtime)

    assert result.returncode != 0
    assert "refusing to replace an unmanaged runtime directory" in result.stderr
    assert sentinel.read_text(encoding="utf-8") == "do not delete"


def test_failed_staged_build_keeps_existing_managed_runtime(tmp_path):
    good_archive = runtime_archive(tmp_path)
    bad_archive = runtime_archive(tmp_path, succeeds=False)
    runtime = tmp_path / "runtime"
    created = run_builder("--tarball", good_archive, "--runtime-dir", runtime)
    assert created.returncode == 0, created.stderr
    sentinel = runtime / "existing-runtime-sentinel"
    sentinel.write_text("keep", encoding="utf-8")

    failed = run_builder(
        "--force", "--tarball", bad_archive, "--runtime-dir", runtime
    )

    assert failed.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert (runtime / "buddymon-runtime.json").is_file()


def test_force_accepts_legacy_buddymon_runtime_metadata(tmp_path):
    archive = runtime_archive(tmp_path)
    runtime = tmp_path / "legacy-runtime"
    write_python_stub(runtime / "bin" / "python3")
    (runtime / "buddymon-runtime.json").write_text(
        json.dumps({
            "built_at": "2026-07-01T00:00:00+00:00",
            "platform": "aarch64-apple-darwin",
            "python": "3.12.0",
            "pillow": "12.0.0",
            "source_url": "https://example.invalid/runtime.tar.gz",
        }),
        encoding="utf-8",
    )

    result = run_builder(
        "--force", "--tarball", archive, "--runtime-dir", runtime
    )

    assert result.returncode == 0, result.stderr
    metadata = json.loads((runtime / "buddymon-runtime.json").read_text())
    assert metadata["managed_by"] == "buddymon"


def test_force_refuses_symlinked_ownership_marker(tmp_path):
    runtime = tmp_path / "unmanaged-runtime"
    runtime.mkdir()
    sentinel = runtime / "sentinel"
    sentinel.write_text("do not delete", encoding="utf-8")
    external_marker = tmp_path / "external-marker.json"
    external_marker.write_text(
        json.dumps({"managed_by": "buddymon", "schema_version": 1}),
        encoding="utf-8",
    )
    (runtime / "buddymon-runtime.json").symlink_to(external_marker)

    result = run_builder("--force", "--runtime-dir", runtime)

    assert result.returncode != 0
    assert "refusing to replace an unmanaged runtime directory" in result.stderr
    assert sentinel.read_text(encoding="utf-8") == "do not delete"


@pytest.mark.parametrize(
    "destination",
    [Path("/"), ROOT.parent, ROOT, ROOT / ".git"],
)
def test_runtime_builder_rejects_protected_destinations(destination):
    result = run_builder("--runtime-dir", destination)

    assert result.returncode != 0
    assert "refusing unsafe runtime destination" in result.stderr


def test_runtime_builder_rejects_home_destination(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env["HOME"] = str(home)

    result = run_builder("--runtime-dir", home, env=env)

    assert result.returncode != 0
    assert "refusing unsafe runtime destination" in result.stderr


def test_runtime_builder_rejects_symlink_destination(tmp_path):
    real_runtime = tmp_path / "real-runtime"
    real_runtime.mkdir()
    linked_runtime = tmp_path / "linked-runtime"
    linked_runtime.symlink_to(real_runtime, target_is_directory=True)

    result = run_builder("--runtime-dir", linked_runtime)

    assert result.returncode != 0
    assert "refusing symlink runtime destination" in result.stderr


def test_runtime_builder_rejects_explicit_empty_destination():
    result = run_builder("--runtime-dir=")

    assert result.returncode == 2
    assert "--runtime-dir requires a directory" in result.stderr
