import SwiftUI

public struct SidebarView: View {
    /**
     Summary
     Render the sidebar navigation list of sections.

     Inputs
     theme: Theme values.
     model: Dashboard view model.

     Outputs
     A SwiftUI sidebar view.

     Side effects
     Updates the selected section key via binding.

     Error handling
     None.

     Ties to other methods
     Used by `RootView`.

     Why this exists
     Provides a native navigation pattern similar to iOS and macOS sidebar apps.
     */

    @ObservedObject public var model: DashboardViewModel

    public var body: some View {
        /**
         Summary
         Render the sidebar list with search and section health badges.

         Inputs
         None.

         Outputs
         A SwiftUI sidebar view.

         Side effects
         Updates selected section binding and search text binding.

         Error handling
         None.

         Ties to other methods
         Uses `DashboardViewModel.sidebarSections` and `DashboardViewModel.sectionHealth`.

         Why this exists
         Provides a native-feeling navigation model with clear section status at a glance.
         */
        List(selection: $model.selectedSectionKey) {
            ForEach(model.sidebarSections) { section in
                HStack(spacing: 10) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(section.title)
                            .font(model.theme.fonts.body)
                            .foregroundStyle(model.theme.colors.foreground)
                        Text(section.subtitle)
                            .font(model.theme.fonts.caption)
                            .foregroundStyle(model.theme.colors.label)
                    }
                    Spacer()
                    if section.key != DashboardViewModel.overviewKey {
                        SectionHealthBadge(theme: model.theme, health: model.sectionHealth(for: section.key))
                    }
                }
                .tag(section.key as String?)
                .padding(.vertical, 4)
            }
        }
        .listStyle(.sidebar)
        .scrollContentBackground(.hidden)
        .background(model.theme.colors.background)
        .navigationTitle(model.appTitle)
        #if os(macOS)
        .searchable(text: $model.sectionSearchText, placement: .sidebar)
        #else
        .searchable(text: $model.sectionSearchText)
        #endif
    }
}
