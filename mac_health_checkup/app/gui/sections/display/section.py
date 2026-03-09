from __future__ import annotations

from mac_health_checkup.app.gui.sections.display.parsing import (
    _parse_ioreg_display_rows,
    _parse_raw_display_rows,
)
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.diagnostics.display import DisplayDiagnostics
from mac_health_checkup.diagnostics.display_transport import DisplayTransportDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/display/section.py"


def _display_row_sort_key(item: tuple[int, tuple[str, ...]]) -> tuple[int, int]:
    """
    Summary
    Sort display rows to prefer the built-in display at the top.

    Inputs
    item: Tuple of (original_index, row tuple).

    Outputs
    Sort key where lower values appear first.

    Side effects
    None.

    Error handling
    Returns a stable key even when row data is missing.

    Ties to other methods
    Used by `update_section` before rendering the Display table.

    Why this exists
    The built-in panel (often shown as "Color LCD" or "Built-in Display") should be easiest to find.
    """
    try:
        idx, row = item
        name = (row[0] if len(row) > 0 else "").strip().lower()
        connection = (row[3] if len(row) > 3 else "").strip().lower()
        transport = (row[-1] if row else "").strip().lower()

        is_internal = False
        if "color lcd" in name or "built-in" in name or "built in" in name:
            is_internal = True
        if connection in {"built-in", "built in", "internal"}:
            is_internal = True
        if transport in {"internal"}:
            is_internal = True

        priority = 0 if is_internal else 1
        return (priority, idx)
    except (RuntimeError, ValueError, TypeError, IndexError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_display_row_sort_key", "Failed to build display row sort key", exc)
        ) from exc


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Display section table from diagnostics.

    Inputs
    host: SectionHost implementation.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host table output.

    Error handling
    Raises `RuntimeError` with module and method context when section rendering fails.

    Ties to other methods
    Used by the dashboard section handler.

    Why this exists
    Keeps display rendering logic isolated.
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
            merged_rows = [row for _, row in sorted(enumerate(merged_rows), key=_display_row_sort_key)]
            host.render_table("display", headers, merged_rows)
            return {"display": data, "transport": transport}

        raw_ioreg = data.get("raw_ioreg")
        if isinstance(raw_ioreg, str) and raw_ioreg.strip():
            ioreg_rows = _parse_ioreg_display_rows(raw_ioreg)
            ioreg_rows = [row for _, row in sorted(enumerate(ioreg_rows), key=_display_row_sort_key)]
            host.render_table("display", headers, ioreg_rows)
            return {"display": data, "source": "ioreg"}

        host.render_table("display", headers, [])
        return {"display": data, "source": "empty"}
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Display section", exc)
        ) from exc
