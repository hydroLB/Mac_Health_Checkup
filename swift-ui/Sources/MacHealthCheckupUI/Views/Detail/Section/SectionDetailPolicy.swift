import MacHealthCheckupCore
import SwiftUI

enum SectionDetailPolicy {
    static func shouldShowFieldSummaryCard(sectionKey: String?, payload: SnapshotSection) -> Bool {
        /**
         Summary
         Decide whether to render the "field" summary card for a section.

         Inputs
         sectionKey: Optional section key.
         payload: Snapshot section payload.

         Outputs
         True when the summary card should be shown.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `SectionDetailView` to avoid redundant summaries when metrics or tables already provide details.

         Why this exists
         Some sections publish a verbose `field` plus a richer metrics/table representation; showing both is redundant and can read like duplicate data.
         */
        let key = (sectionKey ?? "").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let field = payload.field?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if field.isEmpty { return false }

        let hasMetrics = (payload.metrics?.isEmpty == false)
        let hasTable = (payload.table != nil && !(payload.table?.rows.isEmpty ?? true))

        if hasMetrics || hasTable {
            if [
                "fan",
                "battery",
                "ssd",
                "network",
                "input",
                "display",
                "security",
                "system",
                "updates",
                "devices",
                "ports",
            ].contains(key) {
                return false
            }
        }

        return true
    }

    static func tableTitle(for key: String) -> String? {
        /**
         Summary
         Provide an appropriate table title for a section detail view.

         Inputs
         key: Section key string.

         Outputs
         Optional title string. Nil hides the title entirely.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `SectionDetailView` to avoid showing a generic "Table" header for list-style sections.

         Why this exists
         Custom list sections already communicate their structure; a redundant "Table" header looks non-native.
         */
        switch key {
        case "display", "input", "devices", "ports":
            return nil
        default:
            return "Table"
        }
    }
}
