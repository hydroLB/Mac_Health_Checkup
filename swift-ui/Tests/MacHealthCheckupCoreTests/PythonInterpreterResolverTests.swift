import XCTest
@testable import MacHealthCheckupCore

#if os(macOS)

final class PythonInterpreterResolverTests: XCTestCase {
    func testResolveUsesOverrideWhenValid() throws {
        /**
         Summary
         Ensure an explicit override wins when it is executable and meets the minimum version.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Creates a temporary executable file.

         Error handling
         Fails via XCTest assertions when resolution returns an unexpected path.

         Ties to other methods
         Exercises `PythonInterpreterResolver.resolve`.

         Why this exists
         Overrides are a key escape hatch when the default discovery does not match a user's environment.
         */
        let tempDir = try makeTempDir()
        let overridePython = tempDir.appendingPathComponent("python-override")
        try writeExecutableStub(at: overridePython)

        let resolved = try PythonInterpreterResolver.resolve(
            pythonOverride: overridePython.path,
            environment: [:],
            requiredMinimum: PythonVersion(major: 3, minor: 11, patch: 0),
            fallbackCandidates: [],
            versionProbe: { _ in PythonVersion(major: 3, minor: 11, patch: 2) }
        )

        XCTAssertEqual(resolved.path, overridePython.path)
    }

    func testResolveFailsWhenOverrideTooOldEvenIfFallbackValid() throws {
        /**
         Summary
         Ensure explicit overrides are treated as authoritative and do not silently fall back.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Creates temporary executable files.

         Error handling
         Fails via XCTest assertions when no error is thrown or message is not actionable.

         Ties to other methods
         Exercises `PythonInterpreterResolver.resolve`.

         Why this exists
         Silent fallback can mask misconfiguration and make troubleshooting harder for users.
         */
        let tempDir = try makeTempDir()
        let overridePython = tempDir.appendingPathComponent("python-override-old")
        let fallbackPython = tempDir.appendingPathComponent("python-fallback-good")
        try writeExecutableStub(at: overridePython)
        try writeExecutableStub(at: fallbackPython)

        do {
            _ = try PythonInterpreterResolver.resolve(
                pythonOverride: overridePython.path,
                environment: [:],
                requiredMinimum: PythonVersion(major: 3, minor: 11, patch: 0),
                fallbackCandidates: [fallbackPython.path],
                versionProbe: { path in
                    if path == overridePython.path {
                        return PythonVersion(major: 3, minor: 9, patch: 18)
                    }
                    return PythonVersion(major: 3, minor: 11, patch: 0)
                }
            )
            XCTFail("Expected resolver to throw for an invalid explicit override")
        } catch let error as AppError {
            XCTAssertTrue(error.description.contains("Invalid Python override"))
        }
    }

    func testResolveFallsBackWhenNoOverrides() throws {
        /**
         Summary
         Ensure fallback candidates are used when no overrides are provided.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Creates a temporary executable file.

         Error handling
         Fails via XCTest assertions when the resolver does not choose the expected fallback.

         Ties to other methods
         Exercises `PythonInterpreterResolver.resolve`.

         Why this exists
         The macOS app should "just work" without requiring users to set environment variables.
         */
        let tempDir = try makeTempDir()
        let fallbackPython = tempDir.appendingPathComponent("python-fallback")
        try writeExecutableStub(at: fallbackPython)

        let resolved = try PythonInterpreterResolver.resolve(
            pythonOverride: nil,
            environment: [:],
            requiredMinimum: PythonVersion(major: 3, minor: 11, patch: 0),
            fallbackCandidates: [fallbackPython.path],
            versionProbe: { _ in PythonVersion(major: 3, minor: 12, patch: 1) }
        )

        XCTAssertEqual(resolved.path, fallbackPython.path)
    }

    private func makeTempDir() throws -> URL {
        /**
         Summary
         Create a unique temporary directory for test artifacts.

         Inputs
         None.

         Outputs
         URL to the created directory.

         Side effects
         Writes to the system temporary directory.

         Error handling
         Throws if directory creation fails.

         Ties to other methods
         Used by tests in this file.

         Why this exists
         Keeps test artifacts isolated and avoids relying on system interpreter paths.
         */
        let base = FileManager.default.temporaryDirectory
        let dir = base.appendingPathComponent("mac-health-checkup-tests-\(UUID().uuidString)", isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            return dir
        } catch {
            throw AppError.context(#fileID, #function, "Failed to create temporary directory", error)
        }
    }

    private func writeExecutableStub(at url: URL) throws {
        /**
         Summary
         Write a small executable file so `isExecutableFile(atPath:)` can validate candidates.

         Inputs
         url: Destination file URL.

         Outputs
         None.

         Side effects
         Writes a file to disk and sets executable permissions.

         Error handling
         Throws when writing or chmod fails.

         Ties to other methods
         Used by tests that exercise the resolver.

         Why this exists
         Resolver selection checks executability before probing; tests must be hermetic and deterministic.
         */
        let contents = "#!/bin/sh\nexit 0\n"
        do {
            guard let data = contents.data(using: .utf8) else {
                throw AppError.context(#fileID, #function, "Failed to encode executable stub as UTF-8")
            }
            try data.write(to: url, options: [.atomic])
        } catch {
            throw AppError.context(#fileID, #function, "Failed to write executable stub to \(url.path)", error)
        }

        do {
            try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: url.path)
        } catch {
            throw AppError.context(#fileID, #function, "Failed to mark stub executable at \(url.path)", error)
        }
    }
}

#endif
