import SwiftUI
import MacHealthCheckupCore

public struct DetailView: View {
    /**
     Summary
     Render a selected section's content as iOS-style cards.

     Inputs
     theme: Theme values.
     model: Dashboard view model.

     Outputs
     A SwiftUI detail view.

     Side effects
     None.

     Error handling
     None. Displays empty state when data is unavailable.

     Ties to other methods
     Used by `RootView` and consumes `SnapshotSection` from the view model.

     Why this exists
     Keeps section rendering consistent across all sections and avoids one-off UI styles.
     */

    @ObservedObject public var model: DashboardViewModel

    public var body: some View {
        /**
         Summary
         Route to the overview screen or the selected section detail screen.

         Inputs
         None.

         Outputs
         A SwiftUI view representing the current selection.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Uses `DashboardViewModel.selectedSectionKey` and `DashboardViewModel.overviewKey`.

         Why this exists
         Keeps selection routing centralized so the rest of the UI can stay focused on rendering.
         */
        let selectedKey = model.selectedSectionKey
        if selectedKey == DashboardViewModel.overviewKey {
            OverviewView(theme: model.theme, model: model)
        } else {
            SectionDetailView(theme: model.theme, model: model, selectedKey: selectedKey)
        }
    }
}

private struct SectionDetailView: View {
    let theme: Theme
    @ObservedObject var model: DashboardViewModel
    let selectedKey: String?

    var body: some View {
        /**
         Summary
         Render a single section's detailed content with cards, tables, and diagnostics.

         Inputs
         None.

         Outputs
         A SwiftUI view for the section detail screen.

         Side effects
         Supports pull-to-refresh via `.refreshable`.

         Error handling
         None. Displays placeholders when data is unavailable.

         Ties to other methods
         Uses `DashboardViewModel.sectionPayload`, `DashboardViewModel.sectionHealth`, and `DashboardViewModel.refreshOnce`.

         Why this exists
         Provides a consistent, native-feeling detail screen for all sections without per-section UI divergence.
         */
        let descriptor = model.sections.first(where: { $0.key == selectedKey })
        let payload = selectedKey.flatMap { model.sectionPayload(for: $0) }
        let health = selectedKey.map { model.sectionHealth(for: $0) } ?? .unknown

        ScrollView {
            VStack(alignment: .leading, spacing: theme.layout.cardSpacing) {
                if selectedKey == nil {
                    Card(theme: theme) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Select a section")
                                .font(theme.fonts.sectionTitle)
                                .foregroundStyle(theme.colors.section)
                            Text("Choose a section from the sidebar to see details.")
                                .font(theme.fonts.body)
                                .foregroundStyle(theme.colors.field)
                        }
                    }
                } else {
                    if let descriptor {
                        HStack(alignment: .firstTextBaseline, spacing: 10) {
                            Button {
                                model.selectedSectionKey = DashboardViewModel.overviewKey
                            } label: {
                                HStack(spacing: 6) {
                                    Image(systemName: "chevron.left")
                                    Text("Overview")
                                }
                            }
                            .buttonStyle(.plain)
                            .foregroundStyle(theme.colors.label)

                            VStack(alignment: .leading, spacing: 4) {
                                Text(descriptor.title)
                                    .font(theme.fonts.sectionTitle)
                                    .foregroundStyle(theme.colors.section)
                                Text(descriptor.subtitle)
                                    .font(theme.fonts.caption)
                                    .foregroundStyle(theme.colors.label)
                            }
                            Spacer()
                            if selectedKey != nil {
                                SectionHealthBadge(theme: theme, health: health)
                            }
                        }
                    }

                    if selectedKey == "performance", model.thermalPermissionRequired(sectionKey: "performance") {
                        Card(theme: theme) {
                            VStack(alignment: .leading, spacing: 10) {
                                Text("Temperature sensors need authorization")
                                    .font(theme.fonts.body)
                                    .foregroundStyle(theme.colors.label)
                                Text("macOS restricts low-level thermal sensors. Authorize once and the Performance section will populate a full sensor table.")
                                    .font(theme.fonts.body)
                                    .foregroundStyle(theme.colors.field)
                                    .fixedSize(horizontal: false, vertical: true)
                                Button("Open Temperature Sensors Settings") {
                                    model.openSettings(focus: .temperatureSensors)
                                }
                                .buttonStyle(.borderedProminent)
                                .tint(theme.colors.section)
                            }
                        }
                    }

                    Card(theme: theme) {
                        if let payload, let field = payload.field, !field.isEmpty {
                            Text(field)
                                .font(theme.fonts.body)
                                .foregroundStyle(theme.colors.field)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .textSelection(.enabled)
                        } else if model.isRefreshing || model.snapshot == nil {
                            HStack(spacing: 10) {
                                ProgressView()
                                    .controlSize(.small)
                                Text(model.refreshStatusText ?? "Refreshing…")
                                    .font(theme.fonts.body)
                                    .foregroundStyle(theme.colors.field)
                            }
                        } else {
                            Text("No data yet")
                                .font(theme.fonts.body)
                                .foregroundStyle(theme.colors.field)
                        }
                    }

                    if let metrics = payload?.metrics, !metrics.isEmpty {
                        Card(theme: theme) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Metrics")
                                    .font(theme.fonts.body)
                                    .foregroundStyle(theme.colors.label)
                                MetricsGridView(theme: theme, sectionKey: selectedKey, model: model, rows: metrics)
                            }
                        }
                    }

