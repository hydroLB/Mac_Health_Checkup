from __future__ import annotations

from mac_health_checkup.core.config.validation.primitives import (
    require_bool,
    require_float,
    require_int,
    require_str,
)
from mac_health_checkup.core.types import JsonDict, JsonValue
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/lookup.py"


def get_nested_value(raw: JsonDict, path: str) -> JsonValue | None:
    """
    Summary
    Retrieve a nested value from a JSON dict by dotted path.

    Inputs
    raw: Raw config dict.
    path: Dotted key path such as `logging.max_lines`.

    Outputs
    The nested JSON value, or `None` when the path is missing.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when the input is malformed.

    Ties to other methods
    Used by `get_config_value` to read overrides safely.

    Why this exists
    Centralizes dotted path traversal and error reporting so config consumers stay small.
    """
    try:
        current: JsonValue = raw
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
    except (AttributeError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "get_nested_value", "Failed to read nested value", exc)
        ) from exc


def coerce_value(default: JsonValue, value: JsonValue) -> JsonValue:
    """
    Summary
    Coerce a config override to the type implied by a default value.

    Inputs
    default: Default value which defines the expected type.
    value: Raw override value from the config JSON.

    Outputs
    Coerced value when compatible, otherwise the provided default.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when coercion fails unexpectedly.

    Ties to other methods
    Used by `get_config_value` when no explicit validator is provided.

    Why this exists
    Keeps config access ergonomic without weakening typing for core configuration paths.
    """
    try:
        if isinstance(default, bool):
            return require_bool(value)
        if isinstance(default, int) and not isinstance(default, bool):
            return require_int(-1_000_000, 1_000_000)(value)
        if isinstance(default, float):
            return require_float(-1_000_000.0, 1_000_000.0)(value)
        if isinstance(default, str):
            return require_str(value)
        if isinstance(default, list) and isinstance(value, list):
            return value
        if isinstance(default, dict) and isinstance(value, dict):
            return value
        return default
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "coerce_value", "Failed to coerce config value", exc)
        ) from exc
