from __future__ import annotations

import errno
from dataclasses import dataclass
from enum import Enum

from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/utils/error_boundary.py"


class ErrorBoundary(str, Enum):
    """
    Summary
    Enumerate runtime boundaries where exceptions are mapped into stable user-facing failures.

    Inputs
    None.

    Outputs
    String enum values for boundary names.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `map_boundary_exception` and boundary entrypoints.

    Why this exists
    Boundary-aware mapping keeps CLI, UI, and API failures consistent and operable.
    """

    CLI = "cli"
    UI = "ui"
    API = "api"


class ErrorCode(str, Enum):
    """
    Summary
    Enumerate machine-readable error codes shared across boundaries.

    Inputs
    None.

    Outputs
    String enum values for stable error identifiers.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `BoundaryError` and `map_boundary_exception`.

    Why this exists
    Stable codes improve debugging, tests, and client-side handling.
    """

    INPUT_INVALID = "input_invalid"
    CONFIG_INVALID = "config_invalid"
    AUTH_FAILED = "auth_failed"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"
    FORBIDDEN = "forbidden"
    CLIENT_DISCONNECTED = "client_disconnected"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class BoundaryError:
    """
    Summary
    Carry normalized boundary failure details.

    Inputs
    code: Stable error code.
    boundary: Runtime boundary where the failure happened.
    user_message: Human-readable message safe for user output.
    detail: Low-level detail string for diagnostics.
    http_status: HTTP status code used by API boundaries.
    exit_code: Process exit code used by CLI/UI boundaries.

    Outputs
    Immutable boundary error model.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Returned by `map_boundary_exception` and rendered by boundary handlers.

    Why this exists
    Centralized error metadata prevents boundary-specific drift in failure behavior.
    """

    code: ErrorCode
    boundary: ErrorBoundary
    user_message: str
    detail: str
    http_status: int
    exit_code: int

    def to_api_payload(self) -> JsonDict:
        """
        Summary
        Render a boundary error as a standardized API payload.

        Inputs
        None.

        Outputs
        `JsonDict` with `ok`, `error`, and `message`.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when serialization data is invalid.

        Ties to other methods
        Used by HTTP handlers at the API boundary.

        Why this exists
        API clients need stable machine-readable error structures.
        """
        try:
            return {
                "ok": False,
                "error": self.code.value,
                "message": self.user_message,
            }
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "BoundaryError.to_api_payload", "Failed to build API payload", exc)
            ) from exc

    def to_stderr_line(self, *, module_path: str, method: str) -> str:
        """
        Summary
        Render a boundary error as one standardized stderr line.

        Inputs
        module_path: Module path for context.
        method: Method name for context.

        Outputs
        Single-line formatted error string.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when formatting fails unexpectedly.

        Ties to other methods
        Used by CLI and UI script boundaries.

        Why this exists
        Consistent stderr formatting keeps failures actionable without tracebacks.
        """
        try:
            message = f"[{self.boundary.value}:{self.code.value}] {self.user_message}"
            if self.detail:
                message = f"{message} ({self.detail})"
            return f"{module_path}:{method} {message}"
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "BoundaryError.to_stderr_line", "Failed to format stderr line", exc)
            ) from exc


def is_client_disconnect_exception(exc: BaseException) -> bool:
    """
    Summary
    Determine whether an exception represents a normal client disconnect.

    Inputs
    exc: Exception raised during network I/O.

    Outputs
    True when the exception indicates a disconnect, otherwise false.

    Side effects
    None.

    Error handling
    Returns false when input inspection fails.

    Ties to other methods
    Used by API handlers and `_infer_error_code`.

    Why this exists
    Client disconnects should not be treated as server faults.
    """
    try:
        if isinstance(exc, (BrokenPipeError, ConnectionResetError)):
            return True
        if isinstance(exc, OSError):
            return getattr(exc, "errno", None) in (errno.EPIPE, errno.ECONNRESET)
        return False
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError):
        return False


def map_boundary_exception(
    exc: BaseException,
    *,
    boundary: ErrorBoundary,
    default_message: str,
) -> BoundaryError:
    """
    Summary
    Map an exception into a standardized boundary error model.

    Inputs
    exc: Exception raised at a boundary.
    boundary: Boundary where the exception occurred.
    default_message: Fallback high-level message for user output.

    Outputs
    `BoundaryError` containing normalized code, message, and status metadata.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when mapping fails.

    Ties to other methods
    Used by CLI, UI, and API boundaries for centralized failure mapping.

    Why this exists
    Prevents inconsistent ad-hoc boundary error handling across entrypoints.
    """
    try:
        code = _infer_error_code(exc)
        user_message = _user_message_for_code(code=code, boundary=boundary, default_message=default_message)
        detail = str(exc).strip()
        status = _http_status_for_code(code)
        exit_code = _exit_code_for_code(code)
        return BoundaryError(
            code=code,
            boundary=boundary,
            user_message=user_message,
            detail=detail,
            http_status=status,
            exit_code=exit_code,
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as map_exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "map_boundary_exception", "Failed to map boundary exception", map_exc)
        ) from map_exc


