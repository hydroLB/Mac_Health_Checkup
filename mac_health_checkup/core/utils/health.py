from __future__ import annotations

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/utils/health.py"


def health_from_percent(
    value: float,
    *,
    excellent_min: float,
    good_min: float,
    fair_min: float,
) -> str:
    """
    Summary
    Map a health percentage to a qualitative label.

    Inputs
    value: Percent value from 0 to 100.
    excellent_min: Lower bound for "excellent" classification.
    good_min: Lower bound for "good" classification.
    fair_min: Lower bound for "fair" classification.

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
        if excellent_min <= good_min:
            raise ValueError("excellent_min must be greater than good_min")
        if good_min <= fair_min:
            raise ValueError("good_min must be greater than fair_min")
        if value >= excellent_min:
            return "excellent"
        if value >= good_min:
            return "good"
        if value >= fair_min:
            return "fair"
        return "degraded"
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "health_from_percent", "Failed to map health", exc)
        ) from exc
