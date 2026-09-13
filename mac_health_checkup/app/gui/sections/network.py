from __future__ import annotations

from typing import Optional

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.diagnostics.network import NetworkQualityDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/network.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Network section from diagnostics.

    Inputs
    host: SectionHost implementation.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host fields.

    Error handling
    Raises `RuntimeError` with module and method context when section rendering fails.

    Ties to other methods
    Used by the dashboard section handler.

    Why this exists
    Keeps network rendering logic isolated.
    """
    try:
        data = NetworkQualityDiagnostics.fetch()
        interface = data.get("interface")
        iface = interface if isinstance(interface, str) else None
        _render(host, data, iface)
        return data
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Network section", exc)
        ) from exc


def _render(host: SectionHost, data: JsonDict, interface: Optional[str]) -> None:
    """
    Summary
    Render network data into the host.

    Inputs
    host: SectionHost implementation.
    data: Diagnostics dict.
    interface: Optional interface name.

    Outputs
    None.

    Side effects
    Updates host fields and metrics.

    Error handling
    Raises `RuntimeError` with module and method context when rendering fails.

    Ties to other methods
    Used by `update_section` and tests.

    Why this exists
    Separates rendering from data fetch for testability.
    """
    try:
        iface_str = interface or "unknown"
        ipv4 = data.get("ipv4")
        ipv4_str = str(ipv4) if isinstance(ipv4, str) and ipv4 else ""
        ssid = data.get("ssid")
        ssid_str = str(ssid) if isinstance(ssid, str) and ssid else ""
        rssi = data.get("rssi_dbm")
        rx = data.get("rx_mbps")
        tx = data.get("tx_mbps")
        rx_str = f"{rx:.1f} Mbps" if isinstance(rx, (int, float)) else ""
        tx_str = f"{tx:.1f} Mbps" if isinstance(tx, (int, float)) else ""
        kind = "Wi‑Fi" if ssid_str else "Network"
        parts: list[str] = [kind]
        if ssid_str:
            parts.append(ssid_str)
        if ipv4_str:
            parts.append(ipv4_str)
        if rx_str:
            parts.append(f"↓ {rx_str}")
        if tx_str:
            parts.append(f"↑ {tx_str}")
        host.set_field("network", "  •  ".join(parts) if parts else "Network unavailable")

        rows: list[tuple[str, str, str]] = []
        rows.append(("Interface", iface_str, "info"))
        if ssid_str:
            rows.append(("SSID", ssid_str, "info"))
        if ipv4_str:
            rows.append(("IPv4", ipv4_str, "info"))
        if isinstance(rssi, int):
            thresholds = get_config().thresholds
            status = "ok"
            if rssi <= thresholds.rssi_bad_dbm:
                status = "bad"
            elif rssi <= thresholds.rssi_warn_dbm:
                status = "warn"
            rows.append(("RSSI", f"{rssi} dBm", status))
        tx_rate = data.get("tx_rate_mbps")
        if isinstance(tx_rate, int):
            rows.append(("Tx Rate", f"{tx_rate} Mbps", "info"))
        if isinstance(rx, (int, float)):
            rows.append(("Down (live)", f"{rx:.1f} Mbps", "info"))
        if isinstance(tx, (int, float)):
            rows.append(("Up (live)", f"{tx:.1f} Mbps", "info"))
        cap_down = data.get("down_mbps")
        cap_up = data.get("up_mbps")
        if isinstance(cap_down, (int, float)):
            rows.append(("Downlink capacity", f"{cap_down} Mbps", "info"))
        if isinstance(cap_up, (int, float)):
            rows.append(("Uplink capacity", f"{cap_up} Mbps", "info"))
        if data.get("capacity_test_enabled") is False:
            rows.append(("Capacity test", "Disabled (opt in)", "info"))
        host.render_metrics_table("network", rows, columns=2)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_render", "Failed to render Network section", exc)
        ) from exc
