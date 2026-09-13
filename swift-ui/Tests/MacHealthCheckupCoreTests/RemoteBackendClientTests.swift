import Foundation
import XCTest
@testable import MacHealthCheckupCore

final class RemoteBackendClientTests: XCTestCase {
    func testHealthStatusUsesHealthPathWithoutAuthorizationHeader() async throws {
        /**
         Summary
        Ensure the health check hits `/v1/health` and does not send an Authorization header.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Uses a URLProtocol stub to intercept URLSession requests.

         Error handling
         Fails via XCTest assertions on mismatched requests or unexpected errors.

         Ties to other methods
         Exercises `RemoteBackendClient.fetchHealthStatus`.

         Why this exists
         Pairing flows should validate reachability without leaking token details into unauthenticated endpoints.
         */
        let baseURL = try XCTUnwrap(URL(string: "http://127.0.0.1:7878"))
        let config = RemoteBackendConfig(baseURL: baseURL, authToken: "secret", timeoutSeconds: 5)

        let recorder = RequestRecorder()
        URLProtocolStub.handler = { request in
            Task { await recorder.record(request) }
            let response = HTTPURLResponse(
                url: try XCTUnwrap(request.url),
                statusCode: 200,
                httpVersion: "HTTP/1.1",
                headerFields: ["Content-Type": "application/json"]
            )!
            return (response, Data("{}".utf8))
        }

        let session = URLSession(configuration: _sessionConfiguration())
        let client = RemoteBackendClient(config: config, session: session)
        let health = try await client.fetchHealthStatus()

        XCTAssertEqual(health.httpStatus, 200)
        let request = await recorder.awaitRequest()
        XCTAssertEqual(request.httpMethod, "GET")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), nil)
        XCTAssertEqual(request.url?.path, "/v1/health")
    }

    func testFetchSnapshotSendsAuthorizationHeaderAndDecodesSchemaV2() async throws {
        /**
         Summary
         Ensure snapshot requests send a Bearer Authorization header and decode schema version 2.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Uses a URLProtocol stub to intercept URLSession requests.

         Error handling
         Fails via XCTest assertions on mismatched requests or decoding failures.

         Ties to other methods
         Exercises `RemoteBackendClient.fetchSnapshotResponse`.

         Why this exists
         The iOS client must authenticate snapshot calls and remain resilient to schema drift.
         */
        let baseURL = try XCTUnwrap(URL(string: "http://127.0.0.1:7878"))
        let config = RemoteBackendConfig(baseURL: baseURL, authToken: "secret-token", timeoutSeconds: 5)

        let snapshotJSON = """
        {
          "schema_version": 2,
          "generated_at_unix_ms": 1700000000000,
          "theme": {
            "ui": { "window_title": "Mac Health Checkup" },
            "colors": {
              "bg": "#23272e",
              "fg": "#ffffff",
              "ok": "#2ecc40",
              "warn": "#ffdc00",
              "bad": "#ff4136",
              "section": "#339af0",
              "label": "#f1c40f",
              "field": "#daf6ff"
            },
            "fonts": {
              "family_default": "Helvetica",
              "family_mono": "Menlo",
              "size_section": 16,
              "size_banner": 18,
              "size_field": 13,
              "size_tooltip": 10
            },
            "gui": {
              "card_bg": "#1b2027",
              "card_border": "#2a313c",
              "section_padx": 4,
              "section_pady": 3,
              "auto_refresh_ms": 1000,
              "scrollable_rows": {}
            }
          },
          "section_catalog": [],
          "sections": [],
          "ok": true,
          "error": null
        }
        """

        let recorder = RequestRecorder()
        URLProtocolStub.handler = { request in
            Task { await recorder.record(request) }
            let response = HTTPURLResponse(
                url: try XCTUnwrap(request.url),
                statusCode: 200,
                httpVersion: "HTTP/1.1",
                headerFields: ["Content-Type": "application/json", "X-Snapshot-Exit-Code": "0"]
            )!
            return (response, Data(snapshotJSON.utf8))
        }

        let session = URLSession(configuration: _sessionConfiguration())
        let client = RemoteBackendClient(config: config, session: session)
        let response = try await client.fetchSnapshotResponse()

        XCTAssertEqual(response.exitCode, 0)
        XCTAssertEqual(response.snapshot.schema_version, 2)

        let request = await recorder.awaitRequest()
        XCTAssertEqual(request.url?.path, "/v1/snapshot")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer secret-token")
    }

    func testFetchSnapshotDefaultsMissingExitHeaderFromSnapshotStatus() async throws {
        /**
         Summary
         Ensure a missing transport header falls back to the decoded snapshot status instead of HTTP 200.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Uses a URLProtocol stub for two deterministic snapshot responses.

         Error handling
         Fails through XCTest assertions or propagated client errors.

         Ties to other methods
         Exercises `RemoteBackendClient.fetchSnapshotResponse` fallback exit-code behavior.

         Why this exists
         Proxies may strip custom headers; a successful HTTP status is not a backend process exit code.
         */
        let baseURL = try XCTUnwrap(URL(string: "http://127.0.0.1:7878"))
        let config = RemoteBackendConfig(baseURL: baseURL, authToken: "secret-token", timeoutSeconds: 5)

        for expectedOK in [true, false] {
            let snapshotData = Data(_snapshotJSON(ok: expectedOK).utf8)
            URLProtocolStub.handler = { request in
                let response = HTTPURLResponse(
                    url: try XCTUnwrap(request.url),
                    statusCode: 200,
                    httpVersion: "HTTP/1.1",
                    headerFields: ["Content-Type": "application/json"]
                )!
                return (response, snapshotData)
            }

            let session = URLSession(configuration: _sessionConfiguration())
            let client = RemoteBackendClient(config: config, session: session)
            let response = try await client.fetchSnapshotResponse()

            XCTAssertEqual(response.exitCode, expectedOK ? 0 : 1)
        }
    }

    private func _sessionConfiguration() -> URLSessionConfiguration {
        /**
         Summary
         Create a URLSession configuration that uses the test URLProtocol stub.

         Inputs
         None.

         Outputs
         URLSessionConfiguration configured with URLProtocolStub.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by this test suite for deterministic network behavior.

         Why this exists
         URLProtocol stubbing keeps tests hermetic and fast without hitting the network.
         */
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [URLProtocolStub.self]
        return configuration
    }

    private func _snapshotJSON(ok: Bool) -> String {
        """
        {
          "schema_version": 2,
          "generated_at_unix_ms": 1700000000000,
          "theme": {
            "ui": { "window_title": "Mac Health Checkup" },
            "colors": {
              "bg": "#23272e",
              "fg": "#ffffff",
              "ok": "#2ecc40",
              "warn": "#ffdc00",
              "bad": "#ff4136",
              "section": "#339af0",
              "label": "#f1c40f",
              "field": "#daf6ff"
            },
            "fonts": {
              "family_default": "Helvetica",
              "family_mono": "Menlo",
              "size_section": 16,
              "size_banner": 18,
              "size_field": 13,
              "size_tooltip": 10
            },
            "gui": {
              "card_bg": "#1b2027",
              "card_border": "#2a313c",
              "section_padx": 4,
              "section_pady": 3,
              "auto_refresh_ms": 1000,
              "scrollable_rows": {}
            }
          },
          "section_catalog": [],
          "sections": [],
          "ok": \(ok ? "true" : "false"),
          "error": \(ok ? "null" : "\"snapshot failed\"")
        }
        """
    }

    func testConfigValidationRejectsInvalidPinnedFingerprint() throws {
        /**
         Summary
         Ensure invalid pinned certificate fingerprint values are rejected during validation.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Expects `RemoteBackendConfig.validated` to throw.

         Ties to other methods
         Exercises `RemoteBackendConfig.validated` and `CertificatePinning.normalizedSHA256Fingerprint`.

         Why this exists
         Prevents silent misconfiguration that could make pinning appear enabled when it is not enforceable.
         */
        let baseURL = try XCTUnwrap(URL(string: "https://example.test:7878"))
        let config = RemoteBackendConfig(
            baseURL: baseURL,
            authToken: "secret",
            timeoutSeconds: 5,
            pinnedCertificateSHA256: "not-a-fingerprint"
        )
        XCTAssertThrowsError(try config.validated())
    }

    func testConfigValidationAllowsHTTPForExplicitLoopbackHosts() throws {
        /**
         Summary
         Ensure plain HTTP remains available for local macOS agent and development connections.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Fails when a supported loopback URL does not validate.

         Ties to other methods
         Exercises `RemoteBackendConfig.validated` loopback classification.

         Why this exists
         Transport hardening must preserve IPv4, IPv6, and localhost-based local workflows.
         */
        let urls = [
            "http://127.0.0.1:7878",
            "http://127.42.0.9:7878",
            "http://[::1]:7878",
            "http://localhost:7878",
            "http://LOCALHOST.:7878",
        ]

        for value in urls {
            let baseURL = try XCTUnwrap(URL(string: value))
            let config = RemoteBackendConfig(baseURL: baseURL, authToken: "secret", timeoutSeconds: 5)
            XCTAssertNoThrow(try config.validated(), "Expected loopback HTTP URL to validate: \(value)")
        }
    }

    func testConfigValidationRejectsHTTPForNonLoopbackHost() throws {
        /**
         Summary
         Ensure bearer credentials cannot be sent over cleartext HTTP to a LAN endpoint.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Expects `RemoteBackendConfig.validated` to reject the insecure URL.

         Ties to other methods
         Exercises the remote transport boundary in `RemoteBackendConfig.validated`.

         Why this exists
         Local-network HTTP exposes both the bearer token and sensitive health snapshots to interception.
         */
        let baseURL = try XCTUnwrap(URL(string: "http://192.168.1.10:7878"))
        let config = RemoteBackendConfig(baseURL: baseURL, authToken: "secret", timeoutSeconds: 5)

        XCTAssertThrowsError(try config.validated()) { error in
            XCTAssertTrue(String(describing: error).contains("HTTP is allowed only for loopback"))
        }
    }

    func testConfigValidationRequiresPinForNonLoopbackHTTPS() throws {
        /**
         Summary
         Ensure non-loopback HTTPS uses the certificate pin supplied by the self-signed pairing payload.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         Expects missing pins to fail and a valid pin to normalize successfully.

         Ties to other methods
         Exercises `RemoteBackendConfig.validated` and fingerprint normalization together.

         Why this exists
         Encryption without authenticating the paired self-signed server does not protect the bearer token from a LAN intermediary.
         */
        let baseURL = try XCTUnwrap(URL(string: "https://192.168.1.10:7878"))
        let missingPin = RemoteBackendConfig(baseURL: baseURL, authToken: "secret", timeoutSeconds: 5)
        XCTAssertThrowsError(try missingPin.validated()) { error in
            XCTAssertTrue(String(describing: error).contains("requires a pinned certificate"))
        }

        let colonDelimitedPin = Array(repeating: "AA", count: 32).joined(separator: ":")
        let pinned = RemoteBackendConfig(
            baseURL: baseURL,
            authToken: "secret",
            timeoutSeconds: 5,
            pinnedCertificateSHA256: colonDelimitedPin
        )
        let validated = try pinned.validated()
        XCTAssertEqual(validated.pinnedCertificateSHA256, String(repeating: "aa", count: 32))
    }
}

