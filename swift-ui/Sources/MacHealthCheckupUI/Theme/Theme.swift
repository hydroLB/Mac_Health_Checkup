import SwiftUI
import MacHealthCheckupCore

#if canImport(AppKit)
import AppKit
typealias PlatformColor = NSColor
#elseif canImport(UIKit)
import UIKit
typealias PlatformColor = UIColor
#endif

public struct Theme: Sendable {
    /**
     Summary
     Provide a consistent theme for the SwiftUI dashboard driven by config.

     Inputs
     config: Validated `AppConfig`.

     Outputs
     Theme values for colors and typography.

     Side effects
     None.

     Error handling
     Throws `AppError` when theme construction fails.

     Ties to other methods
     Built by `AppBootstrap.load` and injected into views via environment.

     Why this exists
     Ensures consistent styling across the entire UI without hard-coded values.
     */

    public let colors: ThemeColors
    public let fonts: ThemeFonts
    public let layout: LayoutMetrics

    public init(config: AppConfig) throws {
        self.colors = try ThemeColors(from: config)
        self.fonts = ThemeFonts(from: config)
        self.layout = LayoutMetrics(from: config)
    }

    public init(snapshot: Snapshot) throws {
        /**
         Summary
         Build a Theme from a validated snapshot payload.

         Inputs
         snapshot: Validated snapshot containing `theme` fields.

         Outputs
         Theme values for colors, typography, and spacing.

         Side effects
         None.

         Error handling
         Throws `AppError` when theme construction fails.

         Ties to other methods
         Used by native clients that do not have access to local config files, such as an iOS app.

         Why this exists
         Keeps the UI style consistent with the agent by using the same config-derived theme on every platform.
         */
        self.colors = try ThemeColors(from: snapshot.theme)
        self.fonts = ThemeFonts(from: snapshot.theme)
        self.layout = LayoutMetrics(from: snapshot.theme)
    }

    init(colors: ThemeColors, fonts: ThemeFonts, layout: LayoutMetrics) {
        /**
         Summary
         Initialize a Theme with explicit components.

         Inputs
         colors: ThemeColors value.
         fonts: ThemeFonts value.
         layout: LayoutMetrics value.

         Outputs
         A Theme instance.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `Theme.fallback(appTitle:)`.

         Why this exists
         Allows constructing an intentional fallback theme without requiring config or snapshot decoding.
         */
        self.colors = colors
        self.fonts = fonts
        self.layout = layout
    }

    public static func fallback(appTitle: String) -> Theme {
        /**
         Summary
         Provide a conservative fallback theme for cases where no snapshot or config is available yet.

         Inputs
         appTitle: Application title for consistency across early loading states.

         Outputs
         A Theme instance with safe defaults.

         Side effects
         None.

         Error handling
         Falls back to system colors if hex parsing fails.

         Ties to other methods
         Used by the iOS client before the first successful snapshot fetch populates the theme.

         Why this exists
         A proper iOS client needs to render a polished pairing and loading UI before it can fetch the agent theme.
         */
        _ = appTitle
        let colors = ThemeColors(
            background: Color(red: 0.043, green: 0.051, blue: 0.063),
            foreground: Color.white,
            section: Color(red: 0.039, green: 0.518, blue: 1.0),
            label: Color(red: 0.667, green: 0.698, blue: 0.749),
            field: Color(red: 0.898, green: 0.898, blue: 0.906),
            ok: Color(red: 0.204, green: 0.780, blue: 0.349),
            warn: Color(red: 1.0, green: 0.800, blue: 0.0),
            bad: Color(red: 1.0, green: 0.231, blue: 0.188),
            cardBackground: Color(red: 0.078, green: 0.094, blue: 0.129),
            cardBorder: Color(red: 0.145, green: 0.173, blue: 0.227)
        )
        let fonts = ThemeFonts(
            title: .system(size: 18, weight: .semibold),
            sectionTitle: .system(size: 16, weight: .semibold),
            body: .system(size: 13),
            mono: .system(.body, design: .monospaced),
            caption: .system(size: 11)
        )
        let layout = LayoutMetrics(pagePadding: 14, cardPadding: 12, cardSpacing: 12)
        return Theme(colors: colors, fonts: fonts, layout: layout)
    }
}

public struct LayoutMetrics: Sendable {
    public let pagePadding: CGFloat
    public let cardPadding: CGFloat
    public let cardSpacing: CGFloat

