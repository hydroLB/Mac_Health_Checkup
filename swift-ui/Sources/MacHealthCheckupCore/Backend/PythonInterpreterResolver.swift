import Foundation

#if os(macOS)

struct PythonVersion: Comparable, Sendable {
    /**
     Summary
     Represent a Python semantic version for interpreter validation.

     Inputs
     major: Major version.
     minor: Minor version.
     patch: Patch version.

     Outputs
     Comparable value for minimum version checks.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Used by `PythonInterpreterResolver` when deciding whether an interpreter is supported.

     Why this exists
     The backend requires Python 3.11+; this keeps version checks explicit and testable.
     */

    let major: Int
    let minor: Int
    let patch: Int

    static func < (lhs: PythonVersion, rhs: PythonVersion) -> Bool {
        /**
         Summary
         Compare versions lexicographically.

         Inputs
         lhs: Left-hand version.
         rhs: Right-hand version.

         Outputs
         True when lhs is older than rhs.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by resolver logic to enforce the minimum supported Python version.

         Why this exists
         Avoids ad-hoc version comparisons scattered across the codebase.
         */
        if lhs.major != rhs.major { return lhs.major < rhs.major }
        if lhs.minor != rhs.minor { return lhs.minor < rhs.minor }
        return lhs.patch < rhs.patch
    }
}

struct PythonInterpreterInfo: Sendable {
    /**
     Summary
     Carry a resolved interpreter path plus its detected version.

     Inputs
     path: Absolute path to the executable.
     version: Detected Python version.

     Outputs
     Interpreter metadata for diagnostics and UI error messages.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Returned by `PythonInterpreterResolver.resolve`.

     Why this exists
     Makes interpreter selection auditable and easier to troubleshoot.
     */

    let path: String
    let version: PythonVersion
}

enum PythonInterpreterResolver {
    /**
     Summary
     Resolve a Python interpreter suitable for running the backend module.

     Inputs
     Candidates and environment overrides.

     Outputs
     A validated interpreter path and version.

     Side effects
     Executes interpreter candidates to probe version.

     Error handling
     Throws `AppError` with actionable remediation when no valid interpreter is found.

     Ties to other methods
     Used by `BackendRuntimeConfig.from` during app bootstrap.

     Why this exists
     The macOS SwiftUI app must not accidentally use Xcode's embedded Python 3.9.
     */

    typealias VersionProbe = @Sendable (String) throws -> PythonVersion

