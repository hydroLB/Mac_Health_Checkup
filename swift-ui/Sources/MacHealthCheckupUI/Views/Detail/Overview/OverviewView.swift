import SwiftUI
import MacHealthCheckupCore

struct OverviewView: View {
    let theme: Theme
    @ObservedObject var model: DashboardViewModel
    @State private var expandedKeys: Set<String> = []

    var body: some View {
        /**
         Summary
         Render a single scroll view of health alerts with tap-to-open cards.

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
        GeometryReader { geometry in
            ScrollView {
                VStack(alignment: .leading, spacing: theme.layout.cardSpacing) {
                if model.snapshot == nil {
                    Card(theme: theme) {
                        VStack(alignment: .leading, spacing: theme.layout.verticalScaled(8)) {
                            Text("Loading health data")
                                .font(theme.fonts.sectionTitle)
                                .foregroundStyle(theme.colors.section)
                            HStack(spacing: 10) {
                                if model.isRefreshing {
                                    ProgressView()
                                        .controlSize(.small)
                                }
                                Text(model.refreshStatusText ?? "Waiting for the first health snapshot from this Mac.")
                                    .font(theme.fonts.body)
                                    .foregroundStyle(theme.colors.field)
                                    .fixedSize(horizontal: false, vertical: true)
                                Spacer()
                            }
                            if !model.isRefreshing {
                                Button("Try Again") {
                                    Task {
                                        await model.refreshOnce()
                                    }
                                }
                                .buttonStyle(.bordered)
                                .tint(theme.colors.section)
                            }
                        }
                    }
                }

                let visible = model.visibleSections.filter { OverviewGridPolicy.isAlert(for: model.sectionHealth(for: $0.key)) }
                if model.snapshot != nil && visible.isEmpty {
                    Card(theme: theme) {
                        VStack(alignment: .leading, spacing: theme.layout.verticalScaled(8)) {
                            Text("No warnings or critical alerts")
                                .font(theme.fonts.sectionTitle)
                                .foregroundStyle(theme.colors.section)
                            Text("No alerts in the visible sections. Choose a section in the sidebar for all readings, or review visibility settings.")
                                .font(theme.fonts.body)
                                .foregroundStyle(theme.colors.field)
                                .fixedSize(horizontal: false, vertical: true)
                            HStack(spacing: 10) {
                                Button("Open Section Settings") {
                                    model.openSettings()
                                }
                                .buttonStyle(.borderedProminent)
                                .tint(theme.colors.section)

                                Button("Refresh") {
                                    Task {
                                        await model.refreshOnce()
                                    }
                                }
                                .buttonStyle(.bordered)
                                .disabled(model.isRefreshing)
                            }
                        }
                    }
                }

                let ordered = visible.enumerated().sorted { lhs, rhs in
                    let lhsPriority = OverviewGridPolicy.priority(for: model.sectionHealth(for: lhs.element.key))
                    let rhsPriority = OverviewGridPolicy.priority(for: model.sectionHealth(for: rhs.element.key))
                    if lhsPriority == rhsPriority { return lhs.offset < rhs.offset }
                    return lhsPriority < rhsPriority
                }.map(\.element)
                let contentWidth = max(0, geometry.size.width - (theme.layout.pagePadding * 2))
                let columnCount = OverviewGridPolicy.columnCount(
                    for: contentWidth,
                    spacing: theme.layout.cardSpacing
                )
                let columns = Array(
                    repeating: GridItem(
                        .flexible(minimum: 0, maximum: .infinity),
                        spacing: theme.layout.cardSpacing,
                        alignment: .top
                    ),
                    count: columnCount
                )

                LazyVGrid(columns: columns, alignment: .leading, spacing: theme.layout.cardSpacing) {
                    ForEach(ordered) { section in
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
                                if let first = OverviewContentPolicy.alertMetrics(payload: payload).first {
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
                                Text(OverviewContentPolicy.summary(payload: payload, fallback: model.sectionSummaryText(for: section.key)))
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
                    .overlay {
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(health.color(theme: theme).opacity(0.4), lineWidth: 1)
                            .allowsHitTesting(false)
                    }
                    }
                }
            }
            .padding(theme.layout.pagePadding)
            }
        }
        #if os(iOS)
        .refreshable {
            await model.refreshOnce()
        }
        #endif
        .background(theme.colors.background)
    }
}
