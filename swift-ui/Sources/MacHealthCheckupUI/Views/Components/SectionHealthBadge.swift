import SwiftUI

struct SectionHealthBadge: View {
    /**
     Summary
     Render a compact capsule badge for section health.

     Inputs
     theme: Theme values used for fonts and colors.
     health: Health state to render.

     Outputs
     A SwiftUI view.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Used by `SidebarView`, `DetailView`, and `OverviewView` to display consistent health badges.

     Why this exists
     Keeps badge styling consistent across screens.
     */

    let theme: Theme
    let health: SectionHealth

    var body: some View {
        /**
         Summary
         Render the badge view for the current health state.

         Inputs
         None.

         Outputs
         A SwiftUI view that displays a capsule badge.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used wherever a section health badge is required.

         Why this exists
         Keeps badge rendering logic centralized and style-consistent.
         */
        Text(health.labelText())
            .font(theme.fonts.caption)
            .foregroundStyle(health.color(theme: theme))
            .padding(.horizontal, 8)
            .padding(.vertical, theme.layout.verticalScaled(2))
            .background(health.color(theme: theme).opacity(0.12))
            .clipShape(Capsule())
    }
}
