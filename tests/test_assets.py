"""Optional art-pack lifecycle tests; all installers are local fakes."""

import base64
import hashlib
import json
import os
import runpy
import struct
import subprocess
import sys
import threading
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import app_bridge, assets, paths


def use_temp_state(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setattr(paths, "STATE_DIR", state_dir)
    return state_dir


def write_pack(root, kind, payload):
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{kind}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def expect_species(monkeypatch, kind, *names):
    monkeypatch.setitem(assets.PACK_SPECIES, kind, tuple(names))


def species_pack(name, version):
    return {name: {"version": version}}


def png_chunk(kind, data):
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", checksum)
    )


def trainer_png(width=64, height=64):
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    pixels = b"".join(b"\x00" + (b"\x00" * width) for _ in range(height))
    return (
        assets.PNG_SIGNATURE
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(pixels))
        + png_chunk(b"IEND", b"")
    )


@pytest.mark.parametrize(
    ("portrait", "message"),
    [
        (b"not-a-png", "not a PNG"),
        (trainer_png(width=63), "must be 64x64"),
    ],
)
def test_trainer_portrait_validation_rejects_invalid_image(portrait, message):
    with pytest.raises(ValueError, match=message):
        assets.validate_trainer_portrait(portrait)


def test_install_missing_skips_existing_pack(tmp_path, monkeypatch):
    state_dir = use_temp_state(monkeypatch, tmp_path)
    current = write_pack(state_dir / "packs", "gen2", {"version": "current"})
    calls = []
    monkeypatch.setattr(assets, "ASSET_INSTALLERS", {
        "gen2": lambda destination: calls.append(destination),
    })

    result = assets.install(operation=assets.INSTALL_MISSING, kinds=["gen2"])

    assert result["operation"] == "install_missing"
    assert result["ok"] is True
    assert result["results"] == [{
        "kind": "gen2",
        "status": "skipped",
        "path": str(current),
        "message": "already installed",
    }]
    assert calls == []


def test_install_missing_promotes_valid_staged_pack(tmp_path, monkeypatch):
    state_dir = use_temp_state(monkeypatch, tmp_path)
    expect_species(monkeypatch, "gen2", "Pikachu")

    def install_gen2(destination):
        assert destination.parent == state_dir / "packs"
        write_pack(destination, "gen2", species_pack("Pikachu", "new"))
        print("installed test pack")

    monkeypatch.setattr(assets, "ASSET_INSTALLERS", {"gen2": install_gen2})

    result = app_bridge.install_assets(kinds=["gen2"])

    installed = state_dir / "packs" / "gen2.json"
    assert json.loads(installed.read_text(encoding="utf-8")) == species_pack(
        "Pikachu", "new"
    )
    assert result["operation"] == "install_missing"
    assert result["ok"] is True
    assert result["results"][0]["status"] == "installed"
    assert result["results"][0]["path"] == str(installed)
    assert "installed test pack" in result["results"][0]["output"]
    assert result["packs"]["gen2"]["installed"] is True


def test_refresh_replaces_existing_pack(tmp_path, monkeypatch):
    state_dir = use_temp_state(monkeypatch, tmp_path)
    expect_species(monkeypatch, "box", "Pikachu")
    live_root = state_dir / "packs"
    current = write_pack(live_root, "box", species_pack("Pikachu", "old"))

    def refresh_box(destination):
        write_pack(destination, "box", species_pack("Pikachu", "new"))

    monkeypatch.setattr(assets, "ASSET_INSTALLERS", {"box": refresh_box})

    result = assets.install(operation=assets.REFRESH, kinds=["box"])

    assert result["operation"] == "refresh"
    assert result["ok"] is True
    assert result["results"][0]["status"] == "refreshed"
    assert json.loads(current.read_text(encoding="utf-8")) == species_pack(
        "Pikachu", "new"
    )


def test_trainer_pack_promotes_and_exposes_valid_portrait(tmp_path, monkeypatch):
    state_dir = use_temp_state(monkeypatch, tmp_path)
    portrait = trainer_png()
    encoded = base64.b64encode(portrait).decode("ascii")

    def install_trainer(destination):
        write_pack(
            destination,
            "trainer",
            {"red": {"portrait_base64": encoded}},
        )

    monkeypatch.setattr(
        assets,
        "ASSET_INSTALLERS",
        {"trainer": install_trainer},
    )

    result = assets.install(
        operation=assets.INSTALL_MISSING,
        kinds=["trainer"],
    )

    assert result["ok"] is True
    assert result["results"][0]["status"] == "installed"
    assert assets.trainer_portrait_base64() == encoded
    assert state_dir.joinpath("packs", "trainer.json").is_file()


