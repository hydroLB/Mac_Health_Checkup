from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.diagnostics.updates import SoftwareUpdateDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/updates.py"
_MAX_UPDATE_ROWS = 5


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
        updates = _coerce_update_items(data)
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
                rows.extend(_build_update_rows(updates))
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


def _coerce_update_items(data: JsonDict) -> list[tuple[str, str]]:
    """
    Summary
    Normalize update diagnostics into `(label, size)` tuples for section rendering.

    Inputs
    data: Diagnostics payload from `SoftwareUpdateDiagnostics.fetch`.

    Outputs
    List of `(label, size)` tuples where `size` may be an empty string.

    Side effects
    None.

    Error handling
    Never raises; malformed data is ignored and results in an empty list.

    Ties to other methods
    Used by `update_section`.

    Why this exists
    Keeps section rendering resilient while supporting both legacy `update_labels` and new `update_items`.
    """
    items: list[tuple[str, str]] = []
    raw_items = data.get("update_items")
    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            size = str(item.get("size", "")).strip()
            if label:
                items.append((label, size))
    if items:
        return items

    labels = data.get("update_labels")
    if not isinstance(labels, list):
        return []
    return [(str(item).strip(), "") for item in labels if str(item).strip()]


def _build_update_rows(updates: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    """
    Summary
    Build metrics rows for per-update label and size display.

    Inputs
    updates: Parsed update tuples as `(label, size)`.

    Outputs
    List of metrics rows for `render_metrics_table`.

    Side effects
    None.

    Error handling
    Never raises; malformed rows are skipped.

    Ties to other methods
    Used by `update_section`.

    Why this exists
    Explicit rows make update details visible without requiring users to inspect raw command output.
    """
    rows: list[tuple[str, str, str]] = []
    for index, (label, size) in enumerate(updates[:_MAX_UPDATE_ROWS], start=1):
        normalized_label = str(label).strip()
        normalized_size = str(size).strip()
        if not normalized_label:
            continue
        value = normalized_label if not normalized_size else f"{normalized_label} ({normalized_size})"
        rows.append((f"Update {index}", value, "info"))
    if len(updates) > _MAX_UPDATE_ROWS:
        rows.append(("More", f"+{len(updates) - _MAX_UPDATE_ROWS} additional updates", "info"))
    return rows
