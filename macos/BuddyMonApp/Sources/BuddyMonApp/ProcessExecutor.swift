import Foundation

#if canImport(Darwin)
import Darwin
#endif

struct ProcessCommand: Sendable {
    let executableURL: URL
    let arguments: [String]
    let currentDirectoryURL: URL?
    let environment: [String: String]?
    let timeout: TimeInterval?

    init(
        executableURL: URL,
        arguments: [String] = [],
        currentDirectoryURL: URL? = nil,
        environment: [String: String]? = nil,
        timeout: TimeInterval? = nil
    ) {
        self.executableURL = executableURL
        self.arguments = arguments
        self.currentDirectoryURL = currentDirectoryURL
        self.environment = environment
        self.timeout = timeout
    }
}

struct ProcessResult: Sendable {
    let stdout: Data
    let stderr: Data
    let terminationStatus: Int32
    let terminationReason: Process.TerminationReason

    var succeeded: Bool {
        terminationReason == .exit && terminationStatus == 0
    }

    var stdoutText: String {
        String(decoding: stdout, as: UTF8.self)
    }

    var stderrText: String {
        String(decoding: stderr, as: UTF8.self)
    }
}

enum ProcessExecutorError: Error, LocalizedError, @unchecked Sendable {
    case launchFailed(executableURL: URL, underlying: Error)
    case timedOut(timeout: TimeInterval, result: ProcessResult)
    case cancelled(result: ProcessResult?)

    var errorDescription: String? {
        switch self {
        case .launchFailed(let executableURL, let underlying):
            return "Could not launch \(executableURL.path): \(underlying.localizedDescription)"
        case .timedOut(let timeout, _):
            return "Command timed out after \(Self.durationText(timeout))."
        case .cancelled:
            return "Command was cancelled."
        }
    }

    private static func durationText(_ duration: TimeInterval) -> String {
        if duration.rounded() == duration {
            return "\(Int(duration)) seconds"
        }
        return String(format: "%.2f seconds", duration)
    }
}

final class ProcessExecution: @unchecked Sendable {
    private let lock = NSLock()
    private let terminationGracePeriod: TimeInterval
    private var process: Process?
    private var cancellationRequested = false

    fileprivate init(terminationGracePeriod: TimeInterval) {
        self.terminationGracePeriod = max(0, terminationGracePeriod)
    }

    func cancel() {
        let runningProcess: Process?
        lock.lock()
        cancellationRequested = true
        runningProcess = process
        lock.unlock()

        if let runningProcess {
            requestTermination(of: runningProcess)
        }
    }

    fileprivate func attach(_ process: Process) -> Bool {
        lock.lock()
        self.process = process
        let shouldCancel = cancellationRequested
        lock.unlock()
        return shouldCancel
    }

    fileprivate func finish(_ process: Process) {
        lock.lock()
        if self.process === process {
            self.process = nil
        }
        lock.unlock()
    }

    fileprivate func processDidStart() {
        let runningProcess: Process?
        lock.lock()
        runningProcess = cancellationRequested ? process : nil
        lock.unlock()
        if let runningProcess {
            requestTermination(of: runningProcess)
        }
    }

    fileprivate func terminate() {
        let runningProcess: Process?
        lock.lock()
        runningProcess = process
        lock.unlock()
        if let runningProcess {
            requestTermination(of: runningProcess)
        }
    }

    fileprivate var isCancellationRequested: Bool {
        lock.lock()
        let requested = cancellationRequested
        lock.unlock()
        return requested
    }

    private func requestTermination(of process: Process) {
        guard process.isRunning else { return }
        process.terminate()
        let processIdentifier = process.processIdentifier
        DispatchQueue.global(qos: .utility).asyncAfter(
            deadline: .now() + terminationGracePeriod
        ) { [self] in
            forceKillIfRunning(processIdentifier)
        }
    }

    private func forceKillIfRunning(_ processIdentifier: Int32) {
        lock.lock()
        let runningProcess = process
        let shouldKill = runningProcess?.processIdentifier == processIdentifier
            && runningProcess?.isRunning == true
        lock.unlock()
        guard shouldKill else { return }

#if canImport(Darwin)
        _ = Darwin.kill(processIdentifier, SIGKILL)
#else
        runningProcess?.terminate()
#endif
    }
}

private final class ProcessOutputCapture: @unchecked Sendable {
    private let lock = NSLock()
    private var stdout = Data()
    private var stderr = Data()

    func setStdout(_ data: Data) {
        lock.lock()
        stdout = data
        lock.unlock()
    }

    func setStderr(_ data: Data) {
        lock.lock()
        stderr = data
        lock.unlock()
    }

