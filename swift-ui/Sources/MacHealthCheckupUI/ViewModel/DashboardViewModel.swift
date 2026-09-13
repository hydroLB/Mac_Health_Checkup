import Foundation
import MacHealthCheckupCore

@MainActor
public final class DashboardViewModel: ObservableObject {
    /**
     Summary
     Drive dashboard state for the SwiftUI UI with periodic refresh.

     Inputs
     backend: Backend client for fetching snapshots.
     sections: Ordered section descriptors for navigation.
     refreshIntervalMs: Auto-refresh interval in milliseconds.

     Outputs
     Published UI state including current snapshot and error details.

     Side effects
     Spawns async tasks for periodic refresh.

     Error handling
     Captures errors into `lastError` and keeps the UI responsive.

     Ties to other methods
     Used by `RootView` to render a native SwiftUI dashboard.

     Why this exists
     Centralizes refresh logic so views remain simple and consistent.
     */

    private let backend: any SnapshotBackend
    @Published public var sections: [SectionDescriptor]
    private let refreshIntervalMs: Int
    private let fanRefreshIntervalMs: Int
    private let scrollableRows: [String: Int]
    private let backendTimeoutSeconds: TimeInterval
    private let snapshotCacheFile: URL?
    private let history: MetricHistoryStore?
    private let visibilityStore: SectionVisibilityStore

    @Published public var selectedSectionKey: String?
    @Published public var snapshot: Snapshot?
    @Published private var sectionOverrideByKey: [String: SnapshotSection] = [:]
    @Published public var lastRefreshAt: Date?
    @Published public var lastError: AppError?
    @Published public var isRefreshing: Bool = false
    @Published public var refreshStartedAt: Date?
    @Published public var sectionSearchText: String = ""
    @Published public var theme: Theme
    @Published public var appTitle: String
    @Published public var isSettingsPresented: Bool = false

    private var snapshotRefreshTask: Task<Void, Never>?
    private var fanRefreshTask: Task<Void, Never>?
    private var isFanRefreshInFlight: Bool = false

    nonisolated public static let overviewKey: String = "_overview"

    public init(
        backend: any SnapshotBackend,
        sections: [SectionDescriptor],
        refreshIntervalMs: Int,
        fanRefreshIntervalMs: Int,
        scrollableRows: [String: Int],
        backendTimeoutSeconds: TimeInterval = 60,
        snapshotCacheFile: URL? = nil,
        historyFile: URL? = nil,
        historyEnabled: Bool = false,
        historyRetentionMinutes: Int = 60,
        historyMaxPointsPerSeries: Int = 3600,
        historySaveIntervalSeconds: Int = 10,
        initialTheme: Theme,
        appTitle: String
    ) {
        /**
         Summary
         Initialize the dashboard view model.

         Inputs
         backend: Backend client for fetching snapshots.
         sections: Ordered section descriptors for navigation.
         refreshIntervalMs: Auto-refresh interval in milliseconds.
         scrollableRows: Per-section preferred visible row counts for tables.
         backendTimeoutSeconds: Hard timeout for the backend snapshot process.
         snapshotCacheFile: Optional on-disk snapshot cache for fast startup.
         historyFile: Optional on-disk metrics history file.
         historyEnabled: Toggle for history capture and persistence.
         historyRetentionMinutes: Maximum minutes to retain.
         historyMaxPointsPerSeries: Cap per series.
         historySaveIntervalSeconds: Minimum seconds between writes.

         Outputs
         None.

         Side effects
         Initializes published state including the default selected section.

         Error handling
         None.

         Ties to other methods
         Called by `AppBootstrap.load` during app startup.

         Why this exists
         Makes UI behavior tunable from config while keeping view logic minimal.
         */
        self.backend = backend
        self.sections = sections
        self.refreshIntervalMs = refreshIntervalMs
        self.fanRefreshIntervalMs = fanRefreshIntervalMs
        self.scrollableRows = scrollableRows
        self.backendTimeoutSeconds = backendTimeoutSeconds
        self.snapshotCacheFile = snapshotCacheFile
        self.theme = initialTheme
        self.appTitle = appTitle
        self.visibilityStore = SectionVisibilityStore()
        self.selectedSectionKey = Self.overviewKey
        self.isSettingsPresented = false
        if historyEnabled {
            self.history = MetricHistoryStore(
                fileURL: historyFile,
                retentionMinutes: historyRetentionMinutes,
                maxPointsPerSeries: historyMaxPointsPerSeries,
                saveIntervalSeconds: historySaveIntervalSeconds
            )
        } else {
            self.history = nil
        }

        _loadCachedSnapshotIfAvailable()
    }

