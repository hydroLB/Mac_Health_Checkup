from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.diagnostics.devices import DeviceScanner

MODULE_PATH = "mac_health_checkup/app/gui/sections/devices.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Devices section table from diagnostics.

    Inputs
    host: SectionHost implementation.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host table and field.

    Error handling
    Raises `RuntimeError` with module and method context when section rendering fails.

    Ties to other methods
    Used by the dashboard section handler.

    Why this exists
    Keeps devices rendering logic isolated.
    """
    try:
        cfg = get_config().gui
        grouped = DeviceScanner.scan_by_bus()
        rows: list[tuple[str, ...]] = []
        bus_order: list[tuple[str, str]] = [
            ("bluetooth", "Bluetooth"),
            ("usb", "USB"),
            ("thunderbolt", "Thunderbolt"),
            ("network", "Network"),
        ]
        for key, bus_label in bus_order:
            value = grouped.get(key)
            if not isinstance(value, list):
                continue
            labels = [str(item).strip() for item in value if str(item).strip()]
            if key in {"usb", "thunderbolt"}:
                labels = _filter_device_labels(
                    labels,
                    skip_keywords=cfg.peripheral_skip_keywords,
                    allow_keywords=cfg.peripheral_allow_keywords,
                    max_len=cfg.peripheral_max_name_len,
                )
            else:
                labels = [_truncate_label(label, cfg.peripheral_max_name_len) for label in labels]
            for label in labels:
                rows.append((bus_label, label))

        headers = tuple(cfg.devices_headers)
        if rows:
            host.set_field("devices", f"{len(rows)} connected")
            host.render_table("devices", headers, rows[: cfg.max_devices_lines])
            return {"ok": True, "devices": rows}

        host.set_field("devices", "None detected")
        host.render_table("devices", headers, [])
        return {"ok": False, "devices": []}
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Devices section", exc)
        ) from exc


def _filter_labels(
    labels: list[str], skip_keywords: list[str], allow_keywords: list[str], max_len: int
) -> list[str]:
    """
    Summary
    Filter and normalize device labels based on config keywords.

    Inputs
    labels: Label list.
    skip_keywords: Keywords used to skip labels.
    allow_keywords: Keywords that force-include labels.
    max_len: Maximum label length.

    Outputs
    Filtered list of device labels.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when filtering fails unexpectedly.

    Ties to other methods
    Used by `update_section` to clean device lists.

    Why this exists
    Keeps device lists concise and focused on useful peripherals.
    """
    try:
        filtered: list[str] = []
        skip_set = [item.lower() for item in skip_keywords]
        allow_set = [item.lower() for item in allow_keywords]
        for label in labels:
            lower = label.lower()
            if any(keyword in lower for keyword in allow_set):
                filtered.append(_truncate_label(label, max_len))
                continue
            if any(keyword in lower for keyword in skip_set):
                continue
            filtered.append(_truncate_label(label, max_len))
        return filtered
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_filter_labels", "Failed to filter labels", exc)
        ) from exc


def _filter_device_labels(
    labels: list[str], *, skip_keywords: list[str], allow_keywords: list[str], max_len: int
) -> list[str]:
    """
    Summary
    Filter and normalize device labels for the Devices section.

    Inputs
    labels: Label list.
    skip_keywords: Keywords used to skip labels.
    allow_keywords: Keywords that force-include labels.
    max_len: Maximum label length.

    Outputs
    Filtered list of device labels.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when filtering fails unexpectedly.

    Ties to other methods
    Used by `update_section` to keep the Devices table useful and non-redundant with Ports.

    Why this exists
    Devices should favor real peripherals and adapters while hiding infrastructure nodes that belong in the Ports tree.
    """
    try:
        filtered: list[str] = []
        skip_set = [item.lower() for item in skip_keywords]
        allow_set = [item.lower() for item in allow_keywords]
        keep_if_matches = ("lan", "ethernet")

        for label in labels:
            lower = label.lower()
            if any(keyword in lower for keyword in allow_set):
                filtered.append(_truncate_label(label, max_len))
                continue
            if any(keyword in lower for keyword in keep_if_matches):
                filtered.append(_truncate_label(label, max_len))
                continue
            if _is_infrastructure_label(lower):
                continue
            if any(keyword in lower for keyword in skip_set):
                continue
            filtered.append(_truncate_label(label, max_len))

        return filtered
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_filter_device_labels", "Failed to filter device labels", exc)
        ) from exc


def _is_infrastructure_label(lower_label: str) -> bool:
    """
    Summary
    Detect bus and bridge nodes that should be hidden from the Devices list.

    Inputs
    lower_label: Lowercased label.

    Outputs
    True when the label represents infrastructure rather than an end device.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when detection fails unexpectedly.

    Ties to other methods
    Used by `_filter_device_labels`.

    Why this exists
    The Ports section already shows buses, hubs, and billboards with nesting; duplicating them in Devices makes it noisy.
    """
    try:
        text = (lower_label or "").strip()
        if not text:
            return True
        if text.endswith(" bus"):
            return True
        infra_tokens = (" hub", "billboard")
        if any(token in text for token in infra_tokens):
            return True
        return False
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH, "_is_infrastructure_label", "Failed to detect infrastructure labels", exc
            )
        ) from exc


def _truncate_label(label: str, max_len: int) -> str:
    """
    Summary
    Truncate a label to a maximum length if needed.

    Inputs
    label: Original string.
    max_len: Maximum length.

    Outputs
    Truncated label string.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when truncation fails unexpectedly.

    Ties to other methods
    Used by `_filter_labels` for consistent label sizing.

    Why this exists
    Keeps long labels from overwhelming the UI.
    """
    try:
        if max_len <= 0:
            return label
        if len(label) <= max_len:
            return label
        if max_len <= 3:
            return label[:max_len]
        return label[: max_len - 3] + "..."
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_truncate_label", "Failed to truncate label", exc)
        ) from exc
