import MacHealthCheckupCore
import SwiftUI

enum OverviewContentPolicy {
    static func alertMetrics(payload: SnapshotSection?) -> [MetricsRow] {
        (payload?.metrics ?? []).filter {
            OverviewGridPolicy.isAlert(for: SectionHealth.fromStatusString($0.status))
        }
    }

    static func summary(payload: SnapshotSection?, fallback: String) -> String {
        let alerts = alertMetrics(payload: payload)
        return alerts.isEmpty ? fallback : alerts.map { "\($0.label): \($0.value)" }.joined(separator: " | ")
    }

    static func hasExpandableContent(payload: SnapshotSection?) -> Bool {
        /**
         Summary
         Decide whether an overview card should show an expand/collapse affordance.

         Inputs
         payload: Optional snapshot section payload.

         Outputs
         True when the section has additional content worth previewing.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `OverviewView` to conditionally render a disclosure caret.

         Why this exists
         Keeps the Overview clean while still allowing quick inspection without navigating into a section.
         */
        let alerts = alertMetrics(payload: payload)
        if !alerts.isEmpty { return alerts.count > 1 }
        if let field = payload?.field {
            let trimmed = field.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.count > 160 || trimmed.contains("\n") { return true }
        }
        if let table = payload?.table, !table.rows.isEmpty { return true }
        return false
    }
}

