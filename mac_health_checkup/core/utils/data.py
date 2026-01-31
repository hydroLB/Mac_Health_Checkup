from __future__ import annotations

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/utils/data.py"


def safe_int(value: object) -> int | None:
    """
    Purpose: Safely convert a value to int.
    Ties: Used by diagnostics parsing helpers.
    Inputs: value is an arbitrary object.
    Outputs: int value or None if conversion fails.
    Side effects: None.
    Why: Prevents conversion errors from propagating unexpectedly.
    """
    try:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.strip():
            return int(value.strip())
        return None
    except (TypeError, ValueError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "safe_int", "Failed to convert to int", exc)) from exc


def safe_float(value: object) -> float | None:
    """
    Purpose: Safely convert a value to float.
    Ties: Used by diagnostics parsing helpers.
    Inputs: value is an arbitrary object.
    Outputs: float value or None if conversion fails.
    Side effects: None.
    Why: Prevents conversion errors from propagating unexpectedly.
    """
    try:
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value.strip():
            return float(value.strip())
        return None
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "safe_float", "Failed to convert to float", exc)
        ) from exc


def fmt_percent(value: float | None) -> str:
    """
    Purpose: Format a float percent value for display.
    Ties: Used by diagnostics to summarize health.
    Inputs: value is a percentage or None.
    Outputs: Formatted string like "92%" or "?".
    Side effects: None.
    Why: Keeps percent formatting consistent across sections.
    """
    try:
        if value is None:
            return "?"
        return f"{value:.0f}%"
    except (TypeError, ValueError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "fmt_percent", "Failed to format percent", exc)) from exc


def fmt_bytes(value: float | None) -> str:
    """
    Purpose: Format a bytes value into a decimal unit string.
    Ties: Used by SSD diagnostics and display helpers.
    Inputs: value is bytes as float or None.
    Outputs: Formatted string like "12.3 GB" or "?".
    Side effects: None.
    Why: Keeps byte formatting consistent across sections.
    """
    try:
        if value is None:
            return "?"
        num = float(value)
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        idx = 0
        while num >= 1000 and idx < len(units) - 1:
            num /= 1000
            idx += 1
        if num >= 100:
            return f"{num:.0f} {units[idx]}"
        if num >= 10:
            return f"{num:.1f} {units[idx]}"
        return f"{num:.2f} {units[idx]}"
    except (TypeError, ValueError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "fmt_bytes", "Failed to format bytes", exc)) from exc


def fmt_temp_c(value: float | None) -> str:
    """
    Purpose: Format a temperature in Celsius.
    Ties: Used by diagnostics output formatting.
    Inputs: value is Celsius float or None.
    Outputs: Formatted string like "42C" or "?".
    Side effects: None.
    Why: Keeps temperature formatting consistent.
    """
    try:
        if value is None:
            return "?"
        return f"{value:.0f}C"
    except (TypeError, ValueError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "fmt_temp_c", "Failed to format temp", exc)) from exc


def fmt_temp_f(value: float | None) -> str:
    """
    Purpose: Format a temperature in Fahrenheit.
    Ties: Used by diagnostics output formatting.
    Inputs: value is Fahrenheit float or None.
    Outputs: Formatted string like "100F" or "?".
    Side effects: None.
    Why: Keeps temperature formatting consistent.
    """
    try:
        if value is None:
            return "?"
        return f"{value:.0f}F"
    except (TypeError, ValueError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "fmt_temp_f", "Failed to format temp", exc)) from exc
