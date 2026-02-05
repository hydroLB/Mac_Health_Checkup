import Foundation

public enum HelpText {
    /**
     Summary
     Provide hover help strings for UI elements.

     Inputs
     None. This type is a read-only registry of help text.

     Outputs
     Tooltip strings consumed by SwiftUI `.help`.

     Side effects
     None.

     Error handling
     Unknown keys fall back to a generic explanation.

     Ties to other methods
     Used by `SidebarView`, `DetailView`, and table components to add hover explanations.

     Why this exists
     Tooltips should be centralized and deterministic so the UI can stay clean while still being self-explanatory.
     */

    private static let sectionHelp: [String: String] = [
        "performance": "Thermals and power residency from macOS sensor tooling (best-effort). Some sensor sources may be unavailable on certain macOS builds.",
        "general": "Basic machine identity (model, chip, OS version). Used to interpret other sections.",
        "power": "Battery and charger status, plus power-related system state. Read-only system sources.",
        "fan": "Fan RPM readings when available. Some Macs restrict fan access depending on hardware and macOS build.",
        "battery": "Battery health and charge characteristics (cycles, capacity, temperature).",
        "ssd": "Storage health and SMART-related information when available. Some tools require elevated access.",
        "display": "Connected display inventory and properties (resolution, refresh, transport).",
        "network": "Network interface summary and quality indicators (RSSI, rates, and basic throughput).",
        "devices": "Connected USB device list (best-effort).",
        "ports": "USB topology tree and attached devices. Useful for debugging hubs and display alt-mode paths.",
        "input": "Detected keyboards, mice, and related HID devices.",
        "overview": "At-a-glance summary of all sections. Click into a section for details.",
        "settings": "Configuration and visibility controls for the dashboard."
    ]

    private static let metricHelp: [String: [String: String]] = [
        "battery": [
            "health": "Battery health as a percentage of design capacity, plus a coarse label (excellent/good/etc.).",
            "max / design": "Maximum charge capacity versus original design capacity (mAh).",
            "current capacity": "Current charge capacity reading (mAh).",
            "cycle count": "Number of full charge cycles recorded by the battery controller.",
            "voltage": "Battery pack voltage (V).",
            "temperature": "Battery temperature reading (°C)."
        ],
        "network": [
            "interface": "Active network interface used for the snapshot (e.g., en0).",
            "ssid": "Wi‑Fi network name when connected via Wi‑Fi.",
            "ipv4": "Current IPv4 address for the selected interface.",
            "rssi": "Wi‑Fi signal strength in dBm (more negative is weaker).",
            "tx rate": "Wi‑Fi transmit rate reported by the interface (Mbps).",
            "down (live)": "Best-effort downstream measurement (Mbps).",
            "up (live)": "Best-effort upstream measurement (Mbps).",
            "downlink capacity": "Estimated downlink capacity (Mbps) from system tools when available.",
            "uplink capacity": "Estimated uplink capacity (Mbps) from system tools when available."
        ],
        "performance": [
            "cpu power": "CPU power estimate from power residency sampling (W) when available.",
            "gpu power": "GPU power estimate from power residency sampling (W) when available.",
            "ane power": "Apple Neural Engine power estimate (W) when available."
        ]
    ]

    private static let tableHeaderHelp: [String: [String: String]] = [
        "display": [
            "name": "Display name as reported by the system (may include internal/external naming).",
            "resolution": "Active pixel resolution for the display.",
            "mirror": "Mirror status for the display.",
            "connection": "Connection type (built-in/external).",
            "refresh": "Reported refresh rate (Hz).",
            "transport": "Display transport classification (internal/external) used for estimating bandwidth."
        ],
        "devices": [
            "bus": "Bus type for the device (typically USB).",
            "device": "Device name (best-effort, may be truncated)."
        ],
        "ports": [
            "usb tree": "Indented USB topology as reported by the system."
        ],
        "input": [
            "type": "Input device category (keyboard, mouse, trackpad).",
            "device": "Input device name.",
            "transport": "Transport mechanism (USB, Bluetooth, FIFO, etc.)."
        ]
    ]

    public static func section(key: String?) -> String {
        /**
         Summary
         Return help text for a section key.

         Inputs
         key: Optional section key.

         Outputs
         Tooltip text.

         Side effects
         None.

         Error handling
         Returns a generic message for unknown keys.

         Ties to other methods
         Used by section titles and summary fields.

         Why this exists
         Section-level help should not be duplicated across view files.
         */
        let normalized = (key ?? "").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if normalized.isEmpty { return "Section details emitted by the diagnostics backend." }
        return sectionHelp[normalized] ?? "Section details emitted by the diagnostics backend."
    }

    public static func metric(sectionKey: String?, label: String) -> String {
        /**
         Summary
         Return help text for a metric label within a section.

         Inputs
         sectionKey: Optional section key.
         label: Display label.

         Outputs
         Tooltip text.

         Side effects
         None.

         Error handling
         Falls back to section help when there is no metric-specific mapping.

         Ties to other methods
         Used by metric row labels and values.

         Why this exists
         Metrics are often short labels; tooltips provide context without clutter.
         */
        let s = (sectionKey ?? "").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let l = label.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if s.isEmpty || l.isEmpty { return section(key: sectionKey) }
        return metricHelp[s]?[l] ?? section(key: sectionKey)
    }

    public static func tableHeader(sectionKey: String?, header: String) -> String {
        /**
         Summary
         Return help text for a table header within a section.

         Inputs
         sectionKey: Optional section key.
         header: Column header text.

         Outputs
         Tooltip text.

         Side effects
         None.

         Error handling
         Falls back to section help when no header-specific mapping exists.

         Ties to other methods
         Used by table headers and cells.

         Why this exists
         Column names vary; help text clarifies what a given column represents.
         */
        let s = (sectionKey ?? "").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let h = header.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if s.isEmpty || h.isEmpty { return section(key: sectionKey) }
        return tableHeaderHelp[s]?[h] ?? section(key: sectionKey)
    }

    public static func tableCell(sectionKey: String?, header: String, value: String) -> String {
        /**
         Summary
         Return help text for a table cell.

         Inputs
         sectionKey: Optional section key.
         header: Column header for the cell.
         value: Cell value string.

         Outputs
         Tooltip text.

         Side effects
         None.

         Error handling
         Falls back to header help when values are empty.

         Ties to other methods
         Used by table rendering views.

         Why this exists
         A header explanation plus the current value is the most compact way to explain what the user is hovering.
         */
        let base = tableHeader(sectionKey: sectionKey, header: header)
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return base }
        return "\(base)\n\nCurrent value: \(trimmed)"
    }
}
