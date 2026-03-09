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
