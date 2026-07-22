import json
import os
import re
import shutil
import struct
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SWIFT_DIR = ROOT / "macos" / "BuddyMonApp" / "Sources" / "BuddyMonApp"
BRAND_SNAPSHOT_TOOL = ROOT / "tools" / "BrandStylesSnapshot.swift"
MENU_PANEL_SNAPSHOT_TOOL = ROOT / "tools" / "MenuPanelSnapshot.swift"
MENU_PANEL_STATE_HARNESS_TOOL = ROOT / "tools" / "MenuPanelStateHarness.swift"
MENU_BAR_HARNESS_TOOL = ROOT / "tools" / "MenuBarStateHarness.swift"
SWIFTC = shutil.which("swiftc")

pytestmark = [
    pytest.mark.skipif(sys.platform != "darwin", reason="BuddyMon.app is macOS-only"),
    pytest.mark.skipif(SWIFTC is None, reason="swiftc is not installed"),
]


def swift_brand_color(source: str, name: str) -> tuple[float, float, float]:
    match = re.search(
        rf"static let {re.escape(name)} = NSColor\(\s*"
        r"calibratedRed: ([0-9.]+),\s*"
        r"green: ([0-9.]+),\s*"
        r"blue: ([0-9.]+),",
        source,
    )
    assert match is not None, f"missing Brand Styles color token: {name}"
    return tuple(float(value) for value in match.groups())


def contrast_ratio(
    foreground: tuple[float, float, float],
    background: tuple[float, float, float],
) -> float:
    def linear(channel: float) -> float:
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    def luminance(color: tuple[float, float, float]) -> float:
        red, green, blue = (linear(channel) for channel in color)
        return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)

    foreground_luminance = luminance(foreground)
    background_luminance = luminance(background)
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


HARNESS_SOURCE = r'''
import Foundation

enum HarnessFailure: Error, LocalizedError {
    case failed(String)

    var errorDescription: String? {
        switch self {
        case .failed(let message):
            return message
        }
    }
}

@main
struct NativeRunnerHarness {
    static let pythonURL = URL(fileURLWithPath: "/usr/bin/python3")
    static let stubbornScript = "import signal, time; signal.signal(signal.SIGTERM, lambda *_: None); time.sleep(10)"

    static func emit(_ object: [String: Any]) throws {
        let data = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data([0x0A]))
    }

    static func fixtureRunner() throws -> BuddyMonRunner {
        guard let path = ProcessInfo.processInfo.environment["BUDDYMON_FIXTURE_REPO"] else {
            throw HarnessFailure.failed("BUDDYMON_FIXTURE_REPO is missing")
        }
        return BuddyMonRunner(
            repoURL: URL(fileURLWithPath: path, isDirectory: true),
            pythonURL: pythonURL
        )
    }

    static func simultaneousStreams() async throws {
        let script = #"""
import os
import threading

size = 1_100_000

def write_all(fd, value):
    block = value * 65536
    remaining = size
    while remaining:
        chunk = block[:min(len(block), remaining)]
        remaining -= os.write(fd, chunk)

threads = [
    threading.Thread(target=write_all, args=(1, bytes([1]))),
    threading.Thread(target=write_all, args=(2, bytes([2]))),
]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
"""#
        let result = try await ProcessExecutor().run(ProcessCommand(
            executableURL: pythonURL,
            arguments: ["-c", script]
        ))
        guard result.succeeded else {
            throw HarnessFailure.failed("large stream process failed")
        }
        try emit([
            "stdout_bytes": result.stdout.count,
            "stderr_bytes": result.stderr.count,
            "stdout_payload_bytes": result.stdout.filter { $0 == 1 }.count,
            "stderr_payload_bytes": result.stderr.filter { $0 == 2 }.count,
        ])
    }

    static func largeRunnerJSON() async throws {
        let view = try await fixtureRunner().appView("box")
        let rows = view["rows"] as? [[String: Any]] ?? []
        let blobBytes = (rows.first?["blob"] as? String)?.utf8.count ?? 0
        try emit([
            "rows": rows.count,
            "payload_bytes_lower_bound": rows.count * blobBytes,
        ])
    }

    static func largeRunnerJSONSync() throws {
        let view = try fixtureRunner().appView("box")
        let rows = view["rows"] as? [[String: Any]] ?? []
        let blobBytes = (rows.first?["blob"] as? String)?.utf8.count ?? 0
        try emit([
            "rows": rows.count,
            "payload_bytes_lower_bound": rows.count * blobBytes,
        ])
    }

    static func runnerError() throws {
        do {
            _ = try fixtureRunner().run(["app-view", "box"])
            throw HarnessFailure.failed("runner unexpectedly succeeded")
        } catch let error as BuddyMonRunnerError {
            switch error {
            case .commandFailed(let status, let stdout, let stderr):
                try emit([
                    "status": Int(status),
                    "stdout": stdout,
                    "stderr": stderr,
                    "description": error.localizedDescription,
                ])
            default:
                throw error
            }
        }
    }

    static func timeout() async throws {
        let started = Date()
        do {
            _ = try await ProcessExecutor().run(ProcessCommand(
                executableURL: pythonURL,
                arguments: ["-c", stubbornScript],
                timeout: 0.5
            ))
            throw HarnessFailure.failed("command unexpectedly escaped its timeout")
        } catch let error as ProcessExecutorError {
            switch error {
            case .timedOut(let configuredTimeout, let result):
                try emit([
                    "timeout": configuredTimeout,
                    "elapsed": Date().timeIntervalSince(started),
                    "status": Int(result.terminationStatus),
                    "signalled": result.terminationReason == .uncaughtSignal,
                ])
            default:
                throw error
            }
        }
    }

    static func cancellation() async throws {
        let executor = ProcessExecutor()
        let command = ProcessCommand(
            executableURL: pythonURL,
            arguments: ["-c", stubbornScript]
        )
        let started = Date()
        let task = Task {
            try await executor.run(command)
        }
        try await Task<Never, Never>.sleep(nanoseconds: 500_000_000)
        task.cancel()
        do {
            _ = try await task.value
            throw HarnessFailure.failed("command unexpectedly escaped cancellation")
        } catch let error as ProcessExecutorError {
            switch error {
            case .cancelled(let result):
                guard let result else {
                    throw HarnessFailure.failed("cancelled command returned no result")
                }
                try emit([
                    "elapsed": Date().timeIntervalSince(started),
                    "status": Int(result.terminationStatus),
                    "signalled": result.terminationReason == .uncaughtSignal,
                ])
            default:
                throw error
            }
        }
    }

    static func main() async {
        do {
            switch CommandLine.arguments.dropFirst().first {
            case "streams":
                try await simultaneousStreams()
            case "runner-json":
                try await largeRunnerJSON()
            case "runner-json-sync":
                try largeRunnerJSONSync()
            case "runner-error":
                try runnerError()
            case "timeout":
                try await timeout()
            case "cancel":
                try await cancellation()
            default:
                throw HarnessFailure.failed("unknown harness mode")
            }
        } catch {
            let message = Data((error.localizedDescription + "\n").utf8)
            FileHandle.standardError.write(message)
            exit(1)
        }
    }
}
'''


SINGLE_INSTANCE_HARNESS_SOURCE = r'''
import Darwin
import Foundation

@main
struct SingleInstanceHarness {
    static func main() {
        do {
            try run()
        } catch {
            FileHandle.standardError.write(
                Data((error.localizedDescription + "\n").utf8)
            )
            exit(1)
        }
    }

    static func run() throws {
        let arguments = CommandLine.arguments
        guard arguments.count >= 2 else {
            exit(2)
        }

        let guardInstance = SingleInstanceGuard(
            lockURL: URL(fileURLWithPath: arguments[1])
        )
        switch try guardInstance.acquire() {
        case .acquired:
            FileHandle.standardOutput.write(
                Data("acquired \(getpid())\n".utf8)
            )
        case .alreadyRunning(let processIdentifier):
            let owner = processIdentifier.map(String.init) ?? "unknown"
            FileHandle.standardOutput.write(Data("blocked \(owner)\n".utf8))
            return
        }

        if arguments.dropFirst(2).contains("hold") {
            Thread.sleep(forTimeInterval: 30)
        }
    }
}
'''


LOCAL_STATE_OBSERVER_HARNESS_SOURCE = r'''
import Darwin
import Foundation

@main
@MainActor
struct LocalStateObserverHarness {
    static var observer: LocalStateObserver?
    static var callbackCount = 0
    static var observedState = ""

    static func main() {
        guard CommandLine.arguments.count == 2 else {
            exit(2)
        }

        let directoryURL = URL(
            fileURLWithPath: CommandLine.arguments[1],
            isDirectory: true
        )
        let stateURL = directoryURL.appendingPathComponent("state.json")
        observer = LocalStateObserver(
            stateURL: stateURL,
            debounceInterval: 0.08
        )
        guard observer?.start(onChange: {
            guard let value = try? String(
                contentsOf: stateURL,
                encoding: .utf8
            ) else {
                FileHandle.standardError.write(Data("non-state callback\n".utf8))
                exit(3)
            }
            callbackCount += 1
            observedState = value
            if callbackCount == 1 {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                    print("\(callbackCount)|\(observedState)")
                    observer?.stop()
                    exit(callbackCount == 1 ? 0 : 4)
                }
            }
        }) == true else {
            exit(5)
        }

        DispatchQueue.global().asyncAfter(deadline: .now() + 0.04) {
            let journalURL = directoryURL.appendingPathComponent("journal.jsonl")
            try? Data("noise\n".utf8).write(to: journalURL)
        }
        DispatchQueue.global().asyncAfter(deadline: .now() + 0.24) {
            try? Data("{\"version\":1}".utf8).write(
                to: stateURL,
                options: .atomic
            )
        }
        DispatchQueue.global().asyncAfter(deadline: .now() + 0.27) {
            try? Data("{\"version\":2}".utf8).write(
                to: stateURL,
                options: .atomic
            )
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            FileHandle.standardError.write(Data("observer timed out\n".utf8))
            observer?.stop()
            exit(6)
        }
        dispatchMain()
    }
}
'''