    public init(from config: AppConfig) {
        /**
         Summary
         Build layout metrics from config values with conservative minimums.

         Inputs
         config: Validated `AppConfig`.

         Outputs
         Layout metric values for consistent spacing.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `Theme.init` and consumed by SwiftUI views.

         Why this exists
         Keeps spacing tunable from config while enforcing a readable baseline for a native-feeling UI.
         */
        let padx = max(12, config.gui.section_padx)
        let pady = max(10, config.gui.section_pady)
        self.pagePadding = CGFloat(padx)
        self.cardPadding = 12
        self.cardSpacing = CGFloat(pady)
    }

    public init(from theme: SnapshotTheme) {
        /**
         Summary
         Build layout metrics from snapshot theme values.

         Inputs
         theme: Snapshot theme payload.

         Outputs
         Layout metric values for consistent spacing.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `Theme.init(snapshot:)`.

         Why this exists
         Ensures spacing remains consistent across platforms without duplicating a config file on iOS.
         */
        let padx = max(12, theme.gui.section_padx)
        let pady = max(10, theme.gui.section_pady)
        self.pagePadding = CGFloat(padx)
        self.cardPadding = 12
        self.cardSpacing = CGFloat(pady)
    }

    init(pagePadding: CGFloat, cardPadding: CGFloat, cardSpacing: CGFloat) {
        /**
         Summary
         Initialize layout metrics with explicit values.

         Inputs
         pagePadding: Outer page padding.
         cardPadding: Inner card padding.
         cardSpacing: Vertical spacing between cards.

         Outputs
         A LayoutMetrics value.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `Theme.fallback(appTitle:)` when config or snapshot theme cannot be parsed.

         Why this exists
         Keeps fallback theme construction readable without reusing config-only types.
         */
        self.pagePadding = pagePadding
        self.cardPadding = cardPadding
        self.cardSpacing = cardSpacing
    }
}

public struct ThemeColors: Sendable {
    public let background: Color
    public let foreground: Color
    public let section: Color
    public let label: Color
    public let field: Color
    public let ok: Color
    public let warn: Color
    public let bad: Color
    public let cardBackground: Color
    public let cardBorder: Color

    init(
        background: Color,
        foreground: Color,
        section: Color,
        label: Color,
        field: Color,
        ok: Color,
        warn: Color,
        bad: Color,
        cardBackground: Color,
        cardBorder: Color
    ) {
        /**
         Summary
         Initialize theme colors with explicit SwiftUI Color values.

         Inputs
         background: Background color.
         foreground: Primary foreground color.
         section: Section title color.
         label: Secondary label color.
         field: Primary body field color.
         ok: OK status color.
         warn: Warning status color.
         bad: Error status color.
         cardBackground: Card background color.
         cardBorder: Card border color.

         Outputs
         A ThemeColors value.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `Theme.fallback(appTitle:)` when hex parsing cannot be used.

         Why this exists
         Enables a safe fallback UI that still looks intentional when theme decoding fails.
         */
        self.background = background
        self.foreground = foreground
        self.section = section
        self.label = label
        self.field = field
        self.ok = ok
        self.warn = warn
        self.bad = bad
        self.cardBackground = cardBackground
        self.cardBorder = cardBorder
    }

    public init(from config: AppConfig) throws {
        /**
         Summary
         Build theme colors from validated config values.

         Inputs
         config: Validated `AppConfig`.

         Outputs
         Theme colors.

         Side effects
         None.

         Error handling
         Throws `AppError` if color parsing fails.

         Ties to other methods
         Used by `Theme.init`.

         Why this exists
         Keeps the UI’s look and feel controlled by `config/config.json`.
         */
        background = try Color(hex: config.colors.bg)
        foreground = try Color(hex: config.colors.fg)
        section = try Color(hex: config.colors.section)
        label = try Color(hex: config.colors.label)
        field = try Color(hex: config.colors.field)
        ok = try Color(hex: config.colors.ok)
        warn = try Color(hex: config.colors.warn)
        bad = try Color(hex: config.colors.bad)
        cardBackground = try Color(hex: config.gui.card_bg)
        cardBorder = try Color(hex: config.gui.card_border)
    }

    public init(from theme: SnapshotTheme) throws {
        /**
         Summary
         Build theme colors from a snapshot theme payload.

         Inputs
         theme: Snapshot theme payload.

         Outputs
         Theme colors.

         Side effects
         None.

         Error handling
         Throws `AppError` if color parsing fails.

         Ties to other methods
         Used by `Theme.init(snapshot:)`.

         Why this exists
         Allows native clients to match the agent’s theme exactly without local config duplication.
         */
        background = try Color(hex: theme.colors.bg)
        foreground = try Color(hex: theme.colors.fg)
        section = try Color(hex: theme.colors.section)
        label = try Color(hex: theme.colors.label)
        field = try Color(hex: theme.colors.field)
        ok = try Color(hex: theme.colors.ok)
        warn = try Color(hex: theme.colors.warn)
        bad = try Color(hex: theme.colors.bad)
        cardBackground = try Color(hex: theme.gui.card_bg)
        cardBorder = try Color(hex: theme.gui.card_border)
    }
}