                    if let table = payload?.table {
                        Card(theme: theme) {
                            VStack(alignment: .leading, spacing: 8) {
                                if let key = selectedKey,
                                   let title = _tableTitleForSection(key: key),
                                   !title.isEmpty
                                {
                                    Text(title)
                                        .font(theme.fonts.body)
                                        .foregroundStyle(theme.colors.label)
                                }
                                if selectedKey == "display" {
                                    DisplayListTableView(theme: theme, table: table)
                                } else if selectedKey == "input" {
                                    InputDevicesListTableView(theme: theme, table: table)
                                } else if selectedKey == "devices" {
                                    DevicesListTableView(theme: theme, table: table)
                                } else if selectedKey == "ports" {
                                    IndentedTreeTableView(theme: theme, title: "USB", rows: table.rows)
                                } else {
                                    SectionTableView(
                                        theme: theme,
                                        key: selectedKey,
                                        model: model,
                                        table: table
                                    )
                                }
                            }
                        }
                    }

                }
            }
            .padding(theme.layout.pagePadding)
        }
        .background(theme.colors.background)
    }
}

private func _tableTitleForSection(key: String) -> String? {
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
     Custom list sections (Display, Input, Devices, Ports) already communicate their structure; a redundant "Table" header looks non-native.
     */
    switch key {
    case "display", "input", "devices", "ports":
        return nil
    default:
        return "Table"
    }
}

private struct MetricsGridView: View {
    let theme: Theme
    let sectionKey: String?
    @ObservedObject var model: DashboardViewModel
    let rows: [MetricsRow]

    var body: some View {
        /**
         Summary
         Render a metric list with consistent status badges.

         Inputs
         None.

         Outputs
         A SwiftUI view for metric rows.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Uses `SectionHealth.fromStatusString` for badge mapping.

        Why this exists
        Presents metrics in a clean, scannable layout while keeping status styling consistent.
         */
        VStack(spacing: 8) {
            if sectionKey == "performance" {
                HStack {
                    Text("Sensor")
                        .font(theme.fonts.caption)
                        .foregroundStyle(theme.colors.label)
                    Spacer()
                    Text("Value °C")
                        .font(theme.fonts.caption)
                        .foregroundStyle(theme.colors.label)
                }
                .padding(.bottom, 2)
            }
            ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                let health = SectionHealth.fromStatusString(row.status)
                HStack(spacing: 10) {
                    if let icon = _metricIconName(sectionKey: sectionKey, label: row.label) {
                        Image(systemName: icon)
                            .foregroundStyle(theme.colors.label)
                            .frame(width: 16)
                    }
                    Text(row.label)
                        .font(theme.fonts.body)
                        .foregroundStyle(theme.colors.field)
                    Spacer()
                    Text(row.value)
                        .font(theme.fonts.mono)
                        .foregroundStyle(_metricValueColor(theme: theme, health: health))
                    if let sectionKey {
                        let points = model.historyPoints(sectionKey: sectionKey, metricLabel: row.label)
                        if points.count >= 3 {
                            SparklineView(theme: theme, points: points)
                                .frame(width: 120)
                        }
                    }
                    SectionHealthBadge(theme: theme, health: health)
                }
            }
        }
    }
}

