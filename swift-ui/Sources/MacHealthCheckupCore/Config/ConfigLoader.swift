import Foundation

public final class ConfigLoader: Sendable {
    /**
     Summary
     Load and decode the central JSON config for the SwiftUI frontend.

     Inputs
     None.

     Outputs
     `AppConfig` instances.

     Side effects
     Reads the config file from disk.

     Error handling
     Throws `AppError` with file and method context on decode or validation failures.

     Ties to other methods
     Used by `AppBootstrap.load` during app startup.

     Why this exists
     Keeps the native UI fully driven by the same config knobs as the Python application.
     */

    public init() {
        /**
         Summary
         Initialize the loader.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by the app bootstrap sequence.

         Why this exists
         Provides an explicit entrypoint for config loading and future dependency injection.
         */
    }

    public func load(from fileURL: URL) throws -> AppConfig {
        /**
         Summary
         Load the JSON config from disk and validate it.

         Inputs
         fileURL: URL to the config file.

         Outputs
         Validated `AppConfig`.

         Side effects
         Reads file contents.

         Error handling
         Throws `AppError` when file reads, decoding, or validation fails.

         Ties to other methods
         Called by `AppBootstrap.load`.

         Why this exists
         Allows the SwiftUI app to share theme and refresh settings with the Python app without duplication.
         */
        do {
            let data = try Data(contentsOf: fileURL)
            let decoder = JSONDecoder()
            let config = try decoder.decode(AppConfig.self, from: data)
            return try config.validated()
        } catch let error as AppError {
            throw error
        } catch {
            throw AppError.context(#fileID, #function, "Failed to load config from \(fileURL.path)", error)
        }
    }
}

