import MacHealthCheckupCore
import SwiftUI

struct GeneralInfoSummaryView: View {
    /**
     Summary
     Render the General Info section as clean labeled rows instead of a single pipe-delimited line.

     Inputs
     theme: Theme for consistent typography and colors.
     rawField: Raw field string from the snapshot backend, typically `Model | Chip | macOS X.Y | Serial`.

     Outputs
     A SwiftUI view for the General Info summary card.

     Side effects
     None.

     Error handling
     Falls back to plain text when parsing fails.

     Ties to other methods
     Used by `SectionDetailView` when `selectedKey == "general"`.

     Why this exists
     The General Info payload is easy to parse and reads better as labeled rows, reducing scanning friction and avoiding a "single long selected string" look.
     */

    let theme: Theme
    let rawField: String

    var body: some View {
        /**
         Summary
         Render a parsed set of labeled rows or a plain-text fallback.

         Inputs
         None.

         Outputs
         A SwiftUI view.

         Side effects
         None.

         Error handling
         None. Parsing failures render a plain text fallback.

         Ties to other methods
         Uses `_parseGeneralInfoField`.

         Why this exists
         Keeps the view resilient to backend formatting tweaks without breaking the UI.
         */
        if let parsed = _parseGeneralInfoField(rawField) {
            VStack(alignment: .leading, spacing: 10) {
                _GeneralInfoRow(
                    theme: theme,
                    systemImage: "laptopcomputer",
                    label: "Model",
                    value: parsed.model,
                    valueFont: theme.fonts.body
                )
                Divider().opacity(0.6)
                _GeneralInfoRow(
                    theme: theme,
                    systemImage: "cpu",
                    label: "Chip",
                    value: parsed.chip,
                    valueFont: theme.fonts.body
                )
                Divider().opacity(0.6)
                _GeneralInfoRow(
                    theme: theme,
                    systemImage: "macwindow",
                    label: "OS",
                    value: parsed.os,
                    valueFont: theme.fonts.mono
                )
                Divider().opacity(0.6)
                _GeneralInfoRow(
                    theme: theme,
                    systemImage: "number",
                    label: "Serial",
                    value: parsed.serial,
                    valueFont: theme.fonts.mono
                )
            }
            .textSelection(.enabled)
        } else {
            Text(rawField)
                .font(theme.fonts.body)
                .foregroundStyle(theme.colors.field)
                .frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
        }
    }
}

private struct _GeneralInfoParts: Equatable, Sendable {
    /**
     Summary
     Hold parsed General Info parts for clean rendering.

     Inputs
     model: Model name.
     chip: Chip string.
     os: OS string.
     serial: Serial number.

     Outputs
     Value type consumed by `GeneralInfoSummaryView`.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Produced by `_parseGeneralInfoField`.

     Why this exists
     Keeps parsing and rendering decoupled and avoids re-splitting strings in the view body.
     */

    let model: String
    let chip: String
    let os: String
    let serial: String
}

private func _parseGeneralInfoField(_ raw: String) -> _GeneralInfoParts? {
    /**
     Summary
     Parse the General Info field string into stable parts.

     Inputs
     raw: Raw summary field, expected to be pipe-delimited.

     Outputs
     Parsed parts or nil when parsing fails.

     Side effects
     None.

     Error handling
     Never throws. Returns nil when the shape is unexpected.

     Ties to other methods
     Used by `GeneralInfoSummaryView`.

     Why this exists
     The backend intentionally emits a compact string; the UI can upgrade it into a native layout without changing the snapshot schema.
     */
    let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
    if trimmed.isEmpty { return nil }
    let parts = trimmed
        .split(separator: "|", omittingEmptySubsequences: false)
        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }
    guard parts.count >= 4 else { return nil }
    let model = parts[0]
    let chip = parts[1]
    let os = parts[2]
    let serial = parts[3]
    return _GeneralInfoParts(model: model, chip: chip, os: os, serial: serial)
}

private struct _GeneralInfoRow: View {
    /**
     Summary
     Render a single labeled General Info row with an icon and a selectable value.

     Inputs
     theme: Theme values.
     systemImage: SF Symbol name.
     label: Left-side label.
     value: Right-side value.
     valueFont: Font used for the value.

     Outputs
     A SwiftUI row view.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Used by `GeneralInfoSummaryView`.

     Why this exists
     Keeps the General Info card layout consistent and easy to tweak in one place.
     */

    let theme: Theme
    let systemImage: String
    let label: String
    let value: String
    let valueFont: Font

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Image(systemName: systemImage)
                .foregroundStyle(theme.colors.label)
                .frame(width: 18)
            Text(label)
                .font(theme.fonts.caption)
                .foregroundStyle(theme.colors.label)
                .frame(width: 54, alignment: .leading)
            Text(value)
                .font(valueFont)
                .foregroundStyle(theme.colors.field)
                .frame(maxWidth: .infinity, alignment: .leading)
                .lineLimit(2)
            Spacer(minLength: 0)
        }
    }
}