def test_invalid_trainer_pack_is_rejected_without_breaking_fallback(
    tmp_path, monkeypatch,
):
    state_dir = use_temp_state(monkeypatch, tmp_path)
    write_pack(
        state_dir / "packs",
        "trainer",
        {"red": {"portrait_base64": "not-base64"}},
    )

    def install_invalid_trainer(destination):
        write_pack(
            destination,
            "trainer",
            {"red": {"portrait_base64": "still-not-base64"}},
        )

    monkeypatch.setattr(
        assets,
        "ASSET_INSTALLERS",
        {"trainer": install_invalid_trainer},
    )

    result = assets.install(
        operation=assets.INSTALL_MISSING,
        kinds=["trainer"],
    )

    assert result["ok"] is False
    assert "trainer pack is invalid" in result["results"][0]["message"]
    assert result["packs"]["trainer"]["installed"] is False
    assert assets.trainer_portrait_base64() is None


def test_failed_refresh_preserves_last_good_pack(tmp_path, monkeypatch):
    state_dir = use_temp_state(monkeypatch, tmp_path)
    live_root = state_dir / "packs"
    current = write_pack(live_root, "gen2", {"version": "old"})

    def write_invalid_pack(destination):
        write_pack(destination, "gen2", {})
        print("incomplete download")

    monkeypatch.setattr(assets, "ASSET_INSTALLERS", {"gen2": write_invalid_pack})

    result = assets.install(operation=assets.REFRESH, kinds=["gen2"])

    assert result["ok"] is False
    assert result["results"][0]["status"] == "failed"
    assert "empty or invalid" in result["results"][0]["message"]
    assert "incomplete download" in result["results"][0]["output"]
    assert json.loads(current.read_text(encoding="utf-8")) == {"version": "old"}
    assert not list(live_root.glob(".gen2-*"))


def test_success_without_expected_pack_is_structured_failure(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)
    monkeypatch.setattr(assets, "ASSET_INSTALLERS", {
        "gen2": lambda _destination: None,
    })

    result = assets.install(operation=assets.INSTALL_MISSING, kinds=["gen2"])

    assert result["ok"] is False
    assert result["results"][0]["status"] == "failed"
    assert result["results"][0]["message"] == "installer did not create the gen2 pack"


def test_installer_exit_is_returned_as_structured_failure(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)

    def fail(_destination):
        raise SystemExit("network setup failed")

    monkeypatch.setattr(assets, "ASSET_INSTALLERS", {"gen2": fail})

    result = assets.install(operation=assets.INSTALL_MISSING, kinds=["gen2"])

    assert result["ok"] is False
    assert result["results"][0]["status"] == "failed"
    assert result["results"][0]["message"] == "network setup failed"


def test_promotion_failure_restores_last_good_pack(tmp_path, monkeypatch):
    state_dir = use_temp_state(monkeypatch, tmp_path)
    expect_species(monkeypatch, "box", "Pikachu")
    live_root = state_dir / "packs"
    current = write_pack(live_root, "box", species_pack("Pikachu", "old"))

    def refresh_box(destination):
        write_pack(destination, "box", species_pack("Pikachu", "new"))

    real_replace = os.replace

    def fail_promotion(source, destination):
        source = Path(source)
        destination = Path(destination)
        if source.name == "box.json" and source.parent.name.startswith(".box-"):
            raise OSError("promotion failed")
        return real_replace(source, destination)

    monkeypatch.setattr(assets, "ASSET_INSTALLERS", {"box": refresh_box})
    monkeypatch.setattr(assets.os, "replace", fail_promotion)

    result = assets.install(operation=assets.REFRESH, kinds=["box"])

    assert result["ok"] is False
    assert result["results"][0]["message"] == "promotion failed"
    assert json.loads(current.read_text(encoding="utf-8")) == species_pack(
        "Pikachu", "old"
    )


