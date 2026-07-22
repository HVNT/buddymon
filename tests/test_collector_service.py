"""Scheduled collection and generated LaunchAgent tests."""

import os
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import collector_service, engine, paths, state


class LaunchctlStub:
    def __init__(self, *, bootstrap_failures=0, bootout_failures=()):
        self.calls = []
        self.loaded = set()
        self.bootstrap_failures = bootstrap_failures
        self.bootout_failures = set(bootout_failures)

    def __call__(self, args, **_kwargs):
        self.calls.append(args)
        action = args[1]
        if action == "bootstrap":
            if self.bootstrap_failures:
                self.bootstrap_failures -= 1
                return subprocess.CompletedProcess(
                    args, 5, stdout="", stderr="bootstrap failed"
                )
            payload = plistlib.loads(Path(args[3]).read_bytes())
            self.loaded.add(payload["Label"])
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        label = args[2].rsplit("/", 1)[-1]
        if action == "bootout":
            if label in self.bootout_failures:
                return subprocess.CompletedProcess(
                    args, 5, stdout="", stderr="bootout failed"
                )
            existed = label in self.loaded
            self.loaded.discard(label)
            return subprocess.CompletedProcess(
                args, 0 if existed else 3, stdout="", stderr=""
            )
        if action == "print":
            return subprocess.CompletedProcess(
                args, 0 if label in self.loaded else 3, stdout="", stderr=""
            )
        raise AssertionError(args)


def _state_with_buddy():
    game_state = state.default_state()
    engine.create_starter(game_state, "Pikachu")
    return game_state


def _install_paths(tmp_path, name):
    executable = tmp_path / name / "bin" / "python3"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    script = tmp_path / name / "buddymon.py"
    script.write_text("# BuddyMon\n", encoding="utf-8")
    return executable, script


def _write_label_plist(path, label):
    path.parent.mkdir(parents=True, exist_ok=True)
    contents = plistlib.dumps({"Label": label})
    path.write_bytes(contents)
    return contents


def test_scheduled_gate_is_due_then_waits_for_interval():
    game_state = _state_with_buddy()

    assert collector_service.collection_due(game_state, now=1_000)
    collector_service.mark_collection(game_state, now=1_000)
    assert not collector_service.collection_due(game_state, now=1_299)
    assert collector_service.collection_due(game_state, now=1_300)


def test_scheduled_gate_recovers_from_invalid_or_future_timestamp():
    game_state = _state_with_buddy()
    game_state["collectors"] = {collector_service.SCHEDULED_AT_KEY: "bad"}
    assert collector_service.collection_due(game_state, now=1_000)

    game_state["collectors"][collector_service.SCHEDULED_AT_KEY] = 2_000
    assert collector_service.collection_due(game_state, now=1_000)


def test_generated_plist_uses_resolved_paths_and_scheduled_contract(tmp_path):
    executable = tmp_path / "runtime" / "python3"
    script = tmp_path / "repo" / "buddymon.py"
    payload = plistlib.loads(
        collector_service.plist_bytes(executable=executable, script=script)
    )

    assert payload["Label"] == collector_service.SERVICE_LABEL
    assert payload["ProgramArguments"] == [
        str(executable.absolute()),
        str(script.resolve()),
        "collect",
        "--scheduled",
    ]
    assert payload["StartInterval"] == collector_service.COLLECT_INTERVAL_SECONDS
    assert payload["RunAtLoad"] is True
    assert "/Users/hunt/" not in collector_service.plist_bytes(
        executable=executable, script=script
    ).decode()


def test_generated_plist_preserves_active_python_symlink(tmp_path):
    target = tmp_path / "python3.12"
    target.write_text("#!/bin/sh\n", encoding="utf-8")
    target.chmod(0o755)
    executable = tmp_path / "venv" / "bin" / "python3"
    executable.parent.mkdir(parents=True)
    executable.symlink_to(target)
    script = tmp_path / "repo" / "buddymon.py"

    payload = collector_service.plist_payload(
        executable=executable,
        script=script,
    )

    assert payload["ProgramArguments"][0] == str(executable.absolute())


