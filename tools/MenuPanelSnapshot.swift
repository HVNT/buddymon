import AppKit
import Darwin
import Foundation

private final class MenuPanelSnapshotTarget: NSObject {
    @objc func noop(_ sender: Any?) {}
}

@main
struct MenuPanelSnapshot {
    @MainActor
    static func main() {
        do {
            guard CommandLine.arguments.count == 2 else {
                throw MenuPanelSnapshotError.usage
            }
            let input = FileHandle.standardInput.readDataToEndOfFile()
            guard
                let status = try JSONSerialization.jsonObject(with: input) as? [String: Any]
            else {
                throw MenuPanelSnapshotError.invalidJSON
            }

            _ = NSApplication.shared
            let target = MenuPanelSnapshotTarget()
            let view = BuddyMonCompactMenuView(
                status: status,
                target: target,
                action: #selector(MenuPanelSnapshotTarget.noop(_:))
            )
            view.frame = NSRect(origin: .zero, size: view.preferredSize)
            view.layoutSubtreeIfNeeded()
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
        else { throw MenuPanelSnapshotError.bitmap }
        bitmap.size = bounds.size
        view.cacheDisplay(in: bounds, to: bitmap)
        guard let png = bitmap.representation(using: .png, properties: [:]) else {
            throw MenuPanelSnapshotError.bitmap
        }
        try png.write(to: output, options: .atomic)
    }
}

private enum MenuPanelSnapshotError: Error, LocalizedError {
    case usage
    case invalidJSON
    case bitmap

    var errorDescription: String? {
        switch self {
        case .usage:
            return "usage: menu-panel-snapshot OUTPUT.png"
        case .invalidJSON:
            return "menu-panel-snapshot expected app-status JSON on stdin"
        case .bitmap:
            return "menu-panel-snapshot could not render PNG output"
        }
    }
}
