import Foundation
import MacHealthCheckupCore

enum DashboardRefreshScheduler {
    static func wait(milliseconds: Int) async -> Bool {
        do {
            let nanos = UInt64(max(250, milliseconds)) * 1_000_000
            try await Task.sleep(nanoseconds: nanos)
            return !Task.isCancelled
        } catch is CancellationError {
            return false
        } catch {
            return false
        }
    }
}

enum DashboardSnapshotResponsePolicy {
    static func shouldCacheFullSnapshot(_ response: BackendSnapshotResponse) -> Bool {
        response.exitCode == 0 && response.snapshot.ok
    }

    static func acceptedSection(
        from response: BackendSnapshotResponse,
        key: String
    ) -> SnapshotSection? {
        guard response.exitCode == 0, response.snapshot.ok else {
            return nil
        }
        guard let section = response.snapshot.sections.first(where: { $0.key == key }) else {
            return nil
        }
        if case let .bool(ok)? = section.diagnostics?["ok"], !ok {
            return nil
        }
        return section
    }
}

enum DashboardSectionNavigation {
    static func visibleSections(
        from sections: [SectionDescriptor],
        isSectionHidden: (String) -> Bool
    ) -> [SectionDescriptor] {
        sections.filter { !isSectionHidden($0.key) }
    }

    static func sidebarSections(
        from sections: [SectionDescriptor],
        overviewKey: String,
        searchText: String,
        isSectionHidden: (String) -> Bool
    ) -> [SectionDescriptor] {
        let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let visibleSections = visibleSections(from: sections, isSectionHidden: isSectionHidden)
        let candidates: [SectionDescriptor] = if query.isEmpty {
            visibleSections
        } else {
            visibleSections.filter { section in
                section.title.lowercased().contains(query)
                    || section.subtitle.lowercased().contains(query)
                    || section.key.lowercased().contains(query)
            }
        }
        let overview = SectionDescriptor(title: "Overview", subtitle: "Health alerts", key: overviewKey)
        return [overview] + candidates
    }

    static func normalizedSelectedSectionKey(
        selectedSectionKey: String?,
        overviewKey: String,
        sections: [SectionDescriptor],
        isSectionHidden: (String) -> Bool
    ) -> String? {
        guard let selectedSectionKey else {
            return nil
        }
        guard selectedSectionKey != overviewKey else {
            return overviewKey
        }
        guard sections.contains(where: { $0.key == selectedSectionKey }) else {
            return overviewKey
        }
        return isSectionHidden(selectedSectionKey) ? overviewKey : selectedSectionKey
    }
}