    public var hiddenSectionKeys: Set<String> {
        /**
         Summary
         Expose the current hidden section keys.

         Inputs
         None.

         Outputs
         Set of hidden section keys.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `SettingsView` and section filtering.

         Why this exists
         The UI needs a simple way to display and toggle section visibility without leaking persistence details.
         */
        visibilityStore.hiddenSectionKeys
    }

    public var visibleSections: [SectionDescriptor] {
        /**
         Summary
         Return the ordered section descriptors that are visible in the sidebar and overview.

         Inputs
         None.

         Outputs
         Ordered visible sections.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `SidebarView` and `OverviewView`.

         Why this exists
         Centralizes filtering so both navigation and overview remain consistent.
         */
        DashboardSectionNavigation.visibleSections(
            from: sections,
            isSectionHidden: { [weak self] key in
                self?._isSectionHiddenFromPrimaryUI(key: key) ?? false
            }
        )
    }

    public func setSectionHidden(_ hidden: Bool, key: String) {
        /**
         Summary
         Persistently hide or show a section key and keep selection valid.

         Inputs
         hidden: Whether the section should be hidden.
         key: Section key to update.

         Outputs
         None.

         Side effects
         Writes UserDefaults and may change selected section.

         Error handling
         None.

         Ties to other methods
         Called by `SettingsView`.

         Why this exists
         Hiding the currently selected section should not leave the UI stuck on an invisible destination.
        */
        visibilityStore.setHidden(hidden, key: key)
        objectWillChange.send()
        _normalizeSelectedSection()
    }

    public func resetSectionVisibility() {
        /**
         Summary
         Clear all hidden sections.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Writes UserDefaults and triggers UI updates.

         Error handling
         None.

         Ties to other methods
         Used by `SettingsView`.

         Why this exists
         Provides an idiot-proof way to recover when too many sections are hidden.
        */
        visibilityStore.reset()
        objectWillChange.send()
        _normalizeSelectedSection()
    }

    public func isSectionAutomaticallyHidden(key: String) -> Bool {
        /**
         Summary
         Report whether a section is currently hidden because its data could not be read.

         Inputs
         key: Section key to evaluate.

         Outputs
         True when the latest payload indicates an availability or access failure.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `SettingsView` and `visibleSections`.

         Why this exists
         Settings should explain why a section is absent from the main UI without duplicating diagnostics heuristics.
         */
        _isSectionAutomaticallyHidden(key: key)
    }

    public var refreshStatusText: String? {
        /**
         Summary
         Provide a user-facing status string for the current refresh when one is in progress.

         Inputs
         None.

         Outputs
         Optional string describing refresh progress, or nil when not refreshing.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by overview and detail views to display a generic refresh progress label.

         Why this exists
         The initial snapshot may take time; a small status hint prevents the UI from feeling stuck without exposing collector internals.
         */
        guard isRefreshing else { return nil }
        return "Refreshing…"
    }

    public var sidebarSections: [SectionDescriptor] {
        /**
         Summary
         Return section descriptors for the sidebar including an Overview entry and optional filtering.

         Inputs
         None.

         Outputs
         Ordered array of `SectionDescriptor`.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `SidebarView` to render the navigation list.

         Why this exists
         Provides a consistent, searchable navigation model without duplicating filtering logic in views.
         */
        DashboardSectionNavigation.sidebarSections(
            from: sections,
            overviewKey: Self.overviewKey,
            searchText: sectionSearchText,
            isSectionHidden: { [weak self] key in
                self?._isSectionHiddenFromPrimaryUI(key: key) ?? false
            }
        )
    }

