import json
import os
import re
import signal
import shutil
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
MENU_PANEL_SWIFT_NAMES = (
    "MenuPanelController.swift",
    "CompactTrainerCardView.swift",
    "CompactRootView.swift",
    "CompactTokenUsageView.swift",
    "CompactSettingsView.swift",
    "CompactEncounterView.swift",
    "CompactSetupView.swift",
    "MenuPanelSharedViews.swift",
)
MENU_PANEL_SWIFT_FILES = tuple(
    SWIFT_DIR / name for name in MENU_PANEL_SWIFT_NAMES
)

pytestmark = [
    pytest.mark.skipif(sys.platform != "darwin", reason="BuddyMon.app is macOS-only"),
    pytest.mark.skipif(SWIFTC is None, reason="swiftc is not installed"),
]


def read_menu_panel_sources() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in MENU_PANEL_SWIFT_FILES
    )


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
    static let pythonURL = URL(fileURLWithPath:
        ProcessInfo.processInfo.environment["BUDDYMON_TEST_PYTHON"]
            ?? "/usr/bin/python3"
    )
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
            str(SWIFT_DIR / "MenuPanelSharedViews.swift"),
            str(SWIFT_DIR / "CompactSetupView.swift"),
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
            *map(str, MENU_PANEL_SWIFT_FILES),
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
            *map(str, MENU_PANEL_SWIFT_FILES),
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
    child_env = os.environ.copy() if env is None else env.copy()
    child_env["BUDDYMON_TEST_PYTHON"] = sys.executable
    process = subprocess.Popen(
        [str(executable), mode],
        cwd=ROOT,
        env=child_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate()
        pytest.fail(
            f"native harness mode {mode!r} timed out after {timeout} seconds\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    assert process.returncode == 0, stderr
    return json.loads(stdout)


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