def _infer_error_code(exc: BaseException) -> ErrorCode:
    """
    Summary
    Classify an exception into a stable error code.

    Inputs
    exc: Exception raised at a boundary.

    Outputs
    `ErrorCode` classification.

    Side effects
    None.

    Error handling
    Never raises for unknown exceptions; defaults to `ErrorCode.INTERNAL_ERROR`.

    Ties to other methods
    Used by `map_boundary_exception`.

    Why this exists
    Consistent code inference keeps boundary behavior deterministic.
    """
    try:
        if is_client_disconnect_exception(exc):
            return ErrorCode.CLIENT_DISCONNECTED
        if isinstance(exc, PermissionError):
            return ErrorCode.FORBIDDEN
        if isinstance(exc, (FileNotFoundError, ModuleNotFoundError)):
            return ErrorCode.NOT_FOUND
        if isinstance(exc, TimeoutError):
            return ErrorCode.TIMEOUT

        text = str(exc).lower()
        if "unauthorized" in text or "auth" in text:
            return ErrorCode.AUTH_FAILED
        if "rate_limited" in text or "too many requests" in text:
            return ErrorCode.RATE_LIMITED
        if "timeout" in text:
            return ErrorCode.TIMEOUT
        if "not found" in text:
            return ErrorCode.NOT_FOUND
        if "mac_health_checkup_" in text or "config" in text:
            return ErrorCode.CONFIG_INVALID
        if isinstance(exc, (ValueError, TypeError)):
            return ErrorCode.INPUT_INVALID
        return ErrorCode.INTERNAL_ERROR
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError):
        return ErrorCode.INTERNAL_ERROR


def _user_message_for_code(*, code: ErrorCode, boundary: ErrorBoundary, default_message: str) -> str:
    """
    Summary
    Build a user-facing message for a mapped error code and boundary.

    Inputs
    code: Classified error code.
    boundary: Runtime boundary.
    default_message: Fallback message from caller.

    Outputs
    Safe user-facing message.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when message lookup fails.

    Ties to other methods
    Used by `map_boundary_exception`.

    Why this exists
    Keeps boundary messages concise, explicit, and consistent.
    """
    try:
        if code is ErrorCode.INPUT_INVALID:
            return "Invalid input."
        if code is ErrorCode.CONFIG_INVALID:
            return "Invalid runtime configuration."
        if code is ErrorCode.AUTH_FAILED:
            return "Authentication failed."
        if code is ErrorCode.RATE_LIMITED:
            return "Request rate limit exceeded."
        if code is ErrorCode.NOT_FOUND:
            return "Requested resource was not found."
        if code is ErrorCode.TIMEOUT:
            return "Operation timed out."
        if code is ErrorCode.FORBIDDEN:
            return "Operation is not permitted."
        if code is ErrorCode.CLIENT_DISCONNECTED and boundary is ErrorBoundary.API:
            return "Client disconnected before response completed."
        if code is ErrorCode.INTERNAL_ERROR:
            return "Unexpected internal error."
        return default_message
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_user_message_for_code", "Failed to build user message", exc)
        ) from exc


def _http_status_for_code(code: ErrorCode) -> int:
    """
    Summary
    Map an error code to its API boundary HTTP status.

    Inputs
    code: Classified error code.

    Outputs
    Integer HTTP status code.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when mapping fails.

    Ties to other methods
    Used by `map_boundary_exception`.

    Why this exists
    API responses should map codes to consistent status semantics.
    """
    try:
        if code is ErrorCode.INPUT_INVALID:
            return 400
        if code is ErrorCode.AUTH_FAILED:
            return 401
        if code is ErrorCode.FORBIDDEN:
            return 403
        if code is ErrorCode.NOT_FOUND:
            return 404
        if code is ErrorCode.RATE_LIMITED:
            return 429
        if code is ErrorCode.TIMEOUT:
            return 504
        if code is ErrorCode.CLIENT_DISCONNECTED:
            return 499
        if code is ErrorCode.CONFIG_INVALID:
            return 500
        return 500
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_http_status_for_code", "Failed to map HTTP status", exc)
        ) from exc


def _exit_code_for_code(code: ErrorCode) -> int:
    """
    Summary
    Map an error code to a process exit code for CLI and UI boundaries.

    Inputs
    code: Classified error code.

    Outputs
    Integer process exit code.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when mapping fails.

    Ties to other methods
    Used by `map_boundary_exception`.

    Why this exists
    Exit codes should remain deterministic while preserving existing script compatibility.
    """
    try:
        # Keep compatibility with pre-unification script behavior.
        if code in (
            ErrorCode.INPUT_INVALID,
            ErrorCode.CONFIG_INVALID,
            ErrorCode.NOT_FOUND,
            ErrorCode.AUTH_FAILED,
            ErrorCode.RATE_LIMITED,
            ErrorCode.TIMEOUT,
            ErrorCode.FORBIDDEN,
            ErrorCode.CLIENT_DISCONNECTED,
        ):
            return 1
        return 1
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_exit_code_for_code", "Failed to map exit code", exc)
        ) from exc
