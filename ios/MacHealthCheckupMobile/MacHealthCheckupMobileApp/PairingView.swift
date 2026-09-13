import SwiftUI
import UIKit

struct PairingView: View {
    /**
     Summary
     Render a polished pairing screen for connecting to the Mac agent.

     Inputs
     agentBaseURL: Current base URL value.
     token: Current token value.
     errorMessage: Optional error text for validation or connection failures.
     onConnect: Callback invoked with validated inputs.

     Outputs
     A SwiftUI view.

     Side effects
     None.

     Error handling
     Displays validation errors inline without crashing.

     Ties to other methods
     Calls `MobileAppState.connect` via the `onConnect` callback.

     Why this exists
     A proper iOS app needs an intentional first-run experience rather than assuming local access to diagnostics.
     */

    let agentBaseURL: String
    let storedTokenAvailable: Bool
    let isTestingConnection: Bool
    let healthStatusText: String?
    let errorMessage: String?
    let onTest: (String, String) -> Void
    let onConnect: (String, String) -> Void
    let onForgetStoredToken: () -> Void
    let onImportedTLSFingerprint: (String) -> Void

    @State private var urlText: String = ""
    @State private var tokenText: String = ""
    @State private var showScanner: Bool = false
    @State private var showImportError: Bool = false
    @State private var importErrorMessage: String = ""
    @State private var showForgetTokenConfirmation: Bool = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    _header

                    _pairingCard

