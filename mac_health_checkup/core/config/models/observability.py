from __future__ import annotations

from dataclasses import dataclass

from mac_health_checkup.core.types import RedactionConfig, normalize_redaction_keys
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/models/observability.py"


@dataclass(frozen=True)
class LoggingConfig:
    """
    Summary
    Hold structured logging configuration.

    Inputs
    Log format fields, redaction settings, and sizing limits.

    Outputs
    Immutable logging configuration.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Parsed by `parse_logging` and consumed by logging setup and structured loggers.

    Why this exists
    Keeps logging behavior and redaction rules configurable.
    """

    max_lines: int
    prefix: str
    truncate_len: int
    format: str
    redact_keys: tuple[str, ...]
    redact_replacement: str
    correlation_id_field: str
    event_field: str
    component_field: str

    def redaction(self) -> RedactionConfig:
        """
        Summary
        Build a `RedactionConfig` from logging settings.

        Inputs
        None.

        Outputs
        `RedactionConfig` instance.

        Side effects
        None.

        Error handling
        Raises `ValueError` with module and method context when redaction configuration is invalid.

        Ties to other methods
        Used by `configure_logging_once` and `StructuredLogger` to enforce consistent redaction.

        Why this exists
        Keeps all redaction rules in a single config section while preserving strong typing.
        """
        try:
            return RedactionConfig(
                keys=normalize_redaction_keys(self.redact_keys),
                replacement=self.redact_replacement,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(
                format_error(MODULE_PATH, "LoggingConfig.redaction", "Invalid redaction config", exc)
            ) from exc
