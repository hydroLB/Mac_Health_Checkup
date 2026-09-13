import Foundation
import MacHealthCheckupCore

enum DashboardSnapshotThemeResolver {
    static func theme(
        from snapshot: Snapshot,
        file: StaticString,
        function: StaticString
    ) throws -> Theme {
        do {
            return try Theme(snapshot: snapshot)
        } catch let error as AppError {
            throw error
        } catch {
            throw AppError.context(file, function, "Failed to apply theme", error)
        }
    }
}

enum DashboardSnapshotCatalogMapper {
    static func sections(from snapshot: Snapshot) -> [SectionDescriptor]? {
        guard !snapshot.section_catalog.isEmpty else {
            return nil
        }
        return snapshot.section_catalog.map { item in
            SectionDescriptor(title: item.title, subtitle: item.subtitle, key: item.key)
        }
    }
}

enum DashboardSnapshotCache {
    static func loadSnapshotIfAvailable(
        at fileURL: URL?,
        fileManager: FileManager = .default
    ) throws -> Snapshot? {
        guard let fileURL else {
            return nil
        }
        guard fileManager.fileExists(atPath: fileURL.path) else {
            return nil
        }

        let data = try Data(contentsOf: fileURL, options: [.mappedIfSafe])
        guard !data.isEmpty else {
            return nil
        }

        let decoded = try JSONDecoder().decode(Snapshot.self, from: data)
        return try decoded.validated()
    }

    @discardableResult
    static func writeSnapshotIfPossible(
        rawJSON: String?,
        to fileURL: URL?,
        fileManager: FileManager = .default
    ) throws -> Bool {
        guard let fileURL else {
            return false
        }
        guard let rawJSON, !rawJSON.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return false
        }

        let parent = fileURL.deletingLastPathComponent()
        try fileManager.createDirectory(
            at: parent,
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        try (rawJSON + "\n").write(to: fileURL, atomically: true, encoding: .utf8)
        try fileManager.setAttributes([.posixPermissions: 0o600], ofItemAtPath: fileURL.path)
        return true
    }
}
