import AppKit
import Darwin
import Foundation

private final class ReadmeMenuBarTarget: NSObject {
    @objc func noop(_ sender: Any?) {}
}

/// Captures actual macOS chrome around the shipping status item and panel.
/// The neutral backdrop prevents unrelated desktop content entering the image.
@main
struct ReadmeMenuBarCapture {
    @MainActor
    static func main() {
        do { try captureDemo() }
        catch {
            FileHandle.standardError.write(Data((error.localizedDescription + "\n").utf8))
            exit(1)
        }
    }

    @MainActor
    private static func captureDemo() throws {
        guard CommandLine.arguments.count == 2 else {
            throw CaptureError.failed("usage: readme-menu-bar OUTPUT_DIRECTORY")
        }
        let input = FileHandle.standardInput.readDataToEndOfFile()
        guard let status = try JSONSerialization.jsonObject(with: input) as? [String: Any],
              let payload = MenuBarBuddyPayload.decode(from: status) else {
            throw CaptureError.failed("expected app-status fixture with menu-bar frames")
        }
        let output = URL(fileURLWithPath: CommandLine.arguments[1])
        let app = NSApplication.shared
        app.setActivationPolicy(.accessory)
        app.finishLaunching()
        app.activate(ignoringOtherApps: true)
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        defer { NSStatusBar.system.removeStatusItem(item) }
        guard let button = item.button else { throw CaptureError.failed("no status button") }
        let player = MenuBarBuddyPlayer(button: button)
        player.reduceMotionOverride = true
        player.play(payload.baseline, mode: .hold)
        defer { player.stop() }
        // macOS may initially put a newly registered status item below the
        // display while the menu-bar process lays it out.
        for _ in 0..<50 {
            if let window = button.window {
                let frame = window.convertToScreen(button.convert(button.bounds, to: nil))
                if NSScreen.screens.contains(where: { isInMenuBar(frame, screen: $0) }) {
                    break
                }
            }
            RunLoop.main.run(until: Date(timeIntervalSinceNow: 0.1))
        }
        guard let buttonWindow = button.window else { throw CaptureError.failed("status item hidden") }
        let buttonFrame = buttonWindow.convertToScreen(button.convert(button.bounds, to: nil))
        guard let screen = buttonWindow.screen ?? NSScreen.main else {
            throw CaptureError.failed("no screen for status item")
        }
        guard isInMenuBar(buttonFrame, screen: screen) else {
            throw CaptureError.failed("status item \(buttonFrame) is outside screen \(screen.frame)")
        }
        let backdrop = NSWindow(contentRect: screen.visibleFrame, styleMask: .borderless,
                                backing: .buffered, defer: false)
        backdrop.backgroundColor = BuddyMonBrand.Menu.canvas
        backdrop.level = NSWindow.Level(rawValue: NSWindow.Level.screenSaver.rawValue - 1)
        backdrop.ignoresMouseEvents = true
        backdrop.orderFrontRegardless()
        defer { backdrop.orderOut(nil) }
        settle()
        let width: CGFloat = 384
        let settledButtonFrame = buttonWindow.convertToScreen(button.convert(button.bounds, to: nil))
        let x = min(max(settledButtonFrame.midX - width / 2, screen.frame.minX), screen.frame.maxX - width)
        let strip = NSRect(x: x, y: settledButtonFrame.minY, width: width,
                           height: screen.frame.maxY - settledButtonFrame.minY)
        try capture(strip, to: output.appendingPathComponent("menu-bar.png"))

        let target = ReadmeMenuBarTarget()
        let controller = MenuPanelController()
        controller.attach(to: button)
        controller.presentRoot(status: status, target: target,
                               action: #selector(ReadmeMenuBarTarget.noop(_:)))
        defer { controller.close() }
        settle()
        guard let panel = app.windows.first(where: { $0 is NSPanel && $0.isVisible }) else {
            throw CaptureError.failed("demo panel did not open")
        }
        panel.level = .screenSaver
        panel.orderFrontRegardless()
        settle()
        let bottom = panel.frame.minY - BuddyMonBrand.Spacing.medium
        let sceneX = min(max(panel.frame.midX - width / 2, screen.frame.minX), screen.frame.maxX - width)
        let scene = NSRect(x: sceneX, y: bottom, width: width, height: screen.frame.maxY - bottom)
        try capture(scene, to: output.appendingPathComponent("menu-bar-open.png"))
    }

    @MainActor
    private static func isInMenuBar(_ frame: NSRect, screen: NSScreen) -> Bool {
        frame.width > 0 && screen.frame.intersects(frame)
            && frame.maxY > screen.frame.maxY - NSStatusBar.system.thickness * 2
    }

    @MainActor
    private static func settle() {
        RunLoop.main.run(until: Date(timeIntervalSinceNow: 0.5))
    }

    @MainActor
    private static func capture(_ rect: NSRect, to output: URL) throws {
        let top = NSScreen.screens.first?.frame.maxY ?? 0
        let region = [rect.minX, top - rect.maxY, rect.width, rect.height]
            .map { String(Int($0.rounded())) }.joined(separator: ",")
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
        process.arguments = ["-x", "-R", region, output.path]
        try process.run()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else {
            throw CaptureError.failed("screen capture failed; check Screen Recording permission")
        }
        print(output.path)
    }
}

private enum CaptureError: LocalizedError {
    case failed(String)
    var errorDescription: String? {
        switch self { case .failed(let message): return message }
    }
}
