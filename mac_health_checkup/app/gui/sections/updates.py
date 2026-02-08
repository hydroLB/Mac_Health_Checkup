from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.diagnostics.updates import SoftwareUpdateDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/updates.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Updates section from diagnostics.

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
    OS update posture is a high-value security and stability signal.
    """
    try:
        data = SoftwareUpdateDiagnostics.fetch()
        labels = data.get("update_labels")
        updates = [str(item).strip() for item in labels] if isinstance(labels, list) else []
        updates = [item for item in updates if item]
        count = len(updates)
        available = data.get("updates_available")
        available_bool = bool(available) if isinstance(available, bool) else None

        status = "ok"
        if available_bool is True and count > 0:
            status = "warn"
        elif available_bool is True and count == 0:
            status = "warn"
        elif available_bool is None:
            status = "unknown"

        rows: list[tuple[str, str, str]] = []
        if available_bool is True:
            rows.append(("Updates", f"{count} available", status))
            if count:
                rows.append(("First", updates[0], "info"))
        elif available_bool is False:
            rows.append(("Updates", "Up to date", "ok"))
        else:
            rows.append(("Updates", "Unknown", "unknown"))

        host.render_metrics_table("updates", rows, columns=2)
        if available_bool is False:
            host.set_field("updates", "Up to date")
        elif available_bool is True:
            host.set_field("updates", f"{count} updates available" if count else "Updates available")
        else:
            host.set_field("updates", "Update status unavailable")
        data["ok"] = bool(data.get("ok"))
        return data
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Updates section", exc)
        ) from exc
