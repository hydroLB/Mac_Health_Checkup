import CryptoKit
import Foundation
import Security

public enum CertificatePinning {
    /**
     Summary
     Provide helpers for certificate fingerprint pinning for remote snapshot fetching.

     Inputs
     Public methods accept a SHA-256 fingerprint string for the leaf certificate.

     Outputs
     A URLSession configured with a pinning delegate and normalized fingerprint helpers.

     Side effects
     Creates URLSession instances and participates in server trust challenges.

     Error handling
     Throws `AppError` for invalid fingerprint input.

     Ties to other methods
     Used by `RemoteBackendClient` when `RemoteBackendConfig.pinnedCertificateSHA256` is set.

     Why this exists
     Without TLS pinning, a token can be sniffed on an untrusted LAN even if HTTPS is used with a self-signed cert.
     */

    public static func normalizedSHA256Fingerprint(_ value: String) throws -> String {
        /**
         Summary
         Normalize a SHA-256 fingerprint string into lowercase hex without separators.

         Inputs
         value: Fingerprint string, optionally containing colons or whitespace.

         Outputs
         64-character lowercase hex fingerprint string.

         Side effects
         None.

         Error handling
         Throws `AppError` when the value is not valid SHA-256 hex.

         Ties to other methods
         Used by `RemoteBackendConfig.validated` and by the pinning delegate.

         Why this exists
         Users commonly paste fingerprints in colon-delimited format; normalization keeps comparisons stable.
         */
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        let noSeparators = trimmed
            .replacingOccurrences(of: ":", with: "")
            .replacingOccurrences(of: " ", with: "")
            .lowercased()
        if noSeparators.count != 64 {
            throw AppError.context(#fileID, #function, "Pinned cert fingerprint must be 64 hex chars (sha256)")
        }
        let allowed = CharacterSet(charactersIn: "0123456789abcdef")
        if noSeparators.unicodeScalars.contains(where: { !allowed.contains($0) }) {
            throw AppError.context(#fileID, #function, "Pinned cert fingerprint must be hex")
        }
        return noSeparators
    }

    public static func pinnedSession(expectedLeafCertificateSHA256: String) -> URLSession {
        /**
         Summary
         Create a URLSession that enforces leaf certificate SHA-256 pinning.

         Inputs
         expectedLeafCertificateSHA256: Fingerprint string.

         Outputs
         URLSession configured with a pinning delegate.

         Side effects
         Allocates a URLSession and delegate.

         Error handling
         Falls back to returning a default session if fingerprint normalization fails.

         Ties to other methods
         Used by `RemoteBackendClient` for secure HTTPS access with self-signed certificates.

         Why this exists
         Makes pinning opt-in and easy to adopt without requiring the user to install a trusted CA on iOS.
         */
        let normalized = (try? normalizedSHA256Fingerprint(expectedLeafCertificateSHA256)) ?? ""
        let delegate = PinnedCertificateURLSessionDelegate(expectedLeafCertificateSHA256: normalized)
        let configuration = URLSessionConfiguration.ephemeral
        configuration.waitsForConnectivity = true
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.urlCache = nil
        return URLSession(configuration: configuration, delegate: delegate, delegateQueue: nil)
    }
}

private final class PinnedCertificateURLSessionDelegate: NSObject, URLSessionDelegate, @unchecked Sendable {
    private let expectedLeafCertificateSHA256: String

    init(expectedLeafCertificateSHA256: String) {
        self.expectedLeafCertificateSHA256 = expectedLeafCertificateSHA256
        super.init()
    }

    func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        /**
         Summary
         Validate the server trust challenge by comparing the leaf certificate fingerprint.

         Inputs
         session: URLSession handling the request.
         challenge: Authentication challenge.
         completionHandler: Callback for disposition.

         Outputs
         None.

         Side effects
         May allow a connection that would otherwise fail system trust evaluation when the pin matches.

         Error handling
         Cancels authentication when the pin is missing or does not match.

         Ties to other methods
         Used by `CertificatePinning.pinnedSession`.

         Why this exists
         Supports secure HTTPS to a self-signed Mac agent certificate without requiring CA installation.
         */
        _ = session
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust else {
            completionHandler(.performDefaultHandling, nil)
            return
        }
        guard !expectedLeafCertificateSHA256.isEmpty else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        guard let trust = challenge.protectionSpace.serverTrust else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        let leaf: SecCertificate?
        if #available(macOS 12.0, iOS 15.0, *) {
            let chain = SecTrustCopyCertificateChain(trust) as? [SecCertificate]
            leaf = chain?.first
        } else {
            leaf = SecTrustGetCertificateAtIndex(trust, 0)
        }
        guard let leaf else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        let leafData = SecCertificateCopyData(leaf) as Data
        let digest = SHA256.hash(data: leafData)
        let hex = digest.map { String(format: "%02x", $0) }.joined()
        if hex == expectedLeafCertificateSHA256 {
            completionHandler(.useCredential, URLCredential(trust: trust))
            return
        }
        completionHandler(.cancelAuthenticationChallenge, nil)
    }
}
