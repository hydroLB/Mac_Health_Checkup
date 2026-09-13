import Foundation
import XCTest
@testable import MacHealthCheckupCore
@testable import MacHealthCheckupUI

final class DashboardViewModelHelpersTests: XCTestCase {
    func testRefreshSchedulerReturnsFalseWhenWaitIsCancelled() async {
        let waitTask = Task {
            await DashboardRefreshScheduler.wait(milliseconds: 10_000)
        }
        await Task.yield()
        waitTask.cancel()

        let completed = await waitTask.value
        XCTAssertFalse(completed)
    }

    func testSnapshotResponsePolicyCachesOnlyFullySuccessfulSnapshots() throws {
        let healthy = try _decodeSnapshot(_snapshotJSON(ok: true, sectionsJSON: "[]"))
        let failed = try _decodeSnapshot(_snapshotJSON(ok: false, sectionsJSON: "[]"))

        XCTAssertTrue(
            DashboardSnapshotResponsePolicy.shouldCacheFullSnapshot(
                BackendSnapshotResponse(snapshot: healthy, exitCode: 0, stderr: "", rawJSON: "{}")
            )
        )
        XCTAssertFalse(
            DashboardSnapshotResponsePolicy.shouldCacheFullSnapshot(
                BackendSnapshotResponse(snapshot: healthy, exitCode: 1, stderr: "", rawJSON: "{}")
            )
        )
        XCTAssertFalse(
            DashboardSnapshotResponsePolicy.shouldCacheFullSnapshot(
                BackendSnapshotResponse(snapshot: failed, exitCode: 0, stderr: "", rawJSON: "{}")
            )
        )
    }

    func testSnapshotResponsePolicyRejectsFailedSectionPayload() throws {
        let failed = try _decodeSnapshot(
            _snapshotJSON(
                ok: false,
                sectionsJSON: """
                [
                  { "key": "fan", "field": "failed", "metrics": null, "table": null, "diagnostics": { "ok": false } }
                ]
                """
            )
        )
        let response = BackendSnapshotResponse(
            snapshot: failed,
            exitCode: 1,
            stderr: "fan failed",
            rawJSON: nil
        )

        XCTAssertNil(DashboardSnapshotResponsePolicy.acceptedSection(from: response, key: "fan"))
    }

    func testThemeResolverBuildsThemeFromSnapshot() throws {
        let snapshot = try _decodeSnapshot(
            _snapshotJSON(
                ok: true,
                sectionsJSON: """
                [
                  { "key": "battery", "field": "Battery nominal", "metrics": [["Health", "Normal", "ok"]], "table": null, "diagnostics": null }
                ]
                """
            )
        )

        let theme = try DashboardSnapshotThemeResolver.theme(
            from: snapshot,
            file: "DashboardViewModel.swift",
            function: "_applyThemeIfAvailable"
        )

        XCTAssertEqual(theme.layout.pagePadding, 12)
    }

    func testThemeResolverPreservesActionableThemeDecodingFailure() throws {
        let snapshot = try _decodeSnapshot(
            _snapshotJSON(
                ok: true,
                sectionsJSON: """
                []
                """,
                themeColorsJSON: """
                {
                  "bg": "not-a-color",
                  "fg": "#ffffff",
                  "ok": "#2ecc40",
                  "warn": "#ffdc00",
                  "bad": "#ff4136",
                  "section": "#339af0",
                  "label": "#f1c40f",
                  "field": "#daf6ff"
                }
                """
            )
        )

        XCTAssertThrowsError(
            try DashboardSnapshotThemeResolver.theme(
                from: snapshot,
                file: "DashboardViewModel.swift",
                function: "_applyThemeIfAvailable"
            )
        ) { error in
            let appError = error as? AppError
            XCTAssertNotNil(appError)
            XCTAssertEqual(appError?.userFacingMessage, "Invalid hex color: not-a-color")
        }
    }

