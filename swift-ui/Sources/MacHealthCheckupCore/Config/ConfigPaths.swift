import Foundation

public struct ConfigPaths: Sendable {
    /**
     Summary
     Resolve config-related filesystem paths for the SwiftUI frontend.

     Inputs
     configPathOverride: Optional path override from CLI args.
     repoRootOverride: Optional repo root override from CLI args.

     Outputs
     A set of resolved paths for config loading and backend execution.

     Side effects
     Reads process environment variables.

     Error handling
     Throws `AppError` when required paths cannot be resolved.

     Ties to other methods
     Used by `AppBootstrap.load` to locate `config/config.json` and set the backend working directory.

     Why this exists
     Keeps path resolution deterministic and configurable without code changes.
     */

    public let repoRoot: URL
    public let configFile: URL

    public static func resolve(configPathOverride: String?, repoRootOverride: String?) throws -> ConfigPaths {
        /**
         Summary
         Resolve the repo root and config file paths.

         Inputs
         configPathOverride: Optional config path.
         repoRootOverride: Optional repo root path.

         Outputs
         `ConfigPaths` containing resolved URLs.

         Side effects
         Reads `ProcessInfo.processInfo.environment`.

         Error handling
         Throws `AppError` for invalid inputs or missing files.

         Ties to other methods
         Consumed by `ConfigLoader.load`.

         Why this exists
         Ensures the frontend can be launched from different working directories reliably.
         */
        let env = ProcessInfo.processInfo.environment

        let repoRootStr = repoRootOverride
            ?? env["MAC_HEALTH_CHECKUP_REPO_ROOT"]
            ?? FileManager.default.currentDirectoryPath

        let repoRoot = URL(fileURLWithPath: repoRootStr, isDirectory: true)
        let configStr = configPathOverride ?? env["MAC_HEALTH_CHECKUP_CONFIG"]
        let configFile = if let configStr {
            URL(fileURLWithPath: configStr, isDirectory: false)
        } else {
            repoRoot.appendingPathComponent("config/config.json", isDirectory: false)
        }

        guard FileManager.default.fileExists(atPath: configFile.path) else {
            throw AppError.context(#fileID, #function, "Config file not found at \(configFile.path)")
        }

        return ConfigPaths(repoRoot: repoRoot, configFile: configFile)
    }
}

