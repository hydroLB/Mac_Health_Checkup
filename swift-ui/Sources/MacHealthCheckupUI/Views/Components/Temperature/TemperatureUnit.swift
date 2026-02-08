import Foundation

enum TemperatureUnit: String {
    /**
     Summary
     Represent a temperature unit choice for display and conversion.

     Inputs
     Raw value "C" or "F".

     Outputs
     A typed unit enum.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Used by `TemperatureValueParsing` and `TemperatureValueFormatting`.

     Why this exists
     Keeping unit state typed prevents stringly-typed mistakes and keeps parsing and formatting consistent.
     */

    case celsius = "C"
    case fahrenheit = "F"

    var toggled: TemperatureUnit {
        /**
         Summary
         Return the opposite unit for click-to-toggle UI interactions.

         Inputs
         None.

         Outputs
         The other `TemperatureUnit`.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `TemperatureValueView` and `TemperatureUnitToggleLabel`.

         Why this exists
         Keeps toggle behavior centralized so UI components do not re-encode the mapping.
         */
        switch self {
        case .celsius: return .fahrenheit
        case .fahrenheit: return .celsius
        }
    }
}

