import Foundation

public enum HexColor {
    /**
     Summary
     Provide validation helpers for hex color strings.

     Inputs
     None.

     Outputs
     Validation results.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Used by `ColorsConfig.validated` before the theme is constructed.

     Why this exists
     Keeps config validation explicit and prevents UI crashes from invalid color strings.
     */

    public static func isValidHex(_ value: String) -> Bool {
        /**
         Summary
         Validate a color string in the form `#RRGGBB`.

         Inputs
         value: Candidate string.

         Outputs
         `true` when value matches `#RRGGBB` and contains only hex digits.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used during config validation.

         Why this exists
         Ensures consistent parsing logic for all configured colors.
         */
        guard value.count == 7, value.hasPrefix("#") else { return false }
        let hex = value.dropFirst()
        return hex.allSatisfy { ch in
            ("0"..."9").contains(ch) || ("a"..."f").contains(ch.lowercased())
        }
    }
}

