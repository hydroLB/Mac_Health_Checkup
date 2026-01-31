from __future__ import annotations

from typing import Final

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/utils/usb_tree.py"

_USB_PROPERTY_PREFIXES: Final[tuple[str, ...]] = (
    "vendor id",
    "product id",
    "manufacturer",
    "serial number",
    "location id",
    "current available",
    "current required",
    "extra operating",
    "operating current",
    "bus power",
)


def _strip_sysprop_prefix(line: str) -> str:
    """
    Purpose: Remove system property prefixes from USB tree lines.
    Ties: Used by USB parsing helpers to isolate device labels.
    Inputs: line is a raw USB tree line.
    Outputs: Cleaned label or empty string if line is metadata.
    Side effects: None.
    Why: Keeps device label extraction noise free.
    """
    try:
        stripped = line.strip()
        if not stripped:
            return ""
        if ":" not in stripped:
            return stripped
        head, tail = stripped.split(":", 1)
        if head.strip().lower() in _USB_PROPERTY_PREFIXES:
            return ""
        if head.strip().lower() == "device":
            return tail.strip()
        if tail.strip():
            return ""
        return head.strip()
    except (ValueError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_strip_sysprop_prefix", "Failed to strip prefix", exc)
        ) from exc


def _is_usb_tree_device_line(label: str) -> bool:
    """
    Purpose: Determine whether a line label represents a USB device.
    Ties: Used by USB tree parser to filter metadata lines.
    Inputs: label is a cleaned line string.
    Outputs: True if the label should be treated as a device.
    Side effects: None.
    Why: Prevents metadata from polluting device lists.
    """
    try:
        candidate = label.strip().lower()
        if not candidate:
            return False
        if any(prefix in candidate for prefix in _USB_PROPERTY_PREFIXES):
            return False
        if candidate in {"usb", "usb bus"}:
            return False
        return True
    except (AttributeError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_is_usb_tree_device_line", "Failed to classify label", exc)
        ) from exc


def _extract_usb_tree_items(raw: str) -> list[dict[str, int | str]]:
    """
    Purpose: Extract labeled USB tree items from raw system_profiler output.
    Ties: Used by device parsing and benchmarks.
    Inputs: raw text from system_profiler.
    Outputs: List of dicts with label and indent keys.
    Side effects: None.
    Why: Produces stable device labels for UI rendering and tests.
    """
    try:
        items: list[dict[str, int | str]] = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip(" "))
            label = _strip_sysprop_prefix(line)
            if not label:
                continue
            if label.endswith(":"):
                label = label[:-1].strip()
            if not _is_usb_tree_device_line(label):
                continue
            items.append({"label": label, "indent": indent})
        return items
    except (AttributeError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_extract_usb_tree_items", "Failed to parse USB tree", exc)
        ) from exc
