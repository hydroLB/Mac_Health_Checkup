from __future__ import annotations

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/utils/health.py"


def health_from_percent(value: float) -> str:
    """
    Purpose: Map a health percentage to a qualitative label.
    Ties: Used by battery and SSD diagnostics.
    Inputs: value is a percent from 0 to 100.
    Outputs: Health label string.
    Side effects: None.
    Why: Provides a consistent human readable health label.
    """
    try:
        if value >= 90:
            return "excellent"
        if value >= 80:
            return "good"
        if value >= 65:
            return "fair"
        return "degraded"
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "health_from_percent", "Failed to map health", exc)
        ) from exc
