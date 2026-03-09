import MacHealthCheckupCore
import SwiftUI

enum OverviewContentPolicy {
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
        if let field = payload?.field {
            let trimmed = field.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.count > 160 || trimmed.contains("\n") { return true }
        }
        if let metrics = payload?.metrics, metrics.count > 1 { return true }
        if let table = payload?.table, !table.rows.isEmpty { return true }
        return false
    }
}

