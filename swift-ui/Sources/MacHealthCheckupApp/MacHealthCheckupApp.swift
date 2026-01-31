import SwiftUI
import MacHealthCheckupCore
import MacHealthCheckupUI

#if os(macOS)
import AppKit
#endif

@main
struct MacHealthCheckupApp: App {
    /**
     Summary
     SwiftUI application entrypoint for the native dashboard.

     Inputs
     None.

     Outputs
     A single-window app.

     Side effects
     Loads config and initializes backend dependencies at startup.

     Error handling
     Displays a fatal error view when startup fails.

     Ties to other methods
     Uses `AppBootstrap.load` and `RootView`.

     Why this exists
     Provides a native SwiftUI shell around the existing Python diagnostics backend.
     */

    private let model: DashboardViewModel?
    private let appTitle: String?
    private let startupError: AppError?

    #if os(macOS)
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    #endif

    @MainActor
    init() {
        do {
            let (theme, model, title) = try AppBootstrap.load()
            _ = theme
            self.model = model
            self.appTitle = title
            self.startupError = nil
        } catch let error as AppError {
            self.model = nil
            self.appTitle = nil
            self.startupError = error
        } catch {
            self.model = nil
            self.appTitle = nil
            self.startupError = AppError.context(#fileID, #function, "Startup failed", error)
        }
    }

    var body: some Scene {
        WindowGroup(appTitle ?? "Mac Health Checkup") {
            if let model {
                RootView(model: model)
                    .frame(minWidth: 940, minHeight: 640)
            } else {
                StartupFailureView(error: startupError)
                    .frame(minWidth: 760, minHeight: 420)
            }
        }
    }
}

#if os(macOS)
private final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        /**
         Summary
         Ensure the SwiftUI window becomes visible and focused when launched from a terminal or IDE.

         Inputs
         notification: AppKit launch notification.

         Outputs
         None.

         Side effects
         Forces activation policy to `.regular`, activates the app, and brings the first window to the front.

         Error handling
         None.

         Ties to other methods
         Runs before the SwiftUI `WindowGroup` is interacted with by the user.

         Why this exists
         SwiftUI apps launched via `swift run` can start without becoming the active app, making the window appear "missing".
         */
        _ = notification
        NSApp.setActivationPolicy(.regular)

        func bringToFront() {
            NSApp.activate(ignoringOtherApps: true)
            NSApp.windows.first?.makeKeyAndOrderFront(nil)
        }

        DispatchQueue.main.async {
            bringToFront()
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
            bringToFront()
        }
    }
}
#endif

private struct StartupFailureView: View {
    let error: AppError?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Mac Health Checkup UI failed to start")
                .font(.system(size: 18, weight: .semibold))
            Text(error?.description ?? "Unknown error")
                .font(.system(size: 13))
                .textSelection(.enabled)
            Spacer()
        }
        .padding(18)
    }
}
