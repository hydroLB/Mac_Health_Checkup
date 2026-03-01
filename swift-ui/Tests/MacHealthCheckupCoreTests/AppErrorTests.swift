import XCTest
@testable import MacHealthCheckupCore

final class AppErrorTests: XCTestCase {
    func testUserFacingMessageStripsSourceContextPrefix() {
        /**
         Summary
         Ensure UI-facing messages omit file and method prefixes.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Fails via XCTest assertions when prefix stripping regresses.

         Ties to other methods
         Exercises `AppError.userFacingMessage`.

         Why this exists
         Source context is useful for debugging but should not leak into user-facing banners.
         */
        let error = AppError.context(
            "MacHealthCheckupUI/DashboardViewModel.swift",
            "_backendWarningIfAny(exitCode:snapshot:stderr:)",
            "Backend completed with partial results (exit code 1)."
        )
        XCTAssertEqual(error.userFacingMessage, "Backend completed with partial results (exit code 1).")
    }

    func testUserFacingMessageKeepsPlainMessages() {
        /**
         Summary
         Ensure already-clean messages are preserved unchanged.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Fails via XCTest assertions when plain messages are altered unexpectedly.

         Ties to other methods
         Exercises `AppError.userFacingMessage`.

         Why this exists
         UI text should remain stable when no source-context prefix exists.
         */
        let error = AppError(message: "Network is temporarily unavailable.", underlying: nil)
        XCTAssertEqual(error.userFacingMessage, "Network is temporarily unavailable.")
    }
}
