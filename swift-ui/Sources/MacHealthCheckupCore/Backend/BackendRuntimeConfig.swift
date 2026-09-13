import Foundation

public struct BackendRuntimeConfig: Sendable {
    /**
     Summary
     Hold backend execution configuration for snapshot fetching.

     Inputs
     pythonExecutable: Path to the Python interpreter.
     repoRoot: Working directory for running the backend module.
     timeoutSeconds: Hard timeout for a single snapshot run.

     Outputs
     Runtime configuration for `PythonBackendClient`.

     Side effects
     None.

     Error handling
     Throws `AppError` via `from(...)` when inputs are invalid.

     Ties to other methods
     Built by `AppBootstrap.load` from config and environment overrides.

     Why this exists
     Keeps execution knobs centralized and easy to tune without code edits.
     */

    public let pythonExecutable: String
    public let repoRoot: URL
    public let timeoutSeconds: TimeInterval

    public static func from(
        config: AppConfig,
        repoRoot: URL,
        pythonOverride: String?
    ) throws -> BackendRuntimeConfig {
        /**
         Summary
         Build runtime config using validated config plus optional overrides.

         Inputs
         config: Validated `AppConfig`.
         repoRoot: Resolved repo root.
         pythonOverride: Optional python executable override from CLI args or environment.

         Outputs
         `BackendRuntimeConfig`.

         Side effects
         Reads environment variables.

         Error handling
         Throws `AppError` when resolved values are invalid.

         Ties to other methods
         Used to initialize `PythonBackendClient`.

         Why this exists
         Allows running the SwiftUI frontend with different Python environments safely.
         */
        let env = ProcessInfo.processInfo.environment

        #if os(macOS)
        let minimum = PythonVersion(major: 3, minor: 11, patch: 0)
        let resolved = try PythonInterpreterResolver.resolve(
            pythonOverride: pythonOverride,
            environment: env,
            requiredMinimum: minimum
        )
        let pythonExecutable = resolved.path
        #else
        let pythonExecutable = pythonOverride ?? env["MAC_HEALTH_CHECKUP_PYTHON"] ?? "/usr/bin/python3"
        if pythonExecutable.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            throw AppError.context(#fileID, #function, "Python executable path must be non-empty")
        }
        #endif

        return BackendRuntimeConfig(
            pythonExecutable: pythonExecutable,
            repoRoot: repoRoot,
            timeoutSeconds: TimeInterval(config.timeouts.resolvedSnapshotBackendTimeoutSeconds)
        )
    }
}
