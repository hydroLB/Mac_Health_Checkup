import Foundation
import SwiftUI

private enum TemperatureUnit: String {
    case celsius = "C"
    case fahrenheit = "F"

    var toggled: TemperatureUnit {
        switch self {
        case .celsius: return .fahrenheit
        case .fahrenheit: return .celsius
        }
    }
}

private struct ParsedTemperature {
    let value: Double
    let unit: TemperatureUnit
    let hadDecimal: Bool
}

private func _parseTemperature(text: String) -> ParsedTemperature? {
    let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
    if trimmed.isEmpty { return nil }

    let pattern = #"^\s*([+-]?\d+(?:\.\d+)?)\s*°?\s*([cCfF])\s*$"#
    guard let re = try? NSRegularExpression(pattern: pattern, options: []) else { return nil }
    let range = NSRange(trimmed.startIndex..<trimmed.endIndex, in: trimmed)
    guard let match = re.firstMatch(in: trimmed, options: [], range: range) else { return nil }
    guard match.numberOfRanges >= 3 else { return nil }

    guard
        let valueRange = Range(match.range(at: 1), in: trimmed),
        let unitRange = Range(match.range(at: 2), in: trimmed)
    else { return nil }

    let valueText = String(trimmed[valueRange])
    let unitText = String(trimmed[unitRange]).uppercased()
    guard let value = Double(valueText) else { return nil }
    let unit: TemperatureUnit = (unitText == "F") ? .fahrenheit : .celsius
    let hadDecimal = valueText.contains(".")
    return ParsedTemperature(value: value, unit: unit, hadDecimal: hadDecimal)
}

private func _formatTemperature(value: Double, hadDecimal: Bool) -> String {
    if hadDecimal {
        return String(format: "%.1f", value)
    }
    let rounded = Int(value.rounded())
    return "\(rounded)"
}

private func _convert(value: Double, from: TemperatureUnit, to: TemperatureUnit) -> Double {
    if from == to { return value }
    switch (from, to) {
    case (.celsius, .fahrenheit):
        return (value * 9.0 / 5.0) + 32.0
    case (.fahrenheit, .celsius):
        return (value - 32.0) * 5.0 / 9.0
    default:
        return value
    }
}

struct TemperatureValueView: View {
    /**
     Summary
     Render a temperature string with a click-to-toggle C/F control.

     Inputs
     theme: Theme for styling.
     raw: Raw text value (typically like `75C`).

     Outputs
     A SwiftUI view that displays the value and allows toggling the unit.

     Side effects
     Persists the preferred unit in UserDefaults.

     Error handling
     Falls back to plain text when the input is not a temperature.

     Ties to other methods
     Used by metrics and other views that display temperature values.

     Why this exists
     Temperature values are easier to read when the unit is user-selectable without navigating into settings.
     */

    let theme: Theme
    let raw: String
    let valueColor: Color?

    @AppStorage("mhc_temperature_unit") private var preferredUnitRaw: String = TemperatureUnit.celsius.rawValue

    var body: some View {
        let preferred = TemperatureUnit(rawValue: preferredUnitRaw) ?? .celsius
        if let parsed = _parseTemperature(text: raw) {
            let converted = _convert(value: parsed.value, from: parsed.unit, to: preferred)
            let formatted = _formatTemperature(value: converted, hadDecimal: parsed.hadDecimal)
            HStack(spacing: 0) {
                Text(formatted)
                    .font(theme.fonts.mono)
                    .foregroundStyle(valueColor ?? theme.colors.field)
                Text("°\(preferred.rawValue)")
                    .font(theme.fonts.mono)
                    .foregroundStyle(theme.colors.label)
                    .padding(.leading, 2)
                    .contentShape(Rectangle())
                    .onTapGesture {
                        preferredUnitRaw = preferred.toggled.rawValue
                    }
            }
            .help("Click °\(preferred.rawValue) to toggle temperature units.")
        } else {
            Text(raw)
                .font(theme.fonts.mono)
                .foregroundStyle(valueColor ?? theme.colors.field)
        }
    }
}

struct TemperatureUnitToggleLabel: View {
    /**
     Summary
     Render a standalone unit label that toggles the preferred temperature unit.

     Inputs
     theme: Theme for styling.

     Outputs
     A small clickable unit label.

     Side effects
     Persists the preferred unit in UserDefaults.

     Error handling
     None.

     Ties to other methods
     Used by the Performance metrics header to show the current unit.

     Why this exists
     Users look for the unit indicator in headers; making it clickable is the fastest way to toggle globally.
     */

    let theme: Theme
    @AppStorage("mhc_temperature_unit") private var preferredUnitRaw: String = TemperatureUnit.celsius.rawValue

    var body: some View {
        let preferred = TemperatureUnit(rawValue: preferredUnitRaw) ?? .celsius
        Text("°\(preferred.rawValue)")
            .font(theme.fonts.caption)
            .foregroundStyle(theme.colors.label)
            .contentShape(Rectangle())
            .onTapGesture {
                preferredUnitRaw = preferred.toggled.rawValue
            }
            .help("Click to toggle between °C and °F.")
    }
}
