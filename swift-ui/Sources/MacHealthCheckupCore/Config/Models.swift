import Foundation

public struct AppConfig: Codable, Sendable {
    /**
     Summary
     Mirror the subset of `config/config.json` used by the SwiftUI frontend.

     Inputs
     colors: Theme colors.
     fonts: Font configuration.
     ui: Window title and sizing.
     gui: GUI layout and refresh knobs.
     timeouts: Timeout knobs used by backend execution.

     Outputs
     Decoded configuration value.

     Side effects
     None.

     Error handling
     Validation errors are thrown by `validated()`.

     Ties to other methods
     Created by `ConfigLoader.load` and used to build a `Theme` and backend runtime settings.

     Why this exists
     Keeps frontend behavior driven by the same central config as the Python app.
     */

    public let colors: ColorsConfig
    public let fonts: FontsConfig
    public let ui: UiConfig
    public let gui: GuiConfig
    public let timeouts: TimeoutConfig

    public func validated() throws -> AppConfig {
        /**
         Summary
         Validate decoded config values and normalize derived structures.

         Inputs
         None.

         Outputs
         The same `AppConfig` when validation succeeds.

         Side effects
         None.

         Error handling
         Throws `AppError` when required values are invalid.

         Ties to other methods
         Called by `ConfigLoader.load` before the UI is shown.

         Why this exists
         Failing fast with actionable messages prevents subtle UI and backend bugs.
         */
        _ = try colors.validated()
        _ = try fonts.validated()
        _ = try ui.validated()
        _ = try gui.validated()
        _ = try timeouts.validated()
        return self
    }
}

public struct ColorsConfig: Codable, Sendable {
    public let bg: String
    public let fg: String
    public let ok: String
    public let warn: String
    public let bad: String
    public let section: String
    public let label: String
    public let field: String

    public func validated() throws -> ColorsConfig {
        /**
         Summary
         Validate hex color strings required by the theme.

         Inputs
         None.

         Outputs
         The same `ColorsConfig` when validation succeeds.

         Side effects
         None.

         Error handling
         Throws `AppError` when a color value is not a valid hex color.

         Ties to other methods
         Used by `Theme.init` to create SwiftUI colors.

         Why this exists
         Avoids runtime crashes from invalid color strings.
         */
        let values = [bg, fg, ok, warn, bad, section, label, field]
        for value in values {
            guard HexColor.isValidHex(value) else {
                throw AppError.context(#fileID, #function, "Invalid hex color: \(value)")
            }
        }
        return self
    }
}

public struct FontsConfig: Codable, Sendable {
    public let family_default: String
    public let family_mono: String
    public let size_section: Int
    public let size_banner: Int
    public let size_field: Int
    public let size_tooltip: Int
    public let weight_bold: String
    public let weight_normal: String

    public func validated() throws -> FontsConfig {
        /**
         Summary
         Validate font sizing constraints used by the UI.

         Inputs
         None.

         Outputs
         The same `FontsConfig` when validation succeeds.

         Side effects
         None.

         Error handling
         Throws `AppError` when sizes are out of acceptable bounds.

         Ties to other methods
         Used by `Theme` to build consistent typography.

         Why this exists
         Prevents unreadable UI caused by negative or extreme font sizes.
         */
        for (name, value) in [
            ("size_section", size_section),
            ("size_banner", size_banner),
            ("size_field", size_field),
            ("size_tooltip", size_tooltip),
        ] {
            if value < 8 || value > 48 {
                throw AppError.context(#fileID, #function, "Invalid font size \(name)=\(value)")
            }
        }
        return self
    }
}

public struct UiConfig: Codable, Sendable {
    public let window_size: String
    public let window_title: String

    public func validated() throws -> UiConfig {
        /**
         Summary
         Validate UI window config.

         Inputs
         None.

         Outputs
         The same `UiConfig` when validation succeeds.

         Side effects
         None.

         Error handling
         Throws `AppError` when window title is empty.

         Ties to other methods
         Used by `AppBootstrap.load` and the SwiftUI window title.

         Why this exists
         Ensures the app has a consistent title and avoids blank headers.
         */
        if window_title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            throw AppError.context(#fileID, #function, "ui.window_title must be non-empty")
        }
        return self
    }
}

public struct GuiConfig: Codable, Sendable {
    public let section_rows: [[String]]
    public let scrollable_rows: [String: Int]
    public let card_bg: String
    public let card_border: String
    public let section_padx: Int
    public let section_pady: Int
    public let auto_refresh_ms: Int
    public let fans_refresh_ms: Int?
    public let history_enabled: Bool?
    public let history_retention_minutes: Int?
    public let history_max_points_per_series: Int?
    public let history_save_interval_sec: Int?

