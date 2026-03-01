from __future__ import annotations

import threading
from typing import Sequence

from mac_health_checkup.core.utils.data import (
    fmt_bytes,
    fmt_percent,
    fmt_temp_c,
    fmt_temp_f,
    safe_float,
    safe_int,
)
from mac_health_checkup.core.utils.error_boundary import (
    BoundaryError,
    ErrorBoundary,
    ErrorCode,
    is_client_disconnect_exception,
    map_boundary_exception,
)
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.health import health_from_percent
from mac_health_checkup.core.utils.loggers import (
    LogContext,
    LoggingFields,
    StructuredLogger,
    configure_logging_once,
    new_correlation_id,
)
from mac_health_checkup.core.utils.qr import maybe_render_qr_ansiutf8, qrencode_available
from mac_health_checkup.core.utils.regex_utils import (
    hz_from_text,
    regex_extract_float,
    regex_extract_int,
    regex_extract_str,
)
from mac_health_checkup.core.utils.text import calc_col_widths, render_table_parts
from mac_health_checkup.core.utils.usb_tree import (
    is_usb_tree_device_line,
    parse_usb_tree_items,
    strip_sysprop_prefix,
)

__all__ = [
    "format_error",
    "BoundaryError",
    "ErrorBoundary",
    "ErrorCode",
    "map_boundary_exception",
    "is_client_disconnect_exception",
    "safe_int",
    "safe_float",
    "fmt_bytes",
    "fmt_percent",
    "fmt_temp_c",
    "fmt_temp_f",
    "hz_from_text",
    "regex_extract_float",
    "regex_extract_int",
    "regex_extract_str",
    "calc_col_widths",
    "render_table_parts",
    "safe_run",
    "system_profiler_out",
    "health_from_percent",
    "maybe_render_qr_ansiutf8",
    "qrencode_available",
    "parse_usb_tree_items",
    "is_usb_tree_device_line",
    "strip_sysprop_prefix",
    "LogContext",
    "LoggingFields",
    "StructuredLogger",
    "configure_logging_once",
    "new_correlation_id",
]


def safe_run(
    cmd: Sequence[str],
    context: str,
    *,
    allow_sudo: bool,
    timeout: int | None = None,
    cancel_event: threading.Event | None = None,
) -> tuple[str | None, str | None]:
    """
    Summary
    Lazily dispatch to the shell execution boundary without importing shell internals at package import time.

    Inputs
    cmd: Command argv list.
    context: Context label for boundary errors.
    allow_sudo: Whether sudo retry is allowed.
    timeout: Optional timeout override in seconds.
    cancel_event: Optional cancellation event.

    Outputs
    Tuple of `(stdout, error)` from the shell boundary.

    Side effects
    Executes subprocess commands through `mac_health_checkup.core.utils.shell.safe_run`.

    Error handling
    Propagates `RuntimeError` raised by `safe_run` with contextual errors.

    Ties to other methods
    Used by diagnostics and GUI sections via `mac_health_checkup.core.utils` public surface.

    Why this exists
    Avoids circular imports between `core.config` and `core.utils` while preserving a stable public import surface.
    """
    from mac_health_checkup.core.utils.shell import safe_run as _safe_run

    return _safe_run(
        cmd,
        context,
        allow_sudo=allow_sudo,
        timeout=timeout,
        cancel_event=cancel_event,
    )


def system_profiler_out(
    data_type: str, context: str, timeout: int | None = None
) -> tuple[str | None, str | None]:
    """
    Summary
    Lazily dispatch to `system_profiler` helper without importing shell internals at package import time.

    Inputs
    data_type: `system_profiler` data type argument.
    context: Context label for boundary errors.
    timeout: Optional timeout override in seconds.

    Outputs
    Tuple of `(stdout, error)` from the shell boundary.

    Side effects
    Executes `system_profiler` through `mac_health_checkup.core.utils.shell.system_profiler_out`.

    Error handling
    Propagates `RuntimeError` raised by `system_profiler_out` with contextual errors.

    Ties to other methods
    Used by diagnostics collectors via `mac_health_checkup.core.utils` public surface.

    Why this exists
    Avoids circular imports between `core.config` and `core.utils` while preserving a stable public import surface.
    """
    from mac_health_checkup.core.utils.shell import system_profiler_out as _system_profiler_out

    return _system_profiler_out(data_type, context, timeout=timeout)