    static func resolve(
        pythonOverride: String?,
        environment: [String: String],
        requiredMinimum: PythonVersion,
        fallbackCandidates: [String] = defaultFallbackCandidates(),
        versionProbe: VersionProbe = probeVersion
    ) throws -> PythonInterpreterInfo {
        /**
         Summary
         Choose the best interpreter from overrides and known locations.

         Inputs
         pythonOverride: Optional CLI override.
         environment: Process environment.
         requiredMinimum: Minimum supported Python version.
         versionProbe: Injectable probing function for tests.

         Outputs
         `PythonInterpreterInfo` for the selected interpreter.

         Side effects
         Spawns short-lived processes to probe candidate versions.

         Error handling
         Throws `AppError` when overrides are invalid or no candidate meets requirements.

         Ties to other methods
         Called by `BackendRuntimeConfig.from`.

         Why this exists
         Centralizes interpreter selection so "it runs" from Xcode, VS Code, or terminal.
         */
        let trimmedOverride = pythonOverride?.trimmingCharacters(in: .whitespacesAndNewlines)
        let envOverride = environment["MAC_HEALTH_CHECKUP_PYTHON"]?.trimmingCharacters(in: .whitespacesAndNewlines)

        let explicitOverrides = [trimmedOverride, envOverride]
            .compactMap { $0 }
            .filter { !$0.isEmpty }

        if !explicitOverrides.isEmpty {
            var diagnostics: [String] = []
            if let resolved = try resolveFirstValid(
                candidates: explicitOverrides,
                requiredMinimum: requiredMinimum,
                versionProbe: versionProbe,
                diagnostics: &diagnostics,
                stopOnProbeError: true
            ) { return resolved }

            let details = diagnostics.isEmpty ? "No additional details." : diagnostics.joined(separator: " | ")
            throw AppError.context(
                #fileID,
                #function,
                """
                Invalid Python override. mac-health-checkup requires Python >= \(requiredMinimum.major).\(requiredMinimum.minor). \
                Details: \(details) \
                Set `--python /opt/homebrew/bin/python3` or export `MAC_HEALTH_CHECKUP_PYTHON` to a Python 3.11+ executable.
                """
            )
        }

        var fallbackDiagnostics: [String] = []
        if let resolved = try resolveFirstValid(
            candidates: fallbackCandidates,
            requiredMinimum: requiredMinimum,
            versionProbe: versionProbe,
            diagnostics: &fallbackDiagnostics,
            stopOnProbeError: false
        ) {
            return resolved
        }

        let fallbackDetails = fallbackDiagnostics.isEmpty ? "No additional details." : fallbackDiagnostics.joined(separator: " | ")
        throw AppError.context(
            #fileID,
            #function,
            """
            No supported Python interpreter found. mac-health-checkup requires Python >= \(requiredMinimum.major).\(requiredMinimum.minor). \
            Details: \(fallbackDetails) \
            Install Python 3.11+ (Homebrew recommended) and set `MAC_HEALTH_CHECKUP_PYTHON=/opt/homebrew/bin/python3`, \
            or pass `--python /path/to/python3`.
            """
        )
    }

    private static func defaultFallbackCandidates() -> [String] {
        /**
         Summary
         Provide default interpreter candidates for Apple Silicon and Intel macOS hosts.

         Inputs
         None.

         Outputs
         Candidate interpreter paths in priority order.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used as the default `fallbackCandidates` input to `resolve`.

         Why this exists
         The UI should prefer Homebrew Python over the older Python embedded with Xcode.
         */
        [
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3",
        ]
    }

    private static func resolveFirstValid(
        candidates: [String],
        requiredMinimum: PythonVersion,
        versionProbe: VersionProbe,
        diagnostics: inout [String],
        stopOnProbeError: Bool
    ) throws -> PythonInterpreterInfo? {
        /**
         Summary
         Return the first candidate that exists, is executable, and meets the minimum version.

         Inputs
         candidates: Candidate interpreter paths.
         requiredMinimum: Minimum supported Python version.
         versionProbe: Injectable probe function.
         diagnostics: In/out diagnostic accumulator for invalid candidates.
         stopOnProbeError: Whether to treat probing errors as fatal.

         Outputs
         The first valid interpreter, or nil.

         Side effects
         Probes interpreter versions by running a subprocess.

         Error handling
         Throws `AppError` when probing fails in an unexpected way.

         Ties to other methods
         Used by `resolve`.

         Why this exists
         Keeps the main selection flow readable and testable.
         */
        for candidate in candidates {
            if candidate.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                continue
            }
            if !FileManager.default.isExecutableFile(atPath: candidate) {
                diagnostics.append("\(candidate): not executable or not found")
                continue
            }

            do {
                let version = try versionProbe(candidate)
                if version >= requiredMinimum {
                    return PythonInterpreterInfo(path: candidate, version: version)
                }
                diagnostics.append("\(candidate): version \(version.major).\(version.minor).\(version.patch) is below minimum")
            } catch let error as AppError {
                diagnostics.append("\(candidate): probe error: \(error)")
                if stopOnProbeError { throw error }
            } catch {
                let wrapped = AppError.context(#fileID, #function, "Failed to probe Python version for \(candidate)", error)
                diagnostics.append("\(candidate): probe error: \(wrapped)")
                if stopOnProbeError { throw wrapped }
            }
        }
        return nil
    }

