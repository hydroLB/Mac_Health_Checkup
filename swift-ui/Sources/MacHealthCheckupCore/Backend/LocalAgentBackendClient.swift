import Foundation

#if os(macOS)

import Security

public final class LocalAgentBackendClient: SnapshotBackend, TemperatureAccessBackend, @unchecked Sendable {
    /**
     Summary
     Run a local Mac agent server process and fetch snapshots over loopback HTTP.

     Inputs
     runtime: Backend runtime config (python path, repo root, timeouts).
     baseConfigFile: Path to the base config JSON to overlay with local API settings.

     Outputs
     `BackendSnapshotResponse` values decoded from the local agent API.

     Side effects
     Spawns a long-lived Python process that binds `127.0.0.1:<port>` and serves HTTP endpoints.

     Error handling
     Throws `AppError` when the agent process cannot start, the health check fails, or snapshot fetching fails.

     Ties to other methods
     Intended for the macOS SwiftUI app so refreshes do not pay Python startup cost repeatedly.

     Why this exists
     The original Tk UI kept collectors and caches in a single Python process; a local agent restores that speed and behavior.
     */

    private let state: LocalAgentState

    public init(runtime: BackendRuntimeConfig, baseConfigFile: URL) {
        /**
         Summary
         Initialize the client.

         Inputs
         runtime: Backend runtime config.
         baseConfigFile: Base config file used to build a derived local agent config.

         Outputs
         None.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         `fetchSnapshotResponse` starts the agent lazily on first use.

         Why this exists
         Keeps bootstrap fast and defers process work until a snapshot is actually requested.
         */
        self.state = LocalAgentState(runtime: runtime, baseConfigFile: baseConfigFile)
    }

    deinit {
        /**
         Summary
         Best-effort stop the agent process.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Attempts to terminate the child process.

         Error handling
         None. Errors are intentionally ignored during deinit.

         Ties to other methods
         Complements `LocalAgentState.stop`.

         Why this exists
         Prevents leaving a background agent process running after the UI exits.
         */
        let capturedState = state
        Task { await capturedState.stop() }
    }

    public func fetchSnapshotResponse() async throws -> BackendSnapshotResponse {
        /**
         Summary
         Ensure the local agent is running and fetch a snapshot via HTTP.

         Inputs
         None.

         Outputs
         `BackendSnapshotResponse` containing a validated snapshot.

         Side effects
         Starts the agent process on first use and performs a network request to loopback.

         Error handling
         Throws `AppError` when startup, health checks, or snapshot fetching fail.

         Ties to other methods
         Called by `DashboardViewModel.refreshOnce`.

         Why this exists
         Provides a fast refresh path that keeps Python caches warm between refreshes.
         */
        return try await state.fetchSnapshot()
    }

    public func fetchSectionSnapshotResponse(sectionKey: String) async throws -> BackendSnapshotResponse {
        /**
         Summary
         Ensure the local agent is running and fetch a single-section snapshot via HTTP.

         Inputs
         sectionKey: Section key to fetch.

         Outputs
         `BackendSnapshotResponse` containing a validated snapshot with a subset of sections.

         Side effects
         Starts the agent process on first use and performs a network request to loopback.

         Error handling
         Throws `AppError` when startup, health checks, or snapshot fetching fail.

         Ties to other methods
         Used by `DashboardViewModel` for higher-frequency refreshes of specific sections.

         Why this exists
         Keeps frequent fan updates cheap by avoiding full snapshot recomputation.
         */
        return try await state.fetchSectionSnapshot(sectionKey: sectionKey)
    }

    public func requestTemperatureSensorAccess() async throws -> TemperatureAccessResponse {
        /**
         Summary
         Ensure the local agent is running and request temperature sensor access via HTTP.

         Inputs
         None.

         Outputs
         `TemperatureAccessResponse` describing authorization result.

         Side effects
         Starts the agent process on first use and performs a loopback HTTP request that may trigger a macOS admin prompt.

         Error handling
         Throws `AppError` when startup, health checks, or the authorization request fails.

         Ties to other methods
         Used by the macOS UI settings flow to explicitly request temperature access.

         Why this exists
         Snapshot refresh should not unexpectedly trigger prompts; authorization is explicit and user-initiated.
         */
        return try await state.requestTemperatureAccess()
    }
}

