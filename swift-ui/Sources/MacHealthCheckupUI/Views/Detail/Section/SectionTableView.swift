import MacHealthCheckupCore
import SwiftUI

struct SectionTableView: View {
    /**
     Summary
     Render a scrollable table with dynamic columns and a capped visible height.

     Inputs
     theme: Theme values.
     key: Optional section key, used for per-section sizing preferences.
     model: Dashboard view model providing sizing preferences.
     table: Snapshot table payload.

     Outputs
     A SwiftUI view for table rendering.

     Side effects
     None.

     Error handling
     None. Missing cells are rendered as empty strings.

     Ties to other methods
     Used by `SectionDetailView` for generic table sections.

     Why this exists
     Keeps tables readable and usable for long outputs without stretching the entire page.
     */

    let theme: Theme
    let key: String?
    @ObservedObject var model: DashboardViewModel
    let table: SnapshotTable

    var body: some View {
        /**
         Summary
         Render a table grid with consistent styling and help tooltips.

         Inputs
         None.

         Outputs
         A SwiftUI view containing a scrollable grid.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Uses `DashboardViewModel.preferredTableVisibleRows` to size the table view.

         Why this exists
         Table outputs can be large; sizing keeps the detail view usable without nested scroll conflicts.
         */
        let maxRows = key.flatMap { model.preferredTableVisibleRows(for: $0) }
        let targetRows = maxRows ?? min(10, max(3, table.rows.count))
        let headerHeight: CGFloat = 26
        let rowHeight: CGFloat = 22
        let maxHeight = headerHeight + (CGFloat(targetRows) * rowHeight)

        ScrollView([.horizontal, .vertical]) {
            LazyVGrid(
                columns: Array(
                    repeating: GridItem(.flexible(minimum: 120), alignment: .leading),
                    count: max(1, table.headers.count)
                ),
                alignment: .leading,
                spacing: 8
            ) {
                ForEach(Array(table.headers.enumerated()), id: \.offset) { _, header in
                    Text(header)
                        .font(theme.fonts.mono)
                        .foregroundStyle(theme.colors.label)
                        .lineLimit(1)
                        .help(HelpText.tableHeader(sectionKey: key, header: header))
                }
                ForEach(0..<table.headers.count, id: \.self) { _ in
                    Rectangle()
                        .fill(theme.colors.cardBorder.opacity(0.8))
                        .frame(height: 1)
                }

                ForEach(Array(table.rows.enumerated()), id: \.offset) { rowIndex, row in
                    ForEach(0..<max(1, table.headers.count), id: \.self) { colIndex in
                        let value = colIndex < row.count ? row[colIndex] : ""
                        let header = colIndex < table.headers.count ? table.headers[colIndex] : ""
                        Text(value)
                            .font(theme.fonts.mono)
                            .foregroundStyle(theme.colors.field)
                            .lineLimit(2)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, 2)
                            .background(rowIndex.isMultiple(of: 2) ? Color.clear : theme.colors.background.opacity(0.08))
                            .help(HelpText.tableCell(sectionKey: key, header: header, value: value))
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.vertical, 2)
        }
        .textSelection(.enabled)
        .frame(maxHeight: maxHeight)
    }
}

