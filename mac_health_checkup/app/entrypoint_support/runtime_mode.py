from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from typing import Protocol, TextIO, TypeVar

from mac_health_checkup.core.config import Config
from mac_health_checkup.core.types import JsonDict, RedactionConfig
from mac_health_checkup.core.utils import LogContext, LoggingFields, StructuredLogger, format_error
from mac_health_checkup.core.utils.error_boundary import ErrorBoundary

MODULE_PATH = "mac_health_checkup/app/entrypoint.py"

_RuntimeStateT = TypeVar("_RuntimeStateT")
_ShutdownManagerT = TypeVar("_ShutdownManagerT", bound="_ShutdownManagerProtocol")


class _StartupConfigReportProtocol(Protocol):
    """
    Summary
    Describe the startup config report payload surface used by runtime initialization.

    Inputs
    None.

    Outputs
    Structural protocol for startup validation reports.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `initialize_runtime`.

    Why this exists
    Runtime startup logging depends only on the serialized payload contract, not the concrete report type.
    """

    def to_log_payload(self) -> JsonDict:
        """
        Summary
        Return the structured startup validation payload.

        Inputs
        None.

        Outputs
        `JsonDict` payload.

        Side effects
        None.

        Error handling
        Implementations may raise runtime-specific serialization errors.

        Ties to other methods
        Used by `initialize_runtime`.

        Why this exists
        Runtime initialization logs one startup validation event and needs a typed payload hook.
        """


class _ShutdownManagerProtocol(Protocol):
    """
    Summary
    Describe the shutdown manager surface needed by runtime and mode helpers.

    Inputs
    None.

    Outputs
    Structural protocol for shutdown managers.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `initialize_runtime` and `finish_mode`.

    Why this exists
    Entrypoint support helpers should depend on the smallest lifecycle surface possible.
    """

    def install_handlers(self) -> None:
        """
        Summary
        Install process shutdown handlers.

        Inputs
        None.

        Outputs
        None.

        Side effects
        May register signal handlers.

        Error handling
        Implementations may raise lifecycle-specific errors.

        Ties to other methods
        Used by `initialize_runtime`.

        Why this exists
        Startup installs shutdown handling once per process.
        """

    def trigger_shutdown(self) -> None:
        """
        Summary
        Trigger shutdown bookkeeping.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Signals shutdown to waiting components.

        Error handling
        Implementations may raise lifecycle-specific errors.

        Ties to other methods
        Used by `finish_mode`.

        Why this exists
        Mode helpers should share one shutdown completion path.
        """

    def wait_for_shutdown(self) -> None:
        """
        Summary
        Wait for shutdown to be requested.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Blocks until shutdown is requested.

        Error handling
        Implementations may raise lifecycle-specific errors.

        Ties to other methods
        Used by serve mode helpers that keep running until shutdown is signaled.

        Why this exists
        The shared shutdown contract should match the concrete lifecycle manager surface.
        """


class _ConfigureLoggingOnceProtocol(Protocol):
    """
    Summary
    Describe the logging configuration callable used during runtime initialization.

    Inputs
    None.

    Outputs
    Structural callable protocol.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `initialize_runtime`.

    Why this exists
    `Callable[..., None]` is too loose for strict mypy in this repo, so startup wiring uses an explicit callable protocol.
    """

    def __call__(
        self,
        redaction: RedactionConfig,
        fields: LoggingFields,
        level: int = ...,
        *,
        stream: TextIO | None = ...,
    ) -> None:
        """
        Summary
        Configure process logging once for the current runtime.

        Inputs
        redaction: Logging redaction policy object.
        fields: Structured logging field names.
        level: Logging level.
        stream: Destination stream.

        Outputs
        None.

        Side effects
        May reconfigure process logging.

        Error handling
        Implementations may raise logging setup errors.

        Ties to other methods
        Used by `initialize_runtime`.

        Why this exists
        Startup initialization needs a typed callable surface without introducing `Any`.
        """


