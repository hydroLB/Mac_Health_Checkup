from __future__ import annotations

from dataclasses import dataclass

MODULE_PATH = "mac_health_checkup/app/help_text.py"


@dataclass(frozen=True)
class HelpText:
    """
    Summary
    Provide hover-help text for UI elements.

    Inputs
    None. This module is a read-only registry.

    Outputs
    Human-readable tooltip strings.

    Side effects
    None.

    Error handling
    Unknown keys fall back to a generic explanation.

    Ties to other methods
    Used by the Tk dashboard and the SwiftUI app to show consistent hover help.

    Why this exists
    Tooltips should be deterministic and centralized so UI code does not embed duplicated explanations.
    """


_SECTION_HELP: dict[str, str] = {
    "performance": (
        "Thermals and power residency from macOS sensor tooling (best-effort). "
        "Some macOS builds restrict low-level sensors, so values may be missing."
    ),
    "general": "Basic machine identity (model, chip, OS version). Used to interpret other sections.",
    "power": "Battery and charger status, plus power-related system state. Read-only system sources.",
    "fan": "Fan RPM readings when available. Some Macs restrict fan access without elevated privileges.",
    "battery": "Battery health and charge characteristics (cycles, capacity, temperature).",
    "ssd": "Storage health and SMART-related information when available. Some tools require elevated access.",
    "display": "Connected display inventory and properties (resolution, refresh, transport).",
    "network": "Network interface summary and quality indicators (RSSI, rates, and basic throughput).",
    "devices": "Connected USB device list (best-effort).",
    "ports": "USB topology tree and attached devices. Useful for debugging hubs and display alt-mode paths.",
    "input": "Detected keyboards, mice, and related HID devices.",
    "overview": "At-a-glance summary of all sections. Click into a section for details.",
    "settings": "Configuration and visibility controls for the dashboard.",
}

_METRIC_HELP: dict[tuple[str, str], str] = {
    (
        "battery",
        "health",
    ): "Battery health as a percentage of design capacity, plus a coarse label (excellent/good/etc.).",
    ("battery", "max / design"): "Maximum charge capacity versus original design capacity (mAh).",
    ("battery", "current capacity"): "Current charge capacity reading (mAh).",
    ("battery", "cycle count"): "Number of full charge cycles recorded by the battery controller.",
    ("battery", "voltage"): "Battery pack voltage (V).",
    ("battery", "temperature"): "Battery temperature reading (°C).",
    ("network", "interface"): "Active network interface used for the snapshot (e.g., en0).",
    ("network", "ssid"): "Wi‑Fi network name when connected via Wi‑Fi.",
    ("network", "ipv4"): "Current IPv4 address for the selected interface.",
    ("network", "rssi"): "Wi‑Fi signal strength in dBm (more negative is weaker).",
    ("network", "tx rate"): "Wi‑Fi transmit rate reported by the interface (Mbps).",
    ("network", "down (live)"): "Best-effort downstream measurement (Mbps).",
    ("network", "up (live)"): "Best-effort upstream measurement (Mbps).",
    ("network", "downlink capacity"): "Estimated downlink capacity (Mbps) from system tools when available.",
    ("network", "uplink capacity"): "Estimated uplink capacity (Mbps) from system tools when available.",
    ("performance", "cpu power"): "CPU power estimate from power residency sampling (W) when available.",
    ("performance", "gpu power"): "GPU power estimate from power residency sampling (W) when available.",
    ("performance", "ane power"): "Apple Neural Engine power estimate (W) when available.",
}

_TABLE_HEADER_HELP: dict[tuple[str, str], str] = {
    ("display", "name"): "Display name as reported by the system (may include internal/external naming).",
    ("display", "resolution"): "Active pixel resolution for the display.",
    ("display", "mirror"): "Mirror status for the display.",
    ("display", "connection"): "Connection type (built-in/external).",
    ("display", "refresh"): "Reported refresh rate (Hz).",
    (
        "display",
        "transport",
    ): "Display transport classification (internal/external) used for estimating bandwidth.",
    ("devices", "bus"): "Bus type for the device (typically USB).",
    ("devices", "device"): "Device name (best-effort, may be truncated).",
    ("ports", "usb tree"): "Indented USB topology as reported by the system.",
    ("input", "type"): "Input device category (keyboard, mouse, trackpad).",
    ("input", "device"): "Input device name.",
    ("input", "transport"): "Transport mechanism (USB, Bluetooth, FIFO, etc.).",
}


def section(key: str) -> str:
    """
    Summary
    Return help text for a section key.

    Inputs
    key: Section key string.

    Outputs
    Tooltip text.

    Side effects
    None.

    Error handling
    Returns a generic message for unknown keys.

    Ties to other methods
    Used by UI hover tooltips for section titles and summary fields.

    Why this exists
    Section-level help should not be duplicated across UI layers.
    """
    normalized = (key or "").strip().lower()
    if not normalized:
        return "Section details emitted by the diagnostics backend."
    return _SECTION_HELP.get(normalized, "Section details emitted by the diagnostics backend.")


def metric(section_key: str, label: str) -> str:
    """
    Summary
    Return help text for a metric label within a section.

    Inputs
    section_key: Section key string.
    label: Metric label as displayed in the UI.

    Outputs
    Tooltip text.

    Side effects
    None.

    Error handling
    Falls back to section help when no metric-specific mapping exists.

    Ties to other methods
    Used by UI hover tooltips for metrics tables.

    Why this exists
    Metric labels are often terse; tooltips provide context without cluttering the UI.
    """
    s = (section_key or "").strip().lower()
    label_norm = (label or "").strip().lower()
    if not s or not label_norm:
        return section(s)
    return _METRIC_HELP.get((s, label_norm), section(s))


def table_header(section_key: str, header: str) -> str:
    """
    Summary
    Return help text for a table header within a section.

    Inputs
    section_key: Section key string.
    header: Column header text as displayed in the UI.

    Outputs
    Tooltip text.

    Side effects
    None.

    Error handling
    Falls back to section help when no header-specific mapping exists.

    Ties to other methods
    Used by UI hover tooltips for table headers and cells.

    Why this exists
    Table columns vary by section; a small explanation reduces ambiguity without adding UI chrome.
    """
    s = (section_key or "").strip().lower()
    h = (header or "").strip().lower()
    if not s or not h:
        return section(s)
    return _TABLE_HEADER_HELP.get((s, h), section(s))
