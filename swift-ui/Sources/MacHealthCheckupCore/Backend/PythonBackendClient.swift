import Foundation

#if os(macOS)

public final class PythonBackendClient: SnapshotBackend, Sendable {
    /**
     Summary
     Fetch dashboard snapshots by invoking the Python backend in snapshot mode.

     Inputs
     runtime: Backend execution configuration.
     runner: Process runner for bounded execution.

     Outputs
     `Snapshot` objects decoded from stdout JSON.

     Side effects
     Spawns a Python subprocess.

     Error handling
     Throws `AppError` with module and method context when execution or decoding fails.

     Ties to other methods
     Used by `DashboardViewModel` on macOS to refresh UI state.

     Why this exists
     Keeps macOS diagnostics logic in Python while providing a native SwiftUI frontend.
     */

    private let runtime: BackendRuntimeConfig
    private let runner: ProcessRunner

    public init(runtime: BackendRuntimeConfig, runner: ProcessRunner) {
        /**
         Summary
         Initialize the backend client.

         Inputs
         runtime: Backend runtime config.
         runner: Process runner.

         Outputs
         None.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used during app bootstrap.

         Why this exists
         Makes dependencies explicit and testable.
         */
        self.runtime = runtime
        self.runner = runner
    }

    public func fetchSnapshotResponse() async throws -> BackendSnapshotResponse {
        /**
         Summary
         Run the Python snapshot command and decode its JSON output.

         Inputs
         None.

         Outputs
         A `BackendSnapshotResponse` containing a validated snapshot.

         Side effects
         Spawns a Python subprocess and reads stdout and stderr.

         Error handling
         Throws `AppError` when the process fails or returns invalid JSON.

         Ties to other methods
         Called by `DashboardViewModel.refreshOnce`.

         Why this exists
         Provides the single data source for the SwiftUI dashboard on macOS.
         */
        let args = ["-m", "mac_health_checkup", "--snapshot-json"]
        let result = try await runner.run(
            executable: runtime.pythonExecutable,
            arguments: args,
            workingDirectory: runtime.repoRoot,
            timeoutSeconds: runtime.timeoutSeconds
        )

        guard !result.stdout.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw AppError.context(
                #fileID,
                #function,
                "Backend returned empty stdout (python=\(runtime.pythonExecutable)). stderr=\(result.stderr)"
            )
        }

        do {
            let data = Data(result.stdout.utf8)
            let snapshot = try JSONDecoder().decode(Snapshot.self, from: data)
            let validated = try snapshot.validated()
            return BackendSnapshotResponse(
                snapshot: validated,
                exitCode: result.exitCode,
                stderr: result.stderr,
                rawJSON: result.stdout
            )
        } catch let error as AppError {
            throw error
        } catch {
            throw AppError.context(#fileID, #function, "Failed to decode snapshot JSON", error)
        }
    }

    public func fetchSectionSnapshotResponse(sectionKey: String) async throws -> BackendSnapshotResponse {
        /**
         Summary
         Fetch a section snapshot by running the full Python snapshot command and returning the decoded payload.

         Inputs
         sectionKey: Section key to fetch.

         Outputs
         A `BackendSnapshotResponse` containing a validated snapshot.

         Side effects
         Spawns a Python subprocess.

         Error handling
         Throws `AppError` when execution or decoding fails.

         Ties to other methods
         Used as a fallback backend implementation when the local agent API is not used.

         Why this exists
         The Python backend CLI currently emits full snapshots; section refreshes are primarily served via the local agent API.
         */
        _ = sectionKey
        return try await fetchSnapshotResponse()
    }
}
#endif
