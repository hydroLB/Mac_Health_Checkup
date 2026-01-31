import Foundation
import os

#if os(macOS)

public struct ProcessResult: Sendable {
    /**
     Summary
     Carry the result of a spawned process execution.

     Inputs
     exitCode: Process exit status.
     stdout: Collected stdout text.
     stderr: Collected stderr text.

     Outputs
     Value-type process result.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Returned by `ProcessRunner.run` and consumed by `PythonBackendClient`.

     Why this exists
     Keeps stdout and stderr available for UI error reporting without side channels.
     */

    public let exitCode: Int32
    public let stdout: String
    public let stderr: String
}

public final class ProcessRunner: Sendable {
    /**
     Summary
     Run local processes with timeouts and actionable errors.

     Inputs
     None.

     Outputs
     `ProcessResult` objects.

     Side effects
     Spawns subprocesses and may terminate them on timeout.

     Error handling
     Throws `AppError` with file and method context when execution fails or times out.

     Ties to other methods
     Used by `PythonBackendClient` to call the Python snapshot backend.

     Why this exists
     Provides a single IO boundary for the SwiftUI app with bounded execution time.
     */

    public init() {
        /**
         Summary
         Initialize the runner.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used during app bootstrap.

         Why this exists
         Keeps process execution dependency injectable for tests.
         */
    }

    public func run(
        executable: String,
        arguments: [String],
        workingDirectory: URL,
        timeoutSeconds: TimeInterval
    ) async throws -> ProcessResult {
        /**
         Summary
         Run a process and collect stdout and stderr with a hard timeout.

         Inputs
         executable: Executable path.
         arguments: Argument list.
         workingDirectory: Current directory URL.
         timeoutSeconds: Hard timeout.

         Outputs
         `ProcessResult` containing exit code and captured output.

         Side effects
         Spawns a process and may terminate it.

         Error handling
         Throws `AppError` when the process cannot start, times out, or output cannot be decoded.

         Ties to other methods
         Used by the backend client for snapshot fetching.

         Why this exists
         Keeps the UI responsive by bounding backend execution time.
         */
        if timeoutSeconds <= 0 {
            throw AppError.context(#fileID, #function, "timeoutSeconds must be positive")
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        process.currentDirectoryURL = workingDirectory

        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        do {
            try process.run()
        } catch {
            throw AppError.context(#fileID, #function, "Failed to start process \(executable)", error)
        }

        async let stdoutData = readAll(from: stdoutPipe.fileHandleForReading)
        async let stderrData = readAll(from: stderrPipe.fileHandleForReading)
        let exitCode = try await awaitTermination(process: process, timeoutSeconds: timeoutSeconds)
        let stdout = String(data: try await stdoutData, encoding: .utf8) ?? ""
        let stderr = String(data: try await stderrData, encoding: .utf8) ?? ""

        return ProcessResult(exitCode: exitCode, stdout: stdout, stderr: stderr)
    }

    private func awaitTermination(process: Process, timeoutSeconds: TimeInterval) async throws -> Int32 {
        /**
         Summary
         Await process termination with a hard timeout and forced termination.

         Inputs
         process: Running process.
         timeoutSeconds: Hard timeout duration.

         Outputs
         Termination status as an Int32 exit code.

         Side effects
         May terminate the process on timeout.

         Error handling
         Throws `AppError` when the process times out.

         Ties to other methods
         Used by `run` to enforce bounded execution.

         Why this exists
         Prevents backend hangs from blocking the refresh loop indefinitely.
         */
        try await withCheckedThrowingContinuation { continuation in
            let lock = OSAllocatedUnfairLock(initialState: false)
            let resumeOnce: @Sendable (Result<Int32, Error>) -> Void = { result in
                let shouldResume = lock.withLock { didResume in
                    if didResume {
                        return false
                    }
                    didResume = true
                    return true
                }
                if shouldResume {
                    continuation.resume(with: result)
                }
            }

            process.terminationHandler = { proc in
                resumeOnce(.success(proc.terminationStatus))
            }

            Task {
                let nanos = UInt64(timeoutSeconds * 1_000_000_000)
                try await Task.sleep(nanoseconds: nanos)
                if process.isRunning {
                    process.terminate()
                    resumeOnce(.failure(AppError.context(#fileID, #function, "Process timed out")))
                }
            }
        }
    }

    private func readAll(from handle: FileHandle) async throws -> Data {
        /**
         Summary
         Read all available data from a file handle asynchronously.

         Inputs
         handle: File handle to read from.

         Outputs
         Data read to EOF.

         Side effects
         Performs IO reads.

         Error handling
         Throws `AppError` when reads fail.

         Ties to other methods
         Used by `run` to collect stdout and stderr.

         Why this exists
         Keeps output collection off the main thread to avoid UI stalls.
         */
        try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .utility).async {
                do {
                    let data = try handle.readToEnd() ?? Data()
                    continuation.resume(returning: data)
                } catch {
                    continuation.resume(throwing: AppError.context(#fileID, #function, "Failed to read process output", error))
                }
            }
        }
    }
}

#endif
