import SwiftUI
import MacHealthCheckupCore

public enum SectionHealth: String, Sendable {
    case ok
    case warn
    case bad
    case unknown

    public func labelText() -> String {
        /**
         Summary
         Return a short, user-facing label for the health state.

         Inputs
         None.

         Outputs
         Uppercase label string.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by badge views in the sidebar, overview, and detail screens.

         Why this exists
         Keeps health labeling consistent across the UI.
         */
        switch self {
        case .unknown:
            return "UNK"
        default:
            return rawValue.uppercased()
        }
    }

    public func color(theme: Theme) -> Color {
        /**
         Summary
         Map a health state to a theme color.

         Inputs
         theme: Theme for color mapping.

         Outputs
         A SwiftUI color.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `SectionHealthBadge` to render consistent status colors.

         Why this exists
         Ensures status colors are theme-driven and not hard-coded.
         */
        switch self {
        case .ok:
            return theme.colors.ok
        case .warn:
            return theme.colors.warn
        case .bad:
            return theme.colors.bad
        case .unknown:
            return theme.colors.field
        }
    }

    public static func fromStatusString(_ status: String) -> SectionHealth {
        /**
         Summary
         Normalize a free-form status string into a `SectionHealth`.

         Inputs
         status: Status string such as "ok", "warn", or "bad".

         Outputs
         Mapped `SectionHealth` value.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used when deriving health from metrics statuses.

         Why this exists
         Keeps status mapping centralized so UI logic remains simple and consistent.
         */
        let s = status.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if ["ok", "good", "pass", "info"].contains(s) { return .ok }
        if ["warn", "warning"].contains(s) { return .warn }
        if ["bad", "fail", "error"].contains(s) { return .bad }
        return .unknown
    }

    public static func fromSnapshotSection(_ section: SnapshotSection) -> SectionHealth {
        /**
         Summary
         Derive a `SectionHealth` from a snapshot section payload.

         Inputs
         section: Snapshot section.

         Outputs
         Derived `SectionHealth` value.

         Side effects
         None.

         Error handling
         None. Unknown states are mapped to `.unknown`.

         Ties to other methods
         Used by the view model to show status badges in the sidebar and overview.

         Why this exists
         Provides a consistent rule set for section health without requiring each view to reimplement it.
         */
        if let diagnostics = section.diagnostics,
           case let .bool(ok) = diagnostics["ok"],
           ok == false
        {
            if _shouldTreatFailedDiagnosticsAsUnknown(diagnostics: diagnostics) {
                return .unknown
            }
            return .bad
        }

        if let metrics = section.metrics {
            var best: SectionHealth = .unknown
            for row in metrics {
                let rowHealth = fromStatusString(row.status)
                if rowHealth == .bad { return .bad }
                if rowHealth == .warn { best = .warn }
                if rowHealth == .ok, best == .unknown { best = .ok }
            }
            return best
        }

        if let diagnostics = section.diagnostics,
           case let .bool(ok) = diagnostics["ok"],
           ok == true
        {
            return .ok
        }

        return .unknown
    }

    private static func _shouldTreatFailedDiagnosticsAsUnknown(diagnostics: [String: JSONValue]) -> Bool {
        /**
         Summary
         Determine whether a diagnostics failure represents unavailable data rather than a health failure.

         Inputs
         diagnostics: Section diagnostics payload.

         Outputs
         True when failure should be rendered as unknown.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `fromSnapshotSection` when `diagnostics.ok` is false.

         Why this exists
         Backend collection/access failures should render as unknown to avoid implying a confirmed unhealthy state.
         */
        if let permissionRequired = _boolValue(for: "permission_required", in: diagnostics), permissionRequired {
            return true
        }
        let errorText = _normalizedDiagnosticsText(
            _stringValue(for: "error", in: diagnostics) ??
                _stringValue(for: "guidance", in: diagnostics) ??
                ""
        )
        if errorText.isEmpty {
            return false
        }
        let unavailableTokens: [String] = [
            "unavailable",
            "not available",
            "not reachable",
            "network unreachable",
            "connection refused",
            "connection reset",
            "timed out",
            "timeout",
            "no data",
            "permission denied",
            "permission required",
            "unsupported",
            "iokit/corefoundation unavailable",
        ]
        return unavailableTokens.contains { errorText.contains($0) }
    }

    private static func _stringValue(for key: String, in diagnostics: [String: JSONValue]) -> String? {
        /**
         Summary
         Extract a diagnostics string field when present.

         Inputs
         key: Diagnostics key.
         diagnostics: Section diagnostics payload.

         Outputs
         Optional string value.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `_shouldTreatFailedDiagnosticsAsUnknown`.

         Why this exists
         Keeping JSONValue extraction local avoids repetitive switch logic in health mapping.
         */
        guard let raw = diagnostics[key], case let .string(value) = raw else {
            return nil
        }
        return value
    }

    private static func _boolValue(for key: String, in diagnostics: [String: JSONValue]) -> Bool? {
        /**
         Summary
         Extract a diagnostics boolean field when present.

         Inputs
         key: Diagnostics key.
         diagnostics: Section diagnostics payload.

         Outputs
         Optional boolean value.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `_shouldTreatFailedDiagnosticsAsUnknown`.

         Why this exists
         Permission and capability flags influence whether failures should be marked unknown.
         */
        guard let raw = diagnostics[key], case let .bool(value) = raw else {
            return nil
        }
        return value
    }

    private static func _normalizedDiagnosticsText(_ value: String) -> String {
        /**
         Summary
         Normalize diagnostics text for token-based matching.

         Inputs
         value: Raw diagnostics message.

         Outputs
         Lowercased, trimmed text.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `_shouldTreatFailedDiagnosticsAsUnknown`.

         Why this exists
         Token checks should be robust against case and extra whitespace differences.
         */
        value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }
}