def test_generated_plist_preserves_custom_state_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    payload = collector_service.plist_payload(
        executable=tmp_path / "python3",
        script=tmp_path / "buddymon.py",
    )

    assert payload["EnvironmentVariables"] == {
        "XDG_STATE_HOME": str(tmp_path / "state")
    }


def test_install_status_and_uninstall_use_injected_launchctl(tmp_path):
    runner = LaunchctlStub()
    executable, script = _install_paths(tmp_path, "current")

    installed = collector_service.install_service(
        home=tmp_path,
        executable=executable,
        script=script,
        run_command=runner,
        uid=501,
    )

    assert installed["installed"]
    assert installed["loaded"]
    assert installed["path_matches"]
    assert collector_service.service_path(tmp_path).is_file()
    assert any(call[1] == "bootstrap" for call in runner.calls)

    result = collector_service.uninstall_service(
        home=tmp_path, run_command=runner, uid=501
    )
    assert str(collector_service.service_path(tmp_path)) in result["removed"]
    assert not collector_service.service_path(tmp_path).exists()
    assert collector_service.SERVICE_LABEL not in runner.loaded


def test_install_migrates_legacy_service_after_new_service_starts(tmp_path):
    runner = LaunchctlStub()
    legacy = collector_service.legacy_service_path(tmp_path)
    legacy.parent.mkdir(parents=True)
    legacy.write_text("legacy", encoding="utf-8")
    runner.loaded.add(collector_service.LEGACY_SERVICE_LABEL)
    executable, script = _install_paths(tmp_path, "current")

    status = collector_service.install_service(
        home=tmp_path,
        executable=executable,
        script=script,
        run_command=runner,
        uid=501,
    )

    assert status["loaded"]
    assert not status["legacy_present"]
    assert not legacy.exists()
    assert collector_service.LEGACY_SERVICE_LABEL not in runner.loaded


def test_status_detects_path_drift_and_legacy_service(tmp_path):
    runner = LaunchctlStub()
    old_python, old_script = _install_paths(tmp_path, "old")
    collector_service.install_service(
        home=tmp_path,
        executable=old_python,
        script=old_script,
        run_command=runner,
        uid=501,
    )
    legacy = collector_service.legacy_service_path(tmp_path)
    legacy.write_text("legacy", encoding="utf-8")

    status = collector_service.service_status(
        home=tmp_path,
        executable=tmp_path / "new" / "python3",
        script=tmp_path / "new" / "buddymon.py",
        run_command=runner,
        uid=501,
    )

    assert status["installed"]
    assert not status["path_matches"]
    assert status["legacy_present"]
    assert "stale runtime paths" in collector_service.format_status(status)


def test_install_rejects_missing_paths_before_writing_or_launchctl(tmp_path):
    runner = LaunchctlStub()

    with pytest.raises(
        collector_service.CollectorServiceError,
        match="Python executable is missing",
    ):
        collector_service.install_service(
            home=tmp_path,
            executable=tmp_path / "missing" / "python3",
            script=tmp_path / "missing" / "buddymon.py",
            run_command=runner,
            uid=501,
        )

    assert runner.calls == []
    assert not collector_service.service_path(tmp_path).exists()


def test_install_rejects_non_executable_python_and_missing_script(tmp_path):
    runner = LaunchctlStub()
    executable, script = _install_paths(tmp_path, "current")
    executable.chmod(0o644)

    with pytest.raises(
        collector_service.CollectorServiceError,
        match="not executable",
    ):
        collector_service.install_service(
            home=tmp_path,
            executable=executable,
            script=script,
            run_command=runner,
            uid=501,
        )

    executable.chmod(0o755)
    script.unlink()
    with pytest.raises(
        collector_service.CollectorServiceError,
        match="entrypoint is missing",
    ):
        collector_service.install_service(
            home=tmp_path,
            executable=executable,
            script=script,
            run_command=runner,
            uid=501,
        )

    assert runner.calls == []
    assert not collector_service.service_path(tmp_path).exists()


