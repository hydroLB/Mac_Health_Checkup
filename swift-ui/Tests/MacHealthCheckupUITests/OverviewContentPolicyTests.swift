import XCTest
import MacHealthCheckupCore
@testable import MacHealthCheckupUI

final class OverviewContentPolicyTests: XCTestCase {
    func testMixedHealthCardPreviewsOnlyAlertsAndPreservesDetailPayload() throws {
        let payload = try JSONDecoder().decode(SnapshotSection.self, from: Data(#"{"key":"security","metrics":[["FileVault","Off","warning"],["SIP","Enabled","ok"],["Firewall","Off","bad"],["Sensor","Unavailable","unknown"]]}"#.utf8))
        XCTAssertEqual(OverviewContentPolicy.alertMetrics(payload: payload).map(\.label), ["FileVault", "Firewall"])
        XCTAssertEqual(OverviewContentPolicy.summary(payload: payload, fallback: "All readings"), "FileVault: Off | Firewall: Off")
        XCTAssertTrue(OverviewContentPolicy.hasExpandableContent(payload: payload))
        XCTAssertEqual(payload.metrics?.count, 4)
    }

    func testDiagnosticAlertWithoutMetricsRetainsExplanation() throws {
        let payload = try JSONDecoder().decode(SnapshotSection.self, from: Data(#"{"key":"test","field":"Hardware failure","diagnostics":{"ok":false}}"#.utf8))
        XCTAssertTrue(OverviewGridPolicy.isAlert(for: SectionHealth.fromSnapshotSection(payload)))
        XCTAssertEqual(OverviewContentPolicy.summary(payload: payload, fallback: "Hardware failure"), "Hardware failure")
        XCTAssertFalse(OverviewGridPolicy.isAlert(for: .unknown))
        XCTAssertFalse(OverviewGridPolicy.isAlert(for: .ok))
    }
}
