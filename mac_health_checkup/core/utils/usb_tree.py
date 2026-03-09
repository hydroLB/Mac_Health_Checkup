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
    Summary
    Remove system property prefixes from USB tree lines.

    Inputs
    line: Raw USB tree line.

    Outputs
    Cleaned label or empty string when the line is metadata.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by USB parsing helpers to isolate device labels.

    Why this exists
    Keeps device label extraction noise free.
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
    Summary
    Determine whether a line label represents a USB device.

    Inputs
    label: Cleaned line string.

    Outputs
    True when the label should be treated as a device.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when classification fails unexpectedly.

    Ties to other methods
    Used by USB tree parser to filter metadata lines.

    Why this exists
    Prevents metadata from polluting device lists.
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
    Summary
    Extract labeled USB tree items from raw system_profiler output.

    Inputs
    raw: Raw text from system_profiler.

    Outputs
    List of dicts with label and indent keys.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by device parsing and benchmarks.

    Why this exists
    Produces stable device labels for UI rendering and tests.
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


def strip_sysprop_prefix(line: str) -> str:
    """
    Summary
    Public wrapper around USB property-prefix stripping.

    Inputs
    line: Raw USB tree line.

    Outputs
    Cleaned label or empty string when the line is metadata.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Delegates to `_strip_sysprop_prefix`.

    Why this exists
    Exposes a stable public surface without requiring callers to import underscore-prefixed internals.
    """
    try:
        return _strip_sysprop_prefix(line)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "strip_sysprop_prefix", "Failed to strip prefix", exc)
        ) from exc


def is_usb_tree_device_line(label: str) -> bool:
    """
    Summary
    Public wrapper around USB device-line classification.

    Inputs
    label: Cleaned line label candidate.

    Outputs
    True when the label should be treated as a USB device.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when classification fails unexpectedly.

    Ties to other methods
    Delegates to `_is_usb_tree_device_line`.

    Why this exists
    Keeps internal underscore helpers private while still offering a stable public API.
    """
    try:
        return _is_usb_tree_device_line(label)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "is_usb_tree_device_line", "Failed to classify line", exc)
        ) from exc


def parse_usb_tree_items(raw: str) -> list[dict[str, int | str]]:
    """
    Summary
    Public wrapper around USB tree extraction.

    Inputs
    raw: Raw `system_profiler` USB tree text.

    Outputs
    List of parsed items with `label` and `indent`.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Delegates to `_extract_usb_tree_items`.

    Why this exists
    Provides a supported import surface for USB parsing helpers while preserving existing internal helpers for tests.
    """
    try:
        return _extract_usb_tree_items(raw)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "parse_usb_tree_items", "Failed to parse USB tree items", exc)
        ) from exc
