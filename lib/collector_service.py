"""Scheduled collection and optional user LaunchAgent management."""

import os
import plistlib
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path


COLLECT_INTERVAL_SECONDS = 300
SCHEDULED_AT_KEY = "_last_scheduled_at"
SERVICE_LABEL = "io.github.hvnt.buddymon.collector"
LEGACY_SERVICE_LABEL = "com.hunt.buddymon-collect"


class CollectorServiceError(RuntimeError):
    """Raised when an explicit service lifecycle command fails."""


def collection_due(game_state, now=None):
    """Return whether a scheduled caller should collect now.

    Callers must hold the shared state lock while checking and later marking the
    run. Invalid and future timestamps fail open so clock changes cannot wedge
    collection indefinitely.
    """
    now = time.time() if now is None else float(now)
    value = game_state.get("collectors", {}).get(SCHEDULED_AT_KEY)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return True
    if value > now:
        return True
    return now - value >= COLLECT_INTERVAL_SECONDS


def mark_collection(game_state, now=None):
    """Record a successful scheduled collection while the state lock is held."""
    now = time.time() if now is None else float(now)
    game_state.setdefault("collectors", {})[SCHEDULED_AT_KEY] = now


def script_path():
    return Path(__file__).resolve().parent.parent / "buddymon.py"


def python_path():
    executable = sys.executable or "/usr/bin/python3"
    # Keep a venv or bundled-runtime symlink intact. Resolving it to the base
    # interpreter can silently drop that environment on the next launch.
    return Path(executable).expanduser().absolute()


def launch_agents_dir(home=None):
    root = Path.home() if home is None else Path(home)
    return root / "Library" / "LaunchAgents"


def service_path(home=None):
    return launch_agents_dir(home) / f"{SERVICE_LABEL}.plist"


def legacy_service_path(home=None):
    return launch_agents_dir(home) / f"{LEGACY_SERVICE_LABEL}.plist"


def service_target(label=SERVICE_LABEL, uid=None):
    return f"{service_domain(uid)}/{label}"


def service_domain(uid=None):
    uid = os.getuid() if uid is None else uid
    return f"gui/{uid}"


def plist_payload(executable=None, script=None):
    executable = (
        python_path()
        if executable is None
        else Path(executable).expanduser().absolute()
    )
    script = script_path() if script is None else Path(script).resolve()
    payload = {
        "Label": SERVICE_LABEL,
        "ProgramArguments": [
            str(executable),
            str(script),
            "collect",
            "--scheduled",
        ],
        "StartInterval": COLLECT_INTERVAL_SECONDS,
        "RunAtLoad": True,
    }
    state_home = os.environ.get("XDG_STATE_HOME")
    if state_home:
        payload["EnvironmentVariables"] = {"XDG_STATE_HOME": state_home}
    return payload


def plist_bytes(executable=None, script=None):
    return plistlib.dumps(
        plist_payload(executable=executable, script=script),
        fmt=plistlib.FMT_XML,
        sort_keys=False,
    )


def _validated_plist_payload(executable=None, script=None):
    payload = plist_payload(executable=executable, script=script)
    python = Path(payload["ProgramArguments"][0])
    entrypoint = Path(payload["ProgramArguments"][1])
    if not python.is_file() or not os.access(python, os.X_OK):
        raise CollectorServiceError(
            f"Python executable is missing or not executable: {python}"
        )
    if not entrypoint.is_file() or not os.access(entrypoint, os.R_OK):
        raise CollectorServiceError(
            f"BuddyMon entrypoint is missing or unreadable: {entrypoint}"
        )
    return payload


def _write_bytes(path, contents, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _write_plist(path, payload):
    _write_bytes(
        path,
        plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=False),
    )


def _file_snapshot(path):
    try:
        info = path.stat()
        return path.read_bytes(), stat.S_IMODE(info.st_mode)
    except FileNotFoundError:
        return None


def _restore_file(path, snapshot):
    if snapshot is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    contents, mode = snapshot
    _write_bytes(path, contents, mode)