enum DashboardSectionSummaryFormatter {
    static func summary(for key: String, payload: SnapshotSection?) -> String {
        guard let payload else {
            return "No data yet"
        }

        let normalizedKey = key.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()

        if ["battery", "fan", "ssd", "network", "input", "system", "updates"].contains(normalizedKey) {
            if let metrics = payload.metrics, !metrics.isEmpty {
                if normalizedKey == "network" {
                    let preferredLabels = ["SSID", "IPv4", "RSSI", "Interface"]
                    for label in preferredLabels {
                        if let row = metrics.first(where: { $0.label == label }) {
                            return DashboardTextFormatter.truncate("\(row.label): \(row.value)", maxChars: 160)
                        }
                    }
                }
                if normalizedKey == "system" {
                    let disk = metrics.first(where: {
                        $0.label.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "disk free"
                    })
                    let memory = metrics.first(where: {
                        $0.label.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "memory free"
                    })
                    var parts: [String] = []
                    if let disk {
                        parts.append("Disk free: \(disk.value)")
                    }
                    if let memory {
                        parts.append("Memory free: \(memory.value)")
                    }
                    if !parts.isEmpty {
                        return DashboardTextFormatter.truncate(parts.joined(separator: " | "), maxChars: 160)
                    }
                }
                if normalizedKey == "updates" {
                    let updatesRow = metrics.first(where: {
                        $0.label.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "updates"
                    })
                    if let updatesRow {
                        let value = updatesRow.value.trimmingCharacters(in: .whitespacesAndNewlines)
                        if value.lowercased() == "up to date" {
                            return "Updates: 0 available"
                        }
                        if !value.isEmpty {
                            return DashboardTextFormatter.truncate("Updates: \(value)", maxChars: 160)
                        }
                    }
                    let firstRow = metrics.first(where: {
                        $0.label.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "first"
                    })
                    if let firstRow {
                        let value = firstRow.value.trimmingCharacters(in: .whitespacesAndNewlines)
                        if !value.isEmpty {
                            return DashboardTextFormatter.truncate("First update: \(value)", maxChars: 160)
                        }
                    }
                }
                if let first = metrics.first {
                    return DashboardTextFormatter.truncate("\(first.label): \(first.value)", maxChars: 160)
                }
            }

            if let table = payload.table {
                let rows = table.rows.count
                if normalizedKey == "input" {
                    let names = table.rows.compactMap { row -> String? in
                        if row.indices.contains(1) {
                            return row[1].trimmingCharacters(in: .whitespacesAndNewlines)
                        }
                        return row.first?.trimmingCharacters(in: .whitespacesAndNewlines)
                    }
                    .filter { !$0.isEmpty }
                    if !names.isEmpty {
                        return DashboardTextFormatter.truncate(names.prefix(2).joined(separator: "  •  "), maxChars: 160)
                    }
                    return rows == 1 ? "Input: 1 device" : "Input: \(rows) devices"
                }
            }
        }

        if let field = payload.field?.trimmingCharacters(in: .whitespacesAndNewlines), !field.isEmpty {
            return DashboardTextFormatter.truncate(field, maxChars: 160)
        }

        if let metrics = payload.metrics, let first = metrics.first {
            return DashboardTextFormatter.truncate("\(first.label): \(first.value)", maxChars: 160)
        }

        if let table = payload.table {
            let rows = table.rows.count
            if key == "display" {
                let summaries = table.rows.prefix(2).map { row -> String in
                    let name = row.indices.contains(0) ? row[0] : ""
                    let resolution = row.indices.contains(1) ? row[1] : ""
                    let refresh = row.indices.contains(4) ? row[4] : ""
                    let parts = [name, resolution, refresh].map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                        .filter { !$0.isEmpty && $0 != "?" }
                    return parts.joined(separator: " | ")
                }.filter { !$0.isEmpty }
                if !summaries.isEmpty {
                    return DashboardTextFormatter.truncate(summaries.joined(separator: "  •  "), maxChars: 160)
                }
                return rows == 1 ? "Display: 1 row" : "Display: \(rows) rows"
            }
            if key == "devices" {
                let names = table.rows.compactMap { row -> String? in
                    if row.indices.contains(1) {
                        return row[1].trimmingCharacters(in: .whitespacesAndNewlines)
                    }
                    return row.first?.trimmingCharacters(in: .whitespacesAndNewlines)
                }
                .filter { !$0.isEmpty }
                if !names.isEmpty {
                    return DashboardTextFormatter.truncate(names.prefix(3).joined(separator: ", "), maxChars: 160)
                }
                return rows == 1 ? "Devices: 1 row" : "Devices: \(rows) rows"
            }
            if rows == 1 {
                return "Table: 1 row"
            }
            return "Table: \(rows) rows"
        }

        if let diagnostics = payload.diagnostics {
            if case let .string(error) = diagnostics["error"], !error.isEmpty {
                return DashboardTextFormatter.truncate("Error: \(error)", maxChars: 160)
            }
            if case let .bool(ok) = diagnostics["ok"], ok == false {
                return "Error: section failed"
            }
        }

        return "No data yet"
    }
}

enum DashboardBackendWarningFormatter {
    static func warning(
        exitCode: Int32,
        snapshot: Snapshot,
        stderr: String,
        file: StaticString,
        function: StaticString
    ) -> AppError? {
        if exitCode == 0 && snapshot.ok {
            return nil
        }

        let failedSections = failedSectionKeys(snapshot: snapshot)
        if !failedSections.isEmpty {
            let sectionCount = failedSections.count
            let sectionNoun = sectionCount == 1 ? "section check failed" : "section checks failed"
            let listed = formattedFailedSectionList(failedSections)
            let message =
                "Backend completed with partial results (exit code \(exitCode)). \(sectionCount) \(sectionNoun): \(listed). " +
                "Review backend logs for details."
            return AppError.context(file, function, message)
        }

        let fallback = snapshot.error?.trimmingCharacters(in: .whitespacesAndNewlines) ?? "Snapshot reported ok=false."
        let trimmedStderr = stderr.trimmingCharacters(in: .whitespacesAndNewlines)
        let stderrSuffix = trimmedStderr.isEmpty ? "" : " stderr=\(DashboardTextFormatter.truncate(trimmedStderr, maxChars: 240))"
        return AppError.context(
            file,
            function,
            "Backend completed with warnings (exit code \(exitCode)). \(fallback)\(stderrSuffix)"
        )
    }

    static func failedSectionKeys(snapshot: Snapshot) -> [String] {
        var out: [String] = []
        for section in snapshot.sections {
            guard let diagnostics = section.diagnostics else {
                continue
            }
            if case let .bool(ok) = diagnostics["ok"], ok == false {
                out.append(section.key)
            }
        }
        return out
    }

    static func formattedFailedSectionList(_ sectionKeys: [String]) -> String {
        if sectionKeys.isEmpty {
            return "none"
        }
        if sectionKeys.count <= 4 {
            return sectionKeys.joined(separator: ", ")
        }
        let head = sectionKeys.prefix(4).joined(separator: ", ")
        let remaining = sectionKeys.count - 4
        return "\(head), and \(remaining) more"
    }
}

enum DashboardTextFormatter {
    static func truncate(_ text: String, maxChars: Int) -> String {
        if maxChars <= 0 {
            return ""
        }
        if text.count <= maxChars {
            return text
        }
        let prefixCount = Swift.max(0, maxChars - 1)
        return String(text.prefix(prefixCount)) + "…"
    }
}
