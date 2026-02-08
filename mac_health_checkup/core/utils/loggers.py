from __future__ import annotations

import json
import logging
import sys
import threading
import time
from dataclasses import dataclass
from typing import Mapping, TextIO
from uuid import uuid4

from mac_health_checkup.core.types import JsonValue, RedactionConfig
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/utils/loggers.py"


@dataclass(frozen=True)
class LogContext:
    """
    Summary
    Carry structured logging context fields.

    Inputs
    component: Component identifier for the source of the event.
    corr_id: Correlation id tying related events together.

    Outputs
    Immutable context container.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Consumed by `StructuredLogger` to stamp consistent metadata.

    Why this exists
    Ensures all logs carry consistent tracing metadata.
    """

    component: str
    corr_id: str


@dataclass(frozen=True)
class LoggingFields:
    """
    Summary
    Define field names for structured logging payloads.

    Inputs
    event_field: Name of the field used for event ids.
    corr_id_field: Name of the field used for correlation ids.
    component_field: Name of the field used for component identifiers.

    Outputs
    Immutable container for log field names.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `StructuredFormatter` and `StructuredLogger`.

    Why this exists
    Keeps log field names configurable and consistent.
    """

    event_field: str
    corr_id_field: str
    component_field: str


class StructuredFormatter(logging.Formatter):
    """
    Summary
    Render structured log records as JSON strings.

    Inputs
    Uses `logging.LogRecord` data and a redaction config.

    Outputs
    JSON text for each log line.

    Side effects
    None.

    Error handling
    Never raises during formatting; returns a fallback JSON line when rendering fails.

    Ties to other methods
    Used by `configure_logging_once` to standardize log output.

    Why this exists
    Structured logs are easier to parse and safer to ship to log pipelines.
    """

    def __init__(self, redaction: RedactionConfig, fields: LoggingFields) -> None:
        """
        Summary
        Initialize the formatter with redaction settings.

        Inputs
        redaction: Redaction config with keys and replacement text.
        fields: Field name configuration for structured logs.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when initialization fails.

        Ties to other methods
        Used by `configure_logging_once` and `StructuredLogger`.

        Why this exists
        Ensures secrets are redacted consistently.
        """
        try:
            super().__init__()
            self._redaction = redaction
            self._fields = fields
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "StructuredFormatter.__init__", "Failed to initialize formatter", exc
                )
            ) from exc

    def format(self, record: logging.LogRecord) -> str:
        """
        Summary
        Convert a LogRecord into a JSON string.

        Inputs
        record: Log record containing message, level, and extra fields.

        Outputs
        JSON log line as string.

        Side effects
        None.

        Error handling
        Never raises; returns a fallback JSON object when formatting fails.

        Ties to other methods
        Called by logging handlers for each record.

        Why this exists
        Ensures consistent structured output for all logs.
        """
        try:
            payload: dict[str, JsonValue] = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
                "level": record.levelname,
                "message": record.getMessage(),
            }
            field_map = {
                self._fields.event_field: getattr(record, "event", None),
                self._fields.corr_id_field: getattr(record, "corr_id", None),
                self._fields.component_field: getattr(record, "component", None),
            }
            for field_name, value in field_map.items():
                if isinstance(value, str) and value:
                    payload[field_name] = value
            extra = getattr(record, "payload", None)
            if isinstance(extra, dict):
                payload["payload"] = _redact_dict(extra, self._redaction)
            return json.dumps(payload, ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            fallback = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
                "level": record.levelname,
                "message": f"{MODULE_PATH}:format failed ({type(exc).__name__}: {exc})",
            }
            return json.dumps(fallback, ensure_ascii=True)


