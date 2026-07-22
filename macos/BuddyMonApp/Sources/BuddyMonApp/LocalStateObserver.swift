import Darwin
import Foundation

@MainActor
final class LocalStateObserver {
    private struct FileSignature: Equatable {
        let inode: UInt64
        let size: UInt64
        let modifiedAt: TimeInterval
    }

    private let stateURL: URL
    private let debounceInterval: TimeInterval
    private var source: DispatchSourceFileSystemObject?
    private var pendingChangeCheck: DispatchWorkItem?
    private var lastSignature: FileSignature?
    private var changeHandler: (() -> Void)?

    init(
        stateURL: URL? = nil,
        debounceInterval: TimeInterval = 0.12
    ) {
        self.stateURL = stateURL ?? LocalStateObserver.defaultStateURL
        self.debounceInterval = debounceInterval
    }

    @discardableResult
    func start(onChange: @escaping () -> Void) -> Bool {
        stop()

        let directoryURL = stateURL.deletingLastPathComponent()
        do {
            try FileManager.default.createDirectory(
                at: directoryURL,
                withIntermediateDirectories: true
            )
        } catch {
            return false
        }

        let descriptor = Darwin.open(
            directoryURL.path,
            O_EVTONLY | O_CLOEXEC | O_NOFOLLOW
        )
        guard descriptor >= 0 else { return false }

        lastSignature = currentSignature()
        changeHandler = onChange

        let source = DispatchSource.makeFileSystemObjectSource(
            fileDescriptor: descriptor,
            eventMask: [.write, .rename, .delete],
            queue: .main
        )
        source.setEventHandler { [weak self] in
            self?.scheduleChangeCheck()
        }
        source.setCancelHandler {
            Darwin.close(descriptor)
        }
        self.source = source
        source.resume()
        return true
    }

    func stop() {
        pendingChangeCheck?.cancel()
        pendingChangeCheck = nil
        source?.cancel()
        source = nil
        changeHandler = nil
        lastSignature = nil
    }

    private func scheduleChangeCheck() {
        pendingChangeCheck?.cancel()
        let workItem = DispatchWorkItem { [weak self] in
            self?.emitIfStateChanged()
        }
        pendingChangeCheck = workItem
        DispatchQueue.main.asyncAfter(
            deadline: .now() + debounceInterval,
            execute: workItem
        )
    }

    private func emitIfStateChanged() {
        pendingChangeCheck = nil
        let signature = currentSignature()
        guard signature != lastSignature else { return }
        lastSignature = signature
        changeHandler?()
    }

    private func currentSignature() -> FileSignature? {
        guard
            let attributes = try? FileManager.default.attributesOfItem(
                atPath: stateURL.path
            ),
            let inode = attributes[.systemFileNumber] as? NSNumber,
            let size = attributes[.size] as? NSNumber,
            let modifiedAt = attributes[.modificationDate] as? Date
        else { return nil }

        return FileSignature(
            inode: inode.uint64Value,
            size: size.uint64Value,
            modifiedAt: modifiedAt.timeIntervalSince1970
        )
    }

    private static var defaultStateURL: URL {
        let environment = ProcessInfo.processInfo.environment
        let stateRoot: URL
        if
            let configuredRoot = environment["XDG_STATE_HOME"],
            !configuredRoot.isEmpty
        {
            stateRoot = URL(fileURLWithPath: configuredRoot, isDirectory: true)
        } else {
            stateRoot = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent(".local/state", isDirectory: true)
        }
        return stateRoot
            .appendingPathComponent("buddymon", isDirectory: true)
            .appendingPathComponent("state.json")
    }
}
