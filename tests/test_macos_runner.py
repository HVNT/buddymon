import subprocess

import pytest

from tests.native_test_support import (
    MENU_PANEL_SWIFT_NAMES,
    ROOT,
    SWIFT_DIR,
    fixture_repo,
    pytestmark as pytestmark,
    read_menu_panel_sources,
    run_harness,
    swift_function_body,
)


def test_process_executor_drains_simultaneous_large_streams(native_runner_harness):
    result = run_harness(native_runner_harness, "streams")

    assert result["stdout_payload_bytes"] == 1_100_000
    assert result["stderr_payload_bytes"] == 1_100_000
    assert result["stdout_bytes"] >= 1_100_000
    assert result["stderr_bytes"] >= 1_100_000


def test_process_executor_closes_parent_pipe_writers_after_launch():
    source = (SWIFT_DIR / "ProcessExecutor.swift").read_text(encoding="utf-8")

    launched = source.index("try process.run()")
    stdout_closed = source.index("outputPipe.fileHandleForWriting.closeFile()")
    stderr_closed = source.index("errorPipe.fileHandleForWriting.closeFile()")
    readers_wait = source.index("readers.wait()")

    assert launched < stdout_closed < readers_wait
    assert launched < stderr_closed < readers_wait


def test_buddymon_runner_async_decodes_large_valid_json(
    native_runner_harness, tmp_path
):
    env = fixture_repo(tmp_path, "large")

    result = run_harness(native_runner_harness, "runner-json", env=env)

    assert result["rows"] == 6000
    assert result["payload_bytes_lower_bound"] > 1024 * 1024


def test_buddymon_runner_sync_facade_decodes_large_valid_json(
    native_runner_harness, tmp_path
):
    env = fixture_repo(tmp_path, "large")

    result = run_harness(native_runner_harness, "runner-json-sync", env=env)

    assert result["rows"] == 6000
    assert result["payload_bytes_lower_bound"] > 1024 * 1024


def test_buddymon_runner_preserves_nonzero_stderr(native_runner_harness, tmp_path):
    env = fixture_repo(tmp_path, "error")

    result = run_harness(native_runner_harness, "runner-error", env=env)

    assert result["status"] == 23
    assert result["stdout"] == ""
    assert result["stderr"] == "native runner failure\n"
    assert result["description"] == "native runner failure"


def test_buddymon_runner_describes_failure_with_empty_streams(
    native_runner_harness, tmp_path
):
    env = fixture_repo(tmp_path, "empty-error")

    result = run_harness(native_runner_harness, "runner-error", env=env)

    assert result["status"] == 37
    assert result["stdout"] == ""
    assert result["stderr"] == ""
    assert result["description"] == "BuddyMon command failed with exit status 37."


def test_native_app_keeps_first_launch_offline_and_uses_shared_scheduling():
    app_source = (
        SWIFT_DIR / "AppDelegate.swift"
    ).read_text(encoding="utf-8")

    first_setup = swift_function_body(
        app_source,
        "private func presentStarterSetupIfNeeded()",
    )
    refresh_status = swift_function_body(
        app_source,
        "private func refreshStatus() async",
    )
    assert "presentStarterSetup" in first_setup
    assert "chooseStarter()" not in first_setup
    assert "installAssets" not in first_setup
    assert "if awaitsInitialStatus" in refresh_status
    assert "awaitsInitialStatus = false" in refresh_status
    assert "_ = presentStarterSetupIfNeeded()" in refresh_status
    assert refresh_status.index("hasConfirmedStatus = true") < refresh_status.index(
        "_ = presentStarterSetupIfNeeded()"
    )
    assert '["collect", "--scheduled"]' in app_source
    assert "installAssets" not in app_source
    assert "try runner." not in app_source
    assert "statusRefreshGeneration" in app_source


def test_first_run_and_auxiliary_messages_use_compact_panel_content():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    panel_source = read_menu_panel_sources()
    build_source = (ROOT / "scripts" / "build-macos-app.sh").read_text(
        encoding="utf-8"
    )

    launch = swift_function_body(
        app_source,
        "func applicationDidFinishLaunching",
    )
    assert "flowController" not in launch

    first_setup = swift_function_body(
        app_source,
        "private func presentStarterSetupIfNeeded()",
    )
    assert "menuPanelController.presentStarterSetup(" in first_setup
    choose_starter = swift_function_body(
        app_source,
        "private func chooseStarter(",
    )
    assert 'menuPanelController.presentLoading("Choosing your starter…")' in (
        choose_starter
    )
    assert "private func chooseStarter(_ starter: String) async -> Bool" in app_source
    assert "return false" in choose_starter
    present_message = swift_function_body(app_source, "private func presentMessage(")
    assert "menuPanelController.presentMessage(text)" in present_message
    assert "BuddyMonCompactStarterSetupView" in panel_source
    assert "BuddyMonCompactNoticeView" in panel_source
    assert "presentFlowContent" not in panel_source
    assert "MenuPanelFlowController.swift" not in build_source
    assert "CompactSetupView.swift" in build_source
    assert not (SWIFT_DIR / "MenuPanelFlowController.swift").exists()


