import Foundation

public struct TemperatureAccessResponse: Decodable, Sendable, Equatable {
    /**
     Summary
     Represent the response from the backend temperature authorization endpoint.

     Inputs
     ok: Whether authorization succeeded.
     sensorsFound: Optional count of parsed sensors when available.
     error: Optional machine-readable error string.
     guidance: Optional user-facing guidance text.
     retryAfterSec: Optional retry delay when authorization is rate-limited.
     raw: Optional raw diagnostic output for debugging.

     Outputs
     Value type consumed by the UI for errors and messaging.

     Side effects
     None.

     Error handling
     Decoding errors are surfaced by the caller as `AppError`.

     Ties to other methods
     Returned by `TemperatureAccessBackend.requestTemperatureSensorAccess`.

     Why this exists
     The UI needs a stable, typed shape for the explicit "Request Access" flow without overloading snapshot JSON.
     */

    public let ok: Bool
    public let sensorsFound: Int?
    public let error: String?
    public let guidance: String?
    public let retryAfterSec: Int?
    public let raw: String?

    private enum CodingKeys: String, CodingKey {
        case ok
        case sensorsFound = "sensors_found"
        case error
        case guidance
        case retryAfterSec = "retry_after_sec"
        case raw
    }
}

public protocol TemperatureAccessBackend: Sendable {
    /**
     Summary
     Provide an explicit user-driven authorization flow for temperature sensors.

     Inputs
     None.

     Outputs
     `TemperatureAccessResponse` describing success or actionable failure.

     Side effects
     Implementation-dependent IO such as a backend HTTP request that may trigger a macOS admin prompt.

     Error handling
     Throws `AppError` when the request fails or the response cannot be decoded.

     Ties to other methods
     Implemented by `LocalAgentBackendClient` (macOS) and `RemoteBackendClient` (iOS/macOS).

     Why this exists
     Snapshot refreshes must not unexpectedly trigger admin prompts; authorization should be explicit and user-initiated.
     */

    func requestTemperatureSensorAccess() async throws -> TemperatureAccessResponse
}
