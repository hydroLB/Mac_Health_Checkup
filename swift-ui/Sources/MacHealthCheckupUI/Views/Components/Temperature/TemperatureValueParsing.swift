import Foundation

struct ParsedTemperature {
    /**
     Summary
     Hold a parsed temperature numeric value and unit.

     Inputs
     value: Numeric temperature in the parsed unit.
     unit: Parsed unit (C/F).
     hadDecimal: Whether the original string contained a decimal point.

     Outputs
     Value type consumed by formatting and conversion logic.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Produced by `TemperatureValueParsing.parseTemperature(text:)`.

     Why this exists
     Preserving whether the source had a decimal allows formatting to keep the same "shape" when toggling units.
     */

    let value: Double
    let unit: TemperatureUnit
    let hadDecimal: Bool
}

enum TemperatureValueParsing {
    static func parseTemperature(text: String) -> ParsedTemperature? {
        /**
         Summary
         Parse a temperature string into a numeric value and unit.

         Inputs
         text: Raw text value (examples: `75C`, `75 °F`, `75.5 c`).

         Outputs
         `ParsedTemperature` when parsing succeeds, otherwise nil.

         Side effects
         None.

         Error handling
         Returns nil when regex compilation, matching, or numeric conversion fails.

         Ties to other methods
         Used by `TemperatureValueView` to decide when to render a clickable unit toggle.

         Why this exists
         Centralizing parsing keeps regex behavior consistent across all temperature renderers.
         */
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
}

