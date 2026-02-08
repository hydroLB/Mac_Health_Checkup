from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.data import fmt_percent, fmt_temp_c
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.health import health_from_percent
from mac_health_checkup.diagnostics.battery import BatteryDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/battery.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Battery section fields from diagnostics.

    Inputs
    host: SectionHost implementation.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host fields and metrics.

    Error handling
    Raises `RuntimeError` with module and method context when section rendering fails.

    Ties to other methods
    Used by the dashboard section handler.

    Why this exists
    Keeps battery rendering logic isolated.
    """
    try:
        data = BatteryDiagnostics.fetch()
        summary = str(data.get("health_text", "Battery info unavailable"))
        host.set_field("battery", summary)
        percent = data.get("percent_health")
        percent_val = float(percent) if isinstance(percent, (int, float)) else None
        health_label = health_from_percent(percent_val) if percent_val is not None else "unknown"
        health_status = "unknown"
        if health_label in {"excellent", "good"}:
            health_status = "ok"
        elif health_label == "fair":
            health_status = "warn"
        elif health_label == "degraded":
            health_status = "bad"

        design = data.get("design_capacity")
        max_cap = data.get("max_capacity")
        current = data.get("current_capacity")
        cycle = data.get("cycle_count")
        voltage_mv = data.get("voltage_mv")
        temp_c = data.get("temperature_c")

        rows: list[tuple[str, str, str]] = []
        if percent_val is not None:
            rows.append(("Health", f"{fmt_percent(percent_val)} ({health_label})", health_status))
        if isinstance(max_cap, int) and isinstance(design, int) and design > 0:
            rows.append(("Max / Design", f"{max_cap:,} / {design:,} mAh", "info"))
        if isinstance(current, int):
            rows.append(("Current capacity", f"{current:,} mAh", "info"))
        if isinstance(cycle, int):
            rows.append(("Cycle count", f"{cycle:,}", "info"))
        if isinstance(voltage_mv, int) and voltage_mv > 0:
            rows.append(("Voltage", f"{voltage_mv / 1000.0:.2f} V", "info"))
        if isinstance(temp_c, (int, float)):
            rows.append(("Temperature", fmt_temp_c(float(temp_c)), "info"))
        if rows:
            host.render_metrics_table("battery", rows, columns=2)
        data["ok"] = bool(rows)
        return data
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Battery section", exc)
        ) from exc
