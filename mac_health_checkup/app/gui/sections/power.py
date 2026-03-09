from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import fmt_temp_c, format_error
from mac_health_checkup.diagnostics.battery import BatteryTempDiagnostics
from mac_health_checkup.diagnostics.power import PowerAdapterDiagnostics, USBPowerDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/power.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Power section fields from diagnostics.

    Inputs
    host: SectionHost implementation.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host fields and metrics table.

    Error handling
    Raises `RuntimeError` with module and method context when section rendering fails.

    Ties to other methods
    Used by the dashboard section handler.

    Why this exists
    Keeps power rendering logic isolated.
    """
    try:
        adapter = PowerAdapterDiagnostics.fetch()
        temp = BatteryTempDiagnostics.fetch()
        usb_power = USBPowerDiagnostics.fetch()

        rows: list[tuple[str, str, str]] = []
        adapter_w = adapter.get("adapter_w")
        if adapter_w is not None:
            rows.append(("Adapter", f"{adapter_w} W", "info"))
        charging = adapter.get("is_charging")
        if charging is not None:
            rows.append(("Charging", "Yes" if charging else "No", "info"))
        temp_c = temp.get("temp_c")
        if isinstance(temp_c, (int, float)):
            rows.append(("Battery Temp", fmt_temp_c(float(temp_c)), "info"))
        host.render_metrics_table("power", rows, columns=2)
        return {"adapter": adapter, "battery_temp": temp, "usb_power": usb_power}
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Power section", exc)
        ) from exc