def _run_launchctl(args, run_command):
    try:
        return run_command(
            ["launchctl", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            ["launchctl", *args],
            127,
            stdout="",
            stderr=str(exc),
        )


def _result_message(result):
    return (result.stderr or result.stdout or "launchctl failed").strip()


def _bootout(label, run_command, uid=None):
    return _run_launchctl(["bootout", service_target(label, uid)], run_command)


def _is_loaded(label, run_command, uid=None):
    result = _run_launchctl(["print", service_target(label, uid)], run_command)
    return result.returncode == 0


def _installed_payload(path):
    try:
        with path.open("rb") as stream:
            value = plistlib.load(stream)
        return value if isinstance(value, dict) else None
    except (OSError, plistlib.InvalidFileException):
        return None


def _rollback_install(
    *,
    path,
    snapshot,
    was_loaded,
    bootstrap_attempted,
    run_command,
    uid,
):
    errors = []
    if bootstrap_attempted and _is_loaded(SERVICE_LABEL, run_command, uid):
        result = _bootout(SERVICE_LABEL, run_command, uid)
        if result.returncode != 0:
            errors.append(f"could not stop replacement: {_result_message(result)}")

    restored = False
    try:
        _restore_file(path, snapshot)
        restored = True
    except OSError as exc:
        errors.append(f"could not restore plist: {exc}")

    if was_loaded and restored and not _is_loaded(
        SERVICE_LABEL, run_command, uid
    ):
        result = _run_launchctl(
            ["bootstrap", service_domain(uid), str(path)],
            run_command,
        )
        if result.returncode != 0:
            errors.append(f"could not restart prior service: {_result_message(result)}")
    return errors


def service_status(
    *,
    home=None,
    executable=None,
    script=None,
    run_command=subprocess.run,
    uid=None,
):
    path = service_path(home)
    expected = plist_payload(executable=executable, script=script)
    installed = _installed_payload(path)
    legacy_path = legacy_service_path(home)
    legacy_file = legacy_path.exists()
    legacy_loaded = _is_loaded(LEGACY_SERVICE_LABEL, run_command, uid)
    return {
        "path": str(path),
        "installed": installed is not None,
        "loaded": _is_loaded(SERVICE_LABEL, run_command, uid),
        "path_matches": installed == expected,
        "legacy_path": str(legacy_path),
        "legacy_present": legacy_file or legacy_loaded,
        "legacy_loaded": legacy_loaded,
    }


def install_service(
    *,
    home=None,
    executable=None,
    script=None,
    run_command=subprocess.run,
    uid=None,
):
    payload = _validated_plist_payload(
        executable=executable,
        script=script,
    )
    path = service_path(home)
    snapshot = _file_snapshot(path)
    was_loaded = _is_loaded(SERVICE_LABEL, run_command, uid)
    if was_loaded and (snapshot is None or _installed_payload(path) is None):
        raise CollectorServiceError(
            "Cannot safely replace the loaded collector because its plist "
            "is missing or invalid. Uninstall it explicitly, then install again."
        )
    _write_plist(path, payload)

    bootstrap_attempted = False
    try:
        if was_loaded:
            result = _bootout(SERVICE_LABEL, run_command, uid)
            if result.returncode != 0:
                raise CollectorServiceError(_result_message(result))
        bootstrap_attempted = True
        result = _run_launchctl(
            ["bootstrap", service_domain(uid), str(path)],
            run_command,
        )
        if result.returncode != 0:
            raise CollectorServiceError(_result_message(result))
    except CollectorServiceError as exc:
        rollback_errors = _rollback_install(
            path=path,
            snapshot=snapshot,
            was_loaded=was_loaded,
            bootstrap_attempted=bootstrap_attempted,
            run_command=run_command,
            uid=uid,
        )
        message = str(exc)
        if rollback_errors:
            message += "; rollback failed: " + "; ".join(rollback_errors)
        raise CollectorServiceError(message) from exc

    legacy_path = legacy_service_path(home)
    legacy_loaded = _is_loaded(LEGACY_SERVICE_LABEL, run_command, uid)
    legacy_stopped = not legacy_loaded
    if legacy_loaded:
        legacy_stopped = (
            _bootout(LEGACY_SERVICE_LABEL, run_command, uid).returncode == 0
        )
    if legacy_stopped:
        try:
            legacy_path.unlink()
        except OSError:
            pass
    return service_status(
        home=home,
        executable=executable,
        script=script,
        run_command=run_command,
        uid=uid,
    )


def uninstall_service(*, home=None, run_command=subprocess.run, uid=None):
    services = (
        (SERVICE_LABEL, service_path(home)),
        (LEGACY_SERVICE_LABEL, legacy_service_path(home)),
    )
    snapshots = {path: _file_snapshot(path) for _, path in services}
    loaded = {
        label: _is_loaded(label, run_command, uid) for label, _ in services
    }

    for label, path in services:
        if not loaded[label]:
            continue
        payload = _installed_payload(path)
        if snapshots[path] is None or not payload or payload.get("Label") != label:
            raise CollectorServiceError(
                f"Cannot safely stop {label}: its restorable plist is missing "
                "or invalid."
            )

    removed_paths = []
    try:
        for label, _ in services:
            if not loaded[label]:
                continue
            result = _bootout(label, run_command, uid)
            if result.returncode != 0:
                raise CollectorServiceError(
                    f"could not stop {label}: {_result_message(result)}"
                )
            if _is_loaded(label, run_command, uid):
                raise CollectorServiceError(f"could not confirm {label} stopped")

        for _, path in services:
            if snapshots[path] is None:
                continue
            path.unlink()
            removed_paths.append(path)
    except (CollectorServiceError, OSError) as exc:
        rollback_errors = []
        for _, path in services:
            if path not in removed_paths:
                continue
            try:
                _restore_file(path, snapshots[path])
            except OSError as restore_exc:
                rollback_errors.append(
                    f"could not restore {path.name}: {restore_exc}"
                )
        for label, path in services:
            if not loaded[label] or _is_loaded(label, run_command, uid):
                continue
            result = _run_launchctl(
                ["bootstrap", service_domain(uid), str(path)],
                run_command,
            )
            if result.returncode != 0:
                rollback_errors.append(
                    f"could not restart {label}: {_result_message(result)}"
                )
        message = f"collector uninstall failed: {exc}"
        if rollback_errors:
            message += "; rollback failed: " + "; ".join(rollback_errors)
        raise CollectorServiceError(message) from exc

    return {"removed": [str(path) for path in removed_paths]}


def format_status(status):
    if status["installed"] and status["loaded"] and status["path_matches"]:
        summary = "installed and running"
    elif status["installed"] and not status["path_matches"]:
        summary = "installed with stale runtime paths; reinstall it"
    elif status["installed"]:
        summary = "installed but not running"
    else:
        summary = "not installed"
    if status["legacy_present"]:
        summary += "; legacy collector detected"
    return f"collector service: {summary}\n{status['path']}"
