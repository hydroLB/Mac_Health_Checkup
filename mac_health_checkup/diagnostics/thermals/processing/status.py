from __future__ import annotations

import math

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/processing/status.py"


def status_for_temp(value_c: float, *, warn: float, bad: float) -> str:
    """
    Summary
    Map a numeric temperature into an ok/warn/bad status based on thresholds.

    Inputs
    value_c: Temperature in Celsius.
    warn: Warning threshold in Celsius.
    bad: Bad threshold in Celsius.

    Outputs
    Status string: "ok", "warn", or "bad".

    Side effects
    None.

    Error handling
    Returns "ok" when the input is non-finite or threshold comparisons fail.

    Ties to other methods
    Used by thermals collectors when converting raw temperatures into UI status labels.

    Why this exists
    Keeping thresholding in one pure function ensures consistent status behavior across different temperature sources.
    """
    try:
        if not math.isfinite(float(value_c)):
            return "ok"
        value = float(value_c)
        if value >= float(bad):
            return "bad"
        if value >= float(warn):
            return "warn"
        return "ok"
    except Exception:
        return "ok"
