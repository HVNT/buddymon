"""Delayed native commands must not undo newer navigation."""

import json
import os
import subprocess
import sys
import textwrap

import pytest

from tests.native_test_support import (
    ROOT, SWIFT_DIR, SWIFTC,
    pytestmark as pytestmark, swift_function_body,
)


# Compile the real delegate and command runner. Only presentation is replaced:
# this test must never create status items, open windows, or activate the app.
# A temporary extension exposes the delegate's private async entry points.
APP_ACCESS = r'''
extension AppDelegate {
    func testPrepare() {
        menuBarBuddyController = MenuBarBuddyController()
        attemptedArtworkSetup = true
        awaitsInitialStatus = false
        latestStatus = ["has_buddy": true]
        presentRootPanel()
    }

    func testStart(_ operation: String) -> Task<Void, Never> {
        let generation = advanceDetailPresentationGeneration()
        if operation != "trainer" { presentSettings(["loading": true]) }
        return Task {
            if operation == "trainer" {
                await loadTrainerCard(generation: generation)
            } else if operation == "settings" {
                await loadSettings(generation: generation)
            } else {
                await updatePreference("notifications", value: "off", generation: generation)
            }
        }
    }

    func testBack() { openRootPanel() }
    func testClose() { menuPanelController.close() }
    var testMode: String { menuPanelController.displayMode.rawValue }
    var testVisible: Bool { menuPanelController.isVisible }
    var testContent: Int { menuPanelController.testContent }
}
'''

PRESENTATION_DOUBLE = r'''
import AppKit

@MainActor
final class MenuPanelController {
    enum DisplayMode: String {
        case menu, tokens, settings, trainer, encounter, encounterResult, setup, notice
    }

    var onClose: (() -> Void)?
    private(set) var displayMode: DisplayMode = .menu
    private(set) var isVisible = false
    private(set) var testContent = 0

    private func present(_ mode: DisplayMode) {
        displayMode = mode
        isVisible = true
        testContent += 1
    }

    func close() { onClose?(); isVisible = false }
    func attach(to button: NSStatusBarButton?) {}
    func prepareForTerminalHandoff() -> String? { nil }
    func updateStarterArtwork(_ artwork: [String: Any]) {}
    func beginEncounterAction(_ actionID: String) -> Bool { true }
    func presentLoading(_ message: String) { present(.notice) }
    func presentMessage(_ message: String) { present(.notice) }

    func presentRoot(status: [String: Any], target: AnyObject, action: Selector,
                     preserveFocus: Bool = false) { present(.menu) }
    func presentStarterSetup(target: AnyObject, chooseAction: Selector,
                             artwork: [String: Any], artworkAction: Selector?) { present(.setup) }
    func presentTokenUsage(view: [String: Any], target: AnyObject,
                           backAction: Selector) { present(.tokens) }
    func presentSettings(view: [String: Any], target: AnyObject,
                         backAction: Selector, selectionAction: Selector) { present(.settings) }
    func presentTrainerCard(view: [String: Any], target: AnyObject,
                            backAction: Selector) { present(.trainer) }
    func presentEncounter(view: [String: Any], message: String? = nil,
                          preferredActionID: String? = nil, target: AnyObject,
                          action: Selector, backAction: Selector) { present(.encounter) }
    func presentEncounterResult(result: [String: Any], target: AnyObject,
                                doneAction: Selector) { present(.encounterResult) }
}

struct MenuBarBuddyPreviewEnvelope: Decodable { let schemaVersion: Int }

@MainActor
final class MenuBarBuddyController {
    init(button: NSStatusBarButton? = nil) {}
    func showBooting() {}
    func showUnavailable() {}
    func apply(status: [String: Any]) {}
    func preview(_ envelope: MenuBarBuddyPreviewEnvelope) {}
}
'''

HARNESS = r'''
import AppKit
import Foundation

enum TestError: Error { case timedOut(String) }

@main
struct NavigationHarness {
    @MainActor
    static func waitFor(_ path: URL) async throws {
        for _ in 0..<1_000 {
            if FileManager.default.fileExists(atPath: path.path) { return }
            try await Task.sleep(nanoseconds: 5_000_000)
        }
        throw TestError.timedOut(path.lastPathComponent)
    }

    static func write(_ value: [String: Any], to path: URL) throws {
        try JSONSerialization.data(withJSONObject: value).write(to: path, options: .atomic)
    }

    @MainActor
    static func run() async throws {
        let args = CommandLine.arguments
        let directory = URL(fileURLWithPath: args[1])
        let operation = args[2], outcome = args[3], navigation = args[4]
        let runner = BuddyMonRunner(
            repoURL: directory,
            pythonURL: URL(fileURLWithPath: args[5])
        )
        let delegate = AppDelegate(runner: runner)
        defer { delegate.testClose() }
        delegate.testPrepare()
        let control = directory.appendingPathComponent("control.json")
        try write(["id": "old"], to: control)
        let task = delegate.testStart(operation)
        try await waitFor(directory.appendingPathComponent("entered-old"))

        var release = directory.appendingPathComponent("release-old.json")
        if operation == "preference-fallback" {
            try write(["id": "fallback"], to: control)
            try write(["ok": true], to: release)
            try await waitFor(directory.appendingPathComponent("entered-fallback"))
            release = directory.appendingPathComponent("release-fallback.json")
        }

        if navigation == "back" {
            delegate.testBack()
        } else if navigation == "close" {
            delegate.testClose()
        } else if navigation == "reopen" || navigation == "newer" {
            if navigation == "reopen" {
                delegate.testClose()
                delegate.testBack()
            }
            try write(["id": "new"], to: control)
            try write(["ok": true, "view": [:]], to: directory.appendingPathComponent("release-new.json"))
            await delegate.testStart(operation == "trainer" ? "trainer" : "settings").value
        }
        let before = delegate.testContent
        let expectedMode = delegate.testMode
        let expectedVisibility = delegate.testVisible
        let payload: [String: Any] = outcome == "error"
            ? ["exit_error": true]
            : outcome == "rejected"
                ? ["ok": false, "message": "Preference rejected"]
                : ["ok": true, "view": [:]]
        try write(payload, to: release)
        await task.value

        let result: [String: Any] = [
            "mode": delegate.testMode,
            "expected_mode": expectedMode,
            "visible": delegate.testVisible,
            "expected_visible": expectedVisibility,
            "content_unchanged": delegate.testContent == before,
            "saved": FileManager.default.fileExists(atPath: directory.appendingPathComponent("saved").path),
            "window_count": NSApp.windows.count,
        ]
        let bytes = try JSONSerialization.data(withJSONObject: result, options: .sortedKeys)
        FileHandle.standardOutput.write(bytes)
    }

    @MainActor
    static func main() {
        _ = NSApplication.shared
        NSApp.setActivationPolicy(.prohibited)
        Task { @MainActor in
            do { try await run(); exit(0) }
            catch { fputs("Navigation harness failed: \(error)\n", stderr); exit(1) }
        }
        NSApp.run()
    }
}
'''

