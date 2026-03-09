import MacHealthCheckupCore
import SwiftUI

struct OverviewTablePreview: View {
    let theme: Theme
    let headers: [String]
    let rows: [[String]]

    var body: some View {
        /**
         Summary
         Render a compact, read-only table preview for overview cards.

         Inputs
         None.

         Outputs
         A SwiftUI view showing up to a few rows and columns.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `OverviewExpandedContent`.

         Why this exists
         Full tables can be large; a small preview hints at content without adding heavy scroll regions in the overview list.
         */
        let maxRows = 4
        let maxCols = min(3, max(1, headers.count))
        VStack(alignment: .leading, spacing: theme.layout.verticalScaled(6)) {
            if !headers.isEmpty {
                HStack(spacing: 10) {
                    ForEach(0..<maxCols, id: \.self) { idx in
                        Text(headers[idx])
                            .font(theme.fonts.caption)
                            .foregroundStyle(theme.colors.label)
                            .lineLimit(1)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .help(HelpText.tableHeader(sectionKey: nil, header: headers[idx]))
                    }
                }
                .padding(.bottom, theme.layout.verticalScaled(2))
            }
            ForEach(0..<min(maxRows, rows.count), id: \.self) { rowIndex in
                let row = rows[rowIndex]
                HStack(spacing: 10) {
                    ForEach(0..<maxCols, id: \.self) { colIndex in
                        let value = row.indices.contains(colIndex) ? row[colIndex] : ""
                        let header = headers.indices.contains(colIndex) ? headers[colIndex] : "Value"
                        Text(value)
                            .font(theme.fonts.mono)
                            .foregroundStyle(theme.colors.field)
                            .lineLimit(1)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .help("\(header)\n\nCurrent value: \(value)")
                    }
                }
                if rowIndex < min(maxRows, rows.count) - 1 {
                    Divider().opacity(0.35)
                }
            }
            if rows.count > maxRows {
                Text("… \(rows.count - maxRows) more rows")
                    .font(theme.fonts.caption)
                    .foregroundStyle(theme.colors.label)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, theme.layout.verticalScaled(10))
        .background(theme.colors.background.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}
