import Foundation
import MacHealthCheckupCore

public struct AppLaunchArgs: Sendable {
    /**
     Summary
     Parse and store launch arguments for the SwiftUI executable.

     Inputs
     configPath: Optional config file path.
     repoRoot: Optional repo root path.
     python: Optional python executable path.

     Outputs
     Parsed launch arguments.

     Side effects
     None.

     Error handling
     Throws `AppError` when arguments are malformed.

     Ties to other methods
     Used by `AppBootstrap.load`.

     Why this exists
     Provides explicit overrides without adding external argument parsing dependencies.
     */

    public let configPath: String?
    public let repoRoot: String?
    public let python: String?

    public static func parse(_ argv: [String]) throws -> AppLaunchArgs {
        /**
         Summary
         Parse simple `--key value` arguments.

         Inputs
         argv: Raw `CommandLine.arguments`.

         Outputs
         Parsed `AppLaunchArgs`.

         Side effects
         None.

         Error handling
         Throws `AppError` when flags are unknown or missing values.

         Ties to other methods
         Used by `AppBootstrap.load`.

         Why this exists
         Keeps startup deterministic and avoids silent misconfiguration.
         */
        var configPath: String?
        var repoRoot: String?
        var python: String?

        var i = 1
        while i < argv.count {
            let arg = argv[i]
            func requireValue() throws -> String {
                if i + 1 >= argv.count {
                    throw AppError.context(#fileID, #function, "Missing value for \(arg)")
                }
                return argv[i + 1]
            }

            switch arg {
            case "--":
                return AppLaunchArgs(configPath: configPath, repoRoot: repoRoot, python: python)
            case "--config":
                configPath = try requireValue()
                i += 2
            case "--repo-root":
                repoRoot = try requireValue()
                i += 2
            case "--python":
                python = try requireValue()
                i += 2
            case "--help":
                print("Usage: mac-health-checkup-ui [--config PATH] [--repo-root PATH] [--python PATH]")
                i += 1
            default:
                throw AppError.context(#fileID, #function, "Unknown argument: \(arg)")
            }
        }

        return AppLaunchArgs(configPath: configPath, repoRoot: repoRoot, python: python)
    }
}
