import MacHealthCheckupCore
import MacHealthCheckupUI
import SwiftUI

struct SettingsView: View {
    /**
     Summary
     Render a native iOS settings screen for connection, refresh, and security controls.

     Inputs
     agentBaseURL: Persisted agent base URL binding.
     refreshIntervalMs: Persisted refresh interval binding.
     storedTokenAvailable: Whether a token is stored in secure storage.
     isTestingConnection: Whether a connection test is in progress.
     healthStatus: Most recent health check result.
     errorMessage: Optional error message to surface.
     onSaveToken: Save a new token to secure storage.
     onTestConnection: Trigger a health test.
     onReconnect: Rebuild the dashboard model using current settings.
     onDisconnect: Disconnect without erasing pairing settings.
     onForgetPairing: Disconnect and forget settings and credentials.

     Outputs
     A SwiftUI settings view.

     Side effects
     Calls provided callbacks that persist settings and perform network requests.

     Error handling
     Displays errors inline when provided.

     Ties to other methods
     Used by `MobileRootView` to provide a proper iOS app settings experience.

     Why this exists
     A sleek native app should expose configuration and credential management without forcing app restarts.
     */

    @Binding var agentBaseURL: String
    @Binding var refreshIntervalMs: Int
    @Binding var tlsPin: String

    let theme: Theme
    let storedTokenAvailable: Bool
    let isTestingConnection: Bool
    let healthStatus: RemoteHealthStatus?
    let errorMessage: String?

    let onSaveToken: (String) -> Void
    let onTestConnection: (String) -> Void
    let onReconnect: () -> Void
    let onDisconnect: () -> Void
    let onForgetPairing: () -> Void

    @State private var tokenText: String = ""
    @State private var showForgetPairingConfirmation: Bool = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Connection") {
                    TextField("Agent URL", text: $agentBaseURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)

                    TLSFingerprintView(tlsPin: $tlsPin)

                    VStack(alignment: .leading, spacing: 6) {
                        SecureField("New token (stored in Keychain)", text: $tokenText)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()

                        HStack(spacing: 10) {
                            Button("Save Token") {
                                onSaveToken(tokenText)
                                tokenText = ""
                            }
                            .disabled(tokenText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

                            if storedTokenAvailable && tokenText.isEmpty {
                                Text("Using stored token")
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }

                    Button {
                        onTestConnection(tokenText)
                    } label: {
                        HStack {
                            Text("Test Connection")
                            Spacer()
                            if isTestingConnection {
                                ProgressView()
                            }
                        }
                    }
                    .disabled(agentBaseURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || (!storedTokenAvailable && tokenText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty))

                    if let healthStatus {
                        Text("Reachable (HTTP \(healthStatus.httpStatus), ~\(healthStatus.roundTripMs)ms)")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("Refresh") {
                    Stepper(value: $refreshIntervalMs, in: 1000...60000, step: 1000) {
                        Text("Interval: \(max(1, refreshIntervalMs / 1000))s")
                    }
                    Text("Changes apply on reconnect.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    Button("Reconnect") { onReconnect() }
                        .disabled(agentBaseURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !storedTokenAvailable)
                }

                if let errorMessage, !errorMessage.isEmpty {
                    Section("Status") {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                            .font(.footnote)
                    }
                }

                Section {
                    Button("Disconnect") { onDisconnect() }
                    Button("Forget Pairing", role: .destructive) {
                        showForgetPairingConfirmation = true
                    }
                } footer: {
                    Text("Forget Pairing clears the URL and removes the stored token from Keychain.")
                }
            }
            .navigationTitle("Settings")
            .tint(theme.colors.section)
            .scrollContentBackground(.hidden)
            .background(theme.colors.background.ignoresSafeArea())
        }
        .confirmationDialog(
            "Forget this Mac?",
            isPresented: $showForgetPairingConfirmation,
            titleVisibility: .visible
        ) {
            Button("Forget Pairing", role: .destructive) { onForgetPairing() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This removes the agent URL, certificate pin, and stored token from this iPhone.")
        }
    }
}