def initialize_runtime(
    *,
    get_config_fn: Callable[[], Config],
    build_startup_config_validation_report_fn: Callable[[Config], _StartupConfigReportProtocol],
    configure_logging_once_fn: _ConfigureLoggingOnceProtocol,
    new_correlation_id_fn: Callable[[], str],
    structured_logger_type: type[StructuredLogger],
    logging_fields_type: type[LoggingFields],
    shutdown_manager_type: Callable[[], _ShutdownManagerT],
    state_factory: Callable[[Config, StructuredLogger, LogContext, _ShutdownManagerT], _RuntimeStateT],
) -> _RuntimeStateT:
    """
    Summary
    Load configuration, configure logging, and install shutdown handlers for the current process.

    Inputs
    get_config_fn: Config loader callback.
    build_startup_config_validation_report_fn: Startup report builder callback.
    configure_logging_once_fn: Logging configuration callback.
    new_correlation_id_fn: Correlation id generator callback.
    structured_logger_type: Structured logger constructor.
    logging_fields_type: Logging field container constructor.
    shutdown_manager_type: Shutdown manager constructor.
    state_factory: Runtime state constructor.

    Outputs
    Runtime state instance created by `state_factory`.

    Side effects
    Reads config, configures process logging, writes a startup log event, and installs signal handlers.

    Error handling
    Raises `RuntimeError` with module and method context when runtime setup fails unexpectedly.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._initialize_runtime`.

    Why this exists
    Startup wiring should stay separate from mode routing so the entrypoint file can remain a coordinator.
    """
    try:
        cfg = get_config_fn()
        startup_config_report = build_startup_config_validation_report_fn(cfg)
        fields = logging_fields_type(
            event_field=cfg.logging.event_field,
            corr_id_field=cfg.logging.correlation_id_field,
            component_field=cfg.logging.component_field,
        )
        configure_logging_once_fn(cfg.logging.redaction(), fields, level=logging.INFO, stream=sys.stderr)
        context = LogContext(component="entrypoint", corr_id=new_correlation_id_fn())
        logger = structured_logger_type("mac_health_checkup", cfg.logging.redaction(), fields)
        logger.info(
            "startup config validated",
            event="startup_config_validated",
            context=context,
            payload=startup_config_report.to_log_payload(),
        )
        shutdown = shutdown_manager_type()
        shutdown.install_handlers()
        return state_factory(cfg, logger, context, shutdown)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "initialize_runtime", "Failed to initialize runtime", exc)
        ) from exc


def boundary_from_args(args: argparse.Namespace | None) -> ErrorBoundary:
    """
    Summary
    Resolve the runtime boundary from parsed entrypoint args.

    Inputs
    args: Parsed args or `None` when parsing failed before boundary mode could be inferred.

    Outputs
    `ErrorBoundary` enum value.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when boundary resolution fails unexpectedly.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint.main`.

    Why this exists
    Entrypoint failures should map to a boundary-aware error policy instead of ad-hoc generic handling.
    """
    try:
        if args is None:
            return ErrorBoundary.CLI
        if bool(getattr(args, "serve", False)):
            return ErrorBoundary.API
        if bool(getattr(args, "cli", False)):
            return ErrorBoundary.CLI
        if bool(getattr(args, "snapshot_json", False)) or bool(getattr(args, "snapshot_json_out", None)):
            return ErrorBoundary.CLI
        if bool(getattr(args, "export", None)) or bool(getattr(args, "diff_snapshots", None)):
            return ErrorBoundary.CLI
        return ErrorBoundary.UI
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "boundary_from_args", "Failed to resolve entrypoint boundary", exc)
        ) from exc


def finish_mode(shutdown: _ShutdownManagerProtocol, code: int) -> int:
    """
    Summary
    Trigger shutdown bookkeeping before returning a mode exit code.

    Inputs
    shutdown: Installed shutdown manager.
    code: Mode exit code.

    Outputs
    The provided exit code.

    Side effects
    Triggers shutdown.

    Error handling
    Propagates shutdown manager failures to the caller.

    Ties to other methods
    Used by mode helpers in `mac_health_checkup.app.entrypoint`.

    Why this exists
    Mode helpers should not repeat the same shutdown trigger boilerplate.
    """
    shutdown.trigger_shutdown()
    return code
