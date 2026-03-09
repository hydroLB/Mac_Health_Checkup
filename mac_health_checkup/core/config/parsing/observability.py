from __future__ import annotations

from mac_health_checkup.core.config.models.observability import LoggingConfig
from mac_health_checkup.core.config.parsing.base import get_section
from mac_health_checkup.core.config.validation.collections import require_list_str
from mac_health_checkup.core.config.validation.primitives import require_int, require_str
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/parsing/observability.py"


def parse_logging(raw: JsonDict) -> LoggingConfig:
    """
    Summary
    Parse the `logging` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `LoggingConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by `parse_config` and ultimately by `configure_logging_once`.

    Why this exists
    Ensures logging redaction and formatting remain centrally tunable and validated.
    """
    try:
        section = get_section(raw, "logging")
        keys = tuple(require_list_str(section.get("redact_keys")))
        return LoggingConfig(
            max_lines=require_int(1, 100_000)(section.get("max_lines")),
            prefix=require_str(section.get("prefix")),
            truncate_len=require_int(0, 100_000)(section.get("truncate_len")),
            format=require_str(section.get("format")),
            redact_keys=keys,
            redact_replacement=require_str(section.get("redact_replacement")),
            correlation_id_field=require_str(section.get("correlation_id_field")),
            event_field=require_str(section.get("event_field")),
            component_field=require_str(section.get("component_field")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "parse_logging", "Failed to parse logging", exc)
        ) from exc
