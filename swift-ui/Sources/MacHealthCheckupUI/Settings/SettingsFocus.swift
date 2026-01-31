import Foundation

public enum SettingsFocus: String, Sendable, Equatable {
    /**
     Summary
     Define focus targets inside the Settings sheet for deep-linking from sections.

     Inputs
     None.

     Outputs
     Enum cases used by `DashboardViewModel` and `SettingsView`.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Consumed by `DashboardViewModel.openSettings` and `SettingsView` scrolling behavior.

     Why this exists
     Users should not have to hunt for the correct configuration card when a section detects a fixable permission issue.
     */

    case temperatureSensors

    public var scrollAnchorID: String {
        /**
         Summary
         Provide a stable anchor ID used by `ScrollViewReader` for the focus target.

         Inputs
         None.

         Outputs
         Stable string anchor ID.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `SettingsView` to call `scrollTo`.

         Why this exists
         Keeps scroll targeting stable even if view layout changes.
         */
        switch self {
        case .temperatureSensors:
            return "settings.temperatureSensors"
        }
    }
}

