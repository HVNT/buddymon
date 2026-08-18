import AppKit
import Darwin
import Foundation

private final class ReadmeScreenshotTarget: NSObject {
    @objc func noop(_ sender: Any?) {}
}

@main
struct ReadmeScreenshotSnapshot {
    @MainActor
    static func main() {
        do {
            guard CommandLine.arguments.count == 3 else {
                throw ReadmeScreenshotError.usage
            }
            let kind = CommandLine.arguments[1]
            let input = FileHandle.standardInput.readDataToEndOfFile()
            guard
                let payload = try JSONSerialization.jsonObject(with: input)
                    as? [String: Any]
            else {
                throw ReadmeScreenshotError.invalidJSON
            }

            _ = NSApplication.shared
            let target = ReadmeScreenshotTarget()
            let view: NSView
            let size: NSSize
            switch kind {
            case "menu":
                let menu = BuddyMonCompactMenuView(
                    status: payload,
                    target: target,
                    action: #selector(ReadmeScreenshotTarget.noop(_:))
                )
                view = menu
                size = menu.preferredSize
            case "encounter":
                let encounter = BuddyMonCompactEncounterView(
                    view: payload,
                    message: nil,
                    target: target,
                    action: #selector(ReadmeScreenshotTarget.noop(_:)),
                    backAction: #selector(ReadmeScreenshotTarget.noop(_:))
                )
                view = encounter
                size = encounter.preferredSize
            case "trainer":
                let trainer = BuddyMonCompactTrainerView(
                    view: payload,
                    target: target,
                    backAction: #selector(ReadmeScreenshotTarget.noop(_:))
                )
                view = trainer
                size = trainer.preferredSize
            case "tokens":
                let tokens = BuddyMonCompactTokensView(
                    view: payload,
                    target: target,
                    backAction: #selector(ReadmeScreenshotTarget.noop(_:))
                )
                view = tokens
                size = tokens.preferredSize
            default:
                throw ReadmeScreenshotError.unknownKind(kind)
            }

            view.frame = NSRect(origin: .zero, size: size)
            view.layoutSubtreeIfNeeded()
            freezeAnimations(in: view)
            let output = URL(fileURLWithPath: CommandLine.arguments[2])
            try FileManager.default.createDirectory(
                at: output.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try write(view: view, to: output, scale: 2)
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
    private static func write(view: NSView, to output: URL, scale: CGFloat) throws {
        let bounds = view.bounds
        guard
            let bitmap = NSBitmapImageRep(
                bitmapDataPlanes: nil,
                pixelsWide: Int(ceil(bounds.width * scale)),
                pixelsHigh: Int(ceil(bounds.height * scale)),
                bitsPerSample: 8,
                samplesPerPixel: 4,
                hasAlpha: true,
                isPlanar: false,
                colorSpaceName: .deviceRGB,
                bytesPerRow: 0,
                bitsPerPixel: 0
            )
        else { throw ReadmeScreenshotError.bitmap }
        bitmap.size = bounds.size
        view.cacheDisplay(in: bounds, to: bitmap)
        guard let png = bitmap.representation(using: .png, properties: [:]) else {
            throw ReadmeScreenshotError.bitmap
        }
        try png.write(to: output, options: .atomic)
    }
}

private enum ReadmeScreenshotError: Error, LocalizedError {
    case usage
    case invalidJSON
    case bitmap
    case unknownKind(String)

    var errorDescription: String? {
        switch self {
        case .usage:
            return "usage: readme-screenshot KIND OUTPUT.png"
        case .invalidJSON:
            return "readme-screenshot expected a JSON payload on stdin"
        case .bitmap:
            return "readme-screenshot could not render PNG output"
        case .unknownKind(let value):
            return "unknown readme screenshot kind: \(value)"
        }
    }
}
