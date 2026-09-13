import Foundation
import MacHealthCheckupCore
import MacHealthCheckupUI
import os

@MainActor
final class MobileAppState: ObservableObject {
    /**
     Summary
     Manage pairing settings and construct a dashboard model for the iOS app.

     Inputs
     None.

     Outputs
     Published state including `DashboardViewModel` and validation errors.

     Side effects
     Reads and writes UserDefaults via `@AppStorage`-backed properties in the view layer.

     Error handling
     Stores validation errors and connection errors as `AppError` values.

     Ties to other methods
     Used by `MobileRootView` to build a `RemoteBackendClient` and a `DashboardViewModel`.

     Why this exists
     Keeps app bootstrapping and pairing logic out of SwiftUI view bodies for clarity and testability.
     */

    @Published var model: DashboardViewModel?
    @Published var lastError: AppError?
    @Published var lastHealthStatus: RemoteHealthStatus?
    @Published var isTestingConnection: Bool = false
    @Published var storedTokenAvailable: Bool = false

    private let tokenStore: any SecureTokenStore
    private let snapshotCache: SnapshotCache?
    private let logger = Logger(subsystem: "MacHealthCheckupMobile", category: "mobile-app-state")

    init(
        tokenStore: any SecureTokenStore = KeychainSecureTokenStore(
            service: Bundle.main.bundleIdentifier ?? "io.github.hydroLB.MacHealthCheckupMobile",
            account: "agent-auth-token"
        ),
        snapshotCache: SnapshotCache? = try? SnapshotCache.default()
    ) {
        /**
         Summary
         Initialize app state with secure token storage and snapshot caching.

         Inputs
         tokenStore: Secure token persistence implementation.
         snapshotCache: Optional snapshot cache instance.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Swallows cache initialization failures because they should not block the app; logs structured warnings.

         Ties to other methods
         Used by `MacHealthCheckupMobileApp` to bootstrap the app.

         Why this exists
         Makes security and performance defaults explicit and injectable.
         */
        self.tokenStore = tokenStore
        self.snapshotCache = snapshotCache
        if snapshotCache == nil {
            logger.warning("snapshot_cache_unavailable event=snapshot_cache_unavailable component=mobile state=disabled")
        }
        _refreshStoredTokenAvailable()
    }

    func refreshStoredTokenAvailable() {
        /**
         Summary
         Refresh the stored-token availability flag.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Reads from secure storage.

         Error handling
         Sets `storedTokenAvailable` to false when secure storage read fails and records an app error.

         Ties to other methods
         Used by views that display token status.

         Why this exists
         Avoids reading Keychain repeatedly from SwiftUI view bodies.
         */
        _refreshStoredTokenAvailable()
    }

