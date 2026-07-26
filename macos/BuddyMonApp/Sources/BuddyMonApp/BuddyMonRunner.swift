import Foundation

enum BuddyMonRunnerError: Error, LocalizedError {
    case preflightFailed([String])
    case commandFailed(status: Int32, stdout: String, stderr: String)
    case unexpectedJSON

    var errorDescription: String? {
        switch self {
        case .preflightFailed(let issues):
            return issues.joined(separator: "\n")
        case .commandFailed(let status, let stdout, let stderr):
            let message = stderr.trimmingCharacters(in: .whitespacesAndNewlines)
            if !message.isEmpty {
                return message
            }
            let output = stdout.trimmingCharacters(in: .whitespacesAndNewlines)
            if !output.isEmpty {
                return output
            }
            return "BuddyMon command failed with exit status \(status)."
        case .unexpectedJSON:
            return "BuddyMon returned an unexpected JSON response."
        }
    }
}

final class BuddyMonRunner {
    private let fileManager = FileManager.default
    private let repoURL: URL
    private let pythonURL: URL
    private let usesBundledPython: Bool
    private let processExecutor: ProcessExecutor

    init(
        processExecutor: ProcessExecutor = ProcessExecutor(),
        resourceURL: URL? = nil,
        repoURL: URL? = nil,
        pythonURL: URL? = nil
    ) {
        self.processExecutor = processExecutor
        let resources = resourceURL ?? Bundle.main.resourceURL ?? URL(fileURLWithPath: ".")

        if let repoURL {
            self.repoURL = repoURL
        } else if let override = ProcessInfo.processInfo.environment["BUDDYMON_REPO"], !override.isEmpty {
            self.repoURL = URL(fileURLWithPath: override)
        } else {
            self.repoURL = resources.appendingPathComponent("buddymon", isDirectory: true)
        }

        let bundled = resources.appendingPathComponent("python/bin/python3")
        if let pythonURL {
            self.pythonURL = pythonURL
            usesBundledPython = pythonURL.standardizedFileURL == bundled.standardizedFileURL
        } else if FileManager.default.isExecutableFile(atPath: bundled.path) {
            self.pythonURL = bundled
            usesBundledPython = true
        } else {
            self.pythonURL = URL(fileURLWithPath: "/usr/bin/python3")
            usesBundledPython = false
        }
    }

    var runtimeDescription: String {
        if usesBundledPython {
            return "bundled Python"
        }
        if fileManager.isExecutableFile(atPath: pythonURL.path) {
            return "developer fallback /usr/bin/python3"
        }
        return "missing Python runtime"
    }

    var repoPath: String {
        repoURL.path
    }

    var pythonPath: String {
        pythonURL.path
    }

    private var scriptURL: URL {
        repoURL.appendingPathComponent("buddymon.py")
    }

    func preflightIssues() -> [String] {
        var issues: [String] = []
        if !fileManager.fileExists(atPath: scriptURL.path) {
            issues.append("Missing bundled BuddyMon runtime at \(scriptURL.path).")
        }
        if !fileManager.isExecutableFile(atPath: pythonURL.path) {
            issues.append("Missing Python runtime at \(pythonURL.path).")
        }
        if !usesBundledPython {
            issues.append("This is a developer build. Self-contained builds should bundle Python.")
        }
        return issues
    }

    func diagnosticText(error: Error? = nil) -> String {
        var lines: [String] = []
        lines.append("BuddyMon could not finish setup.")
        lines.append("")
        lines.append("Runtime: \(runtimeDescription)")
        lines.append("Python: \(pythonPath)")
        lines.append("BuddyMon files: \(repoPath)")

        let issues = preflightIssues()
        if !issues.isEmpty {
            lines.append("")
            lines.append("Setup issues:")
            for issue in issues {
                lines.append("- \(issue)")
            }
        }

        if let error {
            lines.append("")
            lines.append("Last error:")
            lines.append(error.localizedDescription)
        }

        lines.append("")
        lines.append("Build a self-contained app with:")
        lines.append("scripts/build-macos-app.sh --friend")
        lines.append("")
        lines.append("Or use a prepared runtime:")
        lines.append("BUDDYMON_PYTHON_RUNTIME=/path/to/runtime scripts/build-macos-app.sh --friend")
        return lines.joined(separator: "\n")
    }

    private func command(_ args: [String], timeout: TimeInterval?) throws -> ProcessCommand {
        let issues = preflightIssues().filter { !$0.contains("developer build") }
        if !issues.isEmpty {
            throw BuddyMonRunnerError.preflightFailed(issues)
        }

        return ProcessCommand(
            executableURL: pythonURL,
            arguments: [scriptURL.path] + args,
            currentDirectoryURL: repoURL,
            environment: ProcessInfo.processInfo.environment.merging([
                "BUDDYMON_PYTHON": pythonPath,
                "PYTHONUNBUFFERED": "1",
            ]) { _, new in new },
            timeout: timeout
        )
    }

    private func output(from result: ProcessResult) throws -> String {
        guard result.succeeded else {
            throw BuddyMonRunnerError.commandFailed(
                status: result.terminationStatus,
                stdout: result.stdoutText,
                stderr: result.stderrText
            )
        }
        return result.stdoutText.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func object(from text: String) throws -> [String: Any] {
        let data = Data(text.utf8)
        guard
            let object = try? JSONSerialization.jsonObject(with: data),
            let dictionary = object as? [String: Any]
        else {
            throw BuddyMonRunnerError.unexpectedJSON
        }
        return dictionary
    }

    func run(_ args: [String], timeout: TimeInterval? = nil) throws -> String {
        try output(from: processExecutor.run(try command(args, timeout: timeout)))
    }

    func run(_ args: [String], timeout: TimeInterval? = nil) async throws -> String {
        try output(from: await processExecutor.run(try command(args, timeout: timeout)))
    }

    func status(timeout: TimeInterval? = nil) throws -> [String: Any] {
        try object(from: run(["app-status"], timeout: timeout))
    }

    func status(timeout: TimeInterval? = nil) async throws -> [String: Any] {
        try object(from: await run(["app-status"], timeout: timeout))
    }

    func appView(_ screen: String, timeout: TimeInterval? = nil) throws -> [String: Any] {
        try object(from: run(["app-view", screen], timeout: timeout))
    }

    func appView(_ screen: String, timeout: TimeInterval? = nil) async throws -> [String: Any] {
        try object(from: await run(["app-view", screen], timeout: timeout))
    }

    func appAction(
        _ action: String,
        _ args: [String],
        timeout: TimeInterval? = nil
    ) throws -> [String: Any] {
        try object(from: run(["app-action", action] + args, timeout: timeout))
    }

    func appAction(
        _ action: String,
        _ args: [String],
        timeout: TimeInterval? = nil
    ) async throws -> [String: Any] {
        try object(from: await run(
            ["app-action", action] + args,
            timeout: timeout
        ))
    }

}
