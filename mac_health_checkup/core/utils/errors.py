from __future__ import annotations

from typing import Optional

MODULE_PATH = "mac_health_checkup/core/utils/errors.py"


def format_error(module: str, func: str, message: str, exc: Optional[BaseException] = None) -> str:
    """
    Summary
    Build a consistent error message with module and function context.

    Inputs
    module: Module path string.
    func: Function or method name.
    message: Detail string describing the failure.
    exc: Optional exception to include (type and message).

    Outputs
    A formatted error string suitable for logs or raised exceptions.

    Side effects
    None.

    Error handling
    Never raises; returns a fallback message when formatting fails unexpectedly.

    Ties to other methods
    Used across utilities and diagnostics for precise error reporting.

    Why this exists
    Standardized errors make debugging and support much faster.
    """
    try:
        base = f"{module}:{func} {message}"
        if exc is None:
            return base
        return f"{base} ({type(exc).__name__}: {exc})"
    except (AttributeError, TypeError, ValueError) as inner_exc:
        return f"{MODULE_PATH}:format_error failed ({type(inner_exc).__name__}: {inner_exc})"