private func _metricValueColor(theme: Theme, health: SectionHealth) -> Color {
    /**
     Summary
     Map a row health state to a value foreground color.

     Inputs
     theme: Theme for color mapping.
     health: Row health state.

     Outputs
     SwiftUI Color for the value text.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Used by `MetricsGridView` to color-code temperatures and other metrics.

     Why this exists
     Mac Fan Control style tables rely on quick visual severity cues.
     */
    switch health {
    case .ok:
        return theme.colors.ok
    case .warn:
        return theme.colors.warn
    case .bad:
        return theme.colors.bad
    case .unknown:
        return theme.colors.foreground
    }
}

private func _metricIconName(sectionKey: String?, label: String) -> String? {
    /**
     Summary
     Choose a system symbol for a metric row based on section key and label.

     Inputs
     sectionKey: Optional section key for additional context.
     label: Metric label string.

     Outputs
     Optional SF Symbol name.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Used by `MetricsGridView` to make dense lists more scannable.

     Why this exists
     Iconography improves at-a-glance parsing in tables with many similar sensors.
     */
    let text = label.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    if sectionKey == "fan" || text.contains("fan") {
        return "fanblades"
    }
    if text.contains("battery") {
        return "battery.100"
    }
    if text.contains("cpu") {
        return "cpu"
    }
    if text.contains("gpu") {
        return "square.stack.3d.down.right"
    }
    if text.contains("ane") {
        return "bolt.horizontal.circle"
    }
    if text.contains("thermal") || text.contains("temp") || text.contains("temperature") {
        return "thermometer"
    }
    if sectionKey == "network" || text.contains("wifi") || text.contains("wi-fi") || text.contains("rssi") {
        return "wifi"
    }
    if text.contains("ethernet") {
        return "network"
    }
    if sectionKey == "power" || text.contains("power") {
        return "bolt.fill"
    }
    return nil
}

private struct SectionTableView: View {
    let theme: Theme
    let key: String?
    @ObservedObject var model: DashboardViewModel
    let table: SnapshotTable