COMMAND_FIXTURE = '''
import json
import sys
import time
from pathlib import Path

root = Path(__file__).parent
if sys.argv[1] == "app-status":
    print(json.dumps({"has_buddy": True}))
    raise SystemExit
request_id = json.loads((root / "control.json").read_text())["id"]
(root / f"entered-{request_id}").touch()
release = root / f"release-{request_id}.json"
for _ in range(1000):
    if release.exists():
        break
    time.sleep(0.005)
response = json.loads(release.read_text())
if response.get("exit_error"):
    print("Delayed command failed", file=sys.stderr)
    raise SystemExit(1)
if sys.argv[1] == "app-action" and response.get("ok"):
    (root / "saved").write_text(sys.argv[-1])
print(json.dumps(response))
'''


@pytest.fixture(scope="session")
def navigation_harness(tmp_path_factory):
    directory = tmp_path_factory.mktemp("native-navigation")
    app_source = directory / "AppDelegate.swift"
    app_source.write_text((SWIFT_DIR / app_source.name).read_text() + APP_ACCESS)
    panel_source = directory / "PresentationDouble.swift"
    panel_source.write_text(textwrap.dedent(PRESENTATION_DOUBLE))
    harness_source = directory / "NavigationHarness.swift"
    harness_source.write_text(textwrap.dedent(HARNESS))
    sources = [
        SWIFT_DIR / name for name in (
            "BuddyMonRunner.swift", "ProcessExecutor.swift",
            "SingleInstanceGuard.swift", "LocalStateObserver.swift",
        )
    ]
    executable = directory / "navigation-harness"
    result = subprocess.run(
        [SWIFTC, "-module-cache-path", str(directory / "module-cache"),
         "-framework", "AppKit",
         *map(str, sources), str(app_source), str(panel_source), str(harness_source),
         "-o", str(executable)],
        cwd=ROOT, text=True, capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return executable


@pytest.mark.parametrize("operation, outcome", [
    (operation, outcome)
    for operation in ("trainer", "settings", "preference", "preference-fallback")
    for outcome in ("success", "error")
] + [("preference", "rejected")])
@pytest.mark.parametrize("navigation", ["back", "close", "reopen", "newer", "stay"])
def test_delayed_detail_response_respects_navigation(
    navigation_harness, tmp_path, operation, outcome, navigation,
):
    (tmp_path / "buddymon.py").write_text(textwrap.dedent(COMMAND_FIXTURE))
    result = subprocess.run(
        [str(navigation_harness), str(tmp_path), operation, outcome, navigation, sys.executable],
        env={**os.environ, "XDG_STATE_HOME": str(tmp_path / "state")},
        text=True, capture_output=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    assert actual["window_count"] == 0, "navigation tests must not open desktop windows"
    if navigation == "stay":
        assert not actual["content_unchanged"], "current responses should still be presented"
    else:
        assert actual["mode"] == actual["expected_mode"]
        assert actual["visible"] == actual["expected_visible"]
        # A passive status refresh may rebuild the root without navigating away.
        if navigation != "back":
            assert actual["content_unchanged"], "an old response replaced the current screen"
    if operation.startswith("preference") and (outcome == "success" or operation.endswith("fallback")):
        assert actual["saved"], "leaving Settings must not cancel an accepted preference save"


def test_navigation_invalidates_detail_requests_before_starting_async_work():
    source = (SWIFT_DIR / "AppDelegate.swift").read_text()
    for name in ("presentRootPanel", "openEncounter", "openTokenUsage",
                 "openTrainerCard", "openSettings", "openTerminalExperience",
                 "handleCompactSettingsAction"):
        body = swift_function_body(source, f"func {name}(")
        assert "advanceDetailPresentationGeneration()" in body
        if "Task {" in body:
            assert body.index("advanceDetailPresentationGeneration()") < body.index("Task {")


def test_shipping_panel_notifies_delegate_on_every_close_path():
    panel_source = (SWIFT_DIR / "MenuPanelController.swift").read_text()
    close = swift_function_body(panel_source, "func close()")
    assert "onClose?()" in close
    assert close.index("onClose?()") < close.index("panel.orderOut(nil)")
    keyboard = swift_function_body(panel_source, "private func installKeyboardMonitor()")
    assert "case 53:\n                self.close()" in keyboard
    outside = swift_function_body(panel_source, "private func installOutsideClickMonitors()")
    assert "self?.close()" in outside
    assert "self.close()" in outside
