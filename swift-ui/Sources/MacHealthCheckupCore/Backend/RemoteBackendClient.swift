import Foundation

public struct RemoteBackendConfig: Sendable {
    /**
     Summary
     Configure remote snapshot fetching from a Mac agent API.

     Inputs
     baseURL: HTTPS agent URL, or an HTTP URL when the host is loopback.
     authToken: Bearer token for `/v1/snapshot`.
     timeoutSeconds: Request timeout.
     pinnedCertificateSHA256: SHA-256 leaf certificate fingerprint; required for non-loopback HTTPS.

     Outputs
     Immutable configuration for `RemoteBackendClient`.

     Side effects
     None.

     Error handling
     Throws `AppError` via `validated()` when values are invalid.

     Ties to other methods
     Used by `RemoteBackendClient.fetchSnapshotResponse`.

     Why this exists
     Keeps pairing and connectivity knobs centralized for the iOS app.
     */

    public let baseURL: URL
    public let authToken: String
    public let timeoutSeconds: TimeInterval
    public let pinnedCertificateSHA256: String?

    public init(
        baseURL: URL,
        authToken: String,
        timeoutSeconds: TimeInterval,
        pinnedCertificateSHA256: String? = nil
    ) {
        /**
         Summary
         Initialize remote backend configuration.

         Inputs
         baseURL: HTTPS agent URL, or an HTTP URL when the host is loopback.
         authToken: Bearer token for `/v1/snapshot`.
         timeoutSeconds: Request timeout.
         pinnedCertificateSHA256: SHA-256 leaf certificate fingerprint; required for non-loopback HTTPS.

         Outputs
         None.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `RemoteBackendClient` initialization and by pairing/settings flows.

         Why this exists
         Preserves a stable initializer surface while adding optional certificate pinning.
         */
        self.baseURL = baseURL
        self.authToken = authToken
        self.timeoutSeconds = timeoutSeconds
        self.pinnedCertificateSHA256 = pinnedCertificateSHA256
    }