def test_native_app_allows_only_one_process(
    single_instance_harness,
    tmp_path,
):
    lock_path = tmp_path / "native-app.lock"
    first = subprocess.Popen(
        [str(single_instance_harness), str(lock_path), "hold"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert first.stdout is not None
        assert first.stdout.readline().strip() == f"acquired {first.pid}"

        second = subprocess.run(
            [str(single_instance_harness), str(lock_path)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        assert second.returncode == 0, second.stderr
        assert second.stdout.strip() == f"blocked {first.pid}"
    finally:
        first.terminate()
        first.wait(timeout=5)

    after_exit = subprocess.run(
        [str(single_instance_harness), str(lock_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert after_exit.returncode == 0, after_exit.stderr
    assert after_exit.stdout.startswith("acquired ")


def test_native_app_rejects_symlink_lock_file(
    single_instance_harness,
    tmp_path,
):
    target = tmp_path / "target"
    target.write_text("do not touch", encoding="utf-8")
    lock_path = tmp_path / "native-app.lock"
    lock_path.symlink_to(target)

    result = subprocess.run(
        [str(single_instance_harness), str(lock_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert target.read_text(encoding="utf-8") == "do not touch"


def test_native_state_observer_filters_noise_and_debounces_atomic_saves(
    local_state_observer_harness,
    tmp_path,
):
    result = subprocess.run(
        [str(local_state_observer_harness), str(tmp_path / "state")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '1|{"version":2}'


def test_native_app_refreshes_from_local_state_without_waiting_for_animation():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    observer_source = (SWIFT_DIR / "LocalStateObserver.swift").read_text(
        encoding="utf-8"
    )
    build_source = (ROOT / "scripts" / "build-macos-app.sh").read_text(
        encoding="utf-8"
    )
    launch = swift_function_body(
        app_source,
        "func applicationDidFinishLaunching",
    )
    default_panel = swift_function_body(
        app_source,
        "private func presentRootPanel()",
    )
    passive_refresh = swift_function_body(
        app_source,
        "private func requestStatusRefresh()",
    )

    assert "installLocalStateObserver()" in launch
    assert "withTimeInterval: 30" in launch
    assert "requestStatusRefresh()" in default_panel
    assert "passiveStatusRefreshPending = true" in passive_refresh
    assert "DispatchSource.makeFileSystemObjectSource" in observer_source
    assert "O_EVTONLY | O_CLOEXEC | O_NOFOLLOW" in observer_source
    assert 'environment["XDG_STATE_HOME"]' in observer_source
    assert "signature != lastSignature" in observer_source
    assert "LocalStateObserver.swift" in build_source
    assert "momentQueue" not in observer_source


def test_native_app_checks_single_instance_before_creating_menu_item():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    build_source = (ROOT / "scripts" / "build-macos-app.sh").read_text(
        encoding="utf-8"
    )
    guard_source = (SWIFT_DIR / "SingleInstanceGuard.swift").read_text(
        encoding="utf-8"
    )
    launch = swift_function_body(
        app_source,
        "func applicationDidFinishLaunching",
    )

    assert launch.index("claimSingleInstance()") < launch.index(
        "NSStatusBar.system.statusItem"
    )
    assert "O_CLOEXEC" in guard_source
    assert "O_NOFOLLOW" in guard_source
    assert "F_GETLK" in guard_source
    assert "DistributedNotificationCenter.default().post(" in app_source
    assert "open-menu-panel" in app_source
    assert "NSApp.setActivationPolicy(.accessory)" in launch
    assert "presentRootPanel()" not in launch
    assert "installApplicationMenu()" not in app_source
    assert "installQuitShortcut()" not in app_source
    assert "<key>LSUIElement</key>\n  <true/>" in build_source
    production_sources = build_source.split(
        'if [[ "${REQUIRE_RUNTIME}" != "1" ]]', 1
    )[0]
    for source_name in MENU_PANEL_SWIFT_NAMES:
        assert source_name in production_sources
    assert "MenuBarBuddy.swift" in production_sources
    assert "BrandStylesPreview.swift" not in production_sources
    assert "StyleArchivePreview.swift" not in production_sources


def test_process_executor_timeout_force_kills_stubborn_child(native_runner_harness):
    result = run_harness(native_runner_harness, "timeout")

    assert result["timeout"] == pytest.approx(0.5)
    assert result["status"] == 9
    assert result["signalled"] is True
    assert result["elapsed"] < 3


def test_process_executor_task_cancellation_force_kills_stubborn_child(
    native_runner_harness,
):
    result = run_harness(native_runner_harness, "cancel")

    assert result["status"] == 9
    assert result["signalled"] is True
    assert result["elapsed"] < 3
