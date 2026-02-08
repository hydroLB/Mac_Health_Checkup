import Foundation

enum TemperatureValueFormatting {
    static func formatTemperature(value: Double, hadDecimal: Bool) -> String {
        /**
         Summary
         Format a numeric temperature value as a string.

         Inputs
         value: Temperature value.
         hadDecimal: Whether the source representation included a decimal.

         Outputs
         Formatted numeric text without the unit.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `TemperatureValueView` after unit conversion.

         Why this exists
         The UI should preserve the original precision style when toggling units to avoid distracting reformatting.
         */
        if hadDecimal {
            return String(format: "%.1f", value)
        }
        let rounded = Int(value.rounded())
        return "\(rounded)"
    }

    static func convert(value: Double, from: TemperatureUnit, to: TemperatureUnit) -> Double {
        /**
         Summary
         Convert a temperature between Celsius and Fahrenheit.

         Inputs
         value: Temperature value in the `from` unit.
         from: Source unit.
         to: Target unit.

         Outputs
         Converted temperature value.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `TemperatureValueView` when toggling units.

         Why this exists
         Keeps conversion math in one place so rounding behavior stays consistent across the UI.
         */
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
}

