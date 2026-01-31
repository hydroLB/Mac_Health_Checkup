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
    Purpose: Carry structured logging context fields.
    Ties: Used by StructuredLogger to stamp consistent metadata.
    Inputs: component identifies the source, corr_id ties events together.
    Outputs: Immutable context container.
    Side effects: None.
    Why: Ensures all logs carry consistent tracing metadata.
    """

    component: str
    corr_id: str


@dataclass(frozen=True)
class LoggingFields:
    """
    Purpose: Define field names for structured logging payloads.
    Ties: Used by StructuredFormatter and StructuredLogger.
    Inputs: event_field, corr_id_field, component_field.
    Outputs: Immutable container for log field names.
    Side effects: None.
    Why: Keeps log field names configurable and consistent.
    """

    event_field: str
    corr_id_field: str
    component_field: str


class StructuredFormatter(logging.Formatter):
    """
    Purpose: Render structured log records as JSON strings.
    Ties: Used by configure_logging_once to standardize log output.
    Inputs: Uses LogRecord data and a redaction config.
    Outputs: JSON text for each log line.
    Side effects: None.
    Why: Structured logs are easier to parse and safer to ship to log pipelines.
    """

    def __init__(self, redaction: RedactionConfig, fields: LoggingFields) -> None:
        """
        Purpose: Initialize the formatter with redaction settings.
        Ties: Used by StructuredLogger initialization.
        Inputs: redaction config with keys and replacement text, fields controls log field names.
        Outputs: None.
        Side effects: None.
        Why: Ensures secrets are redacted consistently.
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
        Purpose: Convert a LogRecord into a JSON string.
        Ties: Called by logging handlers for each record.
        Inputs: record contains message, level, and extra fields.
        Outputs: JSON log line as string.
        Side effects: None.
        Why: Ensures consistent structured output for all logs.
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
    Purpose: Emit structured logs with consistent fields and redaction.
    Ties: Used across diagnostics and app modules for observability.
    Inputs: name for logger, redaction config for payloads, fields for log field names.
    Outputs: Logging methods that emit JSON log records.
    Side effects: Writes to configured logging handlers.
    Why: Standardized logs support debugging and safe telemetry without secrets.
    """

    def __init__(self, name: str, redaction: RedactionConfig, fields: LoggingFields) -> None:
        """
        Purpose: Initialize a StructuredLogger instance.
        Ties: Called by get_structured_logger.
        Inputs: name is the logger name, redaction controls secret scrubbing, fields control log field names.
        Outputs: None.
        Side effects: None.
        Why: Wraps a standard logger with structured logging helpers.
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
        Purpose: Emit a structured log record with context and payload.
        Ties: Used by diagnostics and core utilities for consistent logging.
        Inputs: level is logging level, message is text, event is event id, context holds metadata.
        Outputs: None.
        Side effects: Writes to logging handlers.
        Why: Centralizes structured logging behavior for safety and consistency.
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
        Purpose: Emit a debug log entry.
        Ties: Used by diagnostics to trace execution details.
        Inputs: message text, event id, context metadata, optional payload.
        Outputs: None.
        Side effects: Writes to logging handlers.
        Why: Debug logs aid deep troubleshooting without cluttering info logs.
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
        Purpose: Emit an info log entry.
        Ties: Used for high level state changes and key events.
        Inputs: message text, event id, context metadata, optional payload.
        Outputs: None.
        Side effects: Writes to logging handlers.
        Why: Info logs give a readable operational timeline.
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
        Purpose: Emit a warning log entry.
        Ties: Used for recoverable problems.
        Inputs: message text, event id, context metadata, optional payload.
        Outputs: None.
        Side effects: Writes to logging handlers.
        Why: Warnings surface issues without aborting workflows.
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
        Purpose: Emit an error log entry.
        Ties: Used for failures that require attention.
        Inputs: message text, event id, context metadata, optional payload.
        Outputs: None.
        Side effects: Writes to logging handlers.
        Why: Error logs capture actionable failure details.
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
    Purpose: Generate a new correlation id for traceable logging.
    Ties: Used by entrypoints and diagnostics to correlate log lines.
    Inputs: None.
    Outputs: A new correlation id string.
    Side effects: None.
    Why: Correlation ids make it easy to follow workflows in logs.
    """
    try:
        return uuid4().hex
    except (AttributeError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "new_correlation_id", "Failed to generate correlation id", exc)
        ) from exc


def _redact_dict(payload: Mapping[str, JsonValue], redaction: RedactionConfig) -> dict[str, JsonValue]:
    """
    Purpose: Redact sensitive keys in a payload recursively.
    Ties: Used by StructuredFormatter before logging payloads.
    Inputs: payload mapping and redaction config.
    Outputs: Redacted payload dict.
    Side effects: None.
    Why: Prevents secrets from reaching logs.
    """
    try:
        return _redact_mapping(dict(payload), redaction)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_redact_dict", "Failed to redact payload", exc)
        ) from exc


def _redact_mapping(payload: dict[str, JsonValue], redaction: RedactionConfig) -> dict[str, JsonValue]:
    """
    Purpose: Redact a mutable payload mapping.
    Ties: Called by _redact_dict to process nested structures.
    Inputs: payload dict and redaction config.
    Outputs: Redacted payload dict.
    Side effects: None.
    Why: Keeps redaction logic separate and reusable.
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
    Purpose: Redact list payloads recursively.
    Ties: Used by _redact_mapping to handle list values.
    Inputs: values list and redaction config.
    Outputs: Redacted list of JsonValue items.
    Side effects: None.
    Why: Ensures redaction applies to nested structures too.
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