@pytest.fixture(scope="session")
def native_runner_harness(tmp_path_factory):
    build_dir = tmp_path_factory.mktemp("native-runner")
    harness_source = build_dir / "NativeRunnerHarness.swift"
    harness_source.write_text(textwrap.dedent(HARNESS_SOURCE), encoding="utf-8")
    executable = build_dir / "native-runner-harness"
    module_cache = build_dir / "module-cache"
    result = subprocess.run(
        [
            SWIFTC,
            "-module-cache-path",
            str(module_cache),
            "-framework",
            "AppKit",
            str(SWIFT_DIR / "ProcessExecutor.swift"),
            str(SWIFT_DIR / "BuddyMonRunner.swift"),
            str(harness_source),
            "-o",
            str(executable),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return executable


@pytest.fixture(scope="session")
def single_instance_harness(tmp_path_factory):
    build_dir = tmp_path_factory.mktemp("single-instance")
    harness_source = build_dir / "SingleInstanceHarness.swift"
    harness_source.write_text(
        textwrap.dedent(SINGLE_INSTANCE_HARNESS_SOURCE),
        encoding="utf-8",
    )
    executable = build_dir / "single-instance-harness"
    module_cache = build_dir / "module-cache"
    result = subprocess.run(
        [
            SWIFTC,
            "-module-cache-path",
            str(module_cache),
            str(SWIFT_DIR / "SingleInstanceGuard.swift"),
            str(harness_source),
            "-o",
            str(executable),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return executable


@pytest.fixture(scope="session")
def local_state_observer_harness(tmp_path_factory):
    build_dir = tmp_path_factory.mktemp("local-state-observer")
    harness_source = build_dir / "LocalStateObserverHarness.swift"
    harness_source.write_text(
        textwrap.dedent(LOCAL_STATE_OBSERVER_HARNESS_SOURCE),
        encoding="utf-8",
    )
    executable = build_dir / "local-state-observer-harness"
    module_cache = build_dir / "module-cache"
    result = subprocess.run(
        [
            SWIFTC,
            "-module-cache-path",
            str(module_cache),
            str(SWIFT_DIR / "LocalStateObserver.swift"),
            str(harness_source),
            "-o",
            str(executable),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return executable


@pytest.fixture(scope="session")
def brand_snapshot_harness(tmp_path_factory):
    build_dir = tmp_path_factory.mktemp("brand-snapshot")
    executable = build_dir / "brand-styles-snapshot"
    module_cache = build_dir / "module-cache"
    result = subprocess.run(
        [
            SWIFTC,
            "-module-cache-path",
            str(module_cache),
            "-D",
            "BUDDYMON_DEVELOPMENT",
            "-framework",
            "AppKit",
            "-framework",
            "QuartzCore",
            str(SWIFT_DIR / "BrandStyle.swift"),
            str(SWIFT_DIR / "BrandStylesPreview.swift"),
            str(BRAND_SNAPSHOT_TOOL),
            "-o",
            str(executable),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return executable


@pytest.fixture(scope="session")
def menu_panel_snapshot_harness(tmp_path_factory):
    build_dir = tmp_path_factory.mktemp("menu-panel-snapshot")
    executable = build_dir / "menu-panel-snapshot"
    module_cache = build_dir / "module-cache"
    result = subprocess.run(
        [
            SWIFTC,
            "-module-cache-path",
            str(module_cache),
            "-framework",
            "AppKit",
            "-framework",
            "QuartzCore",
            str(SWIFT_DIR / "BrandStyle.swift"),
            str(SWIFT_DIR / "MenuPanelController.swift"),
            str(MENU_PANEL_SNAPSHOT_TOOL),
            "-o",
            str(executable),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return executable


@pytest.fixture(scope="session")
def menu_panel_state_snapshot_harness(tmp_path_factory):
    build_dir = tmp_path_factory.mktemp("menu-panel-state-snapshot")
    executable = build_dir / "menu-panel-state-snapshot"
    module_cache = build_dir / "module-cache"
    result = subprocess.run(
        [
            SWIFTC,
            "-module-cache-path",
            str(module_cache),
            "-framework",
            "AppKit",
            "-framework",
            "QuartzCore",
            str(SWIFT_DIR / "BrandStyle.swift"),
            str(SWIFT_DIR / "MenuPanelController.swift"),
            str(SWIFT_DIR / "MenuPanelStateHarnessView.swift"),
            str(MENU_PANEL_STATE_HARNESS_TOOL),
            "-o",
            str(executable),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return executable


@pytest.fixture(scope="session")
def menu_bar_state_snapshot_harness(tmp_path_factory):
    build_dir = tmp_path_factory.mktemp("menu-bar-state-snapshot")
    executable = build_dir / "menu-bar-state-snapshot"
    module_cache = build_dir / "module-cache"
    result = subprocess.run(
        [
            SWIFTC,
            "-module-cache-path",
            str(module_cache),
            "-framework",
            "AppKit",
            str(SWIFT_DIR / "BrandStyle.swift"),
            str(SWIFT_DIR / "MenuBarBuddy.swift"),
            str(SWIFT_DIR / "MenuBarStateHarnessView.swift"),
            str(MENU_BAR_HARNESS_TOOL),
            "-o",
            str(executable),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return executable


def run_harness(executable, mode, *, env=None, timeout=15):
    result = subprocess.run(
        [str(executable), mode],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def fixture_repo(tmp_path, mode):
    repo = tmp_path / "runtime"
    repo.mkdir()
    script = repo / "buddymon.py"
    script.write_text(
        textwrap.dedent(
            """
            import json
            import os
            import sys

            mode = os.environ.get("BUDDYMON_FIXTURE_MODE")

            if mode == "error":
                sys.stderr.write("native runner failure\\n")
                sys.stderr.flush()
                raise SystemExit(23)

            if mode == "empty-error":
                raise SystemExit(37)

            rows = [
                {"id": str(index), "blob": "x" * 256}
                for index in range(6000)
            ]
            json.dump({"rows": rows}, sys.stdout)
            """
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["BUDDYMON_FIXTURE_REPO"] = str(repo)
    env["BUDDYMON_FIXTURE_MODE"] = mode
    return env


def swift_function_body(source, signature):
    signature_start = source.index(signature)
    opening_brace = source.index("{", signature_start)
    depth = 0
    for index in range(opening_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening_brace + 1 : index]
    raise AssertionError(f"unterminated Swift function: {signature}")


def test_process_executor_drains_simultaneous_large_streams(native_runner_harness):
    result = run_harness(native_runner_harness, "streams")

    assert result["stdout_payload_bytes"] == 1_100_000
    assert result["stderr_payload_bytes"] == 1_100_000
    assert result["stdout_bytes"] >= 1_100_000
    assert result["stderr_bytes"] >= 1_100_000


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
    window_source = (
        SWIFT_DIR / "StatusWindowController.swift"
    ).read_text(encoding="utf-8")

    first_setup = swift_function_body(
        app_source,
        "private func showFirstSetupIfNeeded()",
    )
    assert "showStarterSetup" in first_setup
    assert "chooseStarter()" not in first_setup
    assert "installAssets" not in first_setup
    assert '["collect", "--scheduled"]' in app_source
    assert "func showConfirmation(" in window_source
    assert "installAssets" not in app_source
    assert "try runner." not in app_source
    assert "statusRefreshGeneration" in app_source


def test_live_auxiliary_flows_use_the_generic_panel_content_host():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    window_source = (SWIFT_DIR / "StatusWindowController.swift").read_text(
        encoding="utf-8"
    )
    panel_source = (SWIFT_DIR / "MenuPanelController.swift").read_text(
        encoding="utf-8"
    )

    launch = swift_function_body(
        app_source,
        "func applicationDidFinishLaunching",
    )
    assert "statusController.contentHandler =" in launch
    assert "menuPanelController.showExpanded(" in launch
    assert "statusController.keyboardHandlerChanged =" in launch
    assert "menuPanelController.setKeyboardHandler(handler)" in launch

    first_setup = swift_function_body(
        app_source,
        "private func showFirstSetupIfNeeded()",
    )
    assert "statusController.showStarterSetup(" in first_setup
    choose_starter = swift_function_body(
        app_source,
        "private func chooseStarter(",
    )
    assert 'statusController.showLoading("Choosing your starter…")' in choose_starter
    show_text = swift_function_body(app_source, "private func showText(")
    assert "statusController.show(text: text)" in show_text
    assert "func showConfirmation(" in window_source

    present = swift_function_body(window_source, "private func present()")
    assert "let contentHandler" in present
    assert "contentHandler(content, size)" in present
    assert "keyboardHandlerChanged(handler)" in window_source
    assert "func showExpanded(content: NSView, preferredSize: NSSize)" in panel_source
    assert "showWindow(nil)" not in window_source


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
        "private func presentDefaultPanel()",
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
    assert "presentDefaultPanel()" not in launch
    assert "installApplicationMenu()" not in app_source
    assert "installQuitShortcut()" not in app_source
    assert "<key>LSUIElement</key>\n  <true/>" in build_source
    production_sources = build_source.split(
        'if [[ "${REQUIRE_RUNTIME}" != "1" ]]', 1
    )[0]
    assert "MenuPanelController.swift" in production_sources
    assert "MenuBarBuddy.swift" in production_sources
    assert "BrandStylesPreview.swift" not in production_sources
    assert "StyleArchivePreview.swift" not in production_sources


def test_native_menu_bar_uses_a_short_pokemon_style_menu():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    buddy_source = (SWIFT_DIR / "MenuBarBuddy.swift").read_text(encoding="utf-8")
    panel_source = (SWIFT_DIR / "MenuPanelController.swift").read_text(
        encoding="utf-8"
    )
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")

    for value in [
        "BuddyMonMenuPanel",
        "BuddyMonCompactMenuView",
        "BuddyMonCompactTokensView",
        "BuddyMonCompactSettingsView",
        "BuddyMonCompactTrainerView",
        "BuddyMonFieldGuideCardBackgroundView",
        "BuddyMonTrainerBadgeView",
        "BuddyMonCompactEncounterView",
        "BuddyMonCompactEncounterResultView",
        'status["native_menu"]',
        'descriptor["image_base64"]',
        "levelPercent(active)",
        'message = "LAST CATCH"',
        '"BUDDYMON"',
        '"LVL. \\(active["level"] as? Int ?? 1)"',
        "BuddyMonMenuProgressView",
        "ARROWS MOVE  ·  RETURN SELECTS  ·  ESC CLOSE",
        "signalSprite(pokemon)",
        "signalSpriteSize",
        "BuddyMonBrand.Menu.makeStatusIndicator(appStatus)",
        "BuddyMonBrand.Menu.AppStatusState",
        'status["tokens"]',
        'menu["token_action"]',
        'menu["footer_items"]',
        "BuddyMonTokenHeaderButton",
        "headerTokenControl(",
        "BuddyMonBrand.Menu.makeDisplayLabel",
        '"↑↓ MOVE  ·  ↵ SELECT  ·  ESC"',
        'modifiers.contains("command")',
        'button.keyEquivalentModifierMask = modifiers.contains("command")',
        'replacingOccurrences(of: "Advanced: ", with: "")',
        "initialResponder",
        "buddymon-menu-sprite-bob",
    ]:
        assert value in panel_source
    assert "BuddyMonMenuStatusIndicatorView" in brand_source

    compact_home = panel_source.split("// MARK: - Compact Menu", 1)[1].split(
        "// MARK: - Token Detail", 1
    )[0]
    assert panel_source.count("BuddyMonFieldGuideCardBackgroundView()") == 6
    assert "private func compactNavigationHeader(" in panel_source
    assert panel_source.count("compactNavigationHeader(") == 6
    assert "let card = BuddyMonFieldGuideCardBackgroundView()" in compact_home
    assert "card.addSubview(root)" in compact_home
    assert "static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth" in compact_home
    assert "BuddyMonBrand.Menu.fieldGuideFrameInset" in compact_home
    assert "static let fieldGuideFrameInset: CGFloat = 8" in brand_source
    assert "static func applyFieldGuideCardSurface" in brand_source
    assert "static let buddySpriteSize: CGFloat = 54" in brand_source
    assert (
        "static let activeBuddyRowHeight: CGFloat = "
        "buddySpriteSize + (compactGap * 2)"
    ) in brand_source
    assert "static let rootContentInset = BuddyMonBrand.Menu.compactGap" in compact_home
    assert "static let buddyContentInset = BuddyMonBrand.Menu.compactGap" in compact_home
    assert "top: Layout.rootContentInset" in compact_home
    assert "root.alignment = .centerX" in compact_home
    assert "left: BuddyMonBrand.Menu.flushInset" in compact_home
    assert "right: BuddyMonBrand.Menu.flushInset" in compact_home
    assert "static let buddyRowWidth = cardWidth" in compact_home
    assert "static let subtleRule = rule.withAlphaComponent(0.28)" in brand_source
    assert "static func makeActiveBuddyRow() -> NSStackView" in brand_source
    assert "private final class BuddyMonMenuActiveRowView" in brand_source
    assert "static let statusIndicatorSize: CGFloat = 6" in brand_source
    assert "static func makeStatusIndicator(_ state: AppStatusState)" in brand_source
    assert "private final class BuddyMonMenuStatusIndicatorView" in brand_source
    assert 'case .active: return "BuddyMon active"' in brand_source
    assert 'case .idle: return "BuddyMon starting"' in brand_source

    header_layout = swift_function_body(panel_source, "private static func header")
    assert "status.isEmpty" in header_layout
    assert "appStatus = .unavailable" in header_layout
    assert "appStatus = .idle" in header_layout
    assert "appStatus = .active" in header_layout
    assert "brandMark(status)" not in header_layout
    assert "private static func brandMark" not in compact_home
    assert "buddymon-menu-cursor" not in compact_home
    assert "brandMarkSize" not in brand_source

    buddy_card_layout = swift_function_body(
        panel_source,
        "private static func buddyCard",
    )
    for edge in ["top", "left", "bottom", "right"]:
        assert f"{edge}: Layout.buddyContentInset" in buddy_card_layout
    assert "hero.spacing = Layout.buddyContentInset" in buddy_card_layout
    assert "BuddyMonBrand.Menu.makeActiveBuddyRow()" in buddy_card_layout
    assert "Layout.buddyRowWidth" in buddy_card_layout
    active_buddy_factory = swift_function_body(
        brand_source,
        "static func makeActiveBuddyRow() -> NSStackView",
    )
    assert "activeBuddyRowHeight" in active_buddy_factory
    assert "applySurface(to: card" not in buddy_card_layout
    assert "xpBarWidth" not in panel_source
    assert "xpRow.widthAnchor.constraint(equalToConstant: Layout.identityWidth)" in buddy_card_layout
    assert "let progressWidth = Layout.identityWidth" in buddy_card_layout
    assert "xpLabel.intrinsicContentSize.width" in buddy_card_layout
    assert "percentLabel.intrinsicContentSize.width" in buddy_card_layout
    assert "progress.widthAnchor.constraint(equalToConstant: progressWidth)" in buddy_card_layout
    assert "percentLabel.setContentHuggingPriority(.required" in buddy_card_layout
    assert "hero.addArrangedSubview(buddySprite(active))" in buddy_card_layout
    assert "spriteWell(active)" not in buddy_card_layout
    buddy_sprite = swift_function_body(
        panel_source,
        "private static func buddySprite",
    )
    assert "let sprite = NSImageView()" in buddy_sprite
    assert "backgroundColor" not in buddy_sprite
    assert "cornerRadius" not in buddy_sprite
    assert "BuddyMonBrand.Menu.tightGap" not in buddy_sprite
    assert "sprite.widthAnchor.constraint" in buddy_sprite
    assert "sprite.heightAnchor.constraint" in buddy_sprite
    assert "BuddyMonBrand.Menu.buddySpriteSize" in buddy_sprite

    assert '"U  OPEN"' not in panel_source
    assert '"U OPEN"' not in panel_source
    assert "root.addArrangedSubview(tokenSection" not in panel_source
    assert 'if status["pending"] as? [String: Any] == nil' in panel_source
    message_box = swift_function_body(
        panel_source,
        "private static func messageBox",
    )
    assert "IS WAITING" not in message_box
    assert "let lead = NSStackView()" not in message_box
    assert "box.spacing = BuddyMonBrand.Menu.tightGap" in message_box
    assert "left: BuddyMonBrand.Menu.flushInset" in message_box
    assert "color = BuddyMonBrand.Menu.ink" in message_box
    assert "BuddyMonBrand.Menu.pokemonColor(recent)" not in message_box
    chevron_index = message_box.index('"▶"')
    signal_index = message_box.index("let sprite = signalSprite(pokemon)")
    label_index = message_box.index("box.addArrangedSubview(messageLabel)")
    name_index = message_box.index("box.addArrangedSubview(nameLabel)")
    rarity_index = message_box.index("BuddyMonBrand.Menu.makeRarityLabel(rarity)")
    spacer_index = message_box.index("box.addArrangedSubview(flexibleSpacer())")
    assert chevron_index < signal_index < label_index < name_index < rarity_index < spacer_index
    assert "box.setCustomSpacing(BuddyMonBrand.Menu.labelGap, after: chevron)" in message_box
    assert "box.setCustomSpacing(BuddyMonBrand.Menu.tightGap, after: sprite)" in message_box
    assert "box.setCustomSpacing(BuddyMonBrand.Menu.compactGap, after: messageLabel)" in message_box
    buddy_card = swift_function_body(
        panel_source,
        "private static func buddyCard",
    )
    assert '"CAUGHT' not in buddy_card
    token_control = swift_function_body(
        panel_source,
        "private static func headerTokenControl",
    )
    assert "row.addArrangedSubview(flexibleSpacer())" in token_control
    assert "applySurface(to: row" not in token_control
    token_metric = swift_function_body(
        panel_source,
        "private static func tokenMetric",
    )
    assert "metric.orientation = .horizontal" in token_metric
    assert "font: BuddyMonBrand.Font.strong(9)" in token_metric

    for value in [
        "handleNativeMenuAction",
        'case "encounter"',
        'case "tokens"',
        'case "trainer"',
        'case "terminal_party"',
        'case "terminal_box"',
        'case "terminal_dex"',
        'case "terminal_activity"',
        'case "settings"',
        'case "refresh"',
        'case "quit"',
        "handleStatusItemClick",
        'var arguments = ["open-menu"]',
        'openTerminalExperience(screen: "party")',
        'openTerminalExperience(screen: "box")',
        'openTerminalExperience(screen: "dex")',
        'openTerminalExperience(screen: "journal")',
        "openSettings()",
    ]:
        assert value in app_source
    assert 'case "open_details"' not in app_source
    terminal_handoff = swift_function_body(
        app_source,
        "private func openTerminalExperience",
    )
    assert "menuPanelController.close()" not in terminal_handoff
    assert "menuPanelController.prepareForTerminalHandoff()" in terminal_handoff
    assert 'arguments.append("--window-frame=\\(windowFrame)")' in terminal_handoff
    assert "func prepareForTerminalHandoff()" in panel_source
    assert "removeOutsideClickMonitors()" in panel_source
    assert "BuddyMonBrand.Menu.terminalWindowWidth" in panel_source
    assert "BuddyMonBrand.Menu.terminalWindowHeight" in panel_source
    assert "static let terminalWindowWidth: CGFloat = 760" in brand_source
    assert "static let terminalWindowHeight: CGFloat = 520" in brand_source
    assert "statusItem.menu = menu" not in app_source
    assert "statusMenu?.popUp" not in app_source
    assert "BuddyMonMenuDashboard" not in app_source
    assert "NSEvent.addLocalMonitorForEvents" not in app_source

    for legacy_copy in ["COMMAND DECK", "COLLECTION  //  TERMINAL", "PRIORITY SIGNAL DETECTED"]:
        assert legacy_copy not in panel_source

    for token in [
        "BuddyMonBrand.Menu.canvas",
        "BuddyMonBrand.Menu.pokemonColor",
        "BuddyMonBrand.Menu.makeActionButton",
    ]:
        assert token in panel_source
    for token in [
        "static let pokemonBlue",
        "static let pikachu",
        "static let xpProgress",
        "static let dataProgress",
        "enum Menu",
        "static let spriteWell",
        "static let xpFill",
        "enum FireRedDisplay",
        "final class BuddyMonFireRedLabel",
        "static let tokenHeaderWidth",
        'case "fire":',
    ]:
        assert token in brand_source
    assert "MenuBarBuddyController" in app_source
    assert "menuBarBuddyController.showBooting()" in app_source
    assert "menuBarBuddyController.apply(status: status)" in app_source
    assert "menuBarBuddyController.showUnavailable()" in app_source
    assert "updateStatusButton" not in app_source
    for token in [
        "MenuBarBuddyPayload",
        "MenuBarBuddyPreviewEnvelope",
        "momentQueue",
        "seenSequenceIDSet",
        "isPreviewing",
        "func preview(",
        'button.title = frame.title.isEmpty ? "" : " \\(frame.title)"',
        "accessibilityDisplayShouldReduceMotion",
        "BuddyMonBrand.Geometry.menuBarIconHeight",
    ]:
        assert token in buddy_source
    for token in [
        "installMenuBarPreviewSignal()",
        "DispatchSource.makeSignalSource(signal: SIGWINCH",
        "consumeMenuBarPreview()",
        "menuBarBuddyController.preview(envelope)",
    ]:
        assert token in app_source
    assert "showStarterSetup" in app_source
    assert '["backup"]' not in app_source
    status_click = swift_function_body(
        app_source,
        "@objc private func handleStatusItemClick",
    )
    assert "menuPanelController.close()" in status_click
    assert "presentDefaultPanel()" in status_click
    default_panel = swift_function_body(
        app_source,
        "private func presentDefaultPanel()",
    )
    assert "showCompact(" in default_panel
    assert "openEncounter()" not in default_panel
    reopen = swift_function_body(
        app_source,
        "func applicationShouldHandleReopen",
    )
    assert "presentDefaultPanel()" in reopen
    assert "openBuddyMon" not in app_source
    assert "showHome" not in app_source


def test_native_panel_locks_its_anchor_for_each_open_session():
    panel_source = (SWIFT_DIR / "MenuPanelController.swift").read_text(
        encoding="utf-8"
    )

    assert "private struct OpenSessionAnchor" in panel_source
    assert "private var openSessionAnchor: OpenSessionAnchor?" in panel_source

    present = swift_function_body(panel_source, "private func presentIfNeeded()")
    assert "openSessionAnchor" in present
    assert "captureOpenSessionAnchor(relativeTo: anchorButton)" in present
    assert "openSessionAnchor = sessionAnchor" in present
    assert "positionPanel(relativeTo: sessionAnchor)" in present

    capture = swift_function_body(
        panel_source,
        "private func captureOpenSessionAnchor",
    )
    assert "window.convertToScreen(buttonInWindow)" in capture
    assert "visibleScreenFrame" in capture

    close = swift_function_body(panel_source, "func close()")
    assert "openSessionAnchor = nil" in close


def test_native_compact_views_render_without_entrance_motion():
    panel_source = (SWIFT_DIR / "MenuPanelController.swift").read_text(
        encoding="utf-8"
    )
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")
    preview_source = (SWIFT_DIR / "BrandStylesPreview.swift").read_text(
        encoding="utf-8"
    )
    brand_docs = (ROOT / "docs" / "brand.md").read_text(encoding="utf-8")

    for token in [
        "struct SectionRevealStyle",
        "static let quickSectionReveal",
        'static let sectionRevealAnimationKey = "buddymon-brand-section-reveal"',
        "static func revealSections",
    ]:
        assert token not in brand_source
    assert "BuddyMonCompactScreenRevealStackView" not in brand_source
    assert "BuddyMonSectionRevealStackView" not in brand_source
    assert "revealsSectionsOnAppearance" not in panel_source
    assert "shouldRevealSections" not in panel_source
    assert "BuddyMonBrand.Menu.applyPanelShell(to: panel)" in panel_source
    panel_shell = swift_function_body(
        brand_source,
        "static func applyPanelShell",
    )
    assert "panel.animationBehavior = .none" in panel_shell
    assert "motionSection()" not in preview_source
    assert '"MOTION + ENTRANCE"' not in preview_source
    assert "fieldGuideActiveRowSample()" in preview_source
    assert "BuddyMonBrand.Menu.makeActiveBuddyRow()" in preview_source
    assert "fieldGuideStatusSample()" in preview_source
    assert "BuddyMonBrand.Menu.makeStatusIndicator(state)" in preview_source
    assert (
        "Compact screens and drill-ins render completely and immediately"
        in brand_docs
    )
    assert "entrance fades" in brand_docs
    assert "private static func animateSprite" in panel_source
    assert 'forKey: "buddymon-menu-sprite-bob"' in panel_source


def test_native_first_signal_onboarding_is_present():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    window_source = (SWIFT_DIR / "StatusWindowController.swift").read_text(
        encoding="utf-8"
    )

    assert "[ FIRST SIGNAL ]" in window_source
    assert "A tiny local companion is looking for a trainer." in window_source
    assert 'NSUserInterfaceItemIdentifier(id)' in window_source
    assert "chooseStarterFromWelcome" in app_source


def test_native_token_action_uses_compact_drill_in_and_preserves_dashboard():
    app_source = (
        SWIFT_DIR / "AppDelegate.swift"
    ).read_text(encoding="utf-8")
    panel_source = (SWIFT_DIR / "MenuPanelController.swift").read_text(
        encoding="utf-8"
    )
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")

    token_menu = swift_function_body(
        app_source,
        "@objc private func openTokenUsage()",
    )
    assert "showTokenUsage()" in token_menu
    assert 'presentCompactTokenUsage(["loading": true])' in token_menu
    assert "statusController.showLoading" not in token_menu
    assert 'runner.appView(\n                "tokens"' in app_source
    assert "menuPanelController.showCompactTokens(" in app_source
    assert "backAction: #selector(showCompactPanel)" in app_source

    compact_tokens = panel_source.split("// MARK: - Token Detail", 1)[1].split(
        "// MARK: - Settings", 1
    )[0]
    assert "let card = BuddyMonFieldGuideCardBackgroundView()" in compact_tokens
    assert "static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth" in compact_tokens
    assert "BuddyMonBrand.Menu.fieldGuideFrameInset" in compact_tokens
    assert '"TOKEN USAGE"' in compact_tokens
    assert 'view["loading"] as? Bool == true' in compact_tokens
    assert '"READING LOCAL TOKEN ACTIVITY…"' in compact_tokens
    assert "static let tokenPanelMinimumHeight = panelMinimumHeight" in brand_source
    assert "static let tokenDailyPulseHeight" in brand_source
    assert "static let dataTrack = raised" in brand_source
    assert "static let dataFill = ink" in brand_source
    assert "private final class BuddyMonTokenDailyPulseView" in compact_tokens
    assert 'dashboard["daily"] as? [[String: Any]]' in compact_tokens
    assert 'dashboard["insights"] as? [[String: Any]]' in compact_tokens
    for label in ["AVG", "PEAK", "STREAK", "BY TOOL"]:
        assert label in compact_tokens
    assert "root.addArrangedSubview(Self.flexibleVerticalSpacer())" in compact_tokens
    assert "ARROWS MOVE" not in compact_tokens
    assert "RETURN SELECTS" not in compact_tokens
    assert "height: BuddyMonBrand.Menu.tokenPanelMinimumHeight" in compact_tokens
    assert "card.fittingSize.height" not in compact_tokens
    navigation_header = swift_function_body(
        panel_source,
        "private func compactNavigationHeader",
    )
    assert "pixel: BuddyMonBrand.Menu.displayButtonPixel" in navigation_header
    assert 'values.joined(separator: " · ")' in compact_tokens
    assert "compactNavigationHeader(" in compact_tokens
    assert 'identifier: "tokens_back"' in compact_tokens
    assert '"B  BACK"' not in compact_tokens


def test_native_settings_show_all_preferences_and_apply_immediately():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    panel_source = (SWIFT_DIR / "MenuPanelController.swift").read_text(
        encoding="utf-8"
    )
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")
    preview_source = (SWIFT_DIR / "BrandStylesPreview.swift").read_text(
        encoding="utf-8"
    )
    harness_source = (SWIFT_DIR / "MenuPanelStateHarnessView.swift").read_text(
        encoding="utf-8"
    )
    menu_policy = (ROOT / "lib" / "menu_panel.py").read_text(encoding="utf-8")

    open_settings = swift_function_body(
        app_source,
        "@objc private func openSettings()",
    )
    assert 'presentCompactSettings(["loading": true])' in open_settings
    assert "loadCompactSettings()" in open_settings
    assert "loadNativeScreen" not in open_settings

    present = swift_function_body(app_source, "private func presentCompactSettings(")
    assert "menuPanelController.showCompactSettings(" in present
    assert "#selector(showCompactPanel)" in present
    assert "#selector(handleCompactSettingsAction(_:))" in present

    selection = swift_function_body(
        app_source,
        "@objc private func handleCompactSettingsAction",
    )
    assert 'let preferencePrefix = "settings_preference:"' in selection
    assert "maxSplits: 1" in selection
    assert "guard selection.count == 2" in selection
    assert "let value = String(selection[1])" in selection
    assert 'runner.appAction(\n                    "preference"' in selection
    assert "[key, value]" in selection
    assert 'response["view"] as? [String: Any]' in selection
    assert "presentCompactSettings(view)" in selection
    assert "await refreshStatus()" in selection

    compact_settings = panel_source.split("// MARK: - Settings", 1)[1].split(
        "// MARK: - Encounter", 1
    )[0]
    for token in [
        "final class BuddyMonCompactSettingsView",
        'view["loading"] as? Bool == true',
        '"READING LOCAL SETTINGS…"',
        '"SETTINGS UNAVAILABLE"',
        '"NO LOCAL SETTINGS FOUND"',
        '"ARROWS MOVE  ·  RETURN SETS  ·  ESC CLOSE"',
        "for setting in rows",
        'setting["allowed_values"] as? [String]',
        'setting["allowed_display_values"] as? [String]',
        "BuddyMonBrand.Menu.SettingsOption(",
        "controls.append(contentsOf: row.optionButtons)",
        "BuddyMonBrand.Menu.makeSettingsRow(",
        "BuddyMonBrand.Menu.settingsPanelMinimumHeight",
    ]:
        assert token in compact_settings
    assert "card.fittingSize.height" not in compact_settings

    navigation = swift_function_body(panel_source, "private func compactNavigationHeader")
    assert 'backAccessibilityLabel: String = "Back to BuddyMon"' in panel_source
    assert "back.setAccessibilityLabel(backAccessibilityLabel)" in navigation
    assert 'back.keyEquivalent = "b"' not in navigation
    assert '"Back to Settings"' not in compact_settings

    for token in [
        "static let settingsPanelMinimumHeight = panelMinimumHeight",
        "static let settingsRowHeight: CGFloat = 18",
        "static let settingsRowBackground = NSColor.clear",
        "static let settingsRowHover = raised.withAlphaComponent(0.55)",
        "static let settingsOptionFontSize: CGFloat = 7.5",
        "struct SettingsOption",
        "static func makeSettingsRow(",
        "static func applySettingsOption(",
        "final class BuddyMonMenuSettingsRowView",
        "private final class BuddyMonMenuSettingsOptionButton",
        '"settings_preference:\\(key):\\(option.value)"',
        'activeOption ? "› \\(optionLabel)" : optionLabel',
        "attributes[.underlineStyle] = NSUnderlineStyle.single.rawValue",
        "addCursorRect(bounds, cursor: .pointingHand)",
        "override func cursorUpdate(with event: NSEvent)",
    ]:
        assert token in brand_source
    option_button = brand_source.split(
        "private final class BuddyMonMenuSettingsOptionButton",
        1,
    )[1].split("final class BuddyMonFireRedLabel", 1)[0]
    assert "override func mouseDown" not in option_button
    assert 'fieldGuideControlSample("FIELD GUIDE / HOVER", hoveredRow)' in preview_source
    assert 'fieldGuideControlSample("FIELD GUIDE / FOCUS", focusedRow)' in preview_source
    assert "BuddyMonBrand.Menu.surface.cgColor" in preview_source
    assert "applySettingsOption(" in preview_source
    assert "settingsCard()" in harness_source
    assert "settingsCard(loading: true)" in harness_source
    assert '"SETTINGS / ALL PREFERENCES"' in harness_source
    assert '"allowed_values": ["auto", "ghostty", "iterm", "terminal"]' in harness_source

    settings_definition = menu_policy.split('"id": "settings"', 1)[1].split("},", 1)[0]
    assert '"presentation": "utility"' in settings_definition
    assert "terminal_screen" not in settings_definition


def test_native_trainer_action_uses_read_only_compact_card():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    panel_source = (SWIFT_DIR / "MenuPanelController.swift").read_text(
        encoding="utf-8"
    )
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")
    brand_preview_source = (SWIFT_DIR / "BrandStylesPreview.swift").read_text(
        encoding="utf-8"
    )
    harness_source = (SWIFT_DIR / "MenuPanelStateHarnessView.swift").read_text(
        encoding="utf-8"
    )

    trainer_action = swift_function_body(
        app_source,
        "@objc private func openTrainerCard()",
    )
    assert "showTrainerCard()" in trainer_action
    assert 'runner.appView(\n                "trainer"' in app_source
    assert "menuPanelController.showCompactTrainer(" in app_source
    assert "backAction: #selector(showCompactPanel)" in app_source

    trainer_section = panel_source.split("// MARK: - Trainer Card", 1)[1].split(
        "// MARK: - Compact Menu", 1
    )[0]
    for token in [
        'view["facts"]',
        'view["trainer_stats"]',
        'view["badges"]',
        'view["star_count"]',
        'view["portrait_base64"]',
        '"TRAINER CARD"',
        "BuddyMonBrand.Menu.applyFieldGuideCardSurface",
        "BuddyMonBrand.Menu.applyTrainerBadge",
        "BuddyMonBrand.Menu.makeTrainerStatusRail",
        "fullBleedTrainerStatusRail",
        "rail.widthAnchor.constraint(equalToConstant: Layout.cardWidth)",
        "rail.centerXAnchor.constraint(equalTo: container.centerXAnchor)",
        "BuddyMonBrand.Menu.trainerBadgeForeground",
        "BuddyMonBrand.Menu.trainerBadgeRingColor",
        "BuddyMonBrand.Menu.trainerBadgeSymbolOpticalLift",
        "TrainerRedFRLG.png",
        "selectionSummary",
        "selectBadge(_:)",
        'view["selected_badge_id"]',
        "setSelected(true)",
        "SELECT A BADGE",
        "cursor: .pointingHand",
        "rail.distribution = .fillEqually",
        "medallion.centerXAnchor.constraint(equalTo: slot.centerXAnchor)",
        "medallion.centerYAnchor.constraint(equalTo: slot.centerYAnchor)",
        "accessibilityDisplayShouldReduceMotion",
        'forKey: "buddymon-trainer-badge-reveal"',
        'forKey: "buddymon-trainer-badge-glow"',
        'forKey: "buddymon-trainer-badge-hover"',
    ]:
        assert token in trainer_section
    assert 'view["level"]' not in trainer_section
    assert 'view["total_xp"]' not in trainer_section
    assert "BuddyMonTrainerBadgeView: NSButton" in trainer_section
    assert "BuddyMonTrainerBadgeView: NSTextField" not in trainer_section
    assert "setAccessibilityRole(.button)" in trainer_section
    assert "focusableControls = [back] + badgeRail.buttons" in trainer_section
    assert "badgeRail.distribution = .equalSpacing" not in trainer_section
    assert "compactNavigationHeader(" in trainer_section
    assert 'identifier: "trainer_back"' in trainer_section
    assert "trailing: idCapsule" in trainer_section

    assert "static let trainerCardWidth: CGFloat = 288" in brand_source
    assert "static let trainerCardHeight: CGFloat = 192" in brand_source
    assert "static let trainerBadgeSize: CGFloat = 28" in brand_source
    assert "static let trainerBadgeDenseSize: CGFloat = 25" in brand_source
    assert "static let trainerBadgeSymbolOpticalLift: CGFloat = 1" in brand_source
    assert "static let trainerPortraitWidth: CGFloat = 64" in brand_source
    assert "static let trainerPortraitHeight: CGFloat = 64" in brand_source
    assert "static let trainerStatusRailHeight: CGFloat = 26" in brand_source
    assert "static func applyFieldGuideCardSurface" in brand_source
    assert "static func applyTrainerBadge" in brand_source
    assert "static func makeTrainerStatusRail" in brand_source
    assert "BuddyMonMenuTrainerStatusRailView" in brand_source
    assert "BuddyMonBrand.Menu.makeTrainerStatusRail" in brand_preview_source
    trainer_status_preview = swift_function_body(
        brand_preview_source,
        "private func fieldGuideTrainerStatusRailSample()",
    )
    assert "BuddyMonBrand.Menu.trainerCardWidth" in trainer_status_preview
    assert "BuddyMonBrand.Menu.cardPadding" not in trainer_status_preview
    assert '"trainer_standard"' in harness_source
    assert '"trainer_national_complete"' in harness_source
    assert '"trainer_stats"' in harness_source
    assert '("shiny_legend", "Shiny Legend Badge"' in harness_source
    assert '"id": "shiny_national"' in harness_source


def test_native_encounter_action_stays_in_the_compact_dropdown():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    panel_source = (SWIFT_DIR / "MenuPanelController.swift").read_text(
        encoding="utf-8"
    )

    open_encounter = swift_function_body(
        app_source,
        "@objc private func openEncounter()",
    )
    encounter = swift_function_body(
        app_source,
        "private func showEncounter(message: String? = nil)",
    )
    action = swift_function_body(
        app_source,
        "@objc private func handleEncounterAction(_ sender: NSButton)",
    )

    assert "statusController.showLoading" not in open_encounter
    assert "showEncounter()" in open_encounter
    assert "menuPanelController.showCompactEncounter(" in encounter
    assert "statusController.showEncounter(" not in encounter
    assert "menuPanelController.showCompactEncounterResult(" in action
    assert "menuPanelController.showCompactEncounter(" in action
    assert "statusController.showEncounterResult(" not in action
    assert 'descriptor["compact_label"]' in panel_source
    assert 'descriptor["shortcut"]' in panel_source
    assert 'descriptor["emoji"]' not in swift_function_body(
        panel_source,
        "init(\n        view: [String: Any],",
    )

    compact_encounter = panel_source.split("// MARK: - Encounter\n", 1)[1].split(
        "// MARK: - Encounter Result", 1
    )[0]
    encounter_result = panel_source.split("// MARK: - Encounter Result", 1)[1]
    for section in [compact_encounter, encounter_result]:
        assert "let card = BuddyMonFieldGuideCardBackgroundView()" in section
        assert "static let cardWidth = BuddyMonBrand.Menu.trainerCardWidth" in section
        assert "BuddyMonBrand.Menu.fieldGuideFrameInset" in section
        assert "compactNavigationHeader(" in section
    assert "pixel: BuddyMonBrand.Menu.displayButtonPixel" in compact_encounter
    assert "pixel: BuddyMonBrand.Menu.displayButtonPixel" in encounter_result
    assert 'identifier: "encounter_back"' in compact_encounter
    assert 'identifier: "encounter_result_back"' in encounter_result
    assert '"H  HOME"' not in compact_encounter
    assert '"RETURN  HOME"' not in encounter_result
    assert '"B BACK' not in encounter_result

    encounter_identity = swift_function_body(
        panel_source,
        "private static func identityCard(",
    )
    assert "color: BuddyMonBrand.Menu.ink" in encounter_identity
    assert "BuddyMonBrand.Menu.makeRarityLabel(" in encounter_identity
    assert "BuddyMonBrand.Menu.pokemonColor(pokemon)" not in encounter_identity

    result_view = swift_function_body(
        panel_source,
        "init(result: [String: Any]",
    )
    assert "color: BuddyMonBrand.Menu.ink" in result_view
    assert "BuddyMonBrand.Menu.makeRarityLabel(" in result_view
    assert "BuddyMonBrand.Menu.pokemonColor(wild)" not in result_view


def test_native_destinations_follow_the_compact_and_terminal_policy():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    panel_source = (SWIFT_DIR / "MenuPanelController.swift").read_text(
        encoding="utf-8"
    )

    menu_action = swift_function_body(
        app_source,
        "@objc private func handleNativeMenuAction",
    )
    for action_id, screen in [
        ("terminal_party", "party"),
        ("terminal_box", "box"),
        ("terminal_dex", "dex"),
        ("terminal_activity", "journal"),
    ]:
        assert f'case "{action_id}": openTerminalExperience(screen: "{screen}")' in (
            menu_action
        )
    assert 'case "trainer": openTrainerCard()' in menu_action
    assert 'case "tokens": openTokenUsage()' in menu_action
    assert 'case "settings": openSettings()' in menu_action

    open_settings = swift_function_body(
        app_source,
        "@objc private func openSettings()",
    )
    assert "presentCompactSettings" in open_settings
    assert "loadCompactSettings" in open_settings
    assert "menuPanelController.showCompactSettings(" in app_source
    assert "NSPopUpButton" not in app_source
    assert 'alert.messageText = "Choose Showcase Pokemon"' not in app_source
    assert 'var arguments = ["open-menu"]' in app_source
    assert "showExpanded(content:" in panel_source
    assert "StatusWindowController()" in app_source
    for removed in [
        "openBuddyMon",
        "showHome",
        "showLibrary",
        "showShowcase",
        "openParty",
        "openBox",
        "openPokedex",
        "openJournal",
    ]:
        assert removed not in app_source


def test_native_keyboard_controls_support_wasd_arrows_and_selection():
    window_source = (
        SWIFT_DIR / "StatusWindowController.swift"
    ).read_text(encoding="utf-8")
    panel_source = (SWIFT_DIR / "MenuPanelController.swift").read_text(
        encoding="utf-8"
    )

    assert "private final class KeyboardWindow: NSWindow" in window_source
    assert "override func keyDown(with event: NSEvent)" in window_source
    assert "private func enableKeyboardControls(" in window_source
    assert '(_, "w"), (_, "a")' in window_source
    assert '(_, "s"), (_, "d")' in window_source
    assert "case (36, _), (76, _), (49, _)" in window_source
    assert "case (53, _)" in window_source
    assert "performClick(nil)" in window_source
    assert 'button.keyEquivalent = "\\r"' not in window_source
    assert "keyboardHandlerChanged(handler)" in window_source
    assert "NSEvent.addLocalMonitorForEvents(matching: .keyDown)" in panel_source
    assert "keyboardHandler(event)" in panel_source
    assert "case 53:" in panel_source
    assert "panel.makeFirstResponder(content.initialResponder)" in panel_source
    assert 'status["active"] as? [String: Any] == nil' in panel_source
    assert "case 123, 126:" in panel_source
    assert "case 124, 125:" in panel_source
    assert "case 36, 49, 76:" in panel_source
    assert "moveCompactFocus(by: -1)" in panel_source
    assert "moveCompactFocus(by: 1)" in panel_source
    assert "activateCompactFocus()" in panel_source
    assert "focusableControls" in panel_source


def test_style_archive_is_developer_only_and_non_normative():
    app_source = (
        SWIFT_DIR / "AppDelegate.swift"
    ).read_text(encoding="utf-8")
    archive_source = (
        SWIFT_DIR / "StyleArchivePreview.swift"
    ).read_text(encoding="utf-8")
    build_source = (ROOT / "scripts" / "build-macos-app.sh").read_text(
        encoding="utf-8"
    )

    assert 'title: "Style Archive"' not in app_source
    assert "showStyleArchive" not in app_source
    assert "ARCHIVED VISUAL EXPLORATIONS // NON-NORMATIVE" in archive_source
    assert "New work always follows BuddyMonBrand." in archive_source
    assert "ConsoleLab" not in app_source
    assert "ConsoleLab" not in archive_source
    assert "LabStyle" not in archive_source
    assert "ArchivedStyle" in archive_source
    assert "SWIFTC_ARGS+=(-D BUDDYMON_DEVELOPMENT)" in build_source
    assert 'if [[ "${REQUIRE_RUNTIME}" != "1" ]]' in build_source
    development_sources = build_source.split(
        'if [[ "${REQUIRE_RUNTIME}" != "1" ]]', 1
    )[1]
    assert "StyleArchivePreview.swift" in development_sources
    assert "BrandStylesPreview.swift" in development_sources
    window_source = (SWIFT_DIR / "StatusWindowController.swift").read_text(
        encoding="utf-8"
    )
    assert "NSFont.systemFont" not in archive_source
    assert "NSFont.systemFont" not in window_source
    for title in [
        "01 / CANVAS + SURFACES",
        "02 / SPACING + DENSITY",
        "03 / TYPOGRAPHY",
        "04 / SECTION CHROME",
        "05 / COMMAND CONTROLS",
        "06 / DATA + SPRITE FRAMES",
    ]:
        assert title in archive_source
    for title in [
        "A / VOID GRID",
        "B / NIGHTSHIFT",
        "C / AFTERBURN",
    ]:
        assert title in archive_source


def test_brand_styles_are_the_canonical_native_visual_system():
    app_source = (SWIFT_DIR / "AppDelegate.swift").read_text(encoding="utf-8")
    window_source = (SWIFT_DIR / "StatusWindowController.swift").read_text(
        encoding="utf-8"
    )
    brand_source = (SWIFT_DIR / "BrandStyle.swift").read_text(encoding="utf-8")
    preview_source = (SWIFT_DIR / "BrandStylesPreview.swift").read_text(
        encoding="utf-8"
    )
    panel_source = (SWIFT_DIR / "MenuPanelController.swift").read_text(
        encoding="utf-8"
    )
    brand_docs = (ROOT / "docs" / "brand.md").read_text(encoding="utf-8")
    agent_rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    capture_script = (ROOT / "scripts" / "capture-brand-styles.sh").read_text(
        encoding="utf-8"
    )
    menu_capture_script = (ROOT / "scripts" / "capture-menu-panel.sh").read_text(
        encoding="utf-8"
    )

    assert not (SWIFT_DIR / "ASCIILab.swift").exists()
    assert not (SWIFT_DIR / "ConsoleLab.swift").exists()
    assert 'title: "Brand Styles"' not in app_source
    assert "BrandStylesWindowController.shared.present()" not in app_source
    assert "#if BUDDYMON_DEVELOPMENT" in preview_source
    assert "BuddyMonBrand" in preview_source
    assert 'static let systemName = "Redline Mono"' in brand_source
    assert "static let section: CGFloat = 72" in brand_source
    assert "static let contentWidth: CGFloat = 880" in brand_source
    assert "static func applySurface" in brand_source
    assert "static func applyButton" in brand_source
    assert "static func makeButton" in brand_source
    assert "static func makeField" in brand_source
    assert "static func makeControlLabel" in brand_source
    assert "static func pokemonColor" in brand_source
    assert "static func makeDisplayLabel" in brand_source
    assert "static func makeRarityLabel" in brand_source
    for rarity, code in [
        ("common", "C"),
        ("uncommon", "U"),
        ("rare", "R"),
        ("legendary", "L"),
        ("mythic", "M"),
        ("starter", "S"),
    ]:
        assert f'case "{rarity}": return "{code}"' in brand_source
    menu_brand_source = brand_source.split("enum Menu {", 1)[1]
    menu_surface_color = swift_brand_color(menu_brand_source, "surface")
    for token in [
        "mutedInk",
        "pokemonGrass",
        "pokemonWater",
        "pokemonRare",
        "rarityLegendary",
        "rarityStarter",
    ]:
        assert contrast_ratio(
            swift_brand_color(menu_brand_source, token),
            menu_surface_color,
        ) >= 4.5, f"{token} must pass normal-text contrast on the menu surface"
    assert "enum FireRedDisplay" in brand_source
    assert "inspired by the FireRed/LeafGreen UI" in brand_source
    assert "static let glyphTracking: CGFloat = 1.5" in brand_source
    assert "private static func metrics(" in brand_source
    assert "glyphWeightExpansion" not in brand_source
    assert "BuddyMonTokenHeaderButton" in panel_source
    assert "headerTokenControl(" in panel_source
    assert '"U OPEN"' not in panel_source
    token_button = swift_function_body(
        panel_source,
        "private final class BuddyMonTokenHeaderButton",
    )
    assert "borderWidth" not in token_button
    assert "focusSurface" not in token_button
    assert "cursor: .pointingHand" in token_button
    footer_button = swift_function_body(
        panel_source,
        "private final class BuddyMonMenuFooterButton",
    )
    assert "cursor: .pointingHand" in footer_button
    assert "BuddyMonMenuFooterButton(" in panel_source
    menu_button = swift_function_body(
        brand_source,
        "private final class BuddyMonMenuActionButton",
    )
    assert "cursor: .pointingHand" in menu_button
    assert "BuddyMonBrand.Motion.animateQuickLinkHover" in menu_button
    assert "static let panelWidth: CGFloat = 304" in brand_source
    assert "static let actionLabelPixel: CGFloat = 0.92" in brand_source
    assert "static let quickLinkHeight: CGFloat = 22" in brand_source
    assert "static let quickLinkColumns = 3" in brand_source
    assert "static let quickLinkHoverLift: CGFloat = 1" in brand_source
    assert "static func makeQuickLink(" in brand_source
    assert "Self.quickLinkGrid(utilityButtons)" in panel_source
    assert "BuddyMonBrand.Menu.quickLinkColumns" in panel_source
    quick_link = swift_function_body(
        brand_source,
        "private static func refreshQuickLink",
    )
    assert "subtleRule" in quick_link
    assert "Geometry.borderWidth" in quick_link
    assert "Geometry.cornerRadius" in quick_link
    quick_link_motion = swift_function_body(
        brand_source,
        "static func animateQuickLinkHover",
    )
    assert "accessibilityDisplayShouldReduceMotion" in quick_link_motion
    assert 'CABasicAnimation(keyPath: "transform.translation.y")' in quick_link_motion
    assert "quickLinkHoverDuration" in quick_link_motion
    assert "fieldGuideQuickLinkSample()" in preview_source
    assert "BuddyMonBrand.Menu.makeQuickLink(" in preview_source
    assert "no separate Open label" in brand_docs
    for token in [
        "canvas",
        "surface",
        "textPrimary",
        "textSecondary",
        "brand",
        "pokemonBlue",
        "rarity",
        "starterWater",
        "starterGrass",
        "pikachu",
        "xpProgress",
        "dataProgress",
    ]:
        assert f"static let {token}" in brand_source

    surface_color = swift_brand_color(brand_source, "surface")
    for token in [
        "textPrimary",
        "textSecondary",
        "brand",
        "rarity",
        "starterWater",
        "starterGrass",
        "pikachu",
    ]:
        assert contrast_ratio(
            swift_brand_color(brand_source, token),
            surface_color,
        ) >= 4.5, f"{token} must pass normal-text contrast on the brand surface"
    assert contrast_ratio(
        swift_brand_color(brand_source, "pokemonBlue"),
        surface_color,
    ) >= 3.0, "pokemonBlue must pass large-identity contrast on the brand surface"

    shipping_source = app_source + panel_source + window_source
    assert "BuddyMonBrand" in panel_source
    assert "BuddyMonBrand" in window_source
    assert "ConsoleTheme" not in shipping_source
    assert "ASCIILab" not in shipping_source
    assert "NSColor(calibratedRed:" not in shipping_source
    assert "NSFont.monospacedSystemFont" not in shipping_source
    assert ".spacing = 14" not in window_source
    assert ".spacing = 18" not in window_source
    assert "root.alignment = .centerX" not in window_source
    assert "BuddyMonBrand.makeButton" in window_source
    assert "BuddyMonBrand.makeButton" in preview_source
    assert "BuddyMonBrand.makeField" in preview_source

    allowed_literal_sources = {"BrandStyle.swift", "StyleArchivePreview.swift"}
    literal_patterns = [
        r"NSColor\(calibratedRed:",
        r"NSFont\.systemFont",
        r"NSFont\.monospacedSystemFont",
        r"\.spacing\s*=\s*\d",
        r"\.borderWidth\s*=\s*\d",
        r"\.cornerRadius\s*=\s*\d",
    ]
    for source_path in SWIFT_DIR.glob("*.swift"):
        if source_path.name in allowed_literal_sources:
            continue
        source = source_path.read_text(encoding="utf-8")
        for pattern in literal_patterns:
            assert re.search(pattern, source) is None, (
                f"{source_path.name} bypasses BuddyMonBrand with {pattern}"
            )
        if (
            source_path.name != "AppDelegate.swift"
            and any(
                name in source
                for name in ["NSView", "NSWindow", "NSButton", "NSTextField"]
            )
        ):
            assert "BuddyMonBrand" in source, (
                f"{source_path.name} defines native UI without BuddyMonBrand"
            )

    assert "spacing rhythm 04 / 08 / 12 / 20 / 32 / 48 / 72" in preview_source
    assert "stack.alignment = .leading" in preview_source
    assert "alignment = .width" not in preview_source
    assert "distribution = .fillEqually" not in preview_source
    assert "BUDDYMON / REDLINE MONO" in preview_source
    assert "BuddyMonBrand.pikachu" in preview_source
    assert "BuddyMonBrand.starterWater" in preview_source
    assert "BuddyMonBrand.starterGrass" in preview_source
    assert "BuddyMonBrand.rarity" in preview_source
    assert "BuddyMonBrand.pokemonBlue" in preview_source
    assert "[⌘1] PARTY" in preview_source
    assert "[F1]" not in preview_source
    assert 'stringValue = "█"' in preview_source
    assert 'forKey: "brand-cursor-blink"' in preview_source
    assert "accessibilityDisplayShouldReduceMotion" in preview_source
    assert "scroll.contentView.scroll(to: .zero)" in preview_source
    assert "static let contentWidth = BuddyMonBrand.Geometry.contentWidth" in preview_source
    assert "interactive: false" in preview_source
    assert "field.refusesFirstResponder = !interactive" in brand_source
    assert "STORIES::COMMON_CONTEXT" in preview_source
    assert "ONE BUDDY MOMENT / THREE SURFACES" in preview_source
    assert "EMOJI STATUSLINE" in preview_source
    assert "MACOS MENU BAR + DROPDOWN" in preview_source
    assert '"PIXEL FELLOW"' in preview_source
    assert '"OFFICIAL PNG"' in preview_source
    assert 'appendingPathComponent("buddymon/packs/gen5"' in preview_source
    assert "bitmap.representation(using: .png" in preview_source
    assert "magnificationFilter = .nearest" in preview_source
    for marker in [
        "WORK SESSION / LEVEL PROGRESS",
        "WILD SIGNAL / DECISION REQUIRED",
        "CATCH RESULT / COLLECTION FOLLOW-THROUGH",
        "01::ACTIVE_BUDDY",
        "02::LIVE_SIGNAL",
        "03::TAIL /journey.log",
        "hunt@buddymon:~$",
        "TYPE SYSTEM",
        "COMMAND CONTROLS",
        "FIELDS + SETTINGS",
        "NAVIGATION + COMMAND PALETTE",
        "COLLECTION ROWS + SPRITE FRAMES",
        "ENCOUNTER STATES",
        "SHOWCASE SLOTS",
        "STATUS + RARITY",
        "PROGRESS + LOADING",
        "DIALOGS + CONFIRMATION",
        "TOKEN SUMMARY + REPORT",
        "DOCTOR + DIAGNOSTIC OUTPUT",
        "BUDDY HEADER + TRAINER STATS",
        "BATTLE HUD + ACTION GRID",
        "BATTLE LOG ROWS",
        "SELECTED-BUDDY SUMMARY",
        "COLLECTION TOOLBAR + FILTERS",
        "POKEDEX CELLS + COMPLETION",
        "JOURNAL FILTERS + EVENT ROWS",
        "STARTER + SOURCE + ART + REPAIR",
        "TOKEN EDGE STATES",
        "KEYBOARD + ACCESSIBILITY",
    ]:
        assert marker in preview_source

    assert "single source of truth" in brand_docs
    assert "BrandStyle.swift" in brand_docs
    assert "StyleArchivePreview.swift" in brand_docs
    assert "scripts/capture-brand-styles.sh" in brand_docs
    assert "Native UI must always use `BuddyMonBrand`" in agent_rules
    assert "Read `docs/brand.md` before changing native UI" in agent_rules
    assert "BrandStyle.swift" in capture_script
    assert "BrandStylesPreview.swift" in capture_script
    assert "BrandStylesSnapshot.swift" in capture_script
    assert "BrandStyle.swift" in menu_capture_script
    assert "MenuPanelController.swift" in menu_capture_script
    assert "MenuPanelSnapshot.swift" in menu_capture_script


def test_brand_styles_full_page_snapshot_is_deterministic(
    brand_snapshot_harness,
    tmp_path,
):
    state_home = tmp_path / "state"
    state_home.mkdir()
    first = tmp_path / "brand-styles-first.png"
    second = tmp_path / "brand-styles-second.png"
    env = os.environ.copy()
    env["XDG_STATE_HOME"] = str(state_home)

    for output in [first, second]:
        result = subprocess.run(
            [str(brand_snapshot_harness), str(output)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    first_png = first.read_bytes()
    assert first_png == second.read_bytes()
    assert first_png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", first_png[16:24])
    assert width >= 944
    assert height >= 8_000
    assert len(first_png) >= 500_000


def test_native_compact_menu_panel_snapshot_is_deterministic(
    menu_panel_snapshot_harness,
    tmp_path,
):
    preview_source = (SWIFT_DIR / "BrandStylesPreview.swift").read_text(
        encoding="utf-8"
    )
    sprite_match = re.search(r'"PIKACHU": "([^"]+)"', preview_source)
    assert sprite_match is not None
    status = {
        "active": {
            "name": "Charizard",
            "type": "Fire",
            "rarity": "starter",
            "level": 78,
            "shiny": False,
            "level_progress": {"percent": 58},
            "sprite_base64": sprite_match.group(1),
        },
        "trainer": {
            "caught_count": 768,
            "species_count": 328,
            "streak": 3,
        },
        "recent": [
            {
                "name": "Palpitoad",
                "type": "Water",
                "sprite_base64": sprite_match.group(1),
            }
        ],
        "tokens": {
            "today": {"label": "Today", "compact": "148K"},
            "yesterday": {"label": "Yesterday", "compact": "102K"},
        },
        "brand_mark_base64": sprite_match.group(1),
        "native_menu": {
            "layout": "compact",
            "token_action": {
                "id": "tokens",
                "label": "Open token detail",
                "shortcut": "u",
            },
            "items": [
                {
                    "id": "trainer",
                    "label": "Trainer",
                    "shortcut": "t",
                    "presentation": "utility",
                },
                {
                    "id": "terminal_party",
                    "label": "Party",
                    "shortcut": "p",
                    "terminal_screen": "party",
                    "presentation": "utility",
                },
                {
                    "id": "terminal_box",
                    "label": "Box",
                    "shortcut": "b",
                    "terminal_screen": "box",
                    "presentation": "utility",
                },
                {
                    "id": "terminal_dex",
                    "label": "Pokedex",
                    "shortcut": "d",
                    "terminal_screen": "dex",
                    "presentation": "utility",
                },
                {
                    "id": "terminal_activity",
                    "label": "Activity",
                    "shortcut": "a",
                    "terminal_screen": "journal",
                    "presentation": "utility",
                },
                {
                    "id": "settings",
                    "label": "Settings",
                    "shortcut": "s",
                    "presentation": "utility",
                },
            ],
            "footer_items": [
                {
                    "id": "refresh",
                    "label": "Refresh",
                    "shortcut": "r",
                    "modifiers": ["command"],
                },
                {
                    "id": "quit",
                    "label": "Quit",
                    "shortcut": "q",
                    "modifiers": ["command"],
                },
            ],
        },
    }
    first = tmp_path / "menu-panel-first.png"
    second = tmp_path / "menu-panel-second.png"

    for output in [first, second]:
        result = subprocess.run(
            [str(menu_panel_snapshot_harness), str(output)],
            cwd=ROOT,
            input=json.dumps(status),
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    first_png = first.read_bytes()
    assert first_png == second.read_bytes()
    assert first_png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", first_png[16:24])
    assert width == 304
    assert 210 <= height <= 300
    assert len(first_png) >= 10_000


def test_compact_menu_panel_state_harness_is_complete_and_deterministic(
    menu_panel_state_snapshot_harness,
    tmp_path,
):
    harness_source = (SWIFT_DIR / "MenuPanelStateHarnessView.swift").read_text(
        encoding="utf-8"
    )
    assert "rarityLegend()" in harness_source
    assert "BuddyMonBrand.Menu.makeRarityLabel(rarity)" in harness_source
    assert 'stateID: "encounter_result_caught"' in harness_source
    assert 'stateID: "encounter_result_ran"' in harness_source
    assert 'loading ? "tokens_loading" : "tokens"' in harness_source
    assert '"daily": [' in harness_source
    assert '"active_streak"' in harness_source
    assert "settingsCard()" in harness_source
    assert "settingsCard(loading: true)" in harness_source

    env = os.environ.copy()
    env["XDG_STATE_HOME"] = str(tmp_path / "state")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    payload = subprocess.run(
        [sys.executable, str(ROOT / "buddymon.py"), "app-menu-panel-harness"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert payload.returncode == 0, payload.stderr
    decoded = json.loads(payload.stdout)
    assert len(decoded["fixtures"]) == 7

    first = tmp_path / "menu-panel-states-first.png"
    second = tmp_path / "menu-panel-states-second.png"
    for output in (first, second):
        result = subprocess.run(
            [str(menu_panel_state_snapshot_harness), str(output)],
            cwd=ROOT,
            input=payload.stdout,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    first_png = first.read_bytes()
    assert first_png == second.read_bytes()
    assert first_png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", first_png[16:24])
    assert width == 944
    assert 1_500 <= height <= 3_600
    assert len(first_png) >= 100_000


def test_menu_bar_state_harness_snapshot_is_complete_and_deterministic(
    menu_bar_state_snapshot_harness,
    tmp_path,
):
    env = os.environ.copy()
    env["XDG_STATE_HOME"] = str(tmp_path / "state")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    payload_result = subprocess.run(
        [sys.executable, str(ROOT / "buddymon.py"), "app-menu-bar-harness"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert payload_result.returncode == 0, payload_result.stderr
    payload = json.loads(payload_result.stdout)
    assert len(payload["sequences"]) == 23

    first = tmp_path / "menu-bar-states-first.png"
    second = tmp_path / "menu-bar-states-second.png"
    for output in [first, second]:
        result = subprocess.run(
            [str(menu_bar_state_snapshot_harness), str(output)],
            cwd=ROOT,
            input=payload_result.stdout,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    first_png = first.read_bytes()
    assert first_png == second.read_bytes()
    assert first_png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", first_png[16:24])
    assert width == 1_180
    assert 2_200 <= height <= 3_000
    assert len(first_png) >= 100_000


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
