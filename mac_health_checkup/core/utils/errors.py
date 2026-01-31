from __future__ import annotations

from typing import Optional

MODULE_PATH = "mac_health_checkup/core/utils/errors.py"


def format_error(module: str, func: str, message: str, exc: Optional[BaseException] = None) -> str:
    """
    Purpose: Build a consistent error message with module and function context.
    Ties: Used across utilities and diagnostics for precise error reporting.
    Inputs: module is the module path, func is the function name, message is the detail, exc is optional.
    Outputs: A formatted error string suitable for logs or raised exceptions.
    Side effects: None.
    Why: Standardized errors make debugging and support much faster.
    """
    try:
        base = f"{module}:{func} {message}"
        if exc is None:
            return base
        return f"{base} ({type(exc).__name__}: {exc})"
    except (AttributeError, TypeError, ValueError) as inner_exc:
        return f"{MODULE_PATH}:format_error failed ({type(inner_exc).__name__}: {inner_exc})"
