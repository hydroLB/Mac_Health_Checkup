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

        #if os(macOS)
        AppDelegate.windowConfiguration = WindowConfiguration(
            title: appTitle ?? "Mac Health Checkup",
            rootView: AnyView(rootContent)
        )
        #endif
    }

    @ViewBuilder
    private var rootContent: some View {
        /**
         Summary
         Build the root dashboard content or startup failure fallback.

         Inputs
         None.

         Outputs
         SwiftUI view used by the app's main window scene.

         Side effects
         None.

         Error handling
         Startup failures are rendered via `StartupFailureView` instead of crashing.

         Ties to other methods
         Used by `body` to keep scene declarations focused on macOS window management.

         Why this exists
         The native app now uses a single explicit macOS window, so the actual content should be reusable without
         duplicating the success and failure branches.
         */
        if let model {
            RootView(model: model)
                .frame(minWidth: 940, minHeight: 640)
        } else {
            StartupFailureView(error: startupError)
                .frame(minWidth: 760, minHeight: 420)
        }
    }

    var body: some Scene {
        Settings {
            EmptyView()
        }
    }
}

#if os(macOS)
private struct WindowConfiguration {
    let title: String
    let rootView: AnyView
}

@MainActor
private final class AppDelegate: NSObject, NSApplicationDelegate {
    static var windowConfiguration: WindowConfiguration?

    private var window: NSWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        /**
         Summary
         Create and focus the primary dashboard window for the Swift package executable.

         Inputs
         notification: AppKit launch notification.

         Outputs
         None.

         Side effects
         Forces activation policy to `.regular`, creates an `NSWindow` hosting the SwiftUI root view, activates the
         app, and brings the window to the front.

         Error handling
         None.

         Ties to other methods
         Uses `_makeWindow` and `_bringToFront`.

         Why this exists
         Swift Package executables can fail to materialize a visible SwiftUI scene when launched via `swift run`.
         Creating the window explicitly restores deterministic native app behavior for users and automation.
         */
        _ = notification
        NSApp.setActivationPolicy(.regular)
        if window == nil {
            window = _makeWindow()
        }

        DispatchQueue.main.async {
            self._bringToFront()
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
            self._bringToFront()
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        /**
         Summary
         Reopen the dashboard window when the dock icon is clicked after the window was closed or hidden.

         Inputs
         sender: Owning application instance.
         flag: Whether a visible window already exists.

         Outputs
         True to indicate the reopen request was handled.

         Side effects
         Recreates the main window when needed and brings it to the front.

         Error handling
         None.

         Ties to other methods
         Uses `_makeWindow` and `_bringToFront`.

         Why this exists
         Users expect a single-window macOS app to reopen predictably from the dock without requiring a relaunch.
         */
        _ = sender
        if !flag, window == nil {
            window = _makeWindow()
        }
        _bringToFront()
        return true
    }

    private func _makeWindow() -> NSWindow {
        /**
         Summary
         Create the primary dashboard window and attach the SwiftUI root view.

         Inputs
         None.

         Outputs
         Configured `NSWindow`.

         Side effects
         Instantiates AppKit window and hosting controller objects.

         Error handling
         Falls back to a small diagnostic view when configuration is missing unexpectedly.

         Ties to other methods
         Used by `applicationDidFinishLaunching` and `applicationShouldHandleReopen`.

         Why this exists
         Keeping window construction in one place makes launch and reopen behavior consistent and testable.
         */
        let configuration = Self.windowConfiguration ?? WindowConfiguration(
            title: "Mac Health Checkup",
            rootView: AnyView(
                StartupFailureView(
                    error: AppError.context(
                        #fileID,
                        #function,
                        "AppDelegate.windowConfiguration missing during launch"
                    )
                )
            )
        )
        let hostingController = NSHostingController(rootView: configuration.rootView)
        let window = NSWindow(contentViewController: hostingController)
        window.title = configuration.title
        window.styleMask = [.titled, .closable, .miniaturizable, .resizable]
        window.setContentSize(NSSize(width: 940, height: 640))
        window.minSize = NSSize(width: 760, height: 420)
        window.center()
        window.isReleasedWhenClosed = false
        return window
    }

    private func _bringToFront() {
        /**
         Summary
         Activate the app and show the primary window.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Brings the window forward and makes it key.

         Error handling
         None.

         Ties to other methods
         Used by `applicationDidFinishLaunching` and `applicationShouldHandleReopen`.

         Why this exists
         Terminal-launched GUI processes can start behind other apps unless activation is made explicit.
         */
        if window == nil {
            window = _makeWindow()
        }
        NSApp.activate(ignoringOtherApps: true)
        window?.makeKeyAndOrderFront(nil)
        window?.orderFrontRegardless()
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
