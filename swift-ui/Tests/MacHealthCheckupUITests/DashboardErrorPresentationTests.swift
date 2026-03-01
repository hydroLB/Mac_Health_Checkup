import Foundation
import XCTest
@testable import MacHealthCheckupCore
@testable import MacHealthCheckupUI

final class DashboardErrorPresentationTests: XCTestCase {
    @MainActor
    func testRefreshOnceFormatsPartialResultsWarningWithCountsAndSectionList() async throws {
        /**
         Summary
         Ensure partial backend failures are presented with a concise count-based warning.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Updates `DashboardViewModel` published state.

         Error handling
         Fails via XCTest assertions when warning text changes unexpectedly.

         Ties to other methods
         Exercises `DashboardViewModel.refreshOnce` and backend warning mapping.

         Why this exists
         Operators need a readable warning that highlights scope without dumping raw collector details.
         */
        let snapshot = try _decodeSnapshot(
            _snapshotJSON(
                ok: false,
                sectionsJSON: """
                [
                  { "key": "startup", "field": "failed", "metrics": null, "table": null, "diagnostics": { "ok": false, "error": "failed" } },
                  { "key": "backups", "field": "failed", "metrics": null, "table": null, "diagnostics": { "ok": false, "error": "failed" } },
                  { "key": "fan", "field": "failed", "metrics": null, "table": null, "diagnostics": { "ok": false, "error": "failed" } },
                  { "key": "battery", "field": "failed", "metrics": null, "table": null, "diagnostics": { "ok": false, "error": "failed" } },
                  { "key": "network", "field": "failed", "metrics": null, "table": null, "diagnostics": { "ok": false, "error": "failed" } }
                ]
                """
            )
        )
        let backend = StaticSnapshotBackend(
            response: BackendSnapshotResponse(snapshot: snapshot, exitCode: 1, stderr: "backend stderr", rawJSON: nil)
        )
        let model = DashboardViewModel(
            backend: backend,
            sections: [SectionDescriptor(title: "Startup", subtitle: "Startup checks", key: "startup")],
            refreshIntervalMs: 1_000,
            fanRefreshIntervalMs: 1_000,
            scrollableRows: [:],
            initialTheme: Theme.fallback(appTitle: "Mac Health Checkup"),
            appTitle: "Mac Health Checkup"
        )

        await model.refreshOnce()

        let message = try XCTUnwrap(model.lastError?.description)
        XCTAssertTrue(message.contains("Backend completed with partial results (exit code 1)."))
        XCTAssertTrue(message.contains("5 section checks failed: startup, backups, fan, battery, and 1 more."))
        XCTAssertTrue(message.contains("Review backend logs for details."))
    }

    func testSectionHealthUsesUnknownWhenDiagnosticsAreUnavailable() throws {
        /**
         Summary
         Ensure unavailable collector diagnostics are rendered as unknown health.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Fails via XCTest assertions when unavailable mapping is not respected.

         Ties to other methods
         Exercises `SectionHealth.fromSnapshotSection` and `SectionHealth.labelText`.

         Why this exists
         Data-source outages should not be shown as confirmed unhealthy system state.
         */
        let snapshot = try _decodeSnapshot(
            _snapshotJSON(
                ok: false,
                sectionsJSON: """
                [
                  { "key": "fan", "field": "Fan speeds unavailable", "metrics": null, "table": null, "diagnostics": { "ok": false, "error": "IOKit/CoreFoundation unavailable" } }
                ]
                """
            )
        )
        let health = SectionHealth.fromSnapshotSection(snapshot.sections[0])
        XCTAssertEqual(health, .unknown)
        XCTAssertEqual(health.labelText(), "UNK")
    }