    public func validated() throws -> GuiConfig {
        /**
         Summary
         Validate GUI layout values used by the SwiftUI frontend.

         Inputs
         None.

         Outputs
         The same `GuiConfig` when validation succeeds.

         Side effects
         None.

         Error handling
         Throws `AppError` when rows are malformed or color strings are invalid.

         Ties to other methods
         Used by `SectionCatalog.fromConfig` and `Theme.init`.

         Why this exists
         Keeps the SwiftUI frontend strict and aligned with the central config registry.
         */
        guard HexColor.isValidHex(card_bg) else {
            throw AppError.context(#fileID, #function, "Invalid gui.card_bg hex color: \(card_bg)")
        }
        guard HexColor.isValidHex(card_border) else {
            throw AppError.context(#fileID, #function, "Invalid gui.card_border hex color: \(card_border)")
        }
        if auto_refresh_ms < 250 || auto_refresh_ms > 60_000 {
            throw AppError.context(#fileID, #function, "gui.auto_refresh_ms out of range: \(auto_refresh_ms)")
        }
        if let fanRefresh = fans_refresh_ms {
            if fanRefresh < 250 || fanRefresh > 60_000 {
                throw AppError.context(#fileID, #function, "gui.fans_refresh_ms out of range: \(fanRefresh)")
            }
        }
        if section_padx < 0 || section_padx > 64 {
            throw AppError.context(#fileID, #function, "gui.section_padx out of range: \(section_padx)")
        }
        if section_pady < 0 || section_pady > 64 {
            throw AppError.context(#fileID, #function, "gui.section_pady out of range: \(section_pady)")
        }
        for row in section_rows {
            if row.count != 3 {
                throw AppError.context(#fileID, #function, "gui.section_rows must contain 3-item rows")
            }
        }
        for (key, value) in scrollable_rows {
            if key.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || value < 1 || value > 200 {
                throw AppError.context(#fileID, #function, "Invalid gui.scrollable_rows entry for \(key)")
            }
        }
        if let minutes = history_retention_minutes {
            if minutes < 1 || minutes > 24 * 60 {
                throw AppError.context(#fileID, #function, "gui.history_retention_minutes out of range: \(minutes)")
            }
        }
        if let maxPoints = history_max_points_per_series {
            if maxPoints < 10 || maxPoints > 200_000 {
                throw AppError.context(#fileID, #function, "gui.history_max_points_per_series out of range: \(maxPoints)")
            }
        }
        if let interval = history_save_interval_sec {
            if interval < 1 || interval > 300 {
                throw AppError.context(#fileID, #function, "gui.history_save_interval_sec out of range: \(interval)")
            }
        }
        return self
    }
}

public struct TimeoutConfig: Codable, Sendable {
    public let default_cmd_timeout: Int
    public let snapshot_backend_timeout_sec: Int?

    public var resolvedSnapshotBackendTimeoutSeconds: Int {
        /**
         Summary
         Provide the effective backend snapshot process timeout.

         Inputs
         None.

         Outputs
         Timeout in seconds as an Int.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `BackendRuntimeConfig.from` to cap `python -m mac_health_checkup --snapshot-json`.

         Why this exists
         The backend snapshot aggregates multiple commands and often exceeds `default_cmd_timeout`; this keeps UI timeouts safe.
         */
        return snapshot_backend_timeout_sec ?? max(30, default_cmd_timeout * 6)
    }

    public func validated() throws -> TimeoutConfig {
        /**
         Summary
         Validate timeout knobs used by backend execution.

         Inputs
         None.

         Outputs
         The same `TimeoutConfig` when validation succeeds.

         Side effects
         None.

         Error handling
         Throws `AppError` when timeouts are invalid.

         Ties to other methods
         Used by `BackendRuntimeConfig.from` to cap backend snapshot execution time.

         Why this exists
         Prevents a hung backend process from freezing the UI refresh loop.
         */
        if default_cmd_timeout < 1 || default_cmd_timeout > 120 {
            throw AppError.context(#fileID, #function, "timeouts.default_cmd_timeout out of range: \(default_cmd_timeout)")
        }
        if let snapshot = snapshot_backend_timeout_sec {
            if snapshot < 5 || snapshot > 600 {
                throw AppError.context(
                    #fileID,
                    #function,
                    "timeouts.snapshot_backend_timeout_sec out of range: \(snapshot)"
                )
            }
        }
        return self
    }
}
