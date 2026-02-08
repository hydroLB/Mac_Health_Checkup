from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.diagnostics.devices import InputDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/input.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Input section from diagnostics.

    Inputs
    host: SectionHost implementation.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host fields and table output.

    Error handling
    Raises `RuntimeError` with module and method context when section rendering fails.

    Ties to other methods
    Used by the dashboard section handler.

    Why this exists
    Keeps input rendering logic isolated.
    """
    try:
        data = InputDiagnostics.fetch()
        details = data.get("details")
        rows: list[tuple[str, ...]] = []
        labels: list[str] = []
        if isinstance(details, list):
            for item in details:
                label = str(item).strip()
                if not label:
                    continue
                labels.append(label)
                kind, rest = (label.split(":", 1) + [""])[:2]
                kind = kind.strip()
                device = rest.strip() if rest else label
                transport = ""
                if device.endswith(")") and "(" in device:
                    base, paren = device.rsplit("(", 1)
                    device = base.strip()
                    transport = paren[:-1].strip()
                if kind and rest:
                    rows.append((kind, device, transport or "?"))
                else:
                    rows.append(("Device", label, "?"))
        if rows:
            host.set_field("input", f"{len(rows)} devices")
            host.render_table("input", ("Type", "Device", "Transport"), rows)
        else:
            host.set_field("input", "None detected")
            host.render_table("input", ("Type", "Device", "Transport"), [])
        return data
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Input section", exc)
        ) from exc