    public func validated() throws -> RemoteBackendConfig {
        /**
         Summary
         Validate remote backend configuration values.

         Inputs
         None.

         Outputs
         The same `RemoteBackendConfig` when validation succeeds.

         Side effects
         None.

         Error handling
         Throws `AppError` when baseURL or token is invalid.

         Ties to other methods
         Called by `RemoteBackendClient.fetchSnapshotResponse`.

         Why this exists
         Prevents confusing runtime failures caused by malformed URLs or missing tokens.
         */
        if authToken.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            throw AppError.context(#fileID, #function, "Remote auth token must be non-empty")
        }
        if timeoutSeconds <= 0 || timeoutSeconds > 120 {
            throw AppError.context(#fileID, #function, "timeoutSeconds out of range: \(timeoutSeconds)")
        }
        guard let scheme = baseURL.scheme?.lowercased(), scheme == "http" || scheme == "https" else {
            throw AppError.context(#fileID, #function, "Remote base URL must use http or https")
        }
        guard let host = baseURL.host, !host.isEmpty else {
            throw AppError.context(#fileID, #function, "Remote base URL must include a host")
        }
        let isLoopback = Self._isLoopbackHost(host)
        if scheme == "http" && !isLoopback {
            throw AppError.context(#fileID, #function, "Remote HTTP is allowed only for loopback hosts")
        }
        if scheme == "https" && !isLoopback && pinnedCertificateSHA256 == nil {
            throw AppError.context(
                #fileID,
                #function,
                "Remote HTTPS requires a pinned certificate fingerprint for non-loopback hosts"
            )
        }
        if let pin = pinnedCertificateSHA256 {
            let normalized = try CertificatePinning.normalizedSHA256Fingerprint(pin)
            return RemoteBackendConfig(
                baseURL: baseURL,
                authToken: authToken,
                timeoutSeconds: timeoutSeconds,
                pinnedCertificateSHA256: normalized
            )
        }
        return self
    }

    private static func _isLoopbackHost(_ host: String) -> Bool {
        /**
         Summary
         Determine whether a URL host is an explicit loopback name or address.

         Inputs
         host: Host value produced by `URL` parsing.

         Outputs
         True for localhost, IPv6 loopback, or an IPv4 address in 127.0.0.0/8.

         Side effects
         None.

         Error handling
         Returns false for malformed or non-loopback hosts.

         Ties to other methods
         Used by `validated()` before allowing bearer-token transport over plain HTTP.

         Why this exists
         Bearer tokens may use HTTP for local development, but must not cross a network in plaintext.
         */
        let normalized = host.lowercased()
        if normalized == "localhost" || normalized == "localhost." || normalized == "::1" {
            return true
        }

        let components = normalized.split(separator: ".", omittingEmptySubsequences: false)
        guard components.count == 4 else {
            return false
        }
        guard let first = UInt8(components[0]), first == 127 else {
            return false
        }
        return components.dropFirst().allSatisfy { UInt8($0) != nil }
    }
}

public final class RemoteBackendClient: SnapshotBackend, Sendable {
    /**
     Summary
     Fetch dashboard snapshots from a Mac agent API over HTTP or HTTPS.

     Inputs
     config: Remote backend configuration.

     Outputs
     `BackendSnapshotResponse` values containing decoded snapshots.

     Side effects
     Performs network requests.

     Error handling
     Throws `AppError` when the request fails or JSON cannot be decoded.

     Ties to other methods
     Used by the iOS app to fetch snapshots from a Mac running `python -m mac_health_checkup --serve`.

     Why this exists
     iOS cannot run the macOS diagnostics collectors locally; this provides a proper native iOS client.
     */

    private let config: RemoteBackendConfig
    private let session: URLSession

    public init(config: RemoteBackendConfig, session: URLSession = .shared) {
        /**
         Summary
         Initialize the remote client.

         Inputs
         config: Remote backend configuration.
         session: URLSession instance for requests.

         Outputs
         None.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used during app bootstrap and settings updates.

         Why this exists
         Keeps the client dependency injectable for tests.
         */
        self.config = config
        if let pin = config.pinnedCertificateSHA256, session === URLSession.shared {
            self.session = CertificatePinning.pinnedSession(expectedLeafCertificateSHA256: pin)
        } else {
            self.session = session
        }
    }

    public func fetchHealthStatus() async throws -> RemoteHealthStatus {
        /**
         Summary
         Perform a lightweight unauthenticated health check against the agent.

         Inputs
         None.

         Outputs
         `RemoteHealthStatus` describing the HTTP status and round-trip time.

         Side effects
         Performs a network request.

         Error handling
         Throws `AppError` when the request fails or returns a non-2xx response.

         Ties to other methods
         Used by pairing flows to verify connectivity before fetching a snapshot.

         Why this exists
         Provides a fast, low-risk way to validate base URL reachability without leaking token details.
         */
        let validated = try config.validated()
        let url = _url(for: validated, path: "v1/health")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = validated.timeoutSeconds
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.cachePolicy = .reloadIgnoringLocalCacheData

        let clock = ContinuousClock()
        let startedAt = clock.now
        do {
            let (_, response) = try await session.data(for: request)
            let http = response as? HTTPURLResponse
            let status = Int32(http?.statusCode ?? -1)
            if status < 200 || status >= 300 {
                throw AppError.context(#fileID, #function, "Remote health HTTP \(status)")
            }
            let elapsed = startedAt.duration(to: clock.now)
            let roundTripMs = elapsed.components.seconds * 1000 + elapsed.components.attoseconds / 1_000_000_000_000_000
            return RemoteHealthStatus(httpStatus: status, roundTripMs: roundTripMs)
        } catch let error as AppError {
            throw error
        } catch {
            throw AppError.context(#fileID, #function, "Failed to fetch remote health", error)
        }
    }

    public func fetchSnapshotResponse() async throws -> BackendSnapshotResponse {
        /**
         Summary
         Fetch a snapshot from the remote agent and decode it.

         Inputs
         None.

         Outputs
         A `BackendSnapshotResponse` containing a validated snapshot.

         Side effects
         Performs a network request.

         Error handling
         Throws `AppError` when the request fails, returns a non-2xx response, or JSON decoding fails.

         Ties to other methods
         Called by `DashboardViewModel.refreshOnce`.

         Why this exists
         Provides a single consistent data source for the iOS app UI.
         */
        let validated = try config.validated()
        let url = _url(for: validated, path: "v1/snapshot")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = validated.timeoutSeconds
        request.setValue("Bearer \(validated.authToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.cachePolicy = .reloadIgnoringLocalCacheData

        do {
            let (data, response) = try await session.data(for: request)
            let http = response as? HTTPURLResponse
            let status = Int32(http?.statusCode ?? -1)
            if status < 200 || status >= 300 {
                let body = String(data: data, encoding: .utf8) ?? ""
                throw AppError.context(#fileID, #function, "Remote snapshot HTTP \(status). body=\(body)")
            }
            let backendExit = http?.value(forHTTPHeaderField: "X-Snapshot-Exit-Code")
            let parsedExit = backendExit.flatMap { Int32($0.trimmingCharacters(in: .whitespacesAndNewlines)) }
            let snapshot = try JSONDecoder().decode(Snapshot.self, from: data)
            let checked = try snapshot.validated()
            let effectiveExit = parsedExit ?? (checked.ok ? 0 : 1)
            return BackendSnapshotResponse(
                snapshot: checked,
                exitCode: effectiveExit,
                stderr: "",
                rawJSON: String(data: data, encoding: .utf8)
            )
        } catch let error as AppError {
            throw error
        } catch {
            throw AppError.context(#fileID, #function, "Failed to fetch remote snapshot", error)
        }
    }

    public func fetchSectionSnapshotResponse(sectionKey: String) async throws -> BackendSnapshotResponse {
        /**
         Summary
         Fetch a single-section snapshot from the remote agent and decode it.

         Inputs
         sectionKey: Section key to fetch (example: "fan").

         Outputs
         A `BackendSnapshotResponse` containing a validated snapshot with a subset of sections.

         Side effects
         Performs a network request.

         Error handling
         Throws `AppError` when the request fails, returns a non-2xx response, or JSON decoding fails.

         Ties to other methods
         Called by `DashboardViewModel` for higher-frequency fan refreshes.

         Why this exists
         Some sections update more frequently than the full dashboard; fetching a subset reduces backend work and improves responsiveness.
         */
        let validated = try config.validated()
        let url = try _url(
            for: validated,
            path: "v1/section",
            queryItems: [URLQueryItem(name: "key", value: sectionKey)]
        )
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = validated.timeoutSeconds
        request.setValue("Bearer \(validated.authToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.cachePolicy = .reloadIgnoringLocalCacheData

        do {
            let (data, response) = try await session.data(for: request)
            let http = response as? HTTPURLResponse
            let status = Int32(http?.statusCode ?? -1)
            if status < 200 || status >= 300 {
                let body = String(data: data, encoding: .utf8) ?? ""
                throw AppError.context(#fileID, #function, "Remote section HTTP \(status). body=\(body)")
            }
            let backendExit = http?.value(forHTTPHeaderField: "X-Snapshot-Exit-Code")
            let parsedExit = backendExit.flatMap { Int32($0.trimmingCharacters(in: .whitespacesAndNewlines)) }
            let snapshot = try JSONDecoder().decode(Snapshot.self, from: data)
            let checked = try snapshot.validated()
            let effectiveExit = parsedExit ?? (checked.ok ? 0 : 1)
            return BackendSnapshotResponse(
                snapshot: checked,
                exitCode: effectiveExit,
                stderr: "",
                rawJSON: String(data: data, encoding: .utf8)
            )
        } catch let error as AppError {
            throw error
        } catch {
            throw AppError.context(#fileID, #function, "Failed to fetch remote section snapshot", error)
        }
    }

    private func _url(for config: RemoteBackendConfig, path: String) -> URL {
        /**
         Summary
         Construct an endpoint URL relative to the configured base URL.

         Inputs
         config: Validated remote config.
         path: Endpoint path such as `v1/snapshot`.

         Outputs
         Fully qualified URL.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `fetchHealthStatus` and `fetchSnapshotResponse`.

         Why this exists
         Keeps URL construction consistent and avoids subtle double-slash bugs.
         */
        return config.baseURL.appendingPathComponent(path)
    }

    private func _url(
        for config: RemoteBackendConfig,
        path: String,
        queryItems: [URLQueryItem]
    ) throws -> URL {
        /**
         Summary
         Construct an endpoint URL with query items relative to the configured base URL.

         Inputs
         config: Validated remote config.
         path: Endpoint path such as `v1/section`.
         queryItems: URL query items.

         Outputs
         Fully qualified URL with query.

         Side effects
         None.

         Error handling
         Throws `AppError` when URL components cannot be built.

         Ties to other methods
         Used by `fetchSectionSnapshotResponse`.

         Why this exists
         Query parameter handling is easiest via `URLComponents` to avoid escaping bugs.
         */
        var components = URLComponents(url: config.baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false)
        components?.queryItems = queryItems
        guard let url = components?.url else {
            throw AppError.context(#fileID, #function, "Failed to build URL for \(path)")
        }
        return url
    }
}

public struct RemoteHealthStatus: Sendable, Equatable {
    /**
     Summary
     Represent a successful health check result.

     Inputs
     httpStatus: HTTP response status code.
     roundTripMs: Approximate request round-trip duration in milliseconds.

     Outputs
     A value type used for UI display.

     Side effects
     None.

     Error handling
     None.

     Ties to other methods
     Returned by `RemoteBackendClient.fetchHealthStatus`.

     Why this exists
     Pairing UX benefits from presenting a quick "reachable" signal with latency feedback.
     */

    public let httpStatus: Int32
    public let roundTripMs: Int64

    public init(httpStatus: Int32, roundTripMs: Int64) {
        /**
         Summary
         Initialize a health status value.

         Inputs
         httpStatus: HTTP status code.
         roundTripMs: Duration in milliseconds.

         Outputs
         None.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `RemoteBackendClient`.

         Why this exists
         Provides a simple, typed container for presenting health check results.
         */
        self.httpStatus = httpStatus
        self.roundTripMs = roundTripMs
    }
}
