from __future__ import annotations

from mac_health_checkup.app.gui.sections.display.parsing import (
    _parse_ioreg_display_rows,
    _parse_raw_display_rows,
)
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.diagnostics.display import DisplayDiagnostics
from mac_health_checkup.diagnostics.display_transport import DisplayTransportDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/display/section.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Purpose: Update the Display section table from diagnostics.
    Ties: Used by dashboard section handler.
    Inputs: host implements SectionHost.
    Outputs: Diagnostics dict for the section.
    Side effects: Updates host table.
    Why: Keeps display rendering logic isolated.
    """
    try:
        data = DisplayDiagnostics.fetch()
        raw = str(data.get("raw", ""))
        rows = _parse_raw_display_rows(raw)
        headers = tuple(get_config().gui.display_headers)
        if rows:
            transport = DisplayTransportDiagnostics.fetch(data)
            transport_list = transport.get("displays")
            transport_labels: list[str] = []
            if isinstance(transport_list, list):
                transport_labels = [str(item) for item in transport_list]
            while len(transport_labels) < len(rows):
                transport_labels.append("?")
            merged_rows = [row + (transport_labels[idx],) for idx, row in enumerate(rows)]
            host.render_table("display", headers, merged_rows)
            return {"display": data, "transport": transport}

        raw_ioreg = data.get("raw_ioreg")
        if isinstance(raw_ioreg, str) and raw_ioreg.strip():
            ioreg_rows = _parse_ioreg_display_rows(raw_ioreg)
            host.render_table("display", headers, ioreg_rows)
            return {"display": data, "source": "ioreg"}

        host.render_table("display", headers, [])
        return {"display": data, "source": "empty"}
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Display section", exc)
        ) from exc