    func result(for process: Process) -> ProcessResult {
        lock.lock()
        let output = stdout
        let error = stderr
        lock.unlock()
        return ProcessResult(
            stdout: output,
            stderr: error,
            terminationStatus: process.terminationStatus,
            terminationReason: process.terminationReason
        )
    }
}

private final class ProcessExecutionBox: @unchecked Sendable {
    private let lock = NSLock()
    private var execution: ProcessExecution?
    private var cancellationRequested = false

    func set(_ execution: ProcessExecution) {
        lock.lock()
        self.execution = execution
        let shouldCancel = cancellationRequested
        lock.unlock()
        if shouldCancel {
            execution.cancel()
        }
    }

    func cancel() {
        let activeExecution: ProcessExecution?
        lock.lock()
        cancellationRequested = true
        activeExecution = execution
        lock.unlock()
        activeExecution?.cancel()
    }
}

final class ProcessExecutor: @unchecked Sendable {
    private let terminationGracePeriod: TimeInterval
    private let executionQueue = DispatchQueue(
        label: "buddymon.process-executor",
        qos: .userInitiated,
        attributes: .concurrent
    )
    private let readerQueue = DispatchQueue(
        label: "buddymon.process-executor.readers",
        qos: .userInitiated,
        attributes: .concurrent
    )

    init(terminationGracePeriod: TimeInterval = 0.5) {
        self.terminationGracePeriod = max(0, terminationGracePeriod)
    }

    func run(_ command: ProcessCommand) throws -> ProcessResult {
        try run(
            command,
            execution: ProcessExecution(terminationGracePeriod: terminationGracePeriod)
        )
    }

    @discardableResult
    func start(
        _ command: ProcessCommand,
        completion: @escaping @Sendable (Result<ProcessResult, ProcessExecutorError>) -> Void
    ) -> ProcessExecution {
        let execution = ProcessExecution(terminationGracePeriod: terminationGracePeriod)
        executionQueue.async { [self] in
            do {
                completion(.success(try run(command, execution: execution)))
            } catch let error as ProcessExecutorError {
                completion(.failure(error))
            } catch {
                completion(.failure(.launchFailed(
                    executableURL: command.executableURL,
                    underlying: error
                )))
            }
        }
        return execution
    }

    func run(_ command: ProcessCommand) async throws -> ProcessResult {
        let executionBox = ProcessExecutionBox()
        return try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                let execution = start(command) { result in
                    switch result {
                    case .success(let value):
                        continuation.resume(returning: value)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
                executionBox.set(execution)
            }
        } onCancel: {
            executionBox.cancel()
        }
    }

    private func run(
        _ command: ProcessCommand,
        execution: ProcessExecution
    ) throws -> ProcessResult {
        let process = Process()
        process.executableURL = command.executableURL
        process.arguments = command.arguments
        process.currentDirectoryURL = command.currentDirectoryURL
        process.environment = command.environment

        let outputPipe = Pipe()
        let errorPipe = Pipe()
        process.standardOutput = outputPipe
        process.standardError = errorPipe

        let terminated = DispatchSemaphore(value: 0)
        process.terminationHandler = { _ in
            terminated.signal()
        }

        if execution.attach(process) {
            execution.finish(process)
            throw ProcessExecutorError.cancelled(result: nil)
        }
        defer {
            execution.finish(process)
        }

        do {
            try process.run()
        } catch {
            throw ProcessExecutorError.launchFailed(
                executableURL: command.executableURL,
                underlying: error
            )
        }
        execution.processDidStart()

        let capture = ProcessOutputCapture()
        let readers = DispatchGroup()
        readers.enter()
        readerQueue.async {
            defer { readers.leave() }
            capture.setStdout(outputPipe.fileHandleForReading.readDataToEndOfFile())
        }
        readers.enter()
        readerQueue.async {
            defer { readers.leave() }
            capture.setStderr(errorPipe.fileHandleForReading.readDataToEndOfFile())
        }

        var timedOut = false
        if let timeout = command.timeout {
            let deadline = DispatchTime.now() + max(0, timeout)
            if terminated.wait(timeout: deadline) == .timedOut {
                timedOut = true
                execution.terminate()
                terminated.wait()
            }
        } else {
            terminated.wait()
        }

        readers.wait()
        let result = capture.result(for: process)
        if execution.isCancellationRequested {
            throw ProcessExecutorError.cancelled(result: result)
        }
        if timedOut {
            throw ProcessExecutorError.timedOut(
                timeout: command.timeout ?? 0,
                result: result
            )
        }
        return result
    }
}
