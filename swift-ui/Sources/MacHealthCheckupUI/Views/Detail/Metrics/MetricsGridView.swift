import SwiftUI
import MacHealthCheckupCore

struct MetricsGridView: View {
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
        VStack(spacing: theme.layout.verticalScaled(8)) {
            if sectionKey == "performance" {
                HStack {
                    Text("Sensor")
                        .font(theme.fonts.caption)
                        .foregroundStyle(theme.colors.label)
                    Spacer()
                    HStack(spacing: 4) {
                        Text("Value")
                            .font(theme.fonts.caption)
                            .foregroundStyle(theme.colors.label)
                        TemperatureUnitToggleLabel(theme: theme)
                    }
                }
                .padding(.bottom, theme.layout.verticalScaled(2))
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
                        .help(HelpText.metric(sectionKey: sectionKey, label: row.label))
                    Spacer()
                    TemperatureValueView(
                        theme: theme,
                        raw: row.value,
                        valueColor: _metricValueColor(theme: theme, health: health)
                    )
                        .help("\(HelpText.metric(sectionKey: sectionKey, label: row.label))\n\nCurrent value: \(row.value)")
                    if let sectionKey {
                        let points = model.historyPoints(sectionKey: sectionKey, metricLabel: row.label)
                        if points.count >= 3 {
                            SparklineView(theme: theme, points: points)
                                .frame(width: 120)
                        }
                    }
                    SectionHealthBadge(theme: theme, health: health)
                }
                .padding(.vertical, theme.layout.verticalScaled(1.5))
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
