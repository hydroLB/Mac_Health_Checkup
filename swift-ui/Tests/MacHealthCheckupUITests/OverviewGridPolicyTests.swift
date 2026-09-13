import XCTest
@testable import MacHealthCheckupUI

final class OverviewGridPolicyTests: XCTestCase {
    func testColumnCountUsesAvailableWidthAndCapsAtThree() {
        XCTAssertEqual(OverviewGridPolicy.columnCount(for: 320, spacing: 12), 1)
        XCTAssertEqual(OverviewGridPolicy.columnCount(for: 692, spacing: 12), 2)
        XCTAssertEqual(OverviewGridPolicy.columnCount(for: 1_044, spacing: 12), 3)
        XCTAssertEqual(OverviewGridPolicy.columnCount(for: 4_000, spacing: 12), 3)
    }

    func testColumnCountHandlesInvalidDimensionsConservatively() {
        XCTAssertEqual(OverviewGridPolicy.columnCount(for: -100, spacing: -12), 1)
        XCTAssertEqual(OverviewGridPolicy.columnCount(for: 800, spacing: 12, minimumWidth: 0), 3)
    }

    func testPriorityPlacesProblemsBeforeHealthySections() {
        XCTAssertLessThan(OverviewGridPolicy.priority(for: .bad), OverviewGridPolicy.priority(for: .warn))
        XCTAssertLessThan(OverviewGridPolicy.priority(for: .warn), OverviewGridPolicy.priority(for: .unknown))
        XCTAssertLessThan(OverviewGridPolicy.priority(for: .unknown), OverviewGridPolicy.priority(for: .ok))
    }
}
