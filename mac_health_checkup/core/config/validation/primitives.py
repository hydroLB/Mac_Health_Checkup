from __future__ import annotations

from typing import Callable

from mac_health_checkup.core.types import JsonValue
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/validation/primitives.py"


def require_int(min_value: int, max_value: int) -> Callable[[JsonValue], int]:
    """
    Summary
    Build an int validator for a bounded range.

    Inputs
    min_value: Inclusive minimum.
    max_value: Inclusive maximum.

    Outputs
    Callable that validates and returns an `int`.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when the validator cannot be built.
    Raises `ValueError` with module and method context when a value is invalid.

    Ties to other methods
    Used by config parsing and `config_max_bytes` for environment overrides.

    Why this exists
    Keeps numeric validation explicit, reusable, and safe under `mypy --strict`.
    """
    try:

        def _validator(value: JsonValue) -> int:
            """
            Summary
            Validate and normalize an integer config value.

            Inputs
            value: Raw JSON value.

            Outputs
            Validated int within bounds.

            Side effects
            None.

            Error handling
            Raises `ValueError` with module and method context on invalid inputs.

            Ties to other methods
            Returned by `require_int` and used by section parsers.

            Why this exists
            Encapsulates parsing and bounds enforcement in a single, reusable callable.
            """
            try:
                if isinstance(value, bool):
                    raise ValueError("bool is not an int for config")
                if isinstance(value, (int, float)):
                    int_value = int(value)
                elif isinstance(value, str) and value.strip():
                    int_value = int(value.strip())
                else:
                    raise ValueError("missing int value")
                if int_value < min_value or int_value > max_value:
                    raise ValueError(f"int out of range {min_value}..{max_value}")
                return int_value
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    format_error(MODULE_PATH, "require_int._validator", "Invalid int value", exc)
                ) from exc

        return _validator
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "require_int", "Failed to build int validator", exc)
        ) from exc


def require_float(min_value: float, max_value: float) -> Callable[[JsonValue], float]:
    """
    Summary
    Build a float validator for a bounded range.

    Inputs
    min_value: Inclusive minimum.
    max_value: Inclusive maximum.

    Outputs
    Callable that validates and returns a `float`.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when the validator cannot be built.
    Raises `ValueError` with module and method context when a value is invalid.

    Ties to other methods
    Used by section parsers for config values that are floats.

    Why this exists
    Standardizes float parsing and validation across all config reads.
    """
    try:

        def _validator(value: JsonValue) -> float:
            """
            Summary
            Validate and normalize a float config value.

            Inputs
            value: Raw JSON value.

            Outputs
            Validated float within bounds.

            Side effects
            None.

            Error handling
            Raises `ValueError` with module and method context on invalid inputs.

            Ties to other methods
            Returned by `require_float` and used by section parsers.

            Why this exists
            Encapsulates parsing and bounds enforcement in a single reusable callable.
            """
            try:
                if isinstance(value, bool):
                    raise ValueError("bool is not a float for config")
                if isinstance(value, (int, float)):
                    float_value = float(value)
                elif isinstance(value, str) and value.strip():
                    float_value = float(value.strip())
                else:
                    raise ValueError("missing float value")
                if float_value < min_value or float_value > max_value:
                    raise ValueError(f"float out of range {min_value}..{max_value}")
                return float_value
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    format_error(MODULE_PATH, "require_float._validator", "Invalid float value", exc)
                ) from exc

        return _validator
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "require_float", "Failed to build float validator", exc)
        ) from exc


def require_bool(value: JsonValue) -> bool:
    """
    Summary
    Validate and normalize a boolean config value.

    Inputs
    value: Raw JSON value.

    Outputs
    Validated boolean.

    Side effects
    None.

    Error handling
    Raises `ValueError` with module and method context on invalid inputs.

    Ties to other methods
    Used by section parsers to validate boolean knobs.

    Why this exists
    Ensures boolean values are not silently mis-typed in JSON overrides.
    """
    try:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower() == "true"
        raise ValueError("invalid bool")
    except (TypeError, ValueError) as exc:
        raise ValueError(format_error(MODULE_PATH, "require_bool", "Invalid bool value", exc)) from exc


def require_str(value: JsonValue) -> str:
    """
    Summary
    Validate and normalize a string config value.

    Inputs
    value: Raw JSON value.

    Outputs
    Validated string.

    Side effects
    None.

    Error handling
    Raises `ValueError` with module and method context on invalid inputs.

    Ties to other methods
    Used by section parsers for string settings.

    Why this exists
    Keeps string values strict to avoid accidental `null` propagation into UI and shell commands.
    """
    try:
        if isinstance(value, str) and value.strip():
            return value
        raise ValueError("invalid string")
    except (TypeError, ValueError) as exc:
        raise ValueError(format_error(MODULE_PATH, "require_str", "Invalid str value", exc)) from exc