def test_install_failure_restores_prior_plist_and_loaded_service(tmp_path):
    runner = LaunchctlStub(bootstrap_failures=1)
    old_python, old_script = _install_paths(tmp_path, "old")
    new_python, new_script = _install_paths(tmp_path, "new")
    path = collector_service.service_path(tmp_path)
    path.parent.mkdir(parents=True)
    original = collector_service.plist_bytes(
        executable=old_python,
        script=old_script,
    )
    path.write_bytes(original)
    runner.loaded.add(collector_service.SERVICE_LABEL)

    with pytest.raises(
        collector_service.CollectorServiceError,
        match="bootstrap failed",
    ):
        collector_service.install_service(
            home=tmp_path,
            executable=new_python,
            script=new_script,
            run_command=runner,
            uid=501,
        )

    assert path.read_bytes() == original
    assert collector_service.SERVICE_LABEL in runner.loaded
    bootstrap_calls = [call for call in runner.calls if call[1] == "bootstrap"]
    assert len(bootstrap_calls) == 2


def test_first_install_failure_removes_generated_plist(tmp_path):
    runner = LaunchctlStub(bootstrap_failures=1)
    executable, script = _install_paths(tmp_path, "current")

    with pytest.raises(
        collector_service.CollectorServiceError,
        match="bootstrap failed",
    ):
        collector_service.install_service(
            home=tmp_path,
            executable=executable,
            script=script,
            run_command=runner,
            uid=501,
        )

    assert not collector_service.service_path(tmp_path).exists()
    assert collector_service.SERVICE_LABEL not in runner.loaded


def test_uninstall_stop_failure_restores_prior_loaded_state(tmp_path):
    runner = LaunchctlStub(
        bootout_failures={collector_service.LEGACY_SERVICE_LABEL}
    )
    current_path = collector_service.service_path(tmp_path)
    legacy_path = collector_service.legacy_service_path(tmp_path)
    current = _write_label_plist(current_path, collector_service.SERVICE_LABEL)
    legacy = _write_label_plist(
        legacy_path, collector_service.LEGACY_SERVICE_LABEL
    )
    runner.loaded.update({
        collector_service.SERVICE_LABEL,
        collector_service.LEGACY_SERVICE_LABEL,
    })

    with pytest.raises(
        collector_service.CollectorServiceError,
        match="bootout failed",
    ):
        collector_service.uninstall_service(
            home=tmp_path,
            run_command=runner,
            uid=501,
        )

    assert current_path.read_bytes() == current
    assert legacy_path.read_bytes() == legacy
    assert runner.loaded == {
        collector_service.SERVICE_LABEL,
        collector_service.LEGACY_SERVICE_LABEL,
    }


def test_uninstall_delete_failure_restores_files_and_loaded_state(
    tmp_path, monkeypatch,
):
    runner = LaunchctlStub()
    current_path = collector_service.service_path(tmp_path)
    legacy_path = collector_service.legacy_service_path(tmp_path)
    current = _write_label_plist(current_path, collector_service.SERVICE_LABEL)
    legacy = _write_label_plist(
        legacy_path, collector_service.LEGACY_SERVICE_LABEL
    )
    runner.loaded.update({
        collector_service.SERVICE_LABEL,
        collector_service.LEGACY_SERVICE_LABEL,
    })
    real_unlink = Path.unlink

    def fail_legacy_delete(path, *args, **kwargs):
        if path == legacy_path:
            raise OSError("delete failed")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_legacy_delete)

    with pytest.raises(
        collector_service.CollectorServiceError,
        match="delete failed",
    ):
        collector_service.uninstall_service(
            home=tmp_path,
            run_command=runner,
            uid=501,
        )

    assert current_path.read_bytes() == current
    assert legacy_path.read_bytes() == legacy
    assert runner.loaded == {
        collector_service.SERVICE_LABEL,
        collector_service.LEGACY_SERVICE_LABEL,
    }


