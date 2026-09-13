import Foundation
import XCTest
@testable import MacHealthCheckupCore

final class SnapshotModelsCodingTests: XCTestCase {
    func testSnapshotEncodingPreservesBackendSchemaAndRoundTrips() throws {
        /**
         Summary
         Ensure cached snapshot encoding preserves array-shaped metrics and arbitrary diagnostics JSON.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Encodes and decodes an in-memory snapshot fixture.

         Error handling
         Fails through XCTest assertions or propagated coding errors.

         Ties to other methods
         Exercises the Codable contract used by the iOS `SnapshotCache`.

         Why this exists
         Snapshot caching must round-trip the Python backend schema instead of synthesizing incompatible Swift shapes.
         */
        let sourceJSON = """
        {
          "schema_version": 2,
          "generated_at_unix_ms": 1700000000000,
          "theme": {
            "ui": { "window_title": "Mac Health Checkup" },
            "colors": {
              "bg": "#23272e",
              "fg": "#ffffff",
              "ok": "#2ecc40",
              "warn": "#ffdc00",
              "bad": "#ff4136",
              "section": "#339af0",
              "label": "#f1c40f",
              "field": "#daf6ff"
            },
            "fonts": {
              "family_default": "Helvetica",
              "family_mono": "Menlo",
              "size_section": 16,
              "size_banner": 18,
              "size_field": 13,
              "size_tooltip": 10
            },
            "gui": {
              "card_bg": "#1b2027",
              "card_border": "#2a313c",
              "section_padx": 4,
              "section_pady": 3,
              "auto_refresh_ms": 1000,
              "scrollable_rows": {}
            }
          },
          "section_catalog": [
            { "title": "Fan", "subtitle": "Cooling", "key": "fan" }
          ],
          "sections": [
            {
              "key": "fan",
              "field": null,
              "metrics": [["Fan 0", "1,234 RPM", "ok"]],
              "table": null,
              "diagnostics": {
                "ok": true,
                "sample_count": 1,
                "nested": { "values": ["one", null, false] }
              }
            }
          ],
          "ok": true,
          "error": null
        }
        """

        let decoded = try JSONDecoder().decode(Snapshot.self, from: Data(sourceJSON.utf8))
        let encoded = try JSONEncoder().encode(decoded)
        let encodedRoot = try XCTUnwrap(
            JSONSerialization.jsonObject(with: encoded) as? [String: Any]
        )
        let sections = try XCTUnwrap(encodedRoot["sections"] as? [[String: Any]])
        let metrics = try XCTUnwrap(sections.first?["metrics"] as? [[Any]])
        XCTAssertEqual(metrics.first?[0] as? String, "Fan 0")
        XCTAssertEqual(metrics.first?[1] as? String, "1,234 RPM")
        XCTAssertEqual(metrics.first?[2] as? String, "ok")

        let roundTripped = try JSONDecoder().decode(Snapshot.self, from: encoded)
        XCTAssertEqual(roundTripped.sections.first?.metrics?.first?.label, "Fan 0")
        if case let .object(nested)? = roundTripped.sections.first?.diagnostics?["nested"],
           case let .array(values)? = nested["values"]
        {
            XCTAssertEqual(values.count, 3)
        } else {
            XCTFail("Expected nested diagnostics JSON to round-trip")
        }
    }
}
