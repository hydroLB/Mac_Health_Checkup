import SwiftUI
import MacHealthCheckupCore
import MacHealthCheckupUI

struct MobileRootView: View {
    /**
     Summary
     Route between pairing UI and the connected dashboard UI.

     Inputs
     state: Mobile app state.

     Outputs
     A SwiftUI view.

     Side effects
     Reads and writes pairing values via `@AppStorage`.

     Error handling
     Displays validation and connection errors inline.

     Ties to other methods
     Uses `PairingView` and `RootView`.

     Why this exists
     Provides a polished iOS-first experience with a clear pairing step.
     */

    @ObservedObject var state: MobileAppState

    @AppStorage("agentBaseURL") private var agentBaseURL: String = ""
    @AppStorage("refreshIntervalMs") private var refreshIntervalMs: Int = 5000
    @AppStorage("tlsPin") private var tlsPin: String = ""

    var body: some View {
        if let model = state.model {
            TabView {
                RootView(model: model)
                    .tabItem { Label("Dashboard", systemImage: "waveform.path.ecg") }

                SettingsView(
                    agentBaseURL: $agentBaseURL,
                    refreshIntervalMs: $refreshIntervalMs,
                    tlsPin: $tlsPin,
                    theme: model.theme,
                    storedTokenAvailable: state.storedTokenAvailable,
                    isTestingConnection: state.isTestingConnection,
                    healthStatus: state.lastHealthStatus,
                    errorMessage: state.lastError?.userFacingMessage,
                    onSaveToken: { token in state.saveToken(token) },
                    onTestConnection: { typedToken in
                        Task {
                            await state.testConnection(
                                agentBaseURL: agentBaseURL,
                                token: typedToken,
                                pinnedCertificateSHA256: tlsPin
                            )
                        }
                    },
                    onReconnect: {
                        state.disconnect()
                        state.connect(
                            agentBaseURL: agentBaseURL,
                            token: "",
                            pinnedCertificateSHA256: tlsPin,
                            refreshIntervalMs: refreshIntervalMs
                        )
                    },
                    onDisconnect: { state.disconnect() },
                    onForgetPairing: {
                        agentBaseURL = ""
                        tlsPin = ""
                        state.forgetStoredToken()
                        state.disconnect()
                    }
                )
                .tabItem { Label("Settings", systemImage: "gearshape") }
            }
            .onAppear { state.refreshStoredTokenAvailable() }
        } else {
            PairingView(
                agentBaseURL: agentBaseURL,
                storedTokenAvailable: state.storedTokenAvailable,
                isTestingConnection: state.isTestingConnection,
                healthStatusText: _healthStatusText(state.lastHealthStatus),
                errorMessage: state.lastError?.userFacingMessage,
                onTest: { baseURL, token in
                    Task {
                        await state.testConnection(
                            agentBaseURL: baseURL,
                            token: token,
                            pinnedCertificateSHA256: tlsPin
                        )
                    }
                },
                onConnect: { baseURL, token in
                    agentBaseURL = baseURL
                    state.connect(
                        agentBaseURL: baseURL,
                        token: token,
                        pinnedCertificateSHA256: tlsPin,
                        refreshIntervalMs: refreshIntervalMs
                    )
                },
                onForgetStoredToken: { state.forgetStoredToken() },
                onImportedTLSFingerprint: { importedPin in tlsPin = importedPin }
            )
            .onAppear {
                state.refreshStoredTokenAvailable()
                if !agentBaseURL.isEmpty && state.storedTokenAvailable {
                    state.connect(
                        agentBaseURL: agentBaseURL,
                        token: "",
                        pinnedCertificateSHA256: tlsPin,
                        refreshIntervalMs: refreshIntervalMs
                    )
                }
            }
        }
    }

    private func _healthStatusText(_ health: RemoteHealthStatus?) -> String? {
        /**
         Summary
         Format a health status value for simple pairing display.

         Inputs
         health: Optional remote health status.

         Outputs
         Optional user-facing string.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by the pairing screen to show a one-line connectivity result.

         Why this exists
         Keeps formatting decisions outside the core networking layer.
         */
        guard let health else { return nil }
        return "Reachable (HTTP \(health.httpStatus), ~\(health.roundTripMs)ms)"
    }
}
