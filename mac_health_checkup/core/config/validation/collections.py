from __future__ import annotations

from mac_health_checkup.core.types import JsonValue
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/validation/collections.py"


def require_list_str(value: JsonValue) -> list[str]:
    """
    Summary
    Validate that a JSON value is a list of strings.

    Inputs
    value: Raw JSON value.

    Outputs
    List of strings.

    Side effects
    None.

    Error handling
    Raises `ValueError` with module and method context on invalid inputs.

    Ties to other methods
    Used by config section parsers for list-based settings.

    Why this exists
    Makes complex nested config shapes explicit and keeps parsing code small.
    """
    try:
        if not isinstance(value, list):
            raise ValueError("expected list")
        out: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("expected list of strings")
            out.append(item)
        return out
    except (TypeError, ValueError) as exc:
        raise ValueError(
            format_error(MODULE_PATH, "require_list_str", "Invalid list[str] value", exc)
        ) from exc


def require_dict_str_int(value: JsonValue) -> dict[str, int]:
    """
    Summary
    Validate that a JSON value is a dict[str, int] with integer-like values.

    Inputs
    value: Raw JSON value.

    Outputs
    Dict mapping strings to ints.

    Side effects
    None.

    Error handling
    Raises `ValueError` with module and method context on invalid inputs.

    Ties to other methods
    Used by GUI config parsing for per-section sizing rules.

    Why this exists
    Keeps dict parsing deterministic and avoids `Any` leakage under strict typing.
    """
    try:
        if not isinstance(value, dict):
            raise ValueError("expected dict")
        out: dict[str, int] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError("expected string keys")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError("expected int values")
            out[k] = int(v)
        return out
    except (TypeError, ValueError) as exc:
        raise ValueError(
            format_error(MODULE_PATH, "require_dict_str_int", "Invalid dict[str,int] value", exc)
        ) from exc


def require_dict_str_str(value: JsonValue) -> dict[str, str]:
    """
    Summary
    Validate that a JSON value is a dict[str, str].

    Inputs
    value: Raw JSON value.

    Outputs
    Dict mapping strings to strings.

    Side effects
    None.

    Error handling
    Raises `ValueError` with module and method context on invalid inputs.

    Ties to other methods
    Used by GUI parsing for token normalization maps.

    Why this exists
    Enforces config shape and keeps downstream logic from handling unexpected types.
    """
    try:
        if not isinstance(value, dict):
            raise ValueError("expected dict")
        out: dict[str, str] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError("expected string keys")
            if not isinstance(v, str):
                raise ValueError("expected string values")
            out[k] = v
        return out
    except (TypeError, ValueError) as exc:
        raise ValueError(
            format_error(MODULE_PATH, "require_dict_str_str", "Invalid dict[str,str] value", exc)
        ) from exc
