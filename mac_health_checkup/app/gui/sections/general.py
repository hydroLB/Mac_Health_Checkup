from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.diagnostics.general import GeneralDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/general.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the General section fields from diagnostics.

    Inputs
    host: SectionHost implementation.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host fields and machine hint.

    Error handling
    Raises `RuntimeError` with module and method context when section rendering fails.

    Ties to other methods
    Used by the dashboard section handler.

    Why this exists
    Keeps General section rendering logic isolated.
    """
    try:
        data = GeneralDiagnostics.fetch()
        model = str(data.get("model", "Unknown"))
        chip = str(data.get("chip", "Unknown"))
        os_version = str(data.get("os", "Unknown"))
        serial = str(data.get("serial", "Unknown"))
        host.set_field("general", f"{model} | {chip} | macOS {os_version} | {serial}")
        host.set_machine_hint(model)
        return data
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update General section", exc)
        ) from exc
