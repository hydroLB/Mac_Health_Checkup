import SwiftUI
import MacHealthCheckupCore

struct OverviewView: View {
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
                        VStack(alignment: .leading, spacing: theme.layout.verticalScaled(8)) {
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
                    let hasExpandableContent = OverviewContentPolicy.hasExpandableContent(payload: payload)
                    let isExpanded = expandedKeys.contains(section.key)

                    Card(theme: theme) {
                        VStack(alignment: .leading, spacing: theme.layout.verticalScaled(10)) {
                            HStack(alignment: .firstTextBaseline, spacing: 10) {
                                VStack(alignment: .leading, spacing: theme.layout.verticalScaled(2)) {
                                    Text(section.title)
                                        .font(theme.fonts.sectionTitle)
                                        .foregroundStyle(theme.colors.section)
                                    Text(section.subtitle)
                                        .font(theme.fonts.caption)
                                        .foregroundStyle(theme.colors.label)
                                }
                                .help(HelpText.section(key: section.key))
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
                                    .help(HelpText.section(key: section.key))
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