    func testCatalogMapperReturnsNilWhenSnapshotCatalogIsEmpty() throws {
        let snapshot = try _decodeSnapshot(
            _snapshotJSON(
                ok: true,
                sectionsJSON: """
                []
                """
            )
        )

        XCTAssertNil(DashboardSnapshotCatalogMapper.sections(from: snapshot))
    }

    func testCatalogMapperBuildsSectionDescriptorsFromSnapshotCatalog() throws {
        let snapshot = try _decodeSnapshot(
            _snapshotJSON(
                ok: true,
                sectionsJSON: """
                []
                """,
                sectionCatalogJSON: """
                [
                  { "title": "Battery", "subtitle": "Power health", "key": "battery" },
                  { "title": "Network", "subtitle": "Connectivity", "key": "network" }
                ]
                """
            )
        )

        let sections = try XCTUnwrap(DashboardSnapshotCatalogMapper.sections(from: snapshot))
        XCTAssertEqual(sections.map(\.key), ["battery", "network"])
        XCTAssertEqual(sections.map(\.title), ["Battery", "Network"])
    }

    func testSnapshotCacheLoadReturnsDecodedValidatedSnapshot() throws {
        let directory = try _makeTemporaryDirectory()
        let fileURL = directory.appendingPathComponent("snapshot.json")
        let rawJSON = _snapshotJSON(
            ok: true,
            sectionsJSON: """
            [
              { "key": "battery", "field": "Battery nominal", "metrics": [["Health", "Normal", "ok"]], "table": null, "diagnostics": null }
            ]
            """,
            sectionCatalogJSON: """
            [
              { "title": "Battery", "subtitle": "Power health", "key": "battery" }
            ]
            """
        )

        try rawJSON.write(to: fileURL, atomically: true, encoding: .utf8)
        let snapshot = try XCTUnwrap(DashboardSnapshotCache.loadSnapshotIfAvailable(at: fileURL))

        XCTAssertEqual(snapshot.sections.map(\.key), ["battery"])
        XCTAssertEqual(snapshot.section_catalog.map(\.key), ["battery"])
    }

    func testSnapshotCacheLoadReturnsNilForMissingAndEmptyFiles() throws {
        let directory = try _makeTemporaryDirectory()
        let missingFile = directory.appendingPathComponent("missing.json")
        XCTAssertNil(try DashboardSnapshotCache.loadSnapshotIfAvailable(at: missingFile))

        let emptyFile = directory.appendingPathComponent("empty.json")
        try "".write(to: emptyFile, atomically: true, encoding: .utf8)
        XCTAssertNil(try DashboardSnapshotCache.loadSnapshotIfAvailable(at: emptyFile))
    }

    func testSnapshotCacheWriteCreatesParentDirectoryAndAppendsTrailingNewline() throws {
        let directory = try _makeTemporaryDirectory()
        let fileURL = directory
            .appendingPathComponent("nested")
            .appendingPathComponent("snapshot.json")
        let rawJSON = _snapshotJSON(ok: true, sectionsJSON: "[]")

        let wrote = try DashboardSnapshotCache.writeSnapshotIfPossible(rawJSON: rawJSON, to: fileURL)
        let contents = try String(contentsOf: fileURL, encoding: .utf8)
        let attributes = try FileManager.default.attributesOfItem(atPath: fileURL.path)
        let permissions = try XCTUnwrap(attributes[.posixPermissions] as? NSNumber)

        XCTAssertTrue(wrote)
        XCTAssertTrue(contents.hasSuffix("\n"))
        XCTAssertEqual(permissions.intValue & 0o777, 0o600)
    }

    func testSnapshotCacheWriteSkipsNilAndBlankJSON() throws {
        let directory = try _makeTemporaryDirectory()
        let fileURL = directory.appendingPathComponent("snapshot.json")

        XCTAssertFalse(try DashboardSnapshotCache.writeSnapshotIfPossible(rawJSON: nil, to: fileURL))
        XCTAssertFalse(try DashboardSnapshotCache.writeSnapshotIfPossible(rawJSON: "   \n", to: fileURL))
        XCTAssertFalse(FileManager.default.fileExists(atPath: fileURL.path))
    }