    private static func probeVersion(pythonExecutable: String) throws -> PythonVersion {
        /**
         Summary
         Execute the interpreter to read its version.

         Inputs
         pythonExecutable: Path to the Python executable.

         Outputs
         Detected Python version.

         Side effects
         Spawns a short-lived Python process.

         Error handling
         Throws `AppError` when the process fails, times out, or returns an unparsable version.

         Ties to other methods
         Used as the default `VersionProbe` implementation.

         Why this exists
         Prevents accidentally selecting Xcode's embedded Python 3.9 when running the app from Xcode.
         */
        let script = "import sys; v=sys.version_info; print(f\"{v[0]}.{v[1]}.{v[2]}\")"
        let result = try runAndCapture(
            executable: pythonExecutable,
            arguments: ["-c", script],
            timeoutSeconds: 2.0
        )

        if result.exitCode != 0 {
            throw AppError.context(
                #fileID,
                #function,
                "Python version probe failed for \(pythonExecutable). stderr=\(result.stderr)"
            )
        }

        let trimmed = result.stdout.trimmingCharacters(in: .whitespacesAndNewlines)
        let parts = trimmed.split(separator: ".").map(String.init)
        if parts.count != 3 {
            throw AppError.context(#fileID, #function, "Unexpected Python version output '\(trimmed)' from \(pythonExecutable)")
        }
        guard let major = Int(parts[0]), let minor = Int(parts[1]), let patch = Int(parts[2]) else {
            throw AppError.context(#fileID, #function, "Failed to parse Python version '\(trimmed)' from \(pythonExecutable)")
        }
        return PythonVersion(major: major, minor: minor, patch: patch)
    }

    private struct CaptureResult: Sendable {
        /**
         Summary
         Represent captured process output for probing.

         Inputs
         exitCode: Termination status.
         stdout: Collected stdout.
         stderr: Collected stderr.

         Outputs
         A value type used by probing helpers.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Returned by `runAndCapture`.

         Why this exists
         Keeps the probe implementation small and explicit.
         */
        let exitCode: Int32
        let stdout: String
        let stderr: String
    }

    private static func runAndCapture(
        executable: String,
        arguments: [String],
        timeoutSeconds: TimeInterval
    ) throws -> CaptureResult {
        /**
         Summary
         Run a process synchronously with a hard timeout, capturing stdout and stderr.

         Inputs
         executable: Executable path.
         arguments: Argument list.
         timeoutSeconds: Hard timeout.

         Outputs
         Captured stdout, stderr, and exit code.

         Side effects
         Spawns a subprocess and may terminate it on timeout.

         Error handling
         Throws `AppError` when the process fails to start or times out.

         Ties to other methods
         Used by `probeVersion`.

         Why this exists
         `BackendRuntimeConfig.from` is synchronous; this keeps version probing bounded and deterministic.
         */
        if timeoutSeconds <= 0 {
            throw AppError.context(#fileID, #function, "timeoutSeconds must be positive")
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments

        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        let semaphore = DispatchSemaphore(value: 0)
        process.terminationHandler = { _ in
            semaphore.signal()
        }

        do {
            try process.run()
        } catch {
            throw AppError.context(#fileID, #function, "Failed to start process \(executable)", error)
        }

        let timeout = DispatchTime.now() + timeoutSeconds
        if semaphore.wait(timeout: timeout) == .timedOut {
            if process.isRunning {
                process.terminate()
            }
            throw AppError.context(#fileID, #function, "Process timed out while probing \(executable)")
        }

        let stdoutData = (try? stdoutPipe.fileHandleForReading.readToEnd()) ?? Data()
        let stderrData = (try? stderrPipe.fileHandleForReading.readToEnd()) ?? Data()
        let stdout = String(data: stdoutData, encoding: .utf8) ?? ""
        let stderr = String(data: stderrData, encoding: .utf8) ?? ""
        return CaptureResult(exitCode: process.terminationStatus, stdout: stdout, stderr: stderr)
    }
}

#endif