private actor LocalAgentState {
    private let runtime: BackendRuntimeConfig
    private let baseConfigFile: URL
    private var process: Process?
    private var stderrBuffer: OutputRingBuffer?
    private var remote: RemoteBackendClient?

    private var baseURL: URL?
    private var token: String?

    init(runtime: BackendRuntimeConfig, baseConfigFile: URL) {
        self.runtime = runtime
        self.baseConfigFile = baseConfigFile
    }

    func fetchSnapshot() async throws -> BackendSnapshotResponse {
        /**
         Summary
         Ensure the agent is started and return a snapshot response from the local API.

         Inputs
         None.

         Outputs
         `BackendSnapshotResponse`.

         Side effects
         Starts a background process and performs a loopback HTTP request.

         Error handling
         Throws `AppError` when startup fails or the request cannot be completed.

         Ties to other methods
         Used by `LocalAgentBackendClient.fetchSnapshotResponse`.

         Why this exists
         Serializes agent lifecycle and snapshot fetching to avoid races.
         */
        try await ensureStarted()
        guard let remote else {
            throw AppError.context(#fileID, #function, "Local agent remote client not initialized")
        }
        return try await remote.fetchSnapshotResponse()
    }

    func fetchSectionSnapshot(sectionKey: String) async throws -> BackendSnapshotResponse {
        /**
         Summary
         Ensure the agent is started and return a section snapshot response from the local API.

         Inputs
         sectionKey: Section key to fetch.

         Outputs
         `BackendSnapshotResponse`.

         Side effects
         Starts a background process and performs a loopback HTTP request.

         Error handling
         Throws `AppError` when startup fails or the request cannot be completed.

         Ties to other methods
         Used by `LocalAgentBackendClient.fetchSectionSnapshotResponse`.

         Why this exists
         Enables high-frequency refresh for a single section without hammering the full snapshot path.
         */
        try await ensureStarted()
        guard let remote else {
            throw AppError.context(#fileID, #function, "Local agent remote client not initialized")
        }
        return try await remote.fetchSectionSnapshotResponse(sectionKey: sectionKey)
    }

    func requestTemperatureAccess() async throws -> TemperatureAccessResponse {
        /**
         Summary
         Ensure the agent is started and request temperature authorization via the local API.

         Inputs
         None.

         Outputs
         `TemperatureAccessResponse`.

         Side effects
         Starts a background process and performs a loopback HTTP request.

         Error handling
         Throws `AppError` when startup fails or the request cannot be completed.

         Ties to other methods
         Used by `LocalAgentBackendClient.requestTemperatureSensorAccess`.

         Why this exists
         Keeps authorization calls serialized with agent lifecycle to avoid races.
         */
        try await ensureStarted()
        guard let remote else {
            throw AppError.context(#fileID, #function, "Local agent remote client not initialized")
        }
        return try await remote.requestTemperatureSensorAccess()
    }

    func stop() async {
        /**
         Summary
         Stop the local agent process if it is running.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Terminates the spawned process.

         Error handling
         None. Best-effort cleanup only.

         Ties to other methods
         Called by `LocalAgentBackendClient.deinit`.

         Why this exists
         Ensures the UI does not leave background processes running.
         */
        if let process {
            if process.isRunning {
                process.terminate()
            }
            self.process = nil
        }
        self.remote = nil
        self.baseURL = nil
        self.token = nil
        self.stderrBuffer = nil
    }

    private func ensureStarted() async throws {
        /**
         Summary
         Start the local agent if not already running and validate readiness via /v1/health.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Writes a derived config file and starts a child Python process.

         Error handling
         Throws `AppError` when startup fails or health checks do not succeed in time.

         Ties to other methods
         Called by `fetchSnapshot`.

         Why this exists
         Prevents paying Python interpreter startup cost on every refresh while keeping behavior deterministic.
         */
        if let process, process.isRunning, remote != nil {
            return
        }

        let port = try LocalPortPicker.pickLoopbackPort()
        let token = try TokenGenerator.generateURLSafeToken(minBytes: 24)
        let baseURL = try URL(string: "http://127.0.0.1:\(port)") ?? {
            throw AppError.context(#fileID, #function, "Failed to build loopback URL for port \(port)")
        }()

        let derivedConfig = try LocalAgentConfigOverlay.buildDerivedConfig(
            baseConfigFile: baseConfigFile,
            bindPort: port,
            authToken: token
        )
        let derivedPath = runtime.repoRoot
            .appendingPathComponent(".local", isDirectory: true)
            .appendingPathComponent("macos-ui-agent-config.json", isDirectory: false)
        try LocalAgentConfigOverlay.writeDerivedConfig(derivedConfig, to: derivedPath)

        let stderrBuffer = OutputRingBuffer(maxBytes: 32_000)
        let process = try startAgentProcess(configFile: derivedPath, stderrBuffer: stderrBuffer)

        let remoteConfig = RemoteBackendConfig(baseURL: baseURL, authToken: token, timeoutSeconds: runtime.timeoutSeconds)
        let remoteClient = RemoteBackendClient(config: remoteConfig)

        self.process = process
        self.stderrBuffer = stderrBuffer
        self.remote = remoteClient
        self.baseURL = baseURL
        self.token = token

        try await awaitHealthy(remoteClient: remoteClient, startupTimeoutSeconds: 5.0)
    }

    private func startAgentProcess(configFile: URL, stderrBuffer: OutputRingBuffer) throws -> Process {
        /**
         Summary
         Spawn the Python agent server process in `--serve` mode.

         Inputs
         configFile: Derived config file to pass via `MAC_HEALTH_CHECKUP_CONFIG`.
         stderrBuffer: Buffer to capture stderr for diagnostics on failure.

         Outputs
         A started `Process` instance.

         Side effects
         Starts a child process that binds a local TCP port.

         Error handling
         Throws `AppError` when the process cannot be started.

         Ties to other methods
         Used by `ensureStarted`.

         Why this exists
         Keeps agent lifecycle management centralized and provides actionable diagnostics when startup fails.
         */
        let process = Process()
        process.executableURL = URL(fileURLWithPath: runtime.pythonExecutable)
        process.arguments = ["-m", "mac_health_checkup", "--serve"]
        process.currentDirectoryURL = runtime.repoRoot

        var env = ProcessInfo.processInfo.environment
        env["MAC_HEALTH_CHECKUP_CONFIG"] = configFile.path
        env["MAC_HEALTH_CHECKUP_REPO_ROOT"] = runtime.repoRoot.path
        env["PYTHONPATH"] = runtime.repoRoot.path
        env["PYTHONUNBUFFERED"] = "1"
        process.environment = env

        process.standardOutput = FileHandle.nullDevice

        let stderrPipe = Pipe()
        process.standardError = stderrPipe
        stderrBuffer.attach(pipe: stderrPipe)

        do {
            try process.run()
            return process
        } catch {
            throw AppError.context(#fileID, #function, "Failed to start local agent process \(runtime.pythonExecutable)", error)
        }
    }

    private func awaitHealthy(remoteClient: RemoteBackendClient, startupTimeoutSeconds: TimeInterval) async throws {
        /**
         Summary
         Poll the health endpoint until it responds successfully or the startup timeout elapses.

         Inputs
         remoteClient: Remote backend client configured for loopback.
         startupTimeoutSeconds: Maximum time to wait for health.

         Outputs
         None.

         Side effects
         Performs repeated HTTP requests to `/v1/health`.

         Error handling
         Throws `AppError` when the agent does not become healthy in time.

         Ties to other methods
         Called after spawning the agent process.

         Why this exists
         Avoids racing the first snapshot request against server startup.
         */
        let clock = ContinuousClock()
        let deadline = clock.now.advanced(by: .seconds(startupTimeoutSeconds))
        var lastError: AppError?

        while clock.now < deadline {
            do {
                _ = try await remoteClient.fetchHealthStatus()
                return
            } catch let error as AppError {
                lastError = error
            } catch {
                lastError = AppError.context(#fileID, #function, "Local agent health check failed", error)
            }
            try? await Task.sleep(nanoseconds: 150_000_000)
        }

        let stderr = stderrBuffer?.asString().trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let suffix = stderr.isEmpty ? "" : " stderr=\(stderr)"
        throw AppError.context(
            #fileID,
            #function,
            "Local agent did not become healthy within \(Int(startupTimeoutSeconds))s.\(suffix)",
            lastError
        )
    }
}

private enum LocalAgentConfigOverlay {
    static func buildDerivedConfig(baseConfigFile: URL, bindPort: Int, authToken: String) throws -> [String: Any] {
        /**
         Summary
         Build a derived config dictionary by overlaying a local-only API section.

         Inputs
         baseConfigFile: Base config JSON file.
         bindPort: Loopback port to bind.
         authToken: Generated auth token for snapshot requests.

         Outputs
         Derived JSON object as a dictionary.

         Side effects
         Reads the base config file from disk.

         Error handling
         Throws `AppError` when the base config is invalid or missing required sections.

         Ties to other methods
         Used by `ensureStarted` before starting the agent process.

         Why this exists
         The macOS UI should start a local-only agent without requiring users to edit `config/config.json`.
         */
        do {
            let data = try Data(contentsOf: baseConfigFile, options: [.mappedIfSafe])
            let json = try JSONSerialization.jsonObject(with: data, options: [])
            guard var root = json as? [String: Any] else {
                throw AppError.context(#fileID, #function, "Base config must be a JSON object: \(baseConfigFile.path)")
            }
            guard var api = root["api"] as? [String: Any] else {
                throw AppError.context(#fileID, #function, "Base config missing 'api' object: \(baseConfigFile.path)")
            }
            var fans = (root["fans"] as? [String: Any]) ?? [:]

            api["enabled"] = true
            api["bind_host"] = "127.0.0.1"
            api["port"] = bindPort
            api["allow_lan"] = false
            api["allow_insecure_http_lan"] = false
            api["tls_enabled"] = false
            api["auth_token"] = authToken

            fans["use_sudo"] = true
            fans["use_admin_prompt"] = true

            root["api"] = api
            root["fans"] = fans
            return root
        } catch let error as AppError {
            throw error
        } catch {
            throw AppError.context(#fileID, #function, "Failed to build derived agent config", error)
        }
    }

    static func writeDerivedConfig(_ obj: [String: Any], to path: URL) throws {
        /**
         Summary
         Write a derived config JSON object to disk.

         Inputs
         obj: Root JSON object dictionary.
         path: Output file location.

         Outputs
         None.

         Side effects
         Creates parent directories and writes the output file.

         Error handling
         Throws `AppError` when serialization or IO fails.

         Ties to other methods
         Called by `ensureStarted`.

         Why this exists
         The Python backend reads config from a file path; writing a derived overlay avoids manual setup.
         */
        do {
            try FileManager.default.createDirectory(at: path.deletingLastPathComponent(), withIntermediateDirectories: true)
            let data = try JSONSerialization.data(withJSONObject: obj, options: [.prettyPrinted, .sortedKeys])
            try data.write(to: path, options: [.atomic])
        } catch {
            throw AppError.context(#fileID, #function, "Failed to write derived config to \(path.path)", error)
        }
    }
}

private enum TokenGenerator {
    static func generateURLSafeToken(minBytes: Int) throws -> String {
        /**
         Summary
         Generate a URL-safe token for Authorization headers.

         Inputs
         minBytes: Minimum entropy bytes.

         Outputs
         URL-safe base64 string without padding.

         Side effects
         Uses system RNG.

         Error handling
         Throws `AppError` when randomness generation fails.

         Ties to other methods
         Used by `LocalAgentState.ensureStarted`.

         Why this exists
         The local agent still enforces bearer auth, even on loopback, to keep behavior consistent with iOS pairing.
         */
        if minBytes < 16 {
            throw AppError.context(#fileID, #function, "minBytes too small: \(minBytes)")
        }
        var bytes = [UInt8](repeating: 0, count: minBytes)
        let status = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        if status != errSecSuccess {
            throw AppError.context(#fileID, #function, "SecRandomCopyBytes failed with status \(status)")
        }
        let data = Data(bytes)
        return data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}

private enum LocalPortPicker {
    static func pickLoopbackPort() throws -> Int {
        /**
         Summary
         Pick an available TCP port on loopback for binding the local agent server.

         Inputs
         None.

         Outputs
         Port number.

         Side effects
         Binds and closes a temporary socket to let the OS choose a free port.

         Error handling
         Throws `AppError` when socket operations fail.

         Ties to other methods
         Used by `LocalAgentState.ensureStarted`.

         Why this exists
         Avoids hard-coded ports and reduces chance of collisions with other local services.
         */
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(0).bigEndian
        addr.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))

        let fd = socket(AF_INET, SOCK_STREAM, 0)
        if fd < 0 {
            throw AppError.context(#fileID, #function, "Failed to create socket")
        }
        defer { close(fd) }

        var a = addr
        let bindResult = withUnsafePointer(to: &a) { ptr in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPtr in
                Darwin.bind(fd, sockaddrPtr, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        if bindResult != 0 {
            throw AppError.context(#fileID, #function, "Failed to bind loopback socket")
        }

        var name = sockaddr_in()
        var len = socklen_t(MemoryLayout<sockaddr_in>.size)
        let nameResult = withUnsafeMutablePointer(to: &name) { ptr in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPtr in
                getsockname(fd, sockaddrPtr, &len)
            }
        }
        if nameResult != 0 {
            throw AppError.context(#fileID, #function, "getsockname failed")
        }
        let port = Int(UInt16(bigEndian: name.sin_port))
        if port <= 0 || port > 65535 {
            throw AppError.context(#fileID, #function, "Invalid chosen port: \(port)")
        }
        return port
    }
}

private final class OutputRingBuffer: @unchecked Sendable {
    /**
     Summary
     Capture a bounded amount of process stderr output for troubleshooting.

     Inputs
     maxBytes: Maximum bytes retained.

     Outputs
     A thread-safe buffer that can return captured text.

     Side effects
     Installs a readability handler on a pipe's file handle.

     Error handling
     None.

     Ties to other methods
     Used by `LocalAgentState` during agent startup.

     Why this exists
     When the agent fails to start, having stderr context makes errors actionable without flooding logs.
     */

    private let maxBytes: Int
    private let lock = NSLock()
    private var data = Data()

    init(maxBytes: Int) {
        self.maxBytes = max(1_024, maxBytes)
    }

    func attach(pipe: Pipe) {
        /**
         Summary
         Begin capturing output from a pipe.

         Inputs
         pipe: Pipe whose file handle will be observed.

         Outputs
         None.

         Side effects
         Installs a readability handler.

         Error handling
         None.

         Ties to other methods
         Used during process start.

         Why this exists
         Prevents the child process from blocking on a full stderr pipe while keeping some diagnostics.
         */
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            guard let self else { return }
            let chunk = handle.availableData
            if chunk.isEmpty { return }
            self.append(chunk)
        }
    }

    func asString() -> String {
        /**
         Summary
         Return captured stderr as a UTF-8 string.

         Inputs
         None.

         Outputs
         Captured stderr string.

         Side effects
         None.

         Error handling
         None. Invalid UTF-8 sequences are replaced.

         Ties to other methods
         Used to enrich startup error messages.

         Why this exists
         Keeps error messages actionable without requiring users to run the agent manually to see stderr.
         */
        lock.lock()
        defer { lock.unlock() }
        return String(decoding: data, as: UTF8.self)
    }

    private func append(_ chunk: Data) {
        lock.lock()
        defer { lock.unlock() }
        data.append(chunk)
        if data.count > maxBytes {
            data.removeFirst(data.count - maxBytes)
        }
    }
}

#endif