def test_rollback_failure_preserves_recovery_backup(tmp_path, monkeypatch):
    state_dir = use_temp_state(monkeypatch, tmp_path)
    expect_species(monkeypatch, "box", "Pikachu")
    live_root = state_dir / "packs"
    write_pack(live_root, "box", species_pack("Pikachu", "old"))

    def refresh_box(destination):
        write_pack(destination, "box", species_pack("Pikachu", "new"))

    real_replace = os.replace

    def fail_promotion_and_restore(source, destination):
        source = Path(source)
        if source.parent.name == ".previous":
            raise OSError("restore failed")
        if source.name == "box.json" and source.parent.name.startswith(".box-"):
            raise OSError("promotion failed")
        return real_replace(source, destination)

    monkeypatch.setattr(assets, "ASSET_INSTALLERS", {"box": refresh_box})
    monkeypatch.setattr(assets.os, "replace", fail_promotion_and_restore)

    result = assets.install(operation=assets.REFRESH, kinds=["box"])

    entry = result["results"][0]
    recovery = Path(entry["recovery_path"])
    assert result["ok"] is False
    assert "restore failed" in entry["message"]
    assert recovery.is_dir()
    assert json.loads(
        (recovery / "box.json").read_text(encoding="utf-8")
    ) == species_pack("Pikachu", "old")
    assert recovery.parent.exists()


def test_refresh_promotes_split_gen5_and_retires_legacy_pack(tmp_path, monkeypatch):
    state_dir = use_temp_state(monkeypatch, tmp_path)
    expect_species(monkeypatch, "gen5", "Pikachu")
    live_root = state_dir / "packs"
    old_split = live_root / "gen5"
    write_pack(old_split, "old", {"frames": ["old"]})
    legacy = write_pack(live_root, "gen5", {"Legacy": {"frames": ["old"]}})

    def refresh_gen5(destination):
        write_pack(destination / "gen5", "pikachu", {"frames": ["new"]})

    monkeypatch.setattr(assets, "ASSET_INSTALLERS", {"gen5": refresh_gen5})

    result = assets.install(operation=assets.REFRESH, kinds=["gen5"])

    refreshed = live_root / "gen5" / "pikachu.json"
    assert result["ok"] is True
    assert result["results"][0]["path"] == str(live_root / "gen5")
    assert json.loads(refreshed.read_text(encoding="utf-8")) == {"frames": ["new"]}
    assert not (live_root / "gen5" / "old.json").exists()
    assert not legacy.exists()


def test_missing_species_rejects_refresh_and_preserves_last_good_pack(
    tmp_path, monkeypatch,
):
    state_dir = use_temp_state(monkeypatch, tmp_path)
    expect_species(monkeypatch, "box", "Bulbasaur", "Ivysaur")
    live_root = state_dir / "packs"
    previous = {
        "Bulbasaur": {"version": "old"},
        "Ivysaur": {"version": "old"},
    }
    current = write_pack(live_root, "box", previous)

    def incomplete_refresh(destination):
        write_pack(
            destination,
            "box",
            {"Bulbasaur": {"version": "new"}},
        )

    monkeypatch.setattr(assets, "ASSET_INSTALLERS", {
        "box": incomplete_refresh,
    })

    result = assets.install(operation=assets.REFRESH, kinds=["box"])

    assert result["ok"] is False
    assert "missing 1 (Ivysaur)" in result["results"][0]["message"]
    assert json.loads(current.read_text(encoding="utf-8")) == previous


def test_concurrent_install_missing_promotes_once(tmp_path, monkeypatch):
    state_dir = use_temp_state(monkeypatch, tmp_path)
    expect_species(monkeypatch, "gen2", "Pikachu")
    installers_ready = threading.Barrier(2)
    calls = []

    def install_gen2(destination):
        calls.append(destination)
        write_pack(destination, "gen2", species_pack("Pikachu", destination.name))
        installers_ready.wait(timeout=5)

    monkeypatch.setattr(assets, "ASSET_INSTALLERS", {"gen2": install_gen2})
    results = []

    def install():
        results.append(
            assets.install(
                operation=assets.INSTALL_MISSING,
                kinds=["gen2"],
            )
        )

    threads = [threading.Thread(target=install) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert len(calls) == 2
    assert sorted(result["results"][0]["status"] for result in results) == [
        "installed",
        "skipped",
    ]
    installed = json.loads(
        (state_dir / "packs" / "gen2.json").read_text(encoding="utf-8")
    )
    assert set(installed) == {"Pikachu"}


def test_unknown_operation_is_rejected(tmp_path, monkeypatch):
    use_temp_state(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="unknown asset operation"):
        assets.install(operation="surprise", kinds=["gen2"])


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["--json"], assets.INSTALL_MISSING),
        (["--json", "--refresh"], assets.REFRESH),
        (["--json", "--force"], assets.REFRESH),
    ],
)
def test_cli_preserves_force_as_refresh_alias(monkeypatch, arguments, expected):
    import buddymon

    calls = []

    def fake_install(kinds=None, operation=None):
        calls.append((kinds, operation))
        return {"operation": operation, "ok": True, "results": [], "packs": {}}

    monkeypatch.setattr(app_bridge, "install_assets", fake_install)

    command = buddymon.install_assets(arguments)
    result = json.loads(command.text)

    assert result["operation"] == expected
    assert command.exit_code == 0
    assert calls == [(None, expected)]


