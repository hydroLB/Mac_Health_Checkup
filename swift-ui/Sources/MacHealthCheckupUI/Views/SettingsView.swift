import SwiftUI

public struct SettingsView: View {
    /**
     Summary
     Render a settings screen that controls which sections are visible in the sidebar and overview.

     Inputs
     theme: Theme used for consistent typography and colors.
     model: Dashboard view model that owns section descriptors and visibility preferences.

     Outputs
     A SwiftUI view for settings.

     Side effects
     Updates persisted visibility preferences via `DashboardViewModel`.

     Error handling
     None. Invalid stored preferences are treated as empty.

     Ties to other methods
     Routed by `DetailView` when `DashboardViewModel.settingsKey` is selected.

     Why this exists
     Users want an idiot-proof way to hide sections without editing config files.
     */

    public let theme: Theme
    @ObservedObject public var model: DashboardViewModel
    @Environment(\.dismiss) private var dismiss

    public var body: some View {
        /**
         Summary
         Render the settings screen layout with a reset action and per-section toggles.

         Inputs
         None.

         Outputs
         A SwiftUI view.

         Side effects
         Changes persisted settings when toggles are switched.

         Error handling
         None.

         Ties to other methods
         Uses `DashboardViewModel.setSectionHidden` and `DashboardViewModel.resetSectionVisibility`.

        Why this exists
         Consolidates all UI customization in one predictable location.
         */
        ScrollView {
            VStack(alignment: .leading, spacing: theme.layout.cardSpacing) {
                Card(theme: theme) {
                    VStack(alignment: .leading, spacing: theme.layout.verticalScaled(10)) {
                        HStack(alignment: .firstTextBaseline, spacing: 10) {
                            Button {
                                dismiss()
                            } label: {
                                HStack(spacing: 6) {
                                    Text("Done")
                                }
                            }
                            .buttonStyle(.plain)
                            .foregroundStyle(theme.colors.label)

                            VStack(alignment: .leading, spacing: theme.layout.verticalScaled(4)) {
                                Text("Settings")
                                    .font(theme.fonts.sectionTitle)
                                    .foregroundStyle(theme.colors.section)
                                Text("Customize sections")
                                    .font(theme.fonts.caption)
                                    .foregroundStyle(theme.colors.label)
                            }
                            Spacer()
                            Button("Reset") {
                                model.resetSectionVisibility()
                            }
                            .buttonStyle(.bordered)
                            .tint(theme.colors.section)
                        }

                        Text("Toggle sections to show or hide them from the sidebar and the overview. Data collection still runs in the background. Sections with unreadable data stay hidden from the main UI until collection succeeds again.")
                            .font(theme.fonts.body)
                            .foregroundStyle(theme.colors.field)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }

                Card(theme: theme) {
                    VStack(alignment: .leading, spacing: 0) {
                        let toggleColumnWidth: CGFloat = 64
                        ForEach(Array(model.sections.enumerated()), id: \.element.key) { index, section in
                            HStack(spacing: 12) {
                                VStack(alignment: .leading, spacing: theme.layout.verticalScaled(2)) {
                                    Text(section.title)
                                        .font(theme.fonts.body)
                                        .foregroundStyle(theme.colors.field)
                                    Text(section.subtitle)
                                        .font(theme.fonts.caption)
                                        .foregroundStyle(theme.colors.label)
                                    if model.isSectionAutomaticallyHidden(key: section.key) {
                                        Text("Hidden from the main UI because the current data could not be read.")
                                            .font(theme.fonts.caption)
                                            .foregroundStyle(theme.colors.warn)
                                            .fixedSize(horizontal: false, vertical: true)
                                    }
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)

                                Toggle(
                                    "",
                                    isOn: Binding(
                                        get: { !model.hiddenSectionKeys.contains(section.key) },
                                        set: { newValue in
                                            model.setSectionHidden(!newValue, key: section.key)
                                        }
                                    )
                                )
                                .labelsHidden()
                                .toggleStyle(.switch)
                                .tint(theme.colors.section)
                                .frame(width: toggleColumnWidth, alignment: .trailing)
                                .accessibilityLabel("\(section.title) visibility")
                            }
                            .padding(.vertical, theme.layout.verticalScaled(7))

                            if index < model.sections.count - 1 {
                                Divider().opacity(0.6)
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
