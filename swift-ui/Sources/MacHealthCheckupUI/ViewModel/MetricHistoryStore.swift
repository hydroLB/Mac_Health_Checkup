import Foundation
import MacHealthCheckupCore

@MainActor
final class MetricHistoryStore {
    /**
     Summary
     Maintain a bounded, persisted time-series history for numeric metrics.

     Inputs
     fileURL: Optional file path for persistence.
     retentionMinutes: Maximum age to retain in memory.
     maxPointsPerSeries: Maximum points per series after pruning.
     saveIntervalSeconds: Minimum seconds between disk writes.

     Outputs
     Time-series values keyed by `sectionKey|metricLabel`.

     Side effects
     Reads and writes a JSON file when persistence is enabled.

     Error handling
     Exposes non-fatal errors via `lastError` for UI surfacing.

     Ties to other methods
     Updated by `DashboardViewModel` after each snapshot refresh and read by sparkline views.

     Why this exists
     Users want graphs over time and data persistence between launches without adding a database dependency.
     */

    struct Point: Codable, Sendable {
        /**
         Summary
         Represent a single time-series sample point.

         Inputs
         t_unix_ms: Timestamp in unix milliseconds.
         v: Numeric value.

         Outputs
         Codable point for persistence.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `Series` and encoded in the history file.

         Why this exists
         Keeps history persistence stable and language-agnostic.
         */
        let t_unix_ms: Int
        let v: Double
    }

    struct FileModel: Codable, Sendable {
        /**
         Summary
         Persisted history file model.

         Inputs
         schema_version: Version for forwards-compatible decoding.
         series: Map of series keys to points.

         Outputs
         Codable root model.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Encoded and decoded by the store.

         Why this exists
         Allows safe evolution of the persisted format without breaking existing users.
         */
        let schema_version: Int
        let series: [String: [Point]]
    }

    private let fileURL: URL?
    private let retentionMinutes: Int
    private let maxPointsPerSeries: Int
    private let saveIntervalSeconds: Int

    private var data: [String: [Point]] = [:]
    private var lastSavedAt: Date?
    private(set) var lastError: AppError?

    init(fileURL: URL?, retentionMinutes: Int, maxPointsPerSeries: Int, saveIntervalSeconds: Int) {
        /**
         Summary
         Initialize the store and load persisted state when available.

         Inputs
         fileURL: Persistence file URL or nil to disable persistence.
         retentionMinutes: Retention window in minutes.
         maxPointsPerSeries: Cap per series.
         saveIntervalSeconds: Minimum save interval.

         Outputs
         None.

         Side effects
         Reads the history file if it exists.

         Error handling
         Stores a non-fatal `AppError` in `lastError` when load fails.

         Ties to other methods
         Called by `DashboardViewModel` during initialization.

         Why this exists
         Keeps app startup fast while still preserving useful history between runs.
         */
        self.fileURL = fileURL
        self.retentionMinutes = max(1, retentionMinutes)
        self.maxPointsPerSeries = max(10, maxPointsPerSeries)
        self.saveIntervalSeconds = max(1, saveIntervalSeconds)
        load()
    }

    func seriesPoints(sectionKey: String, metricLabel: String) -> [Point] {
        /**
         Summary
         Return history points for a specific metric series key.

         Inputs
         sectionKey: Section key.
         metricLabel: Metric label.

         Outputs
         Points array (possibly empty).

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by sparkline views.

         Why this exists
         Keeps series key formatting consistent and centralized.
         */
        let key = seriesKey(sectionKey: sectionKey, metricLabel: metricLabel)
        return data[key] ?? []
    }

    func recordSnapshot(_ snapshot: Snapshot) {
        /**
         Summary
         Extract numeric metrics from a snapshot and append them to history.

         Inputs
         snapshot: Snapshot payload.

         Outputs
         None.

         Side effects
         Updates in-memory history and may write to disk.

         Error handling
         Stores non-fatal persistence errors in `lastError`.

         Ties to other methods
         Called by `DashboardViewModel.refreshOnce`.

         Why this exists
         This is the single integration point between snapshot refreshes and the graphing subsystem.
         */
        let nowMs = Int(Date().timeIntervalSince1970 * 1000.0)
        for section in snapshot.sections {
            guard let metrics = section.metrics else { continue }
            for row in metrics {
                guard let value = parseNumeric(row.value) else { continue }
                append(sectionKey: section.key, metricLabel: row.label, timestampMs: nowMs, value: value)
            }
        }
        prune()
        saveIfNeeded()
    }

