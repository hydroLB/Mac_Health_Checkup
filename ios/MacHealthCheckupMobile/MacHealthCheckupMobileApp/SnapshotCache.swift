import Foundation
import MacHealthCheckupCore

enum SnapshotCacheError: Error, CustomStringConvertible {
    case invalidCacheDirectory(file: StaticString, function: StaticString, message: String)
    case ioFailure(file: StaticString, function: StaticString, message: String, underlying: Error)
    case decodeFailure(file: StaticString, function: StaticString, message: String, underlying: Error)

    var description: String {
        switch self {
        case let .invalidCacheDirectory(file, function, message):
            return "\(file) \(function): \(message)"
        case let .ioFailure(file, function, message, underlying):
            return "\(file) \(function): \(message). underlying=\(underlying)"
        case let .decodeFailure(file, function, message, underlying):
            return "\(file) \(function): \(message). underlying=\(underlying)"
        }
    }
}

struct SnapshotCache: Sendable {
    /**
     Summary
     Persist the last successful snapshot locally to improve perceived performance on launch.

     Inputs
     fileURL: Cache file location.

     Outputs
     Provides load and save operations for a `Snapshot`.

     Side effects
     Reads and writes a file in Application Support.

     Error handling
     Throws `SnapshotCacheError` with context for IO and decoding failures.

     Ties to other methods
     Used by `MobileAppState.connect` to prefill the dashboard before the first refresh.

     Why this exists
     A remote client should not show a blank screen while the first network request is in-flight.
     */

    let fileURL: URL

    static func `default`() throws -> SnapshotCache {
        /**
         Summary
         Construct a default cache using the Application Support directory.

         Inputs
         None.

         Outputs
         A `SnapshotCache` instance.

         Side effects
         Creates the cache directory if missing.

         Error handling
         Throws when directory resolution or creation fails.

         Ties to other methods
         Used by `MobileAppState` initialization.

         Why this exists
         Centralizes cache location logic for consistent behavior across views.
         */
        let fm = FileManager.default
        guard let root = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
            throw SnapshotCacheError.invalidCacheDirectory(
                file: #fileID,
                function: #function,
                message: "Application Support directory not available"
            )
        }
        let dir = root.appendingPathComponent("MacHealthCheckupMobile", isDirectory: true)
        do {
            try fm.createDirectory(at: dir, withIntermediateDirectories: true)
        } catch {
            throw SnapshotCacheError.ioFailure(
                file: #fileID,
                function: #function,
                message: "Failed to create cache directory",
                underlying: error
            )
        }
        return SnapshotCache(fileURL: dir.appendingPathComponent("last-snapshot.json"))
    }

    func load() throws -> Snapshot? {
        /**
         Summary
         Load the cached snapshot from disk.

         Inputs
         None.

         Outputs
         Optional snapshot.

         Side effects
         Reads a file.

         Error handling
         Throws for IO failures and decode failures.

         Ties to other methods
         Used by `MobileAppState` to prefill the UI.

         Why this exists
         Enables instant first paint even when offline or on slow networks.
         */
        let fm = FileManager.default
        if !fm.fileExists(atPath: fileURL.path) {
            return nil
        }
        do {
            let data = try Data(contentsOf: fileURL)
            let snapshot = try JSONDecoder().decode(Snapshot.self, from: data)
            return try snapshot.validated()
        } catch let error as AppError {
            throw SnapshotCacheError.decodeFailure(
                file: #fileID,
                function: #function,
                message: "Cached snapshot validation failed",
                underlying: error
            )
        } catch {
            if error is DecodingError {
                throw SnapshotCacheError.decodeFailure(
                    file: #fileID,
                    function: #function,
                    message: "Cached snapshot decode failed",
                    underlying: error
                )
            }
            throw SnapshotCacheError.ioFailure(
                file: #fileID,
                function: #function,
                message: "Failed to read cached snapshot",
                underlying: error
            )
        }
    }

    func save(_ snapshot: Snapshot) throws {
        /**
         Summary
         Save the latest snapshot to disk atomically.

         Inputs
         snapshot: Snapshot to persist.

         Outputs
         None.

         Side effects
         Writes a file.

         Error handling
         Throws for IO failures.

         Ties to other methods
         Called after a successful refresh.

         Why this exists
         Keeps a reliable local copy for quick startup and offline inspection.
         */
        do {
            let data = try JSONEncoder().encode(snapshot)
            try data.write(to: fileURL, options: [.atomic])
        } catch {
            throw SnapshotCacheError.ioFailure(
                file: #fileID,
                function: #function,
                message: "Failed to write cached snapshot",
                underlying: error
            )
        }
    }
}