                    _macInstructions
                }
                .padding(16)
            }
            .background(
                LinearGradient(
                    colors: [Color.black, Color(red: 0.07, green: 0.08, blue: 0.12)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
            )
            .onAppear {
                urlText = agentBaseURL
                tokenText = ""
            }
            .sheet(isPresented: $showScanner) {
                QRCodeScannerView(
                    onCode: { value in
                        showScanner = false
                        _importPairingText(value)
                    },
                    onCancel: { showScanner = false }
                )
            }
            .alert("Import failed", isPresented: $showImportError) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(importErrorMessage)
            }
            .confirmationDialog(
                "Forget stored token?",
                isPresented: $showForgetTokenConfirmation,
                titleVisibility: .visible
            ) {
                Button("Forget Token", role: .destructive) {
                    onForgetStoredToken()
                    _haptic(.warning)
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("You will need the pairing payload or token from your Mac to reconnect.")
            }
        }
    }

    private var _header: some View {
        /**
         Summary
         Render the brand header for the pairing screen.

         Inputs
         None.

         Outputs
         SwiftUI view.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `body`.

         Why this exists
         Provides a premium first-run experience aligned with a native iOS aesthetic.
         */
        VStack(spacing: 10) {
            ZStack {
                Circle()
                    .fill(.thinMaterial)
                    .frame(width: 84, height: 84)
                Image(systemName: "waveform.path.ecg")
                    .font(.system(size: 34, weight: .semibold))
                    .foregroundStyle(.white)
            }
            Text("Mac Health Checkup")
                .font(.title.bold())
                .foregroundStyle(.white)
            Text("Connect to your Mac agent to view diagnostics.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(.top, 14)
    }

    private var _pairingCard: some View {
        /**
         Summary
         Render the pairing input card with import and connection controls.

         Inputs
         None.

         Outputs
         SwiftUI view.

         Side effects
         Invokes callbacks for connect, test, and token reset.

         Error handling
         Displays validation and connection errors inline.

         Ties to other methods
         Used by `body`.

         Why this exists
         Keeps the primary actions grouped in a clean and touch-friendly surface.
         */
        VStack(spacing: 12) {
            VStack(spacing: 10) {
                TextField("Agent URL (example: https://192.168.1.10:7878)", text: $urlText)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)
                    .textFieldStyle(.roundedBorder)

                VStack(alignment: .leading, spacing: 6) {
                    SecureField("Auth token", text: $tokenText)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .textFieldStyle(.roundedBorder)

                    if storedTokenAvailable && tokenText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        Text("Using stored token")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            HStack(spacing: 10) {
                Button {
                    _pastePairing()
                } label: {
                    Label("Paste", systemImage: "doc.on.clipboard")
                }
                .buttonStyle(.bordered)

                Button {
                    showScanner = true
                } label: {
                    Label("Scan QR", systemImage: "qrcode.viewfinder")
                }
                .buttonStyle(.bordered)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            if let healthStatusText, !healthStatusText.isEmpty {
                Text(healthStatusText)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            if let errorMessage, !errorMessage.isEmpty {
                Text(errorMessage)
                    .font(.footnote)
                    .foregroundStyle(.red)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            HStack(spacing: 10) {
                Button {
                    onTest(urlText, tokenText)
                } label: {
                    HStack(spacing: 8) {
                        Text("Test")
                        if isTestingConnection {
                            ProgressView()
                                .controlSize(.small)
                        }
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .disabled(!_canSubmit(allowEmptyTokenWhenStored: true) || isTestingConnection)

                Button {
                    _haptic(.success)
                    onConnect(urlText, tokenText)
                } label: {
                    Text("Connect")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(!_canSubmit(allowEmptyTokenWhenStored: storedTokenAvailable))
            }

            if storedTokenAvailable {
                Button("Forget stored token", role: .destructive) {
                    showForgetTokenConfirmation = true
                }
                .font(.footnote)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(16)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var _macInstructions: some View {
        /**
         Summary
         Render setup instructions for enabling the Mac agent API.

         Inputs
         None.

         Outputs
         SwiftUI view.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `body`.

         Why this exists
         Smooth pairing depends on clear, actionable steps on the Mac side.
         */
        VStack(alignment: .leading, spacing: 8) {
            Text("On your Mac")
                .font(.headline)
                .foregroundStyle(.white)
            Text("1) In the project directory, run `.venv/bin/python run.py --agent`.\n2) Paste the printed pairing payload here, or scan its QR code.\n3) Keep the Mac agent running while using the companion app.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 4)
    }

    private func _canSubmit(allowEmptyTokenWhenStored: Bool) -> Bool {
        /**
         Summary
         Validate whether the current inputs are sufficient to attempt connect or test actions.

         Inputs
         allowEmptyTokenWhenStored: Whether a missing token is acceptable when a stored token exists.

         Outputs
         True when inputs are acceptable.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by button disabled states.

         Why this exists
         Avoids triggering predictable failures and makes the UI harder to misuse.
         */
        let urlOk = !urlText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        let tokenOk = !tokenText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || (allowEmptyTokenWhenStored && storedTokenAvailable)
        return urlOk && tokenOk
    }

    private func _pastePairing() {
        /**
         Summary
         Import pairing text from the system clipboard.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Reads UIPasteboard and may update input fields.

         Error handling
         Shows an alert when clipboard parsing fails.

         Ties to other methods
         Invoked by the Paste button.

         Why this exists
         Clipboard import is a fast fallback when QR scanning is not available.
         */
        guard let value = UIPasteboard.general.string, !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            _showImportError("Clipboard is empty.")
            return
        }
        _importPairingText(value)
    }

    private func _importPairingText(_ text: String) {
        /**
         Summary
         Parse a pairing payload string and apply it to the URL and token fields.

         Inputs
         text: Raw payload from QR code or clipboard.

         Outputs
         None.

         Side effects
         Updates `urlText` and `tokenText` on success.

         Error handling
         Displays a user-facing error on parse failure.

         Ties to other methods
         Used by QR and clipboard import flows.

         Why this exists
         Keeps input parsing centralized so imports behave consistently across entry points.
         */
        do {
            let result = try PairingImportParser.parse(text: text)
            urlText = result.baseURL
            tokenText = result.token
            if !result.tlsFingerprintSHA256.isEmpty {
                onImportedTLSFingerprint(result.tlsFingerprintSHA256)
            }
            _haptic(.success)
        } catch {
            _showImportError(String(describing: error))
            _haptic(.error)
        }
    }

    private func _showImportError(_ message: String) {
        /**
         Summary
         Surface an import error via an alert.

         Inputs
         message: User-visible message.

         Outputs
         None.

         Side effects
         Updates view state to display an alert.

         Error handling
         None.

         Ties to other methods
         Used by import flows.

         Why this exists
         Makes failures actionable without breaking the pairing flow.
         */
        importErrorMessage = message
        showImportError = true
    }

    private func _haptic(_ type: UINotificationFeedbackGenerator.FeedbackType) {
        /**
         Summary
         Trigger a simple notification haptic.

         Inputs
         type: Feedback type.

         Outputs
         None.

         Side effects
         Plays a haptic if available.

         Error handling
         None.

         Ties to other methods
         Used for connect, test, and import interactions.

         Why this exists
         Adds subtle tactile feedback for a more premium native iOS feel.
         */
        let gen = UINotificationFeedbackGenerator()
        gen.prepare()
        gen.notificationOccurred(type)
    }
}

private struct PairingImport: Sendable, Equatable {
    let baseURL: String
    let token: String
    let tlsFingerprintSHA256: String
}

private enum PairingImportParser {
    enum ParseError: Error, CustomStringConvertible {
        case invalidPayload(message: String)

        var description: String {
            switch self {
            case let .invalidPayload(message):
                return "PairingImportParser.parse: \(message)"
            }
        }
    }

    static func parse(text: String) throws -> PairingImport {
        /**
         Summary
         Parse a pairing payload into URL and token values.

         Inputs
         text: Raw payload string.

         Outputs
         Parsed `PairingImport`.

         Side effects
         None.

         Error handling
         Throws `ParseError` when parsing fails or required values are missing.

         Ties to other methods
         Used by pairing import actions in `PairingView`.

         Why this exists
         Supports multiple import formats without duplicating parsing logic in the UI.
         */
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            throw ParseError.invalidPayload(message: "Empty payload")
        }

        let urlPayload = try _parseAsURLPayload(trimmed)
        if let urlPayload {
            return urlPayload
        }

        let jsonPayload = try _parseAsJSON(trimmed)
        if let jsonPayload {
            return jsonPayload
        }

        if let importFromKeyValue = _parseAsKeyValueLines(trimmed) {
            return importFromKeyValue
        }

        throw ParseError.invalidPayload(message: "Unsupported format. Expected URL, JSON, or key-value lines.")
    }

    private static func _parseAsURLPayload(_ text: String) throws -> PairingImport? {
        /**
         Summary
         Parse a URL-like payload such as `machealthcheckup://pair?url=...&token=...`.

         Inputs
         text: Raw payload.

         Outputs
         Optional parsed import.

         Side effects
         None.

         Error handling
         Throws on malformed URL components.

         Ties to other methods
         Used by `parse`.

         Why this exists
         URL payloads are a simple transport for QR codes and deep links.
         */
        guard let components = URLComponents(string: text) else { return nil }
        guard let queryItems = components.queryItems, !queryItems.isEmpty else { return nil }
        let urlValue = queryItems.first(where: { $0.name.lowercased() == "url" })?.value
        let tokenValue = queryItems.first(where: { $0.name.lowercased() == "token" })?.value
        let pinValue = queryItems.first(where: { $0.name.lowercased() == "pin" })?.value
        guard let baseURL = urlValue?.trimmingCharacters(in: .whitespacesAndNewlines), !baseURL.isEmpty else { return nil }
        guard let token = tokenValue?.trimmingCharacters(in: .whitespacesAndNewlines), !token.isEmpty else {
            throw ParseError.invalidPayload(message: "URL payload missing token")
        }
        let pin = (pinValue ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return PairingImport(baseURL: baseURL, token: token, tlsFingerprintSHA256: pin)
    }

    private static func _parseAsJSON(_ text: String) throws -> PairingImport? {
        /**
         Summary
         Parse a JSON payload like `{ "url": "...", "token": "..." }`.

         Inputs
         text: Raw payload.

         Outputs
         Optional parsed import.

         Side effects
         None.

         Error handling
         Throws for invalid JSON structures.

         Ties to other methods
         Used by `parse`.

         Why this exists
         JSON is a convenient interchange format for copy-paste pairing blobs.
         */
        struct Payload: Decodable {
            let url: String
            let token: String
            let pin: String?
        }
        guard text.first == "{" else { return nil }
        guard let data = text.data(using: .utf8) else { return nil }
        let decoded: Payload
        do {
            decoded = try JSONDecoder().decode(Payload.self, from: data)
        } catch {
            return nil
        }
        let baseURL = decoded.url.trimmingCharacters(in: .whitespacesAndNewlines)
        let token = decoded.token.trimmingCharacters(in: .whitespacesAndNewlines)
        if baseURL.isEmpty || token.isEmpty {
            throw ParseError.invalidPayload(message: "JSON payload must include non-empty url and token")
        }
        let pin = (decoded.pin ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return PairingImport(baseURL: baseURL, token: token, tlsFingerprintSHA256: pin)
    }

    private static func _parseAsKeyValueLines(_ text: String) -> PairingImport? {
        /**
         Summary
         Parse key-value lines like `url=...` and `token=...`.

         Inputs
         text: Raw payload.

         Outputs
         Optional parsed import.

         Side effects
         None.

         Error handling
         Returns nil on parse failure.

         Ties to other methods
         Used by `parse`.

         Why this exists
         Provides a forgiving format for manual copy-paste and terminal outputs.
         */
        let lines = text.split(whereSeparator: \.isNewline).map { String($0) }
        var url: String?
        var token: String?
        var pin: String?

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.lowercased().hasPrefix("url=") {
                url = String(trimmed.dropFirst(4))
            } else if trimmed.lowercased().hasPrefix("token=") {
                token = String(trimmed.dropFirst(6))
            } else if trimmed.lowercased().hasPrefix("pin=") {
                pin = String(trimmed.dropFirst(4))
            }
        }

        guard let baseURL = url?.trimmingCharacters(in: .whitespacesAndNewlines), !baseURL.isEmpty else { return nil }
        guard let tok = token?.trimmingCharacters(in: .whitespacesAndNewlines), !tok.isEmpty else { return nil }
        let tlsPin = (pin ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return PairingImport(baseURL: baseURL, token: tok, tlsFingerprintSHA256: tlsPin)
    }
}