    func testSidebarSectionsFiltersHiddenSectionsAndMatchesSearchText() {
        let sections = [
            SectionDescriptor(title: "Battery", subtitle: "Power health", key: "battery"),
            SectionDescriptor(title: "Fan", subtitle: "Cooling", key: "fan"),
            SectionDescriptor(title: "Network", subtitle: "Connectivity", key: "network"),
        ]

        let sidebarSections = DashboardSectionNavigation.sidebarSections(
            from: sections,
            overviewKey: DashboardViewModel.overviewKey,
            searchText: "pow",
            isSectionHidden: { $0 == "fan" }
        )

        XCTAssertEqual(sidebarSections.map(\.key), [DashboardViewModel.overviewKey, "battery"])
    }

    func testNormalizedSelectedSectionFallsBackToOverviewWhenHidden() {
        let sections = [
            SectionDescriptor(title: "Battery", subtitle: "Power health", key: "battery"),
            SectionDescriptor(title: "Fan", subtitle: "Cooling", key: "fan"),
        ]

        let normalized = DashboardSectionNavigation.normalizedSelectedSectionKey(
            selectedSectionKey: "fan",
            overviewKey: DashboardViewModel.overviewKey,
            sections: sections,
            isSectionHidden: { $0 == "fan" }
        )

        XCTAssertEqual(normalized, DashboardViewModel.overviewKey)
    }

    func testBackendWarningIncludesTrimmedTruncatedStderrWhenSnapshotHasNoFailedSections() throws {
        let snapshot = try _decodeSnapshot(
            _snapshotJSON(
                ok: false,
                sectionsJSON: """
                [
                  { "key": "battery", "field": "Battery nominal", "metrics": [["Health", "Normal", "ok"]], "table": null, "diagnostics": null }
                ]
                """
            )
        )

        let stderr = String(repeating: "x", count: 300)
        let warning = DashboardBackendWarningFormatter.warning(
            exitCode: 2,
            snapshot: snapshot,
            stderr: "  \(stderr)  ",
            file: "DashboardViewModel.swift",
            function: "refreshOnce()"
        )

        let message = try XCTUnwrap(warning?.description)
        XCTAssertTrue(message.contains("Backend completed with warnings (exit code 2)."))
        XCTAssertTrue(message.contains("Snapshot reported ok=false."))
        XCTAssertTrue(message.contains("stderr="))
        XCTAssertTrue(message.contains("…"))
    }

    private func _decodeSnapshot(_ json: String) throws -> Snapshot {
        try JSONDecoder().decode(Snapshot.self, from: Data(json.utf8))
    }

    private func _makeTemporaryDirectory() throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock {
            try? FileManager.default.removeItem(at: directory)
        }
        return directory
    }

    private func _snapshotJSON(
        ok: Bool,
        sectionsJSON: String,
        themeColorsJSON: String = """
        {
          "bg": "#23272e",
          "fg": "#ffffff",
          "ok": "#2ecc40",
          "warn": "#ffdc00",
          "bad": "#ff4136",
          "section": "#339af0",
          "label": "#f1c40f",
          "field": "#daf6ff"
        }
        """,
        sectionCatalogJSON: String = "[]"
    ) -> String {
        """
        {
          "schema_version": 2,
          "generated_at_unix_ms": 1700000000000,
          "theme": {
            "ui": { "window_title": "Mac Health Checkup" },
            "colors": \(themeColorsJSON),
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
          "ok": \(ok ? "true" : "false"),
          "error": null,
          "sections": \(sectionsJSON),
          "section_catalog": \(sectionCatalogJSON)
        }
        """
    }
}