public struct ThemeFonts: Sendable {
    public let title: Font
    public let sectionTitle: Font
    public let body: Font
    public let mono: Font
    public let caption: Font

    init(title: Font, sectionTitle: Font, body: Font, mono: Font, caption: Font) {
        /**
         Summary
         Initialize theme fonts with explicit SwiftUI Font values.

         Inputs
         title: Large title font.
         sectionTitle: Section title font.
         body: Body font.
         mono: Monospaced font.
         caption: Caption font.

         Outputs
         A ThemeFonts value.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `Theme.fallback(appTitle:)` when custom fonts are unavailable.

         Why this exists
         Keeps fallback theme creation explicit and avoids dependence on config-only font settings.
         */
        self.title = title
        self.sectionTitle = sectionTitle
        self.body = body
        self.mono = mono
        self.caption = caption
    }

    public init(from config: AppConfig) {
        /**
         Summary
         Build theme fonts from config values with safe fallbacks.

         Inputs
         config: Validated `AppConfig`.

         Outputs
         Theme fonts.

         Side effects
         None.

         Error handling
         None. Falls back to system fonts if custom fonts are not available.

         Ties to other methods
         Used by `Theme.init`.

         Why this exists
         Ensures typography remains consistent across the UI while tolerating missing font families.
         */
        title = Font.custom(config.fonts.family_default, size: CGFloat(config.fonts.size_banner))
        sectionTitle = Font.custom(config.fonts.family_default, size: CGFloat(config.fonts.size_section)).weight(.semibold)
        body = Font.custom(config.fonts.family_default, size: CGFloat(config.fonts.size_field))
        mono = Font.custom(config.fonts.family_mono, size: CGFloat(config.fonts.size_field))
        caption = Font.custom(config.fonts.family_default, size: CGFloat(config.fonts.size_tooltip))
    }

    public init(from theme: SnapshotTheme) {
        /**
         Summary
         Build theme fonts from snapshot theme values with safe fallbacks.

         Inputs
         theme: Snapshot theme payload.

         Outputs
         Theme fonts.

         Side effects
         None.

         Error handling
         None. Falls back to system fonts if custom fonts are not available.

         Ties to other methods
         Used by `Theme.init(snapshot:)`.

         Why this exists
         Allows a native iOS client to match typography with the agent configuration.
         */
        title = Font.custom(theme.fonts.family_default, size: CGFloat(theme.fonts.size_banner))
        sectionTitle = Font.custom(theme.fonts.family_default, size: CGFloat(theme.fonts.size_section)).weight(.semibold)
        body = Font.custom(theme.fonts.family_default, size: CGFloat(theme.fonts.size_field))
        mono = Font.custom(theme.fonts.family_mono, size: CGFloat(theme.fonts.size_field))
        caption = Font.custom(theme.fonts.family_default, size: CGFloat(theme.fonts.size_tooltip))
    }
}

extension Color {
    init(hex: String) throws {
        /**
         Summary
         Convert a `#RRGGBB` string into a SwiftUI `Color`.

         Inputs
         hex: Hex string in `#RRGGBB` form.

         Outputs
         A SwiftUI color.

         Side effects
         None.

         Error handling
         Throws `AppError` when the string is not valid.

         Ties to other methods
         Used by `ThemeColors`.

         Why this exists
         SwiftUI does not natively parse hex color strings.
         */
        guard HexColor.isValidHex(hex) else {
            throw AppError.context(#fileID, #function, "Invalid hex color: \(hex)")
        }
        let r = CGFloat(Int(hex.dropFirst(1).prefix(2), radix: 16) ?? 0) / 255.0
        let g = CGFloat(Int(hex.dropFirst(3).prefix(2), radix: 16) ?? 0) / 255.0
        let b = CGFloat(Int(hex.dropFirst(5).prefix(2), radix: 16) ?? 0) / 255.0
#if canImport(AppKit)
        self = Color(nsColor: PlatformColor(red: r, green: g, blue: b, alpha: 1.0))
#elseif canImport(UIKit)
        self = Color(uiColor: PlatformColor(red: r, green: g, blue: b, alpha: 1.0))
#else
        self = Color(red: Double(r), green: Double(g), blue: Double(b))
#endif
    }
}
