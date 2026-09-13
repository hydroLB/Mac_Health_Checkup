import SwiftUI
import MacHealthCheckupCore

struct SectionDetailView: View {
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
                        VStack(alignment: .leading, spacing: theme.layout.verticalScaled(8)) {
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
                            .help(HelpText.section(key: descriptor.key))
                            Spacer()
                            if selectedKey != nil {
                                SectionHealthBadge(theme: theme, health: health)
                            }
                        }
                    }

                    if let payload {
                        if SectionDetailPolicy.shouldShowFieldSummaryCard(sectionKey: selectedKey, payload: payload) {
                            if let field = payload.field?.trimmingCharacters(in: .whitespacesAndNewlines), !field.isEmpty {
                                Card(theme: theme) {
                                    if selectedKey == "general" {
                                        GeneralInfoSummaryView(theme: theme, rawField: field)
                                            .help(HelpText.section(key: selectedKey))
                                    } else {
                                        Text(field)
                                            .font(theme.fonts.body)
                                            .foregroundStyle(theme.colors.field)
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                            .textSelection(.enabled)
                                            .help(HelpText.section(key: selectedKey))
                                    }
                                }
                            }
                        }
                    } else if model.isRefreshing || model.snapshot == nil {
                        Card(theme: theme) {
                            VStack(alignment: .leading, spacing: theme.layout.verticalScaled(8)) {
                                Text("Loading section data")
                                    .font(theme.fonts.sectionTitle)
                                    .foregroundStyle(theme.colors.section)
                                HStack(spacing: 10) {
                                    ProgressView()
                                        .controlSize(.small)
                                    Text(model.refreshStatusText ?? "Gathering the latest data for this section…")
                                        .font(theme.fonts.body)
                                        .foregroundStyle(theme.colors.field)
                                        .fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        }
                    } else {
                        Card(theme: theme) {
                            VStack(alignment: .leading, spacing: theme.layout.verticalScaled(8)) {
                                Text("No section data available")
                                    .font(theme.fonts.sectionTitle)
                                    .foregroundStyle(theme.colors.section)
                                Text("This section did not return any data. Refresh to try collecting it again.")
                                    .font(theme.fonts.body)
                                    .foregroundStyle(theme.colors.field)
                                    .fixedSize(horizontal: false, vertical: true)
                                Button("Try Again") {
                                    Task {
                                        await model.refreshOnce()
                                    }
                                }
                                .buttonStyle(.bordered)
                                .tint(theme.colors.section)
                                .disabled(model.isRefreshing)
                            }
                        }
                    }

                    if let metrics = payload?.metrics, !metrics.isEmpty {
                        Card(theme: theme) {
                            VStack(alignment: .leading, spacing: theme.layout.verticalScaled(8)) {
                                Text("Metrics")
                                    .font(theme.fonts.body)
                                    .foregroundStyle(theme.colors.label)
                                    .help("Key-value metrics for this section. Hover a label to see what it means.")
                                MetricsGridView(theme: theme, sectionKey: selectedKey, model: model, rows: metrics)
                            }
                        }
                    }

                    if let table = payload?.table {
                        Card(theme: theme) {
                            VStack(alignment: .leading, spacing: theme.layout.verticalScaled(8)) {
                                if let key = selectedKey,
                                   let title = SectionDetailPolicy.tableTitle(for: key),
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
        #if os(iOS)
        .refreshable {
            await model.refreshOnce()
        }
        #endif
        .background(theme.colors.background)
    }
}