class StructuredLogger:
    """
    Summary
    Emit structured logs with consistent fields and redaction.

    Inputs
    name: Logger name.
    redaction: Redaction config for payloads.
    fields: Log field name configuration.

    Outputs
    Logging methods that emit structured log records.

    Side effects
    Writes to configured logging handlers.

    Error handling
    Methods either raise `RuntimeError` with module and method context or fall back to plain error logs when needed.

    Ties to other methods
    Used across diagnostics and app modules for observability.

    Why this exists
    Standardized logs support debugging and safe telemetry without secrets.
    """

    def __init__(self, name: str, redaction: RedactionConfig, fields: LoggingFields) -> None:
        """
        Summary
        Initialize a StructuredLogger instance.

        Inputs
        name: Logger name.
        redaction: Secret scrubbing rules.
        fields: Log field name configuration.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when initialization fails.

        Ties to other methods
        Used by `get_diagnostics_logger` and other entrypoints to build loggers.

        Why this exists
        Wraps a standard logger with structured logging helpers.
        """
        try:
            self._logger = logging.getLogger(name)
            self._redaction = redaction
            self._fields = fields
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "StructuredLogger.__init__", "Failed to init logger", exc)
            ) from exc

    def log(
        self,
        level: int,
        message: str,
        *,
        event: str,
        context: LogContext,
        payload: Mapping[str, JsonValue] | None = None,
    ) -> None:
        """
        Summary
        Emit a structured log record with context and payload.

        Inputs
        level: Logging level.
        message: Log line message.
        event: Stable event id.
        context: Logging context metadata.
        payload: Optional payload dict.

        Outputs
        None.

        Side effects
        Writes to logging handlers.

        Error handling
        Never raises; logs a fallback error message when emitting the structured record fails.

        Ties to other methods
        Used by diagnostics and core utilities for consistent logging.

        Why this exists
        Centralizes structured logging behavior for safety and consistency.
        """
        try:
            extra: dict[str, object] = {
                "event": event,
                "corr_id": context.corr_id,
                "component": context.component,
            }
            if payload is not None:
                extra["payload"] = dict(payload)
            self._logger.log(level, message, extra=extra)
        except (TypeError, ValueError) as exc:
            err_msg = format_error(MODULE_PATH, "StructuredLogger.log", "Failed to emit log", exc)
            self._logger.error(err_msg)

    def debug(
        self,
        message: str,
        *,
        event: str,
        context: LogContext,
        payload: Mapping[str, JsonValue] | None = None,
    ) -> None:
        """
        Summary
        Emit a debug log entry.

        Inputs
        message: Log line message.
        event: Stable event id.
        context: Logging context metadata.
        payload: Optional payload dict.

        Outputs
        None.

        Side effects
        Writes to logging handlers.

        Error handling
        Raises `RuntimeError` with module and method context when emitting fails unexpectedly.

        Ties to other methods
        Thin wrapper around `StructuredLogger.log`.

        Why this exists
        Debug logs aid deep troubleshooting without cluttering info logs.
        """
        try:
            self.log(logging.DEBUG, message, event=event, context=context, payload=payload)
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "StructuredLogger.debug", "Failed to emit debug", exc)
            ) from exc

    def info(
        self,
        message: str,
        *,
        event: str,
        context: LogContext,
        payload: Mapping[str, JsonValue] | None = None,
    ) -> None:
        """
        Summary
        Emit an info log entry.

        Inputs
        message: Log line message.
        event: Stable event id.
        context: Logging context metadata.
        payload: Optional payload dict.

        Outputs
        None.

        Side effects
        Writes to logging handlers.

        Error handling
        Raises `RuntimeError` with module and method context when emitting fails unexpectedly.

        Ties to other methods
        Thin wrapper around `StructuredLogger.log`.

        Why this exists
        Info logs give a readable operational timeline.
        """
        try:
            self.log(logging.INFO, message, event=event, context=context, payload=payload)
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "StructuredLogger.info", "Failed to emit info", exc)
            ) from exc

    def warning(
        self,
        message: str,
        *,
        event: str,
        context: LogContext,
        payload: Mapping[str, JsonValue] | None = None,
    ) -> None:
        """
        Summary
        Emit a warning log entry.

        Inputs
        message: Log line message.
        event: Stable event id.
        context: Logging context metadata.
        payload: Optional payload dict.

        Outputs
        None.

        Side effects
        Writes to logging handlers.

        Error handling
        Raises `RuntimeError` with module and method context when emitting fails unexpectedly.

        Ties to other methods
        Thin wrapper around `StructuredLogger.log`.

        Why this exists
        Warnings surface issues without aborting workflows.
        """
        try:
            self.log(logging.WARNING, message, event=event, context=context, payload=payload)
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "StructuredLogger.warning", "Failed to emit warning", exc)
            ) from exc

    def error(
        self,
        message: str,
        *,
        event: str,
        context: LogContext,
        payload: Mapping[str, JsonValue] | None = None,
    ) -> None:
        """
        Summary
        Emit an error log entry.

        Inputs
        message: Log line message.
        event: Stable event id.
        context: Logging context metadata.
        payload: Optional payload dict.

        Outputs
        None.

        Side effects
        Writes to logging handlers.

        Error handling
        Raises `RuntimeError` with module and method context when emitting fails unexpectedly.

        Ties to other methods
        Thin wrapper around `StructuredLogger.log`.

        Why this exists
        Error logs capture actionable failure details.
        """
        try:
            self.log(logging.ERROR, message, event=event, context=context, payload=payload)
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "StructuredLogger.error", "Failed to emit error", exc)
            ) from exc