    func testSectionHealthKeepsExplicitFailuresAsBad() throws {
        /**
         Summary
         Ensure explicit non-availability failures continue to render as bad health.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Fails via XCTest assertions when explicit failures are downgraded incorrectly.

         Ties to other methods
         Exercises `SectionHealth.fromSnapshotSection`.

         Why this exists
         The UI still needs to flag true bad states distinctly from missing data.
         */
        let snapshot = try _decodeSnapshot(
            _snapshotJSON(
                ok: false,
                sectionsJSON: """
                [
                  { "key": "battery", "field": "Battery check failed", "metrics": null, "table": null, "diagnostics": { "ok": false, "error": "battery health threshold exceeded" } }
                ]
                """
            )
        )
        let health = SectionHealth.fromSnapshotSection(snapshot.sections[0])
        XCTAssertEqual(health, .bad)
    }

    @MainActor
    func testSectionSummaryTextUsesConcreteSystemMetrics() async throws {
        /**
         Summary
         Ensure system overview summaries include both disk and memory concrete values when available.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Updates `DashboardViewModel` published state.

         Error handling
         Fails via XCTest assertions when summary selection regresses.

         Ties to other methods
         Exercises `DashboardViewModel.sectionSummaryText`.

         Why this exists
         The overview should surface concrete capacity numbers at a glance instead of generic fallback text.
         */
        let snapshot = try _decodeSnapshot(
            _snapshotJSON(
                ok: true,
                sectionsJSON: """
                [
                  {
                    "key": "system",
                    "field": "System pressure unavailable",
                    "metrics": [
                      ["Disk free", "77%", "warn"],
                      ["Memory free", "42%", "ok"]
                    ],
                    "table": null,
                    "diagnostics": { "ok": true }
                  }
                ]
                """
            )
        )
        let backend = StaticSnapshotBackend(
            response: BackendSnapshotResponse(snapshot: snapshot, exitCode: 0, stderr: "", rawJSON: nil)
        )
        let model = DashboardViewModel(
            backend: backend,
            sections: [SectionDescriptor(title: "System", subtitle: "Storage and memory", key: "system")],
            refreshIntervalMs: 1_000,
            fanRefreshIntervalMs: 1_000,
            scrollableRows: [:],
            initialTheme: Theme.fallback(appTitle: "Mac Health Checkup"),
            appTitle: "Mac Health Checkup"
        )

        await model.refreshOnce()

        let summary = model.sectionSummaryText(for: "system")
        XCTAssertEqual(summary, "Disk free: 77% | Memory free: 42%")
    }

    @MainActor
    func testSectionSummaryTextUsesConcreteUpdatesCount() async throws {
        /**
         Summary
         Ensure updates overview summaries show concrete update counts when available.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Updates `DashboardViewModel` published state.

         Error handling
         Fails via XCTest assertions when updates summary text regresses.

         Ties to other methods
         Exercises `DashboardViewModel.sectionSummaryText`.

         Why this exists
         Update posture should report concrete counts instead of generic status text whenever possible.
         */
        let snapshot = try _decodeSnapshot(
            _snapshotJSON(
                ok: true,
                sectionsJSON: """
                [
                  {
                    "key": "updates",
                    "field": "Update status unavailable",
                    "metrics": [
                      ["Updates", "3 available", "warn"],
                      ["First", "macOS 15.4.1-24E123", "info"]
                    ],
                    "table": null,
                    "diagnostics": { "ok": true }
                  }
                ]
                """
            )
        )
        let backend = StaticSnapshotBackend(
            response: BackendSnapshotResponse(snapshot: snapshot, exitCode: 0, stderr: "", rawJSON: nil)
        )
        let model = DashboardViewModel(
            backend: backend,
            sections: [SectionDescriptor(title: "Updates", subtitle: "OS patches", key: "updates")],
            refreshIntervalMs: 1_000,
            fanRefreshIntervalMs: 1_000,
            scrollableRows: [:],
            initialTheme: Theme.fallback(appTitle: "Mac Health Checkup"),
            appTitle: "Mac Health Checkup"
        )

        await model.refreshOnce()

        let summary = model.sectionSummaryText(for: "updates")
        XCTAssertEqual(summary, "Updates: 3 available")
    }

