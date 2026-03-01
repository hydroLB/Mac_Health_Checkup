from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.diagnostics.system import SystemPressureDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/system.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the System section (storage and memory pressure) from diagnostics.

    Inputs
    host: Section host.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host field and metrics.

    Error handling
    Raises `RuntimeError` with module and method context when rendering fails unexpectedly.

    Ties to other methods
    Used by the dashboard section handler registry.

    Why this exists
    Storage and memory pressure are common high-impact health signals and should be easy to spot at a glance.
    """
    try:
        thresholds = get_config().thresholds
        data = SystemPressureDiagnostics.fetch()

        disk_payload = data.get("disk")
        disk_free = disk_payload.get("free_percent") if isinstance(disk_payload, dict) else None
        mem_payload = data.get("memory")
        mem_free = mem_payload.get("free_percent") if isinstance(mem_payload, dict) else None

        rows: list[tuple[str, str, str]] = []
        if isinstance(disk_free, (int, float)):
            free_val = float(disk_free)
            status = "ok"
            if free_val <= thresholds.disk_free_bad_percent:
                status = "bad"
            elif free_val <= thresholds.disk_free_warn_percent:
                status = "warn"
            rows.append(("Disk free", f"{free_val:.0f}%", status))
        else:
            rows.append(("Disk free", "?", "unknown"))

        if isinstance(mem_free, (int, float)):
            free_val = float(mem_free)
            status = "ok"
            if free_val <= thresholds.memory_free_bad_percent:
                status = "bad"
            elif free_val <= thresholds.memory_free_warn_percent:
                status = "warn"
            rows.append(("Memory free", f"{free_val:.0f}%", status))
        else:
            rows.append(("Memory free", "?", "unknown"))

        host.render_metrics_table("system", rows, columns=2)
        summary_parts = [f"{label}: {value}" for label, value, _status in rows if value and value != "?"]
        host.set_field(
            "system", " | ".join(summary_parts) if summary_parts else "System pressure unavailable"
        )
        data["ok"] = bool(data.get("ok"))
        return data
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update System section", exc)
        ) from exc
