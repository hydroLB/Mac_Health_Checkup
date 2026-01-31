import Foundation

@MainActor
public final class SectionVisibilityStore: ObservableObject {
    /**
     Summary
     Persist and expose per-section visibility preferences for the SwiftUI UI.

     Inputs
     defaults: UserDefaults instance used for persistence.

     Outputs
     Published set of hidden section keys.

     Side effects
     Reads and writes UserDefaults.

     Error handling
     Falls back to an empty set when stored data is invalid.

     Ties to other methods
     Used by `DashboardViewModel` and `SettingsView`.

     Why this exists
     Users want to hide sections from the sidebar and overview without editing config files or code.
     */

    public nonisolated static let defaultsKey: String = "mac_health_checkup.hidden_section_keys.v1"

    private let defaults: UserDefaults

    @Published public private(set) var hiddenSectionKeys: Set<String>

    public init(defaults: UserDefaults = .standard) {
        /**
         Summary
         Initialize the store and load persisted preferences.

         Inputs
         defaults: UserDefaults instance used for persistence.

         Outputs
         None.

         Side effects
         Loads stored state from UserDefaults.

         Error handling
         On decode errors, returns an empty set and clears corrupt storage.

         Ties to other methods
         Used by `DashboardViewModel.init`.

         Why this exists
         Provides a single source of truth for section visibility that survives app restarts.
         */
        self.defaults = defaults
        self.hiddenSectionKeys = Self._load(from: defaults)
    }

    public func isHidden(key: String) -> Bool {
        /**
         Summary
         Check whether a section key is hidden.

         Inputs
         key: Section key string.

         Outputs
         True when the key is marked hidden.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `DashboardViewModel.visibleSections`.

         Why this exists
         Keeps visibility checks consistent across views and filtering logic.
         */
        hiddenSectionKeys.contains(key)
    }

    public func setHidden(_ hidden: Bool, key: String) {
        /**
         Summary
         Update a section's hidden state and persist it.

         Inputs
         hidden: Whether the section should be hidden.
         key: Section key string.

         Outputs
         None.

         Side effects
         Writes updated state to UserDefaults.

         Error handling
         None.

         Ties to other methods
         Used by `SettingsView` and `DashboardViewModel`.

         Why this exists
         Provides an explicit API so the UI cannot accidentally bypass persistence.
         */
        if hidden {
            hiddenSectionKeys.insert(key)
        } else {
            hiddenSectionKeys.remove(key)
        }
        Self._save(hiddenSectionKeys, to: defaults)
    }

    public func reset() {
        /**
         Summary
         Clear all hidden section keys.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Writes empty state to UserDefaults.

         Error handling
         None.

         Ties to other methods
         Used by `SettingsView`.

         Why this exists
         Users need a safe escape hatch if they hide too much and lose navigation context.
         */
        hiddenSectionKeys = []
        Self._save(hiddenSectionKeys, to: defaults)
    }

    private static func _load(from defaults: UserDefaults) -> Set<String> {
        /**
         Summary
         Load the stored hidden section set from UserDefaults.

         Inputs
         defaults: UserDefaults instance.

         Outputs
         A set of hidden section keys.

         Side effects
         May clear corrupt storage.

         Error handling
         Returns an empty set when stored data is missing or invalid.

         Ties to other methods
         Used by `init`.

         Why this exists
         Keeps decoding logic contained and testable.
         */
        let raw = defaults.string(forKey: defaultsKey) ?? ""
        if raw.isEmpty { return [] }
        do {
            let data = Data(raw.utf8)
            let decoded = try JSONDecoder().decode([String].self, from: data)
            return Set(decoded.filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty })
        } catch {
            defaults.removeObject(forKey: defaultsKey)
            return []
        }
    }

    private static func _save(_ keys: Set<String>, to defaults: UserDefaults) {
        /**
         Summary
         Persist the hidden section set to UserDefaults.

         Inputs
         keys: Set of hidden section keys.
         defaults: UserDefaults instance.

         Outputs
         None.

         Side effects
         Writes a JSON array string to UserDefaults.

         Error handling
         On encoding failure, clears stored value to avoid corrupt state.

         Ties to other methods
         Used by `setHidden` and `reset`.

         Why this exists
         JSON provides a stable, forward-compatible persistence format.
         */
        do {
            let ordered = keys.sorted()
            let data = try JSONEncoder().encode(ordered)
            let text = String(decoding: data, as: UTF8.self)
            defaults.set(text, forKey: defaultsKey)
        } catch {
            defaults.removeObject(forKey: defaultsKey)
        }
    }
}