    func forgetStoredToken() {
        /**
         Summary
         Delete the stored token from secure storage.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Deletes Keychain state.

         Error handling
         Stores an `AppError` when deletion fails.

         Ties to other methods
         Called by settings and pairing reset actions.

         Why this exists
         Supports safe de-pairing and credential rotation.
         */
        do {
            try tokenStore.deleteToken()
            _refreshStoredTokenAvailable()
            lastError = nil
        } catch {
            lastError = AppError.context(#fileID, #function, "Failed to delete stored token", error)
        }
    }

    func saveToken(_ token: String) {
        /**
         Summary
         Persist a token into secure storage.

         Inputs
         token: Token string.

         Outputs
         None.

         Side effects
         Writes secure storage.

         Error handling
         Stores an `AppError` when secure storage write fails.

         Ties to other methods
         Used by settings and pairing flows.

         Why this exists
         Allows the user to rotate credentials without resetting the entire pairing configuration.
         */
        do {
            let trimmed = token.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty {
                throw AppError.context(#fileID, #function, "Token must be non-empty")
            }
            try tokenStore.saveToken(trimmed)
            _refreshStoredTokenAvailable()
            lastError = nil
        } catch let error as AppError {
            lastError = error
        } catch {
            lastError = AppError.context(#fileID, #function, "Failed to save token", error)
        }
    }

    func connect(agentBaseURL: String, token: String, pinnedCertificateSHA256: String, refreshIntervalMs: Int) {
        /**
         Summary
         Validate pairing settings and create a new dashboard model.

         Inputs
         agentBaseURL: Base URL string such as `http://192.168.1.10:7878`.
         token: Bearer token configured on the Mac agent.
         refreshIntervalMs: Auto-refresh interval in milliseconds.

         Outputs
         None.

         Side effects
         Creates a new `DashboardViewModel` instance.

         Error handling
         Stores an `AppError` in `lastError` when validation fails.

         Ties to other methods
         Called by `PairingView` after user confirmation.

         Why this exists
         Allows a proper iOS client to connect to a Mac agent without embedding macOS-only collectors.
         */
        do {
            let url = try _parseURL(agentBaseURL)
            let tokenToUse = try _resolveToken(typedToken: token)
            if !token.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                try tokenStore.saveToken(tokenToUse)
                _refreshStoredTokenAvailable()
            }

            let remote = RemoteBackendClient(
                config: RemoteBackendConfig(
                    baseURL: url,
                    authToken: tokenToUse,
                    timeoutSeconds: 15,
                    pinnedCertificateSHA256: pinnedCertificateSHA256.trimmingCharacters(in: .whitespacesAndNewlines)
                        .isEmpty ? nil : pinnedCertificateSHA256
                )
            )
            let backend = CachingSnapshotBackend(backend: remote, snapshotCache: snapshotCache, logger: logger)

            var initialTheme = Theme.fallback(appTitle: "Mac Health Checkup")
            var initialTitle = "Mac Health Checkup"
            var initialSections: [SectionDescriptor] = []

            if let snapshotCache, let cached = try? snapshotCache.load() {
                initialTitle = cached.theme.ui.window_title
                initialSections = cached.section_catalog.map { item in
                    SectionDescriptor(title: item.title, subtitle: item.subtitle, key: item.key)
                }
                do {
                    initialTheme = try Theme(snapshot: cached)
                } catch {
                    logger.warning("cached_theme_failed event=cached_theme_failed component=mobile error=\(String(describing: error), privacy: .public)")
                }
            }
            let vm = DashboardViewModel(
                backend: backend,
                sections: initialSections,
                refreshIntervalMs: max(1000, refreshIntervalMs),
                fanRefreshIntervalMs: 5_000,
                scrollableRows: [:],
                initialTheme: initialTheme,
                appTitle: initialTitle
            )
            if let snapshotCache, let cached = try? snapshotCache.load() {
                vm.snapshot = cached
            }
            model = vm
            lastError = nil
        } catch let error as AppError {
            lastError = error
        } catch {
            lastError = AppError.context(#fileID, #function, "Failed to connect", error)
        }
    }

    func testConnection(agentBaseURL: String, token: String, pinnedCertificateSHA256: String) async {
        /**
         Summary
         Validate connectivity to the agent and record a health check result.

         Inputs
         agentBaseURL: Base URL string.
         token: Optional typed token; stored token is used when empty.

         Outputs
         None.

         Side effects
         Performs a network request to `/v1/health` and updates published state.

         Error handling
         Stores an `AppError` into `lastError` on failure.

         Ties to other methods
         Used by pairing and settings views to provide a "Test connection" action.

         Why this exists
         Gives immediate feedback and reduces user frustration during pairing.
         */
        isTestingConnection = true
        defer { isTestingConnection = false }

        do {
            let url = try _parseURL(agentBaseURL)
            let tokenToUse = try _resolveToken(typedToken: token)
            let client = RemoteBackendClient(
                config: RemoteBackendConfig(
                    baseURL: url,
                    authToken: tokenToUse,
                    timeoutSeconds: 10,
                    pinnedCertificateSHA256: pinnedCertificateSHA256.trimmingCharacters(in: .whitespacesAndNewlines)
                        .isEmpty ? nil : pinnedCertificateSHA256
                )
            )
            let health = try await client.fetchHealthStatus()
            lastHealthStatus = health
            lastError = nil
        } catch let error as AppError {
            lastError = error
        } catch {
            lastError = AppError.context(#fileID, #function, "Connection test failed", error)
        }
    }

    func disconnect() {
        /**
         Summary
         Disconnect from the agent by clearing the active dashboard model.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Sets `model` to nil.

         Error handling
         None.

         Ties to other methods
         Called by `MobileRootView` when the user resets pairing settings.

         Why this exists
         Supports re-pairing to a different Mac agent without restarting the app.
         */
        model = nil
    }

    private func _parseURL(_ value: String) throws -> URL {
        /**
         Summary
         Parse a user-provided URL string into a validated URL.

         Inputs
         value: Raw URL string.

         Outputs
         A URL instance.

         Side effects
         None.

         Error handling
         Throws `AppError` when parsing fails or the scheme is unsupported.

         Ties to other methods
         Used by `connect`.

         Why this exists
         Keeps URL validation strict to prevent confusing network failures.
         */
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmed) else {
            throw AppError.context(#fileID, #function, "Invalid agent URL: \(value)")
        }
        let scheme = (url.scheme ?? "").lowercased()
        if scheme != "http" && scheme != "https" {
            throw AppError.context(#fileID, #function, "Agent URL must use http or https")
        }
        return url
    }

    private func _resolveToken(typedToken: String) throws -> String {
        /**
         Summary
         Resolve the token to use from either a typed value or secure storage.

         Inputs
         typedToken: Token value typed by the user, which may be empty.

         Outputs
         Non-empty token string.

         Side effects
         May read from secure storage.

         Error handling
         Throws `AppError` when no token is available.

         Ties to other methods
         Used by `connect` and `testConnection`.

         Why this exists
         Supports a polished UX where the token can be reused without being retyped.
         */
        let trimmed = typedToken.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty {
            return trimmed
        }
        if let stored = try tokenStore.loadToken(), !stored.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return stored
        }
        throw AppError.context(#fileID, #function, "Auth token is required. Enter a token or store one in settings.")
    }

    private func _refreshStoredTokenAvailable() {
        /**
         Summary
         Update the `storedTokenAvailable` flag by reading secure storage.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Reads secure storage and updates published state.

         Error handling
         Sets an `AppError` and disables token-available UX when reads fail.

         Ties to other methods
         Called by init and after token save or delete operations.

         Why this exists
         Centralizes secure storage reads and keeps SwiftUI bodies deterministic.
         */
        do {
            storedTokenAvailable = (try tokenStore.loadToken()) != nil
        } catch {
            storedTokenAvailable = false
            lastError = AppError.context(#fileID, #function, "Failed to read stored token", error)
        }
    }
}

private struct CachingSnapshotBackend: SnapshotBackend {
    /**
     Summary
     Wrap a backend to persist successful snapshots to a local cache.

     Inputs
     backend: Concrete backend implementation.
     snapshotCache: Optional snapshot cache.
     logger: Structured logger for non-fatal cache failures.

     Outputs
     Delegates to the wrapped backend.

     Side effects
     Writes to disk when caching is enabled.

     Error handling
     Never fails the snapshot fetch due to cache write errors; logs warnings instead.

     Ties to other methods
     Used by `MobileAppState.connect`.

     Why this exists
     Improves perceived performance and offline usability without weakening the core refresh path.
     */

    let backend: any SnapshotBackend
    let snapshotCache: SnapshotCache?
    let logger: Logger

    func fetchSnapshotResponse() async throws -> BackendSnapshotResponse {
        /**
         Summary
         Fetch a snapshot and cache it on success.

         Inputs
         None.

         Outputs
         Backend response.

         Side effects
         Writes snapshot to disk when caching is configured.

         Error handling
         Logs cache failures and continues to return the successful snapshot.

         Ties to other methods
         Called by `DashboardViewModel.refreshOnce`.

         Why this exists
         Keeps caching concerns out of the UI model and avoids blocking refresh on disk IO issues.
         */
        let response = try await backend.fetchSnapshotResponse()
        if response.exitCode == 0, response.snapshot.ok, let snapshotCache {
            do {
                try snapshotCache.save(response.snapshot)
            } catch {
                logger.warning("snapshot_cache_write_failed event=snapshot_cache_write_failed component=snapshot_cache error=\(String(describing: error), privacy: .public)")
            }
        }
        return response
    }

    func fetchSectionSnapshotResponse(sectionKey: String) async throws -> BackendSnapshotResponse {
        /**
         Summary
         Fetch a section snapshot without replacing the cached full snapshot.

         Inputs
         sectionKey: Section key requested by the dashboard.

         Outputs
         Backend response containing the requested section payload.

         Side effects
         Delegates network IO to the wrapped backend.

         Error handling
         Propagates backend errors to the dashboard refresh layer.

         Ties to other methods
         Satisfies `SnapshotBackend` and supports the dashboard's higher-frequency fan refresh.

         Why this exists
         A partial section payload must not overwrite the full-snapshot startup cache.
         */
        try await backend.fetchSectionSnapshotResponse(sectionKey: sectionKey)
    }
}
