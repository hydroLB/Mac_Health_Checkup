import Foundation
import SwiftUI
import MacHealthCheckupCore
import MacHealthCheckupUI

enum AppBootstrap {
    /**
     Summary
     Bootstrap the SwiftUI app by loading config and building dependencies.

     Inputs
     None.

     Outputs
     A tuple of (theme, view model) for the root view.

     Side effects
     Reads config from disk and resolves environment overrides.

     Error handling
     Throws `AppError` with source context when bootstrap fails.

     Ties to other methods
     Used by `MacHealthCheckupApp` main entrypoint.

     Why this exists
     Keeps startup logic out of SwiftUI view bodies and makes failures easier to diagnose.
     */

    @MainActor
    static func load() throws -> (Theme, DashboardViewModel, String) {
        /**
         Summary
         Load config and initialize runtime dependencies.

         Inputs
         None.

         Outputs
         Theme and dashboard view model.

         Side effects
         Reads config file and inspects process arguments and environment variables.

         Error handling
         Throws `AppError` when parsing CLI args or loading config fails.

         Ties to other methods
         Called by `MacHealthCheckupApp` init.

         Why this exists
         Ensures startup failures occur before the UI is presented.
         */
        let args = try AppLaunchArgs.parse(CommandLine.arguments)
        let paths = try ConfigPaths.resolve(configPathOverride: args.configPath, repoRootOverride: args.repoRoot)
        let config = try ConfigLoader().load(from: paths.configFile)
        let theme = try Theme(config: config)

        let runtime = try BackendRuntimeConfig.from(
            config: config,
            repoRoot: paths.repoRoot,
            pythonOverride: args.python
        )
        let backend = LocalAgentBackendClient(runtime: runtime, baseConfigFile: paths.configFile)
        let sections = try SectionCatalog.fromConfig(config)
        let snapshotCacheFile = paths.repoRoot.appendingPathComponent(".local/last_snapshot.json", isDirectory: false)
        let historyFile = paths.repoRoot.appendingPathComponent(".local/metric_history.json", isDirectory: false)
        let historyEnabled = config.gui.history_enabled ?? true
        let historyRetentionMinutes = config.gui.history_retention_minutes ?? 60
        let historyMaxPoints = config.gui.history_max_points_per_series ?? 3600
        let historySaveIntervalSeconds = config.gui.history_save_interval_sec ?? 10
        let fanRefreshIntervalMs = config.gui.fans_refresh_ms ?? 5000
        let model = DashboardViewModel(
            backend: backend,
            sections: sections,
            refreshIntervalMs: config.gui.auto_refresh_ms,
            fanRefreshIntervalMs: fanRefreshIntervalMs,
            scrollableRows: config.gui.scrollable_rows,
            backendTimeoutSeconds: runtime.timeoutSeconds,
            snapshotCacheFile: snapshotCacheFile,
            historyFile: historyFile,
            historyEnabled: historyEnabled,
            historyRetentionMinutes: historyRetentionMinutes,
            historyMaxPointsPerSeries: historyMaxPoints,
            historySaveIntervalSeconds: historySaveIntervalSeconds,
            initialTheme: theme,
            appTitle: config.ui.window_title
        )
        return (theme, model, config.ui.window_title)
    }
}
