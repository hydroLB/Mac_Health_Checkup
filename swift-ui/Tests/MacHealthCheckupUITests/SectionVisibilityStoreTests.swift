import XCTest
@testable import MacHealthCheckupUI

final class SectionVisibilityStoreTests: XCTestCase {
    @MainActor
    func testSetHiddenPersistsAcrossInstances() throws {
        /**
         Summary
         Ensure hiding a section persists and is observable after reloading.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Writes to an isolated UserDefaults suite.

         Error handling
         Fails via XCTest assertions on unexpected persistence behavior.

         Ties to other methods
         Exercises `SectionVisibilityStore.setHidden` and `SectionVisibilityStore.init`.

         Why this exists
         Visibility settings must survive app restarts to be useful.
         */
        let suiteName = "mac_health_checkup.tests.visibility.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defaults.removePersistentDomain(forName: suiteName)
        let store = SectionVisibilityStore(defaults: defaults)
        store.setHidden(true, key: "battery")
        XCTAssertTrue(store.hiddenSectionKeys.contains("battery"))

        let reloaded = SectionVisibilityStore(defaults: defaults)
        XCTAssertTrue(reloaded.hiddenSectionKeys.contains("battery"))
    }

    @MainActor
    func testResetClearsStoredValue() throws {
        /**
         Summary
         Ensure reset clears hidden keys and persists the cleared state.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Writes to an isolated UserDefaults suite.

         Error handling
         Fails via XCTest assertions on unexpected persistence behavior.

         Ties to other methods
         Exercises `SectionVisibilityStore.reset`.

         Why this exists
         Users need a reliable escape hatch when they hide too much.
         */
        let suiteName = "mac_health_checkup.tests.visibility.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defaults.removePersistentDomain(forName: suiteName)
        let store = SectionVisibilityStore(defaults: defaults)
        store.setHidden(true, key: "devices")
        store.setHidden(true, key: "ports")
        XCTAssertEqual(store.hiddenSectionKeys, ["devices", "ports"])
        store.reset()
        XCTAssertTrue(store.hiddenSectionKeys.isEmpty)

        let reloaded = SectionVisibilityStore(defaults: defaults)
        XCTAssertTrue(reloaded.hiddenSectionKeys.isEmpty)
    }

    @MainActor
    func testInvalidStoredJSONIsCleared() throws {
        /**
         Summary
         Ensure corrupt stored JSON does not crash and is cleared.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Writes to an isolated UserDefaults suite.

         Error handling
         Fails via XCTest assertions on unexpected decode behavior.

         Ties to other methods
         Exercises `SectionVisibilityStore.init` decode path.

         Why this exists
         An app should remain usable even if preferences become corrupted.
         */
        let suiteName = "mac_health_checkup.tests.visibility.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defaults.removePersistentDomain(forName: suiteName)
        defaults.set("{not json", forKey: SectionVisibilityStore.defaultsKey)
        let store = SectionVisibilityStore(defaults: defaults)
        XCTAssertTrue(store.hiddenSectionKeys.isEmpty)
        XCTAssertNil(defaults.string(forKey: SectionVisibilityStore.defaultsKey))
    }
}
