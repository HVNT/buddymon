import AppKit
import Darwin
import Foundation

@main
struct MenuPanelStateHarness {
    @MainActor
    static func main() {
        do {
            guard CommandLine.arguments.count == 2 else {
                throw MenuPanelStateHarnessError.usage
            }
            let input = FileHandle.standardInput.readDataToEndOfFile()
            guard
                let payload = try JSONSerialization.jsonObject(with: input) as? [String: Any],
                payload["kind"] as? String == "menu_panel_harness"
            else { throw MenuPanelStateHarnessError.invalidJSON }

            _ = NSApplication.shared
            let harness = MenuPanelStateHarnessView(payload: payload)
            let view = harness.snapshotView
            freezeAnimations(in: view)

            let output = URL(fileURLWithPath: CommandLine.arguments[1])
            try FileManager.default.createDirectory(
                at: output.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try write(view: view, to: output)
            FileHandle.standardOutput.write(Data((output.path + "\n").utf8))
        } catch {
            FileHandle.standardError.write(
                Data((error.localizedDescription + "\n").utf8)
            )
            exit(1)
        }
    }

    @MainActor
    private static func freezeAnimations(in view: NSView) {
        view.layer?.removeAllAnimations()
        view.subviews.forEach { freezeAnimations(in: $0) }
    }

    @MainActor
    private static func write(view: NSView, to output: URL) throws {
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
        else { throw MenuPanelStateHarnessError.bitmap }
        bitmap.size = bounds.size
        view.cacheDisplay(in: bounds, to: bitmap)
        guard let png = bitmap.representation(using: .png, properties: [:]) else {
            throw MenuPanelStateHarnessError.bitmap
        }
        try png.write(to: output, options: .atomic)
    }
}

private enum MenuPanelStateHarnessError: Error, LocalizedError {
    case usage
    case invalidJSON
    case bitmap

    var errorDescription: String? {
        switch self {
        case .usage: return "usage: menu-panel-state-harness OUTPUT.png"
        case .invalidJSON: return "expected compact menu-panel harness JSON on stdin"
        case .bitmap: return "could not render compact menu-panel harness PNG"
        }
    }
}
