import hashlib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Optional

import pytest


ROOT = Path(__file__).resolve().parent.parent
APP_BUILDER = ROOT / "scripts" / "build-macos-app.sh"
RUNTIME_BUILDER = ROOT / "scripts" / "build-python-runtime.sh"
RELEASE_VALIDATOR = ROOT / "scripts" / "validate-release-metadata.py"
RELEASE_PACKAGER = ROOT / "scripts" / "package-macos-release.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_native_app_packages_project_icon_without_external_trainer_art():
    source = APP_BUILDER.read_text(encoding="utf-8")
    png = ROOT / "macos" / "BuddyMonApp" / "Resources" / "AppIcon.png"
    icon = ROOT / "macos" / "BuddyMonApp" / "Resources" / "AppIcon.icns"
    removed_trainer = (
        ROOT
        / "macos"
        / "BuddyMonApp"
        / "Resources"
        / "TrainerRedFRLG.png"
    )

    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert icon.read_bytes().startswith(b"icns")
    assert not removed_trainer.exists()
    assert "ICON_SOURCE=" in source
    assert 'cp "${ICON_SOURCE}" "${RESOURCES}/AppIcon.icns"' in source
    assert "TRAINER_PORTRAIT_SOURCE" not in source
    assert "TrainerRedFRLG.png" not in source
    assert "CFBundleIconFile" in source


def test_native_app_install_stops_and_reopens_the_installed_copy():
    source = APP_BUILDER.read_text(encoding="utf-8")

    assert "--install" in source
    assert "stop_running_buddymon" in source
    assert "pgrep -f '/BuddyMon[.]app/Contents/MacOS/BuddyMon$'" in source
    assert 'kill -TERM "${running[@]}"' in source
    assert 'kill -0 "${pid}"' in source
    assert "running BuddyMon did not quit" in source
    assert 'rsync -a --delete "${APP}/" "${INSTALLED_APP}/"' in source
    assert 'open -n "${OPEN_TARGET}"' in source
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
    arguments = [str(arg) for arg in args]
    if "--tarball" in arguments and "--sha256" not in arguments:
        archive = Path(arguments[arguments.index("--tarball") + 1])
        arguments.extend(["--sha256", hashlib.sha256(archive.read_bytes()).hexdigest()])
    command = ["bash", str(RUNTIME_BUILDER), *arguments]
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def run_script(
    script: Path,
    *args: object,
    env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(script), *(str(arg) for arg in args)],
        cwd=ROOT,
        env=env,
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
        (RUNTIME_BUILDER, "--sha256", "requires a hash"),
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


def test_runtime_builder_rejects_a_tarball_with_the_wrong_digest(tmp_path):
    archive = runtime_archive(tmp_path)
    runtime = tmp_path / "runtime"

    result = run_builder(
        "--tarball",
        archive,
        "--sha256",
        "0" * 64,
        "--runtime-dir",
        runtime,
    )

    assert result.returncode != 0
    assert "SHA-256 mismatch" in result.stderr
    assert not runtime.exists()


def test_runtime_builder_refuses_unlocked_unmanaged_runtime(tmp_path):
    runtime = tmp_path / "external-runtime"
    write_python_stub(runtime / "bin" / "python3")
    sentinel = runtime / "external-sentinel"
    sentinel.write_text("keep", encoding="utf-8")

    result = run_builder("--runtime-dir", runtime)

    assert result.returncode != 0
    assert "refusing to replace an unmanaged runtime directory" in result.stderr
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


def test_runtime_builder_uses_only_locked_downloads_and_hashes():
    source = RUNTIME_BUILDER.read_text(encoding="utf-8")
    lock = json.loads(
        (ROOT / "scripts" / "runtime-lock.json").read_text(encoding="utf-8")
    )

    assert "releases/latest" not in source
    assert "runtime-lock.json" in source
    assert "--require-hashes" in source
    assert "SOURCE_SHA256" in source
    assert set(lock["python"]["platforms"]) == {
        "aarch64-apple-darwin",
        "x86_64-apple-darwin",
    }
    assert 'scripts/verify-python-runtime.py" "${RUNTIME_DIR}"' in source


def test_app_builder_requires_explicit_escape_hatch_for_external_runtime(tmp_path):
    runtime = tmp_path / "external-runtime"
    write_python_stub(runtime / "bin" / "python3")

    result = run_script(
        APP_BUILDER,
        "--friend",
        "--no-bootstrap-runtime",
        "--runtime-dir",
        runtime,
    )

    assert result.returncode != 0
    assert "--allow-unlocked-runtime" in result.stderr
    assert "--allow-unlocked-runtime" in APP_BUILDER.read_text(encoding="utf-8")


def test_release_metadata_is_consistent():
    result = subprocess.run(
        [sys.executable, str(RELEASE_VALIDATOR)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "release metadata ok: 0.2.0" in result.stdout


def test_release_packager_requires_explicit_signing_configuration():
    result = run_script(RELEASE_PACKAGER)

    assert result.returncode == 2
    assert "BUDDYMON_CODESIGN_IDENTITY is required" in result.stderr


def test_release_packager_rejects_bundle_metadata_overrides():
    env = os.environ.copy()
    env.update({
        "BUDDYMON_BUNDLE_ID": "com.example.wrong",
        "BUDDYMON_CODESIGN_IDENTITY": "unused",
        "BUDDYMON_NOTARY_PROFILE": "unused",
    })

    result = run_script(RELEASE_PACKAGER, env=env)

    assert result.returncode == 2
    assert "metadata overrides are not allowed" in result.stderr


def test_release_packager_signs_notarizes_and_checksums_the_exact_app():
    source = RELEASE_PACKAGER.read_text(encoding="utf-8")

    for token in [
        "scripts/verify-python-runtime.py",
        "codesign --verify --deep --strict",
        "xcrun notarytool submit",
        "xcrun stapler staple",
        "spctl --assess",
        "shasum -a 256",
    ]:
        assert token in source
    assert 'PRODUCTION_BUNDLE_ID="com.hvnt.buddymon"' in source
    assert 'BUDDYMON_BUNDLE_ID="${PRODUCTION_BUNDLE_ID}"' in source
    assert source.count("scripts/validate-release-metadata.py") >= 2
    assert 'cd "${OUTPUT_DIR}"' in source
    assert (
        'shasum -a 256 "${ARCHIVE_NAME}" > "${ARCHIVE_NAME}.sha256"'
        in source
    )
    assert 'shasum -a 256 "${ARCHIVE}"' not in source


def test_ci_uses_immutable_actions_and_runs_the_release_gate():
    source = CI_WORKFLOW.read_text(encoding="utf-8")
    requirements = (ROOT / "requirements-test.txt").read_text(encoding="utf-8")

    assert "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683" in source
    assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" in source
    assert 'python-version: "3.12.13"' in source
    assert "Pillow==12.3.0" in requirements
    assert "python3 -m pytest tests/ -q" in source
    assert "scripts/validate-release-metadata.py" in source
    assert "scripts/build-macos-app.sh" in source
    assert "scripts/build-python-runtime.sh --runtime-dir .build/ci-python-runtime" in source
    assert "scripts/verify-python-runtime.py .build/ci-python-runtime" in source
    assert 'git diff --check "${BASE_SHA}...${HEAD_SHA}"' in source
    assert "fetch-depth: 0" in source
