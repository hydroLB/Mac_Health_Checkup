import Foundation

public struct BackendSnapshotResponse: Sendable {
    /**
     Summary
     Carry a decoded snapshot plus backend execution metadata.

     Inputs
     snapshot: Decoded snapshot.
     exitCode: Backend status indicator. For local Python backend this is the process exit code.
     stderr: Backend stderr output or diagnostic text.
     rawJSON: Optional raw JSON payload for caching or debugging.

     Outputs
     Value container for the refresh layer.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Returned by `SnapshotBackend.fetchSnapshotResponse` and consumed by `DashboardViewModel`.

     Why this exists
     Allows the UI to render partial snapshots while still surfacing backend issues.
     */

    public let snapshot: Snapshot
    public let exitCode: Int32
    public let stderr: String
    public let rawJSON: String?
}

public protocol SnapshotBackend: Sendable {
    /**
     Summary
     Define a backend interface that can fetch snapshot payloads for the UI.

     Inputs
     None.

     Outputs
     `BackendSnapshotResponse` values.

     Side effects
     Implementation-dependent IO such as network requests or process execution.

     Error handling
     Throws `AppError` when snapshot fetching fails.

     Ties to other methods
     Implemented by `PythonBackendClient` (macOS) and `RemoteBackendClient` (iOS).

     Why this exists
     Allows the same SwiftUI UI to run on macOS and iOS with different backends.
     */

    func fetchSnapshotResponse() async throws -> BackendSnapshotResponse

    func fetchSectionSnapshotResponse(sectionKey: String) async throws -> BackendSnapshotResponse
}