    var body: some View {
        /**
         Summary
         Render a scrollable table with dynamic columns and a capped visible height.

         Inputs
         None.

         Outputs
         A SwiftUI view for table rendering.

         Side effects
         None.

         Error handling
         None. Missing cells are rendered as empty strings.

         Ties to other methods
         Uses `DashboardViewModel.preferredTableVisibleRows` to size the table view.

         Why this exists
         Keeps tables readable and usable for long outputs without stretching the entire page.
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
                }
                ForEach(0..<table.headers.count, id: \.self) { _ in
                    Rectangle()
                        .fill(theme.colors.cardBorder.opacity(0.8))
                        .frame(height: 1)
                }

                ForEach(Array(table.rows.enumerated()), id: \.offset) { rowIndex, row in
                    ForEach(0..<max(1, table.headers.count), id: \.self) { colIndex in
                        let value = colIndex < row.count ? row[colIndex] : ""
                        Text(value)
                            .font(theme.fonts.mono)
                            .foregroundStyle(theme.colors.field)
                            .lineLimit(2)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, 2)
                            .background(rowIndex.isMultiple(of: 2) ? Color.clear : theme.colors.background.opacity(0.08))
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

private struct OverviewView: View {
    let theme: Theme
    @ObservedObject var model: DashboardViewModel
    @State private var expandedKeys: Set<String> = []

    var body: some View {
        /**
         Summary
         Render a single scroll view of all sections with tap-to-open cards.

         Inputs
         None.

         Outputs
         A SwiftUI view for the overview screen.

         Side effects
         Allows pull-to-refresh and updates the selection when cards are tapped.

         Error handling
         None. Displays placeholders while initial data is loading.

         Ties to other methods
         Uses `DashboardViewModel.sectionPayload`, `DashboardViewModel.sectionHealth`, and `DashboardViewModel.refreshOnce`.

         Why this exists
         Provides an at-a-glance dashboard similar to the original Tk layout while remaining native SwiftUI.
         */
        ScrollView {
            VStack(alignment: .leading, spacing: theme.layout.cardSpacing) {
                if model.snapshot == nil {
                    Card(theme: theme) {
                        HStack(spacing: 10) {
                            ProgressView()
                                .controlSize(.small)
                            Spacer()
                        }
                    }
                }

                let visible = model.visibleSections
                if visible.isEmpty {
                    Card(theme: theme) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("No sections enabled")
                                .font(theme.fonts.sectionTitle)
                                .foregroundStyle(theme.colors.section)
                            Text("Open Settings to enable sections again.")
                                .font(theme.fonts.body)
                                .foregroundStyle(theme.colors.field)
                        }
                    }
                }

                ForEach(visible) { section in
                    let health = model.sectionHealth(for: section.key)
                    let payload = model.sectionPayload(for: section.key)
                    let hasExpandableContent = _overviewHasExpandableContent(payload: payload)
                    let isExpanded = expandedKeys.contains(section.key)

                    Card(theme: theme) {
                        VStack(alignment: .leading, spacing: 10) {
                            HStack(alignment: .firstTextBaseline, spacing: 10) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(section.title)
                                        .font(theme.fonts.sectionTitle)
                                        .foregroundStyle(theme.colors.section)
                                    Text(section.subtitle)
                                        .font(theme.fonts.caption)
                                        .foregroundStyle(theme.colors.label)
                                }
                                Spacer()
                                if let first = payload?.metrics?.first {
                                    let points = model.historyPoints(sectionKey: section.key, metricLabel: first.label)
                                    if points.count >= 3 {
                                        SparklineView(theme: theme, points: points)
                                            .frame(width: 120)
                                    }
                                }
                                if hasExpandableContent {
                                    Button {
                                        if expandedKeys.contains(section.key) {
                                            expandedKeys.remove(section.key)
                                        } else {
                                            expandedKeys.insert(section.key)
                                        }
                                    } label: {
                                        Image(systemName: isExpanded ? "chevron.down" : "chevron.right")
                                            .foregroundStyle(theme.colors.label)
                                            .frame(width: 22, height: 22)
                                            .contentShape(Rectangle())
                                    }
                                    .buttonStyle(.plain)
                                }
                                SectionHealthBadge(theme: theme, health: health)
                            }
                            if isExpanded {
                                OverviewExpandedContent(
                                    theme: theme,
                                    model: model,
                                    sectionKey: section.key,
                                    payload: payload
                                )
                            } else {
                                Text(model.sectionSummaryText(for: section.key))
                                    .font(theme.fonts.body)
                                    .foregroundStyle(theme.colors.field)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .lineLimit(3)
                            }
                        }
                        .contentShape(Rectangle())
                        .onTapGesture {
                            model.selectedSectionKey = section.key
                        }
                    }
                }
            }
            .padding(theme.layout.pagePadding)
        }
        .background(theme.colors.background)
    }
}

private func _overviewHasExpandableContent(payload: SnapshotSection?) -> Bool {
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

private struct OverviewExpandedContent: View {
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
        VStack(alignment: .leading, spacing: 10) {
            if sectionKey == "performance", model.thermalPermissionRequired(sectionKey: "performance") {
                Button("Fix Temperature Sensors") {
                    model.openSettings(focus: .temperatureSensors)
                }
                .buttonStyle(.borderedProminent)
                .tint(theme.colors.section)
            }
            if let field = payload?.field {
                let trimmed = field.trimmingCharacters(in: .whitespacesAndNewlines)
                if !trimmed.isEmpty {
                    Text(trimmed)
                        .font(theme.fonts.body)
                        .foregroundStyle(theme.colors.field)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .lineLimit(8)
                        .textSelection(.enabled)
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

private struct OverviewTablePreview: View {
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
        VStack(alignment: .leading, spacing: 6) {
            if !headers.isEmpty {
                HStack(spacing: 10) {
                    ForEach(0..<maxCols, id: \.self) { idx in
                        Text(headers[idx])
                            .font(theme.fonts.caption)
                            .foregroundStyle(theme.colors.label)
                            .lineLimit(1)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(.bottom, 2)
            }
            ForEach(0..<min(maxRows, rows.count), id: \.self) { rowIndex in
                let row = rows[rowIndex]
                HStack(spacing: 10) {
                    ForEach(0..<maxCols, id: \.self) { colIndex in
                        let value = row.indices.contains(colIndex) ? row[colIndex] : ""
                        Text(value)
                            .font(theme.fonts.mono)
                            .foregroundStyle(theme.colors.field)
                            .lineLimit(1)
                            .frame(maxWidth: .infinity, alignment: .leading)
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
        .padding(10)
        .background(theme.colors.background.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}