def test_asset_cli_json_failure_is_json_and_exits_one():
    script = Path(__file__).resolve().parent.parent / "buddymon.py"
    result = subprocess.run(
        [sys.executable, str(script), "install-assets", "--json", "--only=wat"],
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["error"] == "unknown asset pack: wat"


@pytest.mark.parametrize("flag", ["--wat", "--only="])
def test_asset_cli_rejects_invalid_usage_as_json(flag):
    script = Path(__file__).resolve().parent.parent / "buddymon.py"
    result = subprocess.run(
        [sys.executable, str(script), "install-assets", "--json", flag],
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["operation"] == "install_missing"
    assert payload["ok"] is False
    assert payload["results"] == []
    assert payload["error"]


def test_asset_cli_plain_failure_includes_actual_error():
    script = Path(__file__).resolve().parent.parent / "buddymon.py"
    result = subprocess.run(
        [sys.executable, str(script), "install-assets", "--only=wat"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "asset install failed: unknown asset pack: wat" in result.stdout


@pytest.mark.parametrize(
    ("tool", "kind"),
    [
        ("fetch_official.py", "gen2"),
        ("fetch_box.py", "box"),
        ("fetch_gen5.py", "gen5"),
        ("fetch_trainer.py", "trainer"),
    ],
)
def test_direct_asset_tools_use_staged_lifecycle(monkeypatch, tool, kind):
    calls = []
    monkeypatch.setattr(
        assets,
        "installer_cli",
        lambda selected: calls.append(selected) or 7,
    )
    script = Path(__file__).resolve().parent.parent / "tools" / tool

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(script), run_name="__main__")

    assert exc.value.code == 7
    assert calls == [kind]


def test_trainer_installer_writes_pinned_local_pack(tmp_path, monkeypatch):
    from tools import fetch_trainer

    portrait = trainer_png()
    digest = hashlib.sha256(portrait).hexdigest()
    monkeypatch.setattr(fetch_trainer, "TRAINER_SHA256", digest)
    monkeypatch.setattr(fetch_trainer, "fetch", lambda _url: portrait)

    fetch_trainer.main(pack_root=tmp_path)

    pack = json.loads(
        (tmp_path / "trainer.json").read_text(encoding="utf-8")
    )
    entry = pack["red"]
    assert base64.b64decode(entry["portrait_base64"]) == portrait
    assert entry["source_url"] == fetch_trainer.TRAINER_SOURCE
    assert entry["source_commit"] == fetch_trainer.TRAINER_SOURCE_COMMIT
    assert entry["sha256"] == digest


def test_trainer_installer_rejects_unexpected_source_bytes(
    tmp_path, monkeypatch,
):
    from tools import fetch_trainer

    monkeypatch.setattr(fetch_trainer, "fetch", lambda _url: trainer_png())
    monkeypatch.setattr(fetch_trainer, "TRAINER_SHA256", "0" * 64)

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        fetch_trainer.main(pack_root=tmp_path)

    assert not (tmp_path / "trainer.json").exists()


def test_box_installer_fails_on_required_regular_species(tmp_path, monkeypatch):
    from tools import fetch_box

    def fail_fetch(_url):
        raise OSError("regular missing")

    monkeypatch.setattr(fetch_box.species, "ALL_SPECIES", ("Pikachu",))
    monkeypatch.setattr(fetch_box, "fetch", fail_fetch)

    with pytest.raises(RuntimeError, match="missing regular sprite for Pikachu"):
        fetch_box.main(pack_root=tmp_path)

    assert not (tmp_path / "box.json").exists()


def test_gen5_installer_fails_on_required_regular_species(tmp_path, monkeypatch):
    from tools import fetch_gen5

    def fail_fetch(_url):
        raise OSError("regular missing")

    monkeypatch.setattr(fetch_gen5, "MAX_DEX", 1)
    monkeypatch.setattr(fetch_gen5, "dex_names", lambda: {1: "Pikachu"})
    monkeypatch.setattr(fetch_gen5, "fetch", fail_fetch)

    with pytest.raises(RuntimeError, match="missing regular sprite for #1 Pikachu"):
        fetch_gen5.main(pack_root=tmp_path)

    assert not list((tmp_path / "gen5").glob("*.json"))
