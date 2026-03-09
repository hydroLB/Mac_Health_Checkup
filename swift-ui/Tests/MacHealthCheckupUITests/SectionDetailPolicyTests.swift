import XCTest
@testable import MacHealthCheckupCore
@testable import MacHealthCheckupUI

final class SectionDetailPolicyTests: XCTestCase {
    func testSummaryCardIsHiddenForDedupedSectionsWhenMetricsExist() throws {
        /**
         Summary
         Ensure sections with detailed metrics do not render a duplicate top summary card.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Fails via XCTest assertions when de-duplication policy regresses.

         Ties to other methods
         Exercises `SectionDetailPolicy.shouldShowFieldSummaryCard`.

         Why this exists
         The detail screen should avoid showing the same status line twice when a metrics grid already provides the content.
         */
        let payload = try _decodeSection(
            """
            {
              "key": "security",
              "field": "FileVault: Off | SIP: Enabled",
              "metrics": [
                ["FileVault", "Off", "warn"],
                ["SIP", "Enabled", "ok"]
              ],
              "table": null,
              "diagnostics": { "ok": true }
            }
            """
        )

        for key in ["security", "system", "updates", "devices", "ports"] {
            XCTAssertFalse(
                SectionDetailPolicy.shouldShowFieldSummaryCard(sectionKey: key, payload: payload),
                "Expected top summary to be hidden for section \(key) when metrics exist."
            )
        }
    }

    func testSummaryCardIsHiddenForDedupedSectionsWhenTableExists() throws {
        /**
         Summary
         Ensure sections with tabular detail do not render a duplicate top summary card.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Fails via XCTest assertions when de-duplication policy regresses.

         Ties to other methods
         Exercises `SectionDetailPolicy.shouldShowFieldSummaryCard`.

         Why this exists
         Device and port sections are table-first, so the extra summary bar adds no unique value.
         */
        let payload = try _decodeSection(
            """
            {
              "key": "devices",
              "field": "2 attached devices",
              "metrics": null,
              "table": {
                "headers": ["Bus", "Device"],
                "rows": [
                  ["USB", "Keyboard"],
                  ["USB", "Mouse"]
                ]
              },
              "diagnostics": { "ok": true }
            }
            """
        )

        XCTAssertFalse(SectionDetailPolicy.shouldShowFieldSummaryCard(sectionKey: "devices", payload: payload))
        XCTAssertFalse(SectionDetailPolicy.shouldShowFieldSummaryCard(sectionKey: "ports", payload: payload))
    }

    func testSummaryCardRemainsVisibleWhenNoDetailContentExists() throws {
        /**
         Summary
         Ensure sections still show the top summary when no metrics or table content exists.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Fails via XCTest assertions when fallback summary behavior regresses.

         Ties to other methods
         Exercises `SectionDetailPolicy.shouldShowFieldSummaryCard`.

         Why this exists
         Removing the summary unconditionally would leave an empty detail area for sections that only emit field text.
         */
        let payload = try _decodeSection(
            """
            {
              "key": "security",
              "field": "Security checks unavailable",
              "metrics": null,
              "table": null,
              "diagnostics": { "ok": false }
            }
            """
        )

        XCTAssertTrue(SectionDetailPolicy.shouldShowFieldSummaryCard(sectionKey: "security", payload: payload))
    }

    private func _decodeSection(_ json: String) throws -> SnapshotSection {
        /**
         Summary
         Decode a section JSON fixture into a typed `SnapshotSection`.

         Inputs
         json: Section JSON payload.

         Outputs
         Decoded `SnapshotSection`.

         Side effects
         None.

         Error handling
         Throws decoding errors when fixtures are malformed.

         Ties to other methods
         Used by section-detail policy tests.

         Why this exists
         JSON fixtures keep policy tests readable while matching backend wire shapes.
         */
        let data = Data(json.utf8)
        return try JSONDecoder().decode(SnapshotSection.self, from: data)
    }
}