_log_configured = False
_log_lock = threading.Lock()


def configure_logging_once(
    redaction: RedactionConfig,
    fields: LoggingFields,
    level: int = logging.INFO,
    *,
    stream: TextIO | None = None,
) -> None:
    """
    Summary
    Configure root logging once with structured JSON output.

    Inputs
    redaction: Redaction settings for payload scrubbing.
    fields: Field name configuration for structured logs.
    level: Root log level.
    stream: Optional output stream for log lines. Defaults to `sys.stdout` when omitted.

    Outputs
    None.

    Side effects
    Configures root logging and attaches a stream handler.

    Error handling
    Raises `RuntimeError` with module and method context when logger configuration fails.

    Ties to other methods
    Called by application entrypoints to ensure consistent log formatting across modules.

    Why this exists
    Ensures all modules share the same structured logging format and redaction behavior.
    """
    try:
        global _log_configured
        with _log_lock:
            if _log_configured:
                return
            root = logging.getLogger()
            if root.handlers:
                _log_configured = True
                return
            out_stream: TextIO = sys.stdout if stream is None else stream
            handler = logging.StreamHandler(out_stream)
            handler.setFormatter(StructuredFormatter(redaction, fields))
            root.setLevel(level)
            root.addHandler(handler)
            _log_configured = True
    except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "configure_logging_once", "Failed to configure logging", exc)
        ) from exc


def new_correlation_id() -> str:
    """
    Summary
    Generate a new correlation id for traceable logging.

    Inputs
    None.

    Outputs
    A new correlation id string.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when uuid generation fails unexpectedly.

    Ties to other methods
    Used by entrypoints and diagnostics to correlate log lines.

    Why this exists
    Correlation ids make it easy to follow workflows in logs.
    """
    try:
        return uuid4().hex
    except (AttributeError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "new_correlation_id", "Failed to generate correlation id", exc)
        ) from exc


def _redact_dict(payload: Mapping[str, JsonValue], redaction: RedactionConfig) -> dict[str, JsonValue]:
    """
    Summary
    Redact sensitive keys in a payload recursively.

    Inputs
    payload: Payload mapping.
    redaction: Redaction config.

    Outputs
    Redacted payload dict.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when redaction fails unexpectedly.

    Ties to other methods
    Used by `StructuredFormatter` before logging payloads.

    Why this exists
    Prevents secrets from reaching logs.
    """
    try:
        return _redact_mapping(dict(payload), redaction)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_redact_dict", "Failed to redact payload", exc)
        ) from exc


def _redact_mapping(payload: dict[str, JsonValue], redaction: RedactionConfig) -> dict[str, JsonValue]:
    """
    Summary
    Redact a mutable payload mapping.

    Inputs
    payload: Mutable payload dict.
    redaction: Redaction config.

    Outputs
    Redacted payload dict.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when redaction fails unexpectedly.

    Ties to other methods
    Called by `_redact_dict` to process nested structures.

    Why this exists
    Keeps redaction logic separate and reusable.
    """
    try:
        out: dict[str, JsonValue] = {}
        for key, value in payload.items():
            if key.lower() in redaction.keys:
                out[key] = redaction.replacement
            elif isinstance(value, dict):
                out[key] = _redact_mapping(value, redaction)
            elif isinstance(value, list):
                out[key] = _redact_list(value, redaction)
            else:
                out[key] = value
        return out
    except (TypeError, ValueError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_redact_mapping", "Failed to redact mapping", exc)
        ) from exc


def _redact_list(values: list[JsonValue], redaction: RedactionConfig) -> list[JsonValue]:
    """
    Summary
    Redact list payloads recursively.

    Inputs
    values: List of JsonValue items.
    redaction: Redaction config.

    Outputs
    Redacted list of JsonValue items.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when redaction fails unexpectedly.

    Ties to other methods
    Used by `_redact_mapping` to handle list values.

    Why this exists
    Ensures redaction applies to nested structures too.
    """
    try:
        redacted: list[JsonValue] = []
        for value in values:
            if isinstance(value, dict):
                redacted.append(_redact_mapping(value, redaction))
            elif isinstance(value, list):
                redacted.append(_redact_list(value, redaction))
            else:
                redacted.append(value)
        return redacted
    except (TypeError, ValueError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_redact_list", "Failed to redact list", exc)) from exc
