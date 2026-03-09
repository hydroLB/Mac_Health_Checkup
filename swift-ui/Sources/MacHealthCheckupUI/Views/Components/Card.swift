import SwiftUI

public struct Card<Content: View>: View {
    /**
     Summary
     Render a consistent card container used across the dashboard.

     Inputs
     theme: Theme for consistent colors and spacing.
     content: Content builder for the card body.

     Outputs
     A SwiftUI view that wraps provided content with card styling.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Used by `DetailView`, `OverviewView`, and `SettingsView`.

     Why this exists
     Centralizes card presentation so spacing and borders remain uniform across all screens.
     */

    public let theme: Theme
    @ViewBuilder public let content: () -> Content

    public init(theme: Theme, @ViewBuilder content: @escaping () -> Content) {
        /**
         Summary
         Initialize a card wrapper.

         Inputs
         theme: Theme used for styling.
         content: Content builder for the card body.

         Outputs
         A Card instance.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used wherever the UI wants a consistent card shell.

         Why this exists
         Makes card usage ergonomic while keeping styling centralized.
         */
        self.theme = theme
        self.content = content
    }

    public var body: some View {
        /**
         Summary
         Render the card styled container.

         Inputs
         None.

         Outputs
         A SwiftUI view.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by callers embedding content in cards.

         Why this exists
         Ensures all cards share the same padding, border, and background.
         */
        content()
            .padding(.horizontal, theme.layout.cardPadding)
            .padding(.vertical, theme.layout.cardVerticalPadding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(theme.colors.cardBackground)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(theme.colors.cardBorder, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