    public func startAutoRefresh() {
        /**
         Summary
         Start the periodic refresh loop if not already running.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Spawns an async task.

         Error handling
         Captures refresh errors into `lastError`.

         Ties to other methods
         Called by `RootView.task`.

         Why this exists
         Keeps refresh behavior centralized and cancellable.
         */
        if snapshotRefreshTask != nil { return }
        snapshotRefreshTask = Task { [weak self] in
            guard let self else { return }
            await self.refreshOnce()
            while !Task.isCancelled {
                guard await DashboardRefreshScheduler.wait(milliseconds: self.refreshIntervalMs) else {
                    return
                }
                await self.refreshOnce()
            }
        }

        fanRefreshTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                guard await DashboardRefreshScheduler.wait(milliseconds: self.fanRefreshIntervalMs) else {
                    return
                }
                guard self.snapshot != nil else { continue }
                await self.refreshFanOnce()
            }
        }
    }

    public func stopAutoRefresh() {
        /**
         Summary
         Stop the periodic refresh loop.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Cancels the refresh task.

         Error handling
         None.

         Ties to other methods
         Used by `RootView.onDisappear`.

         Why this exists
         Prevents background work from continuing after the UI is closed.
         */
        snapshotRefreshTask?.cancel()
        snapshotRefreshTask = nil
        fanRefreshTask?.cancel()
        fanRefreshTask = nil
    }

    public func refreshOnce() async {
        /**
         Summary
         Fetch a single snapshot and publish it to the UI.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Updates published state.

         Error handling
         Stores an `AppError` in `lastError` and preserves the previous snapshot on failure.

         Ties to other methods
         Called by the auto-refresh loop and the manual refresh action.

        Why this exists
        Keeps snapshot fetching logic consistent and observable.
         */
        if isRefreshing { return }
        refreshStartedAt = Date()
        isRefreshing = true
        defer {
            isRefreshing = false
            refreshStartedAt = nil
        }

        do {
            let response = try await backend.fetchSnapshotResponse()
            snapshot = response.snapshot
            sectionOverrideByKey.removeAll()
            lastRefreshAt = Date()
            _applyThemeIfAvailable(snapshot: response.snapshot)
            _applyCatalogIfAvailable(snapshot: response.snapshot)
            appTitle = response.snapshot.theme.ui.window_title
            lastError = _backendWarningIfAny(exitCode: response.exitCode, snapshot: response.snapshot, stderr: response.stderr)
            if DashboardSnapshotResponsePolicy.shouldCacheFullSnapshot(response) {
                _writeSnapshotCacheIfPossible(rawJSON: response.rawJSON)
            }
            history?.recordSnapshot(response.snapshot)
            _normalizeSelectedSection()
        } catch let error as AppError {
            if _isCancellationError(error) { return }
            lastError = error
        } catch {
            if _isCancellationError(error) { return }
            lastError = AppError.context(#fileID, #function, "Refresh failed", error)
        }
    }

    public func openSettings() {
        /**
         Summary
         Present the settings sheet.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Updates published presentation state used by `RootView`.

         Error handling
         None.

         Ties to other methods
         Called by the toolbar gear and by section CTAs that deep-link into settings.

         Why this exists
         Keeps settings navigation idiot-proof and avoids telling users to hunt for the right card.
         */
        isSettingsPresented = true
    }

    func refreshFanOnce() async {
        /**
         Summary
         Refresh the fan section at a higher cadence than the full snapshot.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Updates `sectionOverrideByKey` for the fan section and records history points.

         Error handling
         Stores non-fatal errors in `lastError` and keeps the last known fan payload.

         Ties to other methods
         Called by `startAutoRefresh` via a dedicated fan refresh task.

         Why this exists
         Fan speeds change quickly; updating them without a full snapshot keeps the UI responsive and reduces backend load.
         */
        if isRefreshing || isFanRefreshInFlight { return }
        isFanRefreshInFlight = true
        defer { isFanRefreshInFlight = false }

        do {
            let response = try await backend.fetchSectionSnapshotResponse(sectionKey: "fan")
            guard let section = DashboardSnapshotResponsePolicy.acceptedSection(
                from: response,
                key: "fan"
            ) else {
                lastError = _backendWarningIfAny(
                    exitCode: response.exitCode,
                    snapshot: response.snapshot,
                    stderr: response.stderr
                ) ?? AppError.context(
                    #fileID,
                    #function,
                    "Fan refresh returned no usable fan section"
                )
                return
            }
            sectionOverrideByKey["fan"] = section
            history?.recordSnapshot(response.snapshot)
        } catch let error as AppError {
            if _isCancellationError(error) { return }
            lastError = error
        } catch {
            if _isCancellationError(error) { return }
            lastError = AppError.context(#fileID, #function, "Fan refresh failed", error)
        }
    }

    private func _isCancellationError(_ error: any Error) -> Bool {
        /**
         Summary
         Decide whether an error represents an expected cancellation.

         Inputs
         error: Error thrown by Swift concurrency tasks or URLSession.

         Outputs
         True when the error is a cancellation and should not be surfaced to the user.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `refreshOnce` and `refreshFanOnce` to avoid showing noisy transient errors.

         Why this exists
         SwiftUI view lifecycle and task cancellation can legitimately cancel in-flight requests; users should not see these as failures.
         */
        if error is CancellationError { return true }
        if let appError = error as? AppError, let underlying = appError.underlying {
            return _isCancellationError(underlying)
        }
        if let urlError = error as? URLError, urlError.code == .cancelled {
            return true
        }
        let ns = error as NSError
        if ns.domain == NSURLErrorDomain && ns.code == NSURLErrorCancelled {
            return true
        }
        return false
    }

    public func sectionPayload(for key: String) -> SnapshotSection? {
        /**
         Summary
         Return the snapshot payload for a specific section key.

         Inputs
         key: Section key.

         Outputs
         `SnapshotSection` or nil when unavailable.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `DetailView` to display section-specific data.

         Why this exists
         Keeps section lookup logic consistent and avoids duplicating filtering in views.
         */
        if let override = sectionOverrideByKey[key] {
            return override
        }
        return snapshot?.sections.first(where: { $0.key == key })
    }

    public func sectionSummaryText(for key: String) -> String {
        /**
         Summary
         Derive a compact, user-facing summary string for a section.

         Inputs
         key: Section key.

         Outputs
         Summary string suitable for overview cards.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by the overview screen to avoid showing "No data yet" when a section publishes metrics or tables instead of `field`.

         Why this exists
         Several collectors only publish metrics or tables, matching the original Tk UI; the overview should still show useful information.
         */
        DashboardSectionSummaryFormatter.summary(for: key, payload: sectionPayload(for: key))
    }

    private func _applyThemeIfAvailable(snapshot: Snapshot) {
        /**
         Summary
         Update the UI theme from a snapshot payload when possible.

         Inputs
         snapshot: Latest snapshot.

         Outputs
         None.

         Side effects
         Updates the published `theme` value.

         Error handling
         Stores a non-fatal error in `lastError` when theme decoding fails.

         Ties to other methods
         Called by `refreshOnce` after a snapshot is received.

         Why this exists
         Allows an iOS client to match the agent’s style without shipping a separate config file.
         */
        do {
            theme = try DashboardSnapshotThemeResolver.theme(
                from: snapshot,
                file: #fileID,
                function: #function
            )
        } catch let error as AppError {
            lastError = error
        } catch {
            lastError = AppError.context(#fileID, #function, "Failed to apply theme", error)
        }
    }

    private func _applyCatalogIfAvailable(snapshot: Snapshot) {
        /**
         Summary
         Update section descriptors from the snapshot catalog when present.

         Inputs
         snapshot: Latest snapshot containing `section_catalog`.

         Outputs
         None.

         Side effects
         Updates published `sections` and may adjust selection.

         Error handling
         None.

         Ties to other methods
         Called by `refreshOnce` after applying the snapshot.

         Why this exists
         Enables the iOS client to render correct labels and ordering without local config duplication.
         */
        guard let newSections = DashboardSnapshotCatalogMapper.sections(from: snapshot) else {
            return
        }
        sections = newSections
        _normalizeSelectedSection()
    }

    public func sectionHealth(for key: String) -> SectionHealth {
        /**
         Summary
         Derive a health state for a section key using the latest snapshot.

         Inputs
         key: Section key.

         Outputs
         Derived `SectionHealth` for badge rendering.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `SidebarView` and `DetailView` to show consistent status badges.

         Why this exists
         Keeps health derivation logic centralized and deterministic.
         */
        guard let payload = sectionPayload(for: key) else {
            return .unknown
        }
        return SectionHealth.fromSnapshotSection(payload)
    }

    private func _isSectionHiddenFromPrimaryUI(key: String) -> Bool {
        /**
         Summary
         Decide whether a section should be omitted from sidebar and overview rendering.

         Inputs
         key: Section key to evaluate.

         Outputs
         True when the section is manually hidden or currently unreadable.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `visibleSections` and selection normalization.

         Why this exists
         Primary UI filtering needs one consistent rule for manual visibility preferences and unreadable collector output.
         */
        visibilityStore.isHidden(key: key) || _isSectionAutomaticallyHidden(key: key)
    }

    private func _isSectionAutomaticallyHidden(key: String) -> Bool {
        /**
         Summary
         Decide whether a section is unreadable and should be hidden automatically.

         Inputs
         key: Section key to evaluate.

         Outputs
         True when the latest section payload represents an unavailable or inaccessible collector.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `isSectionAutomaticallyHidden` and `_isSectionHiddenFromPrimaryUI`.

         Why this exists
         Keeps the unreadable-section rule centralized and aligned with section health heuristics.
         */
        guard let payload = sectionPayload(for: key) else {
            return false
        }
        return SectionHealth.shouldAutoHideFromPrimaryUI(payload)
    }

    private func _normalizeSelectedSection() {
        /**
         Summary
         Keep the selected section aligned with the current visible section set.

         Inputs
         None.

         Outputs
         None.

         Side effects
         May change `selectedSectionKey`.

         Error handling
         None.

         Ties to other methods
         Used after refreshes, catalog updates, and visibility changes.

         Why this exists
         The detail pane should never point at a section that is missing from the main UI.
         */
        selectedSectionKey = DashboardSectionNavigation.normalizedSelectedSectionKey(
            selectedSectionKey: selectedSectionKey,
            overviewKey: Self.overviewKey,
            sections: sections,
            isSectionHidden: { [weak self] key in
                self?._isSectionHiddenFromPrimaryUI(key: key) ?? false
            }
        )
    }

    func historyPoints(sectionKey: String, metricLabel: String) -> [MetricHistoryStore.Point] {
        /**
         Summary
         Return historical points for a specific metric series.

         Inputs
         sectionKey: Section key.
         metricLabel: Metric label.

         Outputs
         Array of points (possibly empty).

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by sparkline views for graphing.

         Why this exists
         Keeps metric history access centralized in the view model.
         */
        return history?.seriesPoints(sectionKey: sectionKey, metricLabel: metricLabel) ?? []
    }

    public func preferredTableVisibleRows(for key: String) -> Int? {
        /**
         Summary
         Return the preferred visible row count for a section table.

         Inputs
         key: Section key.

         Outputs
         Optional row count integer.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by table views to cap vertical size while keeping content scrollable.

         Why this exists
         Mirrors the Python GUI’s per-section scroll preferences using central config knobs.
         */
        return scrollableRows[key]
    }

    private func _backendWarningIfAny(exitCode: Int32, snapshot: Snapshot, stderr: String) -> AppError? {
        /**
         Summary
         Build a non-fatal error when the backend indicates partial failure.

         Inputs
         exitCode: Backend process exit code.
         snapshot: Decoded snapshot.
         stderr: Backend stderr output.

         Outputs
         Optional `AppError` describing the backend issue.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `refreshOnce` to surface partial failures without dropping the snapshot.

        Why this exists
        The UI should keep showing the latest data even when one section fails.
         */
        DashboardBackendWarningFormatter.warning(
            exitCode: exitCode,
            snapshot: snapshot,
            stderr: stderr,
            file: #fileID,
            function: #function
        )
    }

    private func _loadCachedSnapshotIfAvailable() {
        /**
         Summary
         Load a cached snapshot from disk to make startup feel instant when available.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Reads a file from disk and may update published state.

         Error handling
         Stores a non-fatal `AppError` in `lastError` when the cache is present but invalid.

         Ties to other methods
         Called by `init` before auto-refresh starts.

         Why this exists
         The original Tk UI kept collector state in-process; caching avoids a blank UI while the first snapshot is collected.
         */
        do {
            guard let checked = try DashboardSnapshotCache.loadSnapshotIfAvailable(at: snapshotCacheFile) else {
                return
            }
            snapshot = checked
            lastRefreshAt = Date(timeIntervalSince1970: TimeInterval(checked.generated_at_unix_ms) / 1000.0)
            _applyThemeIfAvailable(snapshot: checked)
            _applyCatalogIfAvailable(snapshot: checked)
            appTitle = checked.theme.ui.window_title
        } catch let error as AppError {
            lastError = error
        } catch {
            let cachePath = snapshotCacheFile?.path ?? "<unknown>"
            lastError = AppError.context(#fileID, #function, "Failed to load snapshot cache at \(cachePath)", error)
        }
    }

    private func _writeSnapshotCacheIfPossible(rawJSON: String?) {
        /**
         Summary
         Persist the latest successful snapshot to disk for faster subsequent startups.

         Inputs
         rawJSON: Raw snapshot JSON text when available.

         Outputs
         None.

         Side effects
         Writes a file under the configured cache path.

         Error handling
         Stores a non-fatal `AppError` in `lastError` when cache writes fail.

         Ties to other methods
         Called by `refreshOnce` after updating snapshot state.

         Why this exists
         Users expect the dashboard to render immediately; caching avoids waiting on system_profiler and other slow commands.
         */
        do {
            _ = try DashboardSnapshotCache.writeSnapshotIfPossible(
                rawJSON: rawJSON,
                to: snapshotCacheFile
            )
        } catch {
            guard let snapshotCacheFile else { return }
            lastError = AppError.context(#fileID, #function, "Failed to write snapshot cache at \(snapshotCacheFile.path)", error)
        }
    }
}