    @MainActor
    func testSectionSummaryTextNormalizesUpToDateToZeroUpdates() async throws {
        /**
         Summary
         Ensure "Up to date" updates metrics are normalized to a concrete zero-count summary.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Updates `DashboardViewModel` published state.

         Error handling
         Fails via XCTest assertions when up-to-date normalization regresses.

         Ties to other methods
         Exercises `DashboardViewModel.sectionSummaryText`.

         Why this exists
         Concrete numbers are easier to compare over time than qualitative phrases.
         */
        let snapshot = try _decodeSnapshot(
            _snapshotJSON(
                ok: true,
                sectionsJSON: """
                [
                  {
                    "key": "updates",
                    "field": "Up to date",
                    "metrics": [
                      ["Updates", "Up to date", "ok"]
                    ],
                    "table": null,
                    "diagnostics": { "ok": true }
                  }
                ]
                """
            )
        )
        let backend = StaticSnapshotBackend(
            response: BackendSnapshotResponse(snapshot: snapshot, exitCode: 0, stderr: "", rawJSON: nil)
        )
        let model = DashboardViewModel(
            backend: backend,
            sections: [SectionDescriptor(title: "Updates", subtitle: "OS patches", key: "updates")],
            refreshIntervalMs: 1_000,
            fanRefreshIntervalMs: 1_000,
            scrollableRows: [:],
            initialTheme: Theme.fallback(appTitle: "Mac Health Checkup"),
            appTitle: "Mac Health Checkup"
        )

        await model.refreshOnce()

        let summary = model.sectionSummaryText(for: "updates")
        XCTAssertEqual(summary, "Updates: 0 available")
    }

    private func _decodeSnapshot(_ json: String) throws -> Snapshot {
        /**
         Summary
         Decode a snapshot JSON fixture into a typed `Snapshot`.

         Inputs
         json: Snapshot JSON text.

         Outputs
         Decoded `Snapshot`.

         Side effects
         None.

         Error handling
         Throws decoding errors for malformed fixtures.

         Ties to other methods
         Used by this test suite to keep fixture setup concise.

         Why this exists
         Round-tripping through JSON matches production decoding behavior.
         */
        try JSONDecoder().decode(Snapshot.self, from: Data(json.utf8))
    }

    private func _snapshotJSON(ok: Bool, sectionsJSON: String) -> String {
        /**
         Summary
         Build a minimally valid snapshot JSON fixture with caller-provided sections.

         Inputs
         ok: Top-level snapshot ok flag.
         sectionsJSON: Raw sections JSON array text.

         Outputs
         Snapshot JSON string.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `_decodeSnapshot` callers in this suite.

         Why this exists
         Shared fixture scaffolding keeps tests focused on behavior under test.
         */
        """
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
              "section_padx": 12,
              "section_pady": 10,
              "auto_refresh_ms": 1000,
              "scrollable_rows": {}
            }
          },
          "section_catalog": [],
          "sections": \(sectionsJSON),
          "ok": \(ok ? "true" : "false"),
          "error": null
        }
        """
    }
}

private struct StaticSnapshotBackend: SnapshotBackend {
    /**
     Summary
     Provide deterministic in-memory snapshot responses for dashboard tests.

     Inputs
     response: Snapshot response returned by backend methods.

     Outputs
     A lightweight backend test double.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Used by `DashboardErrorPresentationTests`.

     Why this exists
     View-model tests should remain deterministic without launching backend processes.
     */

    let response: BackendSnapshotResponse

    func fetchSnapshotResponse() async throws -> BackendSnapshotResponse {
        /**
         Summary
         Return the preconfigured snapshot response.

         Inputs
         None.

         Outputs
         `BackendSnapshotResponse`.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Called by `DashboardViewModel.refreshOnce`.

         Why this exists
         Keeps tests focused on UI mapping logic rather than backend transport mechanics.
         */
        response
    }

    func fetchSectionSnapshotResponse(sectionKey: String) async throws -> BackendSnapshotResponse {
        /**
         Summary
         Return the same preconfigured response for section-level fetches.

         Inputs
         sectionKey: Requested section key.

         Outputs
         `BackendSnapshotResponse`.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Satisfies `SnapshotBackend` protocol requirements.

         Why this exists
         This test double does not need section-specific behavior.
         */
        _ = sectionKey
        return response
    }
}
