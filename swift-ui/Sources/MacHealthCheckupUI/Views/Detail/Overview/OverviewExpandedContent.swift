import MacHealthCheckupCore
import SwiftUI

struct OverviewExpandedContent: View {
    let theme: Theme
    @ObservedObject var model: DashboardViewModel
    let sectionKey: String
    let payload: SnapshotSection?

    var body: some View {
        /**
         Summary
         Render a compact preview of section content within the overview card when expanded.

         Inputs
         None.

         Outputs
         A SwiftUI view containing metric and table previews.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `OverviewView` when a card is expanded.

         Why this exists
         Users want to see more details at a glance without losing their place in the overview list.
         */
        VStack(alignment: .leading, spacing: theme.layout.verticalScaled(10)) {
            if let field = payload?.field {
                let trimmed = field.trimmingCharacters(in: .whitespacesAndNewlines)
                if !trimmed.isEmpty {
                    Text(trimmed)
                        .font(theme.fonts.body)
                        .foregroundStyle(theme.colors.field)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .lineLimit(8)
                        .textSelection(.enabled)
                        .help(HelpText.section(key: sectionKey))
                }
            }
            if let metrics = payload?.metrics, !metrics.isEmpty {
                MetricsGridView(theme: theme, sectionKey: nil, model: model, rows: Array(metrics.prefix(6)))
            }
            if let table = payload?.table, !table.rows.isEmpty {
                OverviewTablePreview(theme: theme, headers: table.headers, rows: table.rows)
            }
        }
    }
}
