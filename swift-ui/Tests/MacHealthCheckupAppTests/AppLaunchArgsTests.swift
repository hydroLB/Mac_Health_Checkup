import XCTest
@testable import MacHealthCheckupApp

final class AppLaunchArgsTests: XCTestCase {
    func testParseIgnoresDoubleDashSentinel() throws {
        /**
         Summary
         Ensure `--` is accepted as an end-of-options sentinel.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Fails via XCTest assertions when parsing throws or returns unexpected values.

         Ties to other methods
         Exercises `AppLaunchArgs.parse`.

         Why this exists
         Some launchers include `--` in argv; the app should not fail on this benign sentinel.
         */
        let args = ["mac-health-checkup-ui", "--config", "/tmp/config.json", "--", "--ignored"]
        let parsed = try AppLaunchArgs.parse(args)
        XCTAssertEqual(parsed.configPath, "/tmp/config.json")
    }
}

