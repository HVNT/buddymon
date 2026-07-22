import Darwin
import Foundation

final class SingleInstanceGuard {
    enum Acquisition {
        case acquired
        case alreadyRunning(processIdentifier: pid_t?)
    }

    private let lockURL: URL
    private var descriptor: Int32 = -1

    init(lockURL: URL = SingleInstanceGuard.defaultLockURL) {
        self.lockURL = lockURL
    }

    deinit {
        if descriptor >= 0 {
            Darwin.lockf(descriptor, F_ULOCK, 0)
            Darwin.close(descriptor)
        }
    }

    func acquire() throws -> Acquisition {
        if descriptor >= 0 {
            return .acquired
        }

        try FileManager.default.createDirectory(
            at: lockURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )

        let opened = Darwin.open(
            lockURL.path,
            O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW,
            S_IRUSR | S_IWUSR
        )
        guard opened >= 0 else {
            throw posixError()
        }
        var shouldClose = true
        defer {
            if shouldClose {
                Darwin.close(opened)
            }
        }

        try validateLockFile(opened)

        guard Darwin.lockf(opened, F_TLOCK, 0) == 0 else {
            let failure = errno
            if failure == EACCES || failure == EAGAIN {
                return .alreadyRunning(
                    processIdentifier: lockOwner(of: opened)
                )
            }
            throw posixError(failure)
        }

        descriptor = opened
        shouldClose = false
        return .acquired
    }

    private static let defaultLockURL = FileManager.default
        .homeDirectoryForCurrentUser
        .appendingPathComponent(".local/state/buddymon", isDirectory: true)
        .appendingPathComponent("native-app.lock")

    private func validateLockFile(_ descriptor: Int32) throws {
        var information = stat()
        guard Darwin.fstat(descriptor, &information) == 0 else {
            throw posixError()
        }
        guard
            information.st_mode & S_IFMT == S_IFREG,
            information.st_uid == Darwin.geteuid()
        else {
            throw POSIXError(.EACCES)
        }
    }

    private func lockOwner(of descriptor: Int32) -> pid_t? {
        var query = flock()
        query.l_type = Int16(F_WRLCK)
        query.l_whence = Int16(SEEK_SET)
        query.l_start = 0
        query.l_len = 0

        guard
            Darwin.fcntl(descriptor, F_GETLK, &query) != -1,
            query.l_type != F_UNLCK,
            query.l_pid > 0
        else {
            return nil
        }
        return query.l_pid
    }

    private func posixError(_ code: Int32 = errno) -> POSIXError {
        POSIXError(POSIXErrorCode(rawValue: code) ?? .EIO)
    }
}
