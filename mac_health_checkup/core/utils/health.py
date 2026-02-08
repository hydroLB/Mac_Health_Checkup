from __future__ import annotations

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/utils/health.py"


def health_from_percent(value: float) -> str:
    """
    Summary
    Map a health percentage to a qualitative label.

    Inputs
    value: Percent value from 0 to 100.

    Outputs
    Health label string.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when mapping fails.

    Ties to other methods
    Used by battery and SSD diagnostics.

    Why this exists
    Provides a consistent human readable health label.
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