private actor RequestRecorder {
    func record(_ request: URLRequest) {
        /**
         Summary
         Record the last observed URLRequest and wake any waiter.

         Inputs
         request: URLRequest to store.

         Outputs
         None.

         Side effects
         Updates internal state and resumes a continuation if present.

         Error handling
         None.

         Ties to other methods
         Used by URLProtocol stub handlers in this test suite.

         Why this exists
         Tests need a deterministic way to assert request construction without races.
         */
        self.request = request
        if let continuation {
            self.continuation = nil
            continuation.resume(returning: request)
        }
    }

    func awaitRequest() async -> URLRequest {
        /**
         Summary
         Await a recorded URLRequest.

         Inputs
         None.

         Outputs
         URLRequest that was recorded by `record`.

         Side effects
         Suspends the current task until a request is recorded.

         Error handling
         None.

         Ties to other methods
         Used by tests after invoking RemoteBackendClient methods.

         Why this exists
         URLProtocol callbacks occur asynchronously; awaiting avoids brittle polling.
         */
        if let request {
            return request
        }
        return await withCheckedContinuation { cont in
            continuation = cont
        }
    }

    private var request: URLRequest?
    private var continuation: CheckedContinuation<URLRequest, Never>?
}

private final class URLProtocolStub: URLProtocol {
    nonisolated(unsafe) static var handler: (@Sendable (URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool {
        /**
         Summary
         Determine whether this URLProtocol should handle the given request.

         Inputs
         request: URLRequest under evaluation.

         Outputs
         True to intercept all requests.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by URLSession during request dispatch.

         Why this exists
         Keeps network tests hermetic by ensuring every request is routed through the stub.
         */
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        /**
         Summary
         Return a canonical form of the request.

         Inputs
         request: URLRequest.

         Outputs
         The same request.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by URLSession internal caching logic.

         Why this exists
         The test stub does not need request normalization.
         */
        request
    }

    override func startLoading() {
        /**
         Summary
         Execute the stub handler and feed its response back to URLSession.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Calls URLProtocol client callbacks.

         Error handling
         Reports a failure to the client when no handler is registered or when handler throws.

         Ties to other methods
         Used by URLSession when a request is routed to this URLProtocol.

         Why this exists
         Provides deterministic, in-memory responses for network-dependent code paths.
         */
        guard let handler = Self.handler else {
            client?.urlProtocol(self, didFailWithError: NSError(domain: "URLProtocolStub", code: 1))
            return
        }
        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {
        /**
         Summary
         Stop loading the current request.

         Inputs
         None.

         Outputs
         None.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Called by URLSession when cancelling a request.

         Why this exists
         Required override for URLProtocol.
         */
    }
}