    private func seriesKey(sectionKey: String, metricLabel: String) -> String {
        /**
         Summary
         Create a stable series key for a section and metric label.

         Inputs
         sectionKey: Section key.
         metricLabel: Metric label.

         Outputs
         Combined series key string.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by getters and append logic.

         Why this exists
         Stable keys make persistence and lookup deterministic.
         */
        "\(sectionKey)|\(metricLabel)"
    }

    private func append(sectionKey: String, metricLabel: String, timestampMs: Int, value: Double) {
        /**
         Summary
         Append a point to a metric series with basic de-duplication.

         Inputs
         sectionKey: Section key.
         metricLabel: Metric label.
         timestampMs: Timestamp in unix milliseconds.
         value: Numeric value.

         Outputs
         None.

         Side effects
         Mutates in-memory history.

         Error handling
         None.

         Ties to other methods
         Used by `recordSnapshot`.

         Why this exists
         Prevents unbounded growth and keeps series readable for short-interval refreshes.
         */
        let key = seriesKey(sectionKey: sectionKey, metricLabel: metricLabel)
        var points = data[key] ?? []
        if let last = points.last, last.t_unix_ms == timestampMs {
            return
        }
        points.append(Point(t_unix_ms: timestampMs, v: value))
        if points.count > maxPointsPerSeries {
            points.removeFirst(points.count - maxPointsPerSeries)
        }
        data[key] = points
    }

    private func prune() {
        /**
         Summary
         Prune old points based on retention window.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Mutates in-memory history.

         Error handling
         None.

         Ties to other methods
         Called after recording new points.

         Why this exists
         Keeps memory and persistence bounded even at high refresh rates.
         */
        let cutoff = Int((Date().timeIntervalSince1970 - Double(retentionMinutes) * 60.0) * 1000.0)
        for (key, points) in data {
            let pruned = points.filter { $0.t_unix_ms >= cutoff }
            data[key] = pruned
        }
    }

    private func load() {
        /**
         Summary
         Load persisted history from disk when available.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Reads from disk.

         Error handling
         Stores a non-fatal `AppError` in `lastError` when decoding fails.

         Ties to other methods
         Called by `init`.

         Why this exists
         Provides graphs immediately after launch using previously collected data.
         */
        guard let fileURL else { return }
        if !FileManager.default.fileExists(atPath: fileURL.path) { return }
        do {
            let data = try Data(contentsOf: fileURL, options: [.mappedIfSafe])
            if data.isEmpty { return }
            let decoded = try JSONDecoder().decode(FileModel.self, from: data)
            if decoded.schema_version != 1 { return }
            self.data = decoded.series
            prune()
        } catch let error as AppError {
            lastError = error
        } catch {
            lastError = AppError.context(#fileID, #function, "Failed to load metric history at \(fileURL.path)", error)
        }
    }

    private func saveIfNeeded() {
        /**
         Summary
         Persist history to disk if enough time has elapsed since the last save.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Writes to disk when enabled.

         Error handling
         Stores a non-fatal `AppError` in `lastError` when saving fails.

         Ties to other methods
         Called after recording metrics.

         Why this exists
         Avoids excessive disk IO when auto-refresh is frequent.
         */
        guard let fileURL else { return }
        let now = Date()
        if let lastSavedAt, now.timeIntervalSince(lastSavedAt) < Double(saveIntervalSeconds) {
            return
        }

        do {
            let model = FileModel(schema_version: 1, series: data)
            let encoded = try JSONEncoder().encode(model)
            let parent = fileURL.deletingLastPathComponent()
            try FileManager.default.createDirectory(at: parent, withIntermediateDirectories: true)
            try encoded.write(to: fileURL, options: [.atomic])
            lastSavedAt = now
        } catch {
            lastError = AppError.context(#fileID, #function, "Failed to save metric history at \(fileURL.path)", error)
        }
    }

    private func parseNumeric(_ text: String) -> Double? {
        /**
         Summary
         Parse a numeric value from a metric string like "140 W" or "30C".

         Inputs
         text: Metric value string.

         Outputs
         Parsed Double or nil when no numeric value is present.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `recordSnapshot`.

         Why this exists
         Backend metrics are human-readable strings; graphs need a numeric value.
         */
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return nil }

        var number = ""
        var hasDigit = false
        for ch in trimmed {
            if ch.isNumber {
                number.append(ch)
                hasDigit = true
                continue
            }
            if ch == "." || ch == "-" {
                number.append(ch)
                continue
            }
            if hasDigit { break }
        }
        if number.isEmpty { return nil }
        return Double(number)
    }
}
