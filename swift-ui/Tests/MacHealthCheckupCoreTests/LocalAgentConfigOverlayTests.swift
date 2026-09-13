import Foundation
import XCTest
@testable import MacHealthCheckupCore

#if os(macOS)
final class LocalAgentConfigOverlayTests: XCTestCase {
    func testDerivedConfigUsesPrivateDirectoryAndFilePermissions() throws {
        /**
         Summary
         Ensure the generated local-agent config and its directory are private to the current user.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Writes and removes a temporary derived config file.

         Error handling
         Fails through XCTest assertions or propagated filesystem errors.

         Ties to other methods
         Exercises `LocalAgentConfigOverlay.writeDerivedConfig`.

         Why this exists
         The derived config contains a bearer token and must never be group- or world-readable.
         */
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let configFile = root
            .appendingPathComponent(".local", isDirectory: true)
            .appendingPathComponent("agent.json", isDirectory: false)
        defer { try? FileManager.default.removeItem(at: root) }

        try LocalAgentConfigOverlay.writeDerivedConfig(
            ["api": ["auth_token": "private-token"]],
            to: configFile
        )

        let directoryAttributes = try FileManager.default.attributesOfItem(
            atPath: configFile.deletingLastPathComponent().path
        )
        let fileAttributes = try FileManager.default.attributesOfItem(atPath: configFile.path)
        let directoryMode = try XCTUnwrap(
            directoryAttributes[.posixPermissions] as? NSNumber
        ).intValue & 0o777
        let fileMode = try XCTUnwrap(fileAttributes[.posixPermissions] as? NSNumber).intValue & 0o777

        XCTAssertEqual(directoryMode, 0o700)
        XCTAssertEqual(fileMode, 0o600)
    }
}
#endif
