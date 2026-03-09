import SwiftUI
import MacHealthCheckupCore

public struct RootView: View {
    /**
     Summary
     Render the main SwiftUI dashboard shell with navigation and detail views.

     Inputs
     theme: Theme values used across the UI.
     model: Dashboard view model.

     Outputs
     A SwiftUI view hierarchy.

     Side effects
     Starts and stops auto-refresh.

     Error handling
     Displays errors via an inline banner and details sheet.

     Ties to other methods
     Uses `SidebarView` and `DetailView`.

     Why this exists
     Keeps the UI structure consistent and native-feeling with a sidebar + detail layout.
     */

    @StateObject public var model: DashboardViewModel
    @State private var showErrorDetails: Bool = false

    public init(model: DashboardViewModel) {
        _model = StateObject(wrappedValue: model)
    }

    public var body: some View {
        /**
         Summary
         Render the application shell with navigation, refresh controls, and error surfacing.

         Inputs
         None.

         Outputs
         A SwiftUI view hierarchy.

         Side effects
         Starts auto-refresh and may present an error details sheet.

         Error handling
         Displays non-fatal backend errors via a banner and detail sheet.

         Ties to other methods
         Uses `SidebarView`, `DetailView`, and `DashboardViewModel.startAutoRefresh`.

         Why this exists
         Keeps global app chrome consistent and avoids duplicating refresh and error UI across screens.
         */
        NavigationSplitView {
            SidebarView(model: model)
        } detail: {
            VStack(spacing: 0) {
                if let err = model.lastError {
                    ErrorBanner(theme: model.theme, message: err.userFacingMessage) {
                        showErrorDetails = true
                    }
                    .padding(.horizontal, model.theme.layout.pagePadding)
                    .padding(.top, max(10, model.theme.layout.pagePadding * 0.6))
                    .padding(.bottom, max(8, model.theme.layout.cardSpacing * 0.5))
                }

                DetailView(model: model)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }
            .background(model.theme.colors.background)
        }
        .toolbar {
            #if os(macOS)
            ToolbarItem(placement: .primaryAction) {
                Button {
                    model.openSettings()
                } label: {
                    Image(systemName: "gearshape")
                }
                .help("Settings")
            }
            #else
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    model.openSettings()
                } label: {
                    Image(systemName: "gearshape")
                }
            }
            #endif
        }
        .background(model.theme.colors.background)
        .task { model.startAutoRefresh() }
        .onDisappear { model.stopAutoRefresh() }
        .sheet(isPresented: $showErrorDetails) {
            NavigationStack {
                ErrorDetailView(theme: model.theme, error: model.lastError)
                    .navigationTitle("Error Details")
#if os(iOS)
                    .navigationBarTitleDisplayMode(.inline)
#endif
                    .toolbar {
                        ToolbarItem(placement: .confirmationAction) {
                            Button("Done") {
                                showErrorDetails = false
                            }
                        }
                    }
            }
#if os(iOS)
            .presentationDragIndicator(.visible)
            .presentationDetents([.medium, .large])
#endif
        }
        .sheet(isPresented: $model.isSettingsPresented) {
            SettingsView(theme: model.theme, model: model)
                .frame(minWidth: 560, minHeight: 520)
                .background(model.theme.colors.background)
        }
    }
}

private struct ErrorBanner: View {
    let theme: Theme
    let message: String
    let onDetails: () -> Void

    var body: some View {
        /**
         Summary
         Render a compact error banner with an optional details action.

         Inputs
         None.

         Outputs
         A SwiftUI view for error display.

         Side effects
         Invokes the details callback when requested.

         Error handling
         None.

         Ties to other methods
         Used by `RootView` to surface backend and refresh warnings.

         Why this exists
         Keeps non-fatal errors visible without interrupting user workflows.
         */
        HStack(spacing: 10) {
            Text(message)
                .font(theme.fonts.caption)
                .foregroundStyle(theme.colors.foreground)
                .multilineTextAlignment(.leading)
                .lineLimit(2)
                .truncationMode(.tail)
                .fixedSize(horizontal: false, vertical: true)
                .layoutPriority(1)
            Spacer()
            Button("Details", action: onDetails)
                .font(theme.fonts.caption)
                .buttonStyle(.bordered)
                .controlSize(.small)
        }
        .padding(10)
        .background(theme.colors.bad.opacity(0.18))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(theme.colors.bad.opacity(0.5), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

private struct ErrorDetailView: View {
    let theme: Theme
    let error: AppError?

    var body: some View {
        /**
         Summary
         Render a detailed error sheet.

         Inputs
         None.

         Outputs
         A SwiftUI view displayed as a modal sheet.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Presented by `RootView` when the user requests error details.

         Why this exists
         Provides an accessible place to copy and inspect failure details.
         */
        VStack(alignment: .leading, spacing: 12) {
            let summary = error?.userFacingMessage ?? "No error"
            let technical = error.map { String(describing: $0) } ?? "No error"
            let underlying = error?.underlying.map { String(describing: $0) }?.trimmingCharacters(
                in: .whitespacesAndNewlines
            )

            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Summary")
                        .font(theme.fonts.sectionTitle)
                        .foregroundStyle(theme.colors.section)
                    Text(summary)
                        .font(theme.fonts.body)
                        .foregroundStyle(theme.colors.foreground)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    if let underlying, !underlying.isEmpty {
                        Divider().overlay(theme.colors.cardBorder)
                        Text("Underlying Error")
                            .font(theme.fonts.caption)
                            .foregroundStyle(theme.colors.label)
                        Text(underlying)
                            .font(theme.fonts.mono)
                            .foregroundStyle(theme.colors.field)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }

                    Divider().overlay(theme.colors.cardBorder)
                    Text("Technical Details")
                        .font(theme.fonts.caption)
                        .foregroundStyle(theme.colors.label)
                    Text(technical)
                        .font(theme.fonts.mono)
                        .foregroundStyle(theme.colors.field)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.bottom, 20)
            }
        }
        .padding(16)
        .frame(minWidth: 520, minHeight: 260)
        .background(theme.colors.background)
    }
}
