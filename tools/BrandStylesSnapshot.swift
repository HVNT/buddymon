import AppKit
import Darwin
import Foundation

@main
struct BrandStylesSnapshot {
    @MainActor
    static func main() {
        do {
            guard CommandLine.arguments.count == 2 else {
                throw SnapshotToolError.usage
            }
            _ = NSApplication.shared
            let output = URL(fileURLWithPath: CommandLine.arguments[1])
            try FileManager.default.createDirectory(
                at: output.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try BrandStylesWindowController.shared.writeSnapshot(to: output)
            FileHandle.standardOutput.write(Data((output.path + "\n").utf8))
        } catch {
            FileHandle.standardError.write(
                Data((error.localizedDescription + "\n").utf8)
            )
            exit(1)
        }
    }
}

private enum SnapshotToolError: Error, LocalizedError {
    case usage

    var errorDescription: String? {
        "usage: brand-styles-snapshot OUTPUT.png"
    }
}
