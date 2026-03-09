import SwiftUI
import MacHealthCheckupCore
import MacHealthCheckupUI

@main
struct MacHealthCheckupMobileApp: App {
    /**
     Summary
     iOS application entrypoint for the native Mac Health Checkup client.

     Inputs
     None.

     Outputs
     A SwiftUI app scene.

     Side effects
     Reads persisted pairing settings and performs network requests to the agent when configured.

     Error handling
     Displays pairing and error states in the UI instead of crashing.

     Ties to other methods
     Uses `MobileAppState` to manage pairing settings and create a `DashboardViewModel`.

     Why this exists
     A proper iOS app cannot run macOS diagnostics locally, so it must act as a secure remote client.
     */

    @StateObject private var state = MobileAppState()

    var body: some Scene {
        WindowGroup {
            MobileRootView(state: state)
        }
    }
}