def test_manual_collect_bypasses_schedule_and_scheduled_calls_deduplicate(
    tmp_path, monkeypatch,
):
    import buddymon

    monkeypatch.setattr(paths, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(paths, "STATE_FILE", paths.STATE_DIR / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", paths.STATE_DIR / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", paths.STATE_DIR / "journal.jsonl")
    game_state = _state_with_buddy()
    state.save(game_state)
    calls = []

    def fake_collect(current, _rng):
        calls.append(current)
        return {
            "bootstrapped_now": False,
            "result": None,
            "encounter": None,
            "tokens": {"output": 0, "input": 0, "cache_write": 0, "cache_read": 0},
            "raw_tokens": 0,
        }

    monkeypatch.setattr(buddymon.collectors, "collect", fake_collect)
    monkeypatch.setattr(buddymon.time, "time", lambda: 1_000.0)

    assert buddymon.collect(["--scheduled"]) == "no new tokens"
    assert buddymon.collect(["--scheduled"]) == "scheduled collection not due"
    assert buddymon.collect([]) == "no new tokens"
    assert len(calls) == 2


def test_failed_scheduled_collection_does_not_advance_gate(tmp_path, monkeypatch):
    import buddymon

    monkeypatch.setattr(paths, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(paths, "STATE_FILE", paths.STATE_DIR / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", paths.STATE_DIR / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", paths.STATE_DIR / "journal.jsonl")
    state.save(_state_with_buddy())

    def fail(_current, _rng):
        raise RuntimeError("scan failed")

    monkeypatch.setattr(buddymon.collectors, "collect", fail)
    monkeypatch.setattr(buddymon.time, "time", lambda: 1_000.0)

    try:
        buddymon.collect(["--scheduled"])
    except RuntimeError as exc:
        assert str(exc) == "scan failed"
    else:
        raise AssertionError("scheduled collection should propagate scan failures")

    assert collector_service.collection_due(state.load(), now=1_000)


def test_scheduled_collection_marks_fresh_completion_time(tmp_path, monkeypatch):
    import buddymon

    monkeypatch.setattr(paths, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(paths, "STATE_FILE", paths.STATE_DIR / "state.json")
    monkeypatch.setattr(paths, "SESSIONS_DIR", paths.STATE_DIR / "sessions")
    monkeypatch.setattr(paths, "JOURNAL_FILE", paths.STATE_DIR / "journal.jsonl")
    state.save(_state_with_buddy())
    monkeypatch.setattr(
        buddymon.collectors,
        "collect",
        lambda _current, _rng: {
            "bootstrapped_now": False,
            "result": None,
            "encounter": None,
            "tokens": {
                "output": 0,
                "input": 0,
                "cache_write": 0,
                "cache_read": 0,
            },
            "raw_tokens": 0,
        },
    )
    times = iter((1_000.0, 1_305.0))
    monkeypatch.setattr(buddymon.time, "time", lambda: next(times))

    assert buddymon.collect(["--scheduled"]) == "no new tokens"

    saved = state.load()
    assert saved["collectors"][collector_service.SCHEDULED_AT_KEY] == 1_305.0
    assert not collector_service.collection_due(saved, now=1_604.0)
    assert collector_service.collection_due(saved, now=1_605.0)


def test_collector_cli_dispatches_without_real_launchctl(monkeypatch):
    import buddymon

    healthy = {
        "path": "/tmp/collector.plist",
        "installed": True,
        "loaded": True,
        "path_matches": True,
        "legacy_present": False,
    }
    monkeypatch.setattr(
        buddymon.collector_service, "install_service", lambda: healthy
    )
    monkeypatch.setattr(
        buddymon.collector_service, "service_status", lambda: healthy
    )
    monkeypatch.setattr(
        buddymon.collector_service,
        "uninstall_service",
        lambda: {"removed": ["/tmp/collector.plist"]},
    )

    installed = buddymon.collector_service_command(["install"])
    status = buddymon.collector_service_command(["status"])
    uninstalled = buddymon.collector_service_command(["uninstall"])
    invalid = buddymon.collector_service_command(["wat"])

    assert "installed and running" in installed.text
    assert installed.exit_code == 0
    assert "installed and running" in status.text
    assert status.exit_code == 0
    assert uninstalled.text.endswith("(1 file removed)")
    assert uninstalled.exit_code == 0
    assert invalid.text.startswith("Usage:")
    assert invalid.exit_code == 2


def test_collector_cli_subprocess_exit_codes(tmp_path):
    script = Path(__file__).resolve().parent.parent / "buddymon.py"
    usage = subprocess.run(
        [sys.executable, str(script), "collector", "wat"],
        capture_output=True,
        text=True,
        check=False,
    )
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "PATH": "",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    failed = subprocess.run(
        [sys.executable, str(script), "collector", "install"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert usage.returncode == 2
    assert usage.stdout.startswith("Usage:")
    assert failed.returncode == 1
    assert failed.stdout.startswith("collector service failed:")
