import AppKit
import Darwin
import Foundation

@main
struct MenuBarStateHarness {
    @MainActor
    static func main() {
        do {
            let input = FileHandle.standardInput.readDataToEndOfFile()
            let payload = try JSONDecoder().decode(MenuBarHarnessPayload.self, from: input)
            _ = NSApplication.shared

            if CommandLine.arguments.count == 2 {
                let harness = MenuBarStateHarnessView(
                    payload: payload,
                    animationsEnabled: false
                )
                harness.prepareForSnapshot()
                let snapshot = harness.snapshotView
                let output = URL(fileURLWithPath: CommandLine.arguments[1])
                try FileManager.default.createDirectory(
                    at: output.deletingLastPathComponent(),
                    withIntermediateDirectories: true
                )
                try write(view: snapshot, to: output)
                FileHandle.standardOutput.write(Data((output.path + "\n").utf8))
                return
            }

            guard CommandLine.arguments.count == 1 else {
                throw MenuBarHarnessError.usage
            }
            NSApp.setActivationPolicy(.regular)
            let harness = MenuBarStateHarnessView(payload: payload)
            let window = NSWindow(
                contentRect: NSRect(origin: .zero, size: harness.preferredSize),
                styleMask: [.titled, .closable, .resizable, .miniaturizable],
                backing: .buffered,
                defer: false
            )
            window.title = "BuddyMon Menu-Bar State Harness"
            window.contentView = harness
            window.center()
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            NSApp.run()
        } catch {
            FileHandle.standardError.write(
                Data((error.localizedDescription + "\n").utf8)
            )
            exit(1)
        }
    }

    @MainActor
    private static func write(view: NSView, to output: URL) throws {
        view.layoutSubtreeIfNeeded()
        let bounds = view.bounds
        guard
            let bitmap = NSBitmapImageRep(
                bitmapDataPlanes: nil,
                pixelsWide: Int(ceil(bounds.width)),
                pixelsHigh: Int(ceil(bounds.height)),
                bitsPerSample: 8,
                samplesPerPixel: 4,
                hasAlpha: true,
                isPlanar: false,
                colorSpaceName: .deviceRGB,
                bytesPerRow: 0,
                bitsPerPixel: 0
            )
        else { throw MenuBarHarnessError.bitmap }
        bitmap.size = bounds.size
        view.cacheDisplay(in: bounds, to: bitmap)
        guard let png = bitmap.representation(using: .png, properties: [:]) else {
            throw MenuBarHarnessError.bitmap
        }
        try png.write(to: output, options: .atomic)
    }
}

private enum MenuBarHarnessError: Error, LocalizedError {
    case usage
    case bitmap

    var errorDescription: String? {
        switch self {
        case .usage:
            return "usage: menu-bar-state-harness [OUTPUT.png]"
        case .bitmap:
            return "menu-bar-state-harness could not render PNG output"
        }
    }
}
