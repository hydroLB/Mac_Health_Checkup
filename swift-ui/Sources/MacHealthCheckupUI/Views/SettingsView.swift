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
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: theme.layout.cardSpacing) {
                Card(theme: theme) {
                    VStack(alignment: .leading, spacing: 10) {
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

                            VStack(alignment: .leading, spacing: 4) {
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

                        Text("Toggle sections to show or hide them from the sidebar and the overview. Data collection still runs in the background.")
                            .font(theme.fonts.body)
                            .foregroundStyle(theme.colors.field)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }

                #if os(macOS)
                Card(theme: theme) {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Temperature Sensors")
                            .font(theme.fonts.body)
                            .foregroundStyle(theme.colors.label)
                        Text("macOS restricts low-level sensor access. Mac Fan Control works because it uses a privileged helper. This app uses the standard macOS authorization prompt to run a one-time sensor probe.")
                            .font(theme.fonts.body)
                            .foregroundStyle(theme.colors.field)
                            .fixedSize(horizontal: false, vertical: true)

                        HStack(spacing: 10) {
                            Button("Request Access Now") {
                                Task { await model.requestTemperatureSensorAccess() }
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(theme.colors.section)
                            .disabled(model.isTemperatureAccessInFlight)

                            if model.isTemperatureAccessInFlight {
                                ProgressView()
                                    .progressViewStyle(.circular)
                            }
                            Spacer()
                        }

                        if let status = model.temperatureAccessStatus, !status.isEmpty {
                            Text(status)
                                .font(theme.fonts.caption)
                                .foregroundStyle(theme.colors.label)
                                .fixedSize(horizontal: false, vertical: true)
                        }

                        Text("Tip: The prompt asks for your Mac login password (not Apple ID). If it keeps failing, open Error Details to see the exact osascript/tool output.")
                            .font(theme.fonts.caption)
                            .foregroundStyle(theme.colors.label)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .id(SettingsFocus.temperatureSensors.scrollAnchorID)
                #endif

                Card(theme: theme) {
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(Array(model.sections.enumerated()), id: \.element.key) { index, section in
                            Toggle(isOn: Binding(
                                get: { !model.hiddenSectionKeys.contains(section.key) },
                                set: { newValue in
                                    model.setSectionHidden(!newValue, key: section.key)
                                }
                            )) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(section.title)
                                        .font(theme.fonts.body)
                                        .foregroundStyle(theme.colors.field)
                                    Text(section.subtitle)
                                        .font(theme.fonts.caption)
                                        .foregroundStyle(theme.colors.label)
                                }
                            }
                            .toggleStyle(.switch)
                            .tint(theme.colors.section)
                            .padding(.vertical, 7)

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
            .onAppear {
                _scrollToFocusIfNeeded(proxy: proxy)
            }
            .onChange(of: model.settingsFocus) { _ in
                _scrollToFocusIfNeeded(proxy: proxy)
            }
        }
    }

    private func _scrollToFocusIfNeeded(proxy: ScrollViewProxy) {
        /**
         Summary
         Scroll the settings sheet to a requested focus target when present.

         Inputs
         proxy: Scroll view proxy used to perform scrolling.

         Outputs
         None.

         Side effects
         Scrolls the settings view and clears the focus target once applied.

         Error handling
         None.

         Ties to other methods
         Uses `DashboardViewModel.settingsFocus` which is set by `DashboardViewModel.openSettings`.

         Why this exists
         Makes "fix it" flows idiot-proof by taking users directly to the relevant settings card.
         */
        guard let focus = model.settingsFocus else { return }
        DispatchQueue.main.async {
            withAnimation(.easeInOut(duration: 0.25)) {
                proxy.scrollTo(focus.scrollAnchorID, anchor: .top)
            }
            model.clearSettingsFocus()
        }
    }
}
