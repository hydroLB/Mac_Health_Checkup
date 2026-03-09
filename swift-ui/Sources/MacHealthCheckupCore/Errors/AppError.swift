import Foundation

public struct AppError: Error, CustomStringConvertible, Sendable {
    /**
     Summary
     Carry an actionable error message with source context.

     Inputs
     message: Human-readable error message with context.
     underlying: Optional underlying error for debugging.

     Outputs
     A value-type error suitable for UI display and logging.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Created by `AppError.context` and used across config loading and backend execution.

     Why this exists
     Keeps failure messages consistent and easy to attribute to a specific file and method.
     */
    public let message: String
    public let underlying: (any Error)?

    public var userFacingMessage: String {
        /**
         Summary
         Return a UI-friendly error message without source-code context prefixes.

         Inputs
         None.

         Outputs
         A concise message suitable for banners and user-visible summaries.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by SwiftUI views that render non-technical error banners.

         Why this exists
         Source file and method context is useful for debugging but looks unprofessional in user-facing UI copy.
         */
        let trimmed = message.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            return "Unexpected error."
        }
        guard let firstSpace = trimmed.firstIndex(of: " ") else {
            return trimmed
        }

        let prefix = String(trimmed[..<firstSpace])
        let hasFileAndMethodPrefix = prefix.contains(".swift:") || (prefix.contains("/") && prefix.contains(":"))
        if hasFileAndMethodPrefix {
            let suffix = String(trimmed[trimmed.index(after: firstSpace)...]).trimmingCharacters(
                in: .whitespacesAndNewlines
            )
            if !suffix.isEmpty {
                return suffix
            }
        }
        return trimmed
    }

    public var description: String {
        /**
         Summary
         Render the error into a single line string.

         Inputs
         None.

         Outputs
         A string suitable for UI display.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by SwiftUI views when showing error banners and detail sheets.

         Why this exists
         Ensures the UI always has a deterministic message to display.
         */
        if let underlying {
            return "\(message) (underlying: \(underlying))"
        }
        return message
    }

    public static func context(
        _ file: StaticString,
        _ function: StaticString,
        _ message: String,
        _ underlying: (any Error)? = nil
    ) -> AppError {
        /**
         Summary
         Create a context-rich error tied to a file and function.

         Inputs
         file: Source file identifier.
         function: Source function identifier.
         message: Human-readable message.
         underlying: Optional underlying error.

         Outputs
         A new `AppError` instance.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by loaders and backend runners to create consistent error output.

         Why this exists
         Swift errors often lose call-site context; this keeps failures easy to trace.
         */
        let context = "\(file):\(function) \(message)"
        return AppError(message: context, underlying: underlying)
    }
}
