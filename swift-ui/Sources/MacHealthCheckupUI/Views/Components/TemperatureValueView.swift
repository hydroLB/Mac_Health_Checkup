import Foundation
import SwiftUI

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
        if let parsed = TemperatureValueParsing.parseTemperature(text: raw) {
            let converted = TemperatureValueFormatting.convert(value: parsed.value, from: parsed.unit, to: preferred)
            let formatted = TemperatureValueFormatting.formatTemperature(value: converted, hadDecimal: parsed.hadDecimal)
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
