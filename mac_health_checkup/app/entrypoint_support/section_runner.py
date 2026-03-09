from __future__ import annotations

from collections.abc import Callable, Iterable

from mac_health_checkup.app.cli import ConsoleHost
from mac_health_checkup.core.utils import LogContext, StructuredLogger


def run_sections_best_effort(
    host: ConsoleHost,
    *,
    logger: StructuredLogger | None,
    context: LogContext | None,
    section_keys: Iterable[str],
    run_section_fn: Callable[[ConsoleHost, str], object],
) -> int:
    """
    Summary
    Run all configured sections without letting one failure abort the overall run.

    Inputs
    host: Section host that receives render output.
    logger: Optional structured logger for section lifecycle logs.
    context: Optional log context used when logging is enabled.
    section_keys: Ordered section keys to execute.
    run_section_fn: Section execution callback.

    Outputs
    Exit code `0` when all sections run without raising, else `1`.

    Side effects
    Executes section handlers and mutates the host output stores.

    Error handling
    Captures section exceptions into the host field output and continues. Never raises.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._run_sections_best_effort`.

    Why this exists
    Ensures the CLI remains resilient even when individual diagnostics are unavailable on a given macOS build.
    """
    exit_code = 0
    for key in section_keys:
        _log_section_start(logger=logger, context=context, key=key)
        try:
            result = run_section_fn(host, key)
            _record_section_success(host, key=key, result=result, logger=logger, context=context)
        except Exception as exc:
            exit_code = 1
            _record_section_failure(host, key=key, exc=exc, logger=logger, context=context)
    return exit_code


def _log_section_start(*, logger: StructuredLogger | None, context: LogContext | None, key: str) -> None:
    """
    Summary
    Emit a section start log when logging is enabled.

    Inputs
    logger: Optional structured logger.
    context: Optional log context.
    key: Section key.

    Outputs
    None.

    Side effects
    Emits a log entry when logging is configured.

    Error handling
    None. Logging is skipped when dependencies are unavailable.

    Ties to other methods
    Used by `run_sections_best_effort`.

    Why this exists
    Section start logging should be explicit and centralized.
    """
    if logger is not None and context is not None:
        logger.info("running section", event="section_start", context=context, payload={"section": key})


def _record_section_success(
    host: ConsoleHost,
    *,
    key: str,
    result: object,
    logger: StructuredLogger | None,
    context: LogContext | None,
) -> None:
    """
    Summary
    Record successful section execution results.

    Inputs
    host: ConsoleHost receiving captured diagnostics.
    key: Section key.
    result: Section execution result.
    logger: Optional structured logger.
    context: Optional log context.

    Outputs
    None.

    Side effects
    Stores diagnostics payloads and may emit a completion log.

    Error handling
    Propagates host mutation failures to the caller.

    Ties to other methods
    Used by `run_sections_best_effort`.

    Why this exists
    Successful section handling should keep diagnostics capture and logging together.
    """
    if isinstance(result, dict):
        host.diagnostics[key] = result
    if logger is not None and context is not None:
        logger.info(
            "section completed",
            event="section_end",
            context=context,
            payload={"section": key, "ok": bool(result)},
        )


def _record_section_failure(
    host: ConsoleHost,
    *,
    key: str,
    exc: Exception,
    logger: StructuredLogger | None,
    context: LogContext | None,
) -> None:
    """
    Summary
    Record a section failure without aborting the remaining run.

    Inputs
    host: ConsoleHost receiving fallback diagnostics and field output.
    key: Section key.
    exc: Section exception.
    logger: Optional structured logger.
    context: Optional log context.

    Outputs
    None.

    Side effects
    Stores a failed diagnostics payload, logs the error, and may render an error field on the host.

    Error handling
    Never raises. Host field rendering failures are logged when possible and otherwise ignored.

    Ties to other methods
    Used by `run_sections_best_effort`.

    Why this exists
    Section failures should degrade gracefully while still leaving useful debugging evidence behind.
    """
    host.diagnostics[key] = {"ok": False, "error": str(exc)}
    _log_section_failure(logger=logger, context=context, key=key, exc=exc)
    field_exc = _try_render_error_field(host, key=key, exc=exc)
    if field_exc is not None:
        _log_error_field_failure(logger=logger, context=context, key=key, exc=field_exc)


def _log_section_failure(
    *, logger: StructuredLogger | None, context: LogContext | None, key: str, exc: Exception
) -> None:
    """
    Summary
    Emit a structured log for a section execution failure.

    Inputs
    logger: Optional structured logger.
    context: Optional log context.
    key: Section key.
    exc: Section exception.

    Outputs
    None.

    Side effects
    Emits a log entry when logging is configured.

    Error handling
    None. Logging is skipped when dependencies are unavailable.

    Ties to other methods
    Used by `_record_section_failure`.

    Why this exists
    Failure logging should use one consistent payload shape.
    """
    if logger is not None and context is not None:
        logger.error(
            "section failed",
            event="section_error",
            context=context,
            payload={"section": key, "error": str(exc), "error_type": type(exc).__name__},
        )


def _try_render_error_field(host: ConsoleHost, *, key: str, exc: Exception) -> Exception | None:
    """
    Summary
    Try to render a fallback error field for a failed section.

    Inputs
    host: ConsoleHost receiving fallback output.
    key: Section key.
    exc: Original section exception.

    Outputs
    Render exception when fallback rendering fails, else `None`.

    Side effects
    Mutates host fields on success.

    Error handling
    Never raises. Converts render failures into a returned exception.

    Ties to other methods
    Used by `_record_section_failure`.

    Why this exists
    Rendering the fallback field is a best-effort step and should not interrupt the overall CLI run.
    """
    try:
        host.set_field(key, f"Error: {type(exc).__name__}", tooltip=str(exc))
        return None
    except Exception as render_exc:
        return render_exc


def _log_error_field_failure(
    *, logger: StructuredLogger | None, context: LogContext | None, key: str, exc: Exception
) -> None:
    """
    Summary
    Emit a structured log when fallback error rendering also fails.

    Inputs
    logger: Optional structured logger.
    context: Optional log context.
    key: Section key.
    exc: Rendering exception.

    Outputs
    None.

    Side effects
    Emits a log entry when logging is configured.

    Error handling
    None. Logging is skipped when dependencies are unavailable.

    Ties to other methods
    Used by `_record_section_failure`.

    Why this exists
    A failed fallback render is rare and should still leave a diagnostic breadcrumb.
    """
    if logger is not None and context is not None:
        logger.error(
            "failed to render section error field",
            event="section_error_render_failed",
            context=context,
            payload={"section": key, "error": str(exc), "error_type": type(exc).__name__},
        )
